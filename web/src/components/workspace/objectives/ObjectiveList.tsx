import React, { useMemo } from 'react';

import { useTranslation } from 'react-i18next';

import { Button, Skeleton } from 'antd';
import { Plus } from 'lucide-react';

import { ObjectiveCard } from './ObjectiveCard';

import type { CyberObjective } from '@/types/workspace';

export interface ObjectiveListProps {
  objectives: CyberObjective[];
  onEdit?: ((objective: CyberObjective) => void) | undefined;
  onDelete?: ((objectiveId: string) => void) | undefined;
  onCreate?: (() => void) | undefined;
  loading?: boolean | undefined;
}

export const ObjectiveList: React.FC<ObjectiveListProps> = ({
  objectives,
  onEdit,
  onDelete,
  onCreate,
  loading = false,
}) => {
  const { t } = useTranslation();
  const { topLevel, childrenMap } = useMemo(() => {
    const roots: CyberObjective[] = [];
    const nestedChildren = new Map<string, CyberObjective[]>();

    objectives.forEach((objective) => {
      if (!objective.parent_id) {
        roots.push(objective);
      } else {
        const children = nestedChildren.get(objective.parent_id) || [];
        children.push(objective);
        nestedChildren.set(objective.parent_id, children);
      }
    });

    roots.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());

    return { topLevel: roots, childrenMap: nestedChildren };
  }, [objectives]);

  if (loading) {
    return (
      <div className="space-y-4">
        <Skeleton active paragraph={{ rows: 2 }} />
        <Skeleton active paragraph={{ rows: 2 }} />
      </div>
    );
  }

  return (
    <section className="flex h-full w-full flex-col rounded-3xl border border-border-light bg-surface-muted/90 p-4 shadow-sm dark:border-border-dark dark:bg-surface-dark-alt sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-text-primary dark:text-text-inverse">
            {t('workspaceDetail.objectives.title')}
          </h3>
          <p className="mt-1 max-w-2xl text-sm leading-7 text-text-secondary dark:text-text-muted">
            {t(
              'workspaceDetail.objectives.summary',
              'Capture the big outcomes first, then keep supporting key results nested underneath.'
            )}
          </p>
        </div>
        {onCreate && (
          <Button
            type="primary"
            icon={<Plus size={16} />}
            onClick={onCreate}
            className="min-h-11 self-start"
          >
            {t('workspaceDetail.objectives.addObjective')}
          </Button>
        )}
      </div>

      <div className="mt-5 min-h-0 flex-1 overflow-y-auto pr-1">
        {topLevel.length === 0 ? (
          <div className="flex h-full min-h-[220px] items-center justify-center rounded-2xl border border-dashed border-border-separator bg-surface-light px-6 py-8 text-center dark:border-border-dark dark:bg-surface-dark">
            <div className="max-w-md">
              <div className="text-base font-semibold text-text-primary dark:text-text-inverse">
                {t('workspaceDetail.objectives.noObjectives')}
              </div>
              <p className="mt-2 text-sm leading-7 text-text-secondary dark:text-text-muted">
                {t(
                  'workspaceDetail.objectives.emptySummary',
                  'Start with one shared objective so the blackboard has a clear outcome to anchor tasks and discussion.'
                )}
              </p>
              {onCreate && (
                <Button type="primary" onClick={onCreate} className="mt-4 min-h-11">
                  {t('workspaceDetail.objectives.createFirst')}
                </Button>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-5">
            {topLevel.map((parent) => (
              <div key={parent.id} className="space-y-3">
                <ObjectiveCard objective={parent} onEdit={onEdit} onDelete={onDelete} />

                {childrenMap.has(parent.id) && (
                  <div className="ml-4 space-y-3 border-l border-border-light pl-4 transition-colors duration-200 dark:border-border-dark">
                    {childrenMap.get(parent.id)?.map((child) => (
                      <ObjectiveCard
                        key={child.id}
                        objective={child}
                        onEdit={onEdit}
                        onDelete={onDelete}
                      />
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </section>
  );
};
