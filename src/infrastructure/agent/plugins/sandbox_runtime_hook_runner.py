"""Dedicated sandbox runner for runtime hook execution."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

from src.configuration.config import get_settings
from src.domain.ports.services.sandbox_resource_port import SandboxResourcePort
from src.infrastructure.mcp.utils import parse_tool_result

REPO_ROOT = Path(__file__).resolve().parents[4]


@dataclass(frozen=True)
class SandboxRuntimeHookExecutionResult:
    """Result produced by a sandboxed runtime hook execution."""

    result: dict[str, Any] | None
    sandbox_id: str


class SandboxRuntimeHookRunner:
    """Execute allowlisted runtime hook code inside a project sandbox."""

    def __init__(self, sandbox_resource_port: SandboxResourcePort | None) -> None:
        self._sandbox_resource_port = sandbox_resource_port

    def _resolve_source_path(self, source_path: Path) -> str:
        """Map a repo-local hook source path into the sandbox host-source mount."""
        relative_path = source_path.resolve().relative_to(REPO_ROOT)
        mount_point = get_settings().sandbox_host_source_mount_point
        return str(PurePosixPath(mount_point) / relative_path.as_posix())

    @staticmethod
    def _build_command(
        *,
        source_path: str,
        entrypoint: str,
        payload: dict[str, Any],
    ) -> str:
        """Build a bash command that executes the hook inside sandboxed Python."""
        payload_b64 = base64.b64encode(json.dumps(payload).encode("utf-8")).decode("utf-8")
        return (
            "python3 - <<'PY'\n"
            "import asyncio, base64, importlib.util, inspect, json\n"
            f"payload = json.loads(base64.b64decode({payload_b64!r}).decode('utf-8'))\n"
            f"source_path = {source_path!r}\n"
            f"entrypoint = {entrypoint!r}\n"
            "spec = importlib.util.spec_from_file_location('memstack_sandbox_hook', source_path)\n"
            "if spec is None or spec.loader is None:\n"
            "    raise RuntimeError(f'Unable to load runtime hook module from: {source_path}')\n"
            "module = importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "handler = getattr(module, entrypoint, None)\n"
            "if handler is None or not callable(handler):\n"
            "    raise RuntimeError(f\"Runtime hook entrypoint '{entrypoint}' was not found\")\n"
            "if inspect.iscoroutinefunction(handler):\n"
            "    result = asyncio.run(handler(payload))\n"
            "else:\n"
            "    result = handler(payload)\n"
            "if result is not None and not isinstance(result, dict):\n"
            "    raise RuntimeError('Runtime hook entrypoint must return dict or None')\n"
            "print(json.dumps({'__hook_result__': result}))\n"
            "PY"
        )

    async def run(
        self,
        *,
        project_id: str,
        tenant_id: str,
        source_path: Path,
        entrypoint: str,
        payload: dict[str, Any],
        timeout_seconds: float,
    ) -> SandboxRuntimeHookExecutionResult:
        """Execute a runtime hook inside the project's sandbox."""
        if self._sandbox_resource_port is None:
            raise RuntimeError("SandboxResourcePort is not registered for runtime hook execution")

        sandbox_id = await self._sandbox_resource_port.ensure_sandbox_ready(
            project_id=project_id,
            tenant_id=tenant_id,
        )
        raw_result = await self._sandbox_resource_port.execute_tool(
            project_id=project_id,
            tool_name="bash",
            arguments={
                "command": self._build_command(
                    source_path=self._resolve_source_path(source_path),
                    entrypoint=entrypoint,
                    payload=payload,
                )
            },
            timeout=max(timeout_seconds + 5.0, timeout_seconds),
        )
        parsed = parse_tool_result(raw_result)
        if not isinstance(parsed, dict) or "__hook_result__" not in parsed:
            raise RuntimeError("Sandbox hook execution did not return a valid JSON payload")

        result = parsed["__hook_result__"]
        if result is not None and not isinstance(result, dict):
            raise RuntimeError("Sandbox hook execution returned an invalid payload type")

        return SandboxRuntimeHookExecutionResult(result=result, sandbox_id=sandbox_id)
