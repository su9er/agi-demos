import { useEffect } from 'react';

import { useWorkspaceStore } from '@/stores/workspace';

import { unifiedEventService } from '@/services/unifiedEventService';

/**
 * Subscribes to SSE events for a given workspace and routes them
 * to the appropriate workspace store handlers.
 */
export function useBlackboardSSE(workspaceId: string | null): void {
  useEffect(() => {
    if (!workspaceId) {
      return;
    }

    const store = useWorkspaceStore.getState();
    const unsubscribe = unifiedEventService.subscribeWorkspace(workspaceId, (event) => {
      const type = event.type;
      const data = event.data as Record<string, unknown>;

      if (type.startsWith('workspace.presence.')) {
        store.handlePresenceEvent({ type, data });
      } else if (type.startsWith('workspace.agent_status.')) {
        store.handleAgentStatusEvent({ type, data });
      } else if (type.startsWith('workspace_task_') || type === 'workspace_task_assigned') {
        store.handleTaskEvent({ type, data });
      } else if (type.startsWith('blackboard_')) {
        store.handleBlackboardEvent({ type, data });
      } else if (type === 'workspace_message_created') {
        store.handleChatEvent({ type, data });
      } else if (type === 'workspace_member_joined' || type === 'workspace_member_left') {
        store.handleMemberEvent({ type, data });
      } else if (type === 'workspace_updated' || type === 'workspace_deleted') {
        store.handleWorkspaceLifecycleEvent({ type, data });
      } else if (type === 'workspace_agent_bound' || type === 'workspace_agent_unbound') {
        store.handleAgentBindingEvent({ type, data });
      } else if (type === 'topology_updated' || type.startsWith('workspace.topology.')) {
        store.handleTopologyEvent({ type, data });
      }
    });

    return () => {
      unsubscribe();
    };
  }, [workspaceId]);
}
