"""Unit tests for WorkspaceManifest and FileEntry."""

from __future__ import annotations

import hashlib
import json

import pytest

from src.infrastructure.agent.workspace.manifest import (
    MANIFEST_FILENAME,
    MANIFEST_VERSION,
    FileEntry,
    WorkspaceManifest,
    _compute_sha256,
)

# ---------------------------------------------------------------------------
# FileEntry
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFileEntry:
    """Tests for the FileEntry dataclass."""

    def test_creation_with_required_fields(self) -> None:
        entry = FileEntry(
            relative_path="src/main.py",
            size=1024,
            sha256="abc123",
            created_at="2026-01-01T00:00:00+00:00",
        )
        assert entry.relative_path == "src/main.py"
        assert entry.size == 1024
        assert entry.sha256 == "abc123"
        assert entry.created_at == "2026-01-01T00:00:00+00:00"
        assert entry.synced_to_s3 is False
        assert entry.s3_key is None

    def test_mark_synced(self) -> None:
        entry = FileEntry(
            relative_path="data.json",
            size=512,
            sha256="def456",
            created_at="2026-01-01T00:00:00+00:00",
        )
        entry.mark_synced("s3://bucket/data.json")
        assert entry.synced_to_s3 is True
        assert entry.s3_key == "s3://bucket/data.json"

    def test_creation_with_all_fields(self) -> None:
        entry = FileEntry(
            relative_path="doc.txt",
            size=256,
            sha256="ghi789",
            created_at="2026-02-01T00:00:00+00:00",
            synced_to_s3=True,
            s3_key="s3://bucket/doc.txt",
        )
        assert entry.synced_to_s3 is True
        assert entry.s3_key == "s3://bucket/doc.txt"


# ---------------------------------------------------------------------------
# _compute_sha256
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestComputeSha256:
    """Tests for the _compute_sha256 helper function."""

    def test_known_content(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """SHA-256 of known content matches expected digest."""
        content = b"hello world"
        expected = hashlib.sha256(content).hexdigest()
        file_path = tmp_path / "test.txt"
        file_path.write_bytes(content)
        assert _compute_sha256(file_path) == expected

    def test_empty_file(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """SHA-256 of empty file matches expected digest."""
        expected = hashlib.sha256(b"").hexdigest()
        file_path = tmp_path / "empty.txt"
        file_path.write_bytes(b"")
        assert _compute_sha256(file_path) == expected

    def test_large_file(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """SHA-256 of a file larger than the read chunk size."""
        content = b"x" * (65536 * 3 + 42)  # 3+ chunks
        expected = hashlib.sha256(content).hexdigest()
        file_path = tmp_path / "large.bin"
        file_path.write_bytes(content)
        assert _compute_sha256(file_path) == expected


# ---------------------------------------------------------------------------
# WorkspaceManifest — creation
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWorkspaceManifestCreation:
    """Tests for WorkspaceManifest construction and factory methods."""

    def test_default_values(self) -> None:
        manifest = WorkspaceManifest()
        assert manifest.version == MANIFEST_VERSION
        assert manifest.project_id == ""
        assert manifest.tenant_id == ""
        assert manifest.files == {}
        assert manifest.runtime_dependencies == []
        assert manifest.last_sandbox_id is None
        assert manifest.last_sync_at is None

    def test_create_factory(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        manifest = WorkspaceManifest.create(
            str(tmp_path), project_id="proj-1", tenant_id="tenant-1"
        )
        assert manifest.project_id == "proj-1"
        assert manifest.tenant_id == "tenant-1"
        assert manifest.files == {}

    def test_update_sandbox_id(self) -> None:
        manifest = WorkspaceManifest()
        manifest.update_sandbox_id("sandbox-42")
        assert manifest.last_sandbox_id == "sandbox-42"

    def test_add_runtime_dependency(self) -> None:
        manifest = WorkspaceManifest()
        manifest.add_runtime_dependency("numpy")
        manifest.add_runtime_dependency("pandas")
        manifest.add_runtime_dependency("numpy")  # duplicate
        assert manifest.runtime_dependencies == ["numpy", "pandas"]


# ---------------------------------------------------------------------------
# WorkspaceManifest — queries
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWorkspaceManifestQueries:
    """Tests for query methods on WorkspaceManifest."""

    def test_unsynced_files(self) -> None:
        manifest = WorkspaceManifest()
        synced = FileEntry(
            relative_path="a.py",
            size=10,
            sha256="aaa",
            created_at="2026-01-01T00:00:00+00:00",
            synced_to_s3=True,
            s3_key="s3://a.py",
        )
        unsynced = FileEntry(
            relative_path="b.py",
            size=20,
            sha256="bbb",
            created_at="2026-01-01T00:00:00+00:00",
        )
        manifest.files = {"a.py": synced, "b.py": unsynced}
        result = manifest.unsynced_files()
        assert len(result) == 1
        assert result[0].relative_path == "b.py"

    def test_files_missing_on_disk(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """Detect manifest entries whose files are absent on disk."""
        (tmp_path / "existing.py").write_text("x")
        manifest = WorkspaceManifest()
        manifest.files = {
            "existing.py": FileEntry(
                relative_path="existing.py",
                size=1,
                sha256="x",
                created_at="2026-01-01T00:00:00+00:00",
            ),
            "missing.py": FileEntry(
                relative_path="missing.py",
                size=1,
                sha256="y",
                created_at="2026-01-01T00:00:00+00:00",
            ),
        }
        missing = manifest.files_missing_on_disk(str(tmp_path))
        assert len(missing) == 1
        assert missing[0].relative_path == "missing.py"


# ---------------------------------------------------------------------------
# WorkspaceManifest — scan
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWorkspaceManifestScan:
    """Tests for WorkspaceManifest.scan() directory scanning."""

    def test_scan_empty_directory(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        manifest = WorkspaceManifest.scan(str(tmp_path), project_id="p1")
        assert manifest.project_id == "p1"
        assert manifest.files == {}

    def test_scan_with_files(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        (tmp_path / "hello.txt").write_text("hello")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "world.txt").write_text("world")
        manifest = WorkspaceManifest.scan(str(tmp_path), project_id="p2")
        assert "hello.txt" in manifest.files
        assert "sub/world.txt" in manifest.files
        assert manifest.files["hello.txt"].size == 5
        assert manifest.files["sub/world.txt"].size == 5

    def test_scan_skips_pycache(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.cpython-312.pyc").write_bytes(b"\x00")
        (tmp_path / "real.py").write_text("x = 1")
        manifest = WorkspaceManifest.scan(str(tmp_path))
        assert "real.py" in manifest.files
        assert all("__pycache__" not in p for p in manifest.files)

    def test_scan_skips_manifest_file(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        memstack_dir = tmp_path / ".memstack"
        memstack_dir.mkdir()
        (memstack_dir / "workspace-manifest.json").write_text("{}")
        (tmp_path / "code.py").write_text("pass")
        manifest = WorkspaceManifest.scan(str(tmp_path))
        assert MANIFEST_FILENAME not in manifest.files
        assert "code.py" in manifest.files

    def test_scan_preserves_sync_state_for_unchanged_files(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        """If a file hash hasn't changed, preserve the synced_to_s3 state."""
        content = "stable content"
        (tmp_path / "stable.txt").write_text(content)

        # First scan
        m1 = WorkspaceManifest.scan(str(tmp_path), project_id="p")
        m1.files["stable.txt"].mark_synced("s3://stable.txt")
        m1.save(str(tmp_path))

        # Second scan should preserve sync state
        m2 = WorkspaceManifest.scan(str(tmp_path), project_id="p")
        assert m2.files["stable.txt"].synced_to_s3 is True
        assert m2.files["stable.txt"].s3_key == "s3://stable.txt"

    def test_scan_nonexistent_directory(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        nonexistent = tmp_path / "does_not_exist"
        manifest = WorkspaceManifest.scan(str(nonexistent))
        assert manifest.files == {}

    def test_scan_computes_correct_sha256(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        content = b"checksum test"
        expected = hashlib.sha256(content).hexdigest()
        (tmp_path / "check.txt").write_bytes(content)
        manifest = WorkspaceManifest.scan(str(tmp_path))
        assert manifest.files["check.txt"].sha256 == expected


# ---------------------------------------------------------------------------
# WorkspaceManifest — save / load roundtrip
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestWorkspaceManifestPersistence:
    """Tests for save() and load() roundtrip."""

    def test_save_and_load_roundtrip(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        original = WorkspaceManifest(
            project_id="proj-rt",
            tenant_id="tenant-rt",
            last_sandbox_id="sb-1",
            runtime_dependencies=["requests", "numpy"],
        )
        original.files["main.py"] = FileEntry(
            relative_path="main.py",
            size=100,
            sha256="aabbcc",
            created_at="2026-01-01T00:00:00+00:00",
            synced_to_s3=True,
            s3_key="s3://main.py",
        )
        original.save(str(tmp_path))

        loaded = WorkspaceManifest.load(str(tmp_path))
        assert loaded is not None
        assert loaded.project_id == "proj-rt"
        assert loaded.tenant_id == "tenant-rt"
        assert loaded.last_sandbox_id == "sb-1"
        assert loaded.runtime_dependencies == ["requests", "numpy"]
        assert "main.py" in loaded.files
        assert loaded.files["main.py"].sha256 == "aabbcc"
        assert loaded.files["main.py"].synced_to_s3 is True
        assert loaded.files["main.py"].s3_key == "s3://main.py"

    def test_load_nonexistent_returns_none(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        result = WorkspaceManifest.load(str(tmp_path))
        assert result is None

    def test_load_corrupt_json_returns_none(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        manifest_dir = tmp_path / ".memstack"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "workspace-manifest.json").write_text("not valid json{{{")
        result = WorkspaceManifest.load(str(tmp_path))
        assert result is None

    def test_save_creates_memstack_directory(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        manifest = WorkspaceManifest(project_id="dir-test")
        manifest.save(str(tmp_path))
        assert (tmp_path / ".memstack").is_dir()
        assert (tmp_path / ".memstack" / "workspace-manifest.json").exists()

    def test_save_produces_valid_json(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        manifest = WorkspaceManifest(project_id="json-test")
        manifest.files["a.txt"] = FileEntry(
            relative_path="a.txt",
            size=10,
            sha256="aaaa",
            created_at="2026-01-01T00:00:00+00:00",
        )
        manifest.save(str(tmp_path))

        raw = (tmp_path / ".memstack" / "workspace-manifest.json").read_text()
        data = json.loads(raw)
        assert data["project_id"] == "json-test"
        assert "a.txt" in data["files"]
        assert data["files"]["a.txt"]["sha256"] == "aaaa"

    def test_version_preserved_through_roundtrip(self, tmp_path) -> None:  # type: ignore[no-untyped-def]
        manifest = WorkspaceManifest(version=99, project_id="v-test")
        manifest.save(str(tmp_path))
        loaded = WorkspaceManifest.load(str(tmp_path))
        assert loaded is not None
        assert loaded.version == 99
