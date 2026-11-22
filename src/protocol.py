"""Relay message formats, shared by the relay and the chat client (pure stdlib, no model code).

Binary WebSocket messages carry chat frames: 1 byte id length + user id (UTF-8) + frame.
  client -> relay: the id is the recipient; relay -> client: the relay rewrites it to the sender.
Text WebSocket messages carry JSON control messages (hello / welcome / error / handshake).
"""
import json

MAX_ID_BYTES = 64


def check_id(user_id: str) -> bytes:
    """Return user_id as UTF-8, or raise ValueError if it isn't a 1-64 byte string or contains whitespace."""
    if not isinstance(user_id, str) or any(c.isspace() for c in user_id):
        raise ValueError(f"user id must be a string without whitespace, got {user_id!r}")
    raw = user_id.encode("utf-8")
    if not 1 <= len(raw) <= MAX_ID_BYTES:
        raise ValueError(f"user id must be 1-{MAX_ID_BYTES} UTF-8 bytes, got {len(raw)}")
    return raw


def pack_routed(user_id: str, frame: bytes) -> bytes:
    """Prefix a chat frame with a user id (recipient when sending, sender when delivering)."""
    raw = check_id(user_id)
    return bytes([len(raw)]) + raw + frame


def unpack_routed(data: bytes) -> tuple[str, bytes]:
    """Split a routed message into (user id, chat frame); raises ValueError if malformed."""
    if not data:
        raise ValueError("empty routed message")
    n = data[0]
    if not 1 <= n <= MAX_ID_BYTES or len(data) < 1 + n:
        raise ValueError("bad user id length in routed message")
    return data[1 : 1 + n].decode("utf-8"), data[1 + n :]


def encode_control(message: dict) -> str:
    """Serialize a control message (must have a "type" field) to JSON text."""
    if "type" not in message:
        raise ValueError("control message needs a 'type'")
    return json.dumps(message)


def decode_control(text: str) -> dict:
    """Parse a JSON control message; raises ValueError if it isn't an object with a "type"."""
    message = json.loads(text)
    if not isinstance(message, dict) or "type" not in message:
        raise ValueError("control message must be a JSON object with a 'type'")
    return message
