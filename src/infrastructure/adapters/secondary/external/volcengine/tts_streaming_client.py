"""Async streaming TTS client for Volcengine V3 bidirectional speech synthesis.

Connects to the Volcengine TTS V3 bidirectional WebSocket endpoint, sends
text, and yields synthesized audio chunks as they arrive.

The TTS protocol uses an *event-based* binary framing scheme that differs
from the ASR binary protocol: each frame carries an event code and optional
connection/session IDs alongside the JSON or audio payload.

Usage::

    client = AsyncTTSStreamingClient(
        access_key="...", app_key="...",
    )
    await client.connect()
    async for audio_chunk in client.synthesize("Hello world"):
        play(audio_chunk)
    await client.close()

Reference: https://www.volcengine.com/docs/6561/1354869
"""

from __future__ import annotations

import gzip
import json
import logging
import struct
import uuid
from collections.abc import AsyncGenerator
from typing import Any

from websockets.asyncio.client import ClientConnection, connect
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Protocol constants (TTS-specific)
# ---------------------------------------------------------------------------

PROTOCOL_VERSION: int = 0b0001
HEADER_SIZE: int = 0b0001

# Message types
FULL_CLIENT: int = 0b0001
AUDIO_ONLY_SERVER: int = 0b0100

# Message-type-specific flags
WITH_EVENT: int = 0b0100

# Serialization / compression (shared with ASR but redeclared for isolation)
JSON_SERIALIZATION: int = 0b0001
NO_SERIALIZATION: int = 0b0000
GZIP_COMPRESSION: int = 0b0001
NO_COMPRESSION: int = 0b0000

# ---------------------------------------------------------------------------
# Event codes
# ---------------------------------------------------------------------------

EventStartConnection: int = 1
EventFinishConnection: int = 2
EventConnectionStarted: int = 50
EventConnectionFailed: int = 51
EventStartSession: int = 100
EventFinishSession: int = 102
EventSessionStarted: int = 150
EventSessionFinished: int = 152
EventTaskRequest: int = 200
EventTTSSentenceStart: int = 350
EventTTSSentenceEnd: int = 351

NAMESPACE: str = "BidirectionalTTS"
DEFAULT_SPEAKER: str = "zh_female_tianmeixiaoyuan_moon_bigtts"

_DEFAULT_WS_URL = "wss://openspeech.bytedance.com/api/v3/tts/bidirection"
_RESOURCE_ID = "volc.service_type.10029"


class TTSConnectionError(Exception):
    """Raised when the TTS WebSocket connection or session setup fails."""


class AsyncTTSStreamingClient:
    """Bidirectional streaming TTS client for Volcengine V3.

    Args:
        access_key: Volcengine API access key.
        app_key: Application key for the TTS resource.
        speaker: Voice speaker identifier.
        ws_url: WebSocket endpoint URL.
    """

    def __init__(
        self,
        access_key: str,
        app_key: str,
        speaker: str = DEFAULT_SPEAKER,
        ws_url: str = _DEFAULT_WS_URL,
    ) -> None:
        super().__init__()
        self._access_key = access_key
        self._app_key = app_key
        self._speaker = speaker
        self._ws_url = ws_url
        self._ws: ClientConnection | None = None
        self._connect_id = str(uuid.uuid4())
        self._session_id = ""

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self) -> None:
        """Open WebSocket connection, start connection and session.

        The handshake follows three steps:

        1. TCP + TLS WebSocket upgrade with auth headers.
        2. ``EventStartConnection`` (1) -> wait ``EventConnectionStarted`` (50).
        3. ``EventStartSession`` (100) -> wait ``EventSessionStarted`` (150).

        Raises:
            TTSConnectionError: On any connection / handshake failure.
        """
        headers = {
            "X-Api-Resource-Id": _RESOURCE_ID,
            "X-Api-Access-Key": self._access_key,
            "X-Api-App-Key": self._app_key,
            "X-Api-Connect-Id": self._connect_id,
            "X-Tt-Logid": str(uuid.uuid4()),
        }

        logger.info(
            "TTS connecting to %s (connect_id=%s)",
            self._ws_url,
            self._connect_id,
        )

        try:
            self._ws = await connect(
                self._ws_url,
                additional_headers=headers,
                max_size=None,
                open_timeout=10,
                proxy=None,
        except Exception as exc:
            raise TTSConnectionError(f"Failed to connect to TTS endpoint: {exc}") from exc

        # Step 1 -- start connection
        await self._write_event(EventStartConnection, payload_dict=None)
        resp = await self._read_event()
        event_code = resp.get("event", -1)
        if event_code == EventConnectionFailed:
            raise TTSConnectionError(f"TTS EventConnectionFailed: {resp}")
        if event_code != EventConnectionStarted:
            raise TTSConnectionError(f"Expected EventConnectionStarted(50), got event={event_code}")
        logger.debug("TTS connection started")

        # Step 2 -- start session
        session_payload: dict[str, Any] = {
            "user": {"uid": "memstack"},
            "audio_params": {
                "format": "mp3",
                "sample_rate": 24000,
                "channel": 1,
            },
            "speaker": self._speaker,
        }
        await self._write_event(EventStartSession, payload_dict=session_payload)
        resp = await self._read_event()
        event_code = resp.get("event", -1)
        if event_code != EventSessionStarted:
            raise TTSConnectionError(f"Expected EventSessionStarted(150), got event={event_code}")
        self._session_id = resp.get("session_id", "")
        logger.info("TTS session started (session_id=%s)", self._session_id)

    async def close(self) -> None:
        """Send ``EventFinishSession`` and close the WebSocket."""
        if self._ws is not None:
            try:
                await self._write_event(EventFinishSession, payload_dict=None)
            except (ConnectionClosed, TTSConnectionError):
                pass
            try:
                await self._ws.close()
            except ConnectionClosed:
                pass
            finally:
                self._ws = None
                logger.info(
                    "TTS connection closed (connect_id=%s)",
                    self._connect_id,
                )

    @property
    def is_connected(self) -> bool:
        """Return ``True`` when the underlying WebSocket is open."""
        return self._ws is not None and self._ws.state.name == "OPEN"

    # ------------------------------------------------------------------
    # Text -> Audio streaming
    # ------------------------------------------------------------------

    async def synthesize(self, text: str) -> AsyncGenerator[bytes, None]:
        """Send *text* for synthesis and yield audio chunks.

        Args:
            text: Plain text to synthesize.

        Yields:
            Raw audio bytes (MP3 by default, determined by session params).

        Raises:
            TTSConnectionError: If not connected.
        """
        if self._ws is None:
            raise TTSConnectionError("Not connected -- call connect() first")

        task_payload: dict[str, Any] = {
            "text": text,
            "text_type": "plain",
            "operation": "submit",
            "with_frontend": True,
        }
        await self._write_event(EventTaskRequest, payload_dict=task_payload)

        # Read response frames until the task or session finishes
        while True:
            raw = await self._recv_raw()
            if raw is None:
                # Connection closed
                return

            frame = self._parse_frame(raw)
            if frame is None:
                continue

            kind = frame["kind"]
            if kind == "audio":
                audio: bytes = frame["data"]
                yield audio
            elif kind == "event":
                event_data: dict[str, Any] = frame["data"]
                evt = event_data.get("event", -1)
                if evt in (EventSessionFinished, EventFinishConnection):
                    logger.debug("TTS synthesis finished (event=%s)", evt)
                    return
                # TaskFinished is signalled by event 0 or absence of further
                # audio -- we detect end-of-task when the server stops
                # sending audio-only frames.
                if evt == EventTTSSentenceStart:
                    logger.debug(
                        "TTS sentence start: %s",
                        event_data.get("payload", ""),
                    )
                elif evt == EventTTSSentenceEnd:
                    logger.debug(
                        "TTS sentence end: %s",
                        event_data.get("payload", ""),
                    )
                else:
                    logger.debug("TTS event %s received", evt)

    # ------------------------------------------------------------------
    # Low-level I/O
    # ------------------------------------------------------------------

    async def _write_event(
        self,
        event_code: int,
        *,
        payload_dict: dict[str, Any] | None,
    ) -> None:
        """Pack and send an event message.

        Frame layout::

            header (4B)
            + event_code (4B, big-endian)
            + connect_id_len (4B) + connect_id (UTF-8 bytes)
            + session_id_len (4B) + session_id (UTF-8 bytes)
            + payload_len (4B) + payload (GZIP JSON bytes)
        """
        if self._ws is None:
            raise TTSConnectionError("WebSocket not open")

        # Wrap payload_dict inside canonical envelope expected by server
        envelope: dict[str, Any] = {
            "event": event_code,
            "namespace": NAMESPACE,
        }
        if payload_dict is not None:
            envelope["payload"] = json.dumps(payload_dict, ensure_ascii=False)

        payload_json = json.dumps(envelope, ensure_ascii=False).encode("utf-8")
        compressed_payload = gzip.compress(payload_json)

        header = self._build_header(
            message_type=FULL_CLIENT,
            flags=WITH_EVENT,
            serialization=JSON_SERIALIZATION,
            compression=GZIP_COMPRESSION,
        )

        connect_id_bytes = self._connect_id.encode("utf-8")
        session_id_bytes = self._session_id.encode("utf-8")

        frame = bytearray()
        frame.extend(header)
        frame.extend(struct.pack(">I", event_code))
        frame.extend(struct.pack(">I", len(connect_id_bytes)))
        frame.extend(connect_id_bytes)
        frame.extend(struct.pack(">I", len(session_id_bytes)))
        frame.extend(session_id_bytes)
        frame.extend(struct.pack(">I", len(compressed_payload)))
        frame.extend(compressed_payload)

        await self._ws.send(bytes(frame))
        logger.debug("TTS sent event=%d", event_code)

    async def _recv_raw(self) -> bytes | None:
        """Receive the next binary WebSocket message.

        Returns ``None`` when the connection is closed.
        """
        if self._ws is None:
            return None
        try:
            data = await self._ws.recv(decode=False)
        except ConnectionClosed:
            logger.info("TTS connection closed by server")
            self._ws = None
            return None
        return data

    async def _read_event(self) -> dict[str, Any]:
        """Convenience wrapper: receive and parse a JSON event frame.

        Raises:
            TTSConnectionError: If the connection closes before an event
                arrives or the frame cannot be parsed as a JSON event.
        """
        raw = await self._recv_raw()
        if raw is None:
            raise TTSConnectionError("Connection closed while waiting for TTS event")
        frame = self._parse_frame(raw)
        if frame is None or frame["kind"] != "event":
            raise TTSConnectionError(f"Expected JSON event frame, got: {frame}")
        result: dict[str, Any] = frame["data"]
        return result

    # ------------------------------------------------------------------
    # Frame parsing
    # ------------------------------------------------------------------

    def _parse_frame(self, data: bytes) -> dict[str, Any] | None:
        """Decode a server frame into either an audio or event dict.

        Returns:
            ``{"kind": "audio", "data": <bytes>}`` for audio frames, or
            ``{"kind": "event", "data": <dict>}`` for JSON event frames.
            Returns ``None`` when the frame is too short.
        """
        if len(data) < 4:
            logger.warning("TTS frame too short (%d bytes)", len(data))
            return None

        byte1 = data[1]
        byte2 = data[2]

        msg_type = (byte1 >> 4) & 0x0F
        serialization = (byte2 >> 4) & 0x0F
        compression = byte2 & 0x0F

        header_size_field = data[0] & 0x0F
        offset = header_size_field * 4

        # Audio-only server response (no JSON, raw audio payload)
        if msg_type == AUDIO_ONLY_SERVER or serialization == NO_SERIALIZATION:
            return self._parse_audio_frame(data, offset, compression)

        # JSON event frame
        return self._parse_json_event_frame(data, offset, serialization, compression)

    def _parse_audio_frame(
        self,
        data: bytes,
        offset: int,
        compression: int,
    ) -> dict[str, Any] | None:
        """Extract raw audio bytes from an audio-only frame."""
        if len(data) <= offset:
            return None

        # Some server frames include a 4-byte size prefix before audio
        if len(data) >= offset + 4:
            (declared_size,) = struct.unpack(">I", data[offset : offset + 4])
            remaining = len(data) - offset - 4
            if declared_size == remaining:
                offset += 4
                audio_bytes = data[offset : offset + declared_size]
            else:
                # No size prefix -- treat everything after header as audio
                audio_bytes = data[offset:]
        else:
            audio_bytes = data[offset:]

        if compression == GZIP_COMPRESSION and audio_bytes:
            try:
                audio_bytes = gzip.decompress(audio_bytes)
            except gzip.BadGzipFile:
                pass  # Already decompressed or raw

        return {"kind": "audio", "data": audio_bytes}

    def _parse_json_event_frame(
        self,
        data: bytes,
        offset: int,
        serialization: int,
        compression: int,
    ) -> dict[str, Any] | None:
        """Decode a JSON event frame, skipping event/id length-prefixed
        fields."""
        # Event frames may contain:
        #   event_code(4B) + connect_id_len(4B) + connect_id
        #   + session_id_len(4B) + session_id + payload_len(4B) + payload

        result: dict[str, Any] = {}

        # event_code
        if len(data) >= offset + 4:
            (event_code,) = struct.unpack(">I", data[offset : offset + 4])
            offset += 4
            result["event"] = event_code
        else:
            return self._fallback_json_parse(data, 4, compression)

        # connect_id
        if len(data) >= offset + 4:
            (cid_len,) = struct.unpack(">I", data[offset : offset + 4])
            offset += 4
            if cid_len > 0 and len(data) >= offset + cid_len:
                result["connect_id"] = data[offset : offset + cid_len].decode(
                    "utf-8", errors="replace"
                )
                offset += cid_len

        # session_id
        if len(data) >= offset + 4:
            (sid_len,) = struct.unpack(">I", data[offset : offset + 4])
            offset += 4
            if sid_len > 0 and len(data) >= offset + sid_len:
                result["session_id"] = data[offset : offset + sid_len].decode(
                    "utf-8", errors="replace"
                )
                offset += sid_len

        # payload
        if len(data) >= offset + 4:
            (payload_len,) = struct.unpack(">I", data[offset : offset + 4])
            offset += 4
            if payload_len > 0 and len(data) >= offset + payload_len:
                payload_bytes = data[offset : offset + payload_len]
                if compression == GZIP_COMPRESSION:
                    try:
                        payload_bytes = gzip.decompress(payload_bytes)
                    except gzip.BadGzipFile:
                        pass
                if serialization == JSON_SERIALIZATION:
                    try:
                        parsed: dict[str, Any] = json.loads(payload_bytes)
                        result["payload"] = parsed
                    except json.JSONDecodeError:
                        result["payload_raw"] = payload_bytes.decode("utf-8", errors="replace")

        return {"kind": "event", "data": result}

    def _fallback_json_parse(
        self,
        data: bytes,
        offset: int,
        compression: int,
    ) -> dict[str, Any] | None:
        """Last-resort: try to treat the remainder as bare JSON."""
        raw = data[offset:]
        if compression == GZIP_COMPRESSION:
            try:
                raw = gzip.decompress(raw)
            except gzip.BadGzipFile:
                pass
        try:
            parsed: dict[str, Any] = json.loads(raw)
            return {"kind": "event", "data": parsed}
        except (json.JSONDecodeError, UnicodeDecodeError):
            logger.warning("TTS could not parse frame (%d bytes)", len(data))
            return None

    # ------------------------------------------------------------------
    # Header builder
    # ------------------------------------------------------------------

    @staticmethod
    def _build_header(
        message_type: int,
        flags: int,
        serialization: int,
        compression: int,
    ) -> bytes:
        """Construct the 4-byte TTS protocol header."""
        byte0 = (PROTOCOL_VERSION << 4) | HEADER_SIZE
        byte1 = (message_type << 4) | flags
        byte2 = (serialization << 4) | compression
        byte3 = 0x00
        return bytes([byte0, byte1, byte2, byte3])
