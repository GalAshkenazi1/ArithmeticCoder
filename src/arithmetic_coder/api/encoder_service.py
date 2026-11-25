"""Encode / decode text with any model in the bank, for the encoder showcase."""
from __future__ import annotations

import threading
from collections import OrderedDict
from contextlib import contextmanager
from fractions import Fraction

from arithmetic_coder.coding.encdec import ArithmeticCoder, MessagePack
from arithmetic_coder.coding.trace import encode_with_trace
from arithmetic_coder.models.registry import ModelBankError, get_spec, load_model
from arithmetic_coder.tokenizers import UnknownSymbolError


class ServerBusy(RuntimeError):
    """A model was busy for longer than the service waits (a public server under load)."""


class EncoderService:
    """One coder per model (no key permutation: symbols keep their natural order along [0, 1)).

    Each model runs one request at a time (its own lock), but different models run side by side: a
    slow GPT-2 request never makes the small models wait. (Every model uses the same fixed torch
    thread count, so runs side by side still give bit-identical results.)

    cache_size: encode results kept (by model and text), so the examples everyone clicks are instant.
    wait_seconds: how long a request waits for its model (None: as long as it takes).
    """

    def __init__(self, cache_size: int = 256, wait_seconds: float | None = None):
        self._locks: dict[str, threading.Lock] = {}
        self._locks_lock = threading.Lock()  # guards _locks and _coders (creating them, not using them)
        self._coders: dict[str, ArithmeticCoder] = {}
        self._cache: OrderedDict[tuple[str, str], dict] = OrderedDict()
        self._cache_lock = threading.Lock()
        self.cache_size = cache_size
        self.wait_seconds = wait_seconds

    def lock_for(self, model_id: str) -> threading.Lock:
        """The lock that serialises requests to one model."""
        with self._locks_lock:
            return self._locks.setdefault(model_id, threading.Lock())

    @contextmanager
    def _model(self, model_id: str):
        """Hold model_id's lock, or raise ServerBusy after wait_seconds."""
        lock = self.lock_for(model_id)
        if not lock.acquire(timeout=-1 if self.wait_seconds is None else self.wait_seconds):
            raise ServerBusy("this encoder is busy right now; try again in a moment")
        try:
            yield
        finally:
            lock.release()

    def warm_up(self, model_ids: list[str], text: str = "Word") -> None:
        """Load each model and encode a short text once, so the first visitor doesn't wait."""
        for model_id in model_ids:
            self.encode(model_id, text)

    def coder(self, model_id: str) -> ArithmeticCoder:
        """The (cached) coder for model_id; raises ModelBankError for unknown or missing models."""
        with self._locks_lock:
            if model_id in self._coders:
                return self._coders[model_id]
        spec = get_spec(model_id)
        if not spec.available:
            raise ModelBankError(f"model {model_id!r} is listed but its files are missing")
        coder = ArithmeticCoder(load_model(model_id))  # load_model is cached, so a race only builds a wrapper twice
        with self._locks_lock:
            return self._coders.setdefault(model_id, coder)

    def encode(self, model_id: str, text: str) -> dict:
        """Encode text with a step-by-step trace; raises UnknownSymbolError for unencodable text."""
        key = (model_id, text)
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        result = self._encode(model_id, text)
        with self._cache_lock:
            self._cache[key] = result
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return result

    def _encode(self, model_id: str, text: str) -> dict:
        with self._model(model_id):
            coder = self.coder(model_id)
            unknown = coder.tokenizer.unknown_chars(text)
            if unknown:
                raise UnknownSymbolError(unknown)
            pack, trace = encode_with_trace(coder, text)
        bits = pack.to_bits()
        utf8_bits = 8 * len(text.encode("utf-8"))
        return {
            "model_id": model_id,
            "model_name": get_spec(model_id).name,
            "tokenizer": coder.tokenizer.kind,
            "precision_bits": coder.precision_bits,
            "text": text,
            "bits": bits,
            "symbols": pack.length,
            "stats": {
                "chars": len(text),
                "symbols": pack.length,
                "payload_bits": len(bits),
                "payload_bytes": (len(bits) + 7) // 8,
                "utf8_bits": utf8_bits,
                "bpc": len(bits) / len(text) if text else 0.0,
                "bits_per_symbol": len(bits) / pack.length if pack.length else 0.0,
                "ratio": utf8_bits / len(bits) if bits else 0.0,
            },
            "trace": trace,
        }

    def decode(self, model_id: str, bits: str, symbols: int) -> str:
        """Decode payload bits (the fraction's binary digits) back into text."""
        r = Fraction(int(bits, 2), 1 << len(bits)) if bits else Fraction(0)
        with self._model(model_id):
            return self.coder(model_id).decode(MessagePack(r, symbols))
