"""Integration tests for AIServiceFactory.create_llm_client_for_category.

Verifies the wiring between CategoryRouter and create_litellm_client
inside the category-based model routing path.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.infrastructure.llm.provider_factory import AIServiceFactory


@pytest.mark.integration
class TestCategoryRouterWiring:
    """Verify create_llm_client_for_category routes correctly."""

    @patch(
        "src.infrastructure.llm.litellm.litellm_client.create_litellm_client",
    )
    @patch(
        "src.infrastructure.llm.category_router.CategoryRouter",
    )
    def test_category_router_overrides_model(
        self,
        mock_router_cls: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        """When route() returns preferred_models, the first
        model overrides the original ProviderConfig.model."""
        # Arrange
        routed = MagicMock()
        routed.preferred_models = ["better-model"]
        routed.category.value = "code"
        routed.confidence = 0.95

        mock_router_cls.return_value.route.return_value = routed

        original_cfg = MagicMock()
        original_cfg.provider = "openai"
        original_cfg.model = "gpt-4"
        original_cfg.api_key = "sk-key"
        original_cfg.base_url = "https://api.openai.com"
        original_cfg.embedding_model = "text-embedding-3"
        original_cfg.rerank_model = "rerank-v1"

        mock_create.return_value = MagicMock(name="client")

        # Act -- patch ProviderConfig constructor at call site
        with patch(
            "src.infrastructure.llm.provider_factory.ProviderConfig",
        ) as mock_pc_cls:
            mock_pc_cls.return_value = MagicMock(
                name="overridden_cfg",
            )
            result = AIServiceFactory.create_llm_client_for_category(
                provider_config=original_cfg,
                task_description="Write Python code",
            )

        # Assert -- router was called
        mock_router_cls.return_value.route.assert_called_once_with(
            task_description="Write Python code",
        )
        # Assert -- ProviderConfig rebuilt with overridden model
        mock_pc_cls.assert_called_once_with(
            provider="openai",
            model="better-model",
            api_key="sk-key",
            base_url="https://api.openai.com",
            embedding_model="text-embedding-3",
            rerank_model="rerank-v1",
        )
        # Assert -- create_litellm_client receives overridden cfg
        mock_create.assert_called_once_with(
            mock_pc_cls.return_value,
            cache=None,
        )
        assert result is mock_create.return_value

    @patch(
        "src.infrastructure.llm.litellm.litellm_client.create_litellm_client",
    )
    @patch(
        "src.infrastructure.llm.category_router.CategoryRouter",
    )
    def test_category_router_no_override_when_empty(
        self,
        mock_router_cls: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        """When preferred_models is empty, original config
        is forwarded unchanged."""
        # Arrange
        routed = MagicMock()
        routed.preferred_models = []

        mock_router_cls.return_value.route.return_value = routed

        original_cfg = MagicMock()
        original_cfg.model = "original-model"
        mock_create.return_value = MagicMock(name="client")

        # Act
        result = AIServiceFactory.create_llm_client_for_category(
            provider_config=original_cfg,
            task_description="Hello world",
        )

        # Assert -- original config passed through as-is
        mock_create.assert_called_once_with(
            original_cfg,
            cache=None,
        )
        assert result is mock_create.return_value

    @patch(
        "src.infrastructure.llm.litellm.litellm_client.create_litellm_client",
    )
    @patch(
        "src.infrastructure.llm.category_router.CategoryRouter",
    )
    def test_category_router_preserves_other_config_fields(
        self,
        mock_router_cls: MagicMock,
        mock_create: MagicMock,
    ) -> None:
        """When model is overridden, api_key / base_url /
        embedding_model / rerank_model stay unchanged."""
        # Arrange
        routed = MagicMock()
        routed.preferred_models = ["new-model"]
        routed.category.value = "analysis"
        routed.confidence = 0.8

        mock_router_cls.return_value.route.return_value = routed

        original_cfg = MagicMock()
        original_cfg.provider = "gemini"
        original_cfg.model = "old-model"
        original_cfg.api_key = "secret-key-123"
        original_cfg.base_url = "https://custom.api"
        original_cfg.embedding_model = "embed-v2"
        original_cfg.rerank_model = "rerank-v2"

        mock_create.return_value = MagicMock(name="client")

        # Act
        with patch(
            "src.infrastructure.llm.provider_factory.ProviderConfig",
        ) as mock_pc_cls:
            mock_pc_cls.return_value = MagicMock(
                name="rebuilt_cfg",
            )
            AIServiceFactory.create_llm_client_for_category(
                provider_config=original_cfg,
                task_description="Analyze data",
                cache=True,
            )

        # Assert -- all original fields forwarded
        call_kwargs = mock_pc_cls.call_args[1]
        assert call_kwargs["api_key"] == "secret-key-123"
        assert call_kwargs["base_url"] == "https://custom.api"
        assert call_kwargs["embedding_model"] == "embed-v2"
        assert call_kwargs["rerank_model"] == "rerank-v2"
        assert call_kwargs["provider"] == "gemini"
        # model is the only field changed
        assert call_kwargs["model"] == "new-model"

        # cache kwarg forwarded
        mock_create.assert_called_once_with(
            mock_pc_cls.return_value,
            cache=True,
        )
