"""Demo custom runtime hooks for phase-1 hook extensibility verification."""

from __future__ import annotations

from typing import Any


def append_demo_response_instruction(payload: dict[str, Any]) -> dict[str, Any]:
    """Append a visible response instruction to prove custom code execution."""
    current = list(payload.get("response_instructions", []))
    instruction = "Demo runtime hook executed from custom script."
    if instruction not in current:
        current.append(instruction)
    updated = dict(payload)
    updated["response_instructions"] = current
    updated["demo_hook_executed"] = True
    return updated
