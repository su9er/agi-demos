import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

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

vi.mock('@/hooks/useMentionCandidates', () => ({
  useMentionCandidates: () => ({
    candidates: [
      {
        agent_id: 'agent-1',
        workspace_agent_id: 'binding-1',
        display_name: 'Worker A',
        label: 'alpha',
        status: 'idle',
        is_active: true,
        source: 'workspace',
      },
    ],
  }),
}));

import { MentionPicker } from '@/components/agent/MentionPicker';

describe('MentionPicker binding-aware candidates', () => {
  it('renders display_name and selects by agent_id from a bounded candidate set', () => {
    const onMentionSelected = vi.fn();

    render(
      <MentionPicker
        conversationId="conv-1"
        query="wor"
        open={true}
        onMentionSelected={onMentionSelected}
        onDismiss={vi.fn()}
      />
    );

    expect(screen.getByText('@agent-1')).toBeInTheDocument();
    expect(screen.getByText('Worker A')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('option'));

    expect(onMentionSelected).toHaveBeenCalledWith('agent-1');
  });
});
