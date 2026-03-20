"""SubAgent run trace and execution history endpoints."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.model.agent.subagent_run import SubAgentRun, SubAgentRunStatus
from src.infrastructure.adapters.primary.web.dependencies import (
    get_current_user,
)
from src.infrastructure.adapters.secondary.persistence.database import get_db

from .schemas import (
    ActiveRunCountResponse,
    DescendantTreeResponse,
    SubAgentRunListResponse,
    SubAgentRunResponse,
    TraceChainResponse,
)
from .utils import get_container_with_db

logger = logging.getLogger(__name__)

router = APIRouter()


def run_to_response(run: SubAgentRun) -> SubAgentRunResponse:
    data: dict[str, Any] = run.to_event_data()
    return SubAgentRunResponse(**data)


def parse_statuses(status_csv: str | None) -> list[SubAgentRunStatus] | None:
    if not status_csv:
        return None
    raw = [s.strip() for s in status_csv.split(",") if s.strip()]
    statuses: list[SubAgentRunStatus] = []
    for s in raw:
        try:
            statuses.append(SubAgentRunStatus(s))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status filter value: {s}",
            )
    return statuses or None


# --- Static routes MUST be registered before parameterised routes ---


@router.get(
    "/runs/active/count",
    response_model=ActiveRunCountResponse,
)
async def get_active_run_count(
    request: Request,
    conversation_id: str | None = Query(None, description="Scope to specific conversation"),
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActiveRunCountResponse:
    try:
        container = get_container_with_db(request, db)
        registry = container.subagent_run_registry()

        if conversation_id:
            count = registry.count_active_runs(conversation_id)
        else:
            count = registry.count_all_active_runs()

        return ActiveRunCountResponse(
            active_count=count,
            conversation_id=conversation_id,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting active run count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get active run count: {e!s}") from e


@router.get(
    "/runs/{conversation_id}",
    response_model=SubAgentRunListResponse,
)
async def list_runs(
    conversation_id: str,
    request: Request,
    status: str | None = Query(None, description="Comma-separated status filter"),
    trace_id: str | None = Query(None, description="Filter by trace_id"),
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubAgentRunListResponse:
    try:
        container = get_container_with_db(request, db)
        registry = container.subagent_run_registry()

        statuses = parse_statuses(status)
        runs: list[SubAgentRun] = registry.list_runs(conversation_id, statuses=statuses)

        if trace_id:
            runs = [r for r in runs if r.trace_id == trace_id]

        response_runs = [run_to_response(r) for r in runs]
        return SubAgentRunListResponse(
            conversation_id=conversation_id,
            runs=response_runs,
            total=len(response_runs),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing runs for {conversation_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to list runs: {e!s}") from e


@router.get(
    "/runs/{conversation_id}/trace/{trace_id}",
    response_model=TraceChainResponse,
)
async def get_trace_chain(
    conversation_id: str,
    trace_id: str,
    request: Request,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> TraceChainResponse:
    try:
        container = get_container_with_db(request, db)
        registry = container.subagent_run_registry()

        all_runs: list[SubAgentRun] = registry.list_runs(conversation_id)
        chain = [r for r in all_runs if r.trace_id == trace_id]
        chain.sort(key=lambda r: r.created_at)

        response_runs = [run_to_response(r) for r in chain]
        return TraceChainResponse(
            trace_id=trace_id,
            conversation_id=conversation_id,
            runs=response_runs,
            total=len(response_runs),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trace chain {trace_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get trace chain: {e!s}") from e


@router.get(
    "/runs/{conversation_id}/{run_id}/descendants",
    response_model=DescendantTreeResponse,
)
async def get_descendants(
    conversation_id: str,
    run_id: str,
    request: Request,
    include_terminal: bool = Query(True, description="Include terminal (completed/failed) runs"),
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DescendantTreeResponse:
    try:
        container = get_container_with_db(request, db)
        registry = container.subagent_run_registry()

        descendants: list[SubAgentRun] = registry.list_descendant_runs(
            conversation_id, run_id, include_terminal=include_terminal
        )

        response_runs = [run_to_response(r) for r in descendants]
        return DescendantTreeResponse(
            parent_run_id=run_id,
            conversation_id=conversation_id,
            descendants=response_runs,
            total=len(response_runs),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting descendants for {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get descendants: {e!s}") from e


@router.get(
    "/runs/{conversation_id}/{run_id}",
    response_model=SubAgentRunResponse,
)
async def get_run(
    conversation_id: str,
    run_id: str,
    request: Request,
    current_user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SubAgentRunResponse:
    try:
        container = get_container_with_db(request, db)
        registry = container.subagent_run_registry()

        run = registry.get_run(conversation_id, run_id)
        if run is None:
            raise HTTPException(
                status_code=404,
                detail=f"Run {run_id} not found in conversation {conversation_id}",
            )
        return run_to_response(run)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting run {run_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get run: {e!s}") from e
