import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type { KeyboardEvent as ReactKeyboardEvent } from 'react';

import { useTranslation } from 'react-i18next';

import { Button, Input, Modal, Popconfirm } from 'antd';

import { useWorkspaceActions } from '@/stores/workspace';

import { WorkspaceSettingsPanel } from '@/pages/tenant/WorkspaceSettings';
import { formatDateTime } from '@/utils/date';

import { useLazyMessage } from '@/components/ui/lazyAntd';
import { ChatPanel } from '@/components/workspace/chat/ChatPanel';
import { GeneList } from '@/components/workspace/genes/GeneList';
import { MemberPanel } from '@/components/workspace/MemberPanel';
import {
  ObjectiveCreateModal,
  type ObjectiveFormValues,
} from '@/components/workspace/objectives/ObjectiveCreateModal';
import { ObjectiveList } from '@/components/workspace/objectives/ObjectiveList';
import { PresenceBar } from '@/components/workspace/presence/PresenceBar';
import { TaskBoard } from '@/components/workspace/TaskBoard';

import { buildBlackboardNotes, buildBlackboardStats } from './blackboardUtils';

import type {
  BlackboardPost,
  BlackboardReply,
  CyberGene,
  CyberObjective,
  TopologyEdge,
  TopologyNode,
  Workspace,
  WorkspaceAgent,
  WorkspaceTask,
} from '@/types/workspace';

export interface CentralBlackboardModalProps {
  open: boolean;
  tenantId: string;
  projectId: string;
  workspaceId: string;
  workspace: Workspace | null;
  posts: BlackboardPost[];
  repliesByPostId: Record<string, BlackboardReply[]>;
  loadedReplyPostIds: Record<string, boolean>;
  tasks: WorkspaceTask[];
  objectives: CyberObjective[];
  genes: CyberGene[];
  agents: WorkspaceAgent[];
  topologyNodes: TopologyNode[];
  topologyEdges: TopologyEdge[];
  onClose: () => void;
  onLoadReplies: (postId: string) => Promise<boolean>;
  onCreatePost: (data: { title: string; content: string }) => Promise<boolean>;
  onCreateReply: (postId: string, content: string) => Promise<boolean>;
  onDeletePost: (postId: string) => Promise<boolean>;
  onPinPost: (postId: string) => Promise<void>;
  onUnpinPost: (postId: string) => Promise<void>;
  onDeleteReply: (postId: string, replyId: string) => Promise<void>;
}

type BlackboardTab =
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

const { TextArea } = Input;

function statusBadgeTone(status: string | undefined): string {
  if (status === 'busy' || status === 'running') return 'bg-success';
  if (status === 'error') return 'bg-error';
  if (status === 'idle') return 'bg-text-muted dark:bg-text-muted';
  return 'bg-warning';
}

function getAuthorDisplay(authorId: string | null | undefined, fallback: string): string {
  const normalized = authorId?.trim();
  return normalized && normalized.length > 0 ? normalized : fallback;
}

export function CentralBlackboardModal({
  open,
  tenantId,
  projectId,
  workspaceId,
  workspace,
  posts,
  repliesByPostId,
  loadedReplyPostIds,
  tasks,
  objectives,
  genes,
  agents,
  topologyNodes,
  topologyEdges,
  onClose,
  onLoadReplies,
  onCreatePost,
  onCreateReply,
  onDeletePost,
  onPinPost,
  onUnpinPost,
  onDeleteReply,
}: CentralBlackboardModalProps) {
  const { t } = useTranslation();
  const message = useLazyMessage();
  const { createObjective, deleteObjective, deleteGene, updateGene } = useWorkspaceActions();
  const tabListRef = useRef<HTMLDivElement | null>(null);

  const [activeTab, setActiveTab] = useState<BlackboardTab>('goals');
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [postTitle, setPostTitle] = useState('');
  const [postContent, setPostContent] = useState('');
  const [replyDraft, setReplyDraft] = useState('');
  const [autoReplyRetryBlockedByPostId, setAutoReplyRetryBlockedByPostId] = useState<
    Record<string, boolean>
  >({});
  const [creatingPost, setCreatingPost] = useState(false);
  const [replying, setReplying] = useState(false);
  const [loadingRepliesPostId, setLoadingRepliesPostId] = useState<string | null>(null);
  const [togglingPostId, setTogglingPostId] = useState<string | null>(null);
  const [deletingPostId, setDeletingPostId] = useState<string | null>(null);
  const [deletingReplyId, setDeletingReplyId] = useState<string | null>(null);
  const [showCreateObjective, setShowCreateObjective] = useState(false);
  const [creatingObjective, setCreatingObjective] = useState(false);

  const stats = useMemo(
    () => buildBlackboardStats(tasks, posts, agents, topologyNodes),
    [agents, posts, tasks, topologyNodes]
  );
  const notes = useMemo(
    () => buildBlackboardNotes(workspace, objectives, posts),
    [objectives, posts, workspace]
  );
  const topologyNodeTitles = useMemo(
    () =>
      new Map(
        topologyNodes.map((node) => [
          node.id,
          getAuthorDisplay(node.title, t('blackboard.topologyUntitled', 'Untitled node')),
        ])
      ),
    [t, topologyNodes]
  );

  useEffect(() => {
    const fallbackPostId = posts.find((post) => post.is_pinned)?.id ?? posts[0]?.id ?? null;
    const hasSelectedPost = posts.some((post) => post.id === selectedPostId);

    if (!hasSelectedPost && fallbackPostId !== selectedPostId) {
      setSelectedPostId(fallbackPostId);
    }
  }, [posts, selectedPostId]);

  useEffect(() => {
    setReplyDraft('');
  }, [selectedPostId]);

  useEffect(() => {
    if (!open) {
      setAutoReplyRetryBlockedByPostId({});
    }
  }, [open]);

  const handleLoadReplies = useCallback(
    async (postId: string, options?: { manual?: boolean }) => {
      setLoadingRepliesPostId(postId);
      try {
        const loaded = await onLoadReplies(postId);

        if (loaded) {
          setAutoReplyRetryBlockedByPostId((current) => {
            if (!(postId in current)) {
              return current;
            }

            return { ...current, [postId]: false };
          });
          return;
        }

        if (!options?.manual) {
          setAutoReplyRetryBlockedByPostId((current) => ({ ...current, [postId]: true }));
        }
      } finally {
        setLoadingRepliesPostId((current) => (current === postId ? null : current));
      }
    },
    [onLoadReplies]
  );

  useEffect(() => {
    if (
      !open ||
      !selectedPostId ||
      loadedReplyPostIds[selectedPostId] ||
      autoReplyRetryBlockedByPostId[selectedPostId] === true ||
      loadingRepliesPostId === selectedPostId
    ) {
      return;
    }

    void handleLoadReplies(selectedPostId);
  }, [
    autoReplyRetryBlockedByPostId,
    handleLoadReplies,
    loadedReplyPostIds,
    loadingRepliesPostId,
    open,
    selectedPostId,
  ]);

  const selectedPost = posts.find((post) => post.id === selectedPostId) ?? null;
  const selectedReplies = selectedPost ? (repliesByPostId[selectedPost.id] ?? []) : [];
  const selectedRepliesLoaded = selectedPost ? loadedReplyPostIds[selectedPost.id] === true : false;

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
    [t]
  );

  const moveTabFocus = useCallback((nextIndex: number) => {
    const nextTab = tabs[nextIndex];
    if (!nextTab) {
      return;
    }

    setActiveTab(nextTab.key);

    requestAnimationFrame(() => {
      const nextButton = tabListRef.current?.querySelector<HTMLButtonElement>(
        `#blackboard-tab-${nextTab.key}`
      );
      nextButton?.focus();
    });
  }, [tabs]);

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
    [moveTabFocus, tabs.length]
  );

  const handleCreatePost = async () => {
    const title = postTitle.trim();
    const content = postContent.trim();
    if (!title || !content) {
      return;
    }

    setCreatingPost(true);
    try {
      const created = await onCreatePost({ title, content });
      if (created) {
        setPostTitle('');
        setPostContent('');
      }
    } finally {
      setCreatingPost(false);
    }
  };

  const handleCreateReply = async () => {
    if (!selectedPost) {
      return;
    }

    const nextContent = replyDraft.trim();
    if (!nextContent) {
      return;
    }

    setReplying(true);
    try {
      const created = await onCreateReply(selectedPost.id, nextContent);
      if (created) {
        setReplyDraft('');
      }
    } finally {
      setReplying(false);
    }
  };

  const handleTogglePin = async () => {
    if (!selectedPost) {
      return;
    }

    setTogglingPostId(selectedPost.id);
    try {
      if (selectedPost.is_pinned) {
        await onUnpinPost(selectedPost.id);
      } else {
        await onPinPost(selectedPost.id);
      }
    } finally {
      setTogglingPostId(null);
    }
  };

  const handleDeleteSelectedPost = async () => {
    if (!selectedPost) {
      return;
    }

    setDeletingPostId(selectedPost.id);
    try {
      const deleted = await onDeletePost(selectedPost.id);
      if (deleted) {
        setSelectedPostId((current) => (current === selectedPost.id ? null : current));
      }
    } finally {
      setDeletingPostId(null);
    }
  };

  const handleDeleteSelectedReply = async (replyId: string) => {
    if (!selectedPost) {
      return;
    }

    setDeletingReplyId(replyId);
    try {
      await onDeleteReply(selectedPost.id, replyId);
    } finally {
      setDeletingReplyId(null);
    }
  };

  const handleCreateObjective = async (values: ObjectiveFormValues) => {
    setCreatingObjective(true);
    try {
      const payload: Parameters<typeof createObjective>[3] = {
        title: values.title,
        obj_type: values.obj_type,
      };

      if (values.description) {
        payload.description = values.description;
      }
      if (values.parent_id) {
        payload.parent_id = values.parent_id;
      }

      await createObjective(tenantId, projectId, workspaceId, payload);
      setShowCreateObjective(false);
    } catch {
      message?.error(t('blackboard.errors.createObjective', 'Failed to create objective'));
    } finally {
      setCreatingObjective(false);
    }
  };

  const handleDeleteObjective = async (objectiveId: string) => {
    try {
      await deleteObjective(tenantId, projectId, workspaceId, objectiveId);
    } catch {
      message?.error(t('blackboard.errors.deleteObjective', 'Failed to delete objective'));
    }
  };

  const handleDeleteGene = async (geneId: string) => {
    try {
      await deleteGene(tenantId, projectId, workspaceId, geneId);
    } catch {
      message?.error(t('blackboard.errors.deleteGene', 'Failed to delete gene'));
    }
  };

  const handleToggleGeneActive = async (geneId: string, isActive: boolean) => {
    try {
      await updateGene(tenantId, projectId, workspaceId, geneId, { is_active: isActive });
    } catch {
      message?.error(t('blackboard.errors.updateGene', 'Failed to update gene'));
    }
  };

  return (
    <>
      <Modal
        open={open}
        onCancel={onClose}
        footer={null}
        centered
        destroyOnHidden
        width="min(1440px, calc(100vw - 24px))"
        className="[&_.ant-modal-close]:text-text-muted dark:[&_.ant-modal-close]:text-text-muted [&_.ant-modal-close:hover]:text-text-primary dark:[&_.ant-modal-close:hover]:text-text-inverse [&_.ant-modal-content]:!overflow-hidden [&_.ant-modal-content]:!border [&_.ant-modal-content]:!border-border-light dark:[&_.ant-modal-content]:!border-border-dark [&_.ant-modal-content]:!bg-surface-light dark:[&_.ant-modal-content]:!bg-surface-dark [&_.ant-modal-content]:!p-0 [&_.ant-modal-content]:shadow-2xl"
        styles={{
          mask: {
            backgroundColor: 'rgba(15, 23, 42, 0.5)',
            backdropFilter: 'blur(8px)',
          },
        }}
      >
        <div className="flex max-h-[calc(100dvh-24px)] min-h-[min(620px,calc(100dvh-24px))] flex-col overflow-hidden bg-surface-light dark:bg-surface-dark">
          <div className="border-b border-border-light px-4 py-4 dark:border-border-dark sm:px-6">
            <div className="pr-10">
              <div className="text-xl font-semibold text-text-primary dark:text-text-inverse">
                {t('blackboard.title', 'Blackboard')}
              </div>
              <div className="mt-1 text-sm text-text-secondary dark:text-text-muted">
                {workspace?.name ??
                  t(
                    'blackboard.modalSubtitle',
                    'Shared goals, tasks, discussions, and topology for the active workspace.'
                  )}
              </div>
            </div>
          </div>

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
                  setActiveTab(tab.key);
                }}
                className={`rounded-full px-4 py-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 ${
                  activeTab === tab.key
                    ? 'bg-primary/10 text-primary'
                    : 'text-text-secondary hover:bg-surface-muted hover:text-text-primary dark:text-text-muted dark:hover:bg-surface-elevated dark:hover:text-text-inverse'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {tabs.map((tab) => (
            <div
              key={tab.key}
              id={`blackboard-panel-${tab.key}`}
              role="tabpanel"
              aria-labelledby={`blackboard-tab-${tab.key}`}
              tabIndex={activeTab === tab.key ? 0 : -1}
              hidden={activeTab !== tab.key}
              className="min-h-0 flex-1 overflow-y-auto px-4 py-4 focus-visible:outline-none sm:px-6 sm:py-5"
            >
              {activeTab === tab.key && (
                <>
            {activeTab === 'goals' && (
              <div className="space-y-5">
                <section className="rounded-2xl border border-border-light bg-surface-muted px-4 py-4 dark:border-border-dark dark:bg-background-dark/35">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="max-w-2xl">
                      <h3 className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                        {t('blackboard.goalsOverviewTitle', 'Goals and delivery')}
                      </h3>
                      <p className="mt-1 text-sm leading-7 text-text-secondary dark:text-text-muted">
                        {t(
                          'blackboard.goalsOverviewBody',
                          'Review shared outcomes and the delivery queue together so the blackboard stays connected to execution.'
                        )}
                      </p>
                    </div>
                    <dl className="flex flex-wrap gap-2">
                      {[
                        {
                          key: 'completion',
                          label: t('blackboard.metrics.completion', 'Task completion'),
                          value: `${String(stats.completionRatio)}%`,
                        },
                        {
                          key: 'objectives',
                          label: t('blackboard.objectivesTitle', 'Goals'),
                          value: String(objectives.length),
                        },
                        {
                          key: 'tasks',
                          label: t('blackboard.metrics.tasks', 'Tasks'),
                          value: String(tasks.length),
                        },
                      ].map((metric) => (
                        <div
                          key={metric.key}
                          className="rounded-full border border-border-light bg-surface-light px-3 py-2 dark:border-border-dark dark:bg-surface-dark-alt"
                        >
                          <dt className="text-[11px] uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
                            {metric.label}
                          </dt>
                          <dd className="mt-0.5 text-sm font-semibold text-text-primary dark:text-text-inverse">
                            {metric.value}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                </section>

                <ObjectiveList
                  objectives={objectives}
                  onDelete={(objectiveId) => {
                    void handleDeleteObjective(objectiveId);
                  }}
                  onCreate={() => {
                    setShowCreateObjective(true);
                  }}
                />

                <TaskBoard workspaceId={workspaceId} />
              </div>
            )}

            {activeTab === 'discussion' && (
              <div className="grid gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
                <section className="min-w-0 space-y-4">
                  <div className="rounded-3xl border border-border-light bg-surface-muted p-4 dark:border-border-dark dark:bg-surface-dark-alt">
                    <h3 className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                      {t('blackboard.newPost', 'New Post')}
                    </h3>
                    <div className="mt-4 space-y-3">
                      <label
                        htmlFor="blackboard-post-title"
                        className="block text-xs font-medium uppercase tracking-[0.16em] text-text-muted dark:text-text-muted"
                      >
                        {t('blackboard.postTitle', 'Title')}
                      </label>
                      <Input
                        id="blackboard-post-title"
                        value={postTitle}
                        aria-label={t('blackboard.postTitle', 'Title')}
                        onChange={(event) => {
                          setPostTitle(event.target.value);
                        }}
                        placeholder={t('blackboard.postTitle', 'Title')}
                        maxLength={200}
                        className="min-h-11"
                      />
                      <label
                        htmlFor="blackboard-post-content"
                        className="block text-xs font-medium uppercase tracking-[0.16em] text-text-muted dark:text-text-muted"
                      >
                        {t('blackboard.postContent', 'Content')}
                      </label>
                      <TextArea
                        id="blackboard-post-content"
                        value={postContent}
                        aria-label={t('blackboard.postContent', 'Content')}
                        onChange={(event) => {
                          setPostContent(event.target.value);
                        }}
                        placeholder={t('blackboard.postContent', 'Content')}
                        rows={5}
                        maxLength={2000}
                        showCount
                      />
                      <Button
                        type="primary"
                        onClick={() => {
                          void handleCreatePost();
                        }}
                        disabled={creatingPost || !postTitle.trim() || !postContent.trim()}
                        loading={creatingPost}
                        className="min-h-11 w-full sm:w-auto"
                      >
                        {t('blackboard.createPost', 'Create Post')}
                      </Button>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {posts.map((post) => (
                      <button
                        type="button"
                        key={post.id}
                        onClick={() => {
                          setSelectedPostId(post.id);
                        }}
                        className={`w-full rounded-3xl border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 ${
                          selectedPostId === post.id
                            ? 'border-primary/30 bg-primary/8'
                            : 'border-border-light bg-surface-muted hover:border-border-separator hover:bg-surface-light dark:border-border-dark dark:bg-surface-dark-alt dark:hover:border-border-dark dark:hover:bg-surface-elevated'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h4 className="truncate text-sm font-semibold text-text-primary dark:text-text-inverse">
                              {post.title}
                            </h4>
                            <p className="mt-2 line-clamp-3 break-words text-sm leading-6 text-text-secondary dark:text-text-muted">
                              {post.content}
                            </p>
                          </div>
                          {post.is_pinned && (
                            <span className="rounded-full border border-primary/25 bg-primary/10 px-2 py-1 text-[11px] text-primary dark:text-primary-200">
                              {t('blackboard.pinned', 'Pinned')}
                            </span>
                          )}
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-3 text-xs text-text-muted dark:text-text-muted">
                          <span>{formatDateTime(post.created_at)}</span>
                          <span>
                            {loadedReplyPostIds[post.id]
                              ? `${String((repliesByPostId[post.id] ?? []).length)} ${t('blackboard.replies', 'Replies')}`
                              : t('blackboard.open', 'Open')}
                          </span>
                        </div>
                      </button>
                    ))}

                    {posts.length === 0 && (
                      <div className="rounded-3xl border border-dashed border-border-separator bg-surface-light p-6 text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                        {t('blackboard.noPosts', 'No posts yet')}
                      </div>
                    )}
                  </div>
                </section>

                <section className="min-w-0 rounded-3xl border border-border-light bg-surface-light p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                  {selectedPost ? (
                    <div className="space-y-5">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div className="min-w-0">
                          <div className="text-[11px] uppercase tracking-[0.18em] text-text-muted dark:text-text-muted">
                            {t('blackboard.createdBy', 'Created by')}
                          </div>
                          <div className="mt-1 break-all text-xs font-medium text-text-secondary dark:text-text-secondary">
                            {getAuthorDisplay(
                              selectedPost.author_id,
                              t('blackboard.unknownAuthor', 'Unknown author')
                            )}
                          </div>
                          <h3 className="mt-2 break-words text-2xl font-semibold text-text-primary dark:text-text-inverse">
                            {selectedPost.title}
                          </h3>
                        </div>
                        <div className="rounded-full border border-border-light bg-surface-muted px-3 py-1.5 text-xs text-text-muted dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                          {formatDateTime(selectedPost.created_at)}
                        </div>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        <button
                          type="button"
                          onClick={() => {
                            void handleTogglePin();
                          }}
                          disabled={togglingPostId === selectedPost.id}
                           className="min-h-10 rounded-2xl border border-border-light bg-surface-muted px-4 text-sm text-text-primary transition hover:border-primary/30 hover:bg-primary/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-border-dark dark:bg-surface-dark-alt dark:text-text-inverse"
                         >
                          {selectedPost.is_pinned
                            ? t('blackboard.unpin', 'Unpin')
                            : t('blackboard.pin', 'Pin')}
                        </button>

                        <Popconfirm
                          title={t('blackboard.deleteConfirm', 'Are you sure you want to delete this post?')}
                          okText={t('common.yes', 'Yes')}
                          cancelText={t('common.no', 'No')}
                          onConfirm={() => {
                            void handleDeleteSelectedPost();
                          }}
                        >
                          <button
                            type="button"
                            disabled={deletingPostId === selectedPost.id}
                             className="min-h-10 rounded-2xl border border-error/25 bg-error/10 px-4 text-sm text-status-text-error transition hover:bg-error/15 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60 dark:text-status-text-error-dark"
                           >
                            {t('blackboard.delete', 'Delete')}
                          </button>
                        </Popconfirm>
                      </div>

                      <article className="rounded-3xl border border-border-light bg-surface-muted p-5 text-sm leading-7 text-text-secondary dark:border-border-dark dark:bg-surface-dark-alt dark:text-text-secondary">
                        {selectedPost.content}
                      </article>

                      <div>
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <h4 className="text-base font-semibold text-text-primary dark:text-text-inverse">
                            {t('blackboard.replies', 'Replies')}
                          </h4>
                          <span className="text-xs text-text-muted dark:text-text-muted">
                            {String(selectedReplies.length)}
                          </span>
                        </div>

                        <div className="space-y-3">
                          {!selectedRepliesLoaded && loadingRepliesPostId === selectedPost.id && (
                             <div className="rounded-3xl border border-border-light bg-surface-muted px-4 py-5 text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark-alt dark:text-text-muted">
                               {t('common.loading', 'Loading…')}
                             </div>
                           )}

                           {!selectedRepliesLoaded && loadingRepliesPostId !== selectedPost.id && (
                             <div className="rounded-3xl border border-dashed border-border-separator bg-surface-light p-5 text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                               <div>
                                 {t('blackboard.repliesUnavailable', 'Replies are not loaded yet.')}
                               </div>
                                <button
                                 type="button"
                                 onClick={() => {
                                   void handleLoadReplies(selectedPost.id, { manual: true });
                                 }}
                                 className="mt-3 rounded-2xl border border-border-light px-4 py-2 text-sm text-text-primary transition hover:border-primary/30 hover:bg-primary/8 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 dark:border-border-dark dark:text-text-inverse"
                               >
                                 {t('blackboard.retryReplies', 'Retry loading replies')}
                               </button>
                            </div>
                          )}

                          {selectedRepliesLoaded &&
                            selectedReplies.map((reply) => (
                              <article
                                key={reply.id}
                                 className="rounded-3xl border border-border-light bg-surface-muted p-4 dark:border-border-dark dark:bg-surface-dark-alt"
                               >
                                  <div className="flex items-start justify-between gap-3">
                                    <div className="min-w-0">
                                      <div className="text-[11px] uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
                                        {t('blackboard.createdBy', 'Created by')}
                                      </div>
                                      <div className="mt-1 break-all text-sm font-medium text-text-primary dark:text-text-inverse">
                                        {getAuthorDisplay(
                                          reply.author_id,
                                          t('blackboard.unknownAuthor', 'Unknown author')
                                        )}
                                      </div>
                                      <div className="mt-1 text-xs text-text-muted dark:text-text-muted">
                                        {formatDateTime(reply.created_at)}
                                      </div>
                                    </div>
                                  <Popconfirm
                                    title={t('blackboard.deleteReplyConfirm', 'Are you sure you want to delete this reply?')}
                                    okText={t('common.yes', 'Yes')}
                                    cancelText={t('common.no', 'No')}
                                    onConfirm={() => {
                                      void handleDeleteSelectedReply(reply.id);
                                    }}
                                  >
                                    <button
                                      type="button"
                                      disabled={deletingReplyId === reply.id}
                                       className="rounded-xl border border-border-light px-3 py-2 text-xs text-text-secondary transition hover:border-error/25 hover:bg-error/10 hover:text-status-text-error focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-border-dark dark:text-text-secondary dark:hover:text-status-text-error-dark"
                                     >
                                       {t('blackboard.delete', 'Delete')}
                                     </button>
                                  </Popconfirm>
                                </div>
                                <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-6 text-text-secondary dark:text-text-muted">
                                  {reply.content}
                                </p>
                              </article>
                            ))}

                          {selectedRepliesLoaded && selectedReplies.length === 0 && (
                            <div className="rounded-3xl border border-dashed border-border-separator bg-surface-light p-5 text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                              {t('blackboard.noReplies', 'No replies yet')}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="rounded-3xl border border-border-light bg-surface-muted p-4 dark:border-border-dark dark:bg-surface-dark-alt">
                        <h4 className="text-sm font-semibold text-text-primary dark:text-text-inverse">
                          {t('blackboard.reply', 'Reply')}
                        </h4>
                        <label
                          htmlFor="blackboard-reply-draft"
                          className="mt-3 block text-xs font-medium uppercase tracking-[0.16em] text-text-muted dark:text-text-muted"
                        >
                          {t('blackboard.writeReply', 'Write a reply...')}
                        </label>
                        <TextArea
                          id="blackboard-reply-draft"
                          value={replyDraft}
                          aria-label={t('blackboard.writeReply', 'Write a reply...')}
                          onChange={(event) => {
                            setReplyDraft(event.target.value);
                          }}
                          placeholder={t('blackboard.writeReply', 'Write a reply...')}
                          rows={4}
                          maxLength={1000}
                          showCount
                          className="mt-3"
                        />
                        <div className="mt-3 flex justify-end">
                          <Button
                            type="primary"
                            onClick={() => {
                              void handleCreateReply();
                            }}
                            disabled={replying || !replyDraft.trim()}
                            loading={replying}
                            className="min-h-11"
                          >
                            {t('blackboard.sendReply', 'Send')}
                          </Button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex min-h-[320px] items-center justify-center rounded-3xl border border-dashed border-border-separator bg-surface-light text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                      {t('blackboard.selectPost', 'Select a post to view details')}
                    </div>
                  )}
                </section>
              </div>
            )}

            {activeTab === 'collaboration' && (
              <div className="rounded-3xl border border-border-light bg-surface-light p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                <div className="mb-4">
                  <div className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                    {t('blackboard.tabs.collaboration', 'Collaboration')}
                  </div>
                  <p className="mt-1 text-sm text-text-secondary dark:text-text-muted">
                    {t(
                      'blackboard.collaborationHint',
                      'Keep the workspace-wide collaboration stream inside the central blackboard so execution and discussion stay in one place.'
                    )}
                  </p>
                </div>
                <div className="min-h-[560px]">
                  <ChatPanel tenantId={tenantId} projectId={projectId} workspaceId={workspaceId} />
                </div>
              </div>
            )}

            {activeTab === 'members' && (
              <div className="rounded-3xl border border-border-light bg-surface-light p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                <MemberPanel tenantId={tenantId} projectId={projectId} workspaceId={workspaceId} />
              </div>
            )}

            {activeTab === 'genes' && (
              <div className="rounded-3xl border border-border-light bg-surface-light p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                <GeneList
                  genes={genes}
                  onDelete={(geneId) => {
                    void handleDeleteGene(geneId);
                  }}
                  onToggleActive={(geneId, isActive) => {
                    void handleToggleGeneActive(geneId, isActive);
                  }}
                />
              </div>
            )}

            {activeTab === 'files' && (
              <div className="rounded-3xl border border-dashed border-border-separator bg-surface-light p-8 text-center dark:border-border-dark dark:bg-surface-dark">
                <div className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                  {t('blackboard.filesUnavailableTitle', 'Shared files are not wired here yet')}
                </div>
                <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-text-secondary dark:text-text-muted">
                  {t(
                    'blackboard.filesUnavailableBody',
                    'The central blackboard already combines discussion, goals, and execution. File operations can be added later when a workspace-scoped file endpoint is available.'
                  )}
                </p>
              </div>
            )}

            {activeTab === 'status' && (
              <div className="space-y-5">
                <section className="rounded-2xl border border-border-light bg-surface-muted px-4 py-4 dark:border-border-dark dark:bg-background-dark/35">
                  <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                    <div className="max-w-2xl">
                      <h3 className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                        {t('blackboard.statusOverviewTitle', 'Status and presence')}
                      </h3>
                      <p className="mt-1 text-sm leading-7 text-text-secondary dark:text-text-muted">
                        {t(
                          'blackboard.statusOverviewBody',
                          'Keep agent activity, discussion volume, and topology changes in a single operational read.'
                        )}
                      </p>
                    </div>
                    <dl className="flex flex-wrap gap-2">
                      {[
                        {
                          key: 'progress',
                          label: t('blackboard.metrics.completion', 'Task completion'),
                          value: `${String(stats.completionRatio)}%`,
                        },
                        {
                          key: 'threads',
                          label: t('blackboard.metrics.discussions', 'Discussions'),
                          value: String(stats.discussions),
                        },
                        {
                          key: 'agents',
                          label: t('blackboard.metrics.activeAgents', 'Active agents'),
                          value: String(stats.activeAgents),
                        },
                        {
                          key: 'edges',
                          label: t('blackboard.metrics.links', 'Topology links'),
                          value: String(topologyEdges.length),
                        },
                      ].map((metric) => (
                        <div
                          key={metric.key}
                          className="rounded-full border border-border-light bg-surface-light px-3 py-2 dark:border-border-dark dark:bg-surface-dark-alt"
                        >
                          <dt className="text-[11px] uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
                            {metric.label}
                          </dt>
                          <dd className="mt-0.5 text-sm font-semibold text-text-primary dark:text-text-inverse">
                            {metric.value}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </div>
                </section>

                <PresenceBar workspaceId={workspaceId} />

                <section className="rounded-3xl border border-border-light bg-surface-light p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                  <h3 className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                    {t('blackboard.agentStatusTitle', 'Agent status')}
                  </h3>
                  <p className="mt-1 text-sm leading-7 text-text-secondary dark:text-text-muted">
                    {t(
                      'blackboard.agentStatusBody',
                      'Review workspace-bound agents, their current state, and any placement metadata without leaving the modal.'
                    )}
                  </p>
                  <div className="mt-4 space-y-3">
                    {agents.map((agent) => (
                      <div
                        key={agent.id}
                        className="flex flex-col gap-3 rounded-2xl border border-border-light bg-surface-muted px-4 py-4 sm:flex-row sm:items-center sm:justify-between dark:border-border-dark dark:bg-background-dark/45"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-3">
                            <span
                              className={`h-2.5 w-2.5 rounded-full ${statusBadgeTone(agent.status)}`}
                            />
                            <div className="truncate text-sm font-medium text-text-primary dark:text-text-inverse">
                              {agent.display_name ?? agent.label ?? agent.agent_id}
                            </div>
                          </div>
                          <div className="mt-1 break-all font-mono text-[11px] text-text-muted dark:text-text-muted">
                            {agent.agent_id}
                            {agent.hex_q !== undefined && agent.hex_r !== undefined && (
                              <>
                                {' '}
                                · q {String(agent.hex_q)} / r {String(agent.hex_r)}
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-text-secondary dark:text-text-secondary">
                          <span className="rounded-full border border-border-light bg-surface-light px-3 py-1.5 dark:border-border-dark dark:bg-surface-dark">
                            {agent.status ?? t('blackboard.unknownStatus', 'unknown')}
                          </span>
                          {agent.theme_color && (
                            <span className="inline-flex items-center gap-2 rounded-full border border-border-light bg-surface-light px-3 py-1.5 dark:border-border-dark dark:bg-surface-dark">
                              <span
                                className="h-2.5 w-2.5 rounded-full"
                                style={{ backgroundColor: agent.theme_color }}
                              />
                              {t('blackboard.accentConfigured', 'Accent')}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}

                    {agents.length === 0 && (
                      <div className="rounded-2xl border border-dashed border-border-separator bg-surface-light p-5 text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                        {t('blackboard.noAgents', 'No agents have been bound to this workspace yet.')}
                      </div>
                    )}
                  </div>
                </section>
              </div>
            )}

            {activeTab === 'notes' && (
              <div className="space-y-4">
                {notes.map((note) => (
                  <article
                    key={note.id}
                    className="rounded-3xl border border-border-light bg-surface-muted p-5 dark:border-border-dark dark:bg-surface-dark-alt"
                  >
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="rounded-full border border-border-light bg-surface-light px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-text-muted dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                        {t(`blackboard.noteKinds.${note.kind}`, note.kind)}
                      </span>
                    </div>
                    <h3 className="mt-4 break-words text-lg font-semibold text-text-primary dark:text-text-inverse">
                      {note.title}
                    </h3>
                    <p className="mt-3 whitespace-pre-wrap break-words text-sm leading-7 text-text-secondary dark:text-text-muted">
                      {note.summary}
                    </p>
                  </article>
                ))}

                {notes.length === 0 && (
                  <div className="rounded-3xl border border-dashed border-border-separator bg-surface-light p-8 text-center text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                    {t(
                      'blackboard.noNotes',
                      'No shared notes yet. Add workspace description, objectives, or pinned discussions to make this tab more useful.'
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'topology' && (
              <div className="space-y-5">
                <div className="rounded-3xl border border-border-light bg-surface-muted p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                  <div className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                    {t('blackboard.commandCenter', 'Workspace command center')}
                  </div>
                  <p className="mt-2 text-sm leading-7 text-text-secondary dark:text-text-muted">
                    {t(
                      'blackboard.topologyHint',
                      'The live command surface stays on the page canvas. Use this tab for a structured read of current nodes, connections, and placements while the main board remains visible behind the modal.'
                    )}
                  </p>
                </div>

                <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
                  <div className="rounded-3xl border border-border-light bg-surface-light p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <h3 className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                        {t('blackboard.topologyNodesTitle', 'Nodes')}
                      </h3>
                      <span className="rounded-full bg-surface-muted px-3 py-1 text-xs text-text-muted dark:bg-surface-dark dark:text-text-muted">
                        {String(topologyNodes.length)}
                      </span>
                    </div>
                    <div className="space-y-3">
                      {topologyNodes.map((node) => (
                        <article
                          key={node.id}
                          className="rounded-3xl border border-border-light bg-surface-muted p-4 dark:border-border-dark dark:bg-surface-dark-alt"
                        >
                          <div className="flex flex-wrap items-center gap-3">
                            <span className="rounded-full border border-border-light bg-surface-light px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-text-muted dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                              {node.node_type}
                            </span>
                            {node.status && (
                              <span className="rounded-full bg-surface-light px-3 py-1 text-xs text-text-secondary dark:bg-surface-dark dark:text-text-secondary">
                                {node.status}
                              </span>
                            )}
                          </div>
                          <h4 className="mt-3 break-words text-sm font-semibold text-text-primary dark:text-text-inverse">
                            {node.title}
                          </h4>
                          <div className="mt-3 break-all text-xs text-text-muted dark:text-text-muted">
                            {node.hex_q !== undefined && node.hex_r !== undefined
                              ? `q ${String(node.hex_q)} · r ${String(node.hex_r)}`
                              : t('blackboard.topologyUnplaced', 'No hex placement')}
                          </div>
                        </article>
                      ))}

                      {topologyNodes.length === 0 && (
                        <div className="rounded-3xl border border-dashed border-border-separator bg-surface-light p-5 text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                          {t('blackboard.noTopologyNodes', 'No topology nodes yet.')}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="rounded-3xl border border-border-light bg-surface-light p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <h3 className="text-lg font-semibold text-text-primary dark:text-text-inverse">
                        {t('blackboard.topologyEdgesTitle', 'Edges')}
                      </h3>
                      <span className="rounded-full bg-surface-muted px-3 py-1 text-xs text-text-muted dark:bg-surface-dark dark:text-text-muted">
                        {String(topologyEdges.length)}
                      </span>
                    </div>
                    <div className="space-y-3">
                      {topologyEdges.map((edge) => (
                        <article
                          key={edge.id}
                          className="rounded-3xl border border-border-light bg-surface-muted p-4 dark:border-border-dark dark:bg-surface-dark-alt"
                        >
                          <div className="text-[11px] uppercase tracking-[0.16em] text-text-muted dark:text-text-muted">
                            {t('blackboard.topologyLink', 'Topology link')}
                          </div>
                          <div className="mt-2 break-words text-sm font-medium text-text-primary dark:text-text-inverse">
                            {(topologyNodeTitles.get(edge.source_node_id) ?? edge.source_node_id) +
                              ' → ' +
                              (topologyNodeTitles.get(edge.target_node_id) ?? edge.target_node_id)}
                          </div>
                          <div className="mt-2 break-all font-mono text-[11px] text-text-muted dark:text-text-muted">
                            {edge.source_node_id} → {edge.target_node_id}
                          </div>
                        </article>
                      ))}

                      {topologyEdges.length === 0 && (
                        <div className="rounded-3xl border border-dashed border-border-separator bg-surface-light p-5 text-sm text-text-secondary dark:border-border-dark dark:bg-surface-dark dark:text-text-muted">
                          {t('blackboard.noTopologyEdges', 'No topology edges yet.')}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="rounded-3xl border border-border-light bg-surface-light p-5 dark:border-border-dark dark:bg-surface-dark-alt">
                <WorkspaceSettingsPanel
                  tenantId={tenantId}
                  projectId={projectId}
                  workspaceId={workspaceId}
                />
              </div>
            )}
                </>
              )}
            </div>
          ))}
        </div>
      </Modal>

      <ObjectiveCreateModal
        open={showCreateObjective}
        onClose={() => {
          setShowCreateObjective(false);
        }}
        onSubmit={(values) => {
          void handleCreateObjective(values);
        }}
        parentObjectives={objectives}
        loading={creatingObjective}
      />
    </>
  );
}
