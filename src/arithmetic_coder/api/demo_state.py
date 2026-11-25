"""The demo's shared state: Alice and Bob, each with a session to the other over the same model and key."""
from __future__ import annotations

import threading

from arithmetic_coder.coding.trace import encode_with_trace
from arithmetic_coder.models.registry import ModelBankError, get_spec, load_model
from arithmetic_coder.p2p.client import UserClient

DEFAULT_KEY = "demo-key"
PREFERRED_MODELS = ("shakespeare_char", "uniform")


class UnknownCharactersError(ValueError):
    """Raised when a message contains characters outside the model's vocabulary."""

    def __init__(self, chars: list[str]):
        super().__init__(f"not in the model's vocabulary: {' '.join(repr(c) for c in chars)}")
        self.chars = chars


class DemoState:
    """Alice and Bob in one process; every send really encodes, serialises and decodes."""

    def __init__(self, model_id: str | None = None, key: str = DEFAULT_KEY):
        """Connect Alice and Bob on model_id (default: Shakespeare-GPT, or the uniform baseline)."""
        self._lock = threading.Lock()
        self.alice, self.bob = UserClient("alice"), UserClient("bob")
        self.model_id, self.key = "", key
        if model_id is None:
            model_id = next(m for m in PREFERRED_MODELS if get_spec(m).available)
        self.switch(model_id, key)

    def switch(self, model_id: str, key: str | None = None) -> None:
        """Re-create both sessions on model_id with the shared key, and check the handshake."""
        spec = get_spec(model_id)
        if not spec.available:
            raise ModelBankError(f"model {model_id!r} is listed but its files are missing")
        key = self.key if key is None else key
        model = load_model(model_id)
        with self._lock:
            for user, peer in ((self.alice, "bob"), (self.bob, "alice")):
                if peer in user.sessions:
                    user.remove_peer(peer)
            fp_alice = self.alice.register_peer("bob", model, key)
            fp_bob = self.bob.register_peer("alice", model, key)
            if not (self.alice.verify_peer_handshake("bob", fp_bob) and self.bob.verify_peer_handshake("alice", fp_alice)):
                raise RuntimeError("handshake failed after switching models")
            self.model_id, self.key = model_id, key

    def state(self) -> dict:
        """The shared session as the header shows it."""
        coder = self.alice.sessions["bob"].coder
        is_char = coder.tokenizer.kind == "char"
        return {
            "model_id": self.model_id,
            "model_name": get_spec(self.model_id).name,
            "fingerprint_hex": coder.fingerprint().hex(),
            "vocab_size": len(coder.vocab),
            "vocab": sorted(coder.vocab) if is_char else None,  # only char models restrict the text
            "tokenizer": coder.tokenizer.kind,
            "precision_bits": coder.precision_bits,
            "key": self.key,
        }

    def send(self, sender: str, text: str) -> dict:
        """Encode (with trace) on the sender's side, serialise, and really decode on the receiver's side."""
        sender_client, receiver_client = (self.alice, self.bob) if sender == "alice" else (self.bob, self.alice)
        receiver = receiver_client.user_id
        with self._lock:
            session = sender_client.sessions[receiver]
            unknown = session.coder.tokenizer.unknown_chars(text)
            if unknown:
                raise UnknownCharactersError(unknown)
            pack, trace = encode_with_trace(session.coder, text)
            frame = pack.to_bytes(session.fingerprint)
            result = receiver_client.receive_from(sender, frame)
        if result.text != text:
            raise RuntimeError("decoded text differs from the sent text")

        bits = pack.to_bits()
        payload_bytes = (len(bits) + 7) // 8
        length_end = len(frame) - payload_bytes
        original_bits = 8 * len(text.encode("utf-8"))
        return {
            "sender": sender,
            "receiver": receiver,
            "text": text,
            "decoded_text": result.text,
            "model_id": self.model_id,
            "fingerprint_hex": session.fingerprint.hex(),
            "wire_hex": frame.hex(),
            "wire_bits": "".join(format(b, "08b") for b in frame),
            "wire_layout": [
                {"name": "fingerprint", "start": 0, "end": len(session.fingerprint)},
                {"name": "length", "start": len(session.fingerprint), "end": length_end},
                {"name": "payload", "start": length_end, "end": len(frame)},
            ],
            "stats": {
                "chars": len(text),
                "symbols": pack.length,
                "original_bits": original_bits,
                "compressed_bits": len(bits),
                "wire_bytes": len(frame),
                "bpc": len(bits) / len(text) if text else 0.0,
                "bits_per_symbol": len(bits) / pack.length if pack.length else 0.0,
                "compression_ratio": original_bits / (8 * len(frame)),
            },
            "trace": trace,
        }
