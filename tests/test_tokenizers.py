"""Tests for the tokenizers and for coding with each of them."""
import pytest

from arithmetic_coder import ArithmeticCoder, list_models, load_model
from arithmetic_coder.coding.permutation import keyed_coder
from arithmetic_coder.models.registry import ASCII_VOCAB, DEFAULT_BANK
from arithmetic_coder.models.wrappers import UniformModelWrapper
from arithmetic_coder.tokenizers import CharTokenizer, UnknownSymbolError, char_spans
from arithmetic_coder.tokenizers.bytes import ByteTokenizer
from arithmetic_coder.tokenizers.words import WordTokenizer, build_word_list

TEXTS = ["", "a", "Hello, world!\nSecond line.", "naïve café — “quotes”", "שלום עולם", "emoji 👋🏽 ok", "  two  spaces\n\n"]
GPT2_DIR = DEFAULT_BANK / "gpt2"


def gpt2_tokenizer():
    if not (GPT2_DIR / "vocab.json").exists():
        pytest.skip("GPT-2 not fetched (run training/fetch_gpt2.py)")
    from arithmetic_coder.tokenizers.gpt2_bpe import GPT2Tokenizer

    return GPT2Tokenizer.from_files(GPT2_DIR / "vocab.json", GPT2_DIR / "merges.txt")


@pytest.mark.parametrize("text", TEXTS)
def test_bytes_roundtrip(text):
    tok = ByteTokenizer()
    assert tok.decode(tok.encode(text)) == text
    assert len(tok.encode(text)) == len(text.encode("utf-8"))


@pytest.mark.parametrize("text", TEXTS)
def test_words_roundtrip_and_escape(text):
    tok = WordTokenizer([" world", "Hello", " line", " two", " spaces", "שלום"])
    ids = tok.encode(text)
    assert tok.decode(ids) == text
    if "Hello" in text:
        assert tok.word_index["Hello"] in ids and tok.word_index[" world"] in ids


def test_word_list_is_built_from_frequent_pieces():
    # " and" and " the" appear twice; ties are broken alphabetically, then the single-use pieces
    assert build_word_list("the cat and the dog and the bird", 3) == [" and", " the", " bird"]


def test_char_tokenizer_rejects_unknown():
    tok = CharTokenizer(list(ASCII_VOCAB))
    with pytest.raises(UnknownSymbolError) as error:
        tok.encode("café ✓")
    assert set(error.value.chars) == {"é", "✓"}
    assert tok.unknown_chars("plain") == []


def test_char_spans_cover_multibyte_characters():
    tok = ByteTokenizer()
    text = "a👋b"
    spans = char_spans(text, tok, tok.encode(text))
    assert spans == [(0, 1)] + [(1, 2)] * 4 + [(2, 3)]


@pytest.mark.parametrize("text", TEXTS)
def test_coding_with_every_tokenizer(text):
    for tok in (ByteTokenizer(), WordTokenizer([" world", "Hello", " line"])):
        coder = ArithmeticCoder(UniformModelWrapper(tok))
        pack = coder.encode(text)
        assert pack.length == len(tok.encode(text))
        assert coder.decode(pack) == text


def test_fingerprint_depends_on_tokenizer():
    a = ArithmeticCoder(UniformModelWrapper(WordTokenizer([" the", " and"]))).fingerprint()
    b = ArithmeticCoder(UniformModelWrapper(WordTokenizer([" the", " cat"]))).fingerprint()
    assert a != b


@pytest.mark.parametrize("text, ids", [
    ("Hello world", [15496, 995]),
    ("The quick brown fox", [464, 2068, 7586, 21831]),
    ("\n", [198]),
    (" the", [262]),
])
def test_gpt2_known_encodings(text, ids):
    assert gpt2_tokenizer().encode(text) == ids


@pytest.mark.parametrize("text", TEXTS + ["<|endoftext|> is just text here", "x = f(a, b) ** 2  # done"])
def test_gpt2_roundtrip(text):
    tok = gpt2_tokenizer()
    assert tok.decode(tok.encode(text)) == text


def test_new_models_roundtrip_unicode():
    available = {s.id for s in list_models() if s.available}
    for model_id in ("web_bytes", "wiki_bytes", "web_words"):
        if model_id not in available:
            continue
        coder = keyed_coder(load_model(model_id), "key")
        for text in ("Grüße aus Zürich 👋", "שלום עולם", "plain old text."):
            assert coder.decode(coder.encode(text)) == text


@pytest.mark.parametrize("model_id", ["shakespeare_char", "web_small", "web_bytes", "web_words"])
def test_counts_do_not_depend_on_thread_count(model_id):
    """Peers must get identical counts; check 1 vs 4 inference threads give the same CDFs."""
    if model_id not in {s.id for s in list_models() if s.available}:
        pytest.skip(f"{model_id} not in the bank")
    model = load_model(model_id)
    coder = ArithmeticCoder(model)
    text = "To be, or not to be: that is the question."
    cdfs = {}
    for threads in (1, 4):
        model.threads = threads
        cdfs[threads] = [step.cdf for step in coder.iter_encode(text)]
    model.threads = 4
    assert cdfs[1] == cdfs[4]
