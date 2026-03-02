#!/usr/bin/env python3
"""Migrate workspace directories from old to new default location.

Moves project workspace directories from /tmp/memstack-sandbox (old default)
to /var/lib/memstack/workspaces (new default), preserving all files and
creating/updating workspace manifests.

Usage:
    python scripts/migrate_workspaces.py
    python scripts/migrate_workspaces.py --dry-run
    python scripts/migrate_workspaces.py --source /custom/old/path --target /custom/new/path
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.infrastructure.agent.workspace.manifest import WorkspaceManifest

logger = logging.getLogger(__name__)

OLD_DEFAULT = "/tmp/memstack-sandbox"
NEW_DEFAULT = "/var/lib/memstack/workspaces"


def discover_workspaces(source: Path) -> list[str]:
    """Find project workspace directories in the source path.

    Args:
        source: Base directory to scan.

    Returns:
        List of project IDs (subdirectory names).
    """
    if not source.exists():
        return []
    return [
        entry.name
        for entry in source.iterdir()
        if entry.is_dir() and not entry.name.startswith(".")
    ]


def migrate_workspace(
    project_id: str,
    source: Path,
    target: Path,
    *,
    dry_run: bool = False,
) -> bool:
    """Migrate a single project workspace.

    Args:
        project_id: Project ID (directory name).
        source: Source base directory.
        target: Target base directory.
        dry_run: If True, only log what would happen.

    Returns:
        True if migration succeeded (or would succeed in dry-run).
    """
    src_path = source / project_id
    dst_path = target / project_id

    if not src_path.exists():
        logger.warning("Source workspace does not exist: %s", src_path)
        return False

    if dst_path.exists():
        target_files = list(dst_path.rglob("*"))
        if target_files:
            logger.warning(
                "Target already exists with %d files: %s (skipping)",
                len(target_files),
                dst_path,
            )
            return False
        logger.info("Target exists but is empty, will overwrite: %s", dst_path)

    if dry_run:
        file_count = sum(1 for f in src_path.rglob("*") if f.is_file())
        total_size = sum(f.stat().st_size for f in src_path.rglob("*") if f.is_file())
        logger.info(
            "[DRY RUN] Would migrate %s -> %s (%d files, %.1f MB)",
            src_path,
            dst_path,
            file_count,
            total_size / (1024 * 1024),
        )
        return True

    # Create target directory
    _ = dst_path.mkdir(parents=True, exist_ok=True)

    # Copy files preserving metadata
    try:
        _ = shutil.copytree(src_path, dst_path, dirs_exist_ok=True)
    except OSError:
        logger.exception("Failed to copy %s -> %s", src_path, dst_path)
        return False

    # Create/update workspace manifest
    try:
        manifest = WorkspaceManifest.scan(dst_path, project_id=project_id)
        manifest.save(dst_path)
        logger.info(
            "Created manifest for %s (%d files tracked)",
            project_id,
            len(manifest.files),
        )
    except OSError:
        logger.warning(
            "Failed to create manifest for %s (files were copied successfully)",
            project_id,
            exc_info=True,
        )

    logger.info("Migrated workspace: %s -> %s", src_path, dst_path)
    return True


def main() -> None:
    """Entry point for workspace migration."""
    parser = argparse.ArgumentParser(
        description="Migrate workspace directories to new default location."
    )
    _ = parser.add_argument(
        "--source",
        type=str,
        default=OLD_DEFAULT,
        help=f"Source directory (default: {OLD_DEFAULT})",
    )
    _ = parser.add_argument(
        "--target",
        type=str,
        default=NEW_DEFAULT,
        help=f"Target directory (default: {NEW_DEFAULT})",
    )
    _ = parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without making changes",
    )
    _ = parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable debug logging",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    source = Path(args.source)
    target = Path(args.target)

    if not source.exists():
        logger.info("Source directory does not exist: %s (nothing to migrate)", source)
        return

    workspaces = discover_workspaces(source)
    if not workspaces:
        logger.info("No workspaces found in %s", source)
        return

    logger.info(
        "Found %d workspace(s) in %s%s",
        len(workspaces),
        source,
        " (dry run)" if args.dry_run else "",
    )

    # Ensure target base exists
    if not args.dry_run:
        target.mkdir(parents=True, exist_ok=True)

    succeeded = 0
    failed = 0
    for project_id in sorted(workspaces):
        if migrate_workspace(project_id, source, target, dry_run=args.dry_run):
            succeeded += 1
        else:
            failed += 1

    logger.info(
        "Migration complete: %d succeeded, %d failed, %d total",
        succeeded,
        failed,
        len(workspaces),
    )

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
