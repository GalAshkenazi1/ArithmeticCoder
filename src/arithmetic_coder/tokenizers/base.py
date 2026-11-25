"""Tokenizers turn text into the symbol ids a model predicts, and back.

The coder works on symbol ids; each model brings its own tokenizer. Every tokenizer must be
lossless: decode(encode(text)) == text for any text it accepts.
"""
from __future__ import annotations

import hashlib
import json
from typing import Protocol


class UnknownSymbolError(ValueError):
    """Raised when text contains characters the tokenizer can't represent."""

    def __init__(self, chars: list[str], message: str | None = None):
        super().__init__(message or f"not in the model's vocabulary: {' '.join(repr(c) for c in chars)}")
        self.chars = chars


class Tokenizer(Protocol):
    """What the coder, models and apps need from a tokenizer."""

    kind: str           # "char", "bytes", "words", "gpt2"
    vocab: list[str]    # one display label per symbol id
    bos_id: int | None  # symbol the model sees before the first real symbol

    def encode(self, text: str) -> list[int]: ...

    def decode(self, ids: list[int]) -> str: ...

    def symbol_bytes(self, symbol_id: int) -> bytes: ...

    def unknown_chars(self, text: str) -> list[str]: ...

    def digest(self) -> bytes: ...


def json_digest(kind: str, payload) -> bytes:
    """Stable SHA-256 of a tokenizer's definition (its kind plus a JSON-serialisable payload)."""
    return hashlib.sha256(json.dumps([kind, payload], ensure_ascii=False).encode("utf-8")).digest()


def char_spans(text: str, tokenizer: Tokenizer, ids: list[int]) -> list[tuple[int, int]]:
    """For each symbol, the [start, end) range of characters of text it belongs to.

    Works for any tokenizer through the symbols' UTF-8 bytes: a symbol covering part of a multi-byte
    character (e.g. one byte of an emoji) maps to that whole character.
    """
    byte_to_char: list[int] = []
    for i, c in enumerate(text):
        byte_to_char.extend([i] * len(c.encode("utf-8")))
    spans, offset = [], 0
    for symbol_id in ids:
        size = len(tokenizer.symbol_bytes(symbol_id))
        if size == 0 or offset >= len(byte_to_char):
            spans.append((len(text), len(text)))
            continue
        first, last = byte_to_char[offset], byte_to_char[min(offset + size, len(byte_to_char)) - 1]
        spans.append((first, last + 1))
        offset += size
    return spans
