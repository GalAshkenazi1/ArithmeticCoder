"""Key-derived permutation of the symbol slots: peers sharing a key lay out [0, 1) the same secret way."""
from __future__ import annotations

import hashlib
from typing import Iterator

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


def keyed_coder(model, key: bytes | str, precision_bits: int | None = None):
    """An ArithmeticCoder whose symbol slots are laid out in the order derived from a shared key."""
    from arithmetic_coder.coding.encdec import ArithmeticCoder

    return ArithmeticCoder(model, precision_bits, derive_permutation(key, len(model.tokenizer.vocab)))
