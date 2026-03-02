"""Unit tests for WorkspaceSyncService."""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.application.services.workspace_sync_service import WorkspaceSyncService
from src.domain.ports.services.storage_service_port import StorageServicePort, UploadResult
from src.infrastructure.agent.workspace.manifest import FileEntry, WorkspaceManifest

# ---------------------------------------------------------------------------
# TestPreDestroySync
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPreDestroySync:
    """Tests for WorkspaceSyncService.pre_destroy_sync."""

    async def test_pre_destroy_sync_scans_workspace_and_saves_manifest(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Scan workspace, verify manifest.files contains the files and is saved to disk."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "main.py").write_text("print('hello')")
        (workspace / "data.json").write_text('{"key": "value"}')

        service = WorkspaceSyncService(workspace_base=str(tmp_path))

        manifest = await service.pre_destroy_sync(sandbox_id="sb-1", project_id=project_id)

        assert "main.py" in manifest.files
        assert "data.json" in manifest.files
        assert len(manifest.files) == 2

        # Verify saved to disk
        loaded = WorkspaceManifest.load(str(workspace))
        assert loaded is not None
        assert "main.py" in loaded.files

    async def test_pre_destroy_sync_records_sandbox_id(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Verify manifest.last_sandbox_id is set to the passed sandbox_id."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()

        service = WorkspaceSyncService(workspace_base=str(tmp_path))

        manifest = await service.pre_destroy_sync(sandbox_id="sb-42", project_id=project_id)

        assert manifest.last_sandbox_id == "sb-42"

    async def test_pre_destroy_sync_without_s3_skips_upload(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """s3_backup_enabled=False: no upload calls made."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "file.txt").write_text("content")

        mock_storage: AsyncMock = AsyncMock(spec=StorageServicePort)
        service = WorkspaceSyncService(
            workspace_base=str(tmp_path),
            s3_backup_enabled=False,
            storage_service=mock_storage,
        )

        await service.pre_destroy_sync(sandbox_id="sb-1", project_id=project_id)

        mock_storage.upload_file.assert_not_called()

    async def test_pre_destroy_sync_with_s3_syncs_unsynced_files(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """s3_backup_enabled=True: upload_file called for each unsynced file."""
        project_id = "proj-1"
        tenant_id = "tenant-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "a.py").write_text("a = 1")
        (workspace / "b.py").write_text("b = 2")

        mock_storage: AsyncMock = AsyncMock(spec=StorageServicePort)
        mock_storage.upload_file.return_value = UploadResult(
            object_key="key", size_bytes=10, content_type="application/octet-stream"
        )
        service = WorkspaceSyncService(
            workspace_base=str(tmp_path),
            s3_backup_enabled=True,
            storage_service=mock_storage,
        )

        await service.pre_destroy_sync(
            sandbox_id="sb-1", project_id=project_id, tenant_id=tenant_id
        )

        assert mock_storage.upload_file.call_count == 2

    async def test_pre_destroy_sync_with_s3_marks_files_synced(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """After sync, files have synced_to_s3=True and correct s3_key."""
        project_id = "proj-1"
        tenant_id = "tenant-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "code.py").write_text("x = 1")

        mock_storage: AsyncMock = AsyncMock(spec=StorageServicePort)
        mock_storage.upload_file.return_value = UploadResult(
            object_key="key", size_bytes=5, content_type="application/octet-stream"
        )
        service = WorkspaceSyncService(
            workspace_base=str(tmp_path),
            s3_backup_enabled=True,
            storage_service=mock_storage,
        )

        manifest = await service.pre_destroy_sync(
            sandbox_id="sb-1", project_id=project_id, tenant_id=tenant_id
        )

        entry = manifest.files["code.py"]
        assert entry.synced_to_s3 is True
        expected_key = f"workspaces/{tenant_id}/{project_id}/code.py"
        assert entry.s3_key == expected_key


# ---------------------------------------------------------------------------
# TestPostCreateRestore
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPostCreateRestore:
    """Tests for WorkspaceSyncService.post_create_restore."""

    async def test_post_create_restore_loads_existing_manifest(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Save a manifest to disk first, then call post_create_restore and verify it loaded."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()

        original = WorkspaceManifest(project_id=project_id, tenant_id="t-1")
        original.files["readme.md"] = FileEntry(
            relative_path="readme.md",
            size=50,
            sha256="aabb",
            created_at="2026-01-01T00:00:00+00:00",
        )
        original.save(str(workspace))

        service = WorkspaceSyncService(workspace_base=str(tmp_path))
        manifest = await service.post_create_restore(sandbox_id="sb-new", project_id=project_id)

        assert manifest.project_id == project_id
        assert "readme.md" in manifest.files
        assert manifest.files["readme.md"].sha256 == "aabb"

    async def test_post_create_restore_creates_new_manifest_if_none(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Call on empty workspace, verify returns a manifest with project_id set."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()

        service = WorkspaceSyncService(workspace_base=str(tmp_path))
        manifest = await service.post_create_restore(
            sandbox_id="sb-new", project_id=project_id, tenant_id="t-1"
        )

        assert manifest.project_id == project_id
        assert manifest.tenant_id == "t-1"
        assert manifest.files == {}

    async def test_post_create_restore_updates_sandbox_id(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Verify the new sandbox_id is recorded."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()

        service = WorkspaceSyncService(workspace_base=str(tmp_path))
        manifest = await service.post_create_restore(sandbox_id="sb-99", project_id=project_id)

        assert manifest.last_sandbox_id == "sb-99"

    async def test_post_create_restore_logs_missing_files(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Manifest has a file entry that doesn't exist on disk; method still returns."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()

        # Save manifest with a file entry for a non-existent file
        original = WorkspaceManifest(project_id=project_id)
        original.files["ghost.py"] = FileEntry(
            relative_path="ghost.py",
            size=100,
            sha256="deadbeef",
            created_at="2026-01-01T00:00:00+00:00",
        )
        original.save(str(workspace))

        service = WorkspaceSyncService(workspace_base=str(tmp_path))
        manifest = await service.post_create_restore(sandbox_id="sb-1", project_id=project_id)

        # Should succeed despite missing file
        assert manifest is not None
        assert "ghost.py" in manifest.files


# ---------------------------------------------------------------------------
# TestPostExecutionScan
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPostExecutionScan:
    """Tests for WorkspaceSyncService.post_execution_scan."""

    async def test_post_execution_scan_returns_empty_for_nonexistent_workspace(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Workspace directory doesn't exist: returns empty list."""
        service = WorkspaceSyncService(workspace_base=str(tmp_path))
        changed = await service.post_execution_scan(project_id="nonexistent")
        assert changed == []

    async def test_post_execution_scan_detects_new_files(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Create workspace, scan, add a new file, scan again: new file in results."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "original.py").write_text("x = 1")

        service = WorkspaceSyncService(workspace_base=str(tmp_path))

        # First scan to establish baseline
        changed_first = await service.post_execution_scan(project_id=project_id)
        assert "original.py" in changed_first  # new file on first scan

        # Add a new file
        (workspace / "new_file.py").write_text("y = 2")

        # Second scan should detect only the new file
        changed_second = await service.post_execution_scan(project_id=project_id)
        assert "new_file.py" in changed_second
        assert "original.py" not in changed_second

    async def test_post_execution_scan_detects_changed_files(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Create workspace with a file, scan, change file, scan again: changed file in results."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "mutable.py").write_text("version = 1")

        service = WorkspaceSyncService(workspace_base=str(tmp_path))

        # First scan
        await service.post_execution_scan(project_id=project_id)

        # Modify the file
        (workspace / "mutable.py").write_text("version = 2")

        # Second scan should detect the change
        changed = await service.post_execution_scan(project_id=project_id)
        assert "mutable.py" in changed

    async def test_post_execution_scan_returns_empty_for_unchanged(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Scan twice with no changes: second scan returns empty list."""
        project_id = "proj-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "stable.py").write_text("pass")

        service = WorkspaceSyncService(workspace_base=str(tmp_path))

        # First scan
        await service.post_execution_scan(project_id=project_id)

        # Second scan with no changes
        changed = await service.post_execution_scan(project_id=project_id)
        assert changed == []


# ---------------------------------------------------------------------------
# TestSyncUnsyncedToS3
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestSyncUnsyncedToS3:
    """Tests for WorkspaceSyncService._sync_unsynced_to_s3."""

    async def test_sync_unsynced_to_s3_uploads_files(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Create manifest with unsynced files, call _sync_unsynced_to_s3, verify upload."""
        project_id = "proj-1"
        tenant_id = "tenant-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "upload_me.py").write_text("data")

        mock_storage: AsyncMock = AsyncMock(spec=StorageServicePort)
        mock_storage.upload_file.return_value = UploadResult(
            object_key="key", size_bytes=4, content_type="application/octet-stream"
        )
        service = WorkspaceSyncService(
            workspace_base=str(tmp_path),
            s3_backup_enabled=True,
            storage_service=mock_storage,
        )

        manifest = WorkspaceManifest.scan(str(workspace), project_id=project_id)

        await service._sync_unsynced_to_s3(manifest, workspace, project_id, tenant_id)

        expected_key = f"workspaces/{tenant_id}/{project_id}/upload_me.py"
        mock_storage.upload_file.assert_called_once()
        call_kwargs = mock_storage.upload_file.call_args
        assert call_kwargs.kwargs["object_key"] == expected_key

    async def test_sync_unsynced_to_s3_skips_missing_files(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Manifest entry exists but file is missing on disk: no crash."""
        project_id = "proj-1"
        tenant_id = "tenant-1"
        workspace = tmp_path / project_id
        workspace.mkdir()

        mock_storage: AsyncMock = AsyncMock(spec=StorageServicePort)
        service = WorkspaceSyncService(
            workspace_base=str(tmp_path),
            s3_backup_enabled=True,
            storage_service=mock_storage,
        )

        manifest = WorkspaceManifest(project_id=project_id)
        manifest.files["ghost.py"] = FileEntry(
            relative_path="ghost.py",
            size=50,
            sha256="abc",
            created_at="2026-01-01T00:00:00+00:00",
        )

        # Should not crash
        await service._sync_unsynced_to_s3(manifest, workspace, project_id, tenant_id)

        mock_storage.upload_file.assert_not_called()

    async def test_sync_unsynced_to_s3_handles_upload_failure_gracefully(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """Mock upload_file to raise: no crash, error handled gracefully."""
        project_id = "proj-1"
        tenant_id = "tenant-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "fail.py").write_text("oops")

        mock_storage: AsyncMock = AsyncMock(spec=StorageServicePort)
        mock_storage.upload_file.side_effect = RuntimeError("S3 down")
        service = WorkspaceSyncService(
            workspace_base=str(tmp_path),
            s3_backup_enabled=True,
            storage_service=mock_storage,
        )

        manifest = WorkspaceManifest.scan(str(workspace), project_id=project_id)

        # Should not raise
        await service._sync_unsynced_to_s3(manifest, workspace, project_id, tenant_id)

        # File should NOT be marked as synced
        assert manifest.files["fail.py"].synced_to_s3 is False

    async def test_sync_unsynced_to_s3_no_storage_service_returns_early(  # type: ignore[no-untyped-def]
        self, tmp_path
    ) -> None:
        """storage_service is None: no crash, returns early."""
        project_id = "proj-1"
        tenant_id = "tenant-1"
        workspace = tmp_path / project_id
        workspace.mkdir()
        (workspace / "file.py").write_text("code")

        service = WorkspaceSyncService(
            workspace_base=str(tmp_path),
            s3_backup_enabled=True,
            storage_service=None,
        )

        manifest = WorkspaceManifest.scan(str(workspace), project_id=project_id)

        # Should not crash
        await service._sync_unsynced_to_s3(manifest, workspace, project_id, tenant_id)
