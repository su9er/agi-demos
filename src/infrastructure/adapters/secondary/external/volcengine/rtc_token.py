"""Volcengine RTC AccessToken generator (binary protocol v001).

Reference: https://www.volcengine.com/docs/6348/70121
Algorithm ported from volcengine/rtc-aigc-demo Server/token.js
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import random
import struct
import time

# Privilege flags
PRIV_PUBLISH_STREAM = 0
PRIV_PUBLISH_AUDIO_STREAM = 1
PRIV_PUBLISH_VIDEO_STREAM = 2
PRIV_PUBLISH_DATA_STREAM = 3
PRIV_SUBSCRIBE_STREAM = 4

VERSION = "001"


def _pack_uint16(value: int) -> bytes:
    return struct.pack("<H", value)


def _pack_uint32(value: int) -> bytes:
    return struct.pack("<I", value)


def _pack_string(s: str) -> bytes:
    b = s.encode("utf-8")
    return _pack_uint16(len(b)) + b


def _pack_treemap(m: dict[int, int]) -> bytes:
    """Pack a map of UInt16 keys to UInt32 values, sorted by key."""
    sorted_keys = sorted(m.keys())
    result = _pack_uint16(len(sorted_keys))
    for k in sorted_keys:
        result += _pack_uint16(k)
        result += _pack_uint32(m[k])
    return result


def generate_rtc_token(
    app_id: str,
    app_key: str,
    room_id: str,
    user_id: str,
    expire_time: int = 3600,
) -> str:
    """Generate a Volcengine RTC join token.

    Args:
        app_id: RTC application ID (24 chars).
        app_key: RTC application key (secret).
        room_id: Room identifier to join.
        user_id: User identifier joining the room.
        expire_time: Token validity in seconds (default 3600).

    Returns:
        Token string: VERSION + app_id + base64(content).
    """
    issued_at = int(time.time())
    expire_at = issued_at + expire_time
    nonce = random.randint(0, 0xFFFFFFFF)

    # Default privileges: full publish + subscribe
    privileges: dict[int, int] = {
        PRIV_PUBLISH_STREAM: expire_at,
        PRIV_PUBLISH_AUDIO_STREAM: expire_at,
        PRIV_PUBLISH_VIDEO_STREAM: expire_at,
        PRIV_PUBLISH_DATA_STREAM: expire_at,
        PRIV_SUBSCRIBE_STREAM: expire_at,
    }

    # 1. Pack message payload
    msg = bytearray()
    msg += _pack_uint32(nonce)
    msg += _pack_uint32(issued_at)
    msg += _pack_uint32(expire_at)
    msg += _pack_string(room_id)
    msg += _pack_string(user_id)
    msg += _pack_treemap(privileges)

    # 2. HMAC-SHA256 sign the message
    signature = hmac.new(app_key.encode("utf-8"), bytes(msg), hashlib.sha256).digest()

    # 3. Final serialization: String(msg) + String(signature)
    content = bytearray()
    content += _pack_uint16(len(msg)) + msg
    content += _pack_uint16(len(signature)) + signature

    return VERSION + app_id + base64.b64encode(bytes(content)).decode("utf-8")
