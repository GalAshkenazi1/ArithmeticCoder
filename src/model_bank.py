"""Load models from model_bank/ by name, so every part of the app uses the same models and vocab."""
from __future__ import annotations

import importlib.util
import pickle
import sys
from functools import lru_cache
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.modelwrapper import ModelWrapper, UniformModelWrapper

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "model_bank"
NANOGPT_MODEL_PY = BANK / "nanoGPT" / "model.py"  # git clone https://github.com/karpathy/nanoGPT model_bank/nanoGPT

MODEL_NAMES = ("shakespeare_char", "english_char", "uniform")
VOCAB_SOURCE = "shakespeare_char"  # all bank models share this 65-char vocabulary


class ModelBankError(RuntimeError):
    """Raised when a model name is unknown or its files are missing."""


def bank_vocab(name: str = VOCAB_SOURCE) -> list[str]:
    """Return a bank model's vocabulary in order, read from its meta.pkl (no torch needed)."""
    meta_path = BANK / name / "meta.pkl"
    if not meta_path.exists():
        raise ModelBankError(f"missing {meta_path}")
    with open(meta_path, "rb") as f:
        itos = pickle.load(f)["itos"]
    return [itos[i] for i in range(len(itos))]


@lru_cache(maxsize=1)
def _nanogpt_module() -> ModuleType:
    """Import nanoGPT's model.py under a private module name (keeps its folder off sys.path)."""
    if not NANOGPT_MODEL_PY.exists():
        raise ModelBankError(
            f"nanoGPT code not found at {NANOGPT_MODEL_PY.parent}; run "
            "'git clone https://github.com/karpathy/nanoGPT model_bank/nanoGPT'"
        )
    spec = importlib.util.spec_from_file_location("nanogpt_model", NANOGPT_MODEL_PY)
    module = importlib.util.module_from_spec(spec)
    sys.modules["nanogpt_model"] = module  # dataclasses need the module registered while it loads
    spec.loader.exec_module(module)
    return module


def load_model_uncached(name: str) -> ModelWrapper | UniformModelWrapper:
    """Load a fresh copy of the named model (use load_model to share one copy)."""
    if name not in MODEL_NAMES:
        raise ModelBankError(f"unknown model {name!r}; choose from {', '.join(MODEL_NAMES)}")
    from src.modelwrapper import ModelWrapper, UniformModelWrapper

    if name == "uniform":
        return UniformModelWrapper(bank_vocab())
    folder = BANK / name
    if not (folder / "ckpt.pt").exists():
        raise ModelBankError(f"missing {folder / 'ckpt.pt'}; train it with model_bank/train_nanogpt.py {name}")
    nanogpt = _nanogpt_module()
    return ModelWrapper.from_nanogpt_checkpoint(
        folder / "ckpt.pt", lambda **args: nanogpt.GPT(nanogpt.GPTConfig(**args)), folder / "meta.pkl"
    )


@lru_cache(maxsize=None)
def load_model(name: str) -> ModelWrapper | UniformModelWrapper:
    """Load the named model once and share it (sessions only wrap it, so sharing is safe)."""
    return load_model_uncached(name)
