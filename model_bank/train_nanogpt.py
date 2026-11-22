"""Train small char-level nanoGPT models for the model bank.

Usage (from the project root):
    python model_bank/train_nanogpt.py shakespeare_char
    python model_bank/train_nanogpt.py english_char

Each model ends up in model_bank/<name>/ as ckpt.pt (nanoGPT checkpoint) + meta.pkl (vocab).
All models share the same 65-character vocabulary (the Tiny Shakespeare character set),
the same architecture and the same training budget, so they differ only in training text.
"""
import argparse
import pickle
import shutil
import subprocess
import sys
import unicodedata
import urllib.request
from pathlib import Path

import numpy as np

BANK = Path(__file__).resolve().parent
NANOGPT = BANK / "nanoGPT"  # git clone https://github.com/karpathy/nanoGPT
CACHE = BANK / "_downloads"

SHAKESPEARE_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"
# general (non-Shakespeare) English prose from Project Gutenberg
GUTENBERG_IDS = [1342, 1661, 98, 84, 11]  # Pride and Prejudice, Sherlock Holmes, A Tale of Two Cities, Frankenstein, Alice

# same architecture + budget for every model (sized for CPU training)
TRAIN_ARGS = dict(
    device="cpu", compile=False, dtype="float32",
    n_layer=4, n_head=4, n_embd=128, block_size=128, dropout=0.1, bias=False,
    batch_size=24, gradient_accumulation_steps=1,  # train.py defaults to 40 accumulation steps
    max_iters=2000, lr_decay_iters=2000, learning_rate=1e-3, min_lr=1e-4,
    beta2=0.99, warmup_iters=100, eval_interval=250, eval_iters=50, log_interval=100,
    always_save_checkpoint=False, wandb_log=False,
)


def download(url: str, name: str) -> str:
    """Download url once into the cache folder and return its text."""
    CACHE.mkdir(exist_ok=True)
    path = CACHE / name
    if not path.exists():
        print(f"downloading {url}")
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research script)"})
        with urllib.request.urlopen(req) as r:
            path.write_bytes(r.read())
    return path.read_text(encoding="utf-8")


def shakespeare_text() -> str:
    """Return the Tiny Shakespeare corpus (~1.1M chars)."""
    return download(SHAKESPEARE_URL, "tinyshakespeare.txt")


def strip_gutenberg(text: str) -> str:
    """Remove the Project Gutenberg license header and footer."""
    start = text.find("*** START OF")
    end = text.find("*** END OF")
    text = text[text.find("\n", start) + 1 : end] if start != -1 and end != -1 else text
    return text.strip()


def to_vocab(text: str, vocab: set[str]) -> str:
    """Normalize typography to the Shakespeare character set and drop every other character."""
    text = unicodedata.normalize("NFKD", text).replace("\r\n", "\n")
    for src, dst in {"‘": "'", "’": "'", "“": "'", "”": "'", '"': "'",
                     "—": "-", "–": "-", "_": ""}.items():
        text = text.replace(src, dst)
    return "".join(c for c in text if c in vocab)


def gutenberg_mirror_url(book_id: int) -> str:
    """URL of a book's UTF-8 text on the official aleph.pglaf.org mirror (gutenberg.org itself blocks scripts)."""
    digits = str(book_id)
    folders = "/".join(digits[:-1]) if len(digits) > 1 else "0"
    return f"https://aleph.pglaf.org/{folders}/{book_id}/{book_id}-0.txt"


def english_text(vocab: set[str], n_chars: int) -> str:
    """Return ~n_chars of Gutenberg prose restricted to the Shakespeare vocab."""
    books = [strip_gutenberg(download(gutenberg_mirror_url(i), f"pg{i}.txt")) for i in GUTENBERG_IDS]
    text = to_vocab("\n\n".join(books), vocab)
    if len(text) < n_chars:
        raise RuntimeError(f"english corpus too small: {len(text)} < {n_chars} chars")
    return text[:n_chars]


def prepare(name: str) -> None:
    """Write train.bin / val.bin / meta.pkl for dataset `name` where nanoGPT's train.py looks for them."""
    shakespeare = shakespeare_text()
    chars = sorted(set(shakespeare))  # the shared 65-char vocab
    text = shakespeare if name == "shakespeare_char" else english_text(set(chars), len(shakespeare))

    stoi = {c: i for i, c in enumerate(chars)}
    ids = np.array([stoi[c] for c in text], dtype=np.uint16)
    split = int(0.9 * len(ids))

    data_dir = NANOGPT / "data" / name
    data_dir.mkdir(parents=True, exist_ok=True)
    ids[:split].tofile(data_dir / "train.bin")
    ids[split:].tofile(data_dir / "val.bin")
    with open(data_dir / "meta.pkl", "wb") as f:
        pickle.dump({"vocab_size": len(chars), "itos": dict(enumerate(chars)), "stoi": stoi}, f)
    print(f"{name}: {len(text):,} chars, vocab {len(chars)}, train {split:,} / val {len(ids) - split:,}")


def train(name: str) -> None:
    """Run nanoGPT's train.py on the prepared dataset and store ckpt.pt + meta.pkl in model_bank/<name>."""
    out_dir = BANK / name
    out_dir.mkdir(exist_ok=True)
    args = [f"--{k}={v}" for k, v in {**TRAIN_ARGS, "dataset": name, "out_dir": str(out_dir)}.items()]
    subprocess.run([sys.executable, "-u", "train.py", *args], cwd=NANOGPT, check=True)  # -u: live log output
    shutil.copy(NANOGPT / "data" / name / "meta.pkl", out_dir / "meta.pkl")
    print(f"saved model to {out_dir}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("name", choices=["shakespeare_char", "english_char"])
    name = parser.parse_args().name
    prepare(name)
    train(name)
