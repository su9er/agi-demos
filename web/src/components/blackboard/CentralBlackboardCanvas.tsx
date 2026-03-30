import type React from 'react';
import { useMemo } from 'react';

import { useTranslation } from 'react-i18next';

import {
  AlertTriangle,
  Bot,
  ChevronRight,
  ClipboardCheck,
  MessageSquareText,
  Users,
} from 'lucide-react';

import { generateGrid, getHexCorners, hexToPixel } from '@/components/workspace/hex/useHexLayout';

import { buildBlackboardStats, buildCanvasActors, buildCanvasLinks } from './blackboardUtils';

import type {
  BlackboardPost,
  TopologyEdge,
  TopologyNode,
  WorkspaceAgent,
  WorkspaceTask,
} from '@/types/workspace';

const GRID_RADIUS = 7;
const GRID_HEX_SIZE = 88;
const BOARD_NODE_SIZE = 122;
const OUTER_NODE_SIZE = 90;

function truncateLabel(label: string, maxLength: number): string {
  return label.length > maxLength ? `${label.slice(0, maxLength - 1)}…` : label;
}

function toPolygonPoints(cx: number, cy: number, size: number): string {
  return getHexCorners(cx, cy, size)
    .map((corner) => `${String(corner.x)},${String(corner.y)}`)
    .join(' ');
}

function getNodePalette(kind: 'blackboard' | 'agent' | 'human'): {
  fill: string;
  stroke: string;
  glow: string;
  text: string;
  muted: string;
} {
  if (kind === 'agent') {
    return {
      fill: '#122a18',
      stroke: '#52d685',
      glow: '#2ec46d',
      text: '#effaf3',
      muted: '#97d7b0',
    };
  }

  if (kind === 'human') {
    return {
      fill: '#312110',
      stroke: '#f2a22b',
      glow: '#d48806',
      text: '#fdf2dd',
      muted: '#f2c97b',
    };
  }

  return {
    fill: '#1c1831',
    stroke: '#a78bfa',
    glow: '#8b5cf6',
    text: '#f5f3ff',
    muted: '#d4c8ff',
  };
}

export interface CentralBlackboardCanvasProps {
  workspaceName: string;
  tasks: WorkspaceTask[];
  posts: BlackboardPost[];
  agents: WorkspaceAgent[];
  topologyNodes: TopologyNode[];
  topologyEdges: TopologyEdge[];
  onOpenBlackboard: () => void;
}

export function CentralBlackboardCanvas({
  workspaceName,
  tasks,
  posts,
  agents,
  topologyNodes,
  topologyEdges,
  onOpenBlackboard,
}: CentralBlackboardCanvasProps) {
  const { t } = useTranslation();

  const stats = useMemo(
    () => buildBlackboardStats(tasks, posts, agents, topologyNodes),
    [agents, posts, tasks, topologyNodes]
  );

  const actors = useMemo(() => buildCanvasActors(agents, topologyNodes), [agents, topologyNodes]);

  const topologyLinks = useMemo(
    () => buildCanvasLinks(actors, topologyEdges),
    [actors, topologyEdges]
  );

  const gridCells = useMemo(() => generateGrid(GRID_RADIUS), []);

  const pixelActors = useMemo(
    () =>
      actors.map((actor) => ({
        ...actor,
        ...hexToPixel(actor.q, actor.r, GRID_HEX_SIZE),
      })),
    [actors]
  );

  const pixelLinks = useMemo(
    () =>
      topologyLinks.map((link) => ({
        ...link,
        fromPixel: hexToPixel(link.from.q, link.from.r, GRID_HEX_SIZE),
        toPixel: hexToPixel(link.to.q, link.to.r, GRID_HEX_SIZE),
      })),
    [topologyLinks]
  );

  const pixelGrid = useMemo(
    () =>
      gridCells.map((cell) => ({
        ...cell,
        ...hexToPixel(cell.q, cell.r, GRID_HEX_SIZE),
      })),
    [gridCells]
  );

  const viewBox = useMemo(() => {
    const allPoints = [
      ...pixelGrid.map((cell) => ({ x: cell.x, y: cell.y })),
      ...pixelActors.map((actor) => ({ x: actor.x, y: actor.y })),
      { x: 0, y: 0 },
    ];

    const xs = allPoints.map((point) => point.x);
    const ys = allPoints.map((point) => point.y);
    const minX = Math.min(...xs) - 240;
    const maxX = Math.max(...xs) + 240;
    const minY = Math.min(...ys) - 220;
    const maxY = Math.max(...ys) + 220;

    return `${String(minX)} ${String(minY)} ${String(maxX - minX)} ${String(maxY - minY)}`;
  }, [pixelActors, pixelGrid]);

  const statCards = [
    {
      key: 'tasks',
      label: t('blackboard.metrics.tasks', 'Tasks'),
      value: `${String(stats.completedTasks)}/${String(stats.totalTasks || 0)}`,
      helper: t('blackboard.metrics.completed', 'completed'),
      icon: ClipboardCheck,
    },
    {
      key: 'discussions',
      label: t('blackboard.metrics.discussions', 'Discussions'),
      value: String(stats.discussions),
      helper: t('blackboard.metrics.openThreads', {
        count: stats.openPosts,
        defaultValue: '{{count}} open',
      }),
      icon: MessageSquareText,
    },
    {
      key: 'agents',
      label: t('blackboard.metrics.agents', 'Agents'),
      value: String(stats.activeAgents),
      helper: t('blackboard.metrics.activeAgents', 'active now'),
      icon: Bot,
    },
    {
      key: 'humans',
      label: t('blackboard.metrics.humans', 'Human seats'),
      value: String(stats.humanSeats),
      helper: t('blackboard.metrics.coordinationSeats', 'coordination seats'),
      icon: Users,
    },
    {
      key: 'blocked',
      label: t('blackboard.metrics.blocked', 'Blocked'),
      value: String(stats.blockedTasks),
      helper: t('blackboard.metrics.needsAttention', 'needs attention'),
      icon: AlertTriangle,
    },
  ];

  const boardPalette = getNodePalette('blackboard');
  const boardPolygon = toPolygonPoints(0, 0, BOARD_NODE_SIZE);

  return (
    <div className="relative min-h-[620px] overflow-hidden rounded-[28px] border border-cyan-950/70 bg-[#070b10]">
      <div className="pointer-events-none absolute inset-x-0 top-0 z-20 flex flex-col gap-4 p-4 sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="pointer-events-auto max-w-2xl rounded-3xl border border-white/8 bg-black/30 px-5 py-4 backdrop-blur">
            <div className="text-[11px] uppercase tracking-[0.32em] text-zinc-500">
              {t('blackboard.commandCenter', 'Workspace command center')}
            </div>
            <h2 className="mt-2 text-2xl font-semibold text-zinc-100">{workspaceName}</h2>
            <p className="mt-2 max-w-xl text-sm leading-6 text-zinc-400">
              {t(
                'blackboard.canvasHint',
                'Use the central blackboard to review execution, align the team, and jump into shared tasks and discussions.'
              )}
            </p>
          </div>

          <button
            type="button"
            onClick={onOpenBlackboard}
            className="pointer-events-auto inline-flex items-center justify-center gap-2 self-start rounded-full border border-violet-400/30 bg-violet-500/12 px-4 py-2 text-sm font-medium text-violet-100 transition hover:border-violet-300/50 hover:bg-violet-500/18 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-violet-300/80"
          >
            {t('blackboard.openBoard', 'Open central blackboard')}
            <ChevronRight size={16} />
          </button>
        </div>

        <div className="pointer-events-auto grid gap-2 sm:grid-cols-2 xl:grid-cols-5">
          {statCards.map((card) => {
            const Icon = card.icon;

            return (
              <div
                key={card.key}
                className="rounded-2xl border border-white/8 bg-black/28 px-4 py-3 backdrop-blur"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-[11px] uppercase tracking-[0.18em] text-zinc-500">
                      {card.label}
                    </div>
                    <div className="mt-1 text-lg font-semibold text-zinc-100">{card.value}</div>
                  </div>
                  <span className="rounded-full border border-white/8 bg-white/5 p-2 text-zinc-300">
                    <Icon size={16} />
                  </span>
                </div>
                <div className="mt-2 text-xs text-zinc-500">{card.helper}</div>
              </div>
            );
          })}
        </div>
      </div>

      <div className="absolute inset-x-0 bottom-0 z-20 flex justify-end p-4 sm:p-6">
        <div className="max-w-xs rounded-2xl border border-white/8 bg-black/34 px-4 py-3 text-xs leading-6 text-zinc-400 backdrop-blur">
          <div className="font-medium uppercase tracking-[0.18em] text-zinc-500">
            {t('blackboard.quickActions', 'Quick read')}
          </div>
          <div className="mt-2">
            {t(
              'blackboard.quickActionsHint',
              'The center tracks completion, discussions, and agent activity. Open it to edit tasks, reply to posts, and inspect topology.'
            )}
          </div>
        </div>
      </div>

      <svg
        className="h-full w-full"
        role="img"
        aria-label={t('blackboard.title', 'Blackboard')}
        viewBox={viewBox}
      >
        <defs>
          <filter id="board-node-glow" x="-200%" y="-200%" width="400%" height="400%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="18" result="blurred" />
            <feMerge>
              <feMergeNode in="blurred" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        </defs>

        <rect x="-2000" y="-2000" width="4000" height="4000" fill="#070b10" />

        {pixelGrid.map((cell) => (
          <polygon
            key={`grid-${String(cell.q)}-${String(cell.r)}`}
            points={toPolygonPoints(cell.x, cell.y, GRID_HEX_SIZE)}
            fill="transparent"
            stroke="#14354d"
            strokeOpacity={0.55}
            strokeWidth={1.4}
          />
        ))}

        {pixelActors.map((actor) => (
          <line
            key={`central-link-${actor.key}`}
            x1={0}
            y1={0}
            x2={actor.x}
            y2={actor.y}
            stroke="#a78bfa"
            strokeOpacity={0.22}
            strokeWidth={8}
            strokeLinecap="round"
          />
        ))}

        {pixelLinks.map((link) => (
          <line
            key={link.id}
            x1={link.fromPixel.x}
            y1={link.fromPixel.y}
            x2={link.toPixel.x}
            y2={link.toPixel.y}
            stroke="#3a4e6e"
            strokeOpacity={0.62}
            strokeWidth={4}
            strokeLinecap="round"
          />
        ))}

        <g
          role="button"
          tabIndex={0}
          aria-label={t('blackboard.openBoard', 'Open central blackboard')}
          onClick={onOpenBlackboard}
          onKeyDown={(event: React.KeyboardEvent<SVGGElement>) => {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              onOpenBlackboard();
            }
          }}
          style={{ cursor: 'pointer' }}
        >
          <polygon
            points={boardPolygon}
            fill={boardPalette.glow}
            fillOpacity={0.14}
            filter="url(#board-node-glow)"
          />
          <polygon
            points={boardPolygon}
            fill={boardPalette.fill}
            stroke={boardPalette.stroke}
            strokeWidth={7}
          />
          <polygon
            points={toPolygonPoints(0, 0, BOARD_NODE_SIZE - 10)}
            fill="transparent"
            stroke="#6d5ad7"
            strokeWidth={2}
            strokeOpacity={0.82}
          />

          <text
            x={0}
            y={-18}
            textAnchor="middle"
            fontSize={32}
            fontWeight={600}
            fill={boardPalette.text}
          >
            {t('blackboard.title', 'Blackboard')}
          </text>
          <text
            x={0}
            y={28}
            textAnchor="middle"
            fontSize={22}
            fontWeight={500}
            fill={boardPalette.muted}
          >
            {t('blackboard.completionSummary', {
              done: stats.completedTasks,
              total: stats.totalTasks,
              defaultValue: '{{done}} / {{total}} tasks complete',
            })}
          </text>
          <text x={0} y={66} textAnchor="middle" fontSize={18} fill="#8f85bf">
            {t('blackboard.boardSummaryLine', {
              posts: stats.discussions,
              pinned: stats.pinnedPosts,
              defaultValue: '{{posts}} discussions · {{pinned}} pinned',
            })}
          </text>
        </g>

        {pixelActors.map((actor) => {
          const palette = getNodePalette(actor.kind);
          const polygon = toPolygonPoints(actor.x, actor.y, OUTER_NODE_SIZE);
          const topTextX = actor.x - OUTER_NODE_SIZE * 0.42;
          const topTextY = actor.y - OUTER_NODE_SIZE * 0.52;

          return (
            <g key={actor.key}>
              <polygon
                points={polygon}
                fill={palette.glow}
                fillOpacity={0.08}
                filter="url(#board-node-glow)"
              />
              <polygon
                points={polygon}
                fill={palette.fill}
                stroke={palette.stroke}
                strokeWidth={6}
              />
              <polygon
                points={toPolygonPoints(actor.x, actor.y, OUTER_NODE_SIZE - 8)}
                fill="transparent"
                stroke={palette.stroke}
                strokeOpacity={0.86}
                strokeWidth={1.8}
              />

              <text
                x={topTextX}
                y={topTextY}
                transform={`rotate(-26 ${String(topTextX)} ${String(topTextY)})`}
                textAnchor="start"
                fontSize={16}
                fontWeight={500}
                fill={palette.muted}
              >
                {actor.statusLabel}
              </text>

              <text
                x={actor.x}
                y={actor.y + 8}
                textAnchor="middle"
                fontSize={28}
                fontWeight={500}
                fill={palette.text}
              >
                {truncateLabel(actor.title, 10)}
              </text>
            </g>
          );
        })}
      </svg>
    </div>
  );
}
