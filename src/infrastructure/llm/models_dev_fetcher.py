"""Fetcher and converter for models.dev API data.

Downloads the models.dev catalog (https://models.dev/api.json) and converts
entries to ``ModelMetadata`` instances compatible with the MemStack model
catalog.  The primary output is a regenerated ``models_snapshot.json`` that
can be committed into the repository as an embedded offline snapshot.

Usage (standalone)::

    python -m src.infrastructure.llm.models_dev_fetcher

Or via the helper script ``scripts/generate_models_snapshot.py``.
"""

from __future__ import annotations

import contextlib
import json
import logging
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from src.domain.llm_providers.models import ModelCapability, ModelMetadata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODELS_DEV_URL = "https://models.dev/api.json"

_SNAPSHOT_PATH = Path(__file__).parent / "models_snapshot.json"

# models.dev provider ID -> codebase ProviderType value
PROVIDER_MAP: dict[str, str] = {
    "openai": "openai",
    "anthropic": "anthropic",
    "google": "gemini",
    "deepseek": "deepseek",
    "alibaba": "dashscope",
    "minimax": "minimax",
    "zhipuai": "zai",
    "moonshotai": "kimi",
    "mistral": "mistral",
    "groq": "groq",
    "cohere": "cohere",
}

# Provider-specific overrides for input_budget_ratio and chars_per_token
# that cannot be derived from models.dev.
_PROVIDER_BUDGET_OVERRIDES: dict[str, dict[str, float]] = {
    "dashscope": {"input_budget_ratio": 0.85, "chars_per_token": 1.4},
}

_MODEL_BUDGET_OVERRIDES: dict[str, dict[str, float]] = {
    "qwen-max": {"input_budget_ratio": 0.85, "chars_per_token": 1.2},
    "qwen-vl-max": {"input_budget_ratio": 0.85, "chars_per_token": 1.2},
    "qwen-vl-plus": {"input_budget_ratio": 0.85, "chars_per_token": 1.2},
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch_models_dev(
    url: str = MODELS_DEV_URL,
    *,
    local_path: str | Path | None = None,
) -> dict[str, Any]:
    """Fetch the models.dev JSON catalog.

    Args:
        url: Remote URL to fetch from (default: official API).
        local_path: If provided, read from a local file instead of fetching.

    Returns:
        The raw parsed JSON dict keyed by provider ID.
    """
    if local_path is not None:
        path = Path(local_path)
        logger.info("Reading models.dev data from local file: %s", path)
        return json.loads(path.read_text("utf-8"))

    import urllib.request

    logger.info("Fetching models.dev data from %s", url)
    with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310
        return json.loads(resp.read().decode("utf-8"))


def convert_to_model_metadata(
    raw_data: dict[str, Any],
    *,
    providers: dict[str, str] | None = None,
) -> dict[str, ModelMetadata]:
    """Convert models.dev raw JSON to a dict of ``ModelMetadata``.

    Args:
        raw_data: Full models.dev JSON (provider-keyed).
        providers: Provider mapping override (default: ``PROVIDER_MAP``).

    Returns:
        Dict keyed by model name -> ``ModelMetadata``.
    """
    pmap = providers or PROVIDER_MAP
    result: dict[str, ModelMetadata] = {}

    for dev_provider, codebase_provider in pmap.items():
        provider_data = raw_data.get(dev_provider)
        if provider_data is None:
            logger.warning("Provider '%s' not found in models.dev data", dev_provider)
            continue

        models_raw: dict[str, Any] = provider_data.get("models", {})
        for model_id, model_data in models_raw.items():
            try:
                meta = _convert_single_model(model_id, model_data, codebase_provider)
                if meta is not None:
                    result[meta.name] = meta
            except Exception:
                logger.warning(
                    "Failed to convert model '%s' from provider '%s'",
                    model_id,
                    dev_provider,
                    exc_info=True,
                )

    logger.info("Converted %d models from models.dev", len(result))
    return result


def generate_snapshot(
    models: dict[str, ModelMetadata],
    *,
    output_path: Path | None = None,
) -> Path:
    """Write a ``models_snapshot.json`` file from converted models.

    Args:
        models: Dict of model name -> ``ModelMetadata``.
        output_path: Where to write (default: alongside this module).

    Returns:
        The path of the written file.
    """
    dest = output_path or _SNAPSHOT_PATH

    snapshot: dict[str, Any] = {
        "_meta": {
            "version": "2.0.0",
            "source": "models.dev",
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "description": "Model catalog snapshot generated from models.dev API",
            "model_count": len(models),
        },
        "models": {},
    }

    # Sort by provider then model name for deterministic output
    sorted_models = sorted(models.items(), key=lambda kv: (kv[1].provider or "", kv[0]))

    for name, meta in sorted_models:
        snapshot["models"][name] = _metadata_to_dict(meta)

    _ = dest.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    logger.info("Wrote %d models to %s", len(models), dest)
    return dest


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _convert_single_model(
    model_id: str,
    data: dict[str, Any],
    codebase_provider: str,
) -> ModelMetadata | None:
    """Convert a single models.dev model entry to ``ModelMetadata``."""
    # Skip embedding/reranking models (no chat capability)
    modalities_raw = data.get("modalities", {})
    output_modalities = modalities_raw.get("output", [])
    if not output_modalities:
        return None

    # Build limits
    limit = data.get("limit", {})
    context_length = limit.get("context", 128000)
    max_output_tokens = limit.get("output", 4096)

    # Use explicit input limit when present, otherwise derive
    if "input" in limit:
        max_input_tokens: int | None = limit["input"]
    else:
        max_input_tokens = None  # Will be derived at runtime as context - output

    # Build capabilities
    capabilities = _derive_capabilities(data)

    # Build modalities (deduplicated union of input + output)
    input_mods: list[str] = modalities_raw.get("input", [])
    output_mods: list[str] = modalities_raw.get("output", [])
    all_modalities = list(dict.fromkeys(input_mods + output_mods))

    # Build costs
    cost = data.get("cost", {})

    # Parse release date
    release_date: date | None = None
    release_str = data.get("release_date")
    if release_str:
        with contextlib.suppress(ValueError):
            release_date = date.fromisoformat(release_str)

    # Determine family
    family = data.get("family")

    # Build name (use model_id as-is)
    name = model_id

    # Interleaved reasoning config
    interleaved: dict[str, str] | None = data.get("interleaved")

    # Budget overrides
    budget_ratio = 0.9
    chars_per_token = 3.0
    if name in _MODEL_BUDGET_OVERRIDES:
        budget_ratio = _MODEL_BUDGET_OVERRIDES[name].get("input_budget_ratio", budget_ratio)
        chars_per_token = _MODEL_BUDGET_OVERRIDES[name].get("chars_per_token", chars_per_token)
    elif codebase_provider in _PROVIDER_BUDGET_OVERRIDES:
        overrides = _PROVIDER_BUDGET_OVERRIDES[codebase_provider]
        budget_ratio = overrides.get("input_budget_ratio", budget_ratio)
        chars_per_token = overrides.get("chars_per_token", chars_per_token)

    reasoning_flag = bool(data.get("reasoning", False))
    supports_temperature = bool(data.get("temperature", True))
    supports_tool_call = bool(data.get("tool_call", False))
    supports_structured_output = bool(data.get("structured_output", False))
    supports_attachment = bool(data.get("attachment", False))
    open_weights = bool(data.get("open_weights", False))
    knowledge_cutoff = data.get("knowledge")

    return ModelMetadata(
        name=name,
        context_length=context_length,
        max_output_tokens=max_output_tokens,
        input_cost_per_1m=cost.get("input"),
        output_cost_per_1m=cost.get("output"),
        capabilities=capabilities,
        supports_streaming=True,  # Assume all chat models stream
        supports_json_mode=supports_structured_output or supports_tool_call,
        provider=codebase_provider,
        modalities=all_modalities,
        family=family,
        release_date=release_date,
        description=data.get("name"),
        max_input_tokens=max_input_tokens,
        input_budget_ratio=budget_ratio,
        chars_per_token=chars_per_token,
        # models.dev extended fields
        reasoning=reasoning_flag,
        supports_temperature=supports_temperature,
        supports_tool_call=supports_tool_call,
        supports_structured_output=supports_structured_output,
        supports_attachment=supports_attachment,
        interleaved=interleaved,
        cache_read_cost_per_1m=cost.get("cache_read"),
        cache_write_cost_per_1m=cost.get("cache_write"),
        reasoning_cost_per_1m=cost.get("reasoning"),
        knowledge_cutoff=knowledge_cutoff,
        open_weights=open_weights,
    )


def _derive_capabilities(data: dict[str, Any]) -> list[ModelCapability]:
    """Derive ``ModelCapability`` list from models.dev fields."""
    caps: list[ModelCapability] = [ModelCapability.CHAT]

    if data.get("tool_call"):
        caps.append(ModelCapability.FUNCTION_CALLING)

    modalities_input = data.get("modalities", {}).get("input", [])
    if "image" in modalities_input or "video" in modalities_input:
        caps.append(ModelCapability.VISION)

    # Code capability heuristic: check family or model id
    family = (data.get("family") or "").lower()
    model_id = (data.get("id") or "").lower()
    if "code" in family or "codex" in model_id or "coder" in model_id or "devstral" in model_id:
        caps.append(ModelCapability.CODE)

    return caps


def _metadata_to_dict(meta: ModelMetadata) -> dict[str, Any]:  # noqa: C901, PLR0912
    """Serialize ``ModelMetadata`` to a JSON-compatible dict.

    Only includes non-default fields to keep the snapshot compact.
    """
    d: dict[str, Any] = {
        "name": meta.name,
        "context_length": meta.context_length,
        "max_output_tokens": meta.max_output_tokens,
    }

    if meta.input_cost_per_1m is not None:
        d["input_cost_per_1m"] = meta.input_cost_per_1m
    if meta.output_cost_per_1m is not None:
        d["output_cost_per_1m"] = meta.output_cost_per_1m

    if meta.capabilities:
        d["capabilities"] = [c.value if hasattr(c, "value") else c for c in meta.capabilities]
    d["supports_streaming"] = meta.supports_streaming
    d["supports_json_mode"] = meta.supports_json_mode

    if meta.provider:
        d["provider"] = meta.provider
    if meta.modalities:
        d["modalities"] = meta.modalities
    if meta.family:
        d["family"] = meta.family
    if meta.release_date:
        d["release_date"] = meta.release_date.isoformat()
    if meta.description:
        d["description"] = meta.description

    if meta.max_input_tokens is not None:
        d["max_input_tokens"] = meta.max_input_tokens
    if meta.input_budget_ratio != 0.9:
        d["input_budget_ratio"] = meta.input_budget_ratio
    if meta.chars_per_token != 3.0:
        d["chars_per_token"] = meta.chars_per_token

    # models.dev extended fields (only non-default values)
    if meta.reasoning:
        d["reasoning"] = True
    if not meta.supports_temperature:
        d["supports_temperature"] = False
    if meta.supports_tool_call:
        d["supports_tool_call"] = True
    if meta.supports_structured_output:
        d["supports_structured_output"] = True
    if meta.supports_attachment:
        d["supports_attachment"] = True
    if meta.interleaved is not None:
        d["interleaved"] = meta.interleaved
    if meta.cache_read_cost_per_1m is not None:
        d["cache_read_cost_per_1m"] = meta.cache_read_cost_per_1m
    if meta.cache_write_cost_per_1m is not None:
        d["cache_write_cost_per_1m"] = meta.cache_write_cost_per_1m
    if meta.reasoning_cost_per_1m is not None:
        d["reasoning_cost_per_1m"] = meta.reasoning_cost_per_1m
    if meta.knowledge_cutoff:
        d["knowledge_cutoff"] = meta.knowledge_cutoff
    if meta.open_weights:
        d["open_weights"] = True

    return d


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    raw = fetch_models_dev()
    models = convert_to_model_metadata(raw)
    path = generate_snapshot(models)
    print(f"Generated snapshot with {len(models)} models at {path}")
