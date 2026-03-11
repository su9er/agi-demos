/**
 * useVoiceChat - WebSocket-based voice chat hook.
 *
 * Manages the full lifecycle of a voice chat session:
 *  1. WebSocket connection to the backend voice endpoint
 *  2. Microphone capture via AudioWorklet (raw PCM Int16 at 16kHz)
 *  3. Dispatching incoming text frames (ASR, agent, TTS events) to callbacks
 *  4. Forwarding incoming binary frames (TTS MP3 audio) to a callback
 *
 * The caller is responsible for connection lifecycle (no auto-reconnect).
 */

import { useState, useRef, useCallback, useEffect } from 'react';

import { createWebSocketUrl } from '@/services/client/urlUtils';
import { getAuthToken } from '@/utils/tokenResolver';

export interface UseVoiceChatOptions {
  projectId: string;
  conversationId: string;
  onAsrInterim?: ((text: string) => void) | undefined;
  onAsrFinal?: ((text: string) => void) | undefined;
  onAgentToken?: ((token: string) => void) | undefined;
  onAgentComplete?: ((content: string) => void) | undefined;
  onTtsStart?: (() => void) | undefined;
  onTtsEnd?: (() => void) | undefined;
  onTtsAudio?: ((data: ArrayBuffer) => void) | undefined;
  onError?: ((error: string) => void) | undefined;
  speaker?: string | undefined;
}

export interface UseVoiceChatReturn {
  isConnected: boolean;
  isRecording: boolean;
  connect: () => void;
  disconnect: () => void;
  startRecording: () => Promise<void>;
  stopRecording: () => void;
}

const DEFAULT_SPEAKER = 'zh_female_tianmeixiaoyuan_moon_bigtts';

interface VoiceTextMessage {
  type: string;
  text?: string;
  content?: string;
  message?: string;
}

export const useVoiceChat = (options: UseVoiceChatOptions): UseVoiceChatReturn => {
  const [isConnected, setIsConnected] = useState(false);
  const [isRecording, setIsRecording] = useState(false);

  const wsRef = useRef<WebSocket | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const workletNodeRef = useRef<AudioWorkletNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const sourceNodeRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const isMountedRef = useRef(true);

  // Store the latest options in a ref so callbacks always read current values
  // without causing re-creation of the memoized functions.
  const optionsRef = useRef(options);
  optionsRef.current = options;

  /**
   * Handle an incoming text (JSON) message from the WebSocket.
   */
  const handleTextMessage = useCallback((data: string) => {
    const opts = optionsRef.current;
    let parsed: VoiceTextMessage;
    try {
      parsed = JSON.parse(data) as VoiceTextMessage;
    } catch {
      console.error('Failed to parse voice WS message:', data);
      return;
    }

    switch (parsed.type) {
      case 'asr_interim':
        if (parsed.text !== undefined) {
          opts.onAsrInterim?.(parsed.text);
        }
        break;
      case 'asr_final':
        if (parsed.text !== undefined) {
          opts.onAsrFinal?.(parsed.text);
        }
        break;
      case 'agent_token':
        if (parsed.content !== undefined) {
          opts.onAgentToken?.(parsed.content);
        }
        break;
      case 'agent_complete':
        if (parsed.content !== undefined) {
          opts.onAgentComplete?.(parsed.content);
        }
        break;
      case 'tts_start':
        opts.onTtsStart?.();
        break;
      case 'tts_end':
        opts.onTtsEnd?.();
        break;
      case 'error':
        if (parsed.message !== undefined) {
          opts.onError?.(parsed.message);
        }
        break;
      default:
        // Unknown message type -- ignore
        break;
    }
  }, []);

  /**
   * Stop microphone capture and tear down audio nodes.
   */
  const teardownAudio = useCallback(() => {
    if (workletNodeRef.current) {
      workletNodeRef.current.port.onmessage = null;
      workletNodeRef.current.disconnect();
      workletNodeRef.current = null;
    }

    if (sourceNodeRef.current) {
      sourceNodeRef.current.disconnect();
      sourceNodeRef.current = null;
    }

    if (mediaStreamRef.current) {
      for (const track of mediaStreamRef.current.getTracks()) {
        track.stop();
      }
      mediaStreamRef.current = null;
    }

    if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
      audioContextRef.current.close().catch(() => {
        // Ignore close errors during teardown
      });
      audioContextRef.current = null;
    }
  }, []);

  /**
   * Disconnect the WebSocket and clean up all resources.
   */
  const disconnect = useCallback(() => {
    setIsRecording(false);
    teardownAudio();

    if (wsRef.current) {
      // Prevent onclose from firing further logic after explicit disconnect
      const ws = wsRef.current;
      wsRef.current = null;
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close();
      }
    }

    setIsConnected(false);
  }, [teardownAudio]);

  /**
   * Open a WebSocket connection to the backend voice endpoint.
   */
  const connect = useCallback(() => {
    // Avoid double-connect
    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const token = getAuthToken();
    if (!token) {
      optionsRef.current.onError?.('No auth token available');
      return;
    }

    const wsUrl = createWebSocketUrl('/voice/chat', {
      token,
      project_id: optionsRef.current.projectId,
      conversation_id: optionsRef.current.conversationId,
    });

    const ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';
    wsRef.current = ws;

    ws.onopen = () => {
      if (!isMountedRef.current) return;
      setIsConnected(true);

      // Send voice configuration as the first message
      const config = {
        type: 'voice_config',
        sample_rate: 16000,
        speaker: optionsRef.current.speaker ?? DEFAULT_SPEAKER,
      };
      ws.send(JSON.stringify(config));
    };

    ws.onmessage = (event: MessageEvent) => {
      if (!isMountedRef.current) return;

      if (typeof event.data === 'string') {
        handleTextMessage(event.data);
      } else if (event.data instanceof ArrayBuffer) {
        // Binary frame: TTS MP3 audio
        optionsRef.current.onTtsAudio?.(event.data);
      }
    };

    ws.onerror = () => {
      if (!isMountedRef.current) return;
      optionsRef.current.onError?.('WebSocket connection error');
    };

    ws.onclose = () => {
      if (!isMountedRef.current) return;
      wsRef.current = null;
      setIsConnected(false);
      setIsRecording(false);
    };
  }, [handleTextMessage]);

  /**
   * Start capturing microphone audio and streaming PCM data over the WebSocket.
   */
  const startRecording = useCallback(async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      optionsRef.current.onError?.('WebSocket is not connected');
      return;
    }

    try {
      // Create AudioContext with the browser default sample rate.
      // The AudioWorklet handles resampling to 16kHz.
      const ctx = new AudioContext();
      audioContextRef.current = ctx;

      // Load the worklet module
      await ctx.audioWorklet.addModule('/audio-processor.js');

      // Create the worklet node and configure it with the actual sample rate
      const workletNode = new AudioWorkletNode(ctx, 'audio-processor');
      workletNode.port.postMessage({ type: 'config', sampleRate: ctx.sampleRate });
      workletNodeRef.current = workletNode;

      // Forward PCM chunks to the WebSocket as binary frames
      workletNode.port.onmessage = (event: MessageEvent) => {
        const ws = wsRef.current;
        if (ws && ws.readyState === WebSocket.OPEN && event.data instanceof Int16Array) {
          ws.send(event.data.buffer);
        }
      };

      // Acquire microphone
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      });
      mediaStreamRef.current = stream;

      // Connect: microphone source -> worklet node
      const source = ctx.createMediaStreamSource(stream);
      sourceNodeRef.current = source;
      source.connect(workletNode);

      if (isMountedRef.current) {
        setIsRecording(true);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to start recording';
      optionsRef.current.onError?.(message);
      teardownAudio();
    }
  }, [teardownAudio]);

  /**
   * Stop recording (but keep the WebSocket open).
   */
  const stopRecording = useCallback(() => {
    teardownAudio();
    if (isMountedRef.current) {
      setIsRecording(false);
    }
  }, [teardownAudio]);

  // Cleanup on unmount
  useEffect(() => {
    isMountedRef.current = true;

    return () => {
      isMountedRef.current = false;
      disconnect();
    };
  }, [disconnect]);

  return {
    isConnected,
    isRecording,
    connect,
    disconnect,
    startRecording,
    stopRecording,
  };
};
