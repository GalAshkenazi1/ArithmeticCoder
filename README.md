# arithmetic-coder

Arithmetic coding of text with character-level language models: a proof of concept for sending
compact messages between two peers who share a model and a secret key.

The better the model predicts a message, the fewer bits it needs. A small Shakespeare model sends
Shakespeare-style text at about 2.5 bits per character, against 8 for plain text.

## Setup

```
uv sync --all-groups
```

## Run

| what | command |
|---|---|
| Interactive web demo (Alice and Bob, animated encoder) | `uv run arith-demo`, then open http://127.0.0.1:8000 |
| Chat relay (forwards messages, never sees text or keys) | `uv run arith-relay` |
| Command-line chat client | `uv run arith-chat --user alice`, then `/add bob shakespeare_char <key>` |
| Tests | `uv run pytest` |
| Model comparison study | `uv run --group studies python studies/01_compare_models/compare_models.py` |

## Layout

```
src/arithmetic_coder/   backend (Python package)
  coding/               exact arithmetic coder, key-derived permutation, encoding trace
  models/               model wrappers, vendored nanoGPT definition, model registry
  p2p/                  peer sessions, wire protocol, relay server, CLI client
  api/                  FastAPI backend for the web demo (JSON only)
frontend/               web demo UI: HTML, CSS, JS modules (no build step)
model_bank/             models only: <id>/{ckpt.pt, meta.pkl, model.json, train.log}
training/               separate uv project (CUDA torch): corpora, training recipes, tests
studies/                experiments and their results
tests/                  pytest suite
```

## Models

Every folder in `model_bank/` that contains `ckpt.pt`, `meta.pkl` and `model.json` is a model. The
built-in uniform baselines (`uniform` over the 65 Shakespeare characters, `uniform_ascii` over the 96
printable ASCII characters) need no files.

`model.json` example:

```json
{ "name": "Shakespeare-GPT", "description": "0.8M-param char-level nanoGPT trained on Tiny Shakespeare", "kind": "nanogpt" }
```

### Training models (GPU)

Training lives in `training/`, a separate uv project whose torch is a CUDA build. The app itself
stays on CPU torch, so peers keep getting identical probabilities. The GPU needs an NVIDIA driver
that supports CUDA 13.2.

```
uv sync --project training                                        # once
uv run --project training python training/train.py --list         # recipes
uv run --project training python training/train.py wiki_small     # train one (or several)
uv run --project training pytest training/tests                   # corpus-cleaning tests
```

Each recipe is a corpus, a vocabulary, a size and a training budget (see `RECIPES` in
`training/train.py`). Corpora are downloaded once into `training/_downloads/`:

| recipe | corpus | vocab | size |
|---|---|---|---|
| `shakespeare_char`, `english_char` | Tiny Shakespeare, Gutenberg novels | 65 chars | tiny (0.8M) |
| `wiki_small` | WikiText-2 (Wikipedia) | ASCII (96) | small (3.2M) |
| `stories_small` | TinyStories (simple English) | ASCII (96) | small (3.2M) |
| `web_small` | C4 (web text) | ASCII (96) | small (3.2M) |
| `python_small` | Python standard library source | ASCII (96) | small (3.2M) |

### Importing models trained elsewhere

```
uv run arith-import-model path/to/ckpt.pt --id my_model --name "My-GPT" --description "..." --meta path/to/meta.pkl
```

This works with any char-level nanoGPT checkpoint; use `--vocab ascii` instead of `--meta` if it was
trained on the ASCII vocabulary. The command keeps only the weights, writes `model.json`, and checks
that the model loads.

## Notes

- **Peers must use the same torch version.** The model's probabilities differ slightly between
  torch versions, and a single difference breaks decoding. The fingerprint doesn't detect this.
  `uv.lock` pins the version, so peers who install with `uv sync` match.
- **This is a POC, not secure messaging.** The key permutation only hides the encoding, keys are
  stored in plain text, and the relay has no authentication.
