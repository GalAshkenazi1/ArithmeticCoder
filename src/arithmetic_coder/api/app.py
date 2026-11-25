"""FastAPI backend for the encoder showcase: a JSON API under /api, plus the separate frontend/ at /.

Run:  uv run arith-demo [--host 127.0.0.1] [--port 8000] [--preload all]
Dev:  uv run uvicorn --factory arithmetic_coder.api.app:create_app --reload

The frontend lives in the repo's frontend/ folder (override with ARITH_FRONTEND_DIR). To serve it
from somewhere else, list its origin in ARITH_CORS_ORIGINS (comma-separated).

For a public server (see deploy/): HOST and PORT set where to listen; ARITH_PRELOAD=all loads every
model at startup; ARITH_RATE_LIMIT=<n> allows n API calls per minute per client; ARITH_WAIT_SECONDS
makes a request give up (503) when the models stay busy that long.
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import threading
import time
from collections import defaultdict, deque
from functools import lru_cache
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from arithmetic_coder.api.encoder_service import EncoderService, ServerBusy
from arithmetic_coder.api.schemas import (
    DecodeRequest,
    DecodeResponse,
    EncodeRequest,
    EncodeResponse,
    ModelInfo,
    ModelsResponse,
    SymbolsResponse,
    TokenizeRequest,
    TokenizeResponse,
)
from arithmetic_coder.models.registry import (
    REPO_ROOT,
    ModelBankError,
    ModelSpec,
    get_spec,
    list_models,
    spec_tokenizer,
)
from arithmetic_coder.tokenizers import UnknownSymbolError, char_spans

DEFAULT_MODELS = ("shakespeare_char", "web_bytes", "uniform_bytes")  # first available is shown first
mimetypes.add_type("application/manifest+json", ".webmanifest")  # the PWA manifest (not in every MIME table)
SYMBOL_SAMPLE = 300  # big vocabularies (words, GPT-2) list this many symbols


class RateLimiter:
    """At most per_minute API calls per client in any 60 seconds (a sliding window per IP)."""

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, client: str) -> bool:
        now = time.monotonic()
        with self._lock:
            if len(self._hits) > 10_000:  # forget clients that went quiet
                for key in [k for k, q in self._hits.items() if not q or now - q[-1] > 60]:
                    del self._hits[key]
            hits = self._hits[client]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= self.per_minute:
                return False
            hits.append(now)
            return True


def _env_number(name: str, kind=int):
    value = os.environ.get(name, "").strip()
    return kind(value) if value else None


def frontend_dir() -> Path:
    """Where the static frontend lives (ARITH_FRONTEND_DIR, or the repo's frontend/)."""
    return Path(os.environ.get("ARITH_FRONTEND_DIR", REPO_ROOT / "frontend"))


@lru_cache(maxsize=None)
def _tokenizer(spec: ModelSpec):
    """A listed model's tokenizer, loaded once (no model weights needed)."""
    return spec_tokenizer(spec)


@lru_cache(maxsize=None)
def _char_vocab(spec: ModelSpec) -> tuple[str, ...] | None:
    """The characters a char model accepts (None for tokenizers that take any text)."""
    if spec.tokenizer != "char" or not spec.available:
        return None
    return tuple(sorted(_tokenizer(spec).vocab))


def _model_info(spec: ModelSpec) -> ModelInfo:
    info = spec.info
    return ModelInfo(id=spec.id, name=spec.name, description=spec.description, vocab_size=spec.vocab_size,
                     available=spec.available, tokenizer=spec.tokenizer, kind=spec.kind,
                     vocab=list(v) if (v := _char_vocab(spec)) else None,
                     dataset=info.get("dataset"), examples=info.get("examples", []),
                     training=info.get("training"), context_tokens=spec.context_tokens)


def _available_spec(model_id: str) -> ModelSpec:
    spec = get_spec(model_id)
    if not spec.available:
        raise ModelBankError(f"model {model_id!r} is listed but its files are missing")
    return spec


def _label(tokenizer, symbol_id: int) -> str:
    """Display label of a symbol: its text, with only the bytes that aren't valid UTF-8 as \\xNN.

    (tokenizer.vocab labels stay as they are: they are part of the coder's fingerprint.)
    """
    return tokenizer.symbol_bytes(symbol_id).decode("utf-8", errors="backslashreplace")


def _symbol_sample(spec: ModelSpec) -> dict:
    """All symbols of small vocabularies; for words, the most frequent words; for GPT-2, every n-th token."""
    vocab = _tokenizer(spec).vocab
    if len(vocab) <= 256:
        return {"ids": range(len(vocab)), "sampled": False, "note": ""}
    if spec.tokenizer == "words":
        n = min(SYMBOL_SAMPLE, len(vocab) - 256)
        return {"ids": range(256, 256 + n), "sampled": True,
                "note": f"the {n} most frequent of its {len(vocab) - 256:,} words (plus the 256 bytes)"}
    step = max(1, (len(vocab) - 256) // SYMBOL_SAMPLE)
    return {"ids": range(256, len(vocab), step), "sampled": True,
            "note": f"every {step}th of its {len(vocab):,} tokens (ids 0-255 are the single bytes)"}


def create_app(service: EncoderService | None = None, static_dir: Path | None = None,
               rate_limit: int | None = None) -> FastAPI:
    """Build the app: API routes first, then the frontend mounted at / (so /api/* always wins).

    rate_limit: API calls per minute per client (default ARITH_RATE_LIMIT; None or 0: no limit).
    """
    app = FastAPI(title="Arithmetic-coding encoder showcase")
    encoders = service or EncoderService(wait_seconds=_env_number("ARITH_WAIT_SECONDS", float))

    origins = [o for o in os.environ.get("ARITH_CORS_ORIGINS", "").split(",") if o]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    per_minute = rate_limit if rate_limit is not None else _env_number("ARITH_RATE_LIMIT")
    if per_minute:
        limiter = RateLimiter(per_minute)

        @app.middleware("http")
        async def limit_api_calls(request: Request, call_next):
            if request.method == "POST" and request.url.path.startswith("/api/"):
                # behind a proxy (Hugging Face, Render, ...) the client is the first X-Forwarded-For hop
                forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
                client = forwarded or (request.client.host if request.client else "?")
                if not limiter.allow(client):
                    return JSONResponse(status_code=429, content={
                        "detail": f"too many requests: at most {per_minute} a minute, please wait a moment"})
            return await call_next(request)

    @app.exception_handler(ServerBusy)
    async def busy(_request: Request, error: ServerBusy):
        return JSONResponse(status_code=503, content={"detail": str(error)})

    @app.get("/api/health")
    def health() -> dict:
        """For the host's health check: the app is up, and how many encoders it lists."""
        return {"ok": True, "models": sum(1 for s in list_models() if s.available and s.info.get("showcase", True))}

    @app.get("/api/models", response_model=ModelsResponse)
    def get_models() -> dict:
        """The showcase's models (with what they were trained on), and the one to show first.

        Models marked "showcase": false (redundant next to another one) stay usable by id, unlisted.
        """
        specs = [s for s in list_models() if s.info.get("showcase", True)]
        available = {s.id for s in specs if s.available}
        default = next((m for m in DEFAULT_MODELS if m in available), next(iter(available), ""))
        return {"models": [_model_info(s) for s in specs], "default": default}

    @app.get("/api/models/{model_id}/symbols", response_model=SymbolsResponse)
    def get_symbols(model_id: str) -> dict:
        """A model's symbols (its alphabet): all of them, or a sample for big vocabularies."""
        try:
            spec = _available_spec(model_id)
        except ModelBankError as e:
            raise HTTPException(status_code=404, detail=str(e)) from e
        tokenizer = _tokenizer(spec)
        sample = _symbol_sample(spec)
        return {"model_id": model_id, "tokenizer": spec.tokenizer, "count": len(tokenizer.vocab),
                "symbols": [{"id": i, "label": _label(tokenizer, i)} for i in sample["ids"]],
                "sampled": sample["sampled"], "note": sample["note"]}

    @app.post("/api/tokenize", response_model=TokenizeResponse)
    def tokenize(request: TokenizeRequest) -> dict:
        """How a model cuts text into symbols, with each symbol's character span (no model run)."""
        try:
            spec = _available_spec(request.model_id)
        except ModelBankError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        tokenizer = _tokenizer(spec)
        unknown = tokenizer.unknown_chars(request.text)
        if unknown:
            raise HTTPException(status_code=422, detail={"message": str(UnknownSymbolError(unknown)),
                                                         "unknown_chars": unknown})
        ids = tokenizer.encode(request.text)
        spans = char_spans(request.text, tokenizer, ids)
        return {"model_id": spec.id, "tokenizer": spec.tokenizer, "text": request.text,
                "symbols": [{"id": i, "label": _label(tokenizer, i), "char_start": a, "char_end": b}
                            for i, (a, b) in zip(ids, spans)]}

    @app.post("/api/encode", response_model=EncodeResponse)
    def encode(request: EncodeRequest) -> dict:
        """Encode text with one model and return the step-by-step trace for the animation."""
        try:
            return encoders.encode(request.model_id, request.text)
        except ModelBankError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except UnknownSymbolError as e:
            raise HTTPException(status_code=422, detail={"message": str(e), "unknown_chars": e.chars}) from e

    @app.post("/api/decode", response_model=DecodeResponse)
    def decode(request: DecodeRequest) -> dict:
        """Decode payload bits back into text: proof that the bits alone carry the message."""
        try:
            return {"text": encoders.decode(request.model_id, request.bits, request.symbols)}
        except ModelBankError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        except (ValueError, IndexError, UnicodeDecodeError) as e:  # bits that aren't a valid message
            raise HTTPException(status_code=422, detail=f"these bits don't decode: {e}") from e

    static = static_dir or frontend_dir()
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    return app


def main() -> None:
    """Console entry point (arith-demo): serve the API and the frontend."""
    import uvicorn

    parser = argparse.ArgumentParser(description="Arithmetic-coding encoder showcase.")
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", 8000)))
    parser.add_argument("--preload", default=os.environ.get("ARITH_PRELOAD", ""),
                        help='"all", or comma-separated model ids, to load before serving')
    args = parser.parse_args()
    service = EncoderService(wait_seconds=_env_number("ARITH_WAIT_SECONDS", float))
    if args.preload:
        listed = [s.id for s in list_models() if s.available and s.info.get("showcase", True)]
        ids = listed if args.preload == "all" else [i for i in args.preload.split(",") if i]
        for model_id in ids:
            start = time.perf_counter()
            service.warm_up([model_id])
            print(f"loaded {model_id} in {time.perf_counter() - start:.1f} s", flush=True)
    print(f"open http://{args.host}:{args.port}", flush=True)
    uvicorn.run(create_app(service), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
