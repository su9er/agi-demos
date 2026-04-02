import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';

import { ProjectLayout } from '../../layouts/ProjectLayout';
import { screen, render, waitFor } from '../utils';

vi.mock('@/components/layout/AppSidebar', () => ({
  ProjectSidebar: ({ projectId }: { projectId?: string }) => (
    <nav data-testid="project-sidebar">
      <span>Overview</span>
      <span>Memories</span>
      <span>Knowledge Graph</span>
      <span>Project: {projectId}</span>
    </nav>
  ),
}));

vi.mock('@/components/layout/AppHeader', () => {
  const Header = Object.assign(
    ({ children }: { children?: React.ReactNode }) => (
      <header data-testid="app-header">{children}</header>
    ),
    {
      Search: () => <div data-testid="search">Search</div>,
      Tools: ({ children }: { children?: React.ReactNode }) => (
        <div data-testid="tools">{children}</div>
      ),
      ThemeToggle: () => <div data-testid="theme-toggle">Theme</div>,
      LanguageSwitcher: () => <div data-testid="lang-toggle">Lang</div>,
      Notifications: () => <div data-testid="notifications">Notifications</div>,
      WorkspaceSwitcher: () => <div data-testid="workspace-switcher">MockSwitcher</div>,
      PrimaryAction: ({ label }: { label?: string }) => (
        <button type="button" data-testid="primary-action">
          {label === 'nav.newMemory' ? 'New Memory' : label}
        </button>
      ),
      UserMenu: () => <div data-testid="user-menu">User</div>,
    }
  );
  return { AppHeader: Header };
});

vi.mock('@/components/common/RouteErrorBoundary', () => ({
  RouteErrorBoundary: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/stores/project', () => {
  const state = {
    currentProject: { id: 'p1', name: 'Test Project' },
    projects: [{ id: 'p1', name: 'Test Project' }],
    setCurrentProject: vi.fn(),
    getProject: vi.fn().mockResolvedValue({ id: 'p1', name: 'Test Project' }),
  };
  const hook = ((selector?: any) => (selector ? selector(state) : state)) as any;
  hook.getState = () => state;
  hook.setState = vi.fn();
  hook.subscribe = vi.fn();
  return { useProjectStore: hook };
});

vi.mock('@/stores/tenant', () => {
  const state = {
    tenants: [{ id: 't1', name: 'Test Tenant' }],
    currentTenant: { id: 't1', name: 'Test Tenant' },
    setCurrentTenant: vi.fn(),
    listTenants: vi.fn().mockResolvedValue([]),
  };
  const hook = ((selector?: any) => (selector ? selector(state) : state)) as any;
  hook.getState = () => state;
  hook.setState = vi.fn();
  hook.subscribe = vi.fn();
  return { useTenantStore: hook };
});

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useParams: vi.fn(() => ({ projectId: 'p1' })),
    Outlet: () => <div data-testid="outlet">Page Content</div>,
  };
});

describe('ProjectLayout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders project navigation items', async () => {
    render(<ProjectLayout />);

    await waitFor(() => {
      expect(screen.getByText('Overview')).toBeInTheDocument();
    });
    expect(screen.getByText('Memories')).toBeInTheDocument();
    expect(screen.getByText('Knowledge Graph')).toBeInTheDocument();
  });

  it('renders header components', async () => {
    render(<ProjectLayout />);

    await waitFor(() => {
      expect(screen.getByTestId('theme-toggle')).toBeInTheDocument();
    });
    expect(screen.getByTestId('lang-toggle')).toBeInTheDocument();
    expect(screen.getByTestId('workspace-switcher')).toBeInTheDocument();
  });

  it('renders New Memory button', async () => {
    render(<ProjectLayout />);

    await waitFor(() => {
      expect(screen.getByText('New Memory')).toBeInTheDocument();
    });
  });
});
