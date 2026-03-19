# MemStack 多代理架构演进提案

> 版本: 1.0 | 日期: 2026-03-19 | 状态: 提案

---

## 目录

1. [概述](#1-概述)
2. [现状分析](#2-现状分析)
3. [目标架构](#3-目标架构)
   - 3.1 Agent 身份与隔离模型
   - 3.2 消息路由与绑定
   - 3.3 子代理生命周期
   - 3.4 Spawn 防护机制
   - 3.5 可插拔上下文引擎
   - 3.6 会话管理
   - 3.7 工具策略与隔离
   - 3.8 并行执行与编排
   - 3.9 事件与可观测性
4. [领域模型变更](#4-领域模型变更)
5. [基础设施适配](#5-基础设施适配)
6. [差距分析](#6-差距分析)
7. [分阶段实施计划](#7-分阶段实施计划)
8. [风险与缓解](#8-风险与缓解)

---

## 1. 概述

### 1.1 背景与目标

MemStack 已经构建了一套成熟的四层代理架构 (Tool -> Skill -> SubAgent -> Agent), 具备 ReAct 推理循环、SubAgent 编排、并行调度、Redis 事件总线等核心能力. 但在多代理协作的深度场景中 -- 例如多个 SubAgent 长时间并行执行、跨代理消息路由、子代理生命周期精细管控 -- 现有架构存在若干空白.

本提案以 OpenClaw 项目的多代理模式作为参考架构, 结合 MemStack 自身的 DDD + Hexagonal Architecture 约束, 提出一套渐进式的架构演进方案. 核心目标:

- **生命周期韧性**: SubAgent 结果持久化, announce 重试, 孤儿检测, 确保多代理协作的可靠性
- **精细管控**: Spawn 防护, steer/kill 控制协议, 分层工具策略, 确保多代理行为可预测
- **灵活路由**: Binding-based 消息路由, 从 "SubAgent 匹配" 升级到 "消息级别调度"
- **上下文工程**: 可插拔上下文引擎, 生命周期钩子, 会话 fork/merge, 提升上下文利用效率
- **可观测性**: 跨代理执行链追踪, 新增事件类型, 支持多代理场景下的调试与监控

### 1.2 设计原则

| 原则 | 说明 |
|------|------|
| **增量式演进** | 每个阶段独立可交付, 不引入 breaking change, 现有 SubAgent 流程完全兼容 |
| **领域驱动** | 所有核心概念建模为领域对象, 遵循 `@dataclass(kw_only=True)`, 无基础设施泄漏 |
| **端口适配** | 新能力通过 Port 接口定义, 基础设施层提供 Redis/Ray 实现 |
| **Python 原生** | OpenClaw 是 TypeScript 实现, 所有模式需适配到 Python asyncio/FastAPI/Redis/Ray 技术栈 |
| **安全优先** | 代理隔离、工具策略、跨代理认证贯穿始终 |

### 1.3 参考架构

OpenClaw 提供了经过生产验证的多代理协作模式, 核心包括:

- Registry + Announce + Dispatch 三层协作模型
- Binding-based 消息路由 (最具体匹配优先)
- Per-agent workspace 隔离 (AGENTS.md / SOUL.md / 独立状态)
- Spawn guardrails (深度/并发/白名单/超时)
- Pluggable context engine (ingest -> assemble -> compact -> afterTurn 钩子链)
- Frozen result + announce retry 持久化语义

本提案不照搬 OpenClaw 实现, 而是提取其架构模式, 映射到 MemStack 的 Python/DDD 世界.

---

## 2. 现状分析

### 2.1 四层能力模型

```
+-----------------------------------------------------------+
|  L4: Agent (ReAct 推理循环)                                |
|  - ReActAgent: 顶层代理包装, 路由决策                        |
|  - SessionProcessor: 流式 LLM, 工具执行, HITL, doom-loop    |
|  - ReActLoop: Think -> Act -> Observe 循环协调器             |
+-----------------------------------------------------------+
|  L3: SubAgent (专业化代理)                                  |
|  - SubAgentRouter: 关键词/描述匹配到 SubAgent 定义           |
|  - ParallelScheduler: DAG 感知的并发执行                     |
|  - BackgroundExecutor: 后台 SubAgent 运行                   |
|  - SubAgentRunRegistry: 生命周期追踪                         |
|  - ContextBridge: Token 预算感知的上下文凝缩                  |
|  - TaskDecomposer: LLM-based 任务分解                       |
|  - ResultAggregator: 多 SubAgent 结果合并                   |
+-----------------------------------------------------------+
|  L2: Skill (声明式工具组合)                                  |
|  - SkillOrchestrator: 技能匹配与路由                         |
|  - SkillExecutor: 技能执行                                  |
|  - 触发模式: keyword / semantic / hybrid                    |
+-----------------------------------------------------------+
|  L1: Tool (原子能力)                                        |
|  - Terminal, Desktop, WebSearch, WebScrape                  |
|  - Plan (Enter/Update/Exit), Clarification, Decision        |
|  - GetEnvVar, RequestEnvVar, SandboxMCPToolWrapper          |
|  - delegate_to_subagent, parallel_delegate_subagents        |
|  - sessions_spawn, sessions_list, sessions_wait, sessions_ack|
+-----------------------------------------------------------+
```

### 2.2 核心执行路径

ExecutionRouter 根据置信度评分 (0.0-1.0) 决定执行路径:

```
DIRECT_SKILL -> SUBAGENT -> PLAN_MODE -> REACT_LOOP
```

路由决策由以下组件协同完成:
- **IntentGate**: 意图识别与分发
- **Domain-lane heuristics**: 领域匹配启发式规则
- **Forced flags**: 强制路径标志

### 2.3 通信基础设施

| 组件 | 机制 | 用途 |
|------|------|------|
| Redis Message Bus | `agent:messages:{parent_session_id}` | 子代理 -> 父代理异步 announce |
| Redis Event Streams | `agent:events:{conversation_id}` | SSE 事件发布到前端 |
| Ray Actors | `ProjectAgentActor` | 项目级别隔离与横向扩展 |
| ProcessorFactory | 每个 SubAgent 创建独立 SessionProcessor | 执行隔离 |

父代理通过 `_check_agent_announcements` 轮询子代理完成消息.

### 2.4 领域模型现状

**核心聚合:**

| 实体 | 职责 |
|------|------|
| `Conversation` | 聚合根, 持有 `current_plan_id`, `parent_conversation_id`, `current_mode` (BUILD/PLAN/EXPLORE) |
| `Message` | 承载 `tool_calls`, `tool_results`, `work_plan_ref`, `task_step_index`, `thought_level` |
| `ExecutionPlan` (WorkPlan) | 有序执行步骤, 状态转换, 反思设置 |
| `SubAgent` | 租户作用域的定义, 包含触发器、允许的工具/技能、模型配置 |
| `SubAgentRun` | 运行时执行记录, 不可变状态转换 |
| `SubAgentResult` | 结构化结果, 提供 `to_context_message()` 注入父会话 |
| `AgentExecution` | 单次 ReAct 循环记录 |
| `WorkflowPattern` | 已学习的路由/计划建议模式 |

**领域端口:**

- `SubAgentOrchestratorPort`, `ReActLoopPort`, `LLMInvokerPort`, `ToolExecutorPort`, `ContextManagerPort`
- `AgentServicePort`: stream_chat_v2, create_conversation, get_available_tools
- Repository ports: ConversationRepository, MessageRepository, SubAgentRepository, AgentExecutionRepository

**事件系统:**

已定义 70+ `AgentEventType` 值, 通过 `EventConverter` 转换为 SSE dict, 经 Redis streams 发布到前端.

### 2.5 现有优势

MemStack 的代理基础设施已具备相当成熟度:

1. **完备的四层模型**: 从原子工具到高阶推理的完整抽象层次
2. **DAG 感知的并行调度**: ParallelScheduler 已支持任务依赖关系
3. **成熟的 HITL 系统**: 持久化请求, 完整的暂停/恢复生命周期
4. **Ray Actor 隔离**: 项目级别的计算隔离已就绪
5. **丰富的事件系统**: 70+ 事件类型覆盖了大部分场景
6. **DDD 纪律**: 领域层纯净, Port/Adapter 分离清晰

这些构成了多代理架构演进的坚实基础, 我们要做的不是推翻重建, 而是在现有基础上填补关键空白.

---

## 3. 目标架构

### 3.1 Agent 身份与隔离模型

#### 3.1.1 OpenClaw 模式

OpenClaw 为每个 Agent 分配独立的 workspace 目录:

```
~/.openclaw/workspace-<agentId>/
  AGENTS.md       # Agent 能力描述
  SOUL.md         # 行为准则
  USER.md         # 用户偏好
  IDENTITY.md     # 身份标识
  skills/         # Agent 专有技能
  state/          # 运行时状态
  sessions/       # 会话数据
```

每个 Agent 拥有独立的 sandbox 模式和工具策略, 实现完全隔离.

#### 3.1.2 MemStack 适配

MemStack 的 Agent 运行在 Ray Actor 内, 隔离粒度是项目级别 (`ProjectAgentActor`). 我们不需要文件系统级别的 workspace (那是 CLI 工具的模式), 而是需要逻辑上的 Agent 身份与配置隔离.

**AgentIdentity 值对象:**

```python
@dataclass(kw_only=True)
class AgentIdentity:
    """Agent 的身份标识与能力声明."""
    agent_id: str
    name: str
    description: str
    system_prompt: str
    model_config: AgentModelConfig
    allowed_tools: list[str] = field(default_factory=list)
    allowed_skills: list[str] = field(default_factory=list)
    spawn_policy: SpawnPolicy = field(default_factory=SpawnPolicy)
    tool_policy: ToolPolicy = field(default_factory=ToolPolicy)
    metadata: dict[str, str] = field(default_factory=dict)
```

**隔离层次:**

```
ProjectAgentActor (Ray Actor)           -- 项目级隔离 (已有)
  |
  +-- AgentIdentity (配置隔离)            -- 每个 Agent 独立的身份/模型/工具配置
  |
  +-- SessionProcessor (执行隔离)         -- 每个 SubAgent 独立的处理器实例 (已有)
  |
  +-- Redis namespace (状态隔离)          -- 每个 Agent 独立的状态键空间
       agent:{project_id}:{agent_id}:*
```

**Agent 注册与发现:**

利用现有的 `SubAgent` 实体扩展, 新增 `identity` 字段关联 `AgentIdentity`. Agent 注册存储在 PostgreSQL (定义) + Redis (运行时状态). 发现通过 `SubAgentRouter` 扩展的 binding 匹配实现 (详见 3.2).

**关键决策: 不引入文件系统 workspace**

OpenClaw 的 workspace 模式适合 CLI/桌面场景. MemStack 是云平台, Agent 的 "workspace" 由数据库记录 + Redis 状态 + Ray Actor 共同构成. 这种抽象更适合分布式部署和多租户隔离.

### 3.2 消息路由与绑定

#### 3.2.1 OpenClaw 模式

OpenClaw 使用 Binding-based 路由, 按优先级匹配:

```
peer -> parentPeer -> guildId+roles -> guildId -> teamId -> accountId -> channel -> default
```

最具体的绑定优先匹配 (most-specific-wins). 这允许精细控制 "哪个 Agent 处理哪类消息".

#### 3.2.2 MemStack 适配

当前 MemStack 的消息路由发生在两个层面:

1. **ExecutionRouter** (宏观): 决定走 DIRECT_SKILL / SUBAGENT / PLAN_MODE / REACT_LOOP 路径
2. **SubAgentRouter** (微观): 根据关键词/描述匹配选择具体的 SubAgent

缺失的是: 在消息进入 Agent 系统之前, 没有 "哪个 Agent 应该处理这条消息" 的路由层.

**引入 MessageBinding 模型:**

```python
class BindingScope(str, Enum):
    """绑定作用域, 按优先级从高到低排列."""
    CONVERSATION = "conversation"     # 特定会话绑定
    USER_AGENT = "user_agent"        # 用户 + Agent 绑定
    PROJECT_ROLE = "project_role"    # 项目 + 角色绑定
    PROJECT = "project"              # 项目级别绑定
    TENANT = "tenant"               # 租户级别绑定
    DEFAULT = "default"             # 默认绑定

@dataclass(kw_only=True)
class MessageBinding:
    """消息到 Agent 的绑定规则."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_id: str
    scope: BindingScope
    scope_id: str                    # 作用域标识 (conversation_id / project_id / tenant_id)
    priority: int = 0               # 同作用域内的优先级
    filter_pattern: str | None = None  # 可选的消息内容过滤模式
    is_active: bool = True
```

**路由流程:**

```
Inbound Message
    |
    v
[MessageRouter]  -- 查找所有匹配的 Binding, 按 scope 优先级排序
    |
    v
[Matched Agent]  -- 如果有匹配, 直接路由到该 Agent
    |  (无匹配)
    v
[ExecutionRouter] -- 回退到现有路由逻辑 (DIRECT_SKILL -> SUBAGENT -> ...)
    |
    v
[SubAgentRouter]  -- 现有的关键词/描述匹配
```

**关键决策: Binding 层作为可选增强**

MessageBinding 不替换现有的 ExecutionRouter / SubAgentRouter, 而是在它们之上增加一层. 不配置 Binding 时, 系统行为与现在完全一致. 这确保了向后兼容.

### 3.3 子代理生命周期 (Handoff Protocol)

#### 3.3.1 现有生命周期

```
Spawn (SubAgentRunRegistry.register)
    |
    v
Run (BackgroundExecutor / ParallelScheduler)
    |
    v
Complete/Failed/Cancelled/TimedOut (状态转换)
    |
    v
Announce (Redis message bus: agent:messages:{parent_session_id})
    |
    v
Parent polls (_check_agent_announcements) -> Result injected
```

#### 3.3.2 目标生命周期

```
Spawn Request
    |
    v
[SpawnValidator] -- 深度/并发/白名单/超时检查 (新增, 详见 3.4)
    |  (rejected)
    +---------> SpawnRejected event
    |  (approved)
    v
Register (SubAgentRunRegistry + frozen_result slot)
    |
    v
Run (独立 SessionProcessor)
    |  (steer/kill 可干预)
    +<--------- Steer message injection (新增, 详见 3.3.4)
    +<--------- Kill with cascade (新增)
    |
    v
Complete -> Freeze Result (持久化到 frozen_result, 新增)
    |
    v
Announce (带重试和错误分类, 新增)
    |  (transient error -> retry with backoff)
    |  (permanent error -> mark failed, preserve frozen result)
    |  (success -> parent acknowledges)
    v
Cleanup (orphan detection, stale reconciliation, announce expiry)
```

#### 3.3.3 Frozen Result 持久化

**问题**: 当前 SubAgentResult 依赖于会话/会话消息状态. 如果父会话被删除或 SubAgent 的会话被清理, 结果就丢失了.

**方案**: 在 `SubAgentRun` 上新增 `frozen_result_text` 字段. SubAgent 完成时, 将结果序列化并冻结到该字段. 此后即使会话数据被清理, 结果仍可恢复.

```python
# SubAgentRun 实体扩展
@dataclass(kw_only=True)
class SubAgentRun:
    # ... 现有字段 ...
    frozen_result_text: str | None = None      # 冻结的结果文本
    frozen_at: datetime | None = None          # 冻结时间戳
    announce_state: AnnounceState = AnnounceState.PENDING
    announce_attempts: int = 0
    announce_last_error: str | None = None
    announce_expires_at: datetime | None = None

class AnnounceState(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RETRY = "retry"
    FAILED_TRANSIENT = "failed_transient"
    FAILED_PERMANENT = "failed_permanent"
    EXPIRED = "expired"
```

#### 3.3.4 Steer/Control 协议

**问题**: 当前无法向正在运行的 SubAgent 注入消息或强制终止.

**方案**: 通过 Redis channel 实现控制消息注入.

```
控制消息通道: agent:control:{subagent_run_id}

消息类型:
  - STEER:  注入上下文消息到 SubAgent 的处理循环
  - KILL:   终止 SubAgent 执行, 可选 cascade (终止其所有子代理)
  - PAUSE:  暂停执行 (配合 HITL)
  - RESUME: 恢复执行
```

SessionProcessor 在每个 Think-Act-Observe 循环之间检查控制通道:

```
Think -> [check control channel] -> Act -> [check control channel] -> Observe
```

**Tools 暴露给父 Agent:**

- `subagent_steer(run_id, message)`: 注入消息
- `subagent_kill(run_id, cascade=False)`: 终止执行
- `subagent_status(run_id)`: 查询运行状态 (扩展现有 `sessions_list`)

#### 3.3.5 Announce 重试与错误分类

**错误分类:**

| 类型 | 示例 | 处理策略 |
|------|------|----------|
| Transient | Redis 连接超时, 父 Actor 暂时不可达 | 指数退避重试, 最多 5 次 |
| Permanent | 父会话已删除, 父 Agent 不存在 | 标记失败, 保留 frozen result |

**重试配置:**

```python
@dataclass(kw_only=True)
class AnnounceConfig:
    """Announce 重试配置."""
    max_retries: int = 5
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    expiry_seconds: int = 3600  # 1 小时后过期
```

#### 3.3.6 孤儿检测与回收

**问题**: 如果父 Agent 崩溃, 正在运行的子 Agent 成为孤儿.

**方案**: 启动时 reconciliation + 周期性 sweeper.

1. **启动 reconciliation**: `ProjectAgentActor` 启动时, 从 Redis/DB 恢复所有 RUNNING 状态的 SubAgentRun, 检查其父会话是否仍然存在. 不存在则标记为 ORPHANED.
2. **周期性 sweeper**: 每 5 分钟扫描一次, 检查:
   - 超时的运行 (超过 `run_timeout_seconds`)
   - 无心跳的运行 (SubAgent 定期写入 heartbeat key)
   - announce 过期的运行

### 3.4 Spawn 防护机制

#### 3.4.1 OpenClaw 模式

```typescript
maxSpawnDepth: 2        // 最大嵌套深度
maxChildrenPerAgent: 5  // 每个 Agent 最大子代理数
maxConcurrent: 3        // 全局最大并发
runTimeoutSeconds: 300  // 单次运行超时
allowAgents: [...]      // Agent 白名单
```

#### 3.4.2 MemStack 适配

MemStack 已有 `max_subagent_delegation_depth` 配置, 但缺少完整的验证管道.

**SpawnPolicy 值对象:**

```python
@dataclass(kw_only=True)
class SpawnPolicy:
    """SubAgent 创建策略."""
    max_depth: int = 2
    max_children_per_agent: int = 5
    max_concurrent: int = 3
    run_timeout_seconds: int = 300
    allow_agents: list[str] = field(default_factory=list)  # 空 = 允许全部
    deny_agents: list[str] = field(default_factory=list)
```

**SpawnValidator 端口:**

```python
class SpawnValidatorPort(Protocol):
    """Spawn 验证器端口."""

    async def validate(
        self,
        parent_run: SubAgentRun | None,
        target_agent_id: str,
        spawn_policy: SpawnPolicy,
    ) -> SpawnValidationResult: ...

@dataclass(kw_only=True)
class SpawnValidationResult:
    approved: bool
    rejection_reason: str | None = None
    current_depth: int = 0
    current_children_count: int = 0
    current_concurrent_count: int = 0
```

**验证管道 (按顺序执行):**

```
1. 深度检查: 从 parent_run 递归计算当前深度, 对比 max_depth
2. 白名单检查: target_agent_id 是否在 allow_agents (非空时) 且不在 deny_agents
3. 子代理数检查: 当前 Agent 的 RUNNING 子代理数 < max_children_per_agent
4. 并发数检查: 全局 RUNNING SubAgentRun 数 < max_concurrent
5. 超时注册: 将 run_timeout_seconds 注入到 SubAgentRun, sweeper 据此超时
```

任一检查失败则拒绝 Spawn, 发出 `SpawnRejected` 领域事件.

### 3.5 可插拔上下文引擎

#### 3.5.1 OpenClaw 模式

```typescript
interface ContextEngine {
  ingest(message: Message): Promise<void>          // 新消息到达
  assemble(session: Session): Promise<Context>     // 组装上下文 (在 LLM 调用前)
  compact(context: Context): Promise<Context>      // 上下文压缩 (超出 token 预算时)
  afterTurn(result: TurnResult): Promise<void>     // 单轮完成后
  onSubagentEnded(result: SubagentResult): Promise<void>  // 子代理完成后
}
```

#### 3.5.2 MemStack 适配

MemStack 已有:
- `ContextManagerPort`: 上下文管理抽象
- `ContextBridge`: Token 预算感知的上下文凝缩
- `session/compaction.py`: 会话压缩逻辑

缺失的是: 统一的生命周期钩子管道, 以及可插拔性.

**ContextEnginePort:**

```python
class ContextEnginePort(Protocol):
    """可插拔上下文引擎端口."""

    async def on_message_ingest(
        self, message: Message, conversation: Conversation
    ) -> None:
        """新消息到达时调用. 用于索引、摘要提取等."""
        ...

    async def assemble_context(
        self, conversation: Conversation, token_budget: int
    ) -> AssembledContext:
        """在 LLM 调用前组装完整上下文."""
        ...

    async def compact_context(
        self, context: AssembledContext, target_tokens: int
    ) -> AssembledContext:
        """上下文超出预算时压缩."""
        ...

    async def after_turn(
        self, conversation: Conversation, turn_result: TurnResult
    ) -> None:
        """单轮推理完成后调用. 用于反思、记忆提取等."""
        ...

    async def on_subagent_ended(
        self, conversation: Conversation, result: SubAgentResult
    ) -> None:
        """子代理完成时调用. 用于结果整合、上下文更新等."""
        ...
```

**AssembledContext 值对象:**

```python
@dataclass(kw_only=True)
class AssembledContext:
    """组装后的上下文."""
    system_prompt: str
    messages: list[Message]
    injected_context: list[ContextSegment]  # 从记忆/知识图谱注入的额外上下文
    total_tokens: int
    budget_tokens: int
    is_compacted: bool = False
```

**与现有组件的整合:**

```
SessionProcessor
    |
    +-- 调用 ContextEnginePort.assemble_context()  (替代直接构建消息列表)
    |
    +-- 在 token 超限时调用 compact_context()      (替代直接调用 compaction)
    |
    +-- 在工具执行后调用 after_turn()              (新增)
    |
    +-- 在 SubAgent 完成时调用 on_subagent_ended() (新增)

ContextBridge -> 成为 ContextEnginePort 的默认实现中的一个组件
compaction.py -> 成为 compact_context() 的底层实现
```

**可插拔性**: 通过 DI Container 注入不同的 ContextEnginePort 实现. 默认实现整合现有 ContextBridge + compaction. 高级实现可加入 RAG 检索、知识图谱注入、对话摘要等.

### 3.6 会话管理

#### 3.6.1 OpenClaw 模式

- **dmScope**: main (全局会话) / per-peer (每用户独立会话) / per-channel-peer (每频道每用户)
- **daily/idle reset**: 按日/按空闲时间自动重置会话
- **session fork/merge**: 子代理 fork 出独立会话, 完成后结果 merge 回父会话

#### 3.6.2 MemStack 适配

MemStack 的 `Conversation` 已有 `parent_conversation_id` 字段, 支持父子关系. 但缺少正式的 fork/merge 语义.

**Session Fork:**

当 SubAgent 被 spawn 时, 从父 Conversation fork 出子 Conversation:

```python
@dataclass(kw_only=True)
class Conversation:
    # ... 现有字段 ...
    fork_source_id: str | None = None          # fork 来源会话 ID
    fork_context_snapshot: str | None = None   # fork 时的上下文快照 (压缩)
    merge_strategy: MergeStrategy = MergeStrategy.RESULT_ONLY

class MergeStrategy(str, Enum):
    RESULT_ONLY = "result_only"          # 仅合并最终结果 (默认)
    FULL_HISTORY = "full_history"        # 合并完整对话历史
    SUMMARY = "summary"                  # 合并 LLM 生成的摘要
```

**Session Merge:**

SubAgent 完成时, 根据 `MergeStrategy` 将结果合并回父会话:

```
RESULT_ONLY:   frozen_result_text -> 注入为父会话的 assistant message
FULL_HISTORY:  子会话的所有 messages -> 折叠为父会话的 context segment
SUMMARY:       LLM 对子会话 messages 做摘要 -> 注入为父会话 context
```

**Session Lifecycle:**

```
Created -> Active -> [Fork] -> Forked (子会话)
                  -> [Idle timeout] -> Idle
                  -> [Daily reset] -> Archived
                  -> [Merge] -> Merged (子会话完成, 结果已合并)
                  -> [Close] -> Closed
```

**与现有机制的关系:**

当前子代理结果通过 `SubAgentResult.to_context_message()` 注入父会话. 这本质上就是 `RESULT_ONLY` 的 merge 策略. 新方案将其正式化, 并提供更多选项.

### 3.7 工具策略与隔离

#### 3.7.1 OpenClaw 模式

每个 Agent 有独立的工具策略:

```typescript
toolPolicy: {
  allow: ["terminal", "web_search"],   // 白名单
  deny: ["desktop"],                    // 黑名单
  precedence: "deny"                    // deny 优先于 allow
}
```

#### 3.7.2 MemStack 适配

MemStack 已有 `SubAgent.allowed_tools` 和 SubAgentRouter 中的工具过滤. 但缺少:
- 分层策略 (Agent 级 -> Skill 级 -> 全局)
- 显式的 deny list
- 优先级规则

**ToolPolicy 值对象:**

```python
class ToolPolicyPrecedence(str, Enum):
    ALLOW_FIRST = "allow_first"    # 先检查 allow, 不在则拒绝
    DENY_FIRST = "deny_first"     # 先检查 deny, 不在则允许

@dataclass(kw_only=True)
class ToolPolicy:
    """分层工具策略."""
    allow: list[str] = field(default_factory=list)   # 空 = 允许全部
    deny: list[str] = field(default_factory=list)
    precedence: ToolPolicyPrecedence = ToolPolicyPrecedence.DENY_FIRST

    def is_allowed(self, tool_name: str) -> bool:
        """检查工具是否被允许."""
        if self.precedence == ToolPolicyPrecedence.DENY_FIRST:
            if tool_name in self.deny:
                return False
            if not self.allow:
                return True
            return tool_name in self.allow
        else:
            if tool_name in self.allow:
                return True
            if tool_name in self.deny:
                return False
            return not self.allow  # allow 为空时允许全部
```

**分层策略解析:**

```
Global ToolPolicy (系统默认)
    |
    v  merge
Agent-level ToolPolicy (AgentIdentity.tool_policy)
    |
    v  merge
Skill-level ToolPolicy (Skill 定义中的工具限制)
    |
    v
Final effective tool set
```

合并规则: 每一层的 deny 累加, allow 取交集 (越下层越严格).

### 3.8 并行执行与编排

#### 3.8.1 现有能力

MemStack 已经具备强大的并行执行基础:

- **ParallelScheduler**: DAG 感知的并发调度, 支持依赖关系
- **TaskDecomposer**: LLM-based 任务分解
- **ResultAggregator**: 多结果合并
- **BackgroundExecutor**: 后台执行

#### 3.8.2 增强方向

**更丰富的 DAG 依赖表达:**

```python
class DependencyType(str, Enum):
    HARD = "hard"           # 必须等待完成才能开始
    SOFT = "soft"           # 可以先开始, 但合并时需要等待
    STREAMING = "streaming" # 流式消费上游的部分结果

@dataclass(kw_only=True)
class TaskDependency:
    source_task_id: str
    target_task_id: str
    dependency_type: DependencyType = DependencyType.HARD
```

**流式部分结果:**

当前 ResultAggregator 等待所有 SubAgent 完成后才合并. 增强为支持流式部分结果:

```
SubAgent A: [partial_1] -> [partial_2] -> [final]
SubAgent B: [partial_1] -> [final]

ResultAggregator:
  -> on partial_1 from A: 立即转发给父 Agent (如果有 streaming 依赖)
  -> on final from B: 缓存
  -> on final from A: 合并 A + B, 生成最终结果
```

**与 Spawn 防护的整合:**

ParallelScheduler 在调度前调用 SpawnValidator, 确保:
- 并发数不超限
- 所有 target agent 在白名单内
- 总超时在预算内

### 3.9 事件与可观测性

#### 3.9.1 新增事件类型

| 事件 | 触发时机 | 数据 |
|------|----------|------|
| `SUBAGENT_STEER` | 控制消息注入到运行中的 SubAgent | run_id, message |
| `SUBAGENT_KILL` | SubAgent 被强制终止 | run_id, cascade, reason |
| `SPAWN_REJECTED` | Spawn 请求被防护机制拒绝 | target_agent_id, rejection_reason, policy |
| `ANNOUNCE_RETRY` | Announce 重试 | run_id, attempt, error_type |
| `ANNOUNCE_EXPIRED` | Announce 过期 | run_id, frozen_result_available |
| `CONTEXT_COMPACTED` | 上下文被压缩 | conversation_id, before_tokens, after_tokens |
| `CONTEXT_ASSEMBLED` | 上下文组装完成 | conversation_id, total_tokens, segments_count |
| `SESSION_FORKED` | 会话被 fork | parent_id, child_id, fork_context_size |
| `SESSION_MERGED` | 会话结果被 merge | parent_id, child_id, merge_strategy |
| `ORPHAN_DETECTED` | 孤儿 SubAgent 被检测到 | run_id, parent_session_id, action |
| `TOOL_POLICY_DENIED` | 工具使用被策略拒绝 | agent_id, tool_name, policy_layer |

#### 3.9.2 跨代理执行链追踪

**Trace Context 传播:**

每个 SubAgentRun 携带 `trace_id` 和 `parent_span_id`, 形成分布式追踪链:

```
[Root Agent] trace_id=T1, span_id=S1
    |
    +-- [SubAgent A] trace_id=T1, span_id=S2, parent_span_id=S1
    |       |
    |       +-- [SubAgent A1] trace_id=T1, span_id=S4, parent_span_id=S2
    |
    +-- [SubAgent B] trace_id=T1, span_id=S3, parent_span_id=S1
```

这与 MemStack 已有的 Jaeger/OTel 可观测性基础设施无缝整合.

**多代理 Timeline 视图:**

前端可基于 trace_id 渲染完整的多代理执行 timeline, 展示:
- 各 Agent 的启动/完成时间
- Steer/kill 控制事件
- Announce 重试/过期
- 上下文压缩事件
- 工具策略拒绝

---

## 4. 领域模型变更

### 4.1 新增值对象

| 值对象 | 所在模块 | 职责 |
|--------|----------|------|
| `SpawnPolicy` | `domain/model/agent/spawn_policy.py` | SubAgent 创建策略 (深度/并发/白名单/超时) |
| `ToolPolicy` | `domain/model/agent/tool_policy.py` | 分层工具策略 (allow/deny/precedence) |
| `AgentIdentity` | `domain/model/agent/identity.py` | Agent 身份标识与能力声明 |
| `AnnounceConfig` | `domain/model/agent/announce_config.py` | Announce 重试配置 |
| `MessageBinding` | `domain/model/agent/binding.py` | 消息到 Agent 的绑定规则 |
| `AssembledContext` | `domain/model/agent/context.py` | 组装后的上下文容器 |
| `TaskDependency` | `domain/model/agent/dependency.py` | 任务间依赖关系 |
| `SpawnValidationResult` | `domain/model/agent/spawn_policy.py` | Spawn 验证结果 |

### 4.2 实体修改

**SubAgentRun 扩展:**

```python
@dataclass(kw_only=True)
class SubAgentRun:
    # 现有字段保持不变...

    # 新增: Frozen Result
    frozen_result_text: str | None = None
    frozen_at: datetime | None = None

    # 新增: Announce 状态
    announce_state: AnnounceState = AnnounceState.PENDING
    announce_attempts: int = 0
    announce_last_error: str | None = None
    announce_expires_at: datetime | None = None

    # 新增: 追踪
    trace_id: str | None = None
    parent_span_id: str | None = None

    # 新增: 心跳
    last_heartbeat_at: datetime | None = None
```

**Conversation 扩展:**

```python
@dataclass(kw_only=True)
class Conversation:
    # 现有字段保持不变...

    # 新增: Fork/Merge 语义
    fork_source_id: str | None = None
    fork_context_snapshot: str | None = None
    merge_strategy: MergeStrategy = MergeStrategy.RESULT_ONLY
```

**SubAgent 扩展:**

```python
@dataclass(kw_only=True)
class SubAgent:
    # 现有字段保持不变...

    # 新增: Agent 身份
    identity: AgentIdentity | None = None

    # 新增: Spawn 策略 (覆盖全局默认)
    spawn_policy: SpawnPolicy | None = None

    # 新增: 工具策略 (替代 allowed_tools 的简单列表)
    tool_policy: ToolPolicy | None = None
```

### 4.3 新增枚举

```python
class AnnounceState(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    RETRY = "retry"
    FAILED_TRANSIENT = "failed_transient"
    FAILED_PERMANENT = "failed_permanent"
    EXPIRED = "expired"

class MergeStrategy(str, Enum):
    RESULT_ONLY = "result_only"
    FULL_HISTORY = "full_history"
    SUMMARY = "summary"

class BindingScope(str, Enum):
    CONVERSATION = "conversation"
    USER_AGENT = "user_agent"
    PROJECT_ROLE = "project_role"
    PROJECT = "project"
    TENANT = "tenant"
    DEFAULT = "default"

class ToolPolicyPrecedence(str, Enum):
    ALLOW_FIRST = "allow_first"
    DENY_FIRST = "deny_first"

class DependencyType(str, Enum):
    HARD = "hard"
    SOFT = "soft"
    STREAMING = "streaming"

class ControlMessageType(str, Enum):
    STEER = "steer"
    KILL = "kill"
    PAUSE = "pause"
    RESUME = "resume"
```

### 4.4 新增领域事件

```python
@dataclass(kw_only=True)
class SubAgentSteered(AgentDomainEvent):
    """控制消息已注入到运行中的 SubAgent."""
    run_id: str
    message: str

@dataclass(kw_only=True)
class SubAgentKilled(AgentDomainEvent):
    """SubAgent 已被强制终止."""
    run_id: str
    cascade: bool
    reason: str

@dataclass(kw_only=True)
class SpawnRejected(AgentDomainEvent):
    """Spawn 请求被防护机制拒绝."""
    target_agent_id: str
    rejection_reason: str
    current_depth: int
    max_depth: int

@dataclass(kw_only=True)
class AnnounceRetried(AgentDomainEvent):
    """Announce 重试."""
    run_id: str
    attempt: int
    error_type: str  # "transient" | "permanent"

@dataclass(kw_only=True)
class ContextCompacted(AgentDomainEvent):
    """上下文已压缩."""
    conversation_id: str
    before_tokens: int
    after_tokens: int

@dataclass(kw_only=True)
class SessionForked(AgentDomainEvent):
    """会话已被 fork."""
    parent_conversation_id: str
    child_conversation_id: str

@dataclass(kw_only=True)
class SessionMerged(AgentDomainEvent):
    """会话结果已被 merge."""
    parent_conversation_id: str
    child_conversation_id: str
    merge_strategy: MergeStrategy

@dataclass(kw_only=True)
class OrphanDetected(AgentDomainEvent):
    """孤儿 SubAgent 被检测到."""
    run_id: str
    parent_session_id: str
    action: str  # "cancelled" | "adopted" | "cleaned"

@dataclass(kw_only=True)
class ToolPolicyDenied(AgentDomainEvent):
    """工具使用被策略拒绝."""
    agent_id: str
    tool_name: str
    policy_layer: str  # "agent" | "skill" | "global"
```

### 4.5 新增端口

```python
class ContextEnginePort(Protocol):
    """可插拔上下文引擎."""
    async def on_message_ingest(self, message: Message, conversation: Conversation) -> None: ...
    async def assemble_context(self, conversation: Conversation, token_budget: int) -> AssembledContext: ...
    async def compact_context(self, context: AssembledContext, target_tokens: int) -> AssembledContext: ...
    async def after_turn(self, conversation: Conversation, turn_result: TurnResult) -> None: ...
    async def on_subagent_ended(self, conversation: Conversation, result: SubAgentResult) -> None: ...

class SpawnValidatorPort(Protocol):
    """Spawn 验证器."""
    async def validate(
        self, parent_run: SubAgentRun | None, target_agent_id: str, spawn_policy: SpawnPolicy
    ) -> SpawnValidationResult: ...

class AnnounceServicePort(Protocol):
    """Announce 服务."""
    async def announce(self, run: SubAgentRun, result: SubAgentResult) -> None: ...
    async def retry_pending(self) -> list[SubAgentRun]: ...
    async def expire_stale(self, cutoff: datetime) -> list[SubAgentRun]: ...

class ControlChannelPort(Protocol):
    """SubAgent 控制通道."""
    async def send_control(self, run_id: str, message_type: ControlMessageType, payload: dict) -> None: ...
    async def check_control(self, run_id: str) -> list[ControlMessage] | None: ...

class MessageRouterPort(Protocol):
    """消息路由器 (Binding-based)."""
    async def resolve_agent(self, message: Message, context: RoutingContext) -> str | None: ...
    async def register_binding(self, binding: MessageBinding) -> None: ...
    async def remove_binding(self, binding_id: str) -> None: ...
```

### 4.6 领域约束遵循

所有上述变更严格遵循 MemStack 领域层约束:

| 约束 | 遵循方式 |
|------|----------|
| `@dataclass(kw_only=True)` | 所有值对象和实体扩展字段使用 kw_only |
| Enum for statuses | AnnounceState, MergeStrategy, BindingScope 等均为 Enum |
| 无基础设施导入 | 所有新增模型仅依赖标准库和领域内类型 |
| Protocol for ports | 所有新端口使用 `typing.Protocol` 定义 |
| 不可变状态转换 | SubAgentRun 的 announce_state 遵循有限状态机 |

---

## 5. 基础设施适配

### 5.1 技术栈映射

| OpenClaw (TypeScript) | MemStack (Python) | 适配策略 |
|-----------------------|-------------------|----------|
| Map + disk persistence (runs.json) | SubAgentRunRegistry + Redis + PostgreSQL | 已有, 扩展 frozen_result 字段 |
| Channel/pubsub for announce | Redis Streams + Message Bus | 已有, 增加 retry 逻辑 |
| Spawner class | BackgroundExecutor + ProcessorFactory | 已有, 增加 SpawnValidator 前置检查 |
| Per-agent workspace (file system) | AgentIdentity + Redis namespace | 逻辑隔离替代物理隔离 |
| Context engine hooks (JS callbacks) | ContextEnginePort (Python Protocol) | 新建, 默认实现整合现有组件 |
| Binding store (in-memory) | MessageBinding + Redis sorted set | 新建 |
| Control channel (in-process) | Redis pub/sub: `agent:control:{run_id}` | 新建 |

### 5.2 Redis Key Schema (新增)

```
# Frozen Result (持久化到 DB, Redis 仅做缓存)
agent:frozen_result:{run_id}          -> frozen result text (TTL: 24h)

# Announce 状态
agent:announce:{run_id}               -> JSON {state, attempts, last_error, expires_at}

# 控制通道
agent:control:{run_id}                -> Redis List, LPUSH/BRPOP 模式

# Agent 心跳
agent:heartbeat:{run_id}              -> timestamp (TTL: 30s, 定期续期)

# 消息绑定索引
agent:bindings:{project_id}           -> Redis Sorted Set, score=priority
agent:binding:{binding_id}            -> JSON binding data

# Agent 状态隔离
agent:state:{project_id}:{agent_id}:* -> Agent 专有状态键空间

# Orphan 检测
agent:sweeper:last_run                -> timestamp
```

### 5.3 现有组件扩展 vs 新建

| 组件 | 策略 | 说明 |
|------|------|------|
| `SubAgentRunRegistry` | **扩展** | 增加 frozen_result, announce_state 管理, heartbeat 检查 |
| `BackgroundExecutor` | **扩展** | Spawn 前调用 SpawnValidator, 执行中检查 ControlChannel |
| `SessionProcessor` | **扩展** | 循环间检查 ControlChannel, 调用 ContextEngine hooks |
| `SubAgentRouter` | **扩展** | 支持 ToolPolicy 分层解析 |
| `ContextBridge` | **包装** | 成为 ContextEnginePort 默认实现的内部组件 |
| `SpawnValidator` | **新建** | `infrastructure/agent/subagent/spawn_validator.py` |
| `AnnounceService` | **新建** | `infrastructure/agent/subagent/announce_service.py` |
| `ControlChannel` | **新建** | `infrastructure/agent/subagent/control_channel.py` |
| `MessageRouter` | **新建** | `infrastructure/agent/routing/message_router.py` |
| `DefaultContextEngine` | **新建** | `infrastructure/agent/context/default_engine.py` |
| `OrphanSweeper` | **新建** | `infrastructure/agent/subagent/orphan_sweeper.py` |

### 5.4 Ray Actor 变更

`ProjectAgentActor` 需要增加:

1. **启动时 reconciliation**: 调用 `OrphanSweeper.reconcile()` 恢复/清理上次崩溃遗留的 SubAgentRun
2. **周期性 sweeper**: 启动后台 task 定期执行 `OrphanSweeper.sweep()`
3. **ControlChannel 监听**: 每个活跃的 SubAgentRun 注册到 ControlChannel, Actor 级别统一监听

### 5.5 数据库迁移

需要新增的 Alembic 迁移:

```
1. SubAgentRun 表:
   + frozen_result_text TEXT
   + frozen_at TIMESTAMP
   + announce_state VARCHAR(20) DEFAULT 'pending'
   + announce_attempts INTEGER DEFAULT 0
   + announce_last_error TEXT
   + announce_expires_at TIMESTAMP
   + trace_id VARCHAR(64)
   + parent_span_id VARCHAR(64)
   + last_heartbeat_at TIMESTAMP

2. Conversation 表:
   + fork_source_id VARCHAR(36) REFERENCES conversations(id)
   + fork_context_snapshot TEXT
   + merge_strategy VARCHAR(20) DEFAULT 'result_only'

3. SubAgent 表:
   + spawn_policy JSONB
   + tool_policy JSONB

4. 新建 message_bindings 表:
   id VARCHAR(36) PK
   agent_id VARCHAR(36) FK -> sub_agents(id)
   scope VARCHAR(20)
   scope_id VARCHAR(36)
   priority INTEGER
   filter_pattern TEXT
   is_active BOOLEAN DEFAULT TRUE
   created_at TIMESTAMP
   updated_at TIMESTAMP
```

---

## 6. 差距分析

以下是 MemStack 与 OpenClaw 多代理模式之间的 10 个关键差距, 按优先级排序:

| # | 差距 | 现状 | 优先级 | 工作量 | 阶段 |
|---|------|------|--------|--------|------|
| 1 | 无 Spawn 深度/并发/白名单验证管道 | 有 `max_subagent_delegation_depth` 配置但无验证执行 | **P0** | Small | Phase 1 |
| 2 | 无 frozen/durable result 持久化 | 结果依赖会话状态, 会话删除则丢失 | **P0** | Small | Phase 1 |
| 3 | 无 announce retry 与错误分类 | 基础 announce 无重试语义 | **P0** | Medium | Phase 1 |
| 4 | 无孤儿检测与启动 reconciliation | Actor 崩溃后子代理成为孤儿 | **P0** | Medium | Phase 1 |
| 5 | 无 steer/control 协议 | 无法向运行中的 SubAgent 注入消息或终止 | **P1** | Medium | Phase 2 |
| 6 | 无分层工具策略 (allow/deny/precedence) | 仅有 `allowed_tools` 简单列表 | **P1** | Small | Phase 2 |
| 7 | 无 Agent 身份模型 | SubAgent 无独立身份/配置隔离 | **P1** | Medium | Phase 2 |
| 8 | 无可插拔上下文引擎 | 上下文管理嵌入 Processor, 无生命周期钩子 | **P2** | Large | Phase 3 |
| 9 | 无 Binding-based 消息路由 | 路由在 SubAgent 级别, 非消息级别 | **P2** | Large | Phase 3 |
| 10 | 无 session fork/merge 语义 | 子代理结果注入但无正式 fork 模型 | **P2** | Medium | Phase 3 |

**补充差距 (Phase 4):**

| # | 差距 | 优先级 | 工作量 |
|---|------|--------|--------|
| 11 | 无 per-agent workspace 隔离 | P3 | Medium |
| 12 | 无跨代理认证 | P3 | Large |
| 13 | 无多代理执行链追踪 | P3 | Medium |
| 14 | 无 Agent 管理 UI | P3 | Large |

---

## 7. 分阶段实施计划

### Phase 1: 核心生命周期加固 (2-3 周)

**目标**: 确保 SubAgent 的生命周期可靠、结果持久、异常可恢复.

**交付物:**

| 任务 | 涉及组件 | 工作量 | 说明 |
|------|----------|--------|------|
| SpawnPolicy 值对象 | `domain/model/agent/` | 0.5d | 深度/并发/白名单/超时配置 |
| SpawnValidator 实现 | `infrastructure/agent/subagent/` | 1d | 验证管道: 深度 -> 白名单 -> 子代理数 -> 并发数 |
| BackgroundExecutor 集成 | `infrastructure/agent/subagent/` | 0.5d | Spawn 前调用 SpawnValidator |
| SpawnRejected 事件 | `domain/events/` | 0.5d | 新增领域事件 + EventConverter 处理 |
| frozen_result_text 字段 | DB migration + SubAgentRun | 1d | 数据库迁移 + 实体扩展 |
| 结果冻结逻辑 | SubAgentRunRegistry | 0.5d | SubAgent 完成时自动冻结 |
| AnnounceState 枚举 | `domain/model/agent/` | 0.5d | 状态机: PENDING -> DELIVERED/RETRY/FAILED/EXPIRED |
| AnnounceConfig 值对象 | `domain/model/agent/` | 0.5d | 重试配置 |
| AnnounceService 实现 | `infrastructure/agent/subagent/` | 2d | 重试逻辑 + 错误分类 + 过期处理 |
| OrphanSweeper 实现 | `infrastructure/agent/subagent/` | 1.5d | 启动 reconciliation + 周期性清扫 |
| Ray Actor 集成 | `infrastructure/agent/actor/` | 1d | 启动时调用 reconcile, 后台 sweeper task |
| 单元测试 | `tests/unit/` | 2d | SpawnValidator, AnnounceService, OrphanSweeper |
| 集成测试 | `tests/integration/` | 1d | 完整生命周期测试 |

**里程碑**: SubAgent 创建有防护, 结果不丢失, 异常自恢复.

### Phase 2: 控制与隔离 (2-3 周)

**目标**: 实现运行时控制能力和工具/身份隔离.

**交付物:**

| 任务 | 涉及组件 | 工作量 | 说明 |
|------|----------|--------|------|
| ControlChannel 实现 | `infrastructure/agent/subagent/` | 1.5d | Redis pub/sub 控制通道 |
| SessionProcessor 集成 | `infrastructure/agent/processor/` | 1d | 循环间检查控制消息 |
| subagent_steer / subagent_kill 工具 | `infrastructure/agent/tools/` | 1d | 暴露给父 Agent 的控制工具 |
| ToolPolicy 值对象 | `domain/model/agent/` | 0.5d | allow/deny/precedence |
| 分层策略解析 | SubAgentRouter | 1d | Global -> Agent -> Skill 层级合并 |
| AgentIdentity 值对象 | `domain/model/agent/` | 0.5d | 身份标识与能力声明 |
| SubAgent 实体扩展 | Domain + DB migration | 1d | identity, spawn_policy, tool_policy 字段 |
| 新增领域事件 | `domain/events/` | 1d | SubAgentSteered, SubAgentKilled, ToolPolicyDenied |
| 前端事件处理 | `web/src/services/` | 1d | 新事件类型路由 + 处理 |
| 单元测试 | `tests/unit/` | 1.5d | ControlChannel, ToolPolicy 解析 |
| 集成测试 | `tests/integration/` | 1d | Steer/kill 端到端测试 |

**里程碑**: 可控制运行中的 SubAgent, 工具使用有策略约束, Agent 有独立身份.

### Phase 3: 上下文与路由 (3-4 周)

**目标**: 实现可插拔上下文引擎、Binding-based 路由、session fork/merge.

**交付物:**

| 任务 | 涉及组件 | 工作量 | 说明 |
|------|----------|--------|------|
| ContextEnginePort 端口 | `domain/ports/` | 0.5d | 生命周期钩子接口 |
| AssembledContext 值对象 | `domain/model/agent/` | 0.5d | 上下文容器 |
| DefaultContextEngine 实现 | `infrastructure/agent/context/` | 3d | 整合 ContextBridge + compaction |
| SessionProcessor 集成 | `infrastructure/agent/processor/` | 1.5d | 替换直接上下文构建为 engine 调用 |
| MessageBinding 模型 | Domain + DB migration | 1d | Binding 规则 + 存储 |
| MessageRouter 实现 | `infrastructure/agent/routing/` | 2d | Binding 匹配 + fallback 到现有路由 |
| BindingScope 枚举 | `domain/model/agent/` | 0.5d | 优先级排序 |
| MergeStrategy 枚举 | `domain/model/agent/` | 0.5d | RESULT_ONLY / FULL_HISTORY / SUMMARY |
| Conversation 扩展 | Domain + DB migration | 1d | fork_source_id, merge_strategy |
| Session fork/merge 逻辑 | `infrastructure/agent/subagent/` | 2d | Fork 时快照, merge 时按策略合并 |
| 新增领域事件 | `domain/events/` | 0.5d | ContextCompacted, SessionForked, SessionMerged |
| 单元测试 | `tests/unit/` | 2d | ContextEngine, MessageRouter, fork/merge |
| 集成测试 | `tests/integration/` | 1.5d | 完整上下文生命周期, 路由端到端 |

**里程碑**: 上下文管理可扩展, 消息路由精细化, 会话关系正式化.

### Phase 4: 隔离与可观测性 (2-3 周)

**目标**: 完善 Agent 隔离、安全和可观测性.

**交付物:**

| 任务 | 涉及组件 | 工作量 | 说明 |
|------|----------|--------|------|
| Per-agent Redis namespace | `infrastructure/agent/` | 1d | Agent 状态键空间隔离 |
| 跨代理认证 | `infrastructure/security/` | 2d | Per-agent credential scope |
| Trace context 传播 | SubAgentRun + BackgroundExecutor | 1.5d | trace_id / parent_span_id |
| OTel span 集成 | `infrastructure/agent/` | 1d | 自动 span 创建/关联 |
| Agent 管理 API | `infrastructure/adapters/primary/web/` | 2d | CRUD + 状态查询 + binding 管理 |
| Agent 管理 UI | `web/src/pages/` | 3d | Agent 列表/配置/状态/timeline |
| 多代理 timeline 组件 | `web/src/components/agent/` | 2d | 基于 trace_id 的执行链视图 |
| E2E 测试 | `tests/e2e/` | 1.5d | 多代理完整流程 |

**里程碑**: 完整的多代理隔离、安全和可观测性. 运维可通过 UI 管理所有 Agent.

### 整体时间线

```
Week 1-3   [Phase 1: 核心生命周期加固]
           SpawnValidator | Frozen Result | AnnounceService | OrphanSweeper

Week 4-6   [Phase 2: 控制与隔离]
           ControlChannel | ToolPolicy | AgentIdentity | Steer/Kill Tools

Week 7-10  [Phase 3: 上下文与路由]
           ContextEngine | MessageRouter | Session Fork/Merge

Week 11-13 [Phase 4: 隔离与可观测性]
           Agent Workspace | Cross-Agent Auth | Tracing | UI
```

总计约 10-13 周, 每个 Phase 独立可交付.

---

## 8. 风险与缓解

### 8.1 复杂度风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 引入过多新概念导致认知负担 | 中 | 高 | 增量式引入, 每个 Phase 独立可用. 新概念均为可选增强, 不使用时退化到现有行为 |
| 领域模型膨胀 | 中 | 中 | 严格遵循 DDD 纪律: 值对象保持小而聚焦, 新实体仅在确实需要独立生命周期时引入 |
| Port 接口过多 | 低 | 中 | 每个 Port 有清晰的默认实现, 开发者无需全部了解 |

### 8.2 性能风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| Announce retry 的 Redis 开销 | 低 | 低 | 批量操作, 指数退避, 过期清理. Announce 频率本身不高 (SubAgent 完成时才触发) |
| ControlChannel 轮询开销 | 中 | 低 | 使用 Redis BRPOP 阻塞式读取, 无消息时零 CPU. 超时设置为 100ms |
| 周期性 sweeper 扫描 | 低 | 低 | 仅扫描 RUNNING 状态的 run (数量有限). 5 分钟间隔可配置 |
| MessageRouter 绑定匹配 | 低 | 低 | Redis Sorted Set 按优先级预排序, O(n) 扫描 n 通常 < 20 |

### 8.3 迁移风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| 数据库迁移导致停机 | 低 | 高 | 所有新字段均为 nullable 或有默认值, 支持 online migration. 先加字段, 后部署代码 |
| 现有 SubAgent 流程被破坏 | 低 | 高 | **所有变更均为增量式**: SpawnValidator 默认 policy 不拒绝任何请求, AnnounceService 兼容无 retry 的旧行为, ContextEngine 默认实现行为与现有一致 |
| Ray Actor 状态不兼容 | 中 | 中 | 新增的 reconciliation 逻辑自动处理状态不一致. Actor 重启时清理无效状态 |

### 8.4 技术债务风险

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| OpenClaw 模式不完全适配 Python 生态 | 中 | 中 | 本提案已过滤掉不适用的模式 (如文件系统 workspace). 每个适配都有明确的 Python-native 实现方案 |
| 过早优化 (YAGNI) | 中 | 低 | Phase 1 聚焦于已知的痛点 (结果丢失, 无防护, 无恢复). Phase 3-4 的高级功能可根据实际需求决定是否实施 |

---

## 附录 A: 术语表

| 术语 | 定义 |
|------|------|
| **Announce** | 子代理完成后向父代理发送结果通知的过程 |
| **Binding** | 消息到 Agent 的路由绑定规则 |
| **Frozen Result** | SubAgent 完成时持久化的结果快照, 不依赖会话状态 |
| **Fork** | 从父会话创建子会话的过程, 携带上下文快照 |
| **Merge** | 子会话结果合并回父会话的过程 |
| **Orphan** | 父代理已不存在但仍在运行的子代理 |
| **Spawn** | 创建新的 SubAgent 运行实例的过程 |
| **Steer** | 向运行中的 SubAgent 注入控制消息 |
| **Sweeper** | 周期性清扫任务, 检测超时/孤儿/过期的 SubAgent 运行 |

## 附录 B: 参考文献

| 来源 | 用途 |
|------|------|
| OpenClaw 源码 | 多代理协作模式参考 (Registry + Announce + Dispatch) |
| MemStack AGENTS.md | 现有架构约束和编码规范 |
| MemStack 代理模块源码 | 现有组件能力评估 |
| DDD (Eric Evans) | 领域建模方法论 |
| Hexagonal Architecture (Alistair Cockburn) | Port/Adapter 架构模式 |
