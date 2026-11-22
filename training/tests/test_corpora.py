"""Tests for corpus cleaning (run with: uv run --project training pytest training/tests)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # training/ (corpora.py, train.py)

from arithmetic_coder.models.registry import ASCII_VOCAB  # noqa: E402
from corpora import detokenize_wikitext, restrict  # noqa: E402
from train import RECIPES, SIZES, encode_text  # noqa: E402


def test_restrict_to_ascii():
    text = "“Café” — naïve…\tdone ✓ 日本"
    assert restrict(text, ASCII_VOCAB) == '"Cafe" - naive...    done  '


def test_restrict_to_shakespeare_vocab_maps_double_quotes():
    vocab = list("\n !',-.:;?abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
    assert restrict('He said "hi" (twice).', vocab) == "He said 'hi' twice."


def test_detokenize_wikitext():
    raw = " = Valkyria Chronicles = \n\n The game , released in 2011 , sold 1 @,@ 000 @-@ plus copies ( mostly in Japan ) . \n"
    assert detokenize_wikitext(raw) == "= Valkyria Chronicles =\nThe game, released in 2011, sold 1,000-plus copies (mostly in Japan)."


def test_encode_text_roundtrip():
    ids = encode_text("Hi!\n", ASCII_VOCAB)
    assert ids.dtype == np.uint8 and "".join(ASCII_VOCAB[i] for i in ids) == "Hi!\n"


def test_recipes_are_consistent():
    names = [r.name for r in RECIPES.values()]
    assert len(set(names)) == len(names)
    assert all(r.size in SIZES and r.vocab in ("shakespeare", "ascii") for r in RECIPES.values())
