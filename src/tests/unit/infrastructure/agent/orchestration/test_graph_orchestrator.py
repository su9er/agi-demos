"""Unit tests for graph orchestrator scope safeguards."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.domain.model.agent.graph import AgentGraph, GraphRun
from src.infrastructure.agent.orchestration.graph_orchestrator import GraphOrchestrator


@pytest.mark.unit
class TestGraphOrchestratorScope:
    def test_ensure_graph_matches_run_rejects_graph_id_mismatch(self) -> None:
        orchestrator = GraphOrchestrator(
            agent_orchestrator=MagicMock(),
            graph_repo=MagicMock(),
            run_repo=MagicMock(),
        )
        graph = AgentGraph(
            id="graph-b",
            tenant_id="tenant-1",
            project_id="proj-1",
            name="Graph B",
        )
        run = GraphRun(
            id="run-1",
            graph_id="graph-a",
            conversation_id="conv-1",
            tenant_id="tenant-1",
            project_id="proj-1",
        )

        with pytest.raises(ValueError, match="Graph run run-1 does not belong to graph graph-b"):
            orchestrator._ensure_graph_matches_run(graph, run)
