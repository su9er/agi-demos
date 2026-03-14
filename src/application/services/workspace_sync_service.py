"""Workspace sync service for persisting workspace state across sandbox lifecycles.

Implements Option B (Post-Execution Scan) from the architecture doc:
scans workspace directory, updates manifest, and optionally syncs to S3.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.domain.ports.services.storage_service_port import StorageServicePort

from src.infrastructure.agent.workspace.manifest import WorkspaceManifest

logger = logging.getLogger(__name__)


class WorkspaceSyncService:
    """Manages workspace persistence and sync across sandbox lifecycle events.

    Responsibilities:
    - Scan workspace after tool execution to detect new/changed files
    - Update WorkspaceManifest with current state
    - Optionally sync unsynced files to S3 for disaster recovery
    - Restore workspace state after sandbox recreation

    Attributes:
        _workspace_base: Base directory for all project workspaces.
        _s3_backup_enabled: Whether S3 backup is active.
        _s3_bucket: S3 bucket for workspace backups.
        _storage_service: Storage backend for S3 upload operations (optional).
    """

    def __init__(
        self,
        workspace_base: str,
        s3_backup_enabled: bool = False,
        s3_bucket: str = "memstack-workspaces",
        storage_service: StorageServicePort | None = None,
    ) -> None:
        self._workspace_base = workspace_base
        self._s3_backup_enabled = s3_backup_enabled
        self._s3_bucket = s3_bucket
        self._storage_service = storage_service

    def _workspace_path(self, project_id: str) -> Path:
        """Resolve the workspace directory path for a project."""
        return Path(self._workspace_base) / project_id

    async def pre_destroy_sync(
        self,
        sandbox_id: str,
        project_id: str,
        tenant_id: str = "",
    ) -> WorkspaceManifest:
        """Capture workspace state before sandbox destruction.

        Scans the workspace, updates the manifest with current files,
        saves it to disk, and optionally syncs unsynced files to S3.

        If the workspace directory does not exist on the host (e.g. the
        workspace_base points to a container-internal path), an empty
        manifest is returned without attempting any disk writes.

        Args:
            sandbox_id: ID of the sandbox being destroyed.
            project_id: Project that owns the workspace.
            tenant_id: Tenant for S3 key scoping.

        Returns:
            The updated WorkspaceManifest.
        """
        workspace = self._workspace_path(project_id)

        # If the workspace directory does not exist on this host, there is
        # nothing to scan or persist.  Return an empty manifest so the
        # caller (e.g. SandboxIdleReaper) can proceed with termination
        # without hitting OSError on read-only / non-existent paths.
        if not workspace.exists():
            logger.debug(
                "WorkspaceSyncService.pre_destroy_sync: workspace %s does not exist, "
                "skipping sync for sandbox %s (project %s)",
                workspace,
                sandbox_id,
                project_id,
            )
            manifest = WorkspaceManifest.create(
                workspace, project_id=project_id, tenant_id=tenant_id
            )
            manifest.update_sandbox_id(sandbox_id)
            return manifest

        manifest = WorkspaceManifest.scan(workspace, project_id=project_id, tenant_id=tenant_id)
        manifest.update_sandbox_id(sandbox_id)
        manifest.save(workspace)

        if self._s3_backup_enabled and self._storage_service is not None:
            await self._sync_unsynced_to_s3(manifest, workspace, project_id, tenant_id)

        logger.info(
            "WorkspaceSyncService.pre_destroy_sync: saved manifest for sandbox %s "
            "(project %s, %d files, %d unsynced)",
            sandbox_id,
            project_id,
            len(manifest.files),
            len(manifest.unsynced_files()),
        )
        return manifest

    async def post_create_restore(
        self,
        sandbox_id: str,
        project_id: str,
        tenant_id: str = "",
    ) -> WorkspaceManifest:
        """Restore/initialize workspace state after sandbox creation.

        Loads existing manifest or creates a new one. Records the new
        sandbox ID. If S3 backup is enabled and files are missing from
        disk, this is logged (future: download from S3).

        Args:
            sandbox_id: ID of the newly created sandbox.
            project_id: Project that owns the workspace.
            tenant_id: Tenant for S3 key scoping.

        Returns:
            The loaded or newly created WorkspaceManifest.
        """
        workspace = self._workspace_path(project_id)
        manifest = WorkspaceManifest.load(workspace)
        if manifest is None:
            manifest = WorkspaceManifest.create(
                workspace, project_id=project_id, tenant_id=tenant_id
            )

        manifest.update_sandbox_id(sandbox_id)
        manifest.save(workspace)

        missing = manifest.files_missing_on_disk(workspace)
        if missing:
            logger.warning(
                "WorkspaceSyncService.post_create_restore: %d files in manifest "
                "missing from disk for project %s",
                len(missing),
                project_id,
            )

        logger.info(
            "WorkspaceSyncService.post_create_restore: manifest ready for sandbox %s "
            "(project %s, %d files)",
            sandbox_id,
            project_id,
            len(manifest.files),
        )
        return manifest

    async def post_execution_scan(
        self,
        project_id: str,
        tenant_id: str = "",
    ) -> list[str]:
        """Scan workspace for new/changed files after tool execution.

        Updates the manifest and returns paths of changed files.

        Args:
            project_id: Project that owns the workspace.
            tenant_id: Tenant for S3 key scoping.

        Returns:
            List of relative paths that are new or changed since last scan.
        """
        workspace = self._workspace_path(project_id)
        if not workspace.exists():
            return []

        old_manifest = WorkspaceManifest.load(workspace)
        old_files = old_manifest.files if old_manifest else {}

        new_manifest = WorkspaceManifest.scan(workspace, project_id=project_id, tenant_id=tenant_id)
        new_manifest.save(workspace)

        changed: list[str] = []
        for rel_path, entry in new_manifest.files.items():
            old_entry = old_files.get(rel_path)
            if old_entry is None or old_entry.sha256 != entry.sha256:
                changed.append(rel_path)

        if changed:
            logger.info(
                "WorkspaceSyncService.post_execution_scan: %d new/changed files for project %s",
                len(changed),
                project_id,
            )
        return changed

    async def _sync_unsynced_to_s3(
        self,
        manifest: WorkspaceManifest,
        workspace: Path,
        project_id: str,
        tenant_id: str,
    ) -> None:
        """Upload unsynced files from the manifest to S3.

        Args:
            manifest: Current workspace manifest.
            workspace: Absolute workspace directory path.
            project_id: Project ID for S3 key scoping.
            tenant_id: Tenant ID for S3 key scoping.
        """
        unsynced = manifest.unsynced_files()
        if not unsynced:
            return

        if self._storage_service is None:
            logger.warning("S3 backup enabled but no storage service configured; skipping sync")
            return

        synced_count = 0
        for entry in unsynced:
            file_path = workspace / entry.relative_path
            if not file_path.exists():
                logger.warning("Skipping sync for missing file: %s", entry.relative_path)
                continue

            try:
                content = file_path.read_bytes()
                s3_key = f"workspaces/{tenant_id}/{project_id}/{entry.relative_path}"
                await self._storage_service.upload_file(
                    file_content=content,
                    object_key=s3_key,
                    content_type="application/octet-stream",
                )
                entry.mark_synced(s3_key)
                synced_count += 1
            except Exception:
                logger.warning(
                    "Failed to sync file %s to S3",
                    entry.relative_path,
                    exc_info=True,
                )

        # Save updated sync state
        manifest.save(workspace)
        logger.info(
            "Synced %d/%d files to S3 for project %s",
            synced_count,
            len(unsynced),
            project_id,
        )
