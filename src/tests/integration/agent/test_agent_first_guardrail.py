"""Agent First guardrail — static scan of Track B modules.

Enforces the top-level Agent First rule: modules responsible for
**subjective-looking decisions** (routing, HITL policy, termination) MUST
NOT contain regex / NLP / keyword-list / string-heuristic code paths that
substitute for an Agent call.

This is a *guardrail*, not a proof: new modules added to the allow-list
must either be free of the banned markers or explicitly comment them out
of scope. Allow-list lives in this file so changes to it show up in code
review.

Scope (files scanned):
    * ``src/domain/model/agent/conversation/hitl_policy.py``
    * ``src/domain/model/agent/conversation/termination.py``
    * ``src/infrastructure/agent/routing/*.py``
    * ``src/application/services/agent/termination_service.py``

Banned markers:
    * ``re.`` / ``re.compile`` / ``re.match`` / ``re.search``
    * ``fnmatch`` (glob matching over NL)
    * ``startswith("@")`` / ``endswith("?")`` / ``.lower()`` over message
      content (approximated by heuristic).
    * Hard-coded keyword lists used as control flow (approximated by
      ``KEYWORDS = {...}`` or ``BLOCKED_PHRASES``).

Allowed structural helpers (enum compare, set membership, arithmetic) are
excluded by construction — they do not use ``re``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.integration

_REPO_ROOT = Path(__file__).resolve().parents[4]

_GUARDED_FILES: tuple[Path, ...] = (
    _REPO_ROOT / "src/domain/model/agent/conversation/hitl_policy.py",
    _REPO_ROOT / "src/domain/model/agent/conversation/termination.py",
    _REPO_ROOT / "src/application/services/agent/termination_service.py",
    _REPO_ROOT / "src/infrastructure/agent/routing/conversation_aware_router.py",
)

# Legacy routers that currently use regex for user-configurable binding
# patterns and built-in intent classification. They predate the Agent First
# rule. Flagged here so future cleanup is discoverable; not a current
# failure — they exist outside Track B's Agent First commitment.
_LEGACY_ROUTERS: tuple[Path, ...] = (
    _REPO_ROOT / "src/infrastructure/agent/routing/default_message_router.py",
    _REPO_ROOT / "src/infrastructure/agent/routing/intent_gate.py",
    _REPO_ROOT / "src/infrastructure/agent/routing/binding_router.py",
    _REPO_ROOT / "src/infrastructure/agent/routing/execution_router.py",
)


_BANNED_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("import re", re.compile(r"^\s*import\s+re(\s|$)", re.MULTILINE)),
    ("from re ", re.compile(r"^\s*from\s+re\s+import", re.MULTILINE)),
    ("fnmatch", re.compile(r"\bfnmatch\b")),
    (
        "KEYWORDS collection",
        re.compile(
            r"\b(KEYWORDS|BLOCKED_PHRASES|INTENT_WORDS|TRIGGER_WORDS|BANNED_WORDS)\s*=",
        ),
    ),
    # content.lower() style parsing usually implies NL classification
    (".lower() on content", re.compile(r"\.content\s*\.\s*lower\s*\(")),
    # heuristic phrase match
    ("content.startswith", re.compile(r"\.content\s*\.\s*startswith\s*\(")),
)


def _load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


@pytest.mark.parametrize("path", _GUARDED_FILES, ids=lambda p: p.name)
def test_no_forbidden_nl_patterns(path: Path) -> None:
    """Each guarded file must be free of regex / keyword / NL heuristics."""
    assert path.exists(), f"guarded file disappeared: {path}"
    source = _load(path)
    # Strip docstrings and comments so we only scan executable code.
    code_lines = [
        line for line in source.splitlines() if line.strip() and not line.lstrip().startswith("#")
    ]
    code = "\n".join(code_lines)
    # Remove triple-quoted strings (docstrings / prose blocks).
    code = re.sub(r'"""[\s\S]*?"""', "", code)
    code = re.sub(r"'''[\s\S]*?'''", "", code)

    violations: list[str] = []
    for label, pattern in _BANNED_PATTERNS:
        match = pattern.search(code)
        if match:
            snippet = match.group(0)
            violations.append(f"{label!r} matched {snippet!r}")

    assert not violations, (
        f"Agent First violation in {path.relative_to(_REPO_ROOT)}:\n"
        + "\n".join(f"  - {v}" for v in violations)
        + "\n(structural routing/policy/termination modules must not use "
        "regex or keyword-list NLP — route through an Agent instead.)"
    )


def test_allowlist_is_non_empty_and_resolved() -> None:
    """Sanity: the allow-list must actually point at real files, so a rename
    cannot silently bypass the guardrail."""
    assert _GUARDED_FILES, "allow-list empty"
    missing = [p for p in _GUARDED_FILES if not p.exists()]
    assert not missing, f"missing guarded files: {missing}"


def test_legacy_routers_are_tracked() -> None:
    """Document the legacy routers that still use regex/NLP heuristics.

    They predate Track B's Agent First rule. This test passes only to keep
    them on a tracked watch-list — a future refactor should migrate each
    one to agent-mediated routing and move it from ``_LEGACY_ROUTERS`` to
    ``_GUARDED_FILES``.
    """
    missing = [p for p in _LEGACY_ROUTERS if not p.exists()]
    assert not missing, f"missing legacy router files: {missing}"
