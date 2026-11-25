"""Which model compresses which kind of text? Every bank model encodes held-out text from every corpus.

For each corpus, 12 snippets of ~250 characters are taken from its validation split (the last 10%
of the cleaned text, which no model was trained on) and encoded one by one with the real arithmetic
coder. The score is total payload bits / total characters. A model whose vocabulary lacks some of a
snippet's characters can't encode it at all: those cells are marked "-".

Run (from the project root, after training the models):
    uv run --group studies python studies/02_model_bank/compare_bank.py
"""
import csv
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from arithmetic_coder import ArithmeticCoder, list_models, load_model

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE.parent))
from _shared.style import INK, INK2, MUTED, RAMP, SURFACE  # noqa: E402
from _shared.surprisal import CORPORA, held_out_snippets  # noqa: E402

SNIPPETS, SNIPPET_CHARS = 12, 250  # held_out_snippets' defaults

def main() -> None:
    specs = [s for s in list_models() if s.available and s.id != "uniform"]  # uniform_ascii covers the baseline
    texts = {label: held_out_snippets(corpus, kind) for corpus, kind, label in CORPORA}
    table: dict[str, dict[str, float | None]] = {}
    for spec in specs:
        coder = ArithmeticCoder(load_model(spec.id))
        row, start = {}, time.time()
        for label, snippets in texts.items():
            if any(coder.tokenizer.unknown_chars(s) for s in snippets):
                row[label] = None
                continue
            bits = sum(len(coder.encode(s).to_bits()) for s in snippets)
            row[label] = bits / sum(map(len, snippets))
        table[spec.name] = row
        print(f"{spec.name:18s} " + "  ".join(f"{v:5.2f}" if v else "    -" for v in row.values())
              + f"   ({time.time() - start:.0f}s)", flush=True)

    RESULTS.mkdir(exist_ok=True)
    columns = [label for _, _, label in CORPORA]
    with open(RESULTS / "bits_per_char.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["model"] + columns)
        for name, row in table.items():
            writer.writerow([name] + [f"{row[c]:.3f}" if row[c] else "" for c in columns])

    best = {c: min((r[c] for r in table.values() if r[c]), default=None) for c in columns}
    lines = [
        "# Bits per character: every model on every kind of text",
        "",
        f"{SNIPPETS} held-out snippets of ~{SNIPPET_CHARS} chars per corpus (validation split, never trained on), "
        "each encoded as one message with the real coder. Lower is better; **bold** = best for that text; "
        "'-' = the model's vocabulary can't encode that text (digits, brackets, ...).",
        "",
        "| model | " + " | ".join(columns) + " |",
        "|---|" + "---:|" * len(columns),
    ]
    for name, row in table.items():
        cells = []
        for c in columns:
            v = row[c]
            cells.append("-" if v is None else (f"**{v:.2f}**" if v == best[c] else f"{v:.2f}"))
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    (RESULTS / "bits_per_char.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    plot_heatmap(table, columns, best, RESULTS / "bits_per_char.png")
    print(f"wrote {RESULTS}")


def plot_heatmap(table, columns, best, path) -> None:
    """Models x text kinds, coloured by bits/char (one hue, darker = more bits), values printed in cells."""
    names = list(table)
    values = [v for row in table.values() for v in row.values() if v is not None]
    lo, hi = min(values), max(values)
    fig, ax = plt.subplots(figsize=(1.6 * len(columns) + 2.6, 0.55 * len(names) + 1.6), facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    for i, name in enumerate(names):
        for j, col in enumerate(columns):
            v = table[name][col]
            if v is None:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=SURFACE, edgecolor="#e1e0d9", linewidth=1))
                ax.text(j + 0.5, i + 0.5, "-", ha="center", va="center", color=MUTED, fontsize=9)
                continue
            step = round((v - lo) / (hi - lo) * (len(RAMP) - 1)) if hi > lo else 0
            ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=RAMP[step], edgecolor=SURFACE, linewidth=2))
            ink = "#ffffff" if step >= 3 else INK
            weight = "bold" if v == best[col] else "normal"
            ax.text(j + 0.5, i + 0.5, f"{v:.2f}" + (" *" if v == best[col] else ""), ha="center", va="center",
                    color=ink, fontsize=9, fontweight=weight)
    ax.set_xlim(0, len(columns))
    ax.set_ylim(len(names), 0)
    ax.set_xticks([j + 0.5 for j in range(len(columns))], columns, color=INK2, fontsize=9)
    ax.set_yticks([i + 0.5 for i in range(len(names))], names, color=INK2, fontsize=9)
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    for side in ax.spines.values():
        side.set_visible(False)
    ax.set_title("Bits per character on held-out text (lower is better, * = best for that text)",
                 color=INK, fontsize=11, loc="left", pad=28)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    main()
