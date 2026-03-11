"""Binary framing utilities for Volcengine ASR V3 WebSocket protocol.

Implements the binary header, sequence, and response parsing for the ASR
streaming protocol described at:
  https://www.volcengine.com/docs/6561/1354870

The 4-byte header layout is:
  byte 0: (protocol_version << 4) | header_size
  byte 1: (message_type     << 4) | message_type_specific_flags
  byte 2: (serialization    << 4) | compression
  byte 3: reserved (0x00)
"""

from __future__ import annotations

import gzip
import json
import logging
import struct
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol constants
# ---------------------------------------------------------------------------

PROTOCOL_VERSION: int = 0b0001
HEADER_SIZE: int = 0b0001

# Message types (upper nibble of byte 1)
FULL_CLIENT_REQUEST: int = 0b0001
AUDIO_ONLY_REQUEST: int = 0b0010
FULL_SERVER_RESPONSE: int = 0b1001
SERVER_ERROR_RESPONSE: int = 0b1111

# Message-type-specific flags (lower nibble of byte 1)
NO_SEQUENCE: int = 0b0000
POS_SEQUENCE: int = 0b0001
NEG_SEQUENCE: int = 0b0010
LAST_PACKAGE: int = 0b0010  # Alias used for audio-only last packet

# Serialization (upper nibble of byte 2)
JSON_SERIALIZATION: int = 0b0001
NO_SERIALIZATION: int = 0b0000

# Compression (lower nibble of byte 2)
GZIP_COMPRESSION: int = 0b0001
NO_COMPRESSION: int = 0b0000


# ---------------------------------------------------------------------------
# Header construction
# ---------------------------------------------------------------------------


def generate_header(
    message_type: int = FULL_CLIENT_REQUEST,
    message_type_specific_flags: int = NO_SEQUENCE,
    serialization: int = JSON_SERIALIZATION,
    compression: int = GZIP_COMPRESSION,
) -> bytes:
    """Build a 4-byte protocol header.

    Returns:
        4 bytes packed as ``[version<<4|header_size, msg_type<<4|flags,
        serialization<<4|compression, 0x00]``.
    """
    byte0 = (PROTOCOL_VERSION << 4) | HEADER_SIZE
    byte1 = (message_type << 4) | message_type_specific_flags
    byte2 = (serialization << 4) | compression
    byte3 = 0x00
    return bytes([byte0, byte1, byte2, byte3])


def generate_before_payload(sequence: int = 1) -> bytes:
    """Encode a 4-byte big-endian sequence number.

    Args:
        sequence: Sequence counter (typically starts at 1).

    Returns:
        4 bytes representing *sequence* in big-endian order.
    """
    return struct.pack(">I", sequence)


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


class ProtocolError(Exception):
    """Raised when the server response cannot be decoded."""


def parse_response(data: bytes) -> dict[str, Any]:
    """Parse a binary server response into a structured dict.

    The returned dict always contains:
      * ``header``  -- decoded header fields.
      * ``payload_msg`` -- parsed JSON body (empty dict for audio-only).
      * ``is_last_package`` -- ``True`` when the server signals end-of-stream.
      * ``sequence`` -- the sequence number embedded in the frame (``-1`` when
        the frame carries no sequence).

    Raises:
        ProtocolError: If the frame is too short or the message type is
            ``SERVER_ERROR_RESPONSE``.
    """
    if len(data) < 4:
        raise ProtocolError(f"Response too short ({len(data)} bytes)")

    # -- header --
    byte0 = data[0]
    byte1 = data[1]
    byte2 = data[2]

    protocol_version = (byte0 >> 4) & 0x0F
    header_size_field = byte0 & 0x0F
    msg_type = (byte1 >> 4) & 0x0F
    msg_flags = byte1 & 0x0F
    serialization = (byte2 >> 4) & 0x0F
    compression = byte2 & 0x0F

    header_info: dict[str, int] = {
        "protocol_version": protocol_version,
        "header_size": header_size_field,
        "message_type": msg_type,
        "message_type_specific_flags": msg_flags,
        "serialization": serialization,
        "compression": compression,
    }

    # Header occupies ``header_size_field * 4`` bytes.
    header_byte_count = header_size_field * 4
    offset = header_byte_count

    # -- optional sequence --
    sequence = -1
    has_sequence = msg_flags in (POS_SEQUENCE, NEG_SEQUENCE)
    if has_sequence and len(data) >= offset + 4:
        (sequence,) = struct.unpack(">I", data[offset : offset + 4])
        offset += 4

    # -- payload size + payload --
    payload_msg: dict[str, Any] = {}
    is_last = msg_flags == NEG_SEQUENCE

    if len(data) >= offset + 4:
        (payload_size,) = struct.unpack(">I", data[offset : offset + 4])
        offset += 4
        payload_bytes = data[offset : offset + payload_size]

        if compression == GZIP_COMPRESSION and payload_bytes:
            payload_bytes = gzip.decompress(payload_bytes)

        if serialization == JSON_SERIALIZATION and payload_bytes:
            payload_msg = json.loads(payload_bytes)

    # -- error handling --
    if msg_type == SERVER_ERROR_RESPONSE:
        error_code = payload_msg.get("code", -1)
        error_message = payload_msg.get("message", "unknown error")
        logger.error("ASR server error %s: %s", error_code, error_message)
        raise ProtocolError(f"Server error (code={error_code}): {error_message}")

    return {
        "header": header_info,
        "payload_msg": payload_msg,
        "is_last_package": is_last,
        "sequence": sequence,
    }
