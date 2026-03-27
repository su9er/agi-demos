/**
 * AppHeader.WorkspaceSwitcher - Compound Component
 *
 * Workspace switcher wrapper.
 */

import * as React from 'react';

import { WorkspaceSwitcher as BaseWorkspaceSwitcher } from '@/components/shared/ui/WorkspaceSwitcher';

interface BaseWorkspaceSwitcherProps {
  mode: 'tenant' | 'project';
}

export interface WorkspaceSwitcherProps {
  mode: 'tenant' | 'project';
  as?: React.ComponentType<BaseWorkspaceSwitcherProps> | undefined;
}

export const WorkspaceSwitcher = React.memo(function WorkspaceSwitcher({
  mode,
  as: Component = BaseWorkspaceSwitcher,
}: WorkspaceSwitcherProps) {
  // Responsive width classes
  const widthClass = mode === 'project' ? 'w-full min-w-0' : 'w-full min-w-0';

  return (
    <div className={widthClass}>
      <Component mode={mode} />
    </div>
  );
});

WorkspaceSwitcher.displayName = 'AppHeader.WorkspaceSwitcher';
