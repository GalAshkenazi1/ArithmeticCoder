"""Train char-level nanoGPT models for the model bank (on the GPU when available).

    uv run --project training python training/train.py --list
    uv run --project training python training/train.py wiki_small stories_small web_small python_small

Each model is a recipe: corpus + vocabulary + size + training budget. The result lands in
model_bank/<id>/ (ckpt.pt with weights only, meta.pkl, model.json with training stats, train.log),
built in a hidden temp folder first so a half-trained model never appears in the bank.
"""
from __future__ import annotations

import argparse
import math
import shutil
import time
from contextlib import nullcontext
from dataclasses import dataclass

import numpy as np
import torch

from arithmetic_coder.models.importer import write_model_folder
from arithmetic_coder.models.nanogpt import GPT, GPTConfig
from arithmetic_coder.models.registry import bank_dir
from arithmetic_coder.tokenizers import CharTokenizer
from arithmetic_coder.tokenizers.bytes import ByteTokenizer
from arithmetic_coder.tokenizers.words import WordTokenizer, build_word_list
from corpora import load_corpus, vocabulary

SIZES = {
    "tiny": dict(n_layer=4, n_head=4, n_embd=128, block_size=128, dropout=0.1, bias=False),   # ~0.8M params
    "small": dict(n_layer=4, n_head=4, n_embd=256, block_size=128, dropout=0.1, bias=False),  # ~3.2M params
}
EVAL_INTERVAL, EVAL_ITERS, LOG_INTERVAL = 250, 40, 100


@dataclass(frozen=True)
class Recipe:
    """How to build one model. {params} in the description is filled in after training."""

    corpus: str
    vocab: str      # corpus cleaning: "shakespeare" (65 chars), "ascii" (96 chars) or "utf8" (keep Unicode)
    size: str       # key of SIZES
    name: str
    description: str
    batch_size: int = 64
    max_iters: int = 4000
    learning_rate: float = 1e-3
    min_lr: float = 1e-4
    warmup_iters: int = 200
    tokenizer: str = "char"  # "char", "bytes" or "words"
    words: int = 4096        # word-list size for the "words" tokenizer


RECIPES = {
    # the two original models (trained with these settings through nanoGPT's train.py; kept for reference)
    "shakespeare_char": Recipe("shakespeare", "shakespeare", "tiny", "Shakespeare-GPT",
                               "{params}-param char-level nanoGPT trained on Tiny Shakespeare",
                               batch_size=24, max_iters=2000, warmup_iters=100),
    "english_char": Recipe("gutenberg", "shakespeare", "tiny", "English-GPT",
                           "same architecture, trained on 19th-century Gutenberg prose "
                           "(Austen, Doyle, Dickens, Shelley, Carroll)",
                           batch_size=24, max_iters=2000, warmup_iters=100),
    # the ASCII models: one per kind of text
    "wiki_small": Recipe("wikitext", "ascii", "small", "Wiki-GPT",
                         "{params}-param char nanoGPT trained on Wikipedia articles (WikiText-2)"),
    "stories_small": Recipe("tinystories", "ascii", "small", "TinyStories-GPT",
                            "{params}-param char nanoGPT trained on short stories in simple English (TinyStories)"),
    "web_small": Recipe("c4", "ascii", "small", "Web-GPT",
                        "{params}-param char nanoGPT trained on modern web text (C4)"),
    "python_small": Recipe("python", "ascii", "small", "Python-GPT",
                           "{params}-param char nanoGPT trained on Python source code (the standard library)"),
    # other tokenizations, same core size and training budget (compare with web_small / wiki_small)
    "web_bytes": Recipe("c4", "utf8", "small", "Web-Bytes",
                        "{params}-param nanoGPT over UTF-8 bytes, trained on web text (C4, Unicode kept)",
                        tokenizer="bytes"),
    "wiki_bytes": Recipe("wikitext", "utf8", "small", "Wiki-Bytes",
                         "{params}-param nanoGPT over UTF-8 bytes, trained on Wikipedia (WikiText-2)",
                         tokenizer="bytes"),
    "web_words": Recipe("c4", "utf8", "small", "Web-Words",
                        "{params}-param nanoGPT over 4,096 whole words + byte escape, trained on web text (C4)",
                        tokenizer="words"),
}


def encode_text(text: str, vocab: list[str]) -> np.ndarray:
    """Map text to vocab indices (uint8) with a lookup table; every vocab char is ASCII."""
    table = np.zeros(128, dtype=np.uint8)
    for i, c in enumerate(vocab):
        table[ord(c)] = i
    return table[np.frombuffer(text.encode("ascii"), dtype=np.uint8)]


def build_tokenizer(recipe: Recipe, train_text: str):
    """The recipe's tokenizer; a word list is learned from the training split only."""
    if recipe.tokenizer == "char":
        return CharTokenizer(vocabulary(recipe.vocab))
    if recipe.tokenizer == "bytes":
        return ByteTokenizer()
    if recipe.tokenizer == "words":
        return WordTokenizer(build_word_list(train_text, recipe.words))
    raise ValueError(f"unknown tokenizer {recipe.tokenizer!r}")


def encode_ids(tokenizer, text: str) -> np.ndarray:
    """The text as symbol ids (fast paths for characters and bytes)."""
    if tokenizer.kind == "char":
        return encode_text(text, tokenizer.vocab).astype(np.int32)
    if tokenizer.kind == "bytes":
        return np.frombuffer(text.encode("utf-8"), dtype=np.uint8).astype(np.int32)
    return np.array(tokenizer.encode(text), dtype=np.int32)


def train(model_id: str, device: str, max_iters: int | None = None, max_chars: int | None = None,
          force: bool = False, amp: bool = False) -> None:
    """Train one recipe and install it into the model bank."""
    recipe = RECIPES[model_id]
    final, tmp = bank_dir() / model_id, bank_dir() / f".{model_id}.training"
    if final.exists() and not force:
        raise SystemExit(f"{final} already exists; pass --force to retrain it")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    log_file = open(tmp / "train.log", "w", encoding="utf-8")

    def log(message: str) -> None:
        print(message, flush=True)
        log_file.write(message + "\n")

    text = load_corpus(recipe.corpus, recipe.vocab, **({"max_chars": max_chars} if max_chars else {}))
    char_split = int(0.9 * len(text))  # same train/validation text for every tokenization
    tokenizer = build_tokenizer(recipe, text[:char_split])
    train_ids, val_ids = encode_ids(tokenizer, text[:char_split]), encode_ids(tokenizer, text[char_split:])
    data = {"train": torch.from_numpy(train_ids).to(device), "val": torch.from_numpy(val_ids).to(device)}
    vocab_size = len(tokenizer.vocab)
    size = SIZES[recipe.size]
    block, batch = size["block_size"], recipe.batch_size
    iters = max_iters or recipe.max_iters
    gpu = torch.cuda.get_device_name(0) if device == "cuda" else "-"
    chars_per_symbol = len(text) / (len(train_ids) + len(val_ids))
    val_chars_per_symbol = (len(text) - char_split) / len(val_ids)  # converts loss per symbol to bits per char
    log(f"{model_id}: corpus {recipe.corpus} ({len(text):,} chars), tokenizer {tokenizer.kind} (vocab {vocab_size}, "
        f"{chars_per_symbol:.2f} chars/symbol), size {recipe.size}, {iters} iters x batch {batch} x block {block}, "
        f"device {device} {gpu}")

    torch.manual_seed(1337)
    model = GPT(GPTConfig(vocab_size=vocab_size, **size)).to(device)
    params = sum(p.numel() for p in model.parameters()) - model.transformer.wpe.weight.numel()
    optimizer = model.configure_optimizers(0.1, recipe.learning_rate, (0.9, 0.99), "cuda" if device == "cuda" else "cpu")
    # float16 autocast is opt-in: on a GTX 1650 it is 3.5x *slower* than float32 (no tensor cores)
    use_amp = amp and device == "cuda"
    scaler = torch.amp.GradScaler("cuda", enabled=use_amp)
    autocast = (lambda: torch.autocast("cuda", dtype=torch.float16)) if use_amp else nullcontext
    offsets = torch.arange(block, device=device)

    def get_batch(split_name: str):
        source = data[split_name]
        starts = torch.randint(len(source) - block - 1, (batch,), device=device)
        index = starts[:, None] + offsets
        return source[index].long(), source[index + 1].long()

    @torch.no_grad()
    def estimate_loss() -> dict[str, float]:
        model.eval()
        losses = {}
        for split_name in ("train", "val"):
            total = 0.0
            for _ in range(EVAL_ITERS):
                x, y = get_batch(split_name)
                with autocast():
                    _, loss = model(x, y)
                total += loss.item()
            losses[split_name] = total / EVAL_ITERS
        model.train()
        return losses

    def lr_at(it: int) -> float:
        if it < recipe.warmup_iters:
            return recipe.learning_rate * (it + 1) / recipe.warmup_iters
        progress = min(1.0, (it - recipe.warmup_iters) / max(1, iters - recipe.warmup_iters))
        return recipe.min_lr + 0.5 * (1 + math.cos(math.pi * progress)) * (recipe.learning_rate - recipe.min_lr)

    best_val, best_state, start, tick = float("inf"), None, time.time(), time.time()
    for it in range(iters + 1):
        if it % EVAL_INTERVAL == 0 or it == iters:
            losses = estimate_loss()
            log(f"step {it}: train {losses['train']:.4f}, val {losses['val']:.4f} nats/symbol "
                f"({losses['val'] / math.log(2) / val_chars_per_symbol:.3f} bits/char)")
            if losses["val"] < best_val:
                best_val = losses["val"]
                best_state = {k: v.detach().float().cpu().clone() for k, v in model.state_dict().items()}
        if it == iters:
            break
        for group in optimizer.param_groups:
            group["lr"] = lr_at(it)
        x, y = get_batch("train")
        with autocast():
            _, loss = model(x, y)
        optimizer.zero_grad(set_to_none=True)
        scaler.scale(loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        scaler.step(optimizer)
        scaler.update()
        if it % LOG_INTERVAL == 0 and it:
            ms = (time.time() - tick) * 1000 / LOG_INTERVAL
            tick = time.time()
            log(f"iter {it}: loss {loss.item():.4f}, {ms:.0f} ms/iter")

    minutes = (time.time() - start) / 60
    bits_per_char = best_val / math.log(2) / val_chars_per_symbol
    info = {
        "name": recipe.name,
        "description": recipe.description.format(params=f"{params / 1e6:.1f}M"),
        "kind": "nanogpt",
        "tokenizer": {"kind": tokenizer.kind},
        "vocab_size": vocab_size,
        "training": {
            "corpus": recipe.corpus, "corpus_chars": len(text), "vocab": recipe.vocab, "params": params,
            "iters": iters, "batch_size": batch, "block_size": block,
            "chars_per_symbol": round(val_chars_per_symbol, 3),
            "best_val_loss_nats": round(best_val, 4), "val_bits_per_char": round(bits_per_char, 3),
            "device": f"{device} {gpu}".strip(), "precision": "float16 autocast" if use_amp else "float32",
            "torch": torch.__version__, "minutes": round(minutes, 1),
        },
    }
    model_args = dict(size, vocab_size=vocab_size)
    write_model_folder(tmp, best_state, model_args, tokenizer.vocab if tokenizer.kind == "char" else None, info)
    if tokenizer.kind == "words":
        tokenizer.to_file(tmp / "words.json", source=f"{recipe.corpus} training split, top {recipe.words} pieces")
    log(f"done in {minutes:.1f} min: best val {bits_per_char:.3f} bits/char")
    log_file.close()
    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)
    print(f"installed {recipe.name!r} as {final}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("models", nargs="*", help="recipe ids to train (see --list)")
    parser.add_argument("--list", action="store_true", help="show the recipes and exit")
    parser.add_argument("--device", choices=["auto", "cuda", "cpu"], default="auto")
    parser.add_argument("--force", action="store_true", help="retrain models that already exist")
    parser.add_argument("--max-iters", type=int, help="override the recipe's iterations (e.g. for a smoke test)")
    parser.add_argument("--max-chars", type=int, help="use only the first N characters of the corpus")
    parser.add_argument("--amp", action="store_true",
                        help="float16 mixed precision (faster on GPUs with tensor cores, slower on a GTX 1650)")
    args = parser.parse_args()

    if args.list or not args.models:
        for model_id, r in RECIPES.items():
            installed = "installed" if (bank_dir() / model_id).exists() else "-"
            print(f"{model_id:17s} {r.name:16s} corpus={r.corpus:12s} vocab={r.vocab:11s} size={r.size:5s} {installed}")
        return
    unknown = [m for m in args.models if m not in RECIPES]
    if unknown:
        raise SystemExit(f"unknown recipe(s): {', '.join(unknown)} (see --list)")
    device = ("cuda" if torch.cuda.is_available() else "cpu") if args.device == "auto" else args.device
    if args.device == "cuda" and not torch.cuda.is_available():
        raise SystemExit("CUDA requested but not available (check the NVIDIA driver: it must support CUDA 13.2)")
    for model_id in args.models:
        train(model_id, device, args.max_iters, args.max_chars, args.force, args.amp)


if __name__ == "__main__":
    main()
