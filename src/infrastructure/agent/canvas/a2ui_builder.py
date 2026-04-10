"""A2UI JSONL message builder.

Constructs native A2UI ServerToClientMessage envelopes for the CopilotKit
``@copilotkit/a2ui-renderer`` frontend.  The backend agent emits these messages
as the ``content`` field of an ``a2ui_surface`` CanvasBlock, so the frontend
can call ``processMessages()`` directly.

A2UI message format reference (Google A2UI v0.8):
- ``surfaceUpdate``: ``{"surfaceUpdate":{"surfaceId":"...","components":[...]}}``
- ``dataModelUpdate``: ``{"dataModelUpdate":{"surfaceId":"...","path":"...","contents":[...]}}``
- ``beginRendering``: ``{"beginRendering":{"surfaceId":"...","root":"...","styles":{...}}}``
- ``deleteSurface``: ``{"deleteSurface":{"surfaceId":"..."}}``
"""

from __future__ import annotations

import json
import uuid
from typing import Any


def _new_id() -> str:
    """Generate a compact component ID."""
    return uuid.uuid4().hex[:12]


def _str_val(s: str) -> dict[str, str]:
    """Wrap a string as an A2UI StringValue literal."""
    return {"literal": s}


SURFACE_KEYS = (
    "beginRendering",
    "begin_rendering",
    "surfaceUpdate",
    "surface_update",
    "dataModelUpdate",
    "data_model_update",
    "deleteSurface",
    "delete_surface",
)
TYPED_SURFACE_TYPES = set(SURFACE_KEYS)
SUPPORTED_A2UI_COMPONENT_KEYS = frozenset(
    {"Text", "Button", "Card", "Column", "Row", "TextField", "Divider"}
)
INITIAL_A2UI_SURFACE_EXAMPLE = (
    '{"beginRendering":{"surfaceId":"<id>","root":"<root-component-id>"}}\n'
    '{"surfaceUpdate":{"surfaceId":"<id>","components":[{"id":"<root-component-id>",'
    '"component":{"Text":{"text":{"literal":"hello"}}}}]}}'
)


def _normalize_data_path(path_or_alias: str) -> str:
    """Normalize an A2UI data binding path."""
    stripped = path_or_alias.strip()
    if not stripped:
        return "/"
    if stripped.startswith("/"):
        return stripped
    return f"/{stripped.lstrip('/')}"


def _is_value_map(entry: object) -> bool:
    """Return True when an entry already matches A2UI ValueMap shape."""
    if not isinstance(entry, dict):
        return False
    return isinstance(entry.get("key"), str) and (
        len(entry) == 1
        or any(name in entry for name in ("valueString", "valueNumber", "valueBoolean", "valueMap"))
    )


def _to_value_map(key: str, value: object) -> dict[str, object]:
    """Convert a Python value into an A2UI ValueMap entry."""
    if value is None:
        return {"key": key}
    if isinstance(value, bool):
        return {"key": key, "valueBoolean": value}
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return {"key": key, "valueNumber": value}
    if isinstance(value, dict):
        return {
            "key": key,
            "valueMap": [
                _to_value_map(child_key, child_value) for child_key, child_value in value.items()
            ],
        }
    if isinstance(value, list):
        return {
            "key": key,
            "valueMap": [_to_value_map(str(index), item) for index, item in enumerate(value)],
        }
    return {"key": key, "valueString": str(value)}


def _normalize_data_model_contents(contents: object) -> list[dict[str, object]]:
    """Normalize plain objects into A2UI ValueMap entries."""
    if isinstance(contents, dict):
        return [_to_value_map(key, value) for key, value in contents.items()]
    if isinstance(contents, list):
        return [
            entry if _is_value_map(entry) else _to_value_map(str(index), entry)
            for index, entry in enumerate(contents)
        ]
    return [_to_value_map(".", contents)]


def _strip_markdown_code_fence(messages: str) -> str:
    """Strip a surrounding markdown code fence from a JSONL payload."""
    stripped = messages.strip()
    if not stripped.startswith("```"):
        return stripped
    lines = stripped.splitlines()
    if len(lines) < 3 or not lines[-1].strip().startswith("```"):
        return stripped
    return "\n".join(lines[1:-1]).strip()


def _coerce_message_dicts(raw: object) -> list[dict[str, object]]:
    """Coerce parsed JSON payloads into a list of envelope dictionaries."""
    if isinstance(raw, dict):
        messages = raw.get("messages")
        if isinstance(messages, list):
            return [entry for entry in messages if isinstance(entry, dict)]
        return [raw]
    if isinstance(raw, list):
        return [entry for entry in raw if isinstance(entry, dict)]
    return []


def _extract_json_objects(raw: str) -> list[str]:
    """Extract brace-balanced JSON objects from a string."""
    objects: list[str] = []
    start_index: int | None = None
    depth = 0
    in_string = False
    escape_next = False

    for index, char in enumerate(raw):
        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
            continue
        if char == "{":
            if depth == 0:
                start_index = index
            depth += 1
            continue
        if char != "}":
            continue
        depth -= 1
        if depth == 0 and start_index is not None:
            objects.append(raw[start_index : index + 1])
            start_index = None

    return objects


def _iter_message_dicts(messages: str) -> list[dict[str, object]]:
    """Parse A2UI message payloads into top-level envelope dictionaries."""
    stripped = _strip_markdown_code_fence(messages)
    if not stripped:
        return []

    try:
        return _coerce_message_dicts(json.loads(stripped))
    except json.JSONDecodeError:
        parsed_lines: list[dict[str, object]] = []
        for line in stripped.splitlines():
            candidate = line.strip()
            if not candidate or candidate.startswith("```"):
                continue
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            parsed_lines.extend(_coerce_message_dicts(parsed))
        if parsed_lines:
            return parsed_lines

        parsed_objects: list[dict[str, object]] = []
        for chunk in _extract_json_objects(stripped):
            try:
                parsed = json.loads(chunk)
            except json.JSONDecodeError:
                continue
            parsed_objects.extend(_coerce_message_dicts(parsed))
        return parsed_objects


def _surface_id_from_record(record: dict[str, object]) -> str | None:
    """Extract a surface ID from supported top-level A2UI envelope shapes."""
    for key in SURFACE_KEYS:
        payload = record.get(key)
        if isinstance(payload, dict):
            surface_id = payload.get("surfaceId") or payload.get("surface_id")
            if isinstance(surface_id, str) and surface_id:
                return surface_id

    envelope_type = record.get("type")
    payload = record.get("payload")
    if (
        isinstance(envelope_type, str)
        and envelope_type in TYPED_SURFACE_TYPES
        and isinstance(payload, dict)
    ):
        surface_id = payload.get("surfaceId") or payload.get("surface_id")
        if isinstance(surface_id, str) and surface_id:
            return surface_id

    return None


def _extract_envelope_payload(record: dict[str, object], *keys: str) -> dict[str, object] | None:
    """Return the payload for a direct or typed A2UI envelope."""
    for key in keys:
        payload = record.get(key)
        if isinstance(payload, dict):
            return payload

    envelope_type = record.get("type")
    payload = record.get("payload")
    if isinstance(envelope_type, str) and envelope_type in keys and isinstance(payload, dict):
        return payload
    return None


def _invalid_a2ui_payload(detail: str) -> str:
    """Build a correction-focused A2UI validation error message."""
    return (
        f"Invalid A2UI payload: {detail} "
        "Expected A2UI JSONL with beginRendering/surfaceUpdate envelopes, for example: "
        f"{INITIAL_A2UI_SURFACE_EXAMPLE}"
    )


def _flat_surface_payload_error(parsed_whole: object) -> str | None:
    """Return a targeted error for plain surface objects without A2UI envelopes."""
    if not isinstance(parsed_whole, dict):
        return None
    flat_surface_id = parsed_whole.get("surfaceId") or parsed_whole.get("surface_id")
    if not isinstance(flat_surface_id, str) or "components" not in parsed_whole:
        return None
    return _invalid_a2ui_payload(
        'received a plain {"surfaceId":"...","components":[...]} object. '
        "Wrap it in beginRendering and surfaceUpdate envelopes and include a root id."
    )


def _validate_begin_rendering_payload(payload: dict[str, object]) -> str | None:
    """Validate a beginRendering envelope payload."""
    surface_id = payload.get("surfaceId") or payload.get("surface_id")
    if not isinstance(surface_id, str) or not surface_id.strip():
        return _invalid_a2ui_payload("beginRendering.surfaceId must be a non-empty string.")

    root = payload.get("root")
    if not isinstance(root, str) or not root.strip():
        return _invalid_a2ui_payload("beginRendering.root must be a non-empty string.")
    return None


def _validate_surface_update_component(component: object, index: int) -> str | None:
    """Validate a single surfaceUpdate component entry."""
    if not isinstance(component, dict):
        return _invalid_a2ui_payload(f"surfaceUpdate.components[{index}] must be an object.")

    component_id = component.get("id")
    if not isinstance(component_id, str) or not component_id.strip():
        return _invalid_a2ui_payload(
            f"surfaceUpdate.components[{index}].id must be a non-empty string."
        )

    component_payload = component.get("component")
    if isinstance(component_payload, dict):
        component_keys = [key for key in component_payload if key in SUPPORTED_A2UI_COMPONENT_KEYS]
        allowed_keys = SUPPORTED_A2UI_COMPONENT_KEYS | {"style"}
        extra_keys = [key for key in component_payload if key not in allowed_keys]
        if extra_keys:
            error = _invalid_a2ui_payload(
                f"surfaceUpdate.components[{index}] contains unsupported component keys: "
                f"{sorted(extra_keys)}."
            )
        elif len(component_keys) != 1:
            error = _invalid_a2ui_payload(
                f"surfaceUpdate.components[{index}] must contain exactly one supported "
                f"component key: {sorted(SUPPORTED_A2UI_COMPONENT_KEYS)}."
            )
        else:
            error = None
    else:
        legacy_type = component.get("type")
        if isinstance(legacy_type, str) and legacy_type in SUPPORTED_A2UI_COMPONENT_KEYS:
            error = None
        else:
            error = _invalid_a2ui_payload(
                f"surfaceUpdate.components[{index}] must include a supported 'component' object "
                f"or legacy 'type' string: {sorted(SUPPORTED_A2UI_COMPONENT_KEYS)}."
            )
    return error


def _validate_surface_update_payload(
    payload: dict[str, object],
    *,
    require_initial_render: bool,
) -> str | None:
    """Validate a surfaceUpdate envelope payload."""
    if require_initial_render:
        surface_id = payload.get("surfaceId") or payload.get("surface_id")
        if not isinstance(surface_id, str) or not surface_id.strip():
            return _invalid_a2ui_payload(
                "surfaceUpdate.surfaceId must be a non-empty string for new surfaces."
            )

    components = payload.get("components")
    if not isinstance(components, list):
        return _invalid_a2ui_payload("surfaceUpdate.components must be an array.")

    for index, component in enumerate(components):
        if error := _validate_surface_update_component(component, index):
            return error
    return None


def _validate_a2ui_record(
    record: dict[str, object],
    *,
    require_initial_render: bool,
) -> tuple[bool, bool, bool, str | None]:
    """Validate a single parsed A2UI record and report which envelopes were seen."""
    saw_begin_rendering = False
    saw_surface_update = False
    saw_supported_envelope = False

    begin_rendering = _extract_envelope_payload(record, "beginRendering", "begin_rendering")
    if begin_rendering is not None:
        saw_supported_envelope = True
        saw_begin_rendering = True
        if error := _validate_begin_rendering_payload(begin_rendering):
            return saw_begin_rendering, saw_surface_update, saw_supported_envelope, error

    surface_update = _extract_envelope_payload(record, "surfaceUpdate", "surface_update")
    if surface_update is not None:
        saw_supported_envelope = True
        saw_surface_update = True
        if error := _validate_surface_update_payload(
            surface_update,
            require_initial_render=require_initial_render,
        ):
            return saw_begin_rendering, saw_surface_update, saw_supported_envelope, error

    if _extract_envelope_payload(record, "dataModelUpdate", "data_model_update") is not None:
        saw_supported_envelope = True
    if _extract_envelope_payload(record, "deleteSurface", "delete_surface") is not None:
        saw_supported_envelope = True

    return saw_begin_rendering, saw_surface_update, saw_supported_envelope, None


def _parse_a2ui_validation_records(messages: str) -> tuple[list[dict[str, object]], str | None]:
    """Parse raw A2UI messages for validation and detect flat payload misuse."""
    stripped = _strip_markdown_code_fence(messages)
    if not stripped:
        return [], _invalid_a2ui_payload("payload is empty.")

    parsed_whole: object | None = None
    try:
        parsed_whole = json.loads(stripped)
    except json.JSONDecodeError:
        parsed_whole = None

    if error := _flat_surface_payload_error(parsed_whole):
        return [], error

    records = _iter_message_dicts(messages)
    if not records:
        return [], _invalid_a2ui_payload("could not parse any supported A2UI envelopes.")
    return records, None


def _scan_a2ui_validation_records(
    records: list[dict[str, object]],
    *,
    require_initial_render: bool,
) -> tuple[bool, bool, bool, str | None]:
    """Validate parsed A2UI records and report which required envelopes were seen."""
    saw_begin_rendering = False
    saw_surface_update = False
    saw_supported_envelope = False

    for record in records:
        (
            record_saw_begin,
            record_saw_update,
            record_saw_supported,
            record_error,
        ) = _validate_a2ui_record(record, require_initial_render=require_initial_render)
        if record_error is not None:
            return saw_begin_rendering, saw_surface_update, saw_supported_envelope, record_error
        saw_begin_rendering = saw_begin_rendering or record_saw_begin
        saw_surface_update = saw_surface_update or record_saw_update
        saw_supported_envelope = saw_supported_envelope or record_saw_supported

    return saw_begin_rendering, saw_surface_update, saw_supported_envelope, None


def _finalize_a2ui_validation(
    messages: str,
    *,
    require_initial_render: bool,
    saw_begin_rendering: bool,
    saw_surface_update: bool,
    saw_supported_envelope: bool,
    error: str | None,
) -> str | None:
    """Apply final cross-record A2UI validation rules."""
    if error is not None:
        return error
    if not saw_supported_envelope:
        return _invalid_a2ui_payload("no supported A2UI envelopes were found.")

    surface_ids = extract_surface_ids(messages)
    if len(surface_ids) > 1:
        return _invalid_a2ui_payload(
            "all envelopes in one interactive surface payload must use the same surfaceId."
        )
    if not require_initial_render:
        return None
    if not saw_begin_rendering or not saw_surface_update:
        return _invalid_a2ui_payload(
            "new interactive surfaces must include both beginRendering and surfaceUpdate envelopes."
        )
    return None


def _collect_begin_render_roots(records: list[dict[str, object]]) -> set[str]:
    """Collect root ids declared by beginRendering envelopes."""
    roots: set[str] = set()
    for record in records:
        begin_rendering = _extract_envelope_payload(record, "beginRendering", "begin_rendering")
        if begin_rendering is None:
            continue
        root = begin_rendering.get("root")
        if isinstance(root, str) and root.strip():
            roots.add(root)
    return roots


def _collect_surface_component_ids(records: list[dict[str, object]]) -> set[str]:
    """Collect declared component ids from surfaceUpdate envelopes."""
    component_ids: set[str] = set()
    for record in records:
        surface_update = _extract_envelope_payload(record, "surfaceUpdate", "surface_update")
        if surface_update is None:
            continue
        components = surface_update.get("components")
        if not isinstance(components, list):
            continue
        for component in components:
            if not isinstance(component, dict):
                continue
            component_id = component.get("id")
            if isinstance(component_id, str) and component_id.strip():
                component_ids.add(component_id)
    return component_ids


def validate_a2ui_messages(
    messages: str,
    *,
    require_initial_render: bool = True,
) -> str | None:
    """Validate A2UI payloads before creating or waiting on a surface."""
    records, parse_error = _parse_a2ui_validation_records(messages)
    if parse_error is not None:
        return parse_error

    (
        saw_begin_rendering,
        saw_surface_update,
        saw_supported_envelope,
        record_error,
    ) = _scan_a2ui_validation_records(records, require_initial_render=require_initial_render)
    error = _finalize_a2ui_validation(
        messages,
        require_initial_render=require_initial_render,
        saw_begin_rendering=saw_begin_rendering,
        saw_surface_update=saw_surface_update,
        saw_supported_envelope=saw_supported_envelope,
        error=record_error,
    )
    if error is not None or not require_initial_render:
        return error

    declared_roots = _collect_begin_render_roots(records)
    component_ids = _collect_surface_component_ids(records)
    missing_roots = declared_roots - component_ids
    if missing_roots:
        return _invalid_a2ui_payload(
            f"beginRendering.root must reference a component id present in surfaceUpdate.components. "
            f"Missing roots: {sorted(missing_roots)}."
        )
    return None


def extract_surface_ids(messages: str) -> list[str]:
    """Return unique surface IDs discovered in A2UI message payloads."""
    seen: set[str] = set()
    ordered: list[str] = []
    for record in _iter_message_dicts(messages):
        surface_id = _surface_id_from_record(record)
        if surface_id is None:
            continue
        if surface_id in seen:
            continue
        seen.add(surface_id)
        ordered.append(surface_id)
    return ordered


def extract_surface_id(messages: str) -> str | None:
    """Return the single discovered surface ID, if the payload is unambiguous."""
    surface_ids = extract_surface_ids(messages)
    if len(surface_ids) != 1:
        return None
    return surface_ids[0]


# ---------------------------------------------------------------------------
# Component helpers
# ---------------------------------------------------------------------------


def text_component(text: str, *, style: dict[str, str] | None = None) -> dict[str, Any]:
    """Build an A2UI ``Text`` component."""
    comp: dict[str, Any] = {
        "id": _new_id(),
        "component": {
            "Text": {"text": _str_val(text), **(({"style": style}) if style else {})},
        },
    }
    return comp


def button_component(
    label: str,
    action_id: str,
    *,
    style: dict[str, str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Build an A2UI ``Button`` component with a user-action binding.

    Returns a ``(button, label_text)`` tuple.  The caller **must** include
    both the button dict *and* the label-text dict in the ``surfaceUpdate``
    components list so that the renderer can resolve the child reference.
    """
    label_text = text_component(label)
    props: dict[str, Any] = {
        "child": label_text["id"],
        "action": {"name": action_id},
    }
    if style:
        props["style"] = style
    button = {
        "id": _new_id(),
        "component": {"Button": props},
    }
    return (button, label_text)


def card_component(
    children: list[dict[str, Any]],
    *,
    title: str | None = None,
    style: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build an A2UI ``Card`` wrapper component."""
    child_ids = [c["id"] for c in children]
    props: dict[str, Any] = {}
    if title:
        props["title"] = title
    if style:
        props["style"] = style
    props["children"] = {"explicitList": child_ids}
    return {
        "id": _new_id(),
        "component": {"Card": props},
    }


def column_component(
    children: list[dict[str, Any]],
    *,
    gap: str = "8px",
) -> dict[str, Any]:
    """Build an A2UI ``Column`` layout component."""
    child_ids = [c["id"] for c in children]
    return {
        "id": _new_id(),
        "component": {"Column": {"gap": gap, "children": {"explicitList": child_ids}}},
    }


def row_component(
    children: list[dict[str, Any]],
    *,
    gap: str = "8px",
) -> dict[str, Any]:
    """Build an A2UI ``Row`` layout component."""
    child_ids = [c["id"] for c in children]
    return {
        "id": _new_id(),
        "component": {"Row": {"gap": gap, "children": {"explicitList": child_ids}}},
    }


def text_field_component(
    label: str,
    action_id: str,
    *,
    placeholder: str = "",
    value: str = "",
) -> dict[str, Any]:
    """Build an A2UI ``TextField`` input component.

    The ``action_id`` argument is normalized into the TextField's bound data path
    for compatibility with earlier callers that used it as a logical field name.
    To seed an initial value in the data model, pair this component with a
    ``data_model_update()`` envelope for the same path.
    """
    text_binding: dict[str, str] = {
        "path": _normalize_data_path(action_id),
    }
    if value:
        text_binding["literal"] = value
    return {
        "id": _new_id(),
        "component": {
            "TextField": {
                "label": _str_val(label),
                "text": text_binding,
                **({"placeholder": placeholder} if placeholder else {}),
            },
        },
    }


def divider_component() -> dict[str, Any]:
    """Build an A2UI ``Divider`` component."""
    return {
        "id": _new_id(),
        "component": {"Divider": {}},
    }


# ---------------------------------------------------------------------------
# Envelope constructors
# ---------------------------------------------------------------------------


def surface_update(
    surface_id: str,
    components: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a ``surfaceUpdate`` JSONL envelope."""
    return {
        "surfaceUpdate": {
            "surfaceId": surface_id,
            "components": components,
        },
    }


def data_model_update(
    surface_id: str,
    contents: list[dict[str, object]] | list[object] | dict[str, object] | object,
    *,
    path: str = "/",
) -> dict[str, Any]:
    """Build a ``dataModelUpdate`` JSONL envelope.

    Plain Python objects are normalized into A2UI ValueMap entries so the
    envelope matches the v0.8 data model contract.
    """
    return {
        "dataModelUpdate": {
            "surfaceId": surface_id,
            "path": path,
            "contents": _normalize_data_model_contents(contents),
        },
    }


def begin_rendering(
    surface_id: str,
    root: str,
    *,
    styles: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a ``beginRendering`` JSONL envelope."""
    envelope: dict[str, Any] = {
        "beginRendering": {
            "surfaceId": surface_id,
            "root": root,
        },
    }
    if styles:
        envelope["beginRendering"]["styles"] = styles
    return envelope


def delete_surface(surface_id: str) -> dict[str, Any]:
    """Build a ``deleteSurface`` JSONL envelope."""
    return {
        "deleteSurface": {
            "surfaceId": surface_id,
        },
    }


# ---------------------------------------------------------------------------
# Convenience: pack multiple envelopes into JSONL string
# ---------------------------------------------------------------------------


def pack_messages(messages: list[dict[str, Any]]) -> str:
    """Serialize a list of A2UI message envelopes to a JSONL string.

    Each line is a JSON object. This is the format expected by the
    CopilotKit ``processMessages()`` API.
    """
    return "\n".join(json.dumps(msg, separators=(",", ":")) for msg in messages)
