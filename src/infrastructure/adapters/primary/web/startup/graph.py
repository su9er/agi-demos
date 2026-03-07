"""Graph service initialization for startup."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.configuration.factories import create_native_graph_adapter
from src.domain.llm_providers.models import NoActiveProviderError

if TYPE_CHECKING:
    from src.infrastructure.graph.native_graph_adapter import NativeGraphAdapter

logger = logging.getLogger(__name__)


async def initialize_graph_service() -> NativeGraphAdapter | None:
    """
    Initialize NativeGraphAdapter (self-developed knowledge graph engine).

    Returns ``None`` when no LLM provider is configured yet -- the app can
    still serve requests that don't need the knowledge graph.

    Returns:
        The initialized graph service, or None if no provider is available.

    Raises:
        Exception: If Neo4j is not available or a non-provider error occurs.
    """
    logger.info("Creating NativeGraphAdapter...")
    try:
        graph_service = await create_native_graph_adapter()
        logger.info("NativeGraphAdapter created successfully")
        return graph_service
    except NoActiveProviderError:
        logger.warning(
            "No active LLM provider configured -- graph service disabled. "
            "Configure a provider in the admin UI to enable knowledge graph features."
        )
        return None
    except Exception as e:
        logger.error(f"Failed to create NativeGraphAdapter: {e}")
        logger.error("Neo4j is required for MemStack to function. Please ensure Neo4j is running.")
        raise

async def shutdown_graph_service(graph_service: NativeGraphAdapter) -> None:
    """Shutdown graph service and close Neo4j connection."""
    if hasattr(graph_service, "client") and hasattr(graph_service.client, "close"):
        await graph_service.client.close()
        logger.info("Neo4j connection closed")
