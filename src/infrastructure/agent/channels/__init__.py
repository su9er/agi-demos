"""Multi-channel message adapter system.

Public API
----------
.. autosummary::

    ChannelType
    ChannelTypeStr
    WEBSOCKET
    REST_API
    FEISHU
    SLACK
    WEBHOOK
    normalize_channel_type
    ChannelMessage
    TransportChannelAdapter
    TransportToDomainAdapter
    channel_message_to_domain
    domain_to_channel_message
    ChannelRouter
    RouteResult
    WebSocketChannelAdapter
    RestApiChannelAdapter
"""

from src.infrastructure.agent.channels.adapter_wrappers import TransportToDomainAdapter
from src.infrastructure.agent.channels.channel_adapter import TransportChannelAdapter
from src.infrastructure.agent.channels.channel_message import ChannelMessage
from src.infrastructure.agent.channels.channel_router import ChannelRouter, RouteResult
from src.infrastructure.agent.channels.channel_types import (
    FEISHU,
    REST_API,
    SLACK,
    WEBHOOK,
    WEBSOCKET,
    ChannelType,
    ChannelTypeStr,
    normalize_channel_type,
)
from src.infrastructure.agent.channels.rest_api_adapter import RestApiChannelAdapter
from src.infrastructure.agent.channels.translation import (
    channel_message_to_domain,
    domain_to_channel_message,
)
from src.infrastructure.agent.channels.websocket_adapter import WebSocketChannelAdapter

# Backwards-compat alias: old name -> new name
ChannelAdapter = TransportChannelAdapter

__all__ = [
    "FEISHU",
    "REST_API",
    "SLACK",
    "WEBHOOK",
    "WEBSOCKET",
    "ChannelAdapter",
    "ChannelMessage",
    "ChannelRouter",
    "ChannelType",
    "ChannelTypeStr",
    "RestApiChannelAdapter",
    "RouteResult",
    "TransportChannelAdapter",
    "TransportToDomainAdapter",
    "WebSocketChannelAdapter",
    "channel_message_to_domain",
    "domain_to_channel_message",
    "normalize_channel_type",
]
