"""Channel type definitions for the multi-channel adapter system.

Channel types are plain string constants rather than an enum so that
plugins can register arbitrary new channel types at runtime without
modifying this module.
"""

from __future__ import annotations

# Well-known channel type constants
WEBSOCKET: str = "websocket"
REST_API: str = "rest_api"
FEISHU: str = "feishu"
SLACK: str = "slack"
WEBHOOK: str = "webhook"

# Type alias for annotations
ChannelTypeStr = str

# Backwards-compat alias -- existing code that does
# ``from channel_types import ChannelType`` will get the alias.
ChannelType = ChannelTypeStr


def normalize_channel_type(value: str) -> str:
    """Normalise a channel type string to lowercase with underscores."""
    return value.strip().lower().replace("-", "_")
