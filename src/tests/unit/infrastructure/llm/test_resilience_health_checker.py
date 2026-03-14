"""Unit tests for resilience health checker endpoint resolution."""

from types import SimpleNamespace

import pytest

from src.domain.llm_providers.models import ProviderType
from src.infrastructure.llm.resilience.health_checker import _resolve_endpoint_factory

pytestmark = pytest.mark.unit


def test_resolve_endpoint_factory_supports_volcengine_base_provider() -> None:
    """Volcengine base provider should resolve to Ark models endpoint."""
    endpoint_factory = _resolve_endpoint_factory(ProviderType.VOLCENGINE)

    assert endpoint_factory is not None
    endpoint = endpoint_factory(SimpleNamespace(base_url=None, llm_model="doubao"), "ark-key")
    assert endpoint.url == "https://ark.cn-beijing.volces.com/api/v3/models"
    assert endpoint.headers == {"Authorization": "Bearer ark-key"}


def test_resolve_endpoint_factory_supports_volcengine_variants() -> None:
    """Volcengine specialized variants should reuse the base provider endpoint."""
    endpoint_factory = _resolve_endpoint_factory(ProviderType.VOLCENGINE_CODING)

    assert endpoint_factory is not None
    endpoint = endpoint_factory(
        SimpleNamespace(base_url="https://custom.volcengine.example/api/v3", llm_model="doubao"),
        "ark-key",
    )
    assert endpoint.url == "https://custom.volcengine.example/api/v3/models"


def test_resolve_endpoint_factory_normalizes_other_variants() -> None:
    """Other *_coding variants should map to their base provider endpoints."""
    endpoint_factory = _resolve_endpoint_factory(ProviderType.MINIMAX_CODING)

    assert endpoint_factory is not None
    endpoint = endpoint_factory(SimpleNamespace(base_url=None, llm_model="abab"), "mm-key")
    assert endpoint.url == "https://api.minimax.io/v1/models"
