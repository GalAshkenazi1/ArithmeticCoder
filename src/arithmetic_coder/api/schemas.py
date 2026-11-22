"""Request / response models for the demo API."""
from typing import Literal

from pydantic import BaseModel, Field

MAX_MESSAGE_CHARS = 280  # keeps the trace (and the animation) bounded


class ModelInfo(BaseModel):
    """One model the demo can switch to."""

    id: str
    name: str
    description: str
    vocab_size: int
    available: bool


class ModelsResponse(BaseModel):
    """All models, plus the one Alice and Bob currently share."""

    models: list[ModelInfo]
    current: str


class StateResponse(BaseModel):
    """The shared session between Alice and Bob."""

    model_id: str
    model_name: str
    fingerprint_hex: str
    vocab_size: int
    vocab: list[str]
    key: str


class SwitchRequest(BaseModel):
    """Switch both users to another model (and optionally another shared key)."""

    model_id: str
    key: str | None = Field(default=None, min_length=1, max_length=64)


class SendRequest(BaseModel):
    """A message from one user to the other."""

    sender: Literal["alice", "bob"]
    text: str = Field(max_length=MAX_MESSAGE_CHARS)


class WireSegment(BaseModel):
    """A byte range of the wire frame: [start, end)."""

    name: Literal["fingerprint", "length", "payload"]
    start: int
    end: int


class SendStats(BaseModel):
    """Sizes of one message."""

    chars: int
    original_bits: int       # 8 x UTF-8 bytes
    compressed_bits: int     # k, the payload's exact bit count
    wire_bytes: int          # whole frame, header included
    bpc: float               # k / chars
    compression_ratio: float  # original bits / wire bits


class SendResponse(BaseModel):
    """Everything the frontend shows for one sent message."""

    sender: str
    receiver: str
    text: str
    decoded_text: str
    model_id: str
    fingerprint_hex: str
    wire_hex: str
    wire_bits: str
    wire_layout: list[WireSegment]
    stats: SendStats
    trace: list[dict]
