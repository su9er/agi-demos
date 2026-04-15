from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FixtureCase = dict[str, Any]

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[5]
    / "shared"
    / "fixtures"
    / "canvas-native-block-fixtures.json"
)


@lru_cache(maxsize=1)
def load_native_block_fixture_corpus() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def iter_native_block_contract_cases(*, target: str | None = None) -> list[FixtureCase]:
    cases: list[FixtureCase] = []
    for case in load_native_block_fixture_corpus()["cases"]:
        targets = case.get("targets", [])
        if target is not None and target not in targets:
            continue
        cases.append(case)
    return cases


def serialize_native_block_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, separators=(",", ":"))
