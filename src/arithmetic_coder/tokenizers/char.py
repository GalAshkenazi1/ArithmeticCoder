"""Character tokenizer: one symbol per character from a fixed vocabulary (the original behaviour)."""
from __future__ import annotations

from arithmetic_coder.tokenizers.base import UnknownSymbolError, json_digest


class CharTokenizer:
    """Each character of a fixed vocabulary is one symbol; anything else can't be encoded."""

    kind = "char"

    def __init__(self, vocab: list[str], bos_char: str | None = "\n"):
        """vocab: the characters in symbol-id order. bos_char: the start symbol (must be in vocab)."""
        self.vocab = list(vocab)
        self.index = {c: i for i, c in enumerate(self.vocab)}
        if len(self.index) != len(self.vocab):
            raise ValueError("character vocabulary has duplicates")
        if bos_char is not None and bos_char not in self.index:
            raise ValueError(f"BOS character {bos_char!r} must exist in the vocabulary.")
        self.bos_id = self.index.get(bos_char) if bos_char is not None else None

    def encode(self, text: str) -> list[int]:
        ids = []
        for i, c in enumerate(text):
            symbol = self.index.get(c)
            if symbol is None:
                unknown = self.unknown_chars(text)
                raise UnknownSymbolError(unknown, f"Character {c!r} at position {i} not in vocabulary")
            ids.append(symbol)
        return ids

    def decode(self, ids: list[int]) -> str:
        return "".join(self.vocab[i] for i in ids)

    def symbol_bytes(self, symbol_id: int) -> bytes:
        return self.vocab[symbol_id].encode("utf-8")

    def unknown_chars(self, text: str) -> list[str]:
        return sorted({c for c in text if c not in self.index})

    def digest(self) -> bytes:
        return json_digest(self.kind, self.vocab)
