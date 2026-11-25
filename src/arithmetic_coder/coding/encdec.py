from __future__ import annotations

import hashlib
import json
import math
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from typing import TYPE_CHECKING, Iterator, NamedTuple

import numpy as np

if TYPE_CHECKING:  # type hints only, so importing the coder doesn't load torch
    from arithmetic_coder.models.wrappers import ModelWrapper, UniformModelWrapper

FINGERPRINT_SIZE = 4  # bytes of model fingerprint at the start of every wire frame
_FINGERPRINT_DOMAIN = b"arithmetic-coder/fingerprint/v1"


class EncodeStep(NamedTuple):
    """One encoding step; intervals are (L, R, s) meaning [L / 2^s, (L + R) / 2^s)."""

    index: int                     # position of the symbol in the message
    c_index: int                   # its slot in the coder's (possibly permuted) layout
    cdf: list[int]                 # integer CDF used for this step (cdf[-1] = 2**precision_bits)
    before: tuple[int, int, int]   # interval before the symbol
    after: tuple[int, int, int]    # interval after zooming into the symbol's slot
    symbol_id: int = -1            # the tokenizer's id for the symbol


def _write_varint(n: int) -> bytes:
    """Encode a non-negative int as unsigned LEB128 (7 bits per byte, high bit = more bytes follow)."""
    if n < 0:
        raise ValueError(f"varint must be non-negative, got {n}")
    out = bytearray()
    while True:
        byte, n = n & 0x7F, n >> 7
        out.append(byte | (0x80 if n else 0))
        if not n:
            return bytes(out)


def _read_varint(data: bytes, pos: int) -> tuple[int, int]:
    """Decode an unsigned LEB128 int starting at data[pos]; return (value, position after it)."""
    value, shift = 0, 0
    while True:
        if pos >= len(data):
            raise ValueError("varint runs past the end of the frame")
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        shift += 7
        if not byte & 0x80:
            return value, pos


@dataclass(frozen=True)
class MessagePack:
    r: Fraction  # dyadic rational m / 2**k inside the final interval
    length: int  # number of characters in the original message

    def to_bytes(self, fingerprint: bytes) -> bytes:
        """Serialize to the wire frame: 4-byte fingerprint + varint length + r padded to whole bytes."""
        if len(fingerprint) != FINGERPRINT_SIZE:
            raise ValueError(f"fingerprint must be {FINGERPRINT_SIZE} bytes, got {len(fingerprint)}")
        den = self.r.denominator
        if den & (den - 1) or not (0 <= self.r < 1):
            raise ValueError(f"r must be a dyadic rational in [0, 1), got {self.r}")
        k = den.bit_length() - 1
        nbytes = (k + 7) // 8
        # m / 2^k == (m << pad) / 2^(8 * nbytes), so the k field is not needed on the wire
        payload = (self.r.numerator << (8 * nbytes - k)).to_bytes(nbytes, "big")
        return fingerprint + _write_varint(self.length) + payload

    @classmethod
    def from_bytes(cls, data: bytes) -> tuple[bytes, "MessagePack"]:
        """Parse a wire frame into (fingerprint, MessagePack); raises ValueError on a malformed frame."""
        if len(data) < FINGERPRINT_SIZE + 1:
            raise ValueError(f"frame too short: {len(data)} bytes")
        fingerprint = data[:FINGERPRINT_SIZE]
        length, pos = _read_varint(data, FINGERPRINT_SIZE)
        payload = data[pos:]
        r = Fraction(int.from_bytes(payload, "big"), 1 << (8 * len(payload))) # reduces back to m / 2^k
        return fingerprint, cls(r, length)

    def to_bits(self) -> str:
        """Fractional bits of r after the binary point (e.g. 3/8 -> "011")."""
        k = self.r.denominator.bit_length() - 1
        return format(self.r.numerator, f"0{k}b") if k else ""

    @classmethod
    def from_bits(cls, bits: str, length: int) -> "MessagePack":
        """Inverse of to_bits."""
        r = Fraction(int(bits, 2), 1 << len(bits)) if bits else Fraction(0)
        return cls(r, length)


def shortest_binary_in_range(l, h) -> Fraction:
    """Return the dyadic rational m / 2**k in [l, h) with the smallest k."""

    l, h = Fraction(l), Fraction(h)
    if not (0 <= l < h <= 1):
        raise ValueError(f"need 0 <= l < h <= 1, got l={l}, h={h}")
    if l == 0:
        return Fraction(0)

    # pick K with 2^-K < h - l, so at least one K-bit fraction lies in [l, h)
    w = h - l
    K = w.denominator.bit_length() - w.numerator.bit_length() + 1

    # all K-bit fractions in [l, h) are a/2^K .. b/2^K
    a = -((-l.numerator << K) // l.denominator)     # ceil(l * 2^K)
    b = -((-h.numerator << K) // h.denominator) - 1 # ceil(h * 2^K) - 1

    # the integer in [a, b] with the most trailing zeros: keep the common
    # prefix of (a - 1) and b, then b's first differing bit, then zeros
    p = ((a - 1) ^ b).bit_length() - 1
    m = (b >> p) << p
    return Fraction(m, 1 << K) # Fraction reduction strips the trailing zeros -> minimal k


def default_precision_bits(vocab_size: int) -> int:
    """16 bits up to 256 symbols; more for big vocabularies, so the 1-count floors stay below ~0.1%."""
    return 16 if vocab_size <= 256 else math.ceil(math.log2(vocab_size)) + 10


class ArithmeticCoder:
    """Exact (integer) arithmetic coder over the symbols of a model's tokenizer."""

    def __init__(self,
                 modelwrapper: ModelWrapper | UniformModelWrapper,
                 precision_bits: int | None = None,
                 permutation: list[int] | None = None):
        """Store the model; quantize its probabilities to counts summing to 2**precision_bits.

        permutation (optional, e.g. derived from a shared key) is the order in which the symbols'
        slots are laid out along [0, 1): slot j holds symbol permutation[j].
        """
        self.modelwrapper = modelwrapper
        self.tokenizer = modelwrapper.tokenizer
        n = len(self.tokenizer.vocab)
        self.permutation = list(range(n)) if permutation is None else list(permutation)
        if sorted(self.permutation) != list(range(n)):
            raise ValueError(f"permutation must be a permutation of range({n})")
        self.slot_of = [0] * n                       # symbol id -> slot
        for slot, symbol_id in enumerate(self.permutation):
            self.slot_of[symbol_id] = slot
        self.vocab = [self.tokenizer.vocab[i] for i in self.permutation]  # slot labels, in slot order

        self.precision_bits = (precision_bits or getattr(modelwrapper, "precision_bits", None)
                               or default_precision_bits(n))
        self.total = 1 << self.precision_bits
        if n > self.total:
            raise ValueError("vocab is larger than 2**precision_bits; increase precision_bits")
        self._fingerprint: bytes | None = None

    def fingerprint(self) -> bytes:
        """Return a 4-byte digest of (model, tokenizer, slot order, precision) that both peers must share."""
        if self._fingerprint is None:
            h = hashlib.sha256(_FINGERPRINT_DOMAIN)
            h.update(self.modelwrapper.model_digest())
            h.update(self.precision_bits.to_bytes(2, "big"))
            h.update(json.dumps(self.vocab).encode("utf-8")) # slot order, so it also covers the key
            if self.tokenizer.kind != "char":  # (char models keep the fingerprints they always had)
                h.update(self.tokenizer.digest())
            self._fingerprint = h.digest()[:FINGERPRINT_SIZE]
        return self._fingerprint

    def _get_freqs(self, probs) -> np.ndarray:
        """Turn float probabilities into integer counts (each >= 1, so every symbol stays encodable) that sum to self.total."""
        freqs = np.maximum(1, np.rint(np.asarray(probs, dtype=np.float64) * self.total)).astype(np.int64)
        diff = self.total - int(freqs.sum())

        # put the rounding error on the most likely symbol (resolve ties by slot order)
        top = int(np.argmax(freqs))
        freqs[top] += diff
        if freqs[top] < 1:
            raise ValueError("could not quantize probabilities; increase precision_bits")
        return freqs

    def _get_cdf(self, prefix_ids: list[int]) -> list[int]:
        """Return the integer CDF over slots for the next symbol (cdf[0] = 0, cdf[-1] = self.total)."""
        probs = self.modelwrapper.get_probs(prefix_ids)
        if len(probs) != len(self.vocab):
            raise ValueError(f"model returned {len(probs)} probabilities for a vocab of {len(self.vocab)}")
        slot_probs = np.asarray(probs, dtype=np.float64)[self.permutation]
        return [0] + np.cumsum(self._get_freqs(slot_probs)).tolist()

    def _step(self, L, R, s, cdf, c_index):
        """Narrow the interval [L / 2^s, (L + R) / 2^s) to the sub-interval of slot c_index."""
        L = (L << self.precision_bits) + R * cdf[c_index]
        R = R * (cdf[c_index + 1] - cdf[c_index])
        return L, R, s + self.precision_bits

    def iter_encode(self, msg: str) -> Iterator[EncodeStep]:
        """Yield one EncodeStep per symbol: the CDF used and the interval before and after it.

        Raises UnknownSymbolError if the tokenizer can't represent msg.
        """
        ids = self.tokenizer.encode(msg)
        # interval is [L / 2^s, (L + R) / 2^s), all plain ints -> exact and gcd-free
        L, R, s = 0, 1, 0
        for i, symbol_id in enumerate(ids):
            slot = self.slot_of[symbol_id]
            cdf = self._get_cdf(ids[:i])
            before = (L, R, s)
            L, R, s = self._step(L, R, s, cdf, slot)
            yield EncodeStep(i, slot, cdf, before, (L, R, s), symbol_id)

    def encode(self, msg: str) -> MessagePack:
        """Encode msg as the shortest binary fraction inside its final interval, plus its symbol count."""
        L, R, s = 0, 1, 0
        count = 0
        for step in self.iter_encode(msg):
            L, R, s = step.after
            count += 1
        r = shortest_binary_in_range(Fraction(L, 1 << s), Fraction(L + R, 1 << s))
        return MessagePack(r, count)

    def decode(self, pack: MessagePack) -> str:
        """Recover the message by replaying the model and picking the sub-interval that contains pack.r."""

        r = Fraction(pack.r)
        den = r.denominator
        if den & (den - 1) or not (0 <= r < 1):
            raise ValueError(f"pack.r must be a dyadic rational in [0, 1), got {r}")
        r_num, k = r.numerator, den.bit_length() - 1 # r = r_num / 2^k

        L, R, s = 0, 1, 0
        ids: list[int] = []

        for _ in range(pack.length):

            cdf = self._get_cdf(ids)

            # x = floor(total * (r - l) / rng); exact because the cdf entries are ints:
            # cdf[j] <= total * (r - l) / rng  <=>  cdf[j] <= x
            x = ((r_num << s) - (L << k)) * self.total // (R << k)
            slot = bisect_right(cdf, x) - 1 # cdf[slot] <= x < cdf[slot + 1]

            ids.append(self.permutation[slot])

            L, R, s = self._step(L, R, s, cdf, slot)

        return self.tokenizer.decode(ids)
