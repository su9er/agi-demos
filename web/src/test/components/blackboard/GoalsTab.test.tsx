import { act, fireEvent } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import { GoalsTab } from '@/components/blackboard/tabs/GoalsTab';
import { render, screen } from '@/test/utils';

vi.mock('@/components/workspace/objectives/ObjectiveList', () => ({
  ObjectiveList: () => <div>Objective list</div>,
}));

vi.mock('@/components/workspace/TaskBoard', () => ({
  TaskBoard: () => <div>Task board</div>,
}));

describe('GoalsTab', () => {
  it('shows pending orchestration feedback before a root task exists', () => {
    render(
      <GoalsTab
        objectives={[
          {
            id: 'objective-1',
            workspace_id: 'ws-1',
            title: 'Ship agent collaboration flow',
            obj_type: 'objective',
            progress: 0,
            created_at: '2026-04-17T05:00:00Z',
          },
        ]}
        goalCandidates={[]}
        goalCandidatesLoading={false}
        goalCandidatesError={null}
        tasks={[]}
        completionRatio={0}
        workspaceId="ws-1"
        onDeleteObjective={vi.fn()}
        onProjectObjective={vi.fn()}
        onCreateObjective={vi.fn()}
        onRefreshGoalCandidates={vi.fn()}
        onMaterializeGoalCandidate={vi.fn()}
      />
    );

    expect(screen.getByText('自动编排反馈')).toBeInTheDocument();
    expect(screen.getByText('等待 root task')).toBeInTheDocument();
    expect(screen.getByText(/正在触发 Sisyphus 接管并投影为 root task/i)).toBeInTheDocument();
    expect(screen.getAllByText('目标已创建').length).toBeGreaterThan(0);
    expect(screen.getByText('生成 root task')).toBeInTheDocument();
    expect(screen.getByText('事件流日志')).toBeInTheDocument();
  });

  it('shows live child-task execution counts once orchestration is underway', async () => {
    vi.useFakeTimers();
    const scrollIntoView = vi.fn();
    const clipboardWriteText = vi.spyOn(navigator.clipboard, 'writeText').mockResolvedValue();
    const taskBoardTarget = document.createElement('article');
    taskBoardTarget.id = 'workspace-task-child-2';
    taskBoardTarget.scrollIntoView = scrollIntoView;
    document.body.appendChild(taskBoardTarget);

    render(
      <GoalsTab
        objectives={[
          {
            id: 'objective-1',
            workspace_id: 'ws-1',
            title: 'Ship agent collaboration flow',
            obj_type: 'objective',
            progress: 0,
            created_at: '2026-04-17T05:00:00Z',
          },
        ]}
        goalCandidates={[]}
        goalCandidatesLoading={false}
        goalCandidatesError={null}
        tasks={[
          {
            id: 'root-1',
            workspace_id: 'ws-1',
            title: 'Ship agent collaboration flow',
            status: 'in_progress',
            created_at: '2026-04-17T05:00:10Z',
            updated_at: '2026-04-17T05:02:00Z',
            metadata: {
              task_role: 'goal_root',
              objective_id: 'objective-1',
              goal_progress_summary: '1/2 child tasks done; 1 in progress; 0 blocked; 2/2 assigned',
            },
          },
          {
            id: 'child-1',
            workspace_id: 'ws-1',
            title: 'Create fixture',
            status: 'done',
            assignee_agent_id: 'worker-a',
            created_at: '2026-04-17T05:00:20Z',
            updated_at: '2026-04-17T05:01:20Z',
            completed_at: '2026-04-17T05:01:20Z',
            metadata: {
              task_role: 'execution_task',
              root_goal_task_id: 'root-1',
            },
          },
          {
            id: 'child-2',
            workspace_id: 'ws-1',
            title: 'Run collaboration test',
            status: 'in_progress',
            assignee_agent_id: 'worker-b',
            created_at: '2026-04-17T05:00:30Z',
            updated_at: '2026-04-17T05:02:30Z',
            metadata: {
              task_role: 'execution_task',
              root_goal_task_id: 'root-1',
            },
          },
        ] as never}
        completionRatio={0.5}
        workspaceId="ws-1"
        onDeleteObjective={vi.fn()}
        onProjectObjective={vi.fn()}
        onCreateObjective={vi.fn()}
        onRefreshGoalCandidates={vi.fn()}
        onMaterializeGoalCandidate={vi.fn()}
      />
    );

    expect(screen.getByText('执行中')).toBeInTheDocument();
    expect(screen.getByText(/1 个 child task 正在执行，1\/2 已完成/i)).toBeInTheDocument();
    expect(screen.getByText(/root: in_progress/i)).toBeInTheDocument();
    expect(screen.getByText(/assigned 2/i)).toBeInTheDocument();
    expect(screen.getByText(/running 1/i)).toBeInTheDocument();
    expect(screen.getByText(/done 1/i)).toBeInTheDocument();
    expect(screen.getByText(/1\/2 child tasks done; 1 in progress/i)).toBeInTheDocument();
    expect(screen.getByText('拆解 child tasks')).toBeInTheDocument();
    expect(screen.getByText('分配给 agents')).toBeInTheDocument();
    expect(screen.getByText('执行推进')).toBeInTheDocument();
    expect(screen.getByText('root task 已生成')).toBeInTheDocument();
    expect(screen.getByText('已拆解 2 个 child task')).toBeInTheDocument();
    expect(screen.getByText('已分配 2 个 child task')).toBeInTheDocument();
    expect(screen.getByText('1 个 child task 进入执行中')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /展开详细日志/i }));

    expect(screen.getByText('Create fixture')).toBeInTheDocument();
    expect(screen.getByText('Run collaboration test')).toBeInTheDocument();
    expect(screen.getAllByText('最新：进入执行中').length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole('button', { name: /create fixture/i }));
    expect(screen.getByText('最新：执行完成')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '查看全部事件' }));
    expect(screen.getAllByText(/最新：/).length).toBeGreaterThan(0);
    expect(screen.getAllByText('child task 已创建').length).toBeGreaterThan(0);
    expect(screen.getByText('已分配给 worker-a')).toBeInTheDocument();
    expect(screen.getByText('已分配给 worker-b')).toBeInTheDocument();
    expect(screen.getAllByText('最新：进入执行中').length).toBeGreaterThan(0);
    await act(async () => {
      fireEvent.click(screen.getAllByRole('button', { name: /复制快照/i })[0]);
    });
    expect(clipboardWriteText).toHaveBeenCalled();
    expect(clipboardWriteText.mock.calls[0]?.[0]).toContain('task_id: child-1');
    expect(clipboardWriteText.mock.calls[0]?.[0]).toContain('assignee: worker-a');
    expect(clipboardWriteText.mock.calls[0]?.[0]).toContain('status: done');
    expect(screen.getByText('已复制')).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole('button', { name: /跳转到任务板/i })[1]);
    expect(scrollIntoView).toHaveBeenCalled();
    expect(taskBoardTarget.className).toContain('ring-2');
    vi.runAllTimers();
    expect(taskBoardTarget.className).not.toContain('ring-2');

    taskBoardTarget.remove();
    clipboardWriteText.mockRestore();
    vi.useRealTimers();
  });
});
