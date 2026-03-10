import { httpClient } from './client/httpClient';

// Types matching backend Pydantic models
interface TokenRequest {
  room_id: string;
  user_id: string;
  expire_time?: number;
}

interface TokenResponse {
  token: string;
  app_id: string;
}

interface VoiceChatStartRequest {
  room_id: string;
  user_id: string;
  model_endpoint_id?: string;
  welcome_message?: string;
  voice_type?: string;
  system_messages?: string[];
}

interface VoiceChatStopRequest {
  room_id: string;
  user_id: string;
}

interface VoiceChatStartResponse {
  [key: string]: unknown;
}

// IMPORTANT: paths are relative to /api/v1 (httpClient baseURL)
const BASE_URL = '/volcengine';

export const volcengineRTCService = {
  getToken: (data: TokenRequest): Promise<TokenResponse> =>
    httpClient.post<TokenResponse>(`${BASE_URL}/token`, data),

  startVoiceChat: (data: VoiceChatStartRequest): Promise<VoiceChatStartResponse> =>
    httpClient.post<VoiceChatStartResponse>(`${BASE_URL}/voice-chat/start`, data),

  stopVoiceChat: (data: VoiceChatStopRequest): Promise<void> =>
    httpClient.post(`${BASE_URL}/voice-chat/stop`, data),
};
