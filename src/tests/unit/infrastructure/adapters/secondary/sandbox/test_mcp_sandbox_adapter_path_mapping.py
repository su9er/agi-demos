"""Tests for MCP sandbox path normalization."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.ports.services.sandbox_port import SandboxConfig, SandboxStatus
from src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter import (
    MCPSandboxAdapter,
    MCPSandboxInstance,
)


def _make_settings(
    *,
    host_source_path: str = "",
    host_source_mount_point: str = "/host_src",
    host_memstack_path: str = "",
    host_memstack_mount_point: str = "/workspace/.memstack",
):
    return SimpleNamespace(
        sandbox_host_source_path=host_source_path,
        sandbox_host_source_mount_point=host_source_mount_point,
        sandbox_host_memstack_path=host_memstack_path,
        sandbox_host_memstack_mount_point=host_memstack_mount_point,
    )


def _make_mcp_result(text: str = "ok", *, is_error: bool = False) -> SimpleNamespace:
    return SimpleNamespace(
        content=[{"type": "text", "text": text}],
        isError=is_error,
        metadata={},
    )


@pytest.fixture
def adapter() -> MCPSandboxAdapter:
    """Create an adapter with Docker patched out."""
    with patch(
        "src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter.docker.from_env",
        return_value=MagicMock(),
    ):
        return MCPSandboxAdapter()


@pytest.fixture
def sandbox_instance() -> MCPSandboxInstance:
    """Create a running sandbox instance with a connected MCP client."""
    mcp_client = AsyncMock()
    mcp_client.is_connected = True
    mcp_client.call_tool = AsyncMock(return_value=_make_mcp_result())
    return MCPSandboxInstance(
        id="sandbox-1",
        status=SandboxStatus.RUNNING,
        config=SandboxConfig(image="sandbox-mcp-server:latest"),
        project_path="/var/lib/memstack/workspaces/project-1",
        endpoint="ws://localhost:18765",
        websocket_url="ws://localhost:18765",
        mcp_port=18765,
        mcp_client=mcp_client,
        labels={"memstack.project_id": "project-1"},
    )


def _prepare_call_tool(
    adapter: MCPSandboxAdapter,
    sandbox_instance: MCPSandboxInstance,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter._active_sandboxes[sandbox_instance.id] = sandbox_instance
    monkeypatch.setattr(adapter, "_ensure_sandbox_healthy", AsyncMock(return_value=True))
    monkeypatch.setattr(adapter, "_record_activity", AsyncMock())


@pytest.mark.unit
class TestMCPSandboxAdapterPathMapping:
    """Tests for host/workspace path remapping."""

    def test_normalize_transport_config_maps_workspace_paths(
        self,
        adapter: MCPSandboxAdapter,
        sandbox_instance: MCPSandboxInstance,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Relative and host-workspace paths should normalize to /workspace."""
        adapter._active_sandboxes[sandbox_instance.id] = sandbox_instance
        monkeypatch.setattr(
            "src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter.get_settings",
            lambda: _make_settings(),
        )

        transport_config = {
            "command": "python",
            "args": [
                "servers/pdf_server.py",
                "/var/lib/memstack/workspaces/project-1/input/report.pdf",
                "--output",
                "output/result.pdf",
            ],
        }

        normalized = adapter.normalize_mcp_transport_config_for_sandbox(
            sandbox_instance.id,
            "stdio",
            transport_config,
        )

        assert normalized["args"] == [
            "/workspace/servers/pdf_server.py",
            "/workspace/input/report.pdf",
            "--output",
            "/workspace/output/result.pdf",
        ]

    def test_normalize_transport_config_handles_flag_equals_paths(
        self,
        adapter: MCPSandboxAdapter,
        sandbox_instance: MCPSandboxInstance,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Path-like values embedded in --flag=value arguments should normalize too."""
        adapter._active_sandboxes[sandbox_instance.id] = sandbox_instance
        monkeypatch.setattr(
            "src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter.get_settings",
            lambda: _make_settings(),
        )

        transport_config = {
            "command": "python",
            "args": [
                "--config=servers/pdf_server.toml",
                "--output=/var/lib/memstack/workspaces/project-1/output/result.pdf",
            ],
        }

        normalized = adapter.normalize_mcp_transport_config_for_sandbox(
            sandbox_instance.id,
            "stdio",
            transport_config,
        )

        assert normalized["args"] == [
            "--config=/workspace/servers/pdf_server.toml",
            "--output=/workspace/output/result.pdf",
        ]

    def test_normalize_transport_config_keeps_scoped_package_specs(
        self,
        adapter: MCPSandboxAdapter,
        sandbox_instance: MCPSandboxInstance,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Scoped package specs like @scope/pkg must not be rewritten as paths."""
        adapter._active_sandboxes[sandbox_instance.id] = sandbox_instance
        monkeypatch.setattr(
            "src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter.get_settings",
            lambda: _make_settings(),
        )

        transport_config = {
            "command": "npx",
            "args": ["-y", "@anthropic/mcp-server-fetch"],
        }

        normalized = adapter.normalize_mcp_transport_config_for_sandbox(
            sandbox_instance.id,
            "stdio",
            transport_config,
        )

        assert normalized["args"] == ["-y", "@anthropic/mcp-server-fetch"]

    @pytest.mark.asyncio
    async def test_call_tool_maps_host_source_reads_and_workspace_writes(
        self,
        adapter: MCPSandboxAdapter,
        sandbox_instance: MCPSandboxInstance,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Read paths can resolve from /host_src while output paths land in /workspace."""
        sandbox_instance.config.volumes["/Users/test/project"] = "/host_src"
        _prepare_call_tool(adapter, sandbox_instance, monkeypatch)
        monkeypatch.setattr(
            "src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter.get_settings",
            lambda: _make_settings(host_source_path="/Users/test/project"),
        )

        payload = {
            "input_file": "/Users/test/project/docs/report.pdf",
            "output_file": "/Users/test/project/output/extracted.txt",
        }

        result = await adapter.call_tool(
            sandbox_id=sandbox_instance.id,
            tool_name="mcp_server_call_tool",
            arguments={
                "server_name": "pdf-server",
                "tool_name": "pdf_extract_text",
                "arguments": json.dumps(payload),
            },
        )

        sent_payload = json.loads(
            sandbox_instance.mcp_client.call_tool.await_args.args[1]["arguments"]
        )
        assert result["is_error"] is False
        assert sent_payload["input_file"] == "/host_src/docs/report.pdf"
        assert sent_payload["output_file"] == "/workspace/output/extracted.txt"

    @pytest.mark.asyncio
    async def test_call_tool_rejects_unmounted_host_paths(
        self,
        adapter: MCPSandboxAdapter,
        sandbox_instance: MCPSandboxInstance,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Host-only paths outside the mounted sandbox roots should fail early."""
        _prepare_call_tool(adapter, sandbox_instance, monkeypatch)
        monkeypatch.setattr(
            "src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter.get_settings",
            lambda: _make_settings(host_source_path="/Users/test/project"),
        )

        result = await adapter.call_tool(
            sandbox_id=sandbox_instance.id,
            tool_name="mcp_server_call_tool",
            arguments={
                "server_name": "pdf-server",
                "tool_name": "pdf_extract_text",
                "arguments": json.dumps({"input_file": "/Users/test/other/report.pdf"}),
            },
        )

        assert result["is_error"] is True
        assert "not mounted in the sandbox" in result["content"][0]["text"]
        sandbox_instance.mcp_client.call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_call_tool_rejects_linux_style_unmounted_host_paths(
        self,
        adapter: MCPSandboxAdapter,
        sandbox_instance: MCPSandboxInstance,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Linux host paths should also fail closed when not mounted."""
        _prepare_call_tool(adapter, sandbox_instance, monkeypatch)
        monkeypatch.setattr(
            "src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter.get_settings",
            lambda: _make_settings(),
        )

        result = await adapter.call_tool(
            sandbox_id=sandbox_instance.id,
            tool_name="mcp_server_call_tool",
            arguments={
                "server_name": "pdf-server",
                "tool_name": "pdf_extract_text",
                "arguments": json.dumps({"input_file": "/home/test/other/report.pdf"}),
            },
        )

        assert result["is_error"] is True
        assert "not mounted in the sandbox" in result["content"][0]["text"]
        sandbox_instance.mcp_client.call_tool.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_call_tool_stores_normalized_start_config_for_health_restart(
        self,
        adapter: MCPSandboxAdapter,
        sandbox_instance: MCPSandboxInstance,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Successful mcp_server_start calls should persist normalized configs."""
        _prepare_call_tool(adapter, sandbox_instance, monkeypatch)
        monkeypatch.setattr(
            "src.infrastructure.adapters.secondary.sandbox.mcp_sandbox_adapter.get_settings",
            lambda: _make_settings(),
        )

        await adapter.call_tool(
            sandbox_id=sandbox_instance.id,
            tool_name="mcp_server_start",
            arguments={
                "name": "pdf-server",
                "server_type": "stdio",
                "transport_config": json.dumps(
                    {
                        "command": "python",
                        "args": ["servers/pdf_server.py"],
                    }
                ),
            },
        )

        stored = adapter._mcp_server_configs[(sandbox_instance.id, "pdf-server")]
        assert json.loads(stored["transport_config"])["args"] == [
            "/workspace/servers/pdf_server.py"
        ]
