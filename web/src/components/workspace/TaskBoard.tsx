import React, { useMemo, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button, Input, Select, Tooltip } from 'antd';
import { AlertCircle, Ban, CheckCircle, ListTodo, PlayCircle, Plus } from 'lucide-react';

import { useWorkspaceAgents, useWorkspaceTasks } from '@/stores/workspace';

import { workspaceTaskService } from '@/services/workspaceService';

import { useLazyMessage } from '@/components/ui/lazyAntd';

import type { WorkspaceTaskStatus } from '@/types/workspace';

interface TaskBoardProps {
  workspaceId: string;
}

const PRIORITY_TONES: Record<string, string> = {
  P1: 'border-error-border bg-error-bg text-status-text-error dark:border-error-border-dark dark:bg-error-bg-dark dark:text-status-text-error-dark',
  P2: 'border-caution-border bg-caution-bg text-status-text-caution dark:border-caution-border-dark dark:bg-caution-bg-dark dark:text-status-text-caution-dark',
  P3: 'border-warning-border bg-warning-bg text-status-text-warning dark:border-warning-border-dark dark:bg-warning-bg-dark dark:text-status-text-warning-dark',
  P4: 'border-border-light bg-surface-light text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-secondary',
};

const PRIORITY_RANK: Record<string, number> = {
  P1: 4,
  P2: 3,
  P3: 2,
  P4: 1,
};

const EFFORT_OPTIONS = [
  { label: 'S', value: 'S' },
  { label: 'M', value: 'M' },
  { label: 'L', value: 'L' },
  { label: 'XL', value: 'XL' },
];

const PRIORITY_OPTIONS = [
  { label: 'None', value: '' },
  { label: 'P1', value: 'P1' },
  { label: 'P2', value: 'P2' },
  { label: 'P3', value: 'P3' },
  { label: 'P4', value: 'P4' },
];

export const TaskBoard: React.FC<TaskBoardProps> = ({ workspaceId }) => {
  const { t } = useTranslation();
  const message = useLazyMessage();
  const tasks = useWorkspaceTasks();
  const agents = useWorkspaceAgents();

  const statusOptions = useMemo(
    () => [
      {
        label: (
          <span className="flex items-center gap-1.5">
            <ListTodo size={14} className="text-text-muted dark:text-text-muted" />
            {t('workspaceDetail.taskBoard.statusTodo')}
          </span>
        ),
        value: 'todo',
      },
      {
        label: (
          <span className="flex items-center gap-1.5">
            <PlayCircle size={14} className="text-status-text-info dark:text-status-text-info-dark" />
            {t('workspaceDetail.taskBoard.statusInProgress')}
          </span>
        ),
        value: 'in_progress',
      },
      {
        label: (
          <span className="flex items-center gap-1.5">
            <Ban size={14} className="text-status-text-error dark:text-status-text-error-dark" />
            {t('workspaceDetail.taskBoard.statusBlocked')}
          </span>
        ),
        value: 'blocked',
      },
      {
        label: (
          <span className="flex items-center gap-1.5">
            <CheckCircle
              size={14}
              className="text-status-text-success dark:text-status-text-success-dark"
            />
            {t('workspaceDetail.taskBoard.statusDone')}
          </span>
        ),
        value: 'done',
      },
    ],
    [t]
  );

  const [title, setTitle] = useState('');
  const [priority, setPriority] = useState<string>('');
  const [effort, setEffort] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const sortedTasks = useMemo(() => {
    return tasks
      .filter((task) => task.workspace_id === workspaceId)
      .sort((a, b) => {
        if (a.status === 'blocked' && b.status !== 'blocked') return -1;
        if (b.status === 'blocked' && a.status !== 'blocked') return 1;

        const rankA = PRIORITY_RANK[a.priority || ''] || 0;
        const rankB = PRIORITY_RANK[b.priority || ''] || 0;
        if (rankA !== rankB) return rankB - rankA;

        return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
      });
  }, [tasks, workspaceId]);

  const handleAddTask = async () => {
    const trimmedTitle = title.trim();
    if (!trimmedTitle) {
      return;
    }

    setIsSubmitting(true);
    try {
      const taskResponse = await workspaceTaskService.create(workspaceId, { title: trimmedTitle });

      if (priority || effort) {
        await workspaceTaskService.update(workspaceId, taskResponse.id, {
          ...(priority ? { priority } : {}),
          ...(effort ? { estimated_effort: effort } : {}),
        });
      }

      setTitle('');
      setPriority('');
      setEffort('');
    } catch {
      message?.error(t('workspaceDetail.taskBoard.createFailed'));
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleStatusChange = async (taskId: string, newStatus: WorkspaceTaskStatus) => {
    try {
      await workspaceTaskService.update(workspaceId, taskId, { status: newStatus });
    } catch {
      message?.error(t('workspaceDetail.taskBoard.updateStatusFailed'));
    }
  };

  const handleAgentAssign = async (taskId: string, agentId: string) => {
    try {
      if (agentId) {
        await workspaceTaskService.assignToAgent(workspaceId, taskId, agentId);
      } else {
        await workspaceTaskService.unassignAgent(workspaceId, taskId);
      }
    } catch {
      message?.error(t('workspaceDetail.taskBoard.assignFailed'));
    }
  };

  const agentOptions = useMemo(() => {
    const options = agents.map((agent) => ({
      label: agent.display_name || agent.agent_id,
      value: agent.id || agent.agent_id,
    }));

    return [{ label: t('workspaceDetail.taskBoard.unassigned'), value: '' }, ...options];
  }, [agents, t]);

  return (
    <section className="rounded-3xl border border-border-light bg-surface-muted/90 p-4 shadow-sm dark:border-border-dark dark:bg-surface-dark-alt sm:p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0">
          <h3 className="text-lg font-semibold text-text-primary dark:text-text-inverse">
            {t('workspaceDetail.taskBoard.title')}
          </h3>
          <p className="mt-1 max-w-2xl text-sm leading-7 text-text-secondary dark:text-text-muted">
            {t(
              'workspaceDetail.taskBoard.summary',
              'Capture delivery work, assign ownership, and keep task status visible without leaving the blackboard.'
            )}
          </p>
        </div>
        <div className="rounded-full border border-border-light bg-surface-light px-3 py-1.5 text-xs font-medium text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-secondary">
          {t('workspaceDetail.taskBoard.count', '{{count}} tasks', { count: sortedTasks.length })}
        </div>
      </div>

      <div className="mt-5 grid gap-3 lg:grid-cols-[minmax(0,1.8fr)_minmax(140px,0.7fr)_minmax(120px,0.6fr)_auto]">
        <label className="space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
            {t('workspaceDetail.taskBoard.taskTitle', 'Task title')}
          </span>
          <Input
            aria-label={t('workspaceDetail.taskBoard.taskTitle', 'Task title')}
            placeholder={t('workspaceDetail.taskBoard.taskTitlePlaceholder')}
            value={title}
            onChange={(event) => {
              setTitle(event.target.value);
            }}
            onPressEnter={() => {
              void handleAddTask();
            }}
            className="min-h-11"
          />
        </label>

        <label className="space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
            {t('workspaceDetail.taskBoard.priority', 'Priority')}
          </span>
          <Select
            aria-label={t('workspaceDetail.taskBoard.priority', 'Priority')}
            options={PRIORITY_OPTIONS}
            value={priority}
            onChange={setPriority}
            placeholder={t('workspaceDetail.taskBoard.priority')}
            className="w-full"
          />
        </label>

        <label className="space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
            {t('workspaceDetail.taskBoard.effort', 'Effort')}
          </span>
          <Select
            aria-label={t('workspaceDetail.taskBoard.effort', 'Effort')}
            options={EFFORT_OPTIONS}
            value={effort}
            onChange={setEffort}
            placeholder={t('workspaceDetail.taskBoard.effort')}
            className="w-full"
            allowClear
          />
        </label>

        <div className="flex items-end">
          <Button
            type="primary"
            icon={<Plus size={16} />}
            onClick={() => {
              void handleAddTask();
            }}
            loading={isSubmitting}
            disabled={!title.trim()}
            className="min-h-11 w-full lg:w-auto"
          >
            {t('workspaceDetail.taskBoard.add')}
          </Button>
        </div>
      </div>

      <div className="mt-5 space-y-3">
        {sortedTasks.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border-separator bg-surface-light px-4 py-6 text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
            {t(
              'workspaceDetail.taskBoard.empty',
              'No workspace tasks yet. Add the next concrete task so the team can align around delivery.'
            )}
          </div>
        ) : (
          sortedTasks.map((task) => {
            const isDone = task.status === 'done';
            const isBlocked = task.status === 'blocked';
            const priorityTone =
              PRIORITY_TONES[task.priority || ''] ??
              'border-border-light bg-surface-light text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-secondary';

            return (
              <article
                key={task.id}
                className={`rounded-2xl border border-border-light bg-surface-light px-4 py-4 shadow-sm transition hover:border-border-separator dark:border-border-dark dark:bg-surface-dark ${
                  isDone ? 'opacity-70' : ''
                }`}
              >
                <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={`rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] ${priorityTone}`}
                      >
                        {task.priority || t('workspaceDetail.taskBoard.noPriority', 'No priority')}
                      </span>
                      {task.estimated_effort && (
                        <span className="rounded-full border border-border-light bg-surface-muted px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-text-secondary dark:border-border-dark dark:bg-background-dark dark:text-text-secondary">
                          {t('workspaceDetail.taskBoard.effortLabel', 'Effort')} {task.estimated_effort}
                        </span>
                      )}
                      {isBlocked && (
                        <Tooltip
                          title={
                            task.blocker_reason ||
                            t('workspaceDetail.taskBoard.taskIsBlocked', 'Task is blocked')
                          }
                        >
                          <span className="inline-flex items-center gap-1 rounded-full border border-error-border bg-error-bg px-2.5 py-1 text-[11px] font-medium text-status-text-error dark:border-error-border-dark dark:bg-error-bg-dark dark:text-status-text-error-dark">
                            <AlertCircle size={12} />
                            {t('workspaceDetail.taskBoard.statusBlocked')}
                          </span>
                        </Tooltip>
                      )}
                    </div>

                    <h4
                      className={`mt-3 break-words text-sm font-semibold text-text-primary dark:text-text-inverse ${
                        isDone ? 'line-through decoration-border-separator' : ''
                      }`}
                    >
                      {task.title}
                    </h4>

                    {isBlocked && task.blocker_reason && (
                      <p className="mt-2 text-sm leading-6 text-status-text-error dark:text-status-text-error-dark">
                        {task.blocker_reason}
                      </p>
                    )}
                  </div>

                  <div className="grid gap-3 sm:grid-cols-2 xl:w-[360px] xl:flex-none">
                    <div className="space-y-1.5">
                      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
                        {t('workspaceDetail.taskBoard.assignee', 'Assignee')}
                      </div>
                      <Select
                        aria-label={t('workspaceDetail.taskBoard.assignee', 'Assignee')}
                        size="middle"
                        value={task.assignee_agent_id || ''}
                        options={agentOptions}
                        onChange={(value) => {
                          void handleAgentAssign(task.id, value);
                        }}
                        className="w-full"
                        placeholder={t('workspaceDetail.taskBoard.assignee', 'Assignee')}
                      />
                    </div>

                    <div className="space-y-1.5">
                      <div className="text-[11px] font-medium uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
                        {t('workspaceDetail.taskBoard.status', 'Status')}
                      </div>
                      <Select
                        aria-label={t('workspaceDetail.taskBoard.status', 'Status')}
                        size="middle"
                        value={task.status}
                        options={statusOptions}
                        onChange={(value) => {
                          void handleStatusChange(task.id, value as WorkspaceTaskStatus);
                        }}
                        className="w-full"
                        {...(isBlocked ? { status: 'error' } : {})}
                      />
                    </div>
                  </div>
                </div>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
};
