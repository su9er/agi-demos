# SubAgent Subsystem Enhancement Plan

**Status**: COMPLETE (All 4 phases implemented and verified — 199 new tests, all passing)

---

## Event ID Naming Contract

The codebase uses multiple ID fields for sub-agent tracking. This plan canonicalizes their usage:

| Field Name | Definition | Where Used |
|------------|------------|------------|
| `execution_id` | Unique ID for a single sub-agent execution (UUID). Created by `BackgroundExecutor` or `SubAgentRunner` at spawn time. | `background_executor.py`, `state_tracker.py`, `run_registry.py`, all new domain events |
| `subagent_id` | Alias for `execution_id` in domain events. Used in event payloads for frontend consumption. Set equal to `execution_id`. | `agent_events.py` (all SubAgent*Event classes), frontend stores |
| `run_id` | Legacy field in `RunRegistry` — maps 1:1 to `execution_id`. Do NOT introduce new usages; prefer `execution_id`. | `run_registry.py` (internal only) |
| `conversation_id` | The parent conversation that spawned the sub-agent. Used for scoping and cleanup. | All layers |

**Rule**: In all NEW code, use `execution_id` as the canonical identifier. In event payloads sent to frontend, use `subagent_id` (set to `execution_id` value). Never introduce new `run_id` usages.
**Author**: Sisyphus Orchestrator
**Date**: 2025-03-03
**Reference Projects**: opencode, oh-my-opencode, openclaw

---

## Ambiguity Resolutions (Metis 2.1-2.6)

### 2.1: Sub-agent persistence backend
**Decision**: Hybrid — keep in-memory StateTracker for hot path, add Redis write-through for cross-process visibility. NOT Postgres — too much latency for lifecycle events.

### 2.2: Depth/resource limit enforcement semantics
**Decision**: Hard limits per-conversation, using existing ENV var defaults (max depth = 2 via `AGENT_SUBAGENT_MAX_DELEGATION_DEPTH`, max active = 16 via `AGENT_SUBAGENT_MAX_ACTIVE_RUNS`). These are configurable per-deployment. When hard limit hit, emit `subagent_depth_limited` event and refuse spawn with clear error message.

**Note**: Earlier draft incorrectly stated depth=3, active=5. Actual defaults from `config.py`: `agent_subagent_max_delegation_depth=2`, `agent_subagent_max_active_runs=16`. The plan uses whatever ENV vars are configured — do NOT hardcode limits.
### 2.3: Custom agent trust/permission model
**Decision**: Sandboxed by default — custom filesystem agents inherit a restricted tool allowlist. No recursive spawning unless `allow_spawn: true` in frontmatter. No approval flow (too much friction) — just hard deny on disallowed tools.

### 2.4: Event granularity contract
**Decision**: Summary by default + drill-down on click. Frontend shows collapsed lifecycle (spawning → running → completed/failed). Expanding a SubAgent group reveals full event timeline. Metadata preserved in event data but not rendered until expanded.

### 2.5: Announce/delivery pipeline scope
**Decision**: Direct async calls with retry (current pattern). No message queue — overkill for single-process deployment. The existing `BackgroundExecutor._emit()` callback is sufficient. Add retry wrapper with 3 attempts.

### 2.6: Background agent lifecycle ownership
**Decision**: Managed — BackgroundExecutor tracks all tasks, periodic sweep for orphans (every 60s), timeout enforcement per-run. Fire-and-forget is unsafe.

---

## AI Failure Trap Guardrails

These 9 traps MUST be checked in every code review:

| # | Trap | Guardrail |
|---|------|-----------|
| G1 | Modifying ToolDefinition instead of `._tool_instance` | NEVER add fields to ToolDefinition. Access tool methods via `tool_def._tool_instance` |
| G2 | Adding events without updating ALL 10 pipeline stages | Use checklist below for every new event type |
| G3 | Using global DI container for DB-dependent services | Always `get_container_with_db(request, db)` or `Depends(get_db)` |
| G4 | Breaking SubAgentProcess retry semantics | Retry ONLY if NO tool calls occurred. Check `result.tool_calls_count == 0` |
| G5 | Zustand useShallow omission | ALL object selectors MUST use `useShallow`. Single value selectors don't |
| G6 | Importing actor code in non-actor modules | NEVER import from `infrastructure/agent/actor/` outside actor code |
| G7 | Mutating frozen dataclasses | SubAgentMarkdown is `frozen=True`. Create new instances, don't mutate |
| G8 | Forgetting tenant scoping in queries | ALL new queries MUST include `project_id` or `tenant_id` WHERE clause |
| G9 | httpClient path duplication | Paths are relative to `/api/v1`. NEVER prefix with `/api/v1/` |

---

## New Event Type Checklist

The repo's authoritative checklist is in `src/domain/events/AGENTS.md` (5 steps). This plan extends it with frontend-specific steps for full pipeline coverage.

**Authoritative steps (from `src/domain/events/AGENTS.md`):**
1. `src/domain/events/types.py` — Add enum value to `AgentEventType` + add to `EVENT_CATEGORIES` dict
2. `src/domain/events/agent_events.py` — Create `AgentDomainEvent` Pydantic subclass (NOT dataclass), implement `to_event_dict()`, update `__all__`
3. Run `python scripts/generate_event_types.py` — Auto-generates `web/src/types/generated/eventTypes.ts` (DO NOT edit manually)
4. `src/infrastructure/agent/events/converter.py` — Add transformation in `_apply_transformations()` ONLY if non-standard serialization needed (SubAgent events pass through as-is)
5. `web/src/stores/agent/streamEventHandlers.ts` — Add handler in `createStreamEventHandlers`

**Additional steps for this plan (frontend visualization requires these):**
6. `web/src/types/agent/events.ts` — Add TypeScript interface for event data payload
7. `web/src/services/agent/messageRouter.ts` — Add case in router switch (STOP collapsing into generic types)
8. `web/src/components/agent/message/groupTimelineEvents.ts` — Add new event types to SubAgent grouping logic
9. `web/src/stores/agent/timelineStore.ts` or relevant store — Add state update logic if needed
10. UI component — Render the event (SubAgentTimeline.tsx, BackgroundSubAgentPanel.tsx, etc.)

**Note**: Steps 1-5 are MANDATORY for every new event type. Steps 6-10 apply when the event needs frontend rendering (all events in this plan do).
---

## Phase 1: Foundation — Event Pipeline Enrichment ✅ COMPLETE (34 tests)

### Goal
Enrich the sub-agent event pipeline to preserve lifecycle metadata that the frontend currently destroys. This unblocks all Phase 4 visualization work.

### P1.1: Add Missing Event Types to Backend Enum

**File**: `src/domain/events/types.py`

Add 5 new enum values to `AgentEventType` after line 187 (`SUBAGENT_RETRY`):

```python
SUBAGENT_QUEUED = "subagent_queued"           # SubAgent waiting in queue (depth/concurrency limit)
SUBAGENT_KILLED = "subagent_killed"           # SubAgent forcibly terminated
SUBAGENT_STEERED = "subagent_steered"         # SubAgent received steering instruction
SUBAGENT_DEPTH_LIMITED = "subagent_depth_limited"  # Spawn refused due to depth limit
SUBAGENT_SESSION_UPDATE = "subagent_session_update"  # Progress/status update from running subagent
```

Add all 5 to `EVENT_CATEGORIES` dict as `EventCategory.AGENT`.

**File**: `src/domain/events/agent_events.py`

Add 5 new `AgentDomainEvent` subclasses.

**IMPORTANT**: The codebase uses Pydantic `BaseModel` with field defaults for `event_type` (NOT `ClassVar`). Follow the existing pattern from `SubAgentStartedEvent`:
```python
class SubAgentQueuedEvent(AgentDomainEvent):
    """SubAgent queued — waiting for capacity."""
    event_type: AgentEventType = AgentEventType.SUBAGENT_QUEUED
    subagent_id: str
    subagent_name: str
    queue_position: int = 0
    reason: str = ""  # "depth_limit" | "concurrency_limit"

class SubAgentKilledEvent(AgentDomainEvent):
    """SubAgent forcibly terminated."""
    event_type: AgentEventType = AgentEventType.SUBAGENT_KILLED
    subagent_id: str
    subagent_name: str
    kill_reason: str  # "timeout" | "user_cancel" | "parent_cancel" | "orphan_sweep"

class SubAgentSteeredEvent(AgentDomainEvent):
    """SubAgent received steering instruction from parent."""
    event_type: AgentEventType = AgentEventType.SUBAGENT_STEERED
    subagent_id: str
    subagent_name: str
    instruction: str

class SubAgentDepthLimitedEvent(AgentDomainEvent):
    """SubAgent spawn refused due to depth limit."""
    event_type: AgentEventType = AgentEventType.SUBAGENT_DEPTH_LIMITED
    subagent_name: str
    current_depth: int
    max_depth: int
    parent_subagent_name: str = ""

class SubAgentSessionUpdateEvent(AgentDomainEvent):
    """Progress update from a running SubAgent."""
    event_type: AgentEventType = AgentEventType.SUBAGENT_SESSION_UPDATE
    subagent_id: str
    subagent_name: str
    progress: int = 0  # 0-100
    status_message: str = ""
    tokens_used: int = 0
    tool_calls_count: int = 0
```

Update `__all__` list.

**File**: `src/infrastructure/agent/events/converter.py`

No special transformation needed — `to_event_dict()` handles serialization. Events pass through as-is.

**Post-step**: Run `python scripts/generate_event_types.py` to regenerate `web/src/types/generated/eventTypes.ts`.

### P1.2: Fix Frontend Event Collapsing (messageRouter.ts)

**File**: `web/src/services/agent/messageRouter.ts`

**Problem**: 10+ distinct lifecycle events are collapsed into generic `subagent_started` / `subagent_failed`, destroying metadata needed for visualization.

**Solution**: Route each event type to its own handler instead of collapsing.

Specific changes:
- `subagent_spawning` → route to `onSubAgentSpawning` (NEW handler) instead of mapping to `subagent_started`
- `subagent_session_spawned` → route to `onSubAgentSessionSpawned` (NEW) instead of `subagent_started`
- `subagent_run_started` → route to `onSubAgentRunStarted` (NEW) instead of `subagent_started`
- `subagent_run_completed` → route to `onSubAgentRunCompleted` (NEW) instead of `subagent_completed`
- `subagent_run_failed` → route to `onSubAgentRunFailed` (NEW) instead of `subagent_failed`
- `subagent_killed` → route to `onSubAgentKilled` (NEW) instead of `subagent_failed`
- `subagent_session_message_sent` → route to `onSubAgentMessageSent` (NEW) instead of `subagent_started`
- `subagent_announce_retry` → route to `onSubAgentRetry` (keep existing) but preserve attempt metadata
- `subagent_announce_giveup` → route to `onSubAgentGiveup` (NEW) instead of `subagent_failed`
- `subagent_steered` → route to `onSubAgentSteered` (NEW) instead of `subagent_started`
- `subagent_queued` → route to `onSubAgentQueued` (NEW)
- `subagent_depth_limited` → route to `onSubAgentDepthLimited` (NEW)
- `subagent_session_update` → route to `onSubAgentSessionUpdate` (NEW)

**Implementation approach**: Each new handler appends to the timeline with the REAL event type (not the collapsed one). The handlers themselves are thin — they call `appendSSEEventToTimeline()` with the original event type and full data payload.

**File**: `web/src/stores/agent/streamEventHandlers.ts`

Add handler implementations for each new event type. Each handler:
1. Extracts relevant metadata from event data
2. Calls `appendSSEEventToTimeline(conversationId, event)` with original type
3. Updates `subagentStore` if needed (status changes)

**File**: `web/src/types/agent/events.ts`

Add TypeScript interfaces for new event data payloads:
- `SubAgentQueuedEventData`
- `SubAgentKilledEventData`
- `SubAgentSteeredEventData`
- `SubAgentDepthLimitedEventData`
- `SubAgentSessionUpdateEventData`

### P1.3: Extend SubAgentGroup Status + Timeline Types

**File**: `web/src/components/agent/timeline/SubAgentTimeline.tsx`

Extend `SubAgentGroup.status` union:
```typescript
status: 'running' | 'success' | 'error' | 'background' | 'queued' | 'retrying' | 'steered' | 'killed' | 'doom_loop' | 'depth_limited';
```

Add visual indicators for new statuses (icons, colors).

**File**: `web/src/components/agent/message/groupTimelineEvents.ts`

Update `buildSubAgentGroup()` to:
- Recognize all 5 new event types (`subagent_queued`, `subagent_killed`, `subagent_steered`, `subagent_depth_limited`, `subagent_session_update`) when grouping
- Recognize existing events that were previously collapsed: `subagent_spawning`, `subagent_session_spawned`, `subagent_run_started`, `subagent_run_completed`, `subagent_run_failed`, `subagent_announce_retry`, `subagent_announce_giveup`
- Set correct status based on latest event in group (e.g., `killed` if last event is `subagent_killed`)
- Preserve metadata from lifecycle events (spawn_mode, attempt count, kill reason, queue position, steering instruction, etc.) in group's `events` array

**NOTE**: This file is a critical visualization blocker. Without updating it, new event types will not group correctly in the timeline and may appear as orphan entries.
**File**: `web/src/components/agent/timeline/types.ts`

Add new `TimelineEventType` values if needed for the new subagent event types.

### P1.4: Emit New Events from Backend

**File**: `src/infrastructure/agent/subagent/background_executor.py`

- In `cancel()`: Emit `SubAgentKilledEvent` with `kill_reason="user_cancel"` before cancelling task
- In `_run()`: Emit progress events as `SubAgentSessionUpdateEvent` instead of raw dicts

**IMPORTANT — Formalizing existing informal events**: `background_executor.py` currently emits informal dict events `"background_subagent_started"` and `"background_subagent_completed"` that bypass the domain event system. During Phase 1 implementation:
1. Replace `{"type": "background_subagent_started", ...}` with `SubAgentStartedEvent` (already exists)
2. Replace `{"type": "background_subagent_completed", ...}` with `SubAgentCompletedEvent` (already exists)
3. Ensure all events flow through `EventConverter` for consistent serialization
4. Search for any other raw dict emissions and convert them to proper domain events
**File**: `src/infrastructure/agent/subagent/process.py`

- Emit `SubAgentKilledEvent` when timeout expires
- Emit `SubAgentSessionUpdateEvent` periodically (every N iterations) with progress estimate

**File**: `src/infrastructure/agent/core/subagent_runner.py`

- Before spawning: Check depth limit. If exceeded, emit `SubAgentDepthLimitedEvent` and return error
- If concurrency limit hit: Emit `SubAgentQueuedEvent` and wait (or reject)

### P1.5: Verification

- Run `python scripts/generate_event_types.py` and verify `eventTypes.ts` has all new types
- Run `make lint` on backend (ruff + mypy + pyright)
- Run `pnpm lint` on frontend
- Run `make test-unit` to verify no regressions
- Manual verification: Start dev, trigger SubAgent, verify new events appear in WebSocket stream

---

## Phase 2: Custom Agent Ecosystem ✅ COMPLETE (96 tests)

### Goal
Complete the markdown parser for feature parity with DB-defined agents, add validation and trust model for filesystem agents.

### P2.1: Complete MarkdownParser Field Support

**File**: `src/infrastructure/agent/subagent/markdown_parser.py`

Add 5 new fields to `SubAgentMarkdown` dataclass (line 35-68):

```python
@dataclass(frozen=True)
class SubAgentMarkdown:
    # ... existing fields ...
    max_tokens: int | None = None
    max_retries: int | None = None
    fallback_models: list[str] = field(default_factory=list)
    allowed_skills: list[str] = field(default_factory=list)
    allowed_mcp_servers: list[str] = field(default_factory=list)
    mode: str = "subagent"  # "subagent" | "primary" | "all"
    allow_spawn: bool = False  # Whether this agent can spawn sub-agents
```

Update `SubAgentMarkdownParser.parse()` (line 87-182) to extract new fields from frontmatter:

```python
# In parse() method, after temperature extraction:
max_tokens = frontmatter.get("max_tokens")
if max_tokens is not None:
    try:
        max_tokens = int(max_tokens)
    except (ValueError, TypeError):
        max_tokens = None

max_retries = frontmatter.get("max_retries")
if max_retries is not None:
    try:
        max_retries = int(max_retries)
    except (ValueError, TypeError):
        max_retries = None

fallback_models = self._extract_list(frontmatter, "fallback_models")
allowed_skills = self._extract_list(frontmatter, "allowed_skills")
allowed_mcp_servers = self._extract_list(frontmatter, "allowed_mcp_servers")

mode = str(frontmatter.get("mode", "subagent")).strip()
if mode not in ("subagent", "primary", "all"):
    mode = "subagent"

allow_spawn = frontmatter.get("allow_spawn", False)
if not isinstance(allow_spawn, bool):
    allow_spawn = str(allow_spawn).lower() in ("true", "yes", "1")
```

Pass new fields to `SubAgentMarkdown` constructor.

**File**: `src/infrastructure/agent/subagent/filesystem_loader.py`

Update `_resolve_max_tokens()` (line 262-273) to use the new `markdown.max_tokens` field:
```python
def _resolve_max_tokens(self, markdown: SubAgentMarkdown) -> int:
    if markdown.max_tokens is not None:
        return markdown.max_tokens
    # ... rest unchanged
```

Similarly update `_resolve_max_retries()` and `_resolve_fallback_models()` to use dataclass fields instead of `getattr()` workarounds.

### P2.2: Agent Validation and Trust Model

**New File**: `src/infrastructure/agent/subagent/agent_validator.py`

```python
"""Validates filesystem-loaded SubAgent definitions for safety and correctness."""

@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

class SubAgentValidator:
    """Validates SubAgent definitions loaded from filesystem."""

    # Tools that filesystem agents cannot use by default
    RESTRICTED_TOOLS: ClassVar[set[str]] = {
        "plugin_manager",     # Can install arbitrary code
        "env_var_set",        # Can modify environment
    }

    # Max system prompt size to prevent abuse
    MAX_PROMPT_LENGTH: int = 50_000

    def validate(self, markdown: SubAgentMarkdown) -> ValidationResult:
        """Validate a parsed SubAgent definition."""
        errors: list[str] = []
        warnings: list[str] = []

        # Required fields
        if not markdown.name or len(markdown.name) > 100:
            errors.append("name must be 1-100 characters")
        if not markdown.description:
            warnings.append("description is empty — agent may not be routable")

        # Prompt size
        if len(markdown.content) > self.MAX_PROMPT_LENGTH:
            errors.append(f"system prompt exceeds {self.MAX_PROMPT_LENGTH} chars")

        # Restricted tools
        restricted = set(markdown.tools) & self.RESTRICTED_TOOLS
        if restricted:
            errors.append(f"restricted tools not allowed for filesystem agents: {restricted}")

        # Spawn permission
        if markdown.allow_spawn and not markdown.tools:
            warnings.append("allow_spawn=true but no tools defined")

        # Model validation
        if markdown.model_raw not in ("inherit", "opus", "sonnet", "haiku", "gpt-4", "gpt-4o",
                                       "gemini-pro", "qwen-max", "deepseek-chat"):
            warnings.append(f"unrecognized model '{markdown.model_raw}' — will fall back to inherit")

        # Temperature bounds
        if markdown.temperature is not None and not (0.0 <= markdown.temperature <= 2.0):
            errors.append("temperature must be between 0.0 and 2.0")

        # Max iterations bounds
        if markdown.max_iterations is not None and not (1 <= markdown.max_iterations <= 50):
            errors.append("max_iterations must be between 1 and 50")

        return ValidationResult(valid=len(errors) == 0, errors=errors, warnings=warnings)
```

**File**: `src/infrastructure/agent/subagent/filesystem_loader.py`

Integrate validator into loading pipeline. After parsing markdown, validate before creating SubAgent:

```python
from .agent_validator import SubAgentValidator

# In _load_from_file() or equivalent:
validator = SubAgentValidator()
result = validator.validate(markdown)
if not result.valid:
    logger.warning(f"Invalid agent {path}: {result.errors}")
    return None  # Skip invalid agents
for warning in result.warnings:
    logger.info(f"Agent {markdown.name}: {warning}")
```

### P2.3: 3-Tier Override Resolution Hardening

**File**: `src/infrastructure/agent/subagent/filesystem_loader.py` (or new file `src/infrastructure/agent/subagent/override_resolver.py`)

Implement resolution order: user project agents > tenant agents > global agents

```python
class AgentOverrideResolver:
    """Resolves agent definitions with 3-tier override: project > tenant > global."""

    def resolve(
        self,
        project_agents: dict[str, SubAgent],
        tenant_agents: dict[str, SubAgent],
        global_agents: dict[str, SubAgent],
    ) -> dict[str, SubAgent]:
        """Merge agents with project taking highest priority."""
        merged = dict(global_agents)
        merged.update(tenant_agents)  # Tenant overrides global
        merged.update(project_agents)  # Project overrides tenant
        return merged
```

Integrate into the loading pipeline where agents are collected.

### P2.4: Verification

- Unit tests for new parser fields (all 7 new fields parse correctly from YAML frontmatter)
- Unit tests for validator (restricted tools, bounds checking, required fields)
- Unit tests for override resolver (3-tier priority)
- Run `make lint` and `make test-unit`
- Manual test: Create a `.memstack/agents/test.md` with all new fields, verify it loads correctly

---

## Phase 3: Reliability ✅ COMPLETE (57 tests)

### Goal
Add production-grade reliability features: depth enforcement, orphan recovery, and persistent state tracking.

### P3.1: Depth and Resource Limit Enforcement

**File**: `src/infrastructure/agent/core/subagent_runner.py`

Add depth tracking to the spawn path:

```python
async def check_spawn_limits(
    self,
    conversation_id: str,
    current_depth: int,
    subagent_name: str,
) -> tuple[bool, list[AgentDomainEvent]]:
    """Check if spawning is allowed given current limits.

    Returns:
        Tuple of (allowed: bool, events: list of domain events to emit).
        Caller is responsible for emitting the returned events.
    """
    events: list[AgentDomainEvent] = []

    max_depth = self._config.max_delegation_depth  # From ENV var
    if current_depth >= max_depth:
        events.append(SubAgentDepthLimitedEvent(
            subagent_name=subagent_name,
            current_depth=current_depth,
            max_depth=max_depth,
        ))
        return False, events

    # Check active run count
    active_count = self._run_registry.count_active(conversation_id)
    max_active = self._config.max_active_runs
    if active_count >= max_active:
        events.append(SubAgentQueuedEvent(
            subagent_id="",
            subagent_name=subagent_name,
            reason="concurrency_limit",
        ))
        return False, events

    return True, events
```

**Caller usage pattern:**
```python
allowed, limit_events = await self.check_spawn_limits(
    conversation_id, current_depth, subagent_name
)
for event in limit_events:
    yield event  # Emit via the generator protocol
if not allowed:
    return  # Do not proceed with spawn
```

### P3.2: Orphan Detection and Recovery

**File**: `src/infrastructure/agent/subagent/background_executor.py`

Add periodic orphan sweep:

```python
async def start_orphan_sweep(self, interval_seconds: int = 60) -> None:
    """Start periodic orphan detection sweep."""
    self._sweep_task = asyncio.create_task(self._orphan_sweep_loop(interval_seconds))

async def _orphan_sweep_loop(self, interval: int) -> None:
    """Periodically check for orphaned tasks."""
    while True:
        await asyncio.sleep(interval)
        try:
            await self._sweep_orphans()
        except Exception as e:
            logger.error(f"[BackgroundExecutor] Orphan sweep error: {e}")

async def _sweep_orphans(self) -> None:
    """Find and clean up orphaned background tasks."""
    for exec_id, task in list(self._tasks.items()):
        if task.done():
            # Already done, just clean up tracking
            self._tasks.pop(exec_id, None)
            continue

        # Check if task has been running too long
        state = self._tracker.get_state(exec_id, "")  # Need conversation_id
        if state and state.started_at:
            elapsed = (datetime.now(UTC) - state.started_at).total_seconds()
            timeout = self._timeout_seconds  # Configurable, default 300
            if elapsed > timeout:
                logger.warning(f"[BackgroundExecutor] Orphan detected: {exec_id} (running {elapsed:.0f}s)")
                task.cancel()
                self._tracker.fail(exec_id, state.conversation_id, error="Timed out (orphan sweep)")
                await self._emit({
                    "type": "subagent_killed",
                    "data": {
                        "execution_id": exec_id,
                        "subagent_name": state.subagent_name,
                        "kill_reason": "orphan_sweep",
                        "conversation_id": state.conversation_id,
                    },
                    "timestamp": datetime.now(UTC).isoformat(),
                })
```

### P3.3: StateTracker Redis Write-Through

**File**: `src/infrastructure/agent/subagent/state_tracker.py`

Add Redis persistence layer alongside in-memory cache:

```python
import asyncio
import json

class StateTracker:
    MAX_TRACKED = 50

    def __init__(self, redis_client: Any | None = None) -> None:
        self._states: dict[str, dict[str, SubAgentState]] = {}
        self._redis = redis_client
        self._lock = asyncio.Lock()  # Thread safety for concurrent access

    async def register(self, ...) -> SubAgentState:
        async with self._lock:
            state = SubAgentState(...)
            # In-memory
            if conversation_id not in self._states:
                self._states[conversation_id] = {}
            self._states[conversation_id][execution_id] = state

            # Redis write-through
            if self._redis:
                key = f"subagent:state:{conversation_id}:{execution_id}"
                await self._redis.setex(key, 3600, json.dumps(state.to_dict()))

            return state
```

**Note**: This changes the StateTracker API from sync to async. All callers (BackgroundExecutor, SubAgentRunner) need to be updated to `await` StateTracker methods.

**Alternative** (lower risk): Keep sync in-memory as primary, add async Redis write-through as fire-and-forget side effect. This avoids changing the sync API.

**Decision**: Use fire-and-forget pattern to minimize blast radius:

```python
def register(self, ...) -> SubAgentState:
    # Sync in-memory (unchanged)
    state = SubAgentState(...)
    self._states[conversation_id][execution_id] = state

    # Fire-and-forget Redis write
    if self._redis:
        asyncio.create_task(self._persist_to_redis(state))

    return state

async def _persist_to_redis(self, state: SubAgentState) -> None:
    try:
        key = f"subagent:state:{state.conversation_id}:{state.execution_id}"
        await self._redis.setex(key, 3600, json.dumps(state.to_dict()))
    except Exception as e:
        logger.warning(f"[StateTracker] Redis persist failed: {e}")
```

Add `asyncio.Lock()` around `_states` mutations to prevent race conditions from concurrent background tasks.

### P3.4: Verification

- Unit tests for depth limit enforcement (spawn refused at max depth)
- Unit tests for orphan sweep (tasks older than timeout get cancelled)
- Unit tests for StateTracker lock (concurrent register/complete don't corrupt)
- Integration test: StateTracker + Redis (write-through and read-back)
- Run `make lint` and `make test`

---

## Phase 4: Frontend Visualization ✅ COMPLETE (12 tests)

### Goal
Build rich SubAgent execution visualization — detail panel, enhanced background panel, and parallel/chain visualization.

### P4.1: SubAgent Execution Detail Panel

**New File**: `web/src/components/agent/timeline/SubAgentDetailPanel.tsx`

A drill-down panel that appears when clicking on a SubAgent group in the timeline:

```tsx
interface SubAgentDetailPanelProps {
  group: SubAgentGroup;
  onClose: () => void;
}
```

Contents:
- **Header**: SubAgent name, status badge, duration, model used
- **Timeline strip**: Compact vertical timeline of ALL lifecycle events (spawning → routed → started → act/observe cycles → completed/failed)
- **Metrics bar**: Token usage, tool calls count, iteration count
- **Error section** (if failed): Full error message, doom loop details if applicable
- **Retry history** (if retried): List of attempts with per-attempt model and error

Uses the preserved metadata from Phase 1 (events no longer collapsed).

### P4.2: Enhanced BackgroundSubAgentPanel

**File**: `web/src/components/agent/BackgroundSubAgentPanel.tsx`

Enhancements:
- **Progress bar**: Use `subagent_session_update` events for real-time progress
- **Kill button**: Calls `POST /api/v1/agent/subagent/{execution_id}/cancel`
- **Status chips**: Show new statuses (queued, retrying, steered, killed, doom_loop)
- **Correlation metadata**: Show parent↔child relationship using `sseEventAdapter.ts` utilities (`buildCausationTree`)
- **Auto-collapse completed**: Completed background agents collapse to one-line summary

### P4.3: Parallel/Chain Execution Visualization

**File**: `web/src/components/agent/timeline/SubAgentTimeline.tsx`

Add visual representations for:

**Parallel execution**:
- Detect parallel SubAgent groups (overlapping time ranges)
- Render side-by-side with a "parallel" badge
- Show aggregate metrics (total time = max of parallel durations)

**Chain execution**:
- Detect sequential SubAgent groups (one starts after another completes)
- Render with connecting arrows between groups
- Show cumulative metrics

**DAG visualization** (stretch):
- If task decomposition produced a dependency graph, visualize it
- Use simple box+arrow layout (not full Gantt — too complex for v1)

### P4.4: API Endpoint for SubAgent Cancel

**New File or addition**: `src/infrastructure/adapters/primary/web/routers/agent/subagent_router.py`

```python
@router.post("/subagent/{execution_id}/cancel")
async def cancel_subagent(
    execution_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Cancel a running background SubAgent."""
    # Access BackgroundExecutor via agent session
    # Call executor.cancel(execution_id, conversation_id)
    # Return success/failure
```

**Router registration**: If creating a new `subagent_router.py`, it MUST be registered in the parent router. Add to `src/infrastructure/adapters/primary/web/routers/agent/__init__.py`:
```python
from .subagent_router import router as subagent_router
agent_router.include_router(subagent_router, prefix="", tags=["agent-subagent"])
```
Alternatively, add the cancel endpoint directly to an existing agent router file to avoid registration overhead.

### P4.5: Verification

- Visual review: Start dev, trigger multi-SubAgent task, verify:
  - Detail panel opens on click
  - Background panel shows progress + kill button
  - Parallel SubAgents rendered side-by-side
  - Chain SubAgents rendered sequentially with arrows
- Run `pnpm lint` and `pnpm build` (no TypeScript errors)
- Run `make lint` on backend

---

## Implementation Order & Dependencies

```
Phase 1 (Foundation) ──┬──> Phase 2 (Custom Agents)  [independent]
                       │
                       └──> Phase 3 (Reliability)     [independent]
                       │
                       └──> Phase 4 (Visualization)   [depends on P1 completing]
```

- Phase 2 and Phase 3 can run in parallel after Phase 1
- Phase 4 depends on Phase 1 (event uncollapsing) being complete
- Within each phase, tasks are sequential (P1.1 → P1.2 → P1.3 → P1.4 → P1.5)

## Delegation Strategy

| Phase | Category | Skills | Agent Type |
|-------|----------|--------|------------|
| P1.1-P1.4 (backend events) | `deep` | `python-patterns`, `python-testing` | task (sync) |
| P1.2-P1.3 (frontend events) | `visual-engineering` | `ui-ux-pro-max`, `vercel-react-best-practices` | task (sync) |
| P2.1-P2.3 (parser + validator) | `quick` or `unspecified-low` | `python-patterns`, `python-testing` | task (sync) |
| P3.1-P3.3 (reliability) | `deep` | `python-patterns`, `python-testing` | task (sync) |
| P4.1-P4.3 (visualization) | `visual-engineering` | `ui-ux-pro-max`, `vercel-react-best-practices`, `vercel-composition-patterns` | task (sync) |

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| EventConverter breakage (CRITICAL) | Add unit tests for ALL event types before modifying. Test round-trip: create event → convert → verify SSE dict shape |
| ReActAgent callback wiring (CRITICAL) | Do NOT change callback signatures. Only add new callbacks if absolutely needed |
| StateTracker async migration | Use fire-and-forget Redis, keep sync API unchanged |
| Frontend infinite re-renders | EVERY new Zustand selector with object return MUST use useShallow |
| messageRouter regression | Preserve backward compat — old collapsed events still work, new specific events take priority |

## Testing Strategy

### Per-Phase Test Classes

**Phase 1:**
- `TestSubAgentEventTypes` — verify enum values, category mapping
- `TestSubAgentDomainEvents` — verify `to_event_dict()` serialization for all new events
- `TestEventConverter` — verify pass-through for new SubAgent events
- `TestMessageRouter` — verify new events route to correct handlers (not collapsed)

**Phase 2:**
- `TestMarkdownParserExtendedFields` — all 7 new fields parse from YAML
- `TestSubAgentValidator` — restricted tools, bounds, required fields
- `TestAgentOverrideResolver` — 3-tier priority resolution

**Phase 3:**
- `TestDepthLimitEnforcement` — spawn refused at max depth, event emitted
- `TestOrphanSweep` — timed-out tasks detected and cancelled
- `TestStateTrackerConcurrency` — concurrent register/complete don't corrupt
- `TestStateTrackerRedis` — write-through persistence and recovery

**Phase 4:**
- Visual testing via Playwright (stretch goal)
- Component tests for SubAgentDetailPanel, BackgroundSubAgentPanel

### Coverage Target
- 85%+ for new code (above project 80% minimum)
- Existing code must not drop below 80%

---

## Out of Scope

- Inter-agent message bus / agent-to-agent direct communication
- Agent marketplace / store
- RunRepository migration tooling
- MCP server dynamic attachment per SubAgent
- Per-SubAgent cost allocation and billing
- E2E Playwright tests (stretch goal only)
- Plugin hook invocation standardization (Phase 5 stretch)
- Callback Protocol types for type-safe wiring (Phase 5 stretch)
