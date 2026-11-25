"""GPT-2's byte-level BPE tokenizer, implemented from its published vocab.json + merges.txt.

Same algorithm as OpenAI's reference encoder: split text with GPT-2's regex, map each piece's UTF-8
bytes to printable unicode stand-ins, then merge adjacent pairs by rank until no ranked pair is
left. Lossless for any text, and deterministic (pure Python, no external tokenizer library).
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

import regex

from arithmetic_coder.tokenizers.base import json_digest

PATTERN = regex.compile(r"""'s|'t|'re|'ve|'m|'ll|'d| ?\p{L}+| ?\p{N}+| ?[^\s\p{L}\p{N}]+|\s+(?!\S)|\s+""")
END_OF_TEXT = "<|endoftext|>"


@lru_cache(maxsize=1)
def bytes_to_unicode() -> dict[int, str]:
    """GPT-2's reversible map from the 256 byte values to printable unicode characters."""
    printable = list(range(ord("!"), ord("~") + 1)) + list(range(ord("\xa1"), ord("\xac") + 1)) \
        + list(range(ord("\xae"), ord("\xff") + 1))
    chars, extra = printable[:], 0
    for b in range(256):
        if b not in printable:
            printable.append(b)
            chars.append(256 + extra)
            extra += 1
    return dict(zip(printable, (chr(c) for c in chars)))


class GPT2Tokenizer:
    """50,257 symbols: 256 bytes, 50,000 merged byte sequences, and <|endoftext|> (used as BOS)."""

    kind = "gpt2"

    def __init__(self, encoder: dict[str, int], merges: list[tuple[str, str]], source_digest: bytes = b""):
        self.encoder = encoder
        self.decoder = {i: s for s, i in encoder.items()}
        self.byte_encoder = bytes_to_unicode()
        self.byte_decoder = {c: b for b, c in self.byte_encoder.items()}
        self.ranks = {pair: i for i, pair in enumerate(merges)}
        self.bos_id = encoder[END_OF_TEXT]
        self._source_digest = source_digest
        self._cache: dict[str, list[int]] = {}
        self.vocab = [self._label(i) for i in range(len(self.decoder))]

    @classmethod
    def from_files(cls, vocab_json: Path, merges_txt: Path) -> "GPT2Tokenizer":
        vocab_bytes, merges_bytes = Path(vocab_json).read_bytes(), Path(merges_txt).read_bytes()
        lines = merges_bytes.decode("utf-8").splitlines()
        merges = [tuple(line.split()) for line in lines if line and not line.startswith("#version")]
        digest = hashlib.sha256(vocab_bytes + b"\0" + merges_bytes).digest()
        return cls(json.loads(vocab_bytes), merges, digest)

    def _label(self, symbol_id: int) -> str:
        """Readable label: the token's text if it is valid UTF-8 on its own, else \\xNN bytes."""
        raw = self.symbol_bytes(symbol_id)
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError:
            return "".join(f"\\x{b:02x}" for b in raw)

    def _bpe(self, piece: str) -> list[int]:
        """Token ids of one pre-tokenized piece (already mapped to byte stand-ins)."""
        cached = self._cache.get(piece)
        if cached is not None:
            return cached
        word = list(piece)
        while len(word) > 1:
            pairs = {(word[i], word[i + 1]) for i in range(len(word) - 1)}
            best = min(pairs, key=lambda p: self.ranks.get(p, float("inf")))
            if best not in self.ranks:
                break
            merged, i = [], 0
            while i < len(word):
                if i < len(word) - 1 and (word[i], word[i + 1]) == best:
                    merged.append(word[i] + word[i + 1])
                    i += 2
                else:
                    merged.append(word[i])
                    i += 1
            word = merged
        ids = [self.encoder[token] for token in word]
        if len(self._cache) < 100_000:
            self._cache[piece] = ids
        return ids

    def encode(self, text: str) -> list[int]:
        ids: list[int] = []
        for piece in PATTERN.findall(text):
            ids.extend(self._bpe("".join(self.byte_encoder[b] for b in piece.encode("utf-8"))))
        return ids

    def decode(self, ids: list[int]) -> str:
        return b"".join(self.symbol_bytes(i) for i in ids).decode("utf-8")

    def symbol_bytes(self, symbol_id: int) -> bytes:
        token = self.decoder[symbol_id]
        if token == END_OF_TEXT:
            return b""
        return bytes(self.byte_decoder[c] for c in token)

    def unknown_chars(self, text: str) -> list[str]:
        return []

    def digest(self) -> bytes:
        return json_digest(self.kind, self._source_digest.hex())
