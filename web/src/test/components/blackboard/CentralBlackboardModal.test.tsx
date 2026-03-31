import { beforeEach, describe, expect, it, vi } from 'vitest';

import { CentralBlackboardModal } from '@/components/blackboard/CentralBlackboardModal';
import { render, screen, within } from '@/test/utils';

vi.mock('@/stores/workspace', () => ({
  useWorkspaceActions: () => ({
    createObjective: vi.fn(),
    deleteObjective: vi.fn(),
    deleteGene: vi.fn(),
    updateGene: vi.fn(),
  }),
}));

vi.mock('@/components/ui/lazyAntd', () => ({
  useLazyMessage: () => ({
    error: vi.fn(),
  }),
}));

vi.mock('@/pages/tenant/WorkspaceSettings', () => ({
  WorkspaceSettingsPanel: () => <div>Workspace settings</div>,
}));

vi.mock('@/components/workspace/chat/ChatPanel', () => ({
  ChatPanel: () => <div>Chat panel</div>,
}));

vi.mock('@/components/workspace/genes/GeneList', () => ({
  GeneList: () => <div>Gene list</div>,
}));

vi.mock('@/components/workspace/MemberPanel', () => ({
  MemberPanel: () => <div>Member panel</div>,
}));

vi.mock('@/components/workspace/objectives/ObjectiveCreateModal', () => ({
  ObjectiveCreateModal: () => null,
}));

vi.mock('@/components/workspace/objectives/ObjectiveList', () => ({
  ObjectiveList: () => <div>Objective list</div>,
}));

vi.mock('@/components/workspace/presence/PresenceBar', () => ({
  PresenceBar: () => <div>Presence bar</div>,
}));

vi.mock('@/components/workspace/TaskBoard', () => ({
  TaskBoard: () => <div>Task board</div>,
}));

describe('CentralBlackboardModal', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders a matching tabpanel element for every tab control', () => {
    render(
      <CentralBlackboardModal
        open
        tenantId="tenant-1"
        projectId="project-1"
        workspaceId="workspace-1"
        workspace={{ id: 'workspace-1', name: 'Central board' } as any}
        posts={[]}
        repliesByPostId={{}}
        loadedReplyPostIds={{}}
        tasks={[]}
        objectives={[]}
        genes={[]}
        agents={[]}
        topologyNodes={[]}
        topologyEdges={[]}
        onClose={vi.fn()}
        onLoadReplies={vi.fn().mockResolvedValue(true)}
        onCreatePost={vi.fn().mockResolvedValue(true)}
        onCreateReply={vi.fn().mockResolvedValue(true)}
        onDeletePost={vi.fn().mockResolvedValue(true)}
        onPinPost={vi.fn().mockResolvedValue(undefined)}
        onUnpinPost={vi.fn().mockResolvedValue(undefined)}
        onDeleteReply={vi.fn().mockResolvedValue(undefined)}
      />
    );

    const tablist = screen.getByRole('tablist');
    const tabs = within(tablist).getAllByRole('tab');
    const panels = screen.getAllByRole('tabpanel', { hidden: true });

    expect(panels).toHaveLength(tabs.length);

    tabs.forEach((tab) => {
      const controls = tab.getAttribute('aria-controls');

      expect(controls).toBeTruthy();
      expect(document.getElementById(controls ?? '')).not.toBeNull();
    });
  });
});
