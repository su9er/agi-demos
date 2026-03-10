import { useEffect, useRef, useCallback } from 'react';
import VERTC, { MediaType, RoomProfileType, IRTCEngine } from '@volcengine/rtc';

interface UseVolcRTCOptions {
  appId: string | null;
  roomId: string | null;
  userId: string | null;
  token: string | null;
  autoPublishAudio?: boolean;
  onAiSpeakingChange?: (speaking: boolean) => void;
  onError?: (error: string) => void;
}

interface UseVolcRTCReturn {
  isJoined: boolean; // from a ref, not state to avoid re-renders
  joinRoom: () => Promise<void>;
  leaveRoom: () => void;
  toggleMute: (muted: boolean) => void;
  startCamera: () => Promise<void>;
  stopCamera: () => void;
  engineRef: React.MutableRefObject<IRTCEngine | null>;
}

export const useVolcRTC = ({
  appId,
  roomId,
  userId,
  token,
  autoPublishAudio = true,
  onAiSpeakingChange,
  onError,
}: UseVolcRTCOptions): UseVolcRTCReturn => {
  const engineRef = useRef<IRTCEngine | null>(null);
  const isJoinedRef = useRef(false);

  const initEngine = useCallback(() => {
    if (!appId) return null;
    if (!engineRef.current) {
      engineRef.current = VERTC.createEngine(appId);

      engineRef.current.on(VERTC.events.onUserPublishStream, async ({ userId: remoteUid, mediaType }: { userId: string; mediaType: MediaType }) => {
        if (!engineRef.current) return;
        
        if (mediaType & MediaType.AUDIO) {
          try {
            await engineRef.current.subscribeStream(remoteUid, MediaType.AUDIO);
            
            onAiSpeakingChange?.(true);
          } catch (err) {
            console.error('Failed to subscribe to audio', err);
          }
        }
        if (mediaType & MediaType.VIDEO) {
          try {
            await engineRef.current.subscribeStream(remoteUid, MediaType.VIDEO);
          } catch (err) {
            console.error('Failed to subscribe to video', err);
          }
        }
      });

      engineRef.current.on(VERTC.events.onUserUnpublishStream, ({ mediaType }: { mediaType: MediaType }) => {
        if (mediaType & MediaType.AUDIO) {
          onAiSpeakingChange?.(false);
        }
      });
      
      engineRef.current.on(VERTC.events.onUserJoined, () => {
         // handle if needed
      });
      
      engineRef.current.on(VERTC.events.onUserLeave, () => {
         onAiSpeakingChange?.(false);
      });
    }
    return engineRef.current;
  }, [appId, onAiSpeakingChange]);

  const joinRoom = useCallback(async () => {
    if (!appId || !roomId || !userId || !token) {
      onError?.('Missing required connection parameters');
      return;
    }

    const engine = initEngine();
    if (!engine) return;

    try {
      await engine.joinRoom(
        token,
        roomId,
        { userId },
        { 
          isAutoPublish: autoPublishAudio, 
          isAutoSubscribeAudio: true,
          roomProfileType: RoomProfileType.chat 
        }
      );
      isJoinedRef.current = true;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to join room';
      onError?.(errorMessage);
    }
  }, [appId, roomId, userId, token, autoPublishAudio, initEngine, onError]);

  const leaveRoom = useCallback(() => {
    if (engineRef.current) {
      engineRef.current.leaveRoom();
      VERTC.destroyEngine(engineRef.current);
      engineRef.current = null;
    }
    isJoinedRef.current = false;
    onAiSpeakingChange?.(false);
  }, [onAiSpeakingChange]);

  const toggleMute = useCallback((muted: boolean) => {
    if (engineRef.current && isJoinedRef.current) {
      if (muted) {
        engineRef.current.unpublishStream(MediaType.AUDIO);
      } else {
        engineRef.current.publishStream(MediaType.AUDIO);
      }
    }
  }, []);

  const startCamera = useCallback(async () => {
    if (engineRef.current && isJoinedRef.current) {
      try {
        await engineRef.current.startVideoCapture();
        await engineRef.current.publishStream(MediaType.VIDEO);
      } catch (err: unknown) {
        const errorMessage = err instanceof Error ? err.message : 'Failed to start camera';
        onError?.(errorMessage);
      }
    }
  }, [onError]);

  const stopCamera = useCallback(() => {
    if (engineRef.current && isJoinedRef.current) {
      engineRef.current.stopVideoCapture();
    }
  }, []);

  useEffect(() => {
    return () => {
      leaveRoom();
    };
  }, [leaveRoom]);

  return {
    get isJoined() { return isJoinedRef.current; },
    joinRoom,
    leaveRoom,
    toggleMute,
    startCamera,
    stopCamera,
    engineRef,
  };
};
