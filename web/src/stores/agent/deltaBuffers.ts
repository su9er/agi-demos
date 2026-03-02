/**
 * Delta buffer management for per-conversation token batching.
 *
 * Extracted from agentV3.ts to reduce file size and improve maintainability.
 * Buffers batch rapid token/thought/act updates to reduce re-renders.
 */

import type { ActDeltaEventData } from '../../types/agent';

/**
 * Token delta batching configuration
 * Batches rapid token updates to reduce re-renders and improve performance
 */
export const TOKEN_BATCH_INTERVAL_MS = 50; // Batch tokens every 50ms for smooth streaming
export const THOUGHT_BATCH_INTERVAL_MS = 50; // Same for thought deltas

/**
 * Per-conversation delta buffer state
 * Using Map to isolate buffers per conversation, preventing cross-conversation contamination
 */
export interface DeltaBufferState {
  textDeltaBuffer: string;
  textDeltaFlushTimer: ReturnType<typeof setTimeout> | null;
  thoughtDeltaBuffer: string;
  thoughtDeltaFlushTimer: ReturnType<typeof setTimeout> | null;
  actDeltaBuffer: ActDeltaEventData | null;
  actDeltaFlushTimer: ReturnType<typeof setTimeout> | null;
}

const deltaBuffers = new Map<string, DeltaBufferState>();

/**
 * Get or create delta buffer state for a conversation
 */
export function getDeltaBuffer(conversationId: string): DeltaBufferState {
  let buffer = deltaBuffers.get(conversationId);
  if (!buffer) {
    buffer = {
      textDeltaBuffer: '',
      textDeltaFlushTimer: null,
      thoughtDeltaBuffer: '',
      thoughtDeltaFlushTimer: null,
      actDeltaBuffer: null,
      actDeltaFlushTimer: null,
    };
    deltaBuffers.set(conversationId, buffer);
  }
  return buffer;
}

/**
 * Clear delta buffers for a specific conversation
 * IMPORTANT: Call this before starting any new streaming session to prevent
 * stale buffer content from being flushed into the new session
 */
export function clearDeltaBuffers(conversationId: string): void {
  const buffer = deltaBuffers.get(conversationId);
  if (buffer) {
    if (buffer.textDeltaFlushTimer) {
      clearTimeout(buffer.textDeltaFlushTimer);
      buffer.textDeltaFlushTimer = null;
    }
    if (buffer.thoughtDeltaFlushTimer) {
      clearTimeout(buffer.thoughtDeltaFlushTimer);
      buffer.thoughtDeltaFlushTimer = null;
    }
    if (buffer.actDeltaFlushTimer) {
      clearTimeout(buffer.actDeltaFlushTimer);
      buffer.actDeltaFlushTimer = null;
    }
    buffer.textDeltaBuffer = '';
    buffer.thoughtDeltaBuffer = '';
    buffer.actDeltaBuffer = null;
  }
}

/**
 * Clear all delta buffers across all conversations
 * Used when switching conversations or on cleanup
 */
export function clearAllDeltaBuffers(): void {
  deltaBuffers.forEach((_buffer, conversationId) => {
    clearDeltaBuffers(conversationId);
  });
  deltaBuffers.clear();
}

/**
 * Delete a delta buffer entry for a conversation (after cleanup)
 */
export function deleteDeltaBuffer(conversationId: string): void {
  deltaBuffers.delete(conversationId);
}
