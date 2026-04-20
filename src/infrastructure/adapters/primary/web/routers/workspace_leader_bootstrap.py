from __future__ import annotations

from datetime import UTC, datetime

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.services.workspace_agent_autonomy import is_goal_root_task
from src.application.services.workspace_task_service import WorkspaceTaskService
from src.domain.model.workspace.workspace_agent import WorkspaceAgent
from src.domain.model.workspace.workspace_message import MessageSenderType
from src.infrastructure.adapters.primary.web.routers.agent.utils import get_container_with_db
from src.infrastructure.adapters.primary.web.routers.workspace_chat import (
    _fire_mention_routing,
    get_message_service,
)
from src.infrastructure.adapters.secondary.persistence.models import (
    AgentDefinitionModel,
    User,
    WorkspaceMessageModel,
)
from src.infrastructure.adapters.secondary.persistence.sql_workspace_message_repository import (
    SqlWorkspaceMessageRepository,
)
from src.infrastructure.agent.sisyphus.builtin_agent import (
    BUILTIN_AGENT_NAMESPACE,
    BUILTIN_SISYPHUS_DISPLAY_NAME,
    BUILTIN_SISYPHUS_ID,
    build_builtin_sisyphus_agent,
)


def _format_agent_mention(display_name: str | None, agent_id: str) -> str:
    handle = (display_name or "").strip() or agent_id
    return f'@"{handle}"' if " " in handle else f"@{handle}"


async def ensure_workspace_leader_binding(
    *,
    request: Request,
    db: AsyncSession,
    workspace_id: str,
) -> tuple[WorkspaceAgent, bool]:
    container = get_container_with_db(request, db)
    bindings = await container.workspace_agent_repository().find_by_workspace(
        workspace_id=workspace_id,
        active_only=True,
        limit=1,
        offset=0,
    )
    if bindings:
        return bindings[0], False

    builtin_row = await db.get(AgentDefinitionModel, BUILTIN_SISYPHUS_ID)
    if builtin_row is None:
        builtin_agent = build_builtin_sisyphus_agent(tenant_id=BUILTIN_AGENT_NAMESPACE)
        db.add(
            AgentDefinitionModel(
                id=builtin_agent.id,
                tenant_id=BUILTIN_AGENT_NAMESPACE,
                project_id=None,
                name=builtin_agent.name,
                display_name=builtin_agent.display_name,
                system_prompt=builtin_agent.system_prompt,
                trigger_description=builtin_agent.trigger.description,
                trigger_examples=list(builtin_agent.trigger.examples),
                trigger_keywords=list(builtin_agent.trigger.keywords),
                model=builtin_agent.model.value,
                persona_files=list(builtin_agent.persona_files),
                allowed_tools=list(builtin_agent.allowed_tools),
                allowed_skills=list(builtin_agent.allowed_skills),
                allowed_mcp_servers=list(builtin_agent.allowed_mcp_servers),
                max_tokens=builtin_agent.max_tokens,
                temperature=builtin_agent.temperature,
                max_iterations=builtin_agent.max_iterations,
                workspace_dir=builtin_agent.workspace_dir,
                workspace_config=builtin_agent.workspace_config.to_dict(),
                can_spawn=builtin_agent.can_spawn,
                max_spawn_depth=builtin_agent.max_spawn_depth,
                agent_to_agent_enabled=builtin_agent.agent_to_agent_enabled,
                agent_to_agent_allowlist=builtin_agent.agent_to_agent_allowlist,
                discoverable=builtin_agent.discoverable,
                source=builtin_agent.source.value,
                enabled=builtin_agent.enabled,
                max_retries=builtin_agent.max_retries,
                fallback_models=list(builtin_agent.fallback_models),
                total_invocations=builtin_agent.total_invocations,
                avg_execution_time_ms=builtin_agent.avg_execution_time_ms,
                success_rate=builtin_agent.success_rate,
                metadata_json=builtin_agent.metadata,
                session_policy=builtin_agent.session_policy.to_dict() if builtin_agent.session_policy else None,
                delegate_config=builtin_agent.delegate_config.to_dict() if builtin_agent.delegate_config else None,
                created_at=builtin_agent.created_at,
                updated_at=builtin_agent.updated_at,
            )
        )
        await db.flush()

    binding = await container.workspace_agent_repository().save(
        WorkspaceAgent(
            id=WorkspaceAgent.generate_id(),
            workspace_id=workspace_id,
            agent_id=BUILTIN_SISYPHUS_ID,
            display_name=BUILTIN_SISYPHUS_DISPLAY_NAME,
            description="Auto-bound builtin workspace leader",
            config={"auto_bound_builtin": True, "workspace_role": "leader"},
            is_active=True,
            label="Leader",
            status="idle",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    return binding, True


async def maybe_auto_trigger_existing_root_execution(
    *,
    request: Request,
    db: AsyncSession,
    workspace_id: str,
    current_user: User,
) -> bool:
    container = get_container_with_db(request, db)
    workspace = await container.workspace_repository().find_by_id(workspace_id)
    if workspace is None:
        return False

    leader_binding, _ = await ensure_workspace_leader_binding(
        request=request,
        db=db,
        workspace_id=workspace_id,
    )
    task_service = WorkspaceTaskService(
        workspace_repo=container.workspace_repository(),
        workspace_member_repo=container.workspace_member_repository(),
        workspace_agent_repo=container.workspace_agent_repository(),
        workspace_task_repo=container.workspace_task_repository(),
    )
    tasks = await task_service.list_tasks(
        workspace_id=workspace_id,
        actor_user_id=current_user.id,
        limit=100,
        offset=0,
    )
    root_tasks = [
        task
        for task in tasks
        if is_goal_root_task(task)
        and task.archived_at is None
        and getattr(task.status, "value", task.status) != "done"
    ]
    if len(root_tasks) != 1:
        return False

    root_task = root_tasks[0]
    child_tasks = await container.workspace_task_repository().find_by_root_goal_task_id(
        workspace_id,
        root_task.id,
    )
    if child_tasks:
        return False

    objective_id = root_task.metadata.get("objective_id")
    conversation_scope = (
        f"objective:{objective_id}"
        if isinstance(objective_id, str) and objective_id
        else f"root:{root_task.id}"
    )
    existing_messages = await SqlWorkspaceMessageRepository(db).find_by_workspace(
        workspace_id,
        limit=50,
    )
    if any(
        isinstance(message.metadata.get("conversation_scope"), str)
        and message.metadata.get("conversation_scope") == conversation_scope
        for message in existing_messages
    ):
        return False

    title = root_task.title
    if isinstance(objective_id, str) and objective_id:
        objective = await container.cyber_objective_repository().find_by_id(objective_id)
        if objective is not None:
            title = objective.title

    mention = _format_agent_mention(leader_binding.display_name, leader_binding.agent_id)
    content = (
        f"{mention} 中央黑板已有目标：{title}。"
        "请将这个 objective 转化为 workspace task，拆解并自主执行，直到完成。 "
        "Please decompose this objective into child tasks, execute it, and complete it."
    )
    message_service = get_message_service(request, db)
    message = await message_service.send_message(
        workspace_id=workspace_id,
        sender_id=current_user.id,
        sender_type=MessageSenderType.HUMAN,
        sender_name=current_user.email,
        content=content,
    )
    message.metadata["conversation_scope"] = conversation_scope
    if leader_binding.agent_id not in message.mentions:
        message.mentions = [*message.mentions, leader_binding.agent_id]
    message_row = await db.get(WorkspaceMessageModel, message.id)
    if message_row is not None:
        message_row.metadata_json = dict(message.metadata)
        message_row.mentions_json = list(message.mentions)
        await db.flush()
    await db.commit()
    _fire_mention_routing(
        request=request,
        workspace_id=workspace_id,
        message=message,
        tenant_id=workspace.tenant_id,
        project_id=workspace.project_id,
        user_id=current_user.id,
    )
    return True
