import { useCallback, useMemo } from 'react';

import { useTranslation } from 'react-i18next';

import type { KeyboardEvent as ReactKeyboardEvent, RefObject } from 'react';

export type BlackboardTab =
  | 'goals'
  | 'discussion'
  | 'collaboration'
  | 'members'
  | 'genes'
  | 'files'
  | 'status'
  | 'notes'
  | 'topology'
  | 'settings';

export interface BlackboardTabBarProps {
  activeTab: BlackboardTab;
  onTabChange: (tab: BlackboardTab) => void;
  tabListRef: RefObject<HTMLDivElement | null>;
}

export function BlackboardTabBar({ activeTab, onTabChange, tabListRef }: BlackboardTabBarProps) {
  const { t } = useTranslation();

  const tabs = useMemo(
    () =>
      [
        { key: 'goals', label: t('blackboard.tabs.goals', 'Goals / Tasks') },
        { key: 'discussion', label: t('blackboard.tabs.discussion', 'Discussion') },
        { key: 'collaboration', label: t('blackboard.tabs.collaboration', 'Collaboration') },
        { key: 'members', label: t('blackboard.tabs.members', 'Members') },
        { key: 'genes', label: t('blackboard.tabs.genes', 'Genes') },
        { key: 'files', label: t('blackboard.tabs.files', 'Files') },
        { key: 'status', label: t('blackboard.tabs.status', 'Status') },
        { key: 'notes', label: t('blackboard.tabs.notes', 'Notes') },
        { key: 'topology', label: t('blackboard.tabs.topology', 'Topology') },
        { key: 'settings', label: t('blackboard.tabs.settings', 'Settings') },
      ] as const,
    [t],
  );

  const moveTabFocus = useCallback(
    (nextIndex: number) => {
      const nextTab = tabs[nextIndex];
      if (!nextTab) {
        return;
      }

      onTabChange(nextTab.key);

      requestAnimationFrame(() => {
        const nextButton = tabListRef.current?.querySelector<HTMLButtonElement>(
          `#blackboard-tab-${nextTab.key}`,
        );
        nextButton?.focus();
      });
    },
    [onTabChange, tabListRef, tabs],
  );

  const handleTabKeyDown = useCallback(
    (event: ReactKeyboardEvent<HTMLButtonElement>, index: number) => {
      const lastIndex = tabs.length - 1;

      if (event.key === 'ArrowRight') {
        event.preventDefault();
        moveTabFocus(index === lastIndex ? 0 : index + 1);
        return;
      }

      if (event.key === 'ArrowLeft') {
        event.preventDefault();
        moveTabFocus(index === 0 ? lastIndex : index - 1);
        return;
      }

      if (event.key === 'Home') {
        event.preventDefault();
        moveTabFocus(0);
        return;
      }

      if (event.key === 'End') {
        event.preventDefault();
        moveTabFocus(lastIndex);
      }
    },
    [moveTabFocus, tabs.length],
  );

  return (
    <div
      ref={tabListRef}
      role="tablist"
      aria-label={t('blackboard.tabs.ariaLabel', 'Blackboard sections')}
      className="flex gap-1 overflow-x-auto border-b border-border-light px-4 py-3 dark:border-border-dark sm:px-6"
    >
      {tabs.map((tab) => (
        <button
          key={tab.key}
          type="button"
          role="tab"
          id={`blackboard-tab-${tab.key}`}
          aria-selected={activeTab === tab.key}
          aria-controls={`blackboard-panel-${tab.key}`}
          tabIndex={activeTab === tab.key ? 0 : -1}
          onKeyDown={(event) => {
            handleTabKeyDown(event, tabs.findIndex((item) => item.key === tab.key));
          }}
          onClick={() => {
            onTabChange(tab.key);
          }}
          className={`rounded-full px-4 py-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 ${
            activeTab === tab.key
              ? 'bg-primary/10 font-medium text-primary'
              : 'text-text-secondary hover:bg-surface-muted hover:text-text-primary dark:text-text-muted dark:hover:bg-surface-elevated dark:hover:text-text-inverse'
          }`}
        >
          {tab.label}
        </button>
      ))}
    </div>
  );
}

export const BLACKBOARD_TABS = [
  'goals',
  'discussion',
  'collaboration',
  'members',
  'genes',
  'files',
  'status',
  'notes',
  'topology',
  'settings',
] as const;
