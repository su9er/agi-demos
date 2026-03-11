# Volcengine RTC Server SDK Python Integration Guide

## 1. Problem Statement
The Volcengine RTC Server SDK is a native Linux library (C++) optimized for high-throughput audio/video processing. Directly wrapping it in Python using `ctypes` or `SWIG` can introduce:
- **GIL (Global Interpreter Lock)** contention during real-time PCM audio callbacks.
- **Complexity** in memory management of raw audio buffers between C++ and Python.
- **Stability** issues if the Python interpreter crashes during a native callback.

## 2. Recommended Pattern: The Sidecar (Bridge) Pattern
Instead of a direct binding, use a **C++ Sidecar Process** that handles the RTC session and communicates with the Python Agent via **IPC**.

### Architecture:
```text
[Volcengine RTC Room] <---(PCM/Video)---> [C++ Sidecar] <---(Unix Domain Socket/Shared Memory)---> [Python Agent]
                                          |                                                        |
                                          |-- onUserAudioFrame (Subscribe)                         |-- ASR V3 WebSocket
                                          |-- pushExternalAudioFrame (Publish)                     |-- TTS V3 WebSocket
                                          |                                                        |-- Maas (LLM) Service
```

## 3. Implementation Details

### A. The C++ Sidecar (Audio Bridge)
- **Engine Initialization**:
  ```cpp
  rtc_engine_ = createRtcEngine();
  rtc_engine_->setAudioSourceType(kAudioSourceTypeExternal); // Publish PCM directly
  rtc_engine_->setAudioPlaybackDevice(kAudioPlaybackDeviceExternal); // Subscribe to PCM
  ```
- **Capturing PCM (Subscription)**:
  Implement `IRtcEngineEventHandler::onUserAudioFrame`. Write the raw PCM (typically 16-bit, 16kHz or 48kHz, Mono) to a **Unix Domain Socket** or a **Circular Buffer**.
- **Injecting PCM (Publication)**:
  Listen for incoming bytes on the socket from Python. Use `rtc_engine_->pushExternalAudioFrame` to send them to the room.

### B. The Python Agent
- **ASR Pipeline**: Reads PCM bytes from the socket and feeds them into the `VolcengineASRV3` WebSocket.
- **TTS Pipeline**: Receives synthesized PCM chunks from `VolcengineTTSV3` and writes them directly to the socket.

## 4. Alternative: Cython Binding
If a single process is mandatory, **Cython** is the preferred path.
- **Why?** Cython allows releasing the GIL (`with nogil:`) inside the RTC callbacks, ensuring that Python code execution doesn't block the high-frequency audio interrupt.
- **Example Strategy**: Use Cython's `cpdef` classes to map the `IRtcEngineEventHandler` to a Python object that implements a simple `on_audio(bytes)` method.

