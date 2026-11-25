"""Word tokenizer with a byte escape: frequent words are single symbols, everything else is spelled out.

Symbol ids 0-255 are raw UTF-8 bytes (the escape), followed by N whole words such as " the", "The"
or " said" (with an optional leading space). Encoding splits text into pieces - an optional space
plus a run of letters, or any single character - and emits a word symbol when the piece is in the
word list, otherwise the piece's bytes. Any text can be encoded; unknown words just cost more.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from arithmetic_coder.tokenizers.base import json_digest
from arithmetic_coder.tokenizers.bytes import ByteTokenizer

# an optional space followed by letters (any script, no digits/underscore), or any single character
PIECE = re.compile(r" ?[^\W\d_]+|.", re.DOTALL)


class WordTokenizer:
    """256 byte symbols plus a fixed list of whole words."""

    kind = "words"
    bos_id = 10  # newline byte

    def __init__(self, words: list[str]):
        self.words = list(words)
        if len(set(self.words)) != len(self.words):
            raise ValueError("word list has duplicates")
        bad = [w for w in self.words if PIECE.fullmatch(w) is None or len(w) < 2]
        if bad:
            raise ValueError(f"not single word pieces: {bad[:5]}")
        self.vocab = list(ByteTokenizer.vocab) + self.words
        self.word_index = {w: 256 + i for i, w in enumerate(self.words)}

    @classmethod
    def from_file(cls, path: Path) -> "WordTokenizer":
        return cls(json.loads(Path(path).read_text(encoding="utf-8"))["words"])

    def to_file(self, path: Path, **metadata) -> None:
        Path(path).write_text(json.dumps({"words": self.words, **metadata}, ensure_ascii=False, indent=1),
                              encoding="utf-8")

    def encode(self, text: str) -> list[int]:
        ids: list[int] = []
        for match in PIECE.finditer(text):
            piece = match.group()
            symbol = self.word_index.get(piece)
            if symbol is not None:
                ids.append(symbol)
            else:
                ids.extend(piece.encode("utf-8"))  # escape: spell the piece out byte by byte
        return ids

    def decode(self, ids: list[int]) -> str:
        return b"".join(self.symbol_bytes(i) for i in ids).decode("utf-8")

    def symbol_bytes(self, symbol_id: int) -> bytes:
        return bytes([symbol_id]) if symbol_id < 256 else self.words[symbol_id - 256].encode("utf-8")

    def unknown_chars(self, text: str) -> list[str]:
        return []

    def digest(self) -> bytes:
        return json_digest(self.kind, self.words)


def build_word_list(text: str, size: int) -> list[str]:
    """The `size` most frequent multi-character word pieces of text (ties broken alphabetically)."""
    counts: dict[str, int] = {}
    for match in PIECE.finditer(text):
        piece = match.group()
        if len(piece) >= 2 and piece.strip():
            counts[piece] = counts.get(piece, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [w for w, _ in ranked[:size] if PIECE.fullmatch(w) and len(w) >= 2]
