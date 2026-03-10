import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { useShallow } from 'zustand/react/shallow';

import { volcengineRTCService } from '@/services/volcengineRTCService';

export type CallStatus = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'error';

export interface VoiceCallState {
  // State
  status: CallStatus;
  roomId: string | null;
  userId: string | null;
  appId: string | null;
  token: string | null;
  isMuted: boolean;
  isCameraOn: boolean;
  callStartTime: number | null; // Date.now()
  error: string | null;
  aiSpeaking: boolean; // true when AI bot audio track is active

  // Actions
  startCall: (conversationId: string, userId: string) => Promise<void>;
  endCall: () => Promise<void>;
  toggleMute: () => void;
  toggleCamera: () => void;
  setAiSpeaking: (speaking: boolean) => void;
  reset: () => void;
}

const initialState = {
  status: 'idle' as CallStatus,
  roomId: null,
  userId: null,
  appId: null,
  token: null,
  isMuted: false,
  isCameraOn: false,
  callStartTime: null,
  error: null,
  aiSpeaking: false,
};

export const useVoiceCallStore = create<VoiceCallState>()(
  devtools(
    (set, get) => ({
      ...initialState,

      startCall: async (conversationId: string, userId: string) => {
        set({ status: 'connecting', error: null });
        const roomId = `rtc_${conversationId}`;

        try {
          // 1. Get token
          const tokenRes = await volcengineRTCService.getToken({
            room_id: roomId,
            user_id: userId,
          });

          // 2. Start AI bot
          await volcengineRTCService.startVoiceChat({
            room_id: roomId,
            user_id: userId,
          });

          set({
            status: 'connected',
            roomId,
            userId,
            appId: tokenRes.app_id,
            token: tokenRes.token,
            callStartTime: Date.now(),
          });
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : 'Failed to start call';
          set({ status: 'error', error: errorMessage });
        }
      },

      endCall: async () => {
        const { roomId, userId } = get();
        if (roomId && userId) {
          try {
            await volcengineRTCService.stopVoiceChat({
              room_id: roomId,
              user_id: userId,
            });
          } catch (error) {
            console.error('Error stopping voice chat:', error);
          }
        }
        set({ ...initialState });
      },

      toggleMute: () => set((state) => ({ isMuted: !state.isMuted })),
      toggleCamera: () => set((state) => ({ isCameraOn: !state.isCameraOn })),
      setAiSpeaking: (speaking: boolean) => set({ aiSpeaking: speaking }),
      reset: () => set({ ...initialState }),
    }),
    { name: 'voice-call-store' }
  )
);

// Single-value selectors
export const useVoiceCallStatus = () => useVoiceCallStore((state) => state.status);
export const useVoiceCallError = () => useVoiceCallStore((state) => state.error);
export const useVoiceCallIsMuted = () => useVoiceCallStore((state) => state.isMuted);
export const useVoiceCallIsCameraOn = () => useVoiceCallStore((state) => state.isCameraOn);
export const useVoiceCallAiSpeaking = () => useVoiceCallStore((state) => state.aiSpeaking);
export const useVoiceCallStartTime = () => useVoiceCallStore((state) => state.callStartTime);

// Action selectors
export const useVoiceCallActions = () =>
  useVoiceCallStore(
    useShallow((state) => ({
      startCall: state.startCall,
      endCall: state.endCall,
      toggleMute: state.toggleMute,
      toggleCamera: state.toggleCamera,
      setAiSpeaking: state.setAiSpeaking,
      reset: state.reset,
    }))
  );
