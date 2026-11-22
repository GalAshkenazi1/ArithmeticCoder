"""Compare encoded message length (in bits) across three character models.

Models:
  - nanoGPT Shakespeare: char-level nanoGPT trained on Tiny Shakespeare    (model_bank/shakespeare_char)
  - nanoGPT English:     same architecture, trained on Gutenberg prose     (model_bank/english_char)
  - Uniform:             UniformModelWrapper over the same 65-char vocab   (log2(65) = 6.02 bits/char)

Train the models first:
    python model_bank/train_nanogpt.py shakespeare_char
    python model_bank/train_nanogpt.py english_char

Run (from the project root):
    python research/01_compare_models/compare_models.py

Outputs go to research/01_compare_models/results/.
"""
import csv
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BANK = ROOT / "model_bank"
RESULTS = HERE / "results"
sys.path[:0] = [str(ROOT), str(BANK / "nanoGPT")]

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from model import GPT, GPTConfig  # nanoGPT's model.py

from src.encdec import ArithmeticCoder
from src.modelwrapper import ModelWrapper, UniformModelWrapper

RAW_BITS_PER_CHAR = 8  # plain 8-bit text, for reference

# chart tokens (dataviz reference palette, light mode): categorical slots 1-3 + recessive chrome
COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"


def load_nanogpt(name: str) -> ModelWrapper:
    """Load a char-level nanoGPT checkpoint from the model bank."""
    folder = BANK / name
    return ModelWrapper.from_nanogpt_checkpoint(
        folder / "ckpt.pt", lambda **args: GPT(GPTConfig(**args)), folder / "meta.pkl"
    )


def measure(coder: ArithmeticCoder, sentences: list[str]) -> list[dict]:
    """Encode every sentence, check that it decodes back, and record its length in bits."""
    rows = []
    for text in sentences:
        t0 = time.perf_counter()
        pack = coder.encode(text)
        seconds = time.perf_counter() - t0
        rows.append({"bits": len(pack.to_bits()), "ok": coder.decode(pack) == text, "seconds": seconds})
    return rows


def style(ax, grid_axis: str) -> None:
    """Apply recessive chrome: no top/right spines, hairline grid, muted ticks."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelcolor=INK2)
    ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def new_figure(width: float, height: float):
    """Create a figure + axes on the chart surface color."""
    fig, ax = plt.subplots(figsize=(width, height), facecolor=SURFACE)
    return fig, ax


def plot_bits_per_char(names, bpc, path):
    """Horizontal bars: overall bits per character per model, with the 8-bit raw-text reference."""
    fig, ax = new_figure(7.5, 3.2)
    style(ax, "x")
    y = range(len(names))[::-1]
    ax.barh(list(y), bpc, height=0.5, color=COLORS, edgecolor=SURFACE, linewidth=2)
    for yi, v in zip(y, bpc):
        ax.text(v + 0.1, yi, f"{v:.2f}  ({100 * v / RAW_BITS_PER_CHAR:.0f}%)", va="center", color=INK, fontsize=9)
    ax.axvline(RAW_BITS_PER_CHAR, color=INK2, linewidth=1.2, linestyle="--")
    ax.text(RAW_BITS_PER_CHAR - 0.08, -0.45, "raw 8-bit text", ha="right", va="bottom", color=INK2, fontsize=9)
    ax.set_yticks(list(y), names)
    ax.set_ylim(-0.5, len(names) - 0.5)
    ax.set_xlim(0, RAW_BITS_PER_CHAR + 0.4)
    ax.set_xlabel("bits per character (total bits / total characters); label: value (% of raw size)", color=INK2)
    ax.set_title("Encoded size per character, 100 Shakespeare-style sentences", color=INK, loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_bits_vs_length(names, lengths, bits, bpc, path):
    """Scatter: encoded bits vs sentence length per model, with each model's average-rate line."""
    fig, ax = new_figure(7.5, 4.8)
    style(ax, "both")
    x_max = max(lengths) * 1.04
    # end-of-line label heights, pushed apart so close lines don't get overlapping labels
    label_y = {}
    gap = 0.08 * max(bpc) * x_max
    for k in sorted(range(len(names)), key=lambda k: bpc[k]):
        y = bpc[k] * x_max
        prev = [v for v in label_y.values() if v <= y + gap]
        label_y[k] = max([y] + [v + gap for v in prev])
    for k, (name, color, b, rate) in enumerate(zip(names, COLORS, bits, bpc)):
        ax.scatter(lengths, b, s=28, color=color, edgecolor=SURFACE, linewidth=0.8, alpha=0.9, label=name, zorder=3)
        ax.plot([0, x_max], [0, rate * x_max], color=color, linewidth=1.5, alpha=0.6, zorder=2)
        ax.text(x_max, label_y[k], f"  {name}\n  {rate:.2f} bits/char", color=INK2, fontsize=8, va="center")
    ax.set_xlim(0, x_max)
    ax.set_ylim(0, None)
    ax.set_xlabel("sentence length (characters)", color=INK2)
    ax.set_ylabel("encoded length (bits)", color=INK2)
    ax.set_title("Encoded length vs sentence length", color=INK, loc="left", fontsize=11)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9, loc="upper left")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def plot_bpc_distribution(names, per_sentence_bpc, path):
    """Box + jittered points: spread of per-sentence bits per character for each model."""
    fig, ax = new_figure(7.5, 3.6)
    style(ax, "x")
    y = list(range(len(names)))[::-1]
    for yi, color, values in zip(y, COLORS, per_sentence_bpc):
        ax.boxplot(values, positions=[yi], vert=False, widths=0.45, showfliers=False,
                   medianprops=dict(color=INK, linewidth=1.5), boxprops=dict(color=color, linewidth=1.5),
                   whiskerprops=dict(color=color, linewidth=1.2), capprops=dict(color=color, linewidth=1.2))
        jitter = [yi + 0.18 * ((i * 0.618) % 1 - 0.5) for i in range(len(values))]  # deterministic jitter
        ax.scatter(values, jitter, s=12, color=color, alpha=0.55, edgecolor="none", zorder=3)
    ax.axvline(RAW_BITS_PER_CHAR, color=INK2, linewidth=1.2, linestyle="--")
    ax.set_yticks(y, names)
    ax.set_xlim(0, RAW_BITS_PER_CHAR + 0.4)
    ax.set_xlabel("bits per character, per sentence (dashed: raw 8-bit text)", color=INK2)
    ax.set_title("Per-sentence spread", color=INK, loc="left", fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def main() -> None:
    """Run all models over all sentences and write tables + figures to results/."""
    sentences = json.loads((HERE / "sentences.json").read_text(encoding="utf-8"))["sentences"]
    shakespeare = load_nanogpt("shakespeare_char")
    models = {
        "nanoGPT Shakespeare": shakespeare,
        "nanoGPT English": load_nanogpt("english_char"),
        "Uniform": UniformModelWrapper(shakespeare.get_vocab()),
    }
    names = list(models)

    results = {}
    for name, model in models.items():
        t0 = time.perf_counter()
        results[name] = measure(ArithmeticCoder(model), sentences)
        print(f"{name:20s} done in {time.perf_counter() - t0:.1f}s")

    lengths = [len(s) for s in sentences]
    total_chars = sum(lengths)
    bits = [[r["bits"] for r in results[n]] for n in names]
    per_sentence_bpc = [[b / L for b, L in zip(bs, lengths)] for bs in bits]
    overall_bpc = [sum(bs) / total_chars for bs in bits]
    best = [min(col) for col in zip(*bits)]

    RESULTS.mkdir(exist_ok=True)

    # per-sentence table
    with open(RESULTS / "per_sentence.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "chars", "raw_bits", *[f"bits_{n}" for n in names], *[f"bpc_{n}" for n in names], "text"])
        for i, text in enumerate(sentences):
            w.writerow([i, lengths[i], RAW_BITS_PER_CHAR * lengths[i], *[bs[i] for bs in bits],
                        *[f"{v[i]:.3f}" for v in per_sentence_bpc], text])

    # summary table
    summary = []
    for k, n in enumerate(names):
        summary.append({
            "model": n,
            "mean_bits": statistics.mean(bits[k]),
            "median_bits": statistics.median(bits[k]),
            "total_bits": sum(bits[k]),
            "bits_per_char": overall_bpc[k],
            "pct_of_raw": 100 * overall_bpc[k] / RAW_BITS_PER_CHAR,
            "best_on": sum(b == m for b, m in zip(bits[k], best)),
            "roundtrip_ok": sum(r["ok"] for r in results[n]),
            "mean_encode_ms": 1000 * statistics.mean(r["seconds"] for r in results[n]),
        })
    with open(RESULTS / "summary.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(summary[0]))
        w.writeheader()
        w.writerows(summary)

    md = [
        "# Encoded length by model",
        "",
        f"{len(sentences)} Shakespeare-style sentences, {total_chars:,} characters "
        f"(mean {total_chars / len(sentences):.1f} chars). Raw 8-bit text = {RAW_BITS_PER_CHAR * total_chars:,} bits.",
        "",
        "| model | mean bits | median bits | total bits | bits/char | % of raw | best on | round-trip ok | encode ms |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        *[f"| {s['model']} | {s['mean_bits']:.1f} | {s['median_bits']:.0f} | {s['total_bits']:,} | "
          f"{s['bits_per_char']:.2f} | {s['pct_of_raw']:.0f}% | {s['best_on']} | "
          f"{s['roundtrip_ok']}/{len(sentences)} | {s['mean_encode_ms']:.0f} |" for s in summary],
        "",
        "- **best on**: number of sentences where that model gave the shortest encoding (ties count for each).",
        "- **% of raw**: encoded size relative to 8 bits per character.",
        "",
        "Figures: `bits_per_char.png`, `bits_vs_length.png`, `bpc_distribution.png`.",
    ]
    (RESULTS / "summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    plot_bits_per_char(names, overall_bpc, RESULTS / "bits_per_char.png")
    plot_bits_vs_length(names, lengths, bits, overall_bpc, RESULTS / "bits_vs_length.png")
    plot_bpc_distribution(names, per_sentence_bpc, RESULTS / "bpc_distribution.png")

    print("\n".join(md[4:4 + 2 + len(summary)]))
    print(f"\nwrote results to {RESULTS}")


if __name__ == "__main__":
    main()
