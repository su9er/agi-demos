import { useRef, useCallback } from 'react';

const MAX_WIDTH = 640;
const JPEG_QUALITY = 0.7;

export interface FrameCaptureResult {
  /** Base64 data URL (JPEG) ready for image_url content */
  dataUrl: string;
  /** Width of the captured frame */
  width: number;
  /** Height of the captured frame */
  height: number;
}

export interface UseFrameCaptureReturn {
  /** Capture a single frame from the video element inside the given container */
  captureFrame: (containerId: string) => FrameCaptureResult | null;
  /** Whether a capture is in progress */
  isCapturing: boolean;
}

/**
 * Hook to capture the current frame from a <video> element as a JPEG data URL.
 * Uses a hidden canvas for the conversion. Does not add any npm dependencies.
 */
export function useFrameCapture(): UseFrameCaptureReturn {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const isCapturingRef = useRef(false);

  const captureFrame = useCallback((containerId: string): FrameCaptureResult | null => {
    const container = document.getElementById(containerId);
    if (!container) return null;

    const video = container.querySelector('video');
    if (!video || video.videoWidth === 0 || video.videoHeight === 0) return null;

    isCapturingRef.current = true;
    try {
      // Lazily create canvas (reuse across calls)
      if (!canvasRef.current) {
        canvasRef.current = document.createElement('canvas');
      }
      const canvas = canvasRef.current;

      // Scale down to MAX_WIDTH, preserving aspect ratio
      const scale = video.videoWidth > MAX_WIDTH ? MAX_WIDTH / video.videoWidth : 1;
      const width = Math.round(video.videoWidth * scale);
      const height = Math.round(video.videoHeight * scale);

      canvas.width = width;
      canvas.height = height;

      const ctx = canvas.getContext('2d');
      if (!ctx) return null;

      ctx.drawImage(video, 0, 0, width, height);
      const dataUrl = canvas.toDataURL('image/jpeg', JPEG_QUALITY);

      return { dataUrl, width, height };
    } finally {
      isCapturingRef.current = false;
    }
  }, []);

  return { captureFrame, isCapturing: isCapturingRef.current };
}
