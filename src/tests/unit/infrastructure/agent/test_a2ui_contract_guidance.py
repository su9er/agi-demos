from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[5]
FIXTURE_PATH = REPO_ROOT / "shared/fixtures/a2ui-contract-fixtures.json"
PROMPT_PATH = REPO_ROOT / "src/infrastructure/agent/prompts/system/default.txt"
CANVAS_TOOLS_PATH = REPO_ROOT / "src/infrastructure/agent/canvas/tools.py"


def _load_contract() -> dict[str, object]:
    return json.loads(FIXTURE_PATH.read_text())


def _serialize_records(records: list[dict[str, object]]) -> str:
    return "\n".join(json.dumps(record, separators=(",", ":")) for record in records)


def _find_case(contract: dict[str, object], case_id: str) -> dict[str, object]:
    cases = contract["cases"]
    assert isinstance(cases, list)
    for case in cases:
        if isinstance(case, dict) and case.get("id") == case_id:
            return case
    raise AssertionError(f"Missing contract case: {case_id}")


def test_default_prompt_a2ui_guidance_matches_contract_fixture() -> None:
    contract = _load_contract()
    prompt_text = PROMPT_PATH.read_text()

    guidance = contract["promptGuidance"]
    assert isinstance(guidance, dict)
    components = guidance["supportedComponents"]
    assert isinstance(components, list)
    expected_component_line = "Available A2UI components: " + ", ".join(
        f"`{component}`" for component in components
    ) + "."
    assert expected_component_line in prompt_text
    assert "`List`" not in expected_component_line

    example_case = _find_case(contract, str(guidance["exampleCaseId"]))
    example_records = example_case["records"]
    assert isinstance(example_records, list)
    assert _serialize_records(example_records) in prompt_text

    assert '{"Text":{"text":{"literal":"hello"}}}' not in prompt_text
    assert '{"Text":{"text":{"literalString":"hello"}}}' in prompt_text
    assert (
        '{"dataModelUpdate":{"surfaceId":"<id>","path":"/","contents":[{"key":"status",'
        '"valueString":"ok"}]}}'
    ) in prompt_text
    assert "canonical data binding as its own JSONL line after `surfaceUpdate`" in prompt_text
    assert (
        "Nested `surfaceUpdate.dataModelUpdate` may be accepted and canonicalized for "
        "compatibility with legacy payloads, but it is not canonical authoring."
    ) in prompt_text
    assert (
        "Tabs `tabItems[].child` and Modal `entryPointChild` / `contentChild` must "
        "reference actual component IDs defined in the same surface."
    ) in prompt_text
    assert "update the same surface to reflect the confirmed/completed state" in prompt_text
    assert "MUST update the same surface with `canvas_update`" in prompt_text
    assert "Do not leave the stale pre-submit form visible" in prompt_text


def test_canvas_tool_guidance_stays_within_contract_tiers() -> None:
    contract = _load_contract()
    tool_text = CANVAS_TOOLS_PATH.read_text()

    guidance = contract["promptGuidance"]
    assert isinstance(guidance, dict)
    components = guidance["supportedComponents"]
    assert isinstance(components, list)
    for component in components:
        assert component in tool_text

    aliases = guidance["componentAliases"]
    assert isinstance(aliases, dict)
    for legacy, canonical in aliases.items():
        assert f"{legacy} -> {canonical}" in tool_text

    renderer_only = guidance["rendererOnlyCompatibility"]
    assert isinstance(renderer_only, dict)
    assert set(renderer_only).isdisjoint(set(components))
    for component in renderer_only:
        if component == "List":
            assert "must not be authored" in tool_text

    assert (
        "Nested surfaceUpdate.dataModelUpdate is accepted and canonicalized for "
        "compatibility, but it is not canonical authoring; emit dataModelUpdate as "
        "its own JSON line instead."
    ) in tool_text
    assert (
        "Compatibility aliases Checkbox -> CheckBox and Select -> MultipleChoice are "
        "accepted and canonicalized automatically, but do not author them by default."
    ) in tool_text
    assert (
        "Tabs.tabItems[].child and Modal.entryPointChild/contentChild must reference "
        "component ids defined in the same surface."
    ) in tool_text
    assert "update the same surface" in tool_text
    assert "MUST call " in tool_text
    assert "`canvas_update` on the same block_id" in tool_text
    assert "pre-submit form visible" in tool_text
