"""Regression tests for the arithmetic coder and the MessagePack wire frame."""
import hashlib
import random
from fractions import Fraction

import pytest

from src.encdec import ArithmeticCoder, MessagePack, _write_varint, shortest_binary_in_range


class FakeModel:
    """Deterministic, peaked, context-dependent model with one zero-probability character."""

    def __init__(self, vocab: list[str]):
        self.vocab = list(vocab)

    def get_vocab(self) -> list[str]:
        return self.vocab

    def model_digest(self) -> bytes:
        return hashlib.sha256(b"fake").digest()

    def get_char_probs(self, prefix: str) -> list[float]:
        seed = int.from_bytes(hashlib.sha256(prefix[-3:].encode()).digest()[:4], "big")
        rnd = random.Random(seed)
        w = [rnd.random() ** 8 for _ in self.vocab]
        w[0] = 0.0
        s = sum(w)
        return [x / s for x in w]


def reference_shortest(l, h) -> Fraction:
    """Slow reference: try k = 0, 1, 2, ... bits until a k-bit fraction lands in [l, h)."""
    l, h = Fraction(l), Fraction(h)
    k = 0
    while True:
        m = -((-l.numerator << k) // l.denominator)
        if Fraction(m, 1 << k) < h:
            return Fraction(m, 1 << k)
        k += 1


@pytest.mark.parametrize("l, h, expected", [
    (0, 1, Fraction(0)),
    (0.3, 0.35, Fraction(5, 16)),
    (Fraction(2**60 - 1, 2**61), Fraction(1, 2) + Fraction(1, 2**80), Fraction(1, 2)),  # tiny range, 1 bit
    (1 - Fraction(1, 2**100), 1, 1 - Fraction(1, 2**100)),
])
def test_shortest_binary_edge_cases(l, h, expected):
    assert shortest_binary_in_range(l, h) == expected


def test_shortest_binary_matches_reference():
    rnd = random.Random(0)
    for _ in range(2000):
        d = rnd.randrange(2, 10 ** rnd.randrange(1, 30))
        a, b = sorted((Fraction(rnd.randrange(d), d), Fraction(rnd.randrange(d + 1), d)))
        if a != b:
            assert shortest_binary_in_range(a, b) == reference_shortest(a, b)


def test_shortest_binary_rejects_bad_range():
    with pytest.raises(ValueError):
        shortest_binary_in_range(0.5, 0.5)


@pytest.mark.parametrize("model_name", ["uniform", "fake"])
def test_roundtrip(model_name, vocab, uniform):
    model = uniform if model_name == "uniform" else FakeModel(vocab)
    coder = ArithmeticCoder(model)
    rnd = random.Random(1)
    messages = ["", "a", "\n\n\n", "Good morrow, cousin!\nHow now?"]
    messages += ["".join(rnd.choice(vocab) for _ in range(n)) for n in (50, 500)]
    for msg in messages:
        assert coder.decode(coder.encode(msg)) == msg


def test_unknown_character_raises(uniform):
    with pytest.raises(ValueError, match="not in vocabulary"):
        ArithmeticCoder(uniform).encode("café")


def test_bits_roundtrip(uniform):
    coder = ArithmeticCoder(uniform)
    for msg in ["", "x", "To be wed, or not."]:
        pack = coder.encode(msg)
        assert MessagePack.from_bits(pack.to_bits(), pack.length) == pack


@pytest.mark.parametrize("pack", [
    MessagePack(Fraction(0), 0),
    MessagePack(Fraction(0), 3),             # r = 0 with a non-empty message: empty payload
    MessagePack(Fraction(5, 16), 127),
    MessagePack(Fraction(3, 2**70), 128),
    MessagePack(Fraction(2**200 - 1, 2**200), 70_000),
])
def test_bytes_roundtrip(pack):
    fp = b"\x01\x02\x03\x04"
    frame = pack.to_bytes(fp)
    k = pack.r.denominator.bit_length() - 1
    assert len(frame) == 4 + len(_write_varint(pack.length)) + (k + 7) // 8
    assert MessagePack.from_bytes(frame) == (fp, pack)


@pytest.mark.parametrize("n, size", [(0, 1), (127, 1), (128, 2), (16_383, 2), (16_384, 3), (70_000, 3)])
def test_varint_sizes(n, size):
    assert len(_write_varint(n)) == size


@pytest.mark.parametrize("frame", [b"", b"abcd", b"abcd\x80", b"abcd\xff\xff"])
def test_malformed_frames(frame):
    with pytest.raises(ValueError):
        MessagePack.from_bytes(frame)


def test_to_bytes_checks_fingerprint_size():
    with pytest.raises(ValueError):
        MessagePack(Fraction(1, 2), 1).to_bytes(b"abc")


def test_fingerprint_depends_on_precision_and_vocab_order(vocab, uniform):
    from src.modelwrapper import UniformModelWrapper

    base = ArithmeticCoder(uniform).fingerprint()
    assert len(base) == 4
    assert ArithmeticCoder(UniformModelWrapper(vocab)).fingerprint() == base
    assert ArithmeticCoder(uniform, precision_bits=20).fingerprint() != base
    assert ArithmeticCoder(UniformModelWrapper(vocab[::-1])).fingerprint() != base
