"""
Skill revision hashing.

P2-4 introduces a curated skill registry keyed by ``revision_hash`` — a
deterministic SHA-256 of the canonical-JSON representation of a skill
payload. The same logical skill (same name / tools / template / triggers)
always hashes identically, which gives us DB-level deduplication via the
``uq_curated_skills_hash`` constraint.

Only the intrinsic, human-authored content is hashed; volatile fields such
as ``id``, ``tenant_id``, ``created_at``, ``success_count``, ``failure_count``
and timestamps are excluded so that forking, renaming or usage tracking does
not perturb the hash.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

_VOLATILE_FIELDS: frozenset[str] = frozenset(
    {
        "id",
        "tenant_id",
        "project_id",
        "created_at",
        "updated_at",
        "approved_at",
        "reviewed_at",
        "success_count",
        "failure_count",
        "success_rate",
        "usage_count",
        "status",
        "current_version",
        "version_label",
        "parent_curated_id",
        "revision_hash",
        "is_system_skill",
    }
)

_CANONICAL_FIELDS: tuple[str, ...] = (
    "name",
    "description",
    "trigger_type",
    "trigger_patterns",
    "tools",
    "prompt_template",
    "full_content",
    "metadata",
    "scope",
    "semver",
)


def canonical_skill_dict(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic subset of ``payload`` used for hashing."""
    result: dict[str, Any] = {}
    for field in _CANONICAL_FIELDS:
        if field in payload and field not in _VOLATILE_FIELDS:
            result[field] = payload[field]
    return result


def canonical_json(payload: dict[str, Any]) -> str:
    """Serialise ``payload`` with sorted keys and stable separators."""
    canonical = canonical_skill_dict(payload)
    return json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def revision_hash_of(payload: dict[str, Any]) -> str:
    """Return the SHA-256 hex digest of the canonical payload."""
    return hashlib.sha256(canonical_json(payload).encode("utf-8")).hexdigest()
