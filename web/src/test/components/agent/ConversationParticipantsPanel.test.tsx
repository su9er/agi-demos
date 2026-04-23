import { describe, expect, it, vi } from 'vitest';

import { render, screen } from '@/test/utils';

vi.mock('react-i18next', () => ({
  useTranslation: () => ({
    t: (_key: string, opts?: unknown) => {
      if (opts && typeof opts === 'object' && 'defaultValue' in opts) {
        return (opts as { defaultValue: string }).defaultValue;
      }
      return typeof opts === 'string' ? opts : _key;
    },
  }),
}));

vi.mock('@/hooks/useConversationParticipants', () => ({
  useConversationParticipants: () => ({
    roster: {
      conversation_id: 'c1',
      conversation_mode: 'multi_agent_shared',
      effective_mode: 'multi_agent_shared',
      participant_agents: ['agent-1'],
      participant_bindings: [
        {
          agent_id: 'agent-1',
          workspace_agent_id: 'binding-1',
          display_name: 'Worker A',
          label: null,
          is_active: true,
          source: 'workspace',
        },
      ],
      coordinator_agent_id: 'agent-1',
      focused_agent_id: null,
    },
    loading: false,
    error: null,
    refresh: vi.fn(),
    addParticipant: vi.fn(),
    removeParticipant: vi.fn(),
    setCoordinator: vi.fn(),
  }),
}));

vi.mock('@/hooks/useMentionCandidates', () => ({
  useMentionCandidates: () => ({
    candidates: [],
  }),
}));

import { ConversationParticipantsPanel } from '@/components/agent/ConversationParticipantsPanel';

describe('ConversationParticipantsPanel', () => {
  it('renders participant display_name when binding projection is available', () => {
    render(<ConversationParticipantsPanel conversationId="c1" />);

    expect(screen.getByText('Worker A')).toBeInTheDocument();
    expect(screen.queryByText('agent-1')).not.toBeInTheDocument();
  });
});
