"""Shared fixtures: project imports, the trained Shakespeare model, and a uniform model over its vocab."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SENTENCES = ROOT / "studies" / "01_compare_models" / "sentences.json"

sys.path.insert(0, str(ROOT))

from src.model_bank import ModelBankError, bank_vocab, load_model, load_model_uncached  # noqa: E402


def load_shakespeare():
    """Load a fresh copy of the Shakespeare nanoGPT model, or skip the test if it isn't available."""
    try:
        return load_model_uncached("shakespeare_char")
    except ModelBankError as e:
        pytest.skip(str(e))


@pytest.fixture(scope="session")
def shakespeare():
    """The shared (cached) Shakespeare model, as the chat app would use it."""
    try:
        return load_model("shakespeare_char")
    except ModelBankError as e:
        pytest.skip(str(e))


@pytest.fixture(scope="session")
def shakespeare_copy():
    """A second, independently loaded copy of the Shakespeare model (as the other peer would have)."""
    return load_shakespeare()


@pytest.fixture(scope="session")
def vocab() -> list[str]:
    """The shared 65-character vocabulary, read from the model bank (no torch needed)."""
    return bank_vocab()


@pytest.fixture(scope="session")
def uniform():
    """A uniform model over the shared vocabulary."""
    return load_model("uniform")
