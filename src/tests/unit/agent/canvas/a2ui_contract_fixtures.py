from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

FixtureCase = dict[str, Any]

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[5] / "shared" / "fixtures" / "a2ui-contract-fixtures.json"
)


@lru_cache(maxsize=1)
def load_a2ui_contract_fixture_corpus() -> dict[str, Any]:
    return json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def get_a2ui_contract_case(case_id: str) -> FixtureCase:
    for case in load_a2ui_contract_fixture_corpus()["cases"]:
        if case["id"] == case_id:
            return case
    msg = f"Unknown A2UI contract fixture case: {case_id}"
    raise KeyError(msg)


def iter_backend_contract_cases(*, tier: str | None = None) -> list[FixtureCase]:
    cases: list[FixtureCase] = []
    for case in load_a2ui_contract_fixture_corpus()["cases"]:
        if "backend" not in case.get("targets", []):
            continue
        if tier is not None and case.get("tier") != tier:
            continue
        if not isinstance(case.get("records"), list):
            continue
        cases.append(case)
    return cases


def contract_case_jsonl(case: FixtureCase) -> str:
    records = case.get("records")
    if not isinstance(records, list):
        msg = f"A2UI contract case {case.get('id')} does not define records."
        raise ValueError(msg)
    return "\n".join(json.dumps(record) for record in records)
