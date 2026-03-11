/**
 * AudioWorklet Processor for voice capture.
 *
 * Captures microphone input, resamples from the browser native sample rate
 * (typically 48000 Hz) down to 16000 Hz using linear interpolation, converts
 * Float32 samples to Int16, and posts buffered chunks of 4096 Int16 samples
 * to the main thread via MessagePort.
 *
 * Configuration:
 *   Send { type: 'config', sampleRate: <number> } via port.postMessage
 *   to set the actual browser sample rate (defaults to 48000).
 *
 * Output:
 *   Int16Array of 4096 samples per message.
 */

class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    this.sampleRate = 48000;
    this.targetSampleRate = 16000;
    this.bufferSize = 4096;

    this.outputBuffer = new Int16Array(this.bufferSize);
    this.outputIndex = 0;

    // Fractional position in the input stream for linear interpolation
    this.resamplePosition = 0;

    // Previous sample for interpolation across process() boundaries
    this.previousSample = 0;

    this.port.onmessage = (event) => {
      if (event.data && event.data.type === 'config') {
        if (typeof event.data.sampleRate === 'number' && event.data.sampleRate > 0) {
          this.sampleRate = event.data.sampleRate;
        }
      }
    };
  }

  /**
   * Convert a Float32 sample [-1, 1] to Int16 [-32768, 32767].
   */
  float32ToInt16(sample) {
    const clamped = Math.max(-1, Math.min(1, sample));
    return clamped < 0
      ? Math.max(-32768, Math.round(clamped * 32768))
      : Math.min(32767, Math.round(clamped * 32767));
  }

  process(inputs, _outputs, _parameters) {
    const input = inputs[0];
    if (!input || input.length === 0) {
      return true;
    }

    const channelData = input[0];
    if (!channelData || channelData.length === 0) {
      return true;
    }

    const ratio = this.sampleRate / this.targetSampleRate;
    const inputLength = channelData.length;

    // Walk through the input using fractional positioning for linear interpolation
    while (this.resamplePosition < inputLength) {
      const intIndex = Math.floor(this.resamplePosition);
      const fraction = this.resamplePosition - intIndex;

      // Current sample
      const current = channelData[intIndex];

      // Next sample: use next element if available, otherwise use current
      const next = intIndex + 1 < inputLength
        ? channelData[intIndex + 1]
        : current;

      // Linear interpolation between current and next
      const interpolated = current + fraction * (next - current);

      this.outputBuffer[this.outputIndex] = this.float32ToInt16(interpolated);
      this.outputIndex++;

      // Flush the buffer when full
      if (this.outputIndex >= this.bufferSize) {
        this.port.postMessage(this.outputBuffer.slice());
        this.outputIndex = 0;
      }

      this.resamplePosition += ratio;
    }

    // Save the last sample for potential cross-boundary interpolation
    this.previousSample = channelData[inputLength - 1];

    // Adjust position relative to the next process() call
    this.resamplePosition -= inputLength;

    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);
