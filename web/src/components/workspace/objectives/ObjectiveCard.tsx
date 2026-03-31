import React from 'react';

import { Dropdown } from 'antd';
import { MoreHorizontal, Pencil, Trash2 } from 'lucide-react';

import { ObjectiveProgress } from './ObjectiveProgress';

import type { CyberObjective } from '@/types/workspace';

import type { MenuProps } from 'antd';

export interface ObjectiveCardProps {
  objective: CyberObjective;
  onEdit?: ((objective: CyberObjective) => void) | undefined;
  onDelete?: ((objectiveId: string) => void) | undefined;
}

export const ObjectiveCard: React.FC<ObjectiveCardProps> = ({ objective, onEdit, onDelete }) => {
  const isObjective = objective.obj_type === 'objective';
  const badgeTone = isObjective
    ? 'border-primary/20 bg-primary/8 text-primary dark:border-primary/30 dark:bg-primary/12 dark:text-primary-200'
    : 'border-success-border bg-success-bg text-status-text-success dark:border-success-border-dark dark:bg-success-bg-dark dark:text-status-text-success-dark';

  const menuItems: NonNullable<MenuProps['items']> = [
    ...(onEdit
      ? [
          {
            key: 'edit',
            icon: <Pencil size={14} />,
            label: 'Edit',
            onClick: () => {
              onEdit(objective);
            },
          },
        ]
      : []),
    ...(onDelete
      ? [
          {
            key: 'delete',
            icon: (
              <Trash2
                size={14}
                className="text-status-text-error dark:text-status-text-error-dark"
              />
            ),
            label: (
              <span className="text-status-text-error dark:text-status-text-error-dark">
                Delete
              </span>
            ),
            onClick: () => {
              onDelete(objective.id);
            },
          },
        ]
      : []),
  ];

  return (
    <article className="w-full rounded-2xl border border-border-light bg-surface-light px-4 py-4 shadow-sm transition-colors hover:border-border-separator dark:border-border-dark dark:bg-surface-dark">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span
              className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${badgeTone}`}
            >
              {isObjective ? 'Objective' : 'Key Result'}
            </span>
            <span className="text-xs text-text-muted dark:text-text-muted">
              Created: {new Date(objective.created_at).toLocaleDateString()}
            </span>
          </div>
          <h4 className="mt-3 break-words text-base font-semibold text-text-primary dark:text-text-inverse">
            {objective.title}
          </h4>
          {objective.description && (
            <p
              className="mt-2 line-clamp-2 break-words text-sm leading-6 text-text-secondary dark:text-text-muted"
              title={objective.description}
            >
              {objective.description}
            </p>
          )}
        </div>

        <div className="flex items-start gap-3 sm:flex-none">
          <ObjectiveProgress
            progress={objective.progress}
            size={44}
            strokeWidth={4}
            color={isObjective ? 'var(--color-primary)' : 'var(--color-success)'}
          />

          {menuItems.length > 0 && (
            <Dropdown menu={{ items: menuItems }} trigger={['click']} placement="bottomRight">
              <button
                type="button"
                aria-label={`Open actions for ${objective.title}`}
                className="inline-flex min-h-10 min-w-10 items-center justify-center rounded-full border border-border-light bg-surface-muted text-text-muted transition hover:border-border-separator hover:bg-surface-light hover:text-text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 dark:border-border-dark dark:bg-background-dark dark:text-text-muted dark:hover:bg-surface-elevated dark:hover:text-text-inverse"
              >
                <MoreHorizontal size={18} />
              </button>
            </Dropdown>
          )}
        </div>
      </div>
    </article>
  );
};
