"""Channel type definitions for the multi-channel adapter system."""

from __future__ import annotations

from enum import Enum


class ChannelType(str, Enum):
    """Supported input channel types.

    Each variant represents a distinct transport or integration
    through which messages can enter the agent system.
    """

    WEBSOCKET = "websocket"
    REST_API = "rest_api"
    FEISHU = "feishu"
    SLACK = "slack"
    WEBHOOK = "webhook"
