from __future__ import annotations

import hashlib
import json
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from itertools import accumulate
from typing import TYPE_CHECKING, Iterator, NamedTuple

if TYPE_CHECKING:  # type hints only, so importing the coder doesn't load torch
    from arithmetic_coder.coding.permutation import PermutedModel
    from arithmetic_coder.models.wrappers import ModelWrapper, UniformModelWrapper

FINGERPRINT_SIZE = 4  # bytes of model fingerprint at the start of every wire frame
_FINGERPRINT_DOMAIN = b"arithmetic-coder/fingerprint/v1"


class EncodeStep(NamedTuple):
    """One encoding step; intervals are (L, R, s) meaning [L / 2^s, (L + R) / 2^s)."""

    index: int                     # position of the character in the message
    c_index: int                   # its slot in the coder's (possibly permuted) vocab
    cdf: list[int]                 # integer CDF used for this step (cdf[-1] = 2**precision_bits)
    before: tuple[int, int, int]   # interval before the character
    after: tuple[int, int, int]    # interval after zooming into the character's slot


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


class ArithmeticCoder:
    """Exact (integer) arithmetic coder driven by a character-level language model."""

    def __init__(self,
                 modelwrapper: ModelWrapper | UniformModelWrapper | PermutedModel,
                 precision_bits: int = 16):
        """Store the model and quantize its probabilities to counts summing to 2**precision_bits."""

        self.modelwrapper = modelwrapper           # nanoGPT model wrapper (char-level gentext)
        self.vocab = self.modelwrapper.get_vocab() # list of characters in the vocabulary, in order
        self.char_to_idx = {c: i for i, c in enumerate(self.vocab)}

        self.precision_bits = precision_bits
        self.total = 1 << precision_bits
        if len(self.vocab) > self.total:
            raise ValueError("vocab is larger than 2**precision_bits; increase precision_bits")
        self._fingerprint: bytes | None = None

    def fingerprint(self) -> bytes:
        """Return a 4-byte digest of (model weights, vocab order, precision) that both peers must share."""
        if self._fingerprint is None:
            h = hashlib.sha256(_FINGERPRINT_DOMAIN)
            h.update(self.modelwrapper.model_digest())
            h.update(self.precision_bits.to_bytes(2, "big"))
            h.update(json.dumps(self.vocab).encode("utf-8")) # permuted order, so it also covers the key
            self._fingerprint = h.digest()[:FINGERPRINT_SIZE]
        return self._fingerprint

    def _get_freqs(self, char_probs) -> list:
        """Turn float probabilities into integer counts (each >= 1, so every char stays encodable) that sum to self.total."""
        freqs = [max(1, round(p * self.total)) for p in char_probs]
        diff = self.total - sum(freqs)

        # put the rounding error on the most likely symbol (resolve ties by index order)
        top = freqs.index(max(freqs))
        freqs[top] += diff
        if freqs[top] < 1:
            raise ValueError("could not quantize probabilities; increase precision_bits")
        return freqs

    def _get_cdf(self, prefix: str) -> list:
        """Return the integer CDF for the next char after prefix (cdf[0] = 0, cdf[-1] = self.total)."""
        probs = self.modelwrapper.get_char_probs(prefix)
        if len(probs) != len(self.vocab):
            raise ValueError(f"model returned {len(probs)} probabilities for a vocab of {len(self.vocab)}")
        return list(accumulate([0] + self._get_freqs(probs)))

    def _step(self, L, R, s, cdf, c_index):
        """Narrow the interval [L / 2^s, (L + R) / 2^s) to the sub-interval of c_index."""
        L = (L << self.precision_bits) + R * cdf[c_index]
        R = R * (cdf[c_index + 1] - cdf[c_index])
        return L, R, s + self.precision_bits

    def iter_encode(self, msg: str) -> Iterator[EncodeStep]:
        """Yield one EncodeStep per character: the CDF used and the interval before and after it."""

        # interval is [L / 2^s, (L + R) / 2^s), all plain ints -> exact and gcd-free
        L, R, s = 0, 1, 0
        for i, c in enumerate(msg):
            c_index = self.char_to_idx.get(c) # index of the character in the vocabulary
            if c_index is None:
                raise ValueError(f"Character {c!r} at position {i} not in vocabulary")
            cdf = self._get_cdf(msg[:i])
            before = (L, R, s)
            L, R, s = self._step(L, R, s, cdf, c_index)
            yield EncodeStep(i, c_index, cdf, before, (L, R, s))

    def encode(self, msg: str) -> MessagePack:
        """Encode msg as the shortest binary fraction inside its final interval, plus its length."""
        L, R, s = 0, 1, 0
        for step in self.iter_encode(msg):
            L, R, s = step.after
        r = shortest_binary_in_range(Fraction(L, 1 << s), Fraction(L + R, 1 << s))
        return MessagePack(r, len(msg))


    def decode(self, pack: MessagePack) -> str:
        """Recover the message by replaying the model and picking the sub-interval that contains pack.r."""

        r = Fraction(pack.r)
        den = r.denominator
        if den & (den - 1) or not (0 <= r < 1):
            raise ValueError(f"pack.r must be a dyadic rational in [0, 1), got {r}")
        r_num, k = r.numerator, den.bit_length() - 1 # r = r_num / 2^k

        L, R, s = 0, 1, 0
        decoded_msg = ""

        for _ in range(pack.length):

            cdf = self._get_cdf(decoded_msg)

            # x = floor(total * (r - l) / rng); exact because the cdf entries are ints:
            # cdf[j] <= total * (r - l) / rng  <=>  cdf[j] <= x
            x = ((r_num << s) - (L << k)) * self.total // (R << k)
            c_index = bisect_right(cdf, x) - 1 # cdf[c_index] <= x < cdf[c_index + 1]

            decoded_msg += self.vocab[c_index]

            L, R, s = self._step(L, R, s, cdf, c_index)

        return decoded_msg
