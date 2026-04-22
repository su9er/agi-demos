/** Agent session identity & status — pure types. */
import type { ProjectId } from './project';

export type ConversationId = string & { readonly __brand: 'ConversationId' };

export type SessionStatus =
  | 'idle'
  | 'thinking'
  | 'acting'
  | 'waiting_hitl'
  | 'completed'
  | 'failed';

export interface SessionRef {
  conversationId: ConversationId;
  projectId: ProjectId;
  status: SessionStatus;
}

export function conversationIdOf(raw: string): ConversationId {
  return raw as ConversationId;
}
