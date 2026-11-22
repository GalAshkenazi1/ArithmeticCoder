from pathlib import Path
import torch
import torch.nn.functional as F


class ModelWrapper:
    """Wraps a character-level language model so it returns next-char probabilities for a prefix."""

    def __init__(
        self,
        model: torch.nn.Module,
        itos: dict[int, str] | list[str],
        block_size: int | None = None,
        bos_char: str = "\n",
    ):
        """Move the model to CPU in eval mode and build the vocabulary lookups."""
        self.device = "cpu" # independent of the model's device
        self.model = model.to(self.device)
        self.model.eval()

        if isinstance(itos, dict):
            self.vocab = [itos[i] for i in range(len(itos))]
        else:
            self.vocab = list(itos)

        self.stoi = {ch: i for i, ch in enumerate(self.vocab)}

        self.block_size = block_size or getattr(
            getattr(self.model, "config", None), "block_size", 256
        )

        if bos_char not in self.stoi:
            raise ValueError(
                f"BOS character {bos_char!r} must exist in the vocabulary."
            )
        self.bos_id = self.stoi[bos_char]

    @classmethod
    def from_nanogpt_checkpoint(
        cls,
        ckpt_path: str | Path,
        model_cls: type[torch.nn.Module],
        meta_path: str | Path | None = None,
    ) -> "ModelWrapper":
        """Factory method to create a ModelWrapper from a nanoGPT checkpoint and its vocabulary."""
        import pickle

        checkpoint = torch.load(ckpt_path, map_location="cpu", weights_only=False)

        if meta_path is not None:
            with open(meta_path, "rb") as f:
                meta = pickle.load(f)
            itos = meta["itos"]
        elif "itos" in checkpoint:
            itos = checkpoint["itos"]
        else:
            raise ValueError(
                "Vocabulary (itos) not found in checkpoint or meta_path."
            )

        model_args = checkpoint["model_args"]
        model = model_cls(**model_args)

        state_dict = checkpoint["model"]
        unwanted_prefix = "_orig_mod."
        for k in list(state_dict.keys()):
            if k.startswith(unwanted_prefix):
                state_dict[k[len(unwanted_prefix) :]] = state_dict.pop(k)

        model.load_state_dict(state_dict)
        return cls(
            model=model,
            itos=itos,
            block_size=model_args.get("block_size"),
        )

    def get_vocab(self) -> list[str]:
        """Return the vocabulary as a list of characters in order."""
        return self.vocab

    @torch.inference_mode()
    def get_char_probs(self, prefix: str) -> list[float]:
        """Return the probability distribution over the next character given the prefix."""
        try:
            ids = [self.stoi[ch] for ch in prefix[-self.block_size :]]
        except KeyError as e:
            raise ValueError(
                f"Character {e.args[0]!r} not in model vocabulary."
            ) from e

        # always start the context with BOS, then keep the last block_size tokens
        token_ids = ([self.bos_id] + ids)[-self.block_size :]
        idx = torch.tensor([token_ids], dtype=torch.long, device=self.device)

        output = self.model(idx)
        logits = output[0] if isinstance(output, tuple) else output

        # drop padded vocab slots (nanoGPT may set vocab_size > len(itos))
        last_logits = logits[0, -1, : len(self.vocab)].to(torch.float64)
        probs = F.softmax(last_logits, dim=-1)

        return probs.cpu().tolist()


class UniformModelWrapper:
    """Mock model wrapper that returns uniform probabilities over a given vocabulary."""

    def __init__(self, vocab: list[str]):
        """Store the vocabulary and precompute the uniform distribution."""
        self.vocab = list(vocab)
        self._probs = [1.0 / len(self.vocab)] * len(self.vocab)

    def get_vocab(self) -> list[str]:
        """Return the vocabulary as a list of characters in order."""
        return self.vocab

    def get_char_probs(self, prefix: str) -> list[float]:
        """Return the same uniform distribution for every prefix."""
        return self._probs