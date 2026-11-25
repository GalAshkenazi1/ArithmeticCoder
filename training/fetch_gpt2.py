"""Download OpenAI's GPT-2 (124M) and install it into the model bank, without the transformers library.

    uv run --project training python training/fetch_gpt2.py

Downloads pytorch_model.bin (~550 MB), vocab.json and merges.txt from huggingface.co/openai-community/gpt2
(MIT licence) into training/_downloads/gpt2/, maps the weights onto the package's nanoGPT GPT class
(same transposes as nanoGPT's GPT.from_pretrained), checks the model predicts sensibly, and writes
model_bank/gpt2/{ckpt.pt, vocab.json, merges.txt, model.json}. ckpt.pt is git-ignored (too big).
"""
import json
import math
import shutil

import torch

from arithmetic_coder.models.importer import write_model_folder
from arithmetic_coder.models.nanogpt import GPT, GPTConfig
from arithmetic_coder.models.registry import bank_dir
from arithmetic_coder.tokenizers.gpt2_bpe import GPT2Tokenizer
from corpora import DOWNLOADS, download

BASE_URL = "https://huggingface.co/openai-community/gpt2/resolve/main/"
CONFIG = dict(n_layer=12, n_head=12, n_embd=768, block_size=1024, vocab_size=50257, bias=True, dropout=0.0)
TRANSPOSED = ("attn.c_attn.weight", "attn.c_proj.weight", "mlp.c_fc.weight", "mlp.c_proj.weight")  # HF Conv1D
INFO = {
    "name": "GPT-2 (124M)",
    "description": "OpenAI's pretrained GPT-2 small: 124M params, 50,257-token byte-level BPE, trained on WebText",
    "kind": "nanogpt",
    "tokenizer": {"kind": "gpt2"},
    "vocab_size": 50257,
    "precision_bits": 26,
    "context_tokens": 256,
    "dataset": {"name": "WebText",
                "about": "about 40 GB of text from 8 million web pages that Reddit users linked to (OpenAI, 2019)",
                "url": "https://openai.com/index/better-language-models/"},
    "examples": ["Scientists announced on Tuesday that the new vaccine is safe and effective.",
                 "The company said it expects revenue to grow by 10 percent next year."],
    "training": {"params": 123_653_376, "block_size": 1024},  # params without position embeddings, like train.py
    "source": BASE_URL,
    "licence": "MIT (OpenAI GPT-2)",
}


def convert(hf_state: dict) -> dict:
    """Rename Hugging Face GPT2Model keys to nanoGPT's and transpose the Conv1D weights."""
    out = {}
    for key, tensor in hf_state.items():
        if key.endswith((".attn.bias", ".attn.masked_bias")):  # causal-mask buffers, not weights
            continue
        name = key.removeprefix("transformer.")
        tensor = tensor.t() if name.endswith(TRANSPOSED) else tensor
        out["transformer." + name] = tensor.float().contiguous()
    out["lm_head.weight"] = out["transformer.wte.weight"]  # tied input/output embeddings
    return out


def main() -> None:
    files = {}
    for name in ("pytorch_model.bin", "vocab.json", "merges.txt"):
        (DOWNLOADS / "gpt2").mkdir(parents=True, exist_ok=True)
        files[name] = download(BASE_URL + name, f"gpt2/{name}")
    state = convert(torch.load(files["pytorch_model.bin"], map_location="cpu", weights_only=True))
    model = GPT(GPTConfig(**CONFIG))
    missing, unexpected = model.load_state_dict(state, strict=False)
    missing = [k for k in missing if not k.endswith(".attn.bias")]
    if missing or unexpected:
        raise SystemExit(f"weight mapping failed: missing {missing[:5]}, unexpected {unexpected[:5]}")

    # sanity check: a plain English sentence should cost a few nats per token, not ~log(50257) = 10.8
    tokenizer = GPT2Tokenizer.from_files(files["vocab.json"], files["merges.txt"])
    ids = [tokenizer.bos_id] + tokenizer.encode("The quick brown fox jumps over the lazy dog, and then it went home.")
    with torch.no_grad():
        model.eval()
        _, loss = model(torch.tensor([ids[:-1]]), torch.tensor([ids[1:]]))
    print(f"sanity check: {loss.item():.2f} nats/token ({loss.item() / math.log(2):.2f} bits/token)")
    if loss.item() > 6:
        raise SystemExit("the converted model predicts badly; the weight mapping is probably wrong")

    folder = bank_dir() / "gpt2"
    write_model_folder(folder, model.state_dict(), CONFIG, None, INFO)
    for name in ("vocab.json", "merges.txt"):
        shutil.copy(files[name], folder / name)
    print(f"installed GPT-2 into {folder} ({(folder / 'ckpt.pt').stat().st_size / 1e6:.0f} MB checkpoint)")
    print(json.dumps(INFO, indent=2))


if __name__ == "__main__":
    main()
