"""Tests for the HTTP client helpers."""

from __future__ import annotations

import pytest

from memstack_cli.client import ApiError, base_url


class TestBaseUrl:
    def test_default_localhost(self) -> None:
        assert base_url() == "http://localhost:8000"

    def test_override_and_strip_trailing_slash(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MEMSTACK_API_URL", "https://api.example.com/")
        assert base_url() == "https://api.example.com"


class TestApiError:
    def test_status_and_detail_preserved(self) -> None:
        err = ApiError(404, "not found")
        assert err.status_code == 404
        assert err.detail == "not found"
        assert "HTTP 404" in str(err)
        assert "not found" in str(err)
