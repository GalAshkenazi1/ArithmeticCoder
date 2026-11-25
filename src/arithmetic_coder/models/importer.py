"""Import a char-level nanoGPT checkpoint trained elsewhere into the model bank.

    uv run arith-import-model path/to/ckpt.pt --id my_model --name "My-GPT" --description "..." \
        (--meta path/to/meta.pkl | --vocab ascii)

Writes model_bank/<id>/{ckpt.pt, meta.pkl, model.json}, keeping only the weights (no optimizer
state), then loads the model once to check that it really works. Only import files you trust:
meta.pkl files are Python pickles.
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import shutil
from pathlib import Path

from arithmetic_coder.models.registry import ASCII_VOCAB, ModelBankError, bank_dir, load_model_uncached

_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_]{0,40}$")


def write_model_folder(folder: Path, state_dict: dict, model_args: dict, vocab: list[str] | None, info: dict,
                       extra: dict | None = None) -> None:
    """Write ckpt.pt (weights + model_args only), meta.pkl (char vocab, if given) and model.json."""
    import torch

    folder.mkdir(parents=True, exist_ok=True)
    torch.save({"model": state_dict, "model_args": model_args, **(extra or {})}, folder / "ckpt.pt")
    if vocab is not None:
        with open(folder / "meta.pkl", "wb") as f:
            pickle.dump({"vocab_size": len(vocab), "itos": dict(enumerate(vocab)),
                         "stoi": {c: i for i, c in enumerate(vocab)}}, f)
    (folder / "model.json").write_text(json.dumps(info, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def import_model(ckpt_path: Path, model_id: str, name: str, description: str,
                 meta_path: Path | None = None, vocab: list[str] | None = None, force: bool = False) -> Path:
    """Copy a nanoGPT checkpoint into the bank as model_id and verify it loads; return its folder."""
    import torch

    if not _ID_PATTERN.match(model_id):
        raise ModelBankError("model id must be lowercase letters, digits and underscores (max 41)")
    folder = bank_dir() / model_id
    if folder.exists() and not force:
        raise ModelBankError(f"{folder} already exists (use --force to replace it)")
    if (meta_path is None) == (vocab is None):
        raise ModelBankError("give exactly one of --meta or --vocab")
    if meta_path is not None:
        with open(meta_path, "rb") as f:
            itos = pickle.load(f)["itos"]
        vocab = [itos[i] for i in range(len(itos))]

    checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=True)
    state_dict = {k.removeprefix("_orig_mod."): v for k, v in checkpoint["model"].items()}
    model_args = dict(checkpoint["model_args"])
    if model_args.get("vocab_size", 0) < len(vocab):
        raise ModelBankError(f"model has {model_args.get('vocab_size')} output slots but the vocab has {len(vocab)}")

    if folder.exists():
        shutil.rmtree(folder)
    write_model_folder(folder, state_dict, model_args, vocab,
                       {"name": name, "description": description, "kind": "nanogpt", "imported_from": str(ckpt_path)})
    try:
        probs = load_model_uncached(model_id).get_probs([])
        if len(probs) != len(vocab) or abs(sum(probs) - 1) > 1e-6:
            raise ModelBankError("the imported model doesn't produce a valid distribution")
    except Exception:
        shutil.rmtree(folder)
        raise
    return folder


def main() -> None:
    """Console entry point (arith-import-model)."""
    parser = argparse.ArgumentParser(description="Import a char-level nanoGPT checkpoint into the model bank.")
    parser.add_argument("ckpt", type=Path, help="nanoGPT checkpoint (ckpt.pt)")
    parser.add_argument("--id", required=True, help="folder name in model_bank/, e.g. my_model")
    parser.add_argument("--name", required=True, help="readable name shown in the apps, e.g. My-GPT")
    parser.add_argument("--description", default="", help="one-line description")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--meta", type=Path, help="nanoGPT meta.pkl with the vocabulary (itos)")
    source.add_argument("--vocab", choices=["ascii"], help="use a built-in vocabulary instead of a meta.pkl")
    parser.add_argument("--force", action="store_true", help="replace an existing model with the same id")
    args = parser.parse_args()
    folder = import_model(args.ckpt, args.id, args.name, args.description, args.meta,
                          list(ASCII_VOCAB) if args.vocab == "ascii" else None, args.force)
    print(f"imported {args.name!r} into {folder}")


if __name__ == "__main__":
    main()
