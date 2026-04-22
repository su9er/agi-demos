/**
 * Participants service — Track B P2-3 phase-2.
 *
 * Client for the multi-agent conversation participant endpoints:
 *   GET    /agent/conversations/{id}/participants        — list roster
 *   POST   /agent/conversations/{id}/participants        — add agent
 *   DELETE /agent/conversations/{id}/participants/{agent_id}
 */

import { httpClient } from './client/httpClient';

export type ConversationMode =
  | 'single_agent'
  | 'multi_agent_shared'
  | 'multi_agent_isolated'
  | 'autonomous';

export interface RosterResponse {
  conversation_id: string;
  conversation_mode: ConversationMode;
  effective_mode: ConversationMode;
  participant_agents: string[];
  coordinator_agent_id: string | null;
  focused_agent_id: string | null;
}

export interface AddParticipantRequest {
  agent_id: string;
  role?: string;
}

export interface RemoveParticipantOptions {
  reason?: string;
}

const base = (conversationId: string) =>
  `/agent/conversations/${conversationId}/participants`;

export const participantsService = {
  async listRoster(conversationId: string): Promise<RosterResponse> {
    return httpClient.get<RosterResponse>(base(conversationId));
  },

  async addParticipant(
    conversationId: string,
    payload: AddParticipantRequest
  ): Promise<RosterResponse> {
    return httpClient.post<RosterResponse>(base(conversationId), payload);
  },

  async removeParticipant(
    conversationId: string,
    agentId: string,
    options?: RemoveParticipantOptions
  ): Promise<RosterResponse> {
    return httpClient.delete<RosterResponse>(
      `${base(conversationId)}/${encodeURIComponent(agentId)}`,
      options?.reason ? { data: { reason: options.reason } } : undefined
    );
  },
};
