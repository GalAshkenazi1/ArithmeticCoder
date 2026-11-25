"""Shared study data: held-out text from each corpus, and the real coder's cost for every character.

char_costs() runs encode_with_trace, the same steps encode() uses, so each character's numbers are
the real coder's:  prob = the quantised probability it used (ideal cost -log2 prob), and
bits_added = how much the payload actually grew. Results are cached in studies/_cache/.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

STUDIES = Path(__file__).resolve().parents[1]
ROOT = STUDIES.parent
CACHE = STUDIES / "_cache"
sys.path.insert(0, str(ROOT / "training"))

from arithmetic_coder import ArithmeticCoder, load_model  # noqa: E402
from arithmetic_coder.coding.trace import encode_with_trace  # noqa: E402
from corpora import load_corpus  # noqa: E402

# (corpus, vocabulary its cleaned text was cached with, label)
CORPORA = [
    ("shakespeare", "shakespeare", "Shakespeare"),
    ("gutenberg", "shakespeare", "Gutenberg novels"),
    ("wikitext", "ascii", "Wikipedia"),
    ("tinystories", "ascii", "TinyStories"),
    ("c4", "ascii", "Web (C4)"),
    ("python", "ascii", "Python code"),
]
# each trained model's own kind of text
OWN_TEXT = {
    "shakespeare_char": "Shakespeare", "english_char": "Gutenberg novels", "wiki_small": "Wikipedia",
    "stories_small": "TinyStories", "web_small": "Web (C4)", "python_small": "Python code",
}
MODEL_NAMES = {
    "shakespeare_char": "Shakespeare-GPT", "english_char": "English-GPT", "wiki_small": "Wiki-GPT",
    "stories_small": "TinyStories-GPT", "web_small": "Web-GPT", "python_small": "Python-GPT",
    "uniform_ascii": "Uniform ASCII", "web_bytes": "Web-Bytes", "wiki_bytes": "Wiki-Bytes",
    "web_words": "Web-Words", "gpt2": "GPT-2 (124M)", "uniform_bytes": "Uniform Bytes",
}

CharCost = tuple[str, float, int]  # (char, prob used by the coder, bits the payload grew by)


def held_out_snippets(corpus: str, vocab_kind: str, n: int = 12, length: int = 250) -> list[str]:
    """n evenly spaced snippets from the validation split (last 10%), each starting at a line start."""
    text = load_corpus(corpus, vocab_kind)
    val = text[int(0.9 * len(text)):]
    step = (len(val) - 2 * length) // n
    snippets = []
    for i in range(n):
        start = val.find("\n", i * step) + 1  # begin at a line start, like a real message
        snippets.append(val[start: start + length].strip())
    return snippets


def char_costs(model_id: str, texts: list[str]) -> list[list[CharCost] | None]:
    """Per-character costs of each text under model_id (None where the vocabulary can't encode it)."""
    key = hashlib.sha256(json.dumps([model_id, texts]).encode()).hexdigest()[:16]
    path = CACHE / f"{model_id}-{key}.json"
    if path.exists():
        return [None if t is None else [tuple(c) for c in t] for t in json.loads(path.read_text(encoding="utf-8"))]
    coder = ArithmeticCoder(load_model(model_id))
    out: list[list[CharCost] | None] = []
    for text in texts:
        if coder.tokenizer.unknown_chars(text):
            out.append(None)
            continue
        _, trace = encode_with_trace(coder, text, top_n=1)
        out.append([(s["char"], s["prob"], s["bits_added"]) for s in trace])
    CACHE.mkdir(exist_ok=True)
    path.write_text(json.dumps(out), encoding="utf-8")
    return out


SymbolCost = tuple[str, int, int, float, int]  # (symbol label, char_start, char_end, prob, bits_added)


def symbol_costs(model_id: str, texts: list[str]) -> list[list[SymbolCost] | None]:
    """Like char_costs, but per symbol of the model's tokenizer, with each symbol's character span."""
    key = hashlib.sha256(json.dumps(["symbols", model_id, texts]).encode()).hexdigest()[:16]
    path = CACHE / f"sym-{model_id}-{key}.json"
    if path.exists():
        return [None if t is None else [tuple(c) for c in t] for t in json.loads(path.read_text(encoding="utf-8"))]
    coder = ArithmeticCoder(load_model(model_id))
    out: list[list[SymbolCost] | None] = []
    for text in texts:
        if coder.tokenizer.unknown_chars(text):
            out.append(None)
            continue
        _, trace = encode_with_trace(coder, text, top_n=1)
        out.append([(s["symbol"], s["char_start"], s["char_end"], s["prob"], s["bits_added"]) for s in trace])
    CACHE.mkdir(exist_ok=True)
    path.write_text(json.dumps(out), encoding="utf-8")
    return out


def cost(prob: float) -> float:
    """Ideal cost of a character in bits: -log2 of the probability the coder used."""
    return -math.log2(prob)


CHAR_CLASSES = ["lowercase", "Uppercase", "digit", "space", "newline", "punctuation", "brackets & symbols"]


def char_class(c: str) -> str:
    """Coarse class of a character, for 'which characters are expensive' breakdowns."""
    if c.islower():
        return "lowercase"
    if c.isupper():
        return "Uppercase"
    if c.isdigit():
        return "digit"
    if c == " ":
        return "space"
    if c == "\n":
        return "newline"
    if c in ".,;:!?'\"-":
        return "punctuation"
    return "brackets & symbols"
