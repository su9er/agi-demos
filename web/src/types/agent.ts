/**
 * Agent types for React-mode Agent functionality.
 *
 * This file is a barrel re-export from the split modules in ./agent/.
 * All types are defined in their respective domain-specific files:
 *   - core.ts: Base entities (Message, Conversation, etc.)
 *   - tasks.ts: Agent task system types
 *   - events.ts: SSE event types and data interfaces
 *   - timeline.ts: Timeline event types
 *   - config.ts: Configuration types (tenant, tool composition, patterns)
 *   - workflow.ts: Workflow pattern and skill types
 *   - execution.ts: Execution tracking types
 *   - streaming.ts: Stream handler and service interfaces
 *   - service.ts: Service interfaces
 */
export * from './agent/index';
