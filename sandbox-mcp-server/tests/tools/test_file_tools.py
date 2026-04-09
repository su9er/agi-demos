"""Regression tests for file tools."""

import pytest

from src.tools.file_tools import grep_files


class TestGrepTool:
    """Test suite for grep tool regressions."""

    @pytest.mark.asyncio
    async def test_grep_files_includes_context_lines(self, tmp_path, monkeypatch):
        """Context lines should be included around a match."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        test_file = workspace / "sample.txt"
        test_file.write_text("before\nmatch here\nafter\n", encoding="utf-8")

        monkeypatch.setattr("src.tools.file_tools._EXTRA_ALLOWED_PATHS", [])

        result = await grep_files(
            pattern="match",
            context_lines=1,
            _workspace_dir=str(workspace),
        )

        assert not result.get("isError")
        text = result["content"][0]["text"]
        assert "before" in text
        assert "match here" in text
        assert "after" in text

    @pytest.mark.asyncio
    async def test_grep_files_supports_allowed_paths_outside_workspace(
        self, tmp_path, monkeypatch
    ):
        """Searching an allowlisted path outside the workspace should not crash."""
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        allowed = tmp_path / "allowed"
        allowed.mkdir()
        (allowed / "outside.txt").write_text("needle\n", encoding="utf-8")

        monkeypatch.setattr(
            "src.tools.file_tools._EXTRA_ALLOWED_PATHS",
            [allowed.resolve()],
        )

        result = await grep_files(
            pattern="needle",
            path=str(allowed),
            _workspace_dir=str(workspace),
        )

        assert not result.get("isError")
        assert "outside.txt:1: needle" in result["content"][0]["text"]
