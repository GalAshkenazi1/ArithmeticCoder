"""Arithmetic coding of text with character-level language models, plus a peer-to-peer chat on top.

Subpackages:
    coding  - the exact arithmetic coder, key-derived permutation, encoding traces
    models  - model wrappers, the vendored nanoGPT definition, and the model registry
    p2p     - peer sessions, wire protocol, relay server, CLI chat client
    api     - FastAPI backend for the web demo (frontend lives in the repo's frontend/ folder)

Importing this package does not load torch; models are loaded on demand.
"""
from arithmetic_coder.coding.encdec import ArithmeticCoder, MessagePack
from arithmetic_coder.models.registry import ModelSpec, list_models, load_model
from arithmetic_coder.p2p.client import UserClient

__all__ = ["ArithmeticCoder", "MessagePack", "ModelSpec", "UserClient", "list_models", "load_model"]
