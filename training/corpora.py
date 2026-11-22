"""Training corpora: download once, clean, and restrict to a model's vocabulary.

Each corpus function returns plain text. Downloads are cached in training/_downloads/ and the
cleaned text in training/_data/ (both git-ignored, except the original Shakespeare/Gutenberg files).
"""
from __future__ import annotations

import gzip
import json
import sys
import unicodedata
import urllib.request
from pathlib import Path

from arithmetic_coder.models.registry import ASCII_VOCAB

HERE = Path(__file__).resolve().parent
DOWNLOADS = HERE / "_downloads"
CACHE = HERE / "_data"

SHAKESPEARE_URL = "https://raw.githubusercontent.com/karpathy/char-rnn/master/data/tinyshakespeare/input.txt"
GUTENBERG_IDS = [1342, 1661, 98, 84, 11]  # Pride and Prejudice, Sherlock Holmes, A Tale of Two Cities, Frankenstein, Alice
WIKITEXT_URL = ("https://huggingface.co/datasets/Salesforce/wikitext/resolve/main/"
                "wikitext-2-raw-v1/train-00000-of-00001.parquet")
TINYSTORIES_URL = "https://huggingface.co/datasets/roneneldan/TinyStories/resolve/main/TinyStoriesV2-GPT4-valid.txt"
C4_URL = "https://huggingface.co/datasets/allenai/c4/resolve/main/en/c4-validation.00000-of-00008.json.gz"

MAX_CHARS = 12_000_000  # cap per corpus (train + validation)

# typography -> ASCII, applied before dropping characters outside the vocabulary
_TYPOGRAPHY = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'",
    "“": '"', "”": '"', "„": '"', "«": '"', "»": '"',
    "–": "-", "—": "-", "−": "-", "…": "...", " ": " ", "\t": "    ",
}


def download(url: str, name: str) -> Path:
    """Download url once into training/_downloads/ and return the local path."""
    DOWNLOADS.mkdir(exist_ok=True)
    path = DOWNLOADS / name
    if not path.exists():
        print(f"downloading {url}", flush=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research script)"})
        with urllib.request.urlopen(request) as response:
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(response.read())
            tmp.replace(path)
    return path


def restrict(text: str, vocab: list[str]) -> str:
    """Map typography to ASCII, strip accents, and drop every character outside vocab."""
    allowed = set(vocab)
    text = text.replace("\r\n", "\n")
    for src, dst in _TYPOGRAPHY.items():
        text = text.replace(src, dst)
    if '"' not in allowed:  # the 65-char Shakespeare vocab has no double quote
        text = text.replace('"', "'")
    text = unicodedata.normalize("NFKD", text)  # e -> e + combining accent (dropped below)
    return "".join(c for c in text if c in allowed)


# ---- the corpora ---------------------------------------------------------------------------

def shakespeare() -> str:
    """Tiny Shakespeare (~1.1M chars)."""
    return download(SHAKESPEARE_URL, "tinyshakespeare.txt").read_text(encoding="utf-8")


def _strip_gutenberg(text: str) -> str:
    """Remove the Project Gutenberg licence header and footer."""
    start, end = text.find("*** START OF"), text.find("*** END OF")
    return (text[text.find("\n", start) + 1: end] if start != -1 and end != -1 else text).strip()


def gutenberg() -> str:
    """Five 19th-century novels from the official aleph.pglaf.org mirror (gutenberg.org blocks scripts)."""
    books = []
    for book_id in GUTENBERG_IDS:
        digits = str(book_id)
        url = f"https://aleph.pglaf.org/{'/'.join(digits[:-1]) or '0'}/{book_id}/{book_id}-0.txt"
        books.append(_strip_gutenberg(download(url, f"pg{book_id}.txt").read_text(encoding="utf-8")))
    return "\n\n".join(books)


def detokenize_wikitext(text: str) -> str:
    """Undo WikiText's tokenisation: ' @-@ ' -> '-', ' , ' -> ', ', spaces inside brackets, etc."""
    for src, dst in ((" @-@ ", "-"), (" @,@ ", ","), (" @.@ ", "."), (" , ", ", "), (" . ", ". "),
                     (" ; ", "; "), (" : ", ": "), (" 's", "'s"), (" n't", "n't"), ("( ", "("), (" )", ")"),
                     (" ' ", "' "), (' " ', ' "')):
        text = text.replace(src, dst)
    lines = [line.strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def wikitext() -> str:
    """WikiText-2 (raw): ~11M chars of Wikipedia 'good' and 'featured' articles."""
    import pyarrow.parquet as pq

    rows = pq.read_table(download(WIKITEXT_URL, "wikitext-2-raw-train.parquet")).column("text").to_pylist()
    return detokenize_wikitext("".join(rows))


def tinystories() -> str:
    """TinyStories (GPT-4 generated, validation split): short stories in simple English."""
    text = download(TINYSTORIES_URL, "TinyStoriesV2-GPT4-valid.txt").read_text(encoding="utf-8")
    stories = [s.strip() for s in text.split("<|endoftext|>")]
    return "\n\n".join(s for s in stories if s)


def c4_web() -> str:
    """C4 (Colossal Clean Crawled Corpus, English): cleaned modern web text."""
    docs, total = [], 0
    with gzip.open(download(C4_URL, "c4-validation-00000.json.gz"), "rt", encoding="utf-8") as f:
        for line in f:
            text = json.loads(line)["text"].strip()
            docs.append(text)
            total += len(text) + 2
            if total > MAX_CHARS * 1.1:  # a little extra; restrict() drops some characters
                break
    return "\n\n".join(docs)


def python_stdlib() -> str:
    """The Python standard library's own source code (from this Python installation), tests excluded."""
    lib = Path(sys.base_prefix) / "Lib"
    files = sorted(f for f in lib.rglob("*.py")
                   if "test" not in f.parts and "tests" not in f.parts and "site-packages" not in f.parts)
    return "\n\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in files)


CORPORA = {
    "shakespeare": shakespeare,
    "gutenberg": gutenberg,
    "wikitext": wikitext,
    "tinystories": tinystories,
    "c4": c4_web,
    "python": python_stdlib,
}


def shakespeare_vocab() -> list[str]:
    """The 65-character vocabulary of the original models: every character in Tiny Shakespeare."""
    return sorted(set(shakespeare()))


def vocabulary(kind: str) -> list[str]:
    """A vocabulary by name: 'shakespeare' (65 chars) or 'ascii' (96 chars)."""
    return shakespeare_vocab() if kind == "shakespeare" else list(ASCII_VOCAB)


def load_corpus(corpus: str, vocab_kind: str, max_chars: int = MAX_CHARS) -> str:
    """Cleaned corpus text restricted to the vocabulary (cached in training/_data/)."""
    CACHE.mkdir(exist_ok=True)
    cached = CACHE / f"{corpus}-{vocab_kind}.txt"
    if cached.exists():
        text = cached.read_text(encoding="utf-8")
    else:
        text = restrict(CORPORA[corpus](), vocabulary(vocab_kind))
        cached.write_text(text, encoding="utf-8", newline="\n")
    return text[:max_chars]
