"""Multi-channel message adapter system.

Public API
----------
.. autosummary::

    ChannelType
    ChannelMessage
    ChannelAdapter
    ChannelRouter
    RouteResult
    WebSocketChannelAdapter
    RestApiChannelAdapter
"""

from src.infrastructure.agent.channels.channel_adapter import ChannelAdapter
from src.infrastructure.agent.channels.channel_message import ChannelMessage
from src.infrastructure.agent.channels.channel_router import ChannelRouter, RouteResult
from src.infrastructure.agent.channels.channel_types import ChannelType
from src.infrastructure.agent.channels.rest_api_adapter import RestApiChannelAdapter
from src.infrastructure.agent.channels.websocket_adapter import WebSocketChannelAdapter

__all__ = [
    "ChannelAdapter",
    "ChannelMessage",
    "ChannelRouter",
    "ChannelType",
    "RestApiChannelAdapter",
    "RouteResult",
    "WebSocketChannelAdapter",
]
