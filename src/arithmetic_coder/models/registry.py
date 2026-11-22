"""Model registry: discover the models in model_bank/ by folder, with readable names, and load them by id.

A model is a folder  model_bank/<id>/  containing:
    ckpt.pt     nanoGPT checkpoint
    meta.pkl    vocabulary (itos)
    model.json  {"name": "Shakespeare-GPT", "description": "...", "kind": "nanogpt"}
Add a model by dropping such a folder into the bank, importing one (arith-import-model), or training
one (training/train.py). The built-in uniform baselines need no files. Set ARITH_MODEL_BANK to use a
bank somewhere else.
"""
from __future__ import annotations

import json
import os
import pickle
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from arithmetic_coder.models.wrappers import ModelWrapper, UniformModelWrapper

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_BANK = REPO_ROOT / "model_bank"
VOCAB_SOURCE = "shakespeare_char"  # the "uniform" baseline uses this model's vocabulary
UNIFORM_ID = "uniform"
UNIFORM_ASCII_ID = "uniform_ascii"

# vocabulary of the ASCII models: newline + every printable ASCII character (96 symbols)
ASCII_VOCAB: list[str] = ["\n"] + [chr(i) for i in range(32, 127)]


class ModelBankError(RuntimeError):
    """Raised when a model id is unknown or its files are missing."""


@dataclass(frozen=True)
class ModelSpec:
    """What the registry knows about one model."""

    id: str
    name: str
    description: str
    kind: str          # "nanogpt" or "uniform"
    path: Path | None  # model folder (None for the built-in uniform model)
    vocab_size: int
    available: bool    # False if files are missing (listed, but can't be loaded)


def bank_dir() -> Path:
    """Return the model bank folder (ARITH_MODEL_BANK, or the repo's model_bank/)."""
    return Path(os.environ.get("ARITH_MODEL_BANK", DEFAULT_BANK))


def _read_vocab(folder: Path) -> list[str]:
    """Read a model folder's vocabulary from meta.pkl."""
    with open(folder / "meta.pkl", "rb") as f:
        itos = pickle.load(f)["itos"]
    return [itos[i] for i in range(len(itos))]


def bank_vocab(model_id: str = VOCAB_SOURCE) -> list[str]:
    """Return a bank model's vocabulary in order (no torch needed)."""
    folder = bank_dir() / model_id
    if not (folder / "meta.pkl").exists():
        raise ModelBankError(f"missing {folder / 'meta.pkl'}")
    return _read_vocab(folder)


def _spec_from_folder(folder: Path) -> ModelSpec:
    """Build a spec from a model folder's model.json (missing files make it unavailable)."""
    info = json.loads((folder / "model.json").read_text(encoding="utf-8"))
    has_files = (folder / "ckpt.pt").exists() and (folder / "meta.pkl").exists()
    return ModelSpec(
        id=folder.name,
        name=info.get("name", folder.name),
        description=info.get("description", ""),
        kind=info.get("kind", "nanogpt"),
        path=folder,
        vocab_size=len(_read_vocab(folder)) if has_files else 0,
        available=has_files,
    )


def _uniform_vocab(model_id: str) -> list[str]:
    """Vocabulary of a built-in uniform model."""
    return list(ASCII_VOCAB) if model_id == UNIFORM_ASCII_ID else bank_vocab()


def _uniform_specs() -> list[ModelSpec]:
    """The built-in uniform baselines: over the 65-char Shakespeare vocab, and over printable ASCII."""
    try:
        size = len(bank_vocab())
    except ModelBankError:
        size = 0
    return [
        ModelSpec(UNIFORM_ID, "Uniform Baseline",
                  "every character equally likely: log2(65) = 6.02 bits per char, no model at all",
                  "uniform", None, size, size > 0),
        ModelSpec(UNIFORM_ASCII_ID, "Uniform ASCII",
                  "every printable ASCII character equally likely: log2(96) = 6.58 bits per char",
                  "uniform", None, len(ASCII_VOCAB), True),
    ]


def list_models() -> list[ModelSpec]:
    """Return every model in the bank (sorted by id) plus the built-in uniform baselines."""
    bank = bank_dir()
    folders = sorted(p for p in bank.iterdir() if (p / "model.json").exists()) if bank.exists() else []
    return [_spec_from_folder(p) for p in folders] + _uniform_specs()


def get_spec(model_id: str) -> ModelSpec:
    """Return the spec for model_id, or raise ModelBankError."""
    for spec in list_models():
        if spec.id == model_id:
            return spec
    ids = ", ".join(s.id for s in list_models())
    raise ModelBankError(f"unknown model {model_id!r}; choose from {ids}")


def load_model_uncached(model_id: str) -> ModelWrapper | UniformModelWrapper:
    """Load a fresh copy of the model (use load_model to share one copy)."""
    spec = get_spec(model_id)
    if not spec.available:
        raise ModelBankError(f"model {model_id!r} is listed but its files are missing in {spec.path}")
    from arithmetic_coder.models.wrappers import ModelWrapper, UniformModelWrapper

    if spec.kind == "uniform":
        return UniformModelWrapper(_uniform_vocab(model_id))
    if spec.kind != "nanogpt":
        raise ModelBankError(f"model {model_id!r} has unsupported kind {spec.kind!r}")
    from arithmetic_coder.models.nanogpt import GPT, GPTConfig

    return ModelWrapper.from_nanogpt_checkpoint(
        spec.path / "ckpt.pt", lambda **args: GPT(GPTConfig(**args)), spec.path / "meta.pkl"
    )


@lru_cache(maxsize=None)
def load_model(model_id: str) -> ModelWrapper | UniformModelWrapper:
    """Load the model once and share it (sessions only wrap it, so sharing is safe)."""
    return load_model_uncached(model_id)
