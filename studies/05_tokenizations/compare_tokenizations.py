"""Characters vs bytes vs words vs GPT-2's BPE: what each tokenization costs, gains and handles.

Same held-out text as studies 03/04 (validation splits nobody trained on), real coder numbers.
Every result is reported in bits per *character* of the original text, so tokenizations compare
fairly even though their symbols are different sizes.

Run (from the project root, after training web_bytes / wiki_bytes / web_words and fetching GPT-2):
    uv run --group studies python studies/05_tokenizations/compare_tokenizations.py
"""
import csv
import sys
import time
from pathlib import Path

import numpy as np
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE.parent))
from _shared.style import INK2, MODEL_COLORS, MUTED, SURFACE, new_figure, save, style, title  # noqa: E402
from _shared.surprisal import MODEL_NAMES, cost, held_out_snippets, symbol_costs  # noqa: E402
from corpora import load_corpus  # noqa: E402  (training/, put on sys.path by _shared.surprisal)

from arithmetic_coder import ArithmeticCoder, load_model  # noqa: E402

MODELS = ["web_small", "web_bytes", "web_words", "gpt2", "uniform_ascii", "uniform_bytes"]
TOKENIZER = {"web_small": "characters (96)", "web_bytes": "UTF-8 bytes (256)", "web_words": "words + bytes (4,352)",
             "gpt2": "GPT-2 BPE (50,257)", "uniform_ascii": "characters, no model", "uniform_bytes": "bytes, no model",
             "wiki_small": "characters (96)", "wiki_bytes": "UTF-8 bytes (256)"}
TEXT_KINDS = [("c4", "Web (C4)"), ("wikitext", "Wikipedia"), ("tinystories", "TinyStories")]
HANDWRITTEN_UNICODE = [
    "Grüße aus Zürich! Die Straßenbahn fährt um 7:45 Uhr ab.",
    "שלום עולם, מה שלומך היום? אני כותב הודעה קצרה.",
    "Le café est fermé, mais la crêperie à côté est ouverte.",
    "See you at 8 🙂 bring the 📦 and don't forget the 🎂!",
]


def unicode_snippets(n: int = 8, length: int = 250) -> list[str]:
    """Held-out web snippets that contain real non-ASCII text, plus a few handwritten multilingual lines."""
    text = load_corpus("c4", "utf8")
    val = text[int(0.9 * len(text)):]
    found, pos = [], 0
    while len(found) < n and pos < len(val) - length:
        start = val.find("\n", pos) + 1
        chunk = val[start: start + length].strip()
        if sum(ord(c) > 127 for c in chunk) >= 6:
            found.append(chunk)
            pos = start + length
        else:
            pos = start + 1
    return found + HANDWRITTEN_UNICODE


def bits_per_char(costs: list, texts: list[str]) -> float | None:
    """Real payload bits / characters over the texts a model could encode (None if it could encode none)."""
    pairs = [(c, t) for c, t in zip(costs, texts) if c is not None]
    if not pairs:
        return None
    return sum(b for c, _ in pairs for *_, b in c) / sum(len(t) for _, t in pairs)


def running_bpc(costs: list, length: int) -> np.ndarray:
    """Mean real bits per character after the first n characters, n = 1..length (from symbol end positions)."""
    curves = []
    for c in costs:
        if not c:
            continue
        bits_at_char = np.full(length + 1, np.nan)
        total = 0
        bits_at_char[0] = 0
        for _, _, end, _, b in c:
            total += b
            if end <= length:
                bits_at_char[end] = total
        # carry the last known total forward (characters inside a multi-character symbol)
        for i in range(1, length + 1):
            if np.isnan(bits_at_char[i]):
                bits_at_char[i] = bits_at_char[i - 1]
        curves.append(bits_at_char[1:] / np.arange(1, length + 1))
    return np.mean(curves, axis=0)


def encode_speed(model_id: str, texts: list[str]) -> tuple[float, float]:
    """(milliseconds per character to encode, characters per symbol) on the given texts."""
    coder = ArithmeticCoder(load_model(model_id))
    coder.encode(texts[0][:20])  # warm-up
    start, chars, symbols = time.perf_counter(), 0, 0
    for t in texts:
        symbols += coder.encode(t).length
        chars += len(t)
    return 1000 * (time.perf_counter() - start) / chars, chars / symbols


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    texts = {label: held_out_snippets(corpus, "ascii") for corpus, label in TEXT_KINDS}
    texts["Unicode (web + multilingual)"] = unicode_snippets()
    long_web = held_out_snippets("c4", "ascii", n=20, length=400)

    all_models = MODELS + ["wiki_small", "wiki_bytes"]
    costs = {m: {label: symbol_costs(m, t) for label, t in texts.items()} for m in all_models}
    table = {m: {label: bits_per_char(costs[m][label], t) for label, t in texts.items()} for m in all_models}
    speed = {m: encode_speed(m, texts["Web (C4)"][:4]) for m in MODELS}
    long_costs = {m: symbol_costs(m, long_web) for m in ["web_small", "web_bytes", "web_words", "gpt2"]}
    for m, row in table.items():
        print(f"{MODEL_NAMES[m]:16s} " + "  ".join(f"{v:5.2f}" if v else "    -" for v in row.values()), flush=True)

    plot_bpc(table, texts, RESULTS / "bpc_by_text.png")
    plot_speed(table, speed, RESULTS / "speed_vs_compression.png")
    plot_running(long_costs, RESULTS / "running_bpc_by_tokenizer.png")
    escapes = plot_word_escapes(costs, texts, RESULTS / "words_vs_escapes.png")
    write_stats(table, speed, long_costs, escapes, texts)


def plot_bpc(table, texts, path) -> None:
    fig, ax = new_figure(10, 4.4)
    style(ax, "x")
    labels = list(texts)[::-1]
    for offset, m in zip(np.linspace(-0.28, 0.28, len(MODELS)), MODELS):
        xs = [table[m][label] if table[m][label] is not None else np.nan for label in labels]
        ax.scatter(xs, [i + offset for i in range(len(labels))], s=48, color=MODEL_COLORS[m], edgecolor=SURFACE,
                   linewidth=1.2, zorder=3, label=f"{MODEL_NAMES[m]}  [{TOKENIZER[m]}]",
                   marker="D" if m.startswith("uniform") else "o")
    i_uni = labels.index("Unicode (web + multilingual)")
    ax.text(0.15, i_uni + 0.33, "character models can't encode this text at all", color=MUTED, fontsize=8)
    ax.set_yticks(range(len(labels)), labels)
    ax.set_xlim(0, None)
    ax.set_xlabel("bits per character of the original text (real payload) - lower is better", color=INK2)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5))
    title(ax, "Same text, four tokenizations", "held-out snippets; GPT-2 is ~40x bigger than the others (124M vs ~3M params)")
    save(fig, path)


def plot_speed(table, speed, path) -> None:
    fig, ax = new_figure(8.5, 4.6)
    style(ax)
    ax.set_xscale("log")
    # label offsets (points) chosen so neighbouring points' labels don't collide
    offsets = {"web_small": (-10, -26), "web_bytes": (8, 6), "web_words": (-10, 8), "gpt2": (8, 4),
               "uniform_ascii": (8, -24), "uniform_bytes": (8, -24)}
    for m in MODELS:
        ms, chars_per_symbol = speed[m]
        bpc = table[m]["Web (C4)"]
        ax.scatter([ms], [bpc], s=90, color=MODEL_COLORS[m], edgecolor=SURFACE, linewidth=1.5, zorder=3,
                   marker="D" if m.startswith("uniform") else "o")
        dx, dy = offsets[m]
        ax.annotate(f"{MODEL_NAMES[m]}\n{chars_per_symbol:.2f} chars/symbol", (ms, bpc), xytext=(dx, dy),
                    textcoords="offset points", fontsize=8, color=INK2, ha="right" if dx < 0 else "left")
    ax.set_xlabel("time to encode, ms per character (CPU, log scale)", color=INK2)
    ax.set_ylabel("bits per character (web text)", color=INK2)
    ax.set_ylim(0, 9)
    ax.set_xlim(None, ax.get_xlim()[1] * 4)
    title(ax, "Compression vs speed", "bigger symbols mean fewer model calls; a bigger model costs more per call")
    save(fig, path)


def plot_running(long_costs, path) -> None:
    fig, ax = new_figure(9, 4.4)
    style(ax)
    ax.set_xscale("log")
    for m, costs in long_costs.items():
        curve = running_bpc(costs, 380)
        ax.plot(np.arange(1, len(curve) + 1), curve, color=MODEL_COLORS[m], linewidth=1.8, label=MODEL_NAMES[m])
    ax.set_xticks([1, 5, 10, 20, 50, 100, 200, 380], ["1", "5", "10", "20", "50", "100", "200", "380"])
    ax.set_xlim(2, 380)
    ax.set_ylim(0, 6)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=8, loc="upper right")
    ax.set_xlabel("message length (characters, log scale)", color=INK2)
    ax.set_ylabel("real bits per character so far", color=INK2)
    title(ax, "Cost per character as a message grows (web text)",
          "multi-character symbols pay at their end, so short messages jump; GPT-2 keeps improving with context")
    save(fig, path)


WORD_GROUPS = [("whole-word symbols", "#e34948", "#ffffff"),
               ("letters of unlisted words (spelled out)", "#eda100", "#0b0b0b"),
               ("spaces, punctuation, digits (single bytes)", "#c3c2b7", "#0b0b0b")]


def word_group(symbol: str, span_text: str, tok) -> int:
    """0 = a listed word, 1 = a byte that spells part of an unlisted word, 2 = any other byte."""
    if symbol in tok.word_index:
        return 0
    return 1 if span_text[:1].isalpha() else 2


def plot_word_escapes(costs, texts, path) -> dict:
    """Web-Words: whole words vs spelled-out unlisted words vs other single bytes; symbols and bits."""
    from arithmetic_coder.models.registry import get_spec, load_tokenizer

    tok = load_tokenizer(get_spec("web_words").path, "words")
    result = {}
    for label in ("Web (C4)", "Unicode (web + multilingual)"):
        symbols, bits = [0, 0, 0], [0.0, 0.0, 0.0]
        for c, text in zip(costs["web_words"][label], texts[label]):
            for symbol, start, end, p, _ in c or []:
                g = word_group(symbol, text[start:end], tok)
                symbols[g] += 1
                bits[g] += cost(p)
        result[label] = ([s / sum(symbols) for s in symbols], [b / sum(bits) for b in bits])
    fig, ax = new_figure(10, 3.4)
    style(ax, None)
    rows = [(f"{label}: symbols", shares[0]) for label, shares in result.items()] + \
           [(f"{label}: bits", shares[1]) for label, shares in result.items()]
    for i, (_, shares) in enumerate(rows[::-1]):
        left = 0.0
        for (name, color, ink), share in zip(WORD_GROUPS, shares):
            ax.barh(i, share, left=left, color=color, height=0.55, edgecolor=SURFACE, linewidth=2)
            if share > 0.06:
                ax.text(left + share / 2, i, f"{share:.0%}", ha="center", va="center", color=ink, fontsize=8)
            left += share
    ax.set_yticks(range(len(rows)), [name for name, _ in rows[::-1]], fontsize=8)
    ax.set_xlim(0, 1)
    ax.set_xticks([])
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    handles = [Patch(color=c, label=n) for n, c, _ in WORD_GROUPS]
    ax.legend(handles=handles, frameon=False, labelcolor=INK2, fontsize=8, loc="upper center",
              bbox_to_anchor=(0.5, -0.02), ncols=3)
    title(ax, "Web-Words: what its symbols are, and where its bits go")
    save(fig, path)
    return result


def write_stats(table, speed, long_costs, escapes, texts) -> None:
    labels = list(texts)
    with open(RESULTS / "bits_per_char.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "tokenizer"] + labels)
        for m, row in table.items():
            w.writerow([MODEL_NAMES[m], TOKENIZER[m]] + [f"{row[l]:.3f}" if row[l] else "" for l in labels])
    md = ["# Study 05 - stats (generated)", "", "## Bits per character (real payload)", "",
          "| model | tokenizer | " + " | ".join(labels) + " |", "|---|---|" + "---:|" * len(labels)]
    for m, row in table.items():
        md.append(f"| {MODEL_NAMES[m]} | {TOKENIZER[m]} | " + " | ".join(f"{row[l]:.2f}" if row[l] else "-" for l in labels) + " |")
    md += ["", "## Speed (web text, CPU)", "", "| model | ms per char | chars per symbol |", "|---|---:|---:|"]
    for m, (ms, cps) in speed.items():
        md.append(f"| {MODEL_NAMES[m]} | {ms:.2f} | {cps:.2f} |")
    md += ["", "## Running bits/char on 400-char web messages", "", "| model | 10 chars | 50 | 100 | 380 |", "|---|---:|---:|---:|---:|"]
    for m, c in long_costs.items():
        curve = running_bpc(c, 380)
        md.append(f"| {MODEL_NAMES[m]} | {curve[9]:.2f} | {curve[49]:.2f} | {curve[99]:.2f} | {curve[379]:.2f} |")
    md += ["", "## Web-Words: what the symbols are (share of symbols / share of bits)", "",
           "| text | " + " | ".join(name for name, _, _ in WORD_GROUPS) + " |", "|---|" + "---:|" * len(WORD_GROUPS)]
    for label, (sym, bits) in escapes.items():
        md.append(f"| {label} | " + " | ".join(f"{s:.0%} / {b:.0%}" for s, b in zip(sym, bits)) + " |")
    (RESULTS / "stats.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
