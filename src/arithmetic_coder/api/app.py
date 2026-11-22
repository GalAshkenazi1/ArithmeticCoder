"""FastAPI backend for the web demo: a JSON API under /api, plus static serving of the separate frontend/.

Run:  uv run arith-demo [--host 127.0.0.1] [--port 8000]
Dev:  uv run uvicorn --factory arithmetic_coder.api.app:create_app --reload

The frontend lives in the repo's frontend/ folder (override with ARITH_FRONTEND_DIR). To serve it
from somewhere else, list its origin in ARITH_CORS_ORIGINS (comma-separated).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from arithmetic_coder.api.demo_state import DemoState, UnknownCharactersError
from arithmetic_coder.api.schemas import (
    ModelInfo,
    ModelsResponse,
    SendRequest,
    SendResponse,
    StateResponse,
    SwitchRequest,
)
from arithmetic_coder.models.registry import REPO_ROOT, ModelBankError, list_models


def frontend_dir() -> Path:
    """Where the static frontend lives (ARITH_FRONTEND_DIR, or the repo's frontend/)."""
    return Path(os.environ.get("ARITH_FRONTEND_DIR", REPO_ROOT / "frontend"))


def create_app(state: DemoState | None = None, static_dir: Path | None = None) -> FastAPI:
    """Build the app: API routes first, then the frontend mounted at / (so /api/* always wins)."""
    app = FastAPI(title="Arithmetic-coding P2P demo")
    demo = state or DemoState()

    origins = [o for o in os.environ.get("ARITH_CORS_ORIGINS", "").split(",") if o]
    if origins:
        app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["*"], allow_headers=["*"])

    @app.get("/api/models", response_model=ModelsResponse)
    def get_models() -> dict:
        """All models in the registry and the one in use."""
        models = [ModelInfo(id=s.id, name=s.name, description=s.description,
                            vocab_size=s.vocab_size, available=s.available) for s in list_models()]
        return {"models": models, "current": demo.model_id}

    @app.get("/api/state", response_model=StateResponse)
    def get_state() -> dict:
        """The shared Alice/Bob session."""
        return demo.state()

    @app.post("/api/switch_model", response_model=StateResponse)
    def switch_model(request: SwitchRequest) -> dict:
        """Move both users to another model (and optionally key) at once."""
        try:
            demo.switch(request.model_id, request.key)
        except ModelBankError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
        return demo.state()

    @app.post("/api/send", response_model=SendResponse)
    def send(request: SendRequest) -> dict:
        """Encode on the sender's side, send the real wire frame, decode on the receiver's side."""
        try:
            return demo.send(request.sender, request.text)
        except UnknownCharactersError as e:
            raise HTTPException(status_code=422, detail={"message": str(e), "unknown_chars": e.chars}) from e

    static = static_dir or frontend_dir()
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    return app


def main() -> None:
    """Console entry point (arith-demo): serve the API and the frontend."""
    import uvicorn

    parser = argparse.ArgumentParser(description="Interactive arithmetic-coding chat demo.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    print(f"open http://{args.host}:{args.port}")
    uvicorn.run(create_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
