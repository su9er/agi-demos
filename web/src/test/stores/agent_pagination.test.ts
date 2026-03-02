/**
 * Unit tests for Agent store pagination functionality (agentV3).
 *
 * Tests verify time-based backward pagination support:
 * 1. loadMessages sets pagination metadata (earliestTimeUs, hasEarlier)
 * 2. loadEarlierMessages fetches older messages before earliestTimeUs
 * 3. Guard conditions prevent redundant loads
 * 4. setActiveConversation resets pagination state
 */

import { act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { useAgentV3Store as useAgentStore } from '../../stores/agentV3';

import type { TimelineEvent } from '../../types/agent';

// Mock agent service
const mockGetConversationMessages = vi.fn();
vi.mock('../../services/agentService', () => ({
  agentService: {
    getConversationMessages: (...args: unknown[]) => mockGetConversationMessages(...args),
    chat: vi.fn(),
    createConversation: vi.fn(),
    listConversations: vi.fn(),
    getExecutionStatus: vi.fn().mockResolvedValue(null),
  },
}));

// Mock dynamic imports used by loadMessages
vi.mock('../../stores/contextStore', () => ({
  useContextStore: {
    getState: () => ({
      fetchContextStatus: vi.fn().mockResolvedValue(null),
    }),
  },
}));

vi.mock('../../services/planService', () => ({
  planService: {
    getMode: vi.fn().mockResolvedValue(null),
  },
}));

vi.mock('../../services/client/httpClient', () => ({
  httpClient: {
    get: vi.fn().mockResolvedValue(null),
  },
}));

describe('Agent Store Pagination (agentV3)', () => {
  beforeEach(() => {
    // Reset store to initial state
    useAgentStore.setState({
      conversations: [],
      activeConversationId: null,
      conversationStates: new Map(),
      timeline: [],
      messages: [],
      isLoadingHistory: false,
      isLoadingEarlier: false,
      hasEarlier: false,
      earliestTimeUs: null,
      earliestCounter: null,
      isStreaming: false,
      streamStatus: 'idle',
      error: null,
      agentState: 'idle',
      currentThought: '',
      streamingThought: '',
      isThinkingStreaming: false,
      isPlanMode: false,
      pendingClarification: null,
      pendingDecision: null,
      pendingEnvVarRequest: null,
    });
    vi.clearAllMocks();
  });

  describe('loadMessages - initial load', () => {
    it('should set time-based pagination metadata on initial load', async () => {
      // Arrange
      const mockTimeline: TimelineEvent[] = [
        {
          id: '1',
          type: 'user_message',
          sequenceNumber: 1,
          timestamp: 1000,
          content: 'Hello',
          role: 'user',
          eventTimeUs: 1000000,
          eventCounter: 1,
        } as TimelineEvent,
        {
          id: '2',
          type: 'assistant_message',
          sequenceNumber: 2,
          timestamp: 2000,
          content: 'Hi',
          role: 'assistant',
          eventTimeUs: 2000000,
          eventCounter: 2,
        } as TimelineEvent,
        {
          id: '3',
          type: 'user_message',
          sequenceNumber: 3,
          timestamp: 3000,
          content: 'How are you?',
          role: 'user',
          eventTimeUs: 3000000,
          eventCounter: 3,
        } as TimelineEvent,
      ];
      const mockResponse = {
        conversationId: 'conv-1',
        timeline: mockTimeline,
        total: 3,
        has_more: true,
        first_time_us: 1000000,
        first_counter: 1,
        last_time_us: 3000000,
        last_counter: 3,
      };
      mockGetConversationMessages.mockResolvedValue(mockResponse);

      // Set active conversation so loadMessages proceeds
      useAgentStore.setState({ activeConversationId: 'conv-1' });

      // Act
      await act(async () => {
        await useAgentStore.getState().loadMessages('conv-1', 'project-1');
      });

      // Assert
      const state = useAgentStore.getState();
      expect(state.timeline.length).toBeGreaterThanOrEqual(3);
      expect(state.hasEarlier).toBe(true);
      expect(state.earliestTimeUs).toBe(1000000);
      expect(state.earliestCounter).toBe(1);
      expect(state.isLoadingHistory).toBe(false);
    });

    it('should handle empty timeline response', async () => {
      // Arrange
      const mockResponse = {
        conversationId: 'conv-1',
        timeline: [],
        total: 0,
        has_more: false,
        first_time_us: null,
        first_counter: null,
        last_time_us: null,
        last_counter: null,
      };
      mockGetConversationMessages.mockResolvedValue(mockResponse);

      useAgentStore.setState({ activeConversationId: 'conv-1' });

      // Act
      await act(async () => {
        await useAgentStore.getState().loadMessages('conv-1', 'project-1');
      });

      // Assert
      const state = useAgentStore.getState();
      expect(state.timeline).toEqual([]);
      expect(state.earliestTimeUs).toBeNull();
      expect(state.earliestCounter).toBeNull();
      expect(state.hasEarlier).toBe(false);
    });
  });

  describe('loadEarlierMessages - backward pagination', () => {
    it('should load messages before earliestTimeUs', async () => {
      // Arrange - Set initial state with time-based pagination
      const existingTimeline: TimelineEvent[] = Array.from(
        { length: 10 },
        (_, i): TimelineEvent =>
          ({
            id: `msg-${i + 11}`,
            type: 'user_message',
            sequenceNumber: i + 11,
            timestamp: (i + 11) * 1000,
            content: `Message ${i + 11}`,
            role: 'user',
            eventTimeUs: (i + 11) * 1000000,
            eventCounter: i + 11,
          }) as TimelineEvent
      );

      useAgentStore.setState({
        activeConversationId: 'conv-1',
        earliestTimeUs: 11000000,
        earliestCounter: 11,
        timeline: existingTimeline,
        hasEarlier: true,
        isLoadingEarlier: false,
      });

      const mockEarlierTimeline: TimelineEvent[] = [
        {
          id: 'msg-1',
          type: 'user_message',
          sequenceNumber: 1,
          timestamp: 1000,
          content: 'Msg 1',
          role: 'user',
          eventTimeUs: 1000000,
          eventCounter: 1,
        } as TimelineEvent,
        {
          id: 'msg-2',
          type: 'assistant_message',
          sequenceNumber: 2,
          timestamp: 2000,
          content: 'Msg 2',
          role: 'assistant',
          eventTimeUs: 2000000,
          eventCounter: 2,
        } as TimelineEvent,
        {
          id: 'msg-3',
          type: 'user_message',
          sequenceNumber: 3,
          timestamp: 3000,
          content: 'Msg 3',
          role: 'user',
          eventTimeUs: 3000000,
          eventCounter: 3,
        } as TimelineEvent,
      ];
      const mockEarlierResponse = {
        conversationId: 'conv-1',
        timeline: mockEarlierTimeline,
        total: 3,
        has_more: false,
        first_time_us: 1000000,
        first_counter: 1,
        last_time_us: 3000000,
        last_counter: 3,
      };
      mockGetConversationMessages.mockResolvedValue(mockEarlierResponse);

      // Act
      let result: boolean | undefined;
      await act(async () => {
        result = await useAgentStore.getState().loadEarlierMessages('conv-1', 'project-1');
      });

      // Assert
      const state = useAgentStore.getState();
      expect(result).toBe(true);
      expect(state.timeline.length).toBe(13); // 10 existing + 3 new
      expect(state.hasEarlier).toBe(false);
      expect(state.earliestTimeUs).toBe(1000000);
      expect(state.earliestCounter).toBe(1);
      expect(state.isLoadingEarlier).toBe(false);

      // Verify API was called with time-based pagination params
      expect(mockGetConversationMessages).toHaveBeenCalledWith(
        'conv-1',
        'project-1',
        200, // limit
        undefined, // fromTimeUs
        undefined, // fromCounter
        11000000, // beforeTimeUs
        11 // beforeCounter
      );
    });

    it('should not load when no earliestTimeUs exists', async () => {
      // Arrange
      useAgentStore.setState({
        activeConversationId: 'conv-1',
        earliestTimeUs: null,
        hasEarlier: true,
        isLoadingEarlier: false,
      });

      // Act
      let result: boolean | undefined;
      await act(async () => {
        result = await useAgentStore.getState().loadEarlierMessages('conv-1', 'project-1');
      });

      // Assert
      expect(result).toBe(false);
      expect(mockGetConversationMessages).not.toHaveBeenCalled();
    });

    it('should not load when already loading', async () => {
      // Arrange
      useAgentStore.setState({
        activeConversationId: 'conv-1',
        earliestTimeUs: 11000000,
        earliestCounter: 11,
        hasEarlier: true,
        isLoadingEarlier: true, // Already loading
      });

      // Act
      let result: boolean | undefined;
      await act(async () => {
        result = await useAgentStore.getState().loadEarlierMessages('conv-1', 'project-1');
      });

      // Assert
      expect(result).toBe(false);
      expect(mockGetConversationMessages).not.toHaveBeenCalled();
    });

    it('should not load when conversationId does not match active', async () => {
      // Arrange
      useAgentStore.setState({
        activeConversationId: 'conv-other',
        earliestTimeUs: 11000000,
        earliestCounter: 11,
        hasEarlier: true,
        isLoadingEarlier: false,
      });

      // Act
      let result: boolean | undefined;
      await act(async () => {
        result = await useAgentStore.getState().loadEarlierMessages('conv-1', 'project-1');
      });

      // Assert
      expect(result).toBe(false);
      expect(mockGetConversationMessages).not.toHaveBeenCalled();
    });

    it('should handle API error gracefully', async () => {
      // Arrange
      useAgentStore.setState({
        activeConversationId: 'conv-1',
        earliestTimeUs: 11000000,
        earliestCounter: 11,
        hasEarlier: true,
        isLoadingEarlier: false,
      });
      mockGetConversationMessages.mockRejectedValue(new Error('Network error'));

      // Act
      let result: boolean | undefined;
      await act(async () => {
        result = await useAgentStore.getState().loadEarlierMessages('conv-1', 'project-1');
      });

      // Assert
      expect(result).toBe(false);
      const state = useAgentStore.getState();
      expect(state.isLoadingEarlier).toBe(false);
    });
  });

  describe('Timeline via setState - prepend simulation', () => {
    it('should support prepending events via direct setState', () => {
      // Arrange
      const existingTimeline: TimelineEvent[] = [
        {
          id: 'msg-10',
          type: 'user_message',
          sequenceNumber: 10,
          timestamp: 10000,
          content: 'Msg 10',
          role: 'user',
          eventTimeUs: 10000000,
          eventCounter: 10,
        } as TimelineEvent,
      ];
      useAgentStore.setState({ timeline: existingTimeline });

      const newEvents: TimelineEvent[] = [
        {
          id: 'msg-1',
          type: 'user_message',
          sequenceNumber: 1,
          timestamp: 1000,
          content: 'Msg 1',
          role: 'user',
          eventTimeUs: 1000000,
          eventCounter: 1,
        } as TimelineEvent,
        {
          id: 'msg-2',
          type: 'assistant_message',
          sequenceNumber: 2,
          timestamp: 2000,
          content: 'Msg 2',
          role: 'assistant',
          eventTimeUs: 2000000,
          eventCounter: 2,
        } as TimelineEvent,
      ];

      // Act - prepend via setState (agentV3 has no prependTimelineEvents method)
      act(() => {
        useAgentStore.setState({
          timeline: [...newEvents, ...existingTimeline],
        });
      });

      // Assert
      const state = useAgentStore.getState();
      expect(state.timeline.length).toBe(3);
      expect(state.timeline[0].id).toBe('msg-1');
      expect(state.timeline[1].id).toBe('msg-2');
      expect(state.timeline[2].id).toBe('msg-10');
    });
  });

  describe('setActiveConversation - resets pagination state', () => {
    it('should reset pagination state when switching conversations', () => {
      // Arrange - Set initial pagination state
      useAgentStore.setState({
        activeConversationId: 'conv-1',
        earliestTimeUs: 10000000,
        earliestCounter: 10,
        hasEarlier: true,
        timeline: [
          {
            id: 'msg-1',
            type: 'user_message',
            sequenceNumber: 10,
            timestamp: 10000,
            content: 'Msg',
            role: 'user',
          } as TimelineEvent,
        ],
        conversations: [
          {
            id: 'conv-1',
            project_id: 'project-1',
            title: 'Conv 1',
          } as any,
          {
            id: 'conv-2',
            project_id: 'project-2',
            title: 'Conv 2',
          } as any,
        ],
      });

      // Act - switch to a different conversation
      act(() => {
        useAgentStore.getState().setActiveConversation('conv-2');
      });

      // Assert
      const state = useAgentStore.getState();
      expect(state.activeConversationId).toBe('conv-2');
      // Pagination state should be reset for the new conversation
      // (setActiveConversation restores from conversationStates cache or defaults)
      // Since conv-2 was never loaded, these should be defaults
      expect(state.hasEarlier).toBe(false);
      expect(state.earliestTimeUs).toBeNull();
      expect(state.earliestCounter).toBeNull();
    });

    it('should restore cached pagination state for previously visited conversation', () => {
      // Arrange - Set up conversation states cache
      const cachedState = new Map();
      cachedState.set('conv-2', {
        hasEarlier: true,
        earliestTimeUs: 5000000,
        earliestCounter: 5,
        timeline: [
          {
            id: 'cached-msg',
            type: 'user_message',
            content: 'Cached',
          } as TimelineEvent,
        ],
        messages: [],
        agentState: 'idle',
        currentThought: '',
      });

      useAgentStore.setState({
        activeConversationId: 'conv-1',
        conversationStates: cachedState,
        conversations: [
          { id: 'conv-1', project_id: 'p1', title: 'C1' } as any,
          { id: 'conv-2', project_id: 'p2', title: 'C2' } as any,
        ],
      });

      // Act
      act(() => {
        useAgentStore.getState().setActiveConversation('conv-2');
      });

      // Assert
      const state = useAgentStore.getState();
      expect(state.activeConversationId).toBe('conv-2');
      expect(state.hasEarlier).toBe(true);
      expect(state.earliestTimeUs).toBe(5000000);
      expect(state.earliestCounter).toBe(5);
    });
  });
});
