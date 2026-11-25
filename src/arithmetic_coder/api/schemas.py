"""Request / response models for the encoder showcase API."""
from pydantic import BaseModel, Field

MAX_MESSAGE_CHARS = 280  # keeps the trace (and the animation) bounded


class Dataset(BaseModel):
    """What a model was trained on (model.json "dataset")."""

    name: str
    about: str = ""
    url: str | None = None
    chars: int | None = None  # size of the training text (train + validation), in characters


class TrainingInfo(BaseModel):
    """The few training facts the encoders page shows (model.json "training")."""

    params: int | None = None
    block_size: int | None = None            # symbols of context the model was trained with
    val_bits_per_char: float | None = None   # held-out cost on its own corpus
    chars_per_symbol: float | None = None


class ModelInfo(BaseModel):
    """One model (encoder) the showcase can use."""

    id: str
    name: str
    description: str
    vocab_size: int
    available: bool
    tokenizer: str = "char"  # "char", "bytes", "words", "gpt2"
    vocab: list[str] | None = None  # characters a char model accepts; None = any text works
    kind: str = "nanogpt"           # "nanogpt" or "uniform" (no model)
    dataset: Dataset | None = None  # None: not trained on anything (uniform) or not recorded
    examples: list[str] = []        # typical sentences in the style it was trained on
    training: TrainingInfo | None = None
    context_tokens: int | None = None  # context cap at inference, if smaller than the trained block


class ModelsResponse(BaseModel):
    """All models, plus the one to show first."""

    models: list[ModelInfo]
    default: str


class EncodeRequest(BaseModel):
    """Text to encode with one model."""

    model_id: str
    text: str = Field(max_length=MAX_MESSAGE_CHARS)


class EncodeStats(BaseModel):
    """Sizes of one encoded text."""

    chars: int
    symbols: int          # how many symbols the tokenizer made of the text
    payload_bits: int     # k, the binary fraction's exact digit count
    payload_bytes: int
    utf8_bits: int        # the same text as plain UTF-8
    bpc: float            # payload bits per character
    bits_per_symbol: float
    ratio: float          # UTF-8 bits / payload bits


class EncodeResponse(BaseModel):
    """The encoded text, its sizes, and one trace record per symbol for the animation."""

    model_id: str
    model_name: str
    tokenizer: str
    precision_bits: int
    text: str
    bits: str             # binary digits of the shortest fraction inside the final interval
    symbols: int
    stats: EncodeStats
    trace: list[dict]


class DecodeRequest(BaseModel):
    """Payload bits to decode back into text (the decoder needs the symbol count too)."""

    model_id: str
    bits: str = Field(pattern=r"^[01]*$", max_length=20_000)
    symbols: int = Field(ge=0, le=4 * MAX_MESSAGE_CHARS)


class DecodeResponse(BaseModel):
    text: str


class Symbol(BaseModel):
    """One symbol of a tokenizer: its id and a display label (a char, a word, a token, or \\xNN)."""

    id: int
    label: str


class SymbolsResponse(BaseModel):
    """A model's symbols: all of them for small vocabularies, a sample for big ones."""

    model_id: str
    tokenizer: str
    count: int            # vocabulary size
    symbols: list[Symbol]
    sampled: bool         # True: symbols is a sample (see note)
    note: str = ""


class TokenizeRequest(BaseModel):
    model_id: str
    text: str = Field(max_length=MAX_MESSAGE_CHARS)


class TokenSpan(BaseModel):
    """One symbol of a tokenized text and the characters [char_start, char_end) it covers."""

    id: int
    label: str
    char_start: int
    char_end: int


class TokenizeResponse(BaseModel):
    """How a model's tokenizer cuts a text into symbols (no model run: instant)."""

    model_id: str
    tokenizer: str
    text: str
    symbols: list[TokenSpan]
