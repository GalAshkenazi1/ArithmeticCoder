"""In-memory loopback tests: Alice talks to Bob (Shakespeare model) and to Charlie (uniform model)."""
import json

import pytest
from conftest import SENTENCES

from src.client import (
    CorruptedPayloadError,
    ModelMismatchError,
    PeerNotFoundError,
    UserClient,
)
from src.encdec import MessagePack

KEY_BOB = "alice+bob shared key"
KEY_CHARLIE = b"alice+charlie shared key"


def varint_len(n: int) -> int:
    """Number of bytes in the LEB128 encoding of n."""
    return max(1, (n.bit_length() + 6) // 7)


@pytest.fixture
def users(shakespeare, shakespeare_copy, uniform):
    """Alice-Bob over Shakespeare (each side loads its own copy), Alice-Charlie over uniform."""
    alice, bob, charlie = UserClient("alice"), UserClient("bob"), UserClient("charlie")
    fp_ab = alice.register_peer("bob", shakespeare, KEY_BOB)
    fp_ba = bob.register_peer("alice", shakespeare_copy, KEY_BOB)
    fp_ac = alice.register_peer("charlie", uniform, KEY_CHARLIE)
    fp_ca = charlie.register_peer("alice", uniform, KEY_CHARLIE)
    assert alice.verify_peer_handshake("bob", fp_ba) and bob.verify_peer_handshake("alice", fp_ab)
    assert alice.verify_peer_handshake("charlie", fp_ca) and charlie.verify_peer_handshake("alice", fp_ac)
    return alice, bob, charlie


@pytest.mark.parametrize("text", [
    "",
    "a",
    "Good morrow, gentle cousin.\n\nThe sun hath risen fair upon our house;\nand yet I weep.\n",
    "Hark!? What -- ho; who's there: 3 knaves & a $ purse... Fie!",
])
def test_exact_roundtrip_both_directions(users, text):
    alice, bob, _ = users
    payload = alice.send_to("bob", text)
    result = bob.receive_from("alice", payload)
    assert result.text == text
    assert result.original_bytes == len(text.encode("utf-8"))
    assert result.compressed_bytes == len(payload)
    assert alice.receive_from("bob", bob.send_to("alice", text)).text == text


def test_multi_peer_isolation(users):
    alice, bob, charlie = users
    with pytest.raises(ModelMismatchError):
        charlie.receive_from("alice", alice.send_to("bob", "This was meant for Bob."))
    with pytest.raises(ModelMismatchError):
        bob.receive_from("alice", alice.send_to("charlie", "This was meant for Charlie."))


def test_same_model_different_key_is_rejected(shakespeare):
    alice, eve = UserClient("alice"), UserClient("eve")
    fp_alice = alice.register_peer("bob", shakespeare, KEY_BOB)
    fp_eve = eve.register_peer("alice", shakespeare, "a guessed key")
    assert fp_alice != fp_eve
    assert not eve.verify_peer_handshake("alice", fp_alice)
    with pytest.raises(ModelMismatchError):
        eve.receive_from("alice", alice.send_to("bob", "Secrets for Bob only."))


def test_wire_size(users):
    alice, bob, _ = users
    long_text = "My lord, I pray thee, speak not so of love, for love is but a fever of the blood. " * 3
    for text in ["", "a", "Away, away! The watch is coming.", long_text]:
        payload = alice.send_to("bob", text)
        _, pack = MessagePack.from_bytes(payload)
        k = pack.r.denominator.bit_length() - 1
        assert len(payload) == 4 + varint_len(len(text)) + (k + 7) // 8
        assert bob.receive_from("alice", payload).text == text
    assert varint_len(len(long_text)) == 2


def test_shakespeare_beats_uniform(users):
    alice, _, _ = users
    sentences = json.loads(SENTENCES.read_text(encoding="utf-8"))["sentences"][:10]
    chars = sum(map(len, sentences))

    def payload_bits(peer: str) -> int:
        total = 0
        for text in sentences:
            _, pack = MessagePack.from_bytes(alice.send_to(peer, text))
            total += pack.r.denominator.bit_length() - 1
        return total

    bpc_shakespeare = payload_bits("bob") / chars
    bpc_uniform = payload_bits("charlie") / chars
    assert bpc_shakespeare < 0.6 * bpc_uniform, (bpc_shakespeare, bpc_uniform)


def test_errors(users):
    alice, bob, _ = users
    for call in (lambda: alice.send_to("dave", "hi"),
                 lambda: alice.receive_from("dave", b"\x00" * 8),
                 lambda: alice.verify_peer_handshake("dave", b"\x00" * 4)):
        with pytest.raises(PeerNotFoundError):
            call()
    fingerprint = alice.sessions["bob"].fingerprint
    for frame in (b"", b"\x01\x02", fingerprint + b"\x80"):
        with pytest.raises(CorruptedPayloadError):
            bob.receive_from("alice", frame)
    with pytest.raises(ValueError, match="already has a session"):
        alice.register_peer("bob", alice.sessions["bob"].coder.modelwrapper.inner, KEY_BOB)
