import type { ReactNode } from 'react';

import { describe, expect, it, vi } from 'vitest';

import { WorkspaceSettingsPanel } from '@/pages/tenant/WorkspaceSettings';
import { render, screen } from '@/test/utils';

vi.mock('@/stores/workspace', () => ({
  useCurrentWorkspace: () => ({
    id: 'ws-1',
    name: 'Workspace Alpha',
    description: 'Demo workspace',
  }),
  useWorkspaceMembers: () => [],
  useWorkspaceActions: () => ({
    loadWorkspaceSurface: vi.fn(),
    setCurrentWorkspace: vi.fn(),
  }),
}));

vi.mock('@/services/workspaceService', () => ({
  workspaceService: {
    update: vi.fn(),
    remove: vi.fn(),
    addMember: vi.fn(),
    removeMember: vi.fn(),
    updateMemberRole: vi.fn(),
  },
}));

vi.mock('@/components/ui/lazyAntd', () => ({
  LazyPopconfirm: ({ children }: { children: ReactNode }) => children,
  useLazyMessage: () => ({
    success: vi.fn(),
    error: vi.fn(),
  }),
}));

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

describe('WorkspaceSettingsPanel', () => {
  it('marks workspace settings as a hosted non-authoritative projection', () => {
    render(<WorkspaceSettingsPanel tenantId="t-1" projectId="p-1" workspaceId="ws-1" />);

    const boundaryBadge = screen.getByText('blackboard.settingsSurfaceHint').closest('div');
    expect(boundaryBadge).toHaveAttribute('data-blackboard-boundary', 'hosted');
    expect(boundaryBadge).toHaveAttribute('data-blackboard-authority', 'non-authoritative');
  });
});
