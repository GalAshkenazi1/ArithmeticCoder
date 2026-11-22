"""Tests for the relay message formats."""
import pytest

from src.protocol import MAX_ID_BYTES, decode_control, encode_control, pack_routed, unpack_routed


@pytest.mark.parametrize("user_id, frame", [("bob", b"\x01\x02\x03"), ("b", b""), ("x" * MAX_ID_BYTES, b"\xff" * 300)])
def test_routed_roundtrip(user_id, frame):
    assert unpack_routed(pack_routed(user_id, frame)) == (user_id, frame)


@pytest.mark.parametrize("bad_id", ["", "x" * (MAX_ID_BYTES + 1), "two words", 42])
def test_bad_ids_rejected(bad_id):
    with pytest.raises(ValueError):
        pack_routed(bad_id, b"frame")


@pytest.mark.parametrize("data", [b"", b"\x00abc", b"\x05ab", bytes([MAX_ID_BYTES + 1]) + b"x" * 80])
def test_malformed_routed(data):
    with pytest.raises(ValueError):
        unpack_routed(data)


def test_control_roundtrip():
    message = {"type": "handshake", "to": "bob", "fingerprint": "7868e2ce", "reply": False}
    assert decode_control(encode_control(message)) == message


@pytest.mark.parametrize("text", ["[1, 2]", '{"no": "type"}', "not json"])
def test_bad_control(text):
    with pytest.raises(ValueError):
        decode_control(text)
