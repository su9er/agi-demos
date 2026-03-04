# SubAgent UI/UX Improvement Plan

**Status**: DRAFT
**Author**: Sisyphus Orchestrator
**Date**: 2026-03-04
**Prerequisite**: SUBAGENT_ENHANCEMENT_PLAN.md (complete, 199 tests passing)
**Tech Stack**: React 19.2 + TypeScript 5.9 + Ant Design 6.1 + Zustand 5.0 + Tailwind CSS

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Methodology](#methodology)
3. [E2E Observed Issues](#e2e-observed-issues)
4. [Current Architecture Map](#current-architecture-map)
5. [Industry Research Findings](#industry-research-findings)
6. [Improvement Plan: Tier 1 (Quick Wins)](#tier-1-quick-wins)
7. [Improvement Plan: Tier 2 (Medium-Term)](#tier-2-medium-term)
8. [Improvement Plan: Tier 3 (Long-Term)](#tier-3-long-term)
9. [Implementation Dependencies](#implementation-dependencies)
10. [Risk Assessment](#risk-assessment)

---

## Executive Summary

This plan proposes 15 targeted UI/UX improvements to the SubAgent chat timeline experience, organized in 3 priority tiers. The improvements are informed by:

- **10 UX issues** observed during E2E testing of the SubAgent enhancement project
- **13+ component files** analyzed for current architecture and patterns
- **6 industry references** (ChatGPT Deep Research, AgentPrism, VoltAgent, Inngest, CrewAI, MCP Agentic)
- **Full rendering pipeline trace** (SSE -> store -> grouping -> component)

The plan requires **zero new dependencies** -- all improvements use existing Tailwind CSS, Ant Design 6, and Zustand patterns already in the codebase.

**Estimated total effort**: ~8-12 engineering days across all tiers.

---

## Methodology

### Data Sources

| Source | What We Collected |
|--------|-------------------|
| E2E Screenshots | 4 screenshots from SubAgent test runs, analyzed for 10 specific UX issues |
| Component Analysis | 13 frontend files read in full (SubAgentTimeline, SubAgentDetailPanel, BackgroundSubAgentPanel, groupTimelineEvents, streamEventHandlers, agentV3, SubAgentCard, SubAgentModal, etc.) |
| Rendering Pipeline Trace | Full SSE-to-visual map: sseEventAdapter -> streamEventHandlers -> agentV3 store -> groupTimelineEvents -> MessageArea -> SubAgentTimeline |
| Industry Research | 4 web searches + 2 Exa code searches covering 2024-2025 agent UI patterns |
| Ant Design Patterns | Context7 documentation queries for Timeline, Steps, Collapse, Progress, Badge/Tag, Segmented components |

### Design Principles

1. **Progressive Disclosure**: Show summary by default, details on demand (aligned with ChatGPT Deep Research pattern)
2. **Visual Hierarchy**: SubAgent execution must be visually distinct from main agent reasoning
3. **Status at a Glance**: Any status should be comprehensible in < 1 second
4. **Reuse Existing Patterns**: Match ThinkingBlock, AgentProgressBar, StreamingToolPreparation conventions already in the codebase
5. **No New Dependencies**: All animation via existing Tailwind/CSS keyframes in index.css

---

## E2E Observed Issues

| # | Issue | Severity | Screenshot Evidence |
|---|-------|----------|---------------------|
| 1 | SubAgent name sometimes empty -- card shows "SubAgent:" with no name | High | subagent-card-with-status.png |
| 2 | Weak visual hierarchy -- SubAgent cards nearly identical to reasoning blocks | High | subagent-ui-rendering.png |
| 3 | Status indicators hard to read -- small icons far to the right, technical text like "Session spawned" | Medium | subagent-card-view.png |
| 4 | "View details" not discoverable -- only a small info icon serves as trigger | Medium | subagent-card-view.png |
| 5 | No progress indication -- running SubAgents show only "Executing..." with no progress | Medium | subagent-ui-complete.png |
| 6 | Error states use technical jargon -- "Cancelled by steer restart" is not user-friendly | Medium | subagent-card-with-status.png |
| 7 | SubAgent output indistinguishable from main agent output | Medium | subagent-ui-complete.png |
| 8 | Name mismatch -- user requested "researcher" but card showed "architect" | High | subagent-card-with-status.png (backend event routing issue) |
| 9 | Tight internal padding -- cramped card layout | Low | subagent-card-view.png |
| 10 | Low contrast -- running SubAgent background barely differs from reasoning block background | Medium | subagent-ui-rendering.png |

---

## Current Architecture Map

### Rendering Pipeline (SSE to Visual)

```
WebSocket message
  |
  v
agentService.ts: routeSubagentLifecycleMessage() / routeToHandler()
  |
  v
sseEventAdapter.ts: parseAndConvertEvent() -> sseEventToTimeline()
  |  Maps: subagent_routed, subagent_started, subagent_completed,
  |         subagent_failed, parallel_*, chain_*, background_launched
  v
streamEventHandlers.ts: onSubAgentRouted(), onSubAgentStarted(), etc.
  |  Each handler: appendSSEEventToTimeline() -> updateConversationState()
  |  Some also update useBackgroundStore (launch/complete/fail)
  v
agentV3.ts (Zustand): conversationStates Map -> global timeline[]
  |  updateConversationState() mirrors active conversation to top-level fields
  |  Re-render triggers: set({ timeline, messages, agentState, ... })
  v
MessageArea.tsx: receives timeline prop
  |  useMemo: groupTimelineEvents(timeline) -> GroupedItem[]
  v
groupTimelineEvents.ts: buildSubAgentGroup()
  |  Collects consecutive SUBAGENT_EVENT_TYPES into SubAgentGroup
  |  Terminates on: completed, failed, killed, depth_limited, parallel_completed, chain_completed
  v
SubAgentTimeline.tsx: <SubAgentTimeline group={SubAgentGroup} isStreaming={bool} />
  |  Maps group.status -> icon, color, CSS class
  |  Renders: header, badges, task, reason, summary, error, ParallelDetail, ChainDetail
  v
Visual Output (chat message list)
```

### Key Files to Modify

| File | Size | Role | Modification Scope |
|------|------|------|--------------------|
| `SubAgentTimeline.tsx` | 438 lines | Main visual component | HIGH -- most visual changes here |
| `groupTimelineEvents.ts` | ~300 lines | Event grouping logic | LOW -- grouping rules are solid |
| `streamEventHandlers.ts` | ~1500 lines | SSE -> store | LOW -- only if adding new event data |
| `sseEventAdapter.ts` | ~400 lines | Event parsing | LOW -- only if adding new fields |
| `SubAgentDetailPanel.tsx` | ~250 lines | Detail view | MEDIUM -- needs redesign |
| `BackgroundSubAgentPanel.tsx` | ~300 lines | Background drawer | MEDIUM -- improve status display |
| `index.css` | ~500 lines | Animations/tokens | LOW -- add 2-3 new keyframes |

### Existing Design Tokens

```
Primary: #1e3fae          Animations: 200-300ms interactions, 2s loading
Success: #10b981          Easing: ease-out, ease-in-out, cubic-bezier(0.4, 0, 0.6, 1)
Warning: #f59e0b          Existing keyframes: fade-in, slide-up, scale-in, pulse-slow,
Error:   #ef4444                              shimmer, glow-pulse, typing-dot, bounce-subtle
Info:    #3b82f6
```

### SubAgentGroup Data Shape

```typescript
interface SubAgentGroup {
  kind: 'subagent';
  subagentId: string;
  subagentName: string;                    // Can be empty (Issue #1)
  status: 'running' | 'success' | 'error' | 'background'
        | 'queued' | 'killed' | 'steered' | 'depth_limited';
  events: TimelineEvent[];
  startIndex: number;
  confidence?: number;                     // 0.0-1.0
  reason?: string;                         // Routing reason
  task?: string;                           // Task description
  summary?: string;                        // Completion summary
  error?: string;                          // Error message
  tokensUsed?: number;
  executionTimeMs?: number;
  mode?: 'single' | 'parallel' | 'chain';
  parallelInfo?: { taskCount; subtasks; results?; totalTimeMs? };
  chainInfo?: { stepCount; chainName; steps[]; totalTimeMs? };
}
```

---

## Industry Research Findings

### Pattern 1: Progressive Disclosure (ChatGPT Deep Research)

OpenAI's Deep Research (2025) uses a **fullscreen report view** with:
- Left-side table of contents for long outputs
- Editable plan before execution starts
- Ability to **steer mid-run** (redirect the agent)
- Real-time progress tracking with step indicators

**Applicable to MemStack**: The "collapsed summary / expanded detail" pattern already exists but needs stronger visual differentiation and a progress indicator.

### Pattern 2: Agent Trace Visualization (AgentPrism / VoltAgent)

Evil Martians' AgentPrism and VoltAgent both use:
- **Node-based visualization** showing agents as connected nodes
- Real-time execution path highlighting
- OpenTelemetry-compatible trace format

**Applicable to MemStack**: Long-term, consider a DAG view for parallel/chain SubAgent executions. Short-term, improve the linear timeline with better status transitions.

### Pattern 3: Streaming Durable Workflows (Inngest useAgent)

Inngest's `useAgent` hook provides:
- One-line React hook for streaming multi-step agent output
- Real-time progress updates per step
- Automatic retry and resumption

**Applicable to MemStack**: Our SSE pipeline already provides this. The gap is in the **visual rendering** of these streaming updates, not the data transport.

### Pattern 4: Structured Agent UI Components (A2UI Protocol, MCP Agentic)

Microsoft's MCP Agentic capabilities and the A2UI Protocol propose:
- Rendering agent outputs as **native UI components** (not just markdown)
- Progress update notifications as first-class protocol features
- Resumability and multi-turn progress

**Applicable to MemStack**: SubAgent outputs should be framed as distinct UI blocks, not rendered identically to markdown chat messages.

### Pattern 5: Ant Design Component Composition

Based on Context7 research of Ant Design 6:
- **Timeline** with custom dots and color-per-status for step-by-step execution
- **Steps** component (vertical, `size="small"`) for phase display (queued -> routing -> executing -> completed)
- **Collapse** inside **Card** for progressive disclosure
- **Progress** with `status="active"` for indeterminate "running" animation
- **Badge/Tag** with pulse animation for live status
- **Segmented** for parallel agent view switching

---

## Tier 1: Quick Wins

**Effort**: 1-2 days total | **Impact**: High | **Risk**: Low

These are CSS/display-logic-only changes with no store or event modifications.

---

### 1.1 Fix Empty SubAgent Name Fallback

**Issue**: #1 -- Card shows "SubAgent:" with no name
**Root Cause**: `subagentName` field is empty/undefined in some `subagent_routed` events

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Add fallback: `group.subagentName \|\| group.subagentId?.slice(0, 8) \|\| t('agent.subagent.unnamed')` |

**Visual Spec**: When name is missing, show truncated ID in monospace with a "?" icon prefix:
```
[?] SubAgent abc12def    [Running]
```

**Complexity**: Low (1 line change + i18n key)

---

### 1.2 Increase Visual Hierarchy -- Distinct SubAgent Card Styling

**Issue**: #2, #10 -- SubAgent cards look like reasoning blocks
**Inspiration**: ChatGPT Deep Research uses distinct card frames for sub-task execution

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Replace current bg classes with distinct styling per status |
| `index.css` | Add `subagent-card-running` keyframe (subtle left-border pulse) |

**Visual Spec**:

Status-based card styles (all have 3px left border + slightly elevated shadow):

| Status | Left Border | Background | Shadow |
|--------|------------|------------|--------|
| running | `border-l-blue-500` + pulse | `bg-blue-50/80 dark:bg-blue-950/30` | `shadow-sm shadow-blue-100` |
| success | `border-l-emerald-500` | `bg-emerald-50/60 dark:bg-emerald-950/20` | `shadow-sm` |
| error | `border-l-red-500` | `bg-red-50/60 dark:bg-red-950/20` | `shadow-sm shadow-red-100` |
| background | `border-l-purple-500` | `bg-purple-50/60 dark:bg-purple-950/20` | `shadow-sm` |
| queued | `border-l-gray-400` | `bg-gray-50/60 dark:bg-gray-800/30` | none |
| killed/steered | `border-l-amber-500` | `bg-amber-50/60 dark:bg-amber-950/20` | none |

Key visual differentiator from ThinkingBlock: ThinkingBlock has no left border and uses `bg-gray-50`. SubAgent cards use a **colored left border** as their signature element.

**Complexity**: Low (CSS class changes in one component)

---

### 1.3 Improve Status Readability

**Issue**: #3 -- Status indicators are small icons far to the right with technical text
**Inspiration**: Ant Design Badge/Tag with color-coded inline status

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Replace icon-only status with Tag-like inline pill next to agent name |

**Visual Spec**: Status rendered as colored pill immediately after agent name:

```
[Bot] Code Reviewer  [● Running]     0.85  12.3s
[Bot] Code Reviewer  [✓ Completed]   0.92  45.1s  1,240 tokens
[Bot] Code Reviewer  [✕ Failed]      ---   12.0s
```

Pill colors match left border (blue/green/red/purple/gray/amber). "Running" pill uses `animate-pulse` on the dot.

**Humanized status labels** (replace technical strings):

| Status | Current | Proposed (en) | Proposed (zh) |
|--------|---------|---------------|---------------|
| running | "Executing..." | "Running" | "Running" |
| success | "Completed" | "Completed" | "Done" |
| error | varies (technical) | "Failed" | "Failed" |
| background | "Session spawned" | "Background" | "Background" |
| queued | "Queued" | "Waiting" | "Waiting" |
| killed | "Killed" | "Stopped" | "Stopped" |
| steered | "Steered" | "Redirected" | "Redirected" |
| depth_limited | "Depth limited" | "Depth limit" | "Depth limit" |

**Complexity**: Low (JSX restructure + i18n additions)

---

### 1.4 Increase Card Internal Padding

**Issue**: #9 -- Cramped card layout

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Increase padding from `p-2`/`p-3` to `p-3`/`p-4`, add `gap-2` between sections |

**Complexity**: Low (padding class changes)

---

### 1.5 Humanize Error Messages

**Issue**: #6 -- Technical error messages ("Cancelled by steer restart")

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Add error message mapping function |

**Error Message Map**:

| Technical | User-Friendly (en) | User-Friendly (zh) |
|-----------|---------------------|---------------------|
| "Cancelled by steer restart" | "Stopped: agent was redirected to a new task" | "Stopped: redirected to new task" |
| "Max depth exceeded" | "Stopped: delegation depth limit reached" | "Stopped: depth limit reached" |
| "Killed by user" | "Stopped by user" | "Stopped by user" |
| "Timeout" | "Stopped: execution timed out" | "Stopped: timed out" |
| (other) | Show original + "An error occurred during execution" prefix | "Error during execution" prefix |

**Complexity**: Low (mapping function + i18n)

---

## Tier 2: Medium-Term

**Effort**: 3-5 days total | **Impact**: High | **Risk**: Medium

These involve component restructuring and potentially new sub-components, but no store/event changes.

---

### 2.1 Add Progress Indication for Running SubAgents

**Issue**: #5 -- No progress during execution
**Inspiration**: ChatGPT Deep Research real-time progress, Ant Design Steps component

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Add inline phase indicator for running SubAgents |
| `index.css` | Add shimmer animation for progress bar |

**Visual Spec**: When `status === 'running'`, show a mini phase bar below the header:

```
[Bot] Researcher  [● Running]

  Routed → Started → Executing...
  ━━━━━━━━━━━━━━━━━░░░░░░░░░░░░   (shimmer animation on unfilled portion)
```

Phase progression is derived from `group.events[]` -- count which lifecycle events have been received:
- `subagent_routed` received -> Phase 1/3 (Routed)
- `subagent_started` received -> Phase 2/3 (Started)
- `subagent_session_update` received -> Phase 2/3 still (Executing)
- Terminal event -> 3/3 (Done)

For parallel mode, show `n/total subtasks completed` instead:
```
  Parallel: 2/4 subtasks completed
  ━━━━━━━━━━━━━━━━━░░░░░░░░░░░░
```

**Complexity**: Medium (new sub-component, event counting logic)

---

### 2.2 Make "View Details" Discoverable

**Issue**: #4 -- Only a tiny info icon triggers detail view
**Inspiration**: Ant Design Collapse with explicit header text

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Replace info icon with text button "Show details" / "Hide details" |
| `SubAgentDetailPanel.tsx` | Render inline (not in a separate panel) when expanded |

**Visual Spec**: Add a "Show details >" link below the summary section:

```
[Bot] Researcher  [✓ Completed]  0.92  45.1s  1,240 tokens

  Task: Research authentication patterns
  Summary: Found 3 auth middleware implementations...

  [Show details >]             <- clickable text link, not icon
```

When expanded, show the detail panel **inline** within the card (not as a separate drawer/modal):

```
  [Hide details ^]

  ┌─ Execution Details ─────────────────────────────┐
  │ Started:   14:23:05                              │
  │ Duration:  45.1s                                 │
  │ Tokens:    1,240 (prompt: 890, completion: 350)  │
  │ Model:     gemini-pro                            │
  │ Confidence: 0.92                                 │
  │                                                  │
  │ Timeline:                                        │
  │ ● 14:23:05  Routed (confidence: 0.92)           │
  │ ● 14:23:06  Started                             │
  │ ● 14:23:51  Completed                           │
  └──────────────────────────────────────────────────┘
```

**Complexity**: Medium (restructure detail panel as inline component, add expand/collapse state)

---

### 2.3 Distinct SubAgent Output Framing

**Issue**: #7 -- SubAgent-generated content looks identical to main agent output
**Inspiration**: A2UI Protocol -- render agent outputs as native UI blocks

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Wrap summary/output in a styled quote block |

**Visual Spec**: SubAgent output rendered inside a subtle quote frame:

```
[Bot] Researcher  [✓ Completed]

  ┃ Found 3 authentication middleware implementations in the codebase.
  ┃ The primary pattern uses JWT with httpOnly cookies stored in Redis.
  ┃ Recommended approach: follow the existing AuthMiddleware in
  ┃ src/infrastructure/security/auth_middleware.py.
```

Implementation: A left-border `border-l-2 border-gray-300 pl-3 ml-1` on the summary text with slightly different text color (`text-gray-700 dark:text-gray-300`).

**Complexity**: Low (CSS wrapper around existing summary render)

---

### 2.4 Parallel Execution Visualization Upgrade

**Issue**: Parallel SubAgents lack clear structure
**Inspiration**: VoltAgent flowchart nodes, Ant Design Segmented for view switching

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` (ParallelDetail) | Redesign parallel detail with mini-cards per subtask |

**Visual Spec**: Replace current list with horizontal mini-cards:

```
[Bot] Orchestrator  [● Running]  Parallel: 3 tasks

  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
  │ Researcher   │  │ Code Review  │  │ Security     │
  │ [✓ Done]     │  │ [● Running]  │  │ [○ Waiting]  │
  │ 12.3s        │  │ 5.2s...      │  │ ---          │
  └──────────────┘  └──────────────┘  └──────────────┘
```

For > 4 parallel subtasks, use a 2-column grid. Each mini-card is clickable to expand its detail.

**Complexity**: Medium (new ParallelSubtaskCard sub-component)

---

### 2.5 Chain Execution Step Indicator

**Issue**: Chain mode steps lack sequential visualization
**Inspiration**: Ant Design Steps (vertical, size="small")

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` (ChainDetail) | Redesign with vertical step indicator |

**Visual Spec**:

```
[Bot] Pipeline  [● Running]  Chain: "Research -> Implement -> Review"

  ✓ Step 1: Research     (12.3s, 890 tokens)
  ● Step 2: Implement    (running...)
  ○ Step 3: Review       (pending)
```

Use Ant Design's `<Steps direction="vertical" size="small" current={currentStep}>` with custom icons matching our status colors.

**Complexity**: Medium (integrate Ant Design Steps, map chain steps to Steps items)

---

### 2.6 Animated Status Transitions

**Issue**: Status changes happen instantly with no visual transition
**Inspiration**: Framer Motion-like transitions (but CSS-only per our constraint)

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Add CSS transition classes for status changes |
| `index.css` | Add `subagent-status-transition` keyframe |

**Visual Spec**: When status changes (e.g., running -> completed):
1. Left border color transitions over 300ms (`transition-colors duration-300`)
2. Background color transitions over 300ms
3. Status pill does a subtle `scale-in` animation (existing keyframe)
4. Summary text fades in via `animate-fade-in` (existing keyframe)

**Complexity**: Low-Medium (CSS transitions, may need status tracking for "just changed" state)

---

## Tier 3: Long-Term

**Effort**: 4-6 days total | **Impact**: Medium-High | **Risk**: Medium-High

These require store changes, new components, or significant architectural additions.

---

### 3.1 Execution Timeline Mini-Map

**Inspiration**: ChatGPT Deep Research left-side TOC, AgentPrism trace visualization

**Description**: For conversations with 3+ SubAgent executions, show a floating mini-map on the right side of the chat that summarizes all SubAgent activity:

```
  ┌─ Agent Activity ──┐
  │ ✓ Researcher  12s │
  │ ✓ Coder       45s │
  │ ● Reviewer    ...  │  <- currently running, highlighted
  │ ○ Deployer    ---  │
  └────────────────────┘
```

Clicking an entry scrolls to that SubAgent card in the chat.

**Changes**:
| File | Change |
|------|--------|
| New: `SubAgentMiniMap.tsx` | Floating sidebar component |
| `AgentChatContent.tsx` | Mount mini-map when SubAgent count >= 3 |
| `groupTimelineEvents.ts` | Export a `getSubAgentSummaries()` helper |

**Complexity**: High (new component, scroll-to integration, responsive positioning)

---

### 3.2 Real-Time Streaming Content Preview

**Inspiration**: ChatGPT streaming output, Inngest useAgent real-time hook

**Description**: When a SubAgent is running, show a live preview of its streaming output inside the SubAgent card (truncated to last 3 lines).

```
[Bot] Researcher  [● Running]

  Routed → Started → Executing...
  ━━━━━━━━━━━━━━━━━░░░░░░░░░░░░

  ┃ ...analyzing the authentication middleware...
  ┃ Found jwt_decode() called in 3 locations...
  ┃ Checking token refresh logic in auth_service.py_
                                                    ^ blinking cursor
```

**Changes**:
| File | Change |
|------|--------|
| `streamEventHandlers.ts` | Forward `subagent_session_update` content to a per-subagent preview buffer |
| `agentV3.ts` | Add `subagentPreviews: Map<string, string>` to ConversationState |
| `SubAgentTimeline.tsx` | Subscribe to preview for current subagentId |
| `groupTimelineEvents.ts` | Pass-through session update content |

**Complexity**: High (new store field, streaming buffer management, truncation logic)

---

### 3.3 Controllable Execution (Pause/Cancel/Steer)

**Inspiration**: ChatGPT Deep Research mid-run steering, MCP Agentic resumability

**Description**: Add inline action buttons on running SubAgent cards:

```
[Bot] Researcher  [● Running]  [Pause] [Stop] [Redirect...]
```

- **Pause**: Send `subagent_pause` command (requires backend support)
- **Stop**: Send `subagent_kill` command (already supported via `kill_run` API)
- **Redirect**: Open a mini-input to type new instructions (sends `steer` command)

**Changes**:
| File | Change |
|------|--------|
| `SubAgentTimeline.tsx` | Add action button row for running status |
| New: `SubAgentActions.tsx` | Action buttons component with confirmation dialogs |
| `agentService.ts` | Add `killSubAgent()` and `steerSubAgent()` API methods |
| Backend changes needed | `steer` endpoint, `pause` support |

**Complexity**: High (new component, API integration, backend coordination)

---

### 3.4 DAG Visualization for Complex Orchestrations

**Inspiration**: AgentPrism node graph, VoltAgent interactive flowcharts, LangGraph Studio

**Description**: For parallel + chain mixed orchestrations, offer an optional DAG (directed acyclic graph) view that shows the execution topology:

```
  [Planner] ──┬── [Researcher A] ──┐
              │                     ├── [Synthesizer] ── [Reviewer]
              └── [Researcher B] ──┘
```

**Changes**:
| File | Change |
|------|--------|
| New: `SubAgentDAGView.tsx` | Canvas-based DAG renderer |
| New: `dagLayout.ts` | Layout algorithm (Sugiyama or simple left-to-right) |
| `SubAgentTimeline.tsx` | Add "View as graph" toggle for multi-agent groups |

This is a **separate view mode**, not a replacement for the timeline. Toggle via a small button in the SubAgent card header.

**Complexity**: Very High (graph layout algorithm, canvas/SVG rendering, interactive nodes)
**Recommendation**: Consider using a lightweight library like `elkjs` for layout if the constraint on no new dependencies is relaxed.

---

### 3.5 Execution Cost Dashboard

**Inspiration**: AgentPrism metrics panel, VoltAgent observability

**Description**: Aggregate token usage and execution time across all SubAgents in a conversation and show a collapsible cost summary:

```
  ┌─ Execution Summary ─────────────────────────────┐
  │ Total SubAgents: 4  (3 completed, 1 running)     │
  │ Total Tokens:    5,240  (prompt: 3,800, comp: 1,440)  │
  │ Total Time:      2m 15s                           │
  │ Estimated Cost:  $0.0082                          │
  └───────────────────────────────────────────────────┘
```

**Changes**:
| File | Change |
|------|--------|
| New: `SubAgentCostSummary.tsx` | Aggregation display component |
| `AgentChatContent.tsx` | Mount below chat when SubAgents are present |
| `groupTimelineEvents.ts` | Export `aggregateSubAgentMetrics()` utility |

**Complexity**: Medium (aggregation logic + new display component)

---

## Implementation Dependencies

```
Tier 1 (no dependencies -- can parallelize all):
  1.1 Fix name fallback
  1.2 Visual hierarchy styling
  1.3 Status readability
  1.4 Padding increase
  1.5 Error message humanization

Tier 2 (mostly independent, some internal deps):
  2.1 Progress indication
  2.2 View details discoverable
  2.3 Output framing           <- depends on 1.2 (styling foundation)
  2.4 Parallel viz upgrade     <- depends on 1.2, 1.3 (styling + status)
  2.5 Chain step indicator     <- depends on 1.2, 1.3 (styling + status)
  2.6 Animated transitions     <- depends on 1.2 (new CSS classes to transition)

Tier 3 (sequential dependencies):
  3.1 Mini-map                 <- depends on Tier 1 complete
  3.2 Streaming preview        <- depends on 2.1 (progress), store changes
  3.3 Controllable execution   <- depends on 2.2 (detail panel), backend APIs
  3.4 DAG visualization        <- depends on 2.4 (parallel viz data)
  3.5 Cost dashboard           <- independent (can start after Tier 1)
```

### Recommended Implementation Order

```
Sprint 1 (Days 1-2):  1.1, 1.2, 1.3, 1.4, 1.5  (all Tier 1, parallel)
Sprint 2 (Days 3-5):  2.1, 2.2, 2.3, 2.6        (high-impact Tier 2)
Sprint 3 (Days 6-8):  2.4, 2.5, 3.5              (remaining Tier 2 + cost dashboard)
Sprint 4 (Days 9-12): 3.1, 3.2, 3.3              (long-term, if prioritized)
Backlog:               3.4                         (DAG viz -- defer unless explicitly needed)
```

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CSS changes break dark mode | Medium | Low | Test all status variants in both themes |
| Store changes (Tier 3) cause re-render regressions | Medium | High | Use granular selectors with useShallow, add per-subagent state |
| i18n keys not added for new labels | Low | Low | Add to both en and zh translation files |
| SubAgentDetailPanel divergence (copied from SubAgentTimeline) | High | Medium | Consolidate shared logic into hooks before Tier 2 |
| Backend event payload changes needed | Low | Medium | Tier 1-2 require NO backend changes; Tier 3.3 requires new endpoint |

### Pre-Implementation Checklist

Before starting any tier:
- [ ] Verify E2E tests still pass (`make test-e2e`)
- [ ] Screenshot current SubAgent cards as baseline for visual comparison
- [ ] Confirm i18n translation files location (`web/src/locales/`)
- [ ] Review SubAgentDetailPanel TODO about code duplication

### Post-Implementation Verification

After each tier:
- [ ] `pnpm lint` passes
- [ ] `pnpm format:check` passes
- [ ] Visual comparison: dark mode + light mode screenshots
- [ ] All 8 status variants render correctly (running, success, error, background, queued, killed, steered, depth_limited)
- [ ] Parallel and chain modes display correctly
- [ ] No Zustand infinite re-render (check React DevTools)
- [ ] i18n: both en and zh labels present

---

## Appendix: Industry References

| Reference | URL | Key Pattern |
|-----------|-----|-------------|
| ChatGPT Deep Research | https://openai.com/index/introducing-deep-research/ | Fullscreen report, TOC, editable plan, mid-run steering |
| AgentPrism | https://github.com/evilmartians/agent-prism | Node-based React trace visualization, OpenTelemetry |
| VoltAgent | https://voltagent.dev | Interactive flowcharts, real-time execution paths |
| Inngest useAgent | https://www.inngest.com/blog/agentkit-useagent-realtime-hook | React hook for streaming multi-agent workflows |
| MCP Agentic | https://developer.microsoft.com/blog/can-you-build-agent2agent-communication-on-mcp-yes | Streaming + resumability + progress notifications |
| A2UI Protocol | Various | Agent-to-User Interface Protocol for native UI rendering |
| CrewAI / AutoGen / LangGraph Studio | Various | DAG views, step-by-step execution traces |
