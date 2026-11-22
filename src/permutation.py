from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING, Iterator

if TYPE_CHECKING:  # type hints only, so importing this module doesn't load torch
    from src.modelwrapper import ModelWrapper

_DOMAIN = b"arithmetic-coder/permutation/v1"


def _byte_stream(key: bytes, n: int) -> Iterator[int]:
    """Yield an endless deterministic byte stream: SHA-256 in counter mode over a key-derived seed."""
    seed = hashlib.sha256(_DOMAIN + n.to_bytes(8, "big") + key).digest()
    counter = 0
    while True:
        yield from hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
        counter += 1


def _uniform_below(stream: Iterator[int], m: int) -> int:
    """Draw a uniform integer in [0, m) from the byte stream using rejection sampling."""
    bits = (m - 1).bit_length()
    nbytes = (bits + 7) // 8
    while True:
        x = int.from_bytes(bytes(next(stream) for _ in range(nbytes)), "big") & ((1 << bits) - 1)
        if x < m:
            return x


def derive_permutation(key: bytes | str, n: int) -> list[int]:
    """Derive a uniformly random permutation of range(n) from a shared key, identically on every platform."""
    if isinstance(key, str):
        key = key.encode("utf-8")
    stream = _byte_stream(key, n)
    perm = list(range(n))
    for i in range(n - 1, 0, -1):  # Fisher-Yates
        j = _uniform_below(stream, i + 1)
        perm[i], perm[j] = perm[j], perm[i]
    return perm


class PermutedModel:
    """Wraps a char model so its vocab and probabilities come out in a secret (permuted) slot order."""

    def __init__(self, 
                 inner: ModelWrapper, 
                 perm: list[int]):
        """Store the inner model and the permutation (slot i holds the inner model's character perm[i])."""
        inner_vocab = inner.get_vocab()
        if sorted(perm) != list(range(len(inner_vocab))):
            raise ValueError(f"perm must be a permutation of range({len(inner_vocab)})")
        self.inner = inner
        self.perm = list(perm)
        self.vocab = [inner_vocab[j] for j in self.perm]

    @classmethod
    def from_key(cls, 
                 inner: ModelWrapper, 
                 key: bytes | str) -> "PermutedModel":
        """Build a PermutedModel whose permutation is derived from the users' shared key."""
        return cls(inner, derive_permutation(key, len(inner.get_vocab())))

    def get_vocab(self) -> list[str]:
        """Return the vocabulary in permuted slot order."""
        return self.vocab

    def model_digest(self) -> bytes:
        """Return the inner model's digest (the permutation shows up in the vocab order the coder hashes)."""
        return self.inner.model_digest()

    def get_char_probs(self, prefix: str) -> list[float]:
        """Return the inner model's next-char probabilities in permuted slot order."""
        p = self.inner.get_char_probs(prefix)
        return [p[j] for j in self.perm]
