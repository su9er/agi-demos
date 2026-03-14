"""Reasoning model configuration helper.

Builds provider-specific options for reasoning/thinking models
(OpenAI o1/o3, Anthropic Claude extended thinking, Deepseek reasoner,
Gemini 2.5, Kimi k2-thinking, MiniMax M2/M2.5 reasoning).

Detection strategy (two-layer):
  1. **Catalog lookup** via ``ModelCatalogService`` — uses the ``reasoning``
     and ``supports_temperature`` booleans from models.dev data.
  2. **Prefix heuristic fallback** — hard-coded prefix lists for models
     not yet in the catalog.

Provider-specific HOW-to-configure logic (reasoning_effort, thinking
budget, use_max_completion_tokens, etc.) remains hard-coded because
that is provider SDK contract, not model metadata.

These options are passed through StreamConfig.provider_options -> to_litellm_kwargs()
and ultimately to the LiteLLM SDK.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


# Model prefixes/names that indicate reasoning capability.
# Order matters: more specific patterns first.
_OPENAI_REASONING_PREFIXES = ("o1-", "o3-", "o1", "o3", "o4-mini")
_DEEPSEEK_REASONING_MODELS = ("deepseek-reasoner", "deepseek-r1")
_GEMINI_THINKING_PATTERNS = ("gemini-2.5",)
_KIMI_THINKING_MODELS = ("kimi-k2-thinking",)
_ANTHROPIC_EXTENDED_THINKING_PREFIXES = ("claude-",)
_MINIMAX_REASONING_PREFIXES = ("minimax-m2",)


# ------------------------------------------------------------------
# Catalog helpers (lazy import to avoid circular dependencies)
# ------------------------------------------------------------------


def _catalog_is_reasoning(model: str) -> bool | None:
    """Check the model catalog for the ``reasoning`` flag.

    Returns ``True``/``False`` if the model is known, ``None`` otherwise
    (caller should fall back to heuristics).
    """
    try:
        from src.infrastructure.llm.model_catalog import get_model_catalog_service

        return get_model_catalog_service().is_reasoning_model(model)
    except Exception:
        return None


def _catalog_supports_temperature(model: str) -> bool | None:
    """Check the model catalog for the ``supports_temperature`` flag.

    Returns ``True``/``False`` if the model is known, ``None`` otherwise
    (caller should fall back to heuristics).
    """
    try:
        from src.infrastructure.llm.model_catalog import get_model_catalog_service

        return get_model_catalog_service().model_supports_temperature(model)
    except Exception:
        return None


@dataclass(frozen=True)
class ReasoningModelConfig:
    """Resolved configuration adjustments for a reasoning model.

    Attributes:
        provider_options: Extra kwargs merged into the LiteLLM call.
        use_max_completion_tokens: If True, replace ``max_tokens`` with
            ``max_completion_tokens`` in the LiteLLM kwargs (OpenAI reasoning models).
        omit_temperature: If True, remove ``temperature`` from the LiteLLM kwargs
            (models that reject non-default temperature).
        override_max_tokens: If set, override the max_tokens value to this.
    """

    provider_options: dict[str, Any]
    use_max_completion_tokens: bool = False
    omit_temperature: bool = False
    override_max_tokens: int | None = None


def _is_openai_reasoning(model: str) -> bool:
    model_lower = model.lower()
    # Strip common provider prefixes for comparison
    for prefix in ("openai/", "azure/"):
        if model_lower.startswith(prefix):
            model_lower = model_lower[len(prefix) :]
            break
    return any(model_lower.startswith(p) for p in _OPENAI_REASONING_PREFIXES)


def _is_deepseek_reasoning(model: str) -> bool:
    model_lower = model.lower()
    for prefix in ("deepseek/",):
        if model_lower.startswith(prefix):
            model_lower = model_lower[len(prefix) :]
            break
    return any(model_lower.startswith(p) for p in _DEEPSEEK_REASONING_MODELS)


def _is_gemini_thinking(model: str) -> bool:
    model_lower = model.lower()
    for prefix in ("gemini/", "vertex_ai/"):
        if model_lower.startswith(prefix):
            model_lower = model_lower[len(prefix) :]
            break
    return any(model_lower.startswith(p) for p in _GEMINI_THINKING_PATTERNS)


def _is_kimi_thinking(model: str) -> bool:
    model_lower = model.lower()
    for prefix in ("openai/",):
        if model_lower.startswith(prefix):
            model_lower = model_lower[len(prefix) :]
            break
    return any(model_lower == p for p in _KIMI_THINKING_MODELS)


def _is_anthropic_extended_thinking(model: str) -> bool:
    """Check if an Anthropic model should use extended thinking.

    Note: Extended thinking is opt-in. This only returns True when the
    caller explicitly requests thinking (via thinking_override).
    """
    model_lower = model.lower()
    for prefix in ("anthropic/",):
        if model_lower.startswith(prefix):
            model_lower = model_lower[len(prefix) :]
            break
    return any(model_lower.startswith(p) for p in _ANTHROPIC_EXTENDED_THINKING_PREFIXES)


def _is_minimax_reasoning(model: str) -> bool:
    model_lower = model.lower()
    for prefix in ("minimax/",):
        if model_lower.startswith(prefix):
            model_lower = model_lower[len(prefix) :]
            break
    return any(model_lower.startswith(p) for p in _MINIMAX_REASONING_PREFIXES)


def is_reasoning_model(model: str) -> bool:
    """Return True if the model is a known reasoning/thinking model.

    Checks the model catalog first (``reasoning`` flag from models.dev),
    falls back to prefix heuristics for models not in the catalog.

    This does NOT include Anthropic models because extended thinking is
    opt-in (controlled by thinking_override), not automatic.
    """
    catalog_answer = _catalog_is_reasoning(model)
    if catalog_answer is not None:
        return catalog_answer
    # Fallback to prefix heuristics
    return (
        _is_openai_reasoning(model)
        or _is_deepseek_reasoning(model)
        or _is_gemini_thinking(model)
        or _is_kimi_thinking(model)
        or _is_minimax_reasoning(model)
    )


def should_omit_temperature(model: str) -> bool:
    """Return True if *model* does not accept the temperature parameter.

    Checks the model catalog first (``supports_temperature`` flag from
    models.dev), falls back to reasoning-model heuristic (reasoning models
    typically reject temperature).
    """
    catalog_answer = _catalog_supports_temperature(model)
    if catalog_answer is not None:
        return not catalog_answer  # omit = NOT supports
    # Fallback: reasoning models typically don't support temperature
    return is_reasoning_model(model)


def build_reasoning_config(  # noqa: PLR0911
    model: str,
    *,
    thinking_override: bool | None = None,
    reasoning_effort: str | None = None,
    thinking_budget_tokens: int | None = None,
) -> ReasoningModelConfig | None:
    """Build provider-specific reasoning configuration for a model.

    Args:
        model: The model name (may include provider prefix like "openai/o3-mini").
        thinking_override: Explicit flag to enable/disable thinking.
            For most reasoning models this is ignored (they always reason).
            For Anthropic, True enables extended thinking.
        reasoning_effort: For OpenAI reasoning models: "low", "medium", or "high".
            Defaults to "medium" if not specified.
        thinking_budget_tokens: For Anthropic extended thinking, the budget.
            Defaults to 10000 if not specified.

    Returns:
        ReasoningModelConfig with provider-specific adjustments, or None if
        the model is not a reasoning model and thinking is not requested.
    """
    # OpenAI reasoning models (o1, o3, etc.)
    if _is_openai_reasoning(model):
        effort = reasoning_effort or "medium"
        logger.debug(f"Configuring OpenAI reasoning model {model} with effort={effort}")
        return ReasoningModelConfig(
            provider_options={"reasoning_effort": effort},
            use_max_completion_tokens=True,
            omit_temperature=should_omit_temperature(model),
        )

    # Deepseek reasoning models
    if _is_deepseek_reasoning(model):
        logger.debug(f"Configuring Deepseek reasoning model {model}")
        return ReasoningModelConfig(
            provider_options={},
            omit_temperature=should_omit_temperature(model),
        )

    # Gemini 2.5 thinking models
    if _is_gemini_thinking(model):
        budget = thinking_budget_tokens or 8192
        logger.debug(f"Configuring Gemini thinking model {model} with budget={budget}")
        return ReasoningModelConfig(
            provider_options={
                "thinking": {"type": "enabled", "budget_tokens": budget},
            },
        )

    # Kimi k2-thinking
    if _is_kimi_thinking(model):
        logger.debug(f"Configuring Kimi thinking model {model}")
        return ReasoningModelConfig(
            provider_options={},
            omit_temperature=should_omit_temperature(model),
        )

    # MiniMax reasoning models (M2, M2.1, M2.5, M2.5-highspeed)
    if _is_minimax_reasoning(model):
        logger.debug(f"Configuring MiniMax reasoning model {model}")
        return ReasoningModelConfig(
            provider_options={},
            omit_temperature=should_omit_temperature(model),
        )

    # Anthropic extended thinking (opt-in only)
    if thinking_override and _is_anthropic_extended_thinking(model):
        budget = thinking_budget_tokens or 10000
        logger.debug(f"Configuring Anthropic extended thinking for {model} with budget={budget}")
        return ReasoningModelConfig(
            provider_options={
                "thinking": {"type": "enabled", "budget_tokens": budget},
            },
            # Claude extended thinking needs larger max_tokens
            override_max_tokens=max(16000, budget * 2),
        )

    # Not a recognized reasoning model — check catalog as a final catch-all
    # for models that are reasoning-capable but not matched by prefix heuristics.
    if _catalog_is_reasoning(model):
        omit_temp = should_omit_temperature(model)
        logger.debug(f"Catalog-detected reasoning model {model} (omit_temperature={omit_temp})")
        return ReasoningModelConfig(
            provider_options={},
            omit_temperature=omit_temp,
        )

    return None
