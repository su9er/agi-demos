"""Shared pytest fixtures for memstack_cli tests."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture(autouse=True)
def isolated_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    fake_home = tmp_path / "home"
    fake_home.mkdir()
    monkeypatch.setenv("HOME", str(fake_home))
    import memstack_cli.auth as auth_mod

    monkeypatch.setattr(auth_mod, "CREDENTIALS_DIR", fake_home / ".memstack")
    monkeypatch.setattr(
        auth_mod, "CREDENTIALS_FILE", fake_home / ".memstack" / "credentials"
    )
    return fake_home


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in list(os.environ):
        if key.startswith("MEMSTACK_"):
            monkeypatch.delenv(key, raising=False)


class FakeRequest:
    """Stand-in for memstack_cli.client.request."""

    def __init__(self) -> None:
        self.responses: dict[tuple[str, str], Any] = {}
        self.error: Exception | None = None
        self.calls: list[dict[str, Any]] = []

    def __call__(
        self,
        method: str,
        path: str,
        *,
        api_key: str | None = None,
        json: Any = None,
        params: dict[str, Any] | None = None,
        timeout: float = 60.0,
    ) -> Any:
        self.calls.append(
            {
                "method": method,
                "path": path,
                "api_key": api_key,
                "json": json,
                "params": params,
            }
        )
        if self.error is not None:
            raise self.error
        return self.responses.get((method, path), {})


@pytest.fixture
def fake_request(monkeypatch: pytest.MonkeyPatch) -> FakeRequest:
    fake = FakeRequest()
    import memstack_cli.client as client_mod
    import memstack_cli.commands.artifacts_cmd as artifacts_mod
    import memstack_cli.commands.chat_cmd as chat_mod
    import memstack_cli.commands.info_cmd as info_mod
    import memstack_cli.commands.logs_cmd as logs_mod

    monkeypatch.setattr(client_mod, "request", fake)
    monkeypatch.setattr(artifacts_mod, "request", fake)
    monkeypatch.setattr(chat_mod, "request", fake)
    monkeypatch.setattr(info_mod, "request", fake)
    monkeypatch.setattr(logs_mod, "request", fake)
    return fake
