"""UTF-8 byte tokenizer: 256 symbols, so any text in any language can be encoded."""
from __future__ import annotations

from arithmetic_coder.tokenizers.base import json_digest


def _label(b: int) -> str:
    """Display label of a byte: the character for printable ASCII, \\n for newline, else \\xNN."""
    if b == 10:
        return "\n"
    return chr(b) if 32 <= b < 127 else f"\\x{b:02x}"


class ByteTokenizer:
    """Each UTF-8 byte is one symbol (ids 0-255). Non-ASCII characters take 2-4 symbols."""

    kind = "bytes"
    vocab = [_label(b) for b in range(256)]
    bos_id = 10  # newline

    def encode(self, text: str) -> list[int]:
        return list(text.encode("utf-8"))

    def decode(self, ids: list[int]) -> str:
        return bytes(ids).decode("utf-8")

    def symbol_bytes(self, symbol_id: int) -> bytes:
        return bytes([symbol_id])

    def unknown_chars(self, text: str) -> list[str]:
        return []  # every string has a UTF-8 encoding (lone surrogates aside)

    def digest(self) -> bytes:
        return json_digest(self.kind, "utf-8")
