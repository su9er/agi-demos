"""Unit tests for ToolExecutionRouter, HostToolExecutor, SandboxToolExecutor."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.infrastructure.agent.core.host_tool_executor import HostToolExecutor
from src.infrastructure.agent.core.sandbox_tool_executor import (
    SandboxToolExecutor,
    _normalize_mcp_result,
)
from src.infrastructure.agent.core.tool_execution_router import (
    ToolExecutionConfig,
    ToolExecutionRouter,
)
from src.infrastructure.agent.tools.define import ToolInfo
from src.infrastructure.agent.tools.result import ToolResult


def _make_tool_info(name: str = "test_tool") -> ToolInfo:
    """Create a minimal ToolInfo for testing."""

    async def execute(**kwargs):  # type: ignore[no-untyped-def]
        return ToolResult(output="host result")

    return ToolInfo(
        name=name,
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        execute=execute,
    )


# ---------------------------------------------------------------------------
# ToolExecutionConfig
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToolExecutionConfig:
    """Tests for ToolExecutionConfig dataclass."""

    def test_host_mode_with_defaults(self) -> None:
        """Host mode with default sandbox fields."""
        config = ToolExecutionConfig(execution_mode="host")
        assert config.execution_mode == "host"
        assert config.sandbox_tool_name is None
        assert config.sandbox_dependencies == []

    def test_sandbox_mode_with_all_fields(self) -> None:
        """Sandbox mode with explicit dependencies and tool name."""
        config = ToolExecutionConfig(
            execution_mode="sandbox",
            sandbox_tool_name="my_tool",
            sandbox_dependencies=["requests>=2.0"],
        )
        assert config.execution_mode == "sandbox"
        assert config.sandbox_tool_name == "my_tool"
        assert config.sandbox_dependencies == ["requests>=2.0"]

    def test_sandbox_dependencies_default_is_empty_list(self) -> None:
        """Each instance should get its own empty list (no shared mutable default)."""
        a = ToolExecutionConfig(execution_mode="host")
        b = ToolExecutionConfig(execution_mode="host")
        a.sandbox_dependencies.append("numpy")
        assert b.sandbox_dependencies == []


# ---------------------------------------------------------------------------
# HostToolExecutor
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestHostToolExecutor:
    """Tests for HostToolExecutor — passthrough wrapper."""

    def test_wrap_returns_same_tool(self) -> None:
        """Host executor should return the original ToolInfo unchanged."""
        executor = HostToolExecutor()
        tool = _make_tool_info("passthrough")
        config = ToolExecutionConfig(execution_mode="host")
        result = executor.wrap(tool, config)
        assert result is tool

    def test_wrap_preserves_name_and_description(self) -> None:
        """Metadata remains intact after wrapping."""
        executor = HostToolExecutor()
        tool = _make_tool_info("my_tool")
        config = ToolExecutionConfig(execution_mode="host")
        result = executor.wrap(tool, config)
        assert result.name == "my_tool"
        assert result.description == "A test tool"

    def test_wrap_preserves_execute_callable(self) -> None:
        """Execute callable should be the same object."""
        executor = HostToolExecutor()
        tool = _make_tool_info("exec_test")
        config = ToolExecutionConfig(execution_mode="host")
        result = executor.wrap(tool, config)
        assert result.execute is tool.execute


# ---------------------------------------------------------------------------
# SandboxToolExecutor
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSandboxToolExecutor:
    """Tests for SandboxToolExecutor — sandbox delegation wrapper."""

    def test_wrap_replaces_execute(self) -> None:
        """Wrapped tool should have a different execute callable."""
        mock_port = MagicMock()
        executor = SandboxToolExecutor(
            sandbox_port=mock_port,
            sandbox_id="sandbox-123",
        )
        tool = _make_tool_info("sandbox_tool")
        config = ToolExecutionConfig(execution_mode="sandbox")
        result = executor.wrap(tool, config)
        assert result.name == "sandbox_tool"
        assert result.execute is not tool.execute

    def test_wrap_preserves_metadata(self) -> None:
        """All metadata fields except execute should carry over."""
        mock_port = MagicMock()
        executor = SandboxToolExecutor(
            sandbox_port=mock_port,
            sandbox_id="sandbox-456",
        )
        tool = _make_tool_info("meta_tool")
        config = ToolExecutionConfig(execution_mode="sandbox")
        result = executor.wrap(tool, config)
        assert result.name == "meta_tool"
        assert result.description == "A test tool"
        assert result.parameters == {"type": "object", "properties": {}}

    async def test_execute_delegates_to_sandbox_port(self) -> None:
        """Wrapped execute should call sandbox_port.call_tool."""
        mock_port = AsyncMock()
        mock_port.call_tool = AsyncMock(return_value={"output": "sandbox output"})
        executor = SandboxToolExecutor(
            sandbox_port=mock_port,
            sandbox_id="sandbox-789",
        )
        tool = _make_tool_info("delegate_tool")
        config = ToolExecutionConfig(execution_mode="sandbox")
        wrapped = executor.wrap(tool, config)
        result = await wrapped.execute(query="test")

        mock_port.call_tool.assert_called_once()
        assert isinstance(result, ToolResult)
        assert result.output == "sandbox output"

    async def test_execute_uses_default_tool_name(self) -> None:
        """Without sandbox_tool_name, the original tool name is used."""
        mock_port = AsyncMock()
        mock_port.call_tool = AsyncMock(return_value={"output": "ok"})
        executor = SandboxToolExecutor(
            sandbox_port=mock_port,
            sandbox_id="sandbox-aaa",
        )
        tool = _make_tool_info("original_name")
        config = ToolExecutionConfig(execution_mode="sandbox")
        wrapped = executor.wrap(tool, config)
        await wrapped.execute(query="test")

        call_args = mock_port.call_tool.call_args
        # call_tool(sandbox_id, tool_name, kwargs)
        assert call_args[0][0] == "sandbox-aaa"
        assert call_args[0][1] == "original_name"

    async def test_execute_uses_custom_sandbox_tool_name(self) -> None:
        """sandbox_tool_name in config should override tool name for dispatch."""
        mock_port = AsyncMock()
        mock_port.call_tool = AsyncMock(return_value={"output": "ok"})
        executor = SandboxToolExecutor(
            sandbox_port=mock_port,
            sandbox_id="sandbox-abc",
        )
        tool = _make_tool_info("host_name")
        config = ToolExecutionConfig(
            execution_mode="sandbox",
            sandbox_tool_name="sandbox_name",
        )
        wrapped = executor.wrap(tool, config)
        await wrapped.execute(query="test")

        call_args = mock_port.call_tool.call_args
        assert call_args[0][1] == "sandbox_name"

    async def test_execute_installs_dependencies(self) -> None:
        """Dependencies should be installed before execution."""
        mock_port = AsyncMock()
        mock_port.call_tool = AsyncMock(return_value={"output": "ok"})
        mock_dep_orch = AsyncMock()
        executor = SandboxToolExecutor(
            sandbox_port=mock_port,
            sandbox_id="sandbox-dep",
            dependency_orchestrator=mock_dep_orch,
        )
        tool = _make_tool_info("dep_tool")
        config = ToolExecutionConfig(
            execution_mode="sandbox",
            sandbox_dependencies=["numpy>=1.0"],
        )
        wrapped = executor.wrap(tool, config)
        await wrapped.execute()

        mock_dep_orch.ensure_dependencies.assert_called_once_with("sandbox-dep", ["numpy>=1.0"])

    async def test_execute_skips_deps_when_no_orchestrator(self) -> None:
        """Without dependency_orchestrator, dependencies are silently skipped."""
        mock_port = AsyncMock()
        mock_port.call_tool = AsyncMock(return_value={"output": "ok"})
        executor = SandboxToolExecutor(
            sandbox_port=mock_port,
            sandbox_id="sandbox-nodep",
        )
        tool = _make_tool_info("nodep_tool")
        config = ToolExecutionConfig(
            execution_mode="sandbox",
            sandbox_dependencies=["pandas"],
        )
        wrapped = executor.wrap(tool, config)
        result = await wrapped.execute()
        assert result.output == "ok"

    async def test_execute_propagates_exception(self) -> None:
        """Sandbox errors should propagate to the caller."""
        mock_port = AsyncMock()
        mock_port.call_tool = AsyncMock(side_effect=RuntimeError("sandbox died"))
        executor = SandboxToolExecutor(
            sandbox_port=mock_port,
            sandbox_id="sandbox-err",
        )
        tool = _make_tool_info("err_tool")
        config = ToolExecutionConfig(execution_mode="sandbox")
        wrapped = executor.wrap(tool, config)
        with pytest.raises(RuntimeError, match="sandbox died"):
            await wrapped.execute()


# ---------------------------------------------------------------------------
# _normalize_mcp_result
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestNormalizeMcpResult:
    """Tests for _normalize_mcp_result helper."""

    def test_string_output(self) -> None:
        result = _normalize_mcp_result({"output": "hello"}, "t")
        assert result.output == "hello"
        assert result.is_error is False

    def test_dict_output_is_json_serialized(self) -> None:
        result = _normalize_mcp_result({"output": {"key": "val"}}, "t")
        assert '"key"' in result.output
        assert '"val"' in result.output

    def test_non_string_output_is_stringified(self) -> None:
        result = _normalize_mcp_result({"output": 42}, "t")
        assert result.output == "42"

    def test_missing_output_defaults_to_empty(self) -> None:
        result = _normalize_mcp_result({}, "t")
        assert result.output == ""

    def test_is_error_true_via_isError(self) -> None:
        result = _normalize_mcp_result({"output": "err", "isError": True}, "t")
        assert result.is_error is True

    def test_is_error_true_via_is_error(self) -> None:
        result = _normalize_mcp_result({"output": "err", "is_error": True}, "t")
        assert result.is_error is True

    def test_is_error_false_by_default(self) -> None:
        result = _normalize_mcp_result({"output": "ok"}, "t")
        assert result.is_error is False


# ---------------------------------------------------------------------------
# ToolExecutionRouter
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestToolExecutionRouter:
    """Tests for ToolExecutionRouter — routes to host or sandbox executor."""

    def test_route_host_tool(self) -> None:
        """Host-mode config should delegate to host executor."""
        mock_sandbox_exec = MagicMock()
        mock_host_exec = MagicMock()
        mock_host_exec.wrap = MagicMock(side_effect=lambda t, c: t)

        router = ToolExecutionRouter(
            sandbox_executor=mock_sandbox_exec,
            host_executor=mock_host_exec,
        )
        tool = _make_tool_info("host_tool")
        config = ToolExecutionConfig(execution_mode="host")
        router.wrap_tool(tool, config)
        mock_host_exec.wrap.assert_called_once_with(tool, config)
        mock_sandbox_exec.wrap.assert_not_called()

    def test_route_sandbox_tool(self) -> None:
        """Sandbox-mode config should delegate to sandbox executor."""
        mock_sandbox_exec = MagicMock()
        mock_sandbox_exec.wrap = MagicMock(side_effect=lambda t, c: t)
        mock_host_exec = MagicMock()

        router = ToolExecutionRouter(
            sandbox_executor=mock_sandbox_exec,
            host_executor=mock_host_exec,
        )
        tool = _make_tool_info("sandbox_tool")
        config = ToolExecutionConfig(execution_mode="sandbox")
        router.wrap_tool(tool, config)
        mock_sandbox_exec.wrap.assert_called_once_with(tool, config)
        mock_host_exec.wrap.assert_not_called()

    def test_returns_wrapped_tool(self) -> None:
        """Router should return the result from the executor's wrap()."""
        sentinel_tool = _make_tool_info("wrapped")
        mock_host_exec = MagicMock()
        mock_host_exec.wrap = MagicMock(return_value=sentinel_tool)
        mock_sandbox_exec = MagicMock()

        router = ToolExecutionRouter(
            sandbox_executor=mock_sandbox_exec,
            host_executor=mock_host_exec,
        )
        tool = _make_tool_info("original")
        config = ToolExecutionConfig(execution_mode="host")
        result = router.wrap_tool(tool, config)
        assert result is sentinel_tool
