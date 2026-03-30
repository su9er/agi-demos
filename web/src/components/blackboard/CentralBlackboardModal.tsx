import { useCallback, useEffect, useMemo, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Modal, Popconfirm } from 'antd';

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
  onLoadReplies: (postId: string) => Promise<void>;
  onCreatePost: (data: { title: string; content: string }) => Promise<void>;
  onCreateReply: (postId: string, content: string) => Promise<void>;
  onDeletePost: (postId: string) => Promise<void>;
  onPinPost: (postId: string) => Promise<void>;
  onUnpinPost: (postId: string) => Promise<void>;
  onDeleteReply: (postId: string, replyId: string) => Promise<void>;
}

function statusBadgeTone(status: string | undefined): string {
  if (status === 'busy' || status === 'running') return 'bg-emerald-500';
  if (status === 'error') return 'bg-rose-500';
  if (status === 'idle') return 'bg-zinc-500';
  return 'bg-amber-400';
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

  const [activeTab, setActiveTab] = useState<
    | 'goals'
    | 'discussion'
    | 'collaboration'
    | 'members'
    | 'genes'
    | 'files'
    | 'status'
    | 'notes'
    | 'topology'
    | 'settings'
  >('goals');
  const [selectedPostId, setSelectedPostId] = useState<string | null>(null);
  const [postTitle, setPostTitle] = useState('');
  const [postContent, setPostContent] = useState('');
  const [replyDraft, setReplyDraft] = useState('');
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

  const handleLoadReplies = useCallback(
    async (postId: string) => {
      setLoadingRepliesPostId(postId);
      try {
        await onLoadReplies(postId);
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
      loadingRepliesPostId === selectedPostId
    ) {
      return;
    }

    void handleLoadReplies(selectedPostId);
  }, [handleLoadReplies, loadedReplyPostIds, loadingRepliesPostId, open, selectedPostId]);

  const selectedPost = posts.find((post) => post.id === selectedPostId) ?? null;
  const selectedReplies = selectedPost ? (repliesByPostId[selectedPost.id] ?? []) : [];
  const selectedRepliesLoaded = selectedPost ? loadedReplyPostIds[selectedPost.id] === true : false;

  const tabs = [
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
  ] as const;

  const handleCreatePost = async () => {
    const title = postTitle.trim();
    const content = postContent.trim();
    if (!title || !content) {
      return;
    }

    setCreatingPost(true);
    try {
      await onCreatePost({ title, content });
      setPostTitle('');
      setPostContent('');
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
      await onCreateReply(selectedPost.id, nextContent);
      setReplyDraft('');
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
      await onDeletePost(selectedPost.id);
      setSelectedPostId((current) => (current === selectedPost.id ? null : current));
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
        width={1440}
        className="[&_.ant-modal-close]:text-zinc-400 [&_.ant-modal-close:hover]:text-zinc-100 [&_.ant-modal-content]:!overflow-hidden [&_.ant-modal-content]:!border [&_.ant-modal-content]:!border-white/8 [&_.ant-modal-content]:!bg-[#111214] [&_.ant-modal-content]:!p-0 [&_.ant-modal-content]:shadow-[0_40px_120px_rgba(0,0,0,0.55)]"
        styles={{
          mask: {
            backgroundColor: 'rgba(3, 7, 18, 0.76)',
            backdropFilter: 'blur(10px)',
          },
          header: {
            marginBottom: 0,
            padding: '20px 24px',
            background: '#111214',
            borderBottom: '1px solid rgba(255, 255, 255, 0.08)',
          },
          body: {
            padding: 0,
            background: '#111214',
          },
        }}
        title={
          <div className="pr-10">
            <div className="text-xl font-semibold text-zinc-100">
              {t('blackboard.title', 'Blackboard')}
            </div>
            <div className="mt-1 text-sm text-zinc-500">
              {workspace?.name ??
                t(
                  'blackboard.modalSubtitle',
                  'Shared goals, tasks, discussions, and topology for the active workspace.'
                )}
            </div>
          </div>
        }
      >
        <div className="max-h-[calc(100vh-140px)] min-h-[620px] overflow-hidden bg-[#111214]">
          <div
            role="tablist"
            aria-label={t('blackboard.tabs.ariaLabel', 'Blackboard sections')}
            className="flex gap-1 overflow-x-auto border-b border-white/8 px-4 py-3 sm:px-6"
          >
            {tabs.map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={activeTab === tab.key}
                onClick={() => {
                  setActiveTab(tab.key);
                }}
                className={`rounded-full px-4 py-2 text-sm transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300/80 ${
                  activeTab === tab.key
                    ? 'bg-violet-500/18 text-violet-100'
                    : 'text-zinc-400 hover:bg-white/5 hover:text-zinc-100'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          <div className="max-h-[calc(100vh-210px)] overflow-y-auto px-4 py-4 sm:px-6 sm:py-5">
            {activeTab === 'goals' && (
              <div className="space-y-6 dark">
                <div className="grid gap-3 md:grid-cols-3">
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
                      className="rounded-3xl border border-white/8 bg-white/[0.03] p-4"
                    >
                      <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">
                        {metric.label}
                      </div>
                      <div className="mt-2 text-2xl font-semibold text-zinc-100">{metric.value}</div>
                    </div>
                  ))}
                </div>

                <div className="rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                  <ObjectiveList
                    objectives={objectives}
                    onDelete={(objectiveId) => {
                      void handleDeleteObjective(objectiveId);
                    }}
                    onCreate={() => {
                      setShowCreateObjective(true);
                    }}
                  />
                </div>

                <div className="rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                  <TaskBoard workspaceId={workspaceId} />
                </div>
              </div>
            )}

            {activeTab === 'discussion' && (
              <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
                <section className="space-y-4">
                  <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-4">
                    <h3 className="text-lg font-semibold text-zinc-100">
                      {t('blackboard.newPost', 'New Post')}
                    </h3>
                    <div className="mt-4 space-y-3">
                      <input
                        value={postTitle}
                        aria-label={t('blackboard.postTitle', 'Title')}
                        onChange={(event) => {
                          setPostTitle(event.target.value);
                        }}
                        placeholder={t('blackboard.postTitle', 'Title')}
                        className="min-h-11 w-full rounded-2xl border border-white/8 bg-white/[0.04] px-4 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-violet-400/60 focus:outline-none"
                      />
                      <textarea
                        value={postContent}
                        aria-label={t('blackboard.postContent', 'Content')}
                        onChange={(event) => {
                          setPostContent(event.target.value);
                        }}
                        placeholder={t('blackboard.postContent', 'Content')}
                        rows={5}
                        className="w-full rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3 text-sm leading-6 text-zinc-100 placeholder:text-zinc-500 focus:border-violet-400/60 focus:outline-none"
                      />
                      <button
                        type="button"
                        onClick={() => {
                          void handleCreatePost();
                        }}
                        disabled={creatingPost || !postTitle.trim() || !postContent.trim()}
                        className="min-h-11 rounded-2xl bg-violet-500 px-4 text-sm font-medium text-white transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {creatingPost
                          ? t('blackboard.creatingPost', 'Creating…')
                          : t('blackboard.createPost', 'Create Post')}
                      </button>
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
                        className={`w-full rounded-3xl border p-4 text-left transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300/80 ${
                          selectedPostId === post.id
                            ? 'border-violet-400/40 bg-violet-500/12'
                            : 'border-white/8 bg-white/[0.03] hover:border-white/15 hover:bg-white/[0.05]'
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h4 className="truncate text-sm font-semibold text-zinc-100">
                              {post.title}
                            </h4>
                            <p className="mt-2 line-clamp-3 text-sm leading-6 text-zinc-500">
                              {post.content}
                            </p>
                          </div>
                          {post.is_pinned && (
                            <span className="rounded-full border border-violet-400/30 bg-violet-500/12 px-2 py-1 text-[11px] text-violet-100">
                              {t('blackboard.pinned', 'Pinned')}
                            </span>
                          )}
                        </div>
                        <div className="mt-3 flex items-center justify-between gap-3 text-xs text-zinc-500">
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
                      <div className="rounded-3xl border border-dashed border-white/8 bg-white/[0.02] p-6 text-sm text-zinc-500">
                        {t('blackboard.noPosts', 'No posts yet')}
                      </div>
                    )}
                  </div>
                </section>

                <section className="rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                  {selectedPost ? (
                    <div className="space-y-5">
                      <div className="flex flex-wrap items-start justify-between gap-4">
                        <div>
                          <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">
                            {selectedPost.author_id}
                          </div>
                          <h3 className="mt-2 text-2xl font-semibold text-zinc-100">
                            {selectedPost.title}
                          </h3>
                        </div>
                        <div className="rounded-full border border-white/8 bg-white/5 px-3 py-1.5 text-xs text-zinc-400">
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
                          className="min-h-10 rounded-2xl border border-white/8 bg-white/[0.03] px-4 text-sm text-zinc-100 transition hover:border-violet-400/40 hover:bg-violet-500/12 disabled:cursor-not-allowed disabled:opacity-60"
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
                            className="min-h-10 rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 text-sm text-rose-100 transition hover:bg-rose-500/18 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {t('blackboard.delete', 'Delete')}
                          </button>
                        </Popconfirm>
                      </div>

                      <article className="rounded-3xl border border-white/8 bg-white/[0.03] p-5 text-sm leading-7 text-zinc-300">
                        {selectedPost.content}
                      </article>

                      <div>
                        <div className="mb-3 flex items-center justify-between gap-3">
                          <h4 className="text-base font-semibold text-zinc-100">
                            {t('blackboard.replies', 'Replies')}
                          </h4>
                          <span className="text-xs text-zinc-500">
                            {String(selectedReplies.length)}
                          </span>
                        </div>

                        <div className="space-y-3">
                          {!selectedRepliesLoaded && loadingRepliesPostId === selectedPost.id && (
                            <div className="rounded-3xl border border-white/8 bg-white/[0.03] px-4 py-5 text-sm text-zinc-500">
                              {t('common.loading', 'Loading…')}
                            </div>
                          )}

                          {!selectedRepliesLoaded && loadingRepliesPostId !== selectedPost.id && (
                            <div className="rounded-3xl border border-dashed border-white/8 bg-white/[0.02] p-5 text-sm text-zinc-500">
                              <div>
                                {t('blackboard.repliesUnavailable', 'Replies are not loaded yet.')}
                              </div>
                              <button
                                type="button"
                                onClick={() => {
                                  void handleLoadReplies(selectedPost.id);
                                }}
                                className="mt-3 rounded-2xl border border-white/8 px-4 py-2 text-sm text-zinc-100 transition hover:border-violet-400/40 hover:bg-violet-500/12"
                              >
                                {t('blackboard.retryReplies', 'Retry loading replies')}
                              </button>
                            </div>
                          )}

                          {selectedRepliesLoaded &&
                            selectedReplies.map((reply) => (
                              <article
                                key={reply.id}
                                className="rounded-3xl border border-white/8 bg-white/[0.03] p-4"
                              >
                                <div className="flex items-start justify-between gap-3">
                                  <div>
                                    <div className="text-sm font-medium text-zinc-100">
                                      {reply.author_id}
                                    </div>
                                    <div className="mt-1 text-xs text-zinc-500">
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
                                      className="rounded-xl border border-white/8 px-3 py-2 text-xs text-zinc-300 transition hover:border-rose-400/30 hover:bg-rose-500/12 hover:text-rose-100 disabled:cursor-not-allowed disabled:opacity-60"
                                    >
                                      {t('blackboard.delete', 'Delete')}
                                    </button>
                                  </Popconfirm>
                                </div>
                                <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-zinc-400">
                                  {reply.content}
                                </p>
                              </article>
                            ))}

                          {selectedRepliesLoaded && selectedReplies.length === 0 && (
                            <div className="rounded-3xl border border-dashed border-white/8 bg-white/[0.02] p-5 text-sm text-zinc-500">
                              {t('blackboard.noReplies', 'No replies yet')}
                            </div>
                          )}
                        </div>
                      </div>

                      <div className="rounded-3xl border border-white/8 bg-white/[0.03] p-4">
                        <h4 className="text-sm font-semibold text-zinc-100">
                          {t('blackboard.reply', 'Reply')}
                        </h4>
                        <textarea
                          value={replyDraft}
                          aria-label={t('blackboard.writeReply', 'Write a reply...')}
                          onChange={(event) => {
                            setReplyDraft(event.target.value);
                          }}
                          placeholder={t('blackboard.writeReply', 'Write a reply...')}
                          rows={4}
                          className="mt-3 w-full rounded-2xl border border-white/8 bg-white/[0.04] px-4 py-3 text-sm leading-6 text-zinc-100 placeholder:text-zinc-500 focus:border-violet-400/60 focus:outline-none"
                        />
                        <div className="mt-3 flex justify-end">
                          <button
                            type="button"
                            onClick={() => {
                              void handleCreateReply();
                            }}
                            disabled={replying || !replyDraft.trim()}
                            className="min-h-11 rounded-2xl bg-violet-500 px-4 text-sm font-medium text-white transition hover:bg-violet-400 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {replying
                              ? t('blackboard.replying', 'Sending…')
                              : t('blackboard.sendReply', 'Send')}
                          </button>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <div className="flex min-h-[360px] items-center justify-center rounded-3xl border border-dashed border-white/8 bg-white/[0.02] text-sm text-zinc-500">
                      {t('blackboard.selectPost', 'Select a post to view details')}
                    </div>
                  )}
                </section>
              </div>
            )}

            {activeTab === 'collaboration' && (
              <div className="dark rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                <div className="mb-4">
                  <div className="text-lg font-semibold text-zinc-100">
                    {t('blackboard.tabs.collaboration', 'Collaboration')}
                  </div>
                  <p className="mt-1 text-sm text-zinc-500">
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
              <div className="dark rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                <MemberPanel tenantId={tenantId} projectId={projectId} workspaceId={workspaceId} />
              </div>
            )}

            {activeTab === 'genes' && (
              <div className="dark rounded-[28px] border border-white/8 bg-[#17181d] p-5">
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
              <div className="rounded-[28px] border border-dashed border-white/8 bg-white/[0.02] p-8 text-center">
                <div className="text-lg font-semibold text-zinc-100">
                  {t('blackboard.filesUnavailableTitle', 'Shared files are not wired here yet')}
                </div>
                <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-zinc-500">
                  {t(
                    'blackboard.filesUnavailableBody',
                    'The central blackboard already combines discussion, goals, and execution. File operations can be added later when a workspace-scoped file endpoint is available.'
                  )}
                </p>
              </div>
            )}

            {activeTab === 'status' && (
              <div className="space-y-6 dark">
                <PresenceBar workspaceId={workspaceId} />

                <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
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
                      className="rounded-3xl border border-white/8 bg-white/[0.03] p-4"
                    >
                      <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">
                        {metric.label}
                      </div>
                      <div className="mt-2 text-2xl font-semibold text-zinc-100">{metric.value}</div>
                    </div>
                  ))}
                </div>

                <div className="rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                  <h3 className="text-lg font-semibold text-zinc-100">
                    {t('blackboard.agentStatusTitle', 'Agent status')}
                  </h3>
                  <div className="mt-4 space-y-3">
                    {agents.map((agent) => (
                      <div
                        key={agent.id}
                        className="flex flex-col gap-3 rounded-3xl border border-white/8 bg-white/[0.03] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
                      >
                        <div className="min-w-0">
                          <div className="flex items-center gap-3">
                            <span
                              className={`h-2.5 w-2.5 rounded-full ${statusBadgeTone(agent.status)}`}
                            />
                            <div className="truncate text-sm font-medium text-zinc-100">
                              {agent.display_name ?? agent.label ?? agent.agent_id}
                            </div>
                          </div>
                          <div className="mt-1 text-xs text-zinc-500">
                            {agent.agent_id}
                            {agent.hex_q !== undefined && agent.hex_r !== undefined && (
                              <>
                                {' '}
                                · q {String(agent.hex_q)} / r {String(agent.hex_r)}
                              </>
                            )}
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-zinc-400">
                          <span className="rounded-full border border-white/8 px-3 py-1.5">
                            {agent.status ?? t('blackboard.unknownStatus', 'unknown')}
                          </span>
                          {agent.theme_color && (
                            <span className="rounded-full border border-white/8 px-3 py-1.5">
                              {agent.theme_color}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}

                    {agents.length === 0 && (
                      <div className="rounded-3xl border border-dashed border-white/8 bg-white/[0.02] p-5 text-sm text-zinc-500">
                        {t('blackboard.noAgents', 'No agents have been bound to this workspace yet.')}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'notes' && (
              <div className="space-y-4">
                {notes.map((note) => (
                  <article
                    key={note.id}
                    className="rounded-[28px] border border-white/8 bg-white/[0.03] p-5"
                  >
                    <div className="flex flex-wrap items-center gap-3">
                      <span className="rounded-full border border-white/8 bg-white/5 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-zinc-400">
                        {t(`blackboard.noteKinds.${note.kind}`, note.kind)}
                      </span>
                    </div>
                    <h3 className="mt-4 text-lg font-semibold text-zinc-100">{note.title}</h3>
                    <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-zinc-400">
                      {note.summary}
                    </p>
                  </article>
                ))}

                {notes.length === 0 && (
                  <div className="rounded-[28px] border border-dashed border-white/8 bg-white/[0.02] p-8 text-center text-sm text-zinc-500">
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
                <div className="rounded-[28px] border border-white/8 bg-white/[0.03] p-5">
                  <div className="text-lg font-semibold text-zinc-100">
                    {t('blackboard.commandCenter', 'Workspace command center')}
                  </div>
                  <p className="mt-2 text-sm leading-7 text-zinc-500">
                    {t(
                      'blackboard.topologyHint',
                      'The live command surface stays on the page canvas. Use this tab for a structured read of current nodes, connections, and placements while the main board remains visible behind the modal.'
                    )}
                  </p>
                </div>

                <div className="grid gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(320px,0.8fr)]">
                  <div className="rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <h3 className="text-lg font-semibold text-zinc-100">
                        {t('blackboard.topologyNodesTitle', 'Nodes')}
                      </h3>
                      <span className="rounded-full bg-white/6 px-3 py-1 text-xs text-zinc-400">
                        {String(topologyNodes.length)}
                      </span>
                    </div>
                    <div className="space-y-3">
                      {topologyNodes.map((node) => (
                        <article
                          key={node.id}
                          className="rounded-3xl border border-white/8 bg-white/[0.03] p-4"
                        >
                          <div className="flex flex-wrap items-center gap-3">
                            <span className="rounded-full border border-white/8 px-3 py-1 text-[11px] uppercase tracking-[0.16em] text-zinc-400">
                              {node.node_type}
                            </span>
                            {node.status && (
                              <span className="rounded-full bg-white/6 px-3 py-1 text-xs text-zinc-400">
                                {node.status}
                              </span>
                            )}
                          </div>
                          <h4 className="mt-3 text-sm font-semibold text-zinc-100">{node.title}</h4>
                          <div className="mt-3 text-xs text-zinc-500">
                            {node.hex_q !== undefined && node.hex_r !== undefined
                              ? `q ${String(node.hex_q)} · r ${String(node.hex_r)}`
                              : t('blackboard.topologyUnplaced', 'No hex placement')}
                          </div>
                        </article>
                      ))}

                      {topologyNodes.length === 0 && (
                        <div className="rounded-3xl border border-dashed border-white/8 bg-white/[0.02] p-5 text-sm text-zinc-500">
                          {t('blackboard.noTopologyNodes', 'No topology nodes yet.')}
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <h3 className="text-lg font-semibold text-zinc-100">
                        {t('blackboard.topologyEdgesTitle', 'Edges')}
                      </h3>
                      <span className="rounded-full bg-white/6 px-3 py-1 text-xs text-zinc-400">
                        {String(topologyEdges.length)}
                      </span>
                    </div>
                    <div className="space-y-3">
                      {topologyEdges.map((edge) => (
                        <article
                          key={edge.id}
                          className="rounded-3xl border border-white/8 bg-white/[0.03] p-4"
                        >
                          <div className="text-[11px] uppercase tracking-[0.16em] text-zinc-500">
                            {t('blackboard.topologyLink', 'Topology link')}
                          </div>
                          <div className="mt-2 text-sm font-medium text-zinc-100">
                            {edge.source_node_id} → {edge.target_node_id}
                          </div>
                        </article>
                      ))}

                      {topologyEdges.length === 0 && (
                        <div className="rounded-3xl border border-dashed border-white/8 bg-white/[0.02] p-5 text-sm text-zinc-500">
                          {t('blackboard.noTopologyEdges', 'No topology edges yet.')}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {activeTab === 'settings' && (
              <div className="dark rounded-[28px] border border-white/8 bg-[#17181d] p-5">
                <WorkspaceSettingsPanel
                  tenantId={tenantId}
                  projectId={projectId}
                  workspaceId={workspaceId}
                />
              </div>
            )}
          </div>
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
