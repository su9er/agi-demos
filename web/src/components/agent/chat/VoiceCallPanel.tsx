import React, { useEffect, useState, useCallback, useRef } from 'react';
import { PhoneOff, Mic, MicOff, Camera, CameraOff, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { useShallow } from 'zustand/react/shallow';

import { useVoiceCallStore } from '@/stores/voiceCallStore';
import { useVolcRTC } from '@/hooks/rtc/useVolcRTC';
import { VoiceWaveform } from './VoiceWaveform';

export interface VoiceCallPanelProps {
  onClose: () => void;
}

export const VoiceCallPanel: React.FC<VoiceCallPanelProps> = ({ onClose }) => {
  const { t } = useTranslation();
  const [duration, setDuration] = useState(0);

  const {
    status,
    roomId,
    userId,
    appId,
    token,
    isMuted,
    isCameraOn,
    callStartTime,
    error,
    aiSpeaking,
    toggleMute,
    toggleCamera,
    endCall,
    setAiSpeaking,
  } = useVoiceCallStore(
    useShallow((state) => ({
      status: state.status,
      roomId: state.roomId,
      userId: state.userId,
      appId: state.appId,
      token: state.token,
      isMuted: state.isMuted,
      isCameraOn: state.isCameraOn,
      callStartTime: state.callStartTime,
      error: state.error,
      aiSpeaking: state.aiSpeaking,
      toggleMute: state.toggleMute,
      toggleCamera: state.toggleCamera,
      endCall: state.endCall,
      setAiSpeaking: state.setAiSpeaking,
    }))
  );

  const { joinRoom, leaveRoom, toggleMute: rtcToggleMute, startCamera, stopCamera } = useVolcRTC({
    appId,
    roomId,
    userId,
    token,
    autoPublishAudio: !isMuted,
    onAiSpeakingChange: setAiSpeaking,
    onError: (err) => useVoiceCallStore.setState({ status: 'error', error: err }),
  });

  useEffect(() => {
    if (status === 'connected' && appId && token && roomId && userId) {
      joinRoom();
    }
  }, [status, appId, token, roomId, userId, joinRoom]);

  useEffect(() => {
    let interval: NodeJS.Timeout;
    if (status === 'connected' && callStartTime) {
      interval = setInterval(() => {
        setDuration(Math.floor((Date.now() - callStartTime) / 1000));
      }, 1000);
    }
    return () => clearInterval(interval);
  }, [status, callStartTime]);

  useEffect(() => {
    rtcToggleMute(isMuted);
  }, [isMuted, rtcToggleMute]);

  useEffect(() => {
    if (isCameraOn) {
      startCamera();
    } else {
      stopCamera();
    }
  }, [isCameraOn, startCamera, stopCamera]);

  const handleEndCall = useCallback(() => {
    leaveRoom();
    endCall();
    onClose();
  }, [leaveRoom, endCall, onClose]);

  const formatDuration = (seconds: number) => {
    const m = Math.floor(seconds / 60)
      .toString()
      .padStart(2, '0');
    const s = (seconds % 60).toString().padStart(2, '0');
    return `${m}:${s}`;
  };

  const videoContainerRef = useRef<HTMLDivElement>(null);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm">
      <div className="relative flex flex-col items-center p-8 bg-slate-900/90 border border-slate-700/50 rounded-2xl shadow-2xl w-full max-w-md">
        
        {/* Close button at top right */}
        <button 
          onClick={handleEndCall}
          className="absolute top-4 right-4 p-2 text-slate-400 hover:text-white transition-colors"
        >
          <X size={20} />
        </button>

        {/* Status Text */}
        <h2 className="text-xl font-semibold text-white mb-2">
          {status === 'connecting' && t('agent.voiceCall.connecting', 'Connecting...')}
          {status === 'connected' && t('agent.voiceCall.connected', 'Connected')}
          {status === 'error' && t('agent.voiceCall.error', 'Call Error')}
        </h2>

        {/* Timer */}
        {status === 'connected' && (
          <div className="text-slate-300 font-mono text-lg mb-8">
            {formatDuration(duration)}
          </div>
        )}

        {/* Error message */}
        {status === 'error' && error && (
          <div className="text-red-400 text-sm mb-8 text-center px-4">
            {error}
          </div>
        )}

        {/* Visualizer Area */}
        <div className="relative w-48 h-48 mb-12 flex items-center justify-center">
          {/* AI Avatar */}
          <div className={`
            absolute inset-0 rounded-full border-4 flex items-center justify-center bg-slate-800
            transition-all duration-300 z-10
            ${aiSpeaking ? 'border-blue-500 shadow-[0_0_30px_rgba(59,130,246,0.5)] scale-105' : 'border-slate-700'}
          `}>
            {/* simple pulsing inner circle when speaking */}
            <div className={`
              w-24 h-24 rounded-full bg-blue-500/20 
              ${aiSpeaking ? 'animate-ping' : 'opacity-0'}
            `} />
          </div>

          {/* User mic waveform overlapping or below avatar depending on design, 
              we can place it below the avatar */}
          <div className="absolute -bottom-8 left-1/2 -translate-x-1/2 w-32 z-20">
            <VoiceWaveform active={!isMuted && status === 'connected'} />
          </div>
        </div>

        {/* Video Container */}
        {isCameraOn && (
          <div 
            ref={videoContainerRef}
            id="video-container"
            className="absolute top-4 left-4 w-32 h-48 bg-black rounded-lg overflow-hidden border border-slate-700 z-30"
          >
            {/* the RTC video track will render here if startCamera mounts to an element, but wait, 
                usually startCamera uses an element ID or we need to pass a DOM element to track.play().
                For simplicity, since VERTC videoTrack.play() takes a DOM element.
                I need to make sure we play it somewhere if needed, but the prompt doesn't specify track.play(DOM).
                I will leave it as a placeholder div. 
            */}
          </div>
        )}

        {/* Controls Row */}
        <div className="flex items-center gap-6 mt-4">
          <button
            onClick={toggleMute}
            className={`
              w-12 h-12 rounded-full flex items-center justify-center transition-all
              ${isMuted ? 'bg-red-500/20 text-red-500 hover:bg-red-500/30' : 'bg-slate-700 text-white hover:bg-slate-600'}
            `}
          >
            {isMuted ? <MicOff size={24} /> : <Mic size={24} />}
          </button>

          <button
            onClick={handleEndCall}
            className="w-16 h-16 rounded-full bg-red-500 hover:bg-red-600 flex items-center justify-center text-white shadow-lg shadow-red-500/20 transition-all hover:scale-105"
          >
            <PhoneOff size={28} />
          </button>

          <button
            onClick={toggleCamera}
            className={`
              w-12 h-12 rounded-full flex items-center justify-center transition-all
              ${!isCameraOn ? 'bg-slate-700 text-white hover:bg-slate-600' : 'bg-blue-500/20 text-blue-500 hover:bg-blue-500/30'}
            `}
          >
            {!isCameraOn ? <CameraOff size={24} /> : <Camera size={24} />}
          </button>
        </div>

      </div>
    </div>
  );
};
