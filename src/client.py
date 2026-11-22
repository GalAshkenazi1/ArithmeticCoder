"""Peer-to-peer chat layer: one immutable codec session per peer, compact binary wire frames.

Each pair of peers shares a base model and a secret key. The key derives a PermutedModel, so
every session has its own slot order. Frames start with a 4-byte fingerprint of the session's
model, so a payload sent over the wrong session fails fast instead of decoding to garbage.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.encdec import ArithmeticCoder, MessagePack
from src.permutation import PermutedModel

if TYPE_CHECKING:
    from src.modelwrapper import ModelWrapper, UniformModelWrapper

    BaseModel = ModelWrapper | UniformModelWrapper


class PeerNotFoundError(KeyError):
    """Raised when a user has no session registered for the given peer id."""


class ModelMismatchError(ValueError):
    """Raised when a frame's fingerprint doesn't match the receiving session's model."""


class CorruptedPayloadError(ValueError):
    """Raised when a frame can't be parsed (too short, or a broken length field)."""


@dataclass(frozen=True)
class DecodedResult:
    """A received message plus its size statistics."""

    text: str
    original_bytes: int   # UTF-8 size of the text
    compressed_bytes: int  # size of the whole wire frame, header included
    bits_per_char: float   # payload bits (k) per character, 0.0 for an empty message


@dataclass(frozen=True)
class PeerSession:
    """The dedicated, immutable codec link between the local user and one peer."""

    peer_id: str
    coder: ArithmeticCoder
    fingerprint: bytes
    key: bytes | str = field(repr=False)

    @classmethod
    def create(cls, peer_id: str, base_model: BaseModel, key: bytes | str, precision_bits: int = 16) -> PeerSession:
        """Build the session's coder from the shared base model and key."""
        coder = ArithmeticCoder(PermutedModel.from_key(base_model, key), precision_bits)
        return cls(peer_id, coder, coder.fingerprint(), key)

    def pack_message(self, msg: str) -> bytes:
        """Encode msg and serialize it into a wire frame."""
        return self.coder.encode(msg).to_bytes(self.fingerprint)

    def unpack_message(self, payload: bytes) -> DecodedResult:
        """Check and parse a wire frame, then decode it back to text."""
        try:
            fingerprint, pack = MessagePack.from_bytes(payload)
        except ValueError as e:
            raise CorruptedPayloadError(str(e)) from e
        if fingerprint != self.fingerprint:
            raise ModelMismatchError(
                f"frame fingerprint {fingerprint.hex()} != session fingerprint {self.fingerprint.hex()} "
                f"(peer {self.peer_id!r})"
            )
        text = self.coder.decode(pack)
        k = pack.r.denominator.bit_length() - 1
        return DecodedResult(
            text=text,
            original_bytes=len(text.encode("utf-8")),
            compressed_bytes=len(payload),
            bits_per_char=k / len(text) if text else 0.0,
        )


class UserClient:
    """A user and their independent sessions, one per connected peer."""

    def __init__(self, user_id: str):
        """Create a user with no peers yet."""
        self.user_id = user_id
        self.sessions: dict[str, PeerSession] = {}

    def _session(self, peer_id: str) -> PeerSession:
        """Return the session for peer_id, or raise PeerNotFoundError."""
        try:
            return self.sessions[peer_id]
        except KeyError:
            raise PeerNotFoundError(f"{self.user_id!r} has no session with {peer_id!r}") from None

    def register_peer(self, peer_id: str, base_model: BaseModel, key: bytes | str, precision_bits: int = 16) -> bytes:
        """Create the session with peer_id and return its fingerprint for the handshake."""
        if peer_id in self.sessions:
            raise ValueError(f"{self.user_id!r} already has a session with {peer_id!r}; sessions are immutable")
        session = PeerSession.create(peer_id, base_model, key, precision_bits)
        self.sessions[peer_id] = session
        return session.fingerprint

    def remove_peer(self, peer_id: str) -> None:
        """Forget the session with peer_id (raises PeerNotFoundError if there is none)."""
        self._session(peer_id)
        del self.sessions[peer_id]

    def verify_peer_handshake(self, peer_id: str, peer_fingerprint: bytes) -> bool:
        """Return True if the peer's fingerprint matches our session with them (same model, key, precision)."""
        return self._session(peer_id).fingerprint == peer_fingerprint

    def send_to(self, peer_id: str, text: str) -> bytes:
        """Encode text for peer_id and return the wire frame."""
        return self._session(peer_id).pack_message(text)

    def receive_from(self, peer_id: str, payload: bytes) -> DecodedResult:
        """Decode a wire frame received from peer_id."""
        return self._session(peer_id).unpack_message(payload)
