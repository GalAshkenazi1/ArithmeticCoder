import hashlib
from pathlib import Path

import torch
import torch.nn.functional as F

from arithmetic_coder.tokenizers import CharTokenizer, Tokenizer

INFERENCE_THREADS = 4  # fixed, because the thread count can change float sums (peers must match exactly)


class ModelWrapper:
    """Wraps a language model so it returns next-symbol probabilities for a prefix of symbol ids."""

    def __init__(
        self,
        model: torch.nn.Module,
        tokenizer: Tokenizer,
        block_size: int | None = None,
        precision_bits: int | None = None,
        threads: int = INFERENCE_THREADS,
    ):
        """Move the model to CPU in eval mode. block_size limits the context (default: the model's own)."""
        self.device = "cpu" # independent of the model's device
        self.model = model.to(self.device)
        self.model.eval()
        self.tokenizer = tokenizer
        self.block_size = block_size or getattr(getattr(self.model, "config", None), "block_size", 256)
        if tokenizer.bos_id is None:
            raise ValueError("the tokenizer needs a BOS symbol for the model's first prediction")
        self.bos_id = tokenizer.bos_id
        self.precision_bits = precision_bits
        self.threads = threads
        self._digest: bytes | None = None

    @classmethod
    def from_nanogpt_checkpoint(
        cls,
        ckpt_path: str | Path,
        model_cls: type[torch.nn.Module],
        meta_path: str | Path | None = None,
        tokenizer: Tokenizer | None = None,
        block_size: int | None = None,
        precision_bits: int | None = None,
    ) -> "ModelWrapper":
        """Create a ModelWrapper from a nanoGPT checkpoint; the tokenizer defaults to meta.pkl's characters."""
        checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)
        if tokenizer is None:
            if meta_path is not None:
                import pickle

                with open(meta_path, "rb") as f:
                    itos = pickle.load(f)["itos"]
            elif "itos" in checkpoint:
                itos = checkpoint["itos"]
            else:
                raise ValueError("Vocabulary (itos) not found in checkpoint or meta_path.")
            tokenizer = CharTokenizer([itos[i] for i in range(len(itos))])

        model_args = checkpoint["model_args"]
        model = model_cls(**model_args)
        state_dict = {k.removeprefix("_orig_mod."): v for k, v in checkpoint["model"].items()}
        model.load_state_dict(state_dict)
        return cls(model, tokenizer, block_size=min(block_size or 10**9, model_args.get("block_size", 10**9)),
                   precision_bits=precision_bits)

    def get_vocab(self) -> list[str]:
        """Return the symbol labels in id order."""
        return self.tokenizer.vocab

    def model_digest(self) -> bytes:
        """Return a SHA-256 of everything that shapes the predictions: weights, block_size and BOS id."""
        if self._digest is None:
            h = hashlib.sha256(b"modelwrapper/v1")
            h.update(self.block_size.to_bytes(4, "big") + self.bos_id.to_bytes(4, "big"))
            for name, tensor in sorted(self.model.state_dict().items()):
                t = tensor.detach().cpu().contiguous()
                raw = t.numpy().tobytes()
                h.update(f"{name}|{t.dtype}|{tuple(t.shape)}|{len(raw)}|".encode("utf-8"))
                h.update(raw)
            self._digest = h.digest()
        return self._digest

    @torch.inference_mode()
    def get_probs(self, prefix_ids: list[int]) -> list[float]:
        """Return the probability distribution over the next symbol, given the symbols so far."""
        if torch.get_num_threads() != self.threads:
            torch.set_num_threads(self.threads)
        # always start the context with BOS, then keep the last block_size symbols
        token_ids = ([self.bos_id] + list(prefix_ids[-self.block_size:]))[-self.block_size:]
        idx = torch.tensor([token_ids], dtype=torch.long, device=self.device)

        output = self.model(idx)
        logits = output[0] if isinstance(output, tuple) else output

        # drop padded vocab slots (nanoGPT may set vocab_size > the tokenizer's vocabulary)
        last_logits = logits[0, -1, : len(self.tokenizer.vocab)].to(torch.float64)
        return F.softmax(last_logits, dim=-1).cpu().tolist()


class UniformModelWrapper:
    """Mock model wrapper that returns uniform probabilities over a tokenizer's symbols."""

    def __init__(self, tokenizer: Tokenizer | list[str]):
        """Accepts a tokenizer, or a list of characters (wrapped in a CharTokenizer)."""
        self.tokenizer = tokenizer if not isinstance(tokenizer, list) else CharTokenizer(
            tokenizer, bos_char="\n" if "\n" in tokenizer else None)
        self.precision_bits = None
        n = len(self.tokenizer.vocab)
        self._probs = [1.0 / n] * n

    def get_vocab(self) -> list[str]:
        """Return the symbol labels in id order."""
        return self.tokenizer.vocab

    def model_digest(self) -> bytes:
        """Return a fixed digest identifying the uniform model (the vocab is hashed by the coder)."""
        return hashlib.sha256(b"uniform/v1").digest()

    def get_probs(self, prefix_ids: list[int]) -> list[float]:
        """Return the same uniform distribution for every prefix."""
        return self._probs
