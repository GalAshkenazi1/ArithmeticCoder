"""How do the models differ? Per-character costs of every model on held-out text of every kind.

Uses the same held-out snippets as study 02 (6 corpora x 12 x 250 chars) and the real coder's
per-character numbers (studies/_shared/surprisal.py). Writes figures + results/stats.md.

Run (from the project root):
    uv run --group studies python studies/03_model_differences/compare_models.py
"""
import csv
import sys
from pathlib import Path

import numpy as np
from matplotlib.patches import Rectangle

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE.parent))
from _shared.style import INK, INK2, MODEL_COLORS, MUTED, RAMP, SURFACE, new_figure, save, style, title  # noqa: E402
from _shared.surprisal import (  # noqa: E402
    CHAR_CLASSES, CORPORA, MODEL_NAMES, OWN_TEXT, char_class, char_costs, cost, held_out_snippets,
)

ASCII_MODELS = ["wiki_small", "stories_small", "web_small", "python_small"]
ALL_MODELS = list(OWN_TEXT) + ["uniform_ascii"]
FREE, RAW = 0.1, 8.0  # "free" characters cost under 0.1 bits; raw text costs 8


def load() -> tuple[dict, dict]:
    """texts[label] = snippets; costs[model][label] = per-text lists of (char, prob, bits_added) or None."""
    texts = {label: held_out_snippets(corpus, kind) for corpus, kind, label in CORPORA}
    costs = {m: {label: char_costs(m, texts[label]) for label in texts} for m in ALL_MODELS}
    return texts, costs


def flat(costs_for_label: list) -> list[tuple[str, float, int]]:
    """All characters of the encodable texts, flattened."""
    return [c for text in costs_for_label if text for c in text]


# ---- figure 1: cost by character class --------------------------------------------------------

def by_class(costs) -> dict[str, dict[str, float]]:
    """Mean cost per character class for each ASCII model + uniform, pooled over all 6 corpora."""
    table = {}
    for m in ASCII_MODELS + ["uniform_ascii"]:
        sums, counts = {k: 0.0 for k in CHAR_CLASSES}, {k: 0 for k in CHAR_CLASSES}
        for label in costs[m]:
            for ch, p, _ in flat(costs[m][label]):
                k = char_class(ch)
                sums[k] += cost(p)
                counts[k] += 1
        table[m] = {k: sums[k] / counts[k] for k in CHAR_CLASSES if counts[k]}
    return table


def plot_by_class(table, path) -> None:
    fig, ax = new_figure(9.2, 4.2)
    style(ax, "x")
    classes = CHAR_CLASSES[::-1]
    for offset, m in zip(np.linspace(-0.24, 0.24, len(table)), table):
        xs = [table[m].get(k, np.nan) for k in classes]
        ys = [i + offset for i in range(len(classes))]
        ax.scatter(xs, ys, s=46, color=MODEL_COLORS[m], edgecolor=SURFACE, linewidth=1.2, zorder=3,
                   label=MODEL_NAMES[m], marker="D" if m == "uniform_ascii" else "o")
    ax.set_yticks(range(len(classes)), classes)
    ax.set_xlabel("mean cost (bits per character) - lower is cheaper", color=INK2)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5))
    title(ax, "Which characters are expensive?", "all 6 kinds of held-out text pooled; each dot = one model")
    save(fig, path)


# ---- figure 2: distribution of per-character cost ---------------------------------------------

def distribution_stats(values: list[float]) -> dict[str, float]:
    v = np.array(values)
    return {"chars": len(v), "mean": v.mean(), "median": float(np.median(v)), "p95": float(np.percentile(v, 95)),
            "free_share": float((v < FREE).mean()), "over_raw_share": float((v > RAW).mean()),
            "bits_in_top10pct": float(np.sort(v)[-max(1, len(v) // 10):].sum() / v.sum())}


def plot_distributions(costs, path) -> dict:
    fig, (left, right) = new_figure(10, 4.2, ncols=2, sharey=True)
    stats = {}
    for ax, mode in ((left, "own"), (right, "web")):
        style(ax)
        ax.set_xscale("log")
        models = list(OWN_TEXT) if mode == "own" else ASCII_MODELS + ["uniform_ascii"]
        for m in models:
            label = OWN_TEXT[m] if mode == "own" else "Web (C4)"
            values = sorted(cost(p) for _, p, _ in flat(costs[m][label]))
            if not values:
                continue
            stats[(m, label)] = distribution_stats(values)
            y = np.arange(1, len(values) + 1) / len(values)
            ax.plot(np.clip(values, 1e-3, None), y, color=MODEL_COLORS[m], linewidth=2,
                    linestyle="--" if m == "uniform_ascii" else "-", label=MODEL_NAMES[m])
        for x, text in ((FREE, "0.1 bit = 'free'"), (RAW, "8 bits = raw text")):
            ax.axvline(x, color=MUTED, linewidth=1, linestyle=":")
            ax.text(x, 1.02, text, color=MUTED, fontsize=8, ha="center", va="bottom",
                    transform=ax.get_xaxis_transform())  # just above the plot, clear of the curves
        ax.set_xlim(1e-3, 25)
        ax.set_xlabel("cost of one character (bits, log scale)", color=INK2)
        ax.legend(frameon=False, labelcolor=INK2, fontsize=8, loc="upper left")
    left.set_ylabel("share of characters costing at most x", color=INK2)
    left.set_title("Each model on its own kind of text", loc="left", color=INK, fontsize=11, pad=18)
    right.set_title("Every ASCII model on the same web text", loc="left", color=INK, fontsize=11, pad=18)
    save(fig, path)
    return stats


# ---- figure 3: where models disagree ----------------------------------------------------------

BIN_EDGES = [0.25, 0.5, 1, 2, 4, 7]  # bits; RAMP[i] = cost below BIN_EDGES[i], RAMP[-1] = 7+ bits


def pick_window(snippets: list[str], width: int = 72) -> tuple[int, int]:
    """A window of a Wikipedia snippet with both digits and capitals (names), starting at a word."""
    for i, s in enumerate(snippets):
        for start in [0] + [j + 1 for j, c in enumerate(s) if c == " "]:
            window = s[start: start + width]
            if len(window) == width and sum(c.isdigit() for c in window) >= 3 and sum(c.isupper() for c in window) >= 3:
                return i, start
    return 0, 0


def plot_disagreement(texts, costs, path, width: int = 72) -> str:
    label = "Wikipedia"
    i, start = pick_window(texts[label], width)
    rows = ["wiki_small", "web_small", "stories_small", "python_small", "uniform_ascii"]
    fig, ax = new_figure(13, 3.4)
    ax.set_facecolor(SURFACE)
    for r, m in enumerate(rows):
        chars = costs[m][label][i][start: start + width]
        for j, (ch, p, _) in enumerate(chars):
            bits = cost(p)
            level = next((k for k, edge in enumerate(BIN_EDGES) if bits < edge), len(BIN_EDGES))
            ax.add_patch(Rectangle((j, r), 0.94, 0.9, facecolor=RAMP[level]))
            ax.text(j + 0.47, r + 0.47, "␣" if ch == " " else ch, ha="center", va="center", fontsize=8,
                    family="monospace", color="#ffffff" if level >= 3 else INK)
        total = sum(cost(p) for _, p, _ in chars)
        ax.text(width + 0.6, r + 0.47, f"{total / len(chars):.2f} bits/char", va="center", fontsize=8, color=INK2)
    ax.set_xlim(0, width + 9)
    ax.set_ylim(len(rows), -0.1)
    ax.set_yticks([r + 0.47 for r in range(len(rows))], [MODEL_NAMES[m] for m in rows], color=INK2, fontsize=9)
    ax.set_xticks([])
    for side in ax.spines.values():
        side.set_visible(False)
    ax.tick_params(length=0)
    legend = "  ".join(f"<{e}" for e in BIN_EDGES) + "  7+ bits"
    title(ax, "Where the models are surprised: one Wikipedia sentence, each character tinted by its cost",
          f"lighter = cheaper; bins: {legend}")
    save(fig, path)
    return texts[label][i][start: start + width]


# ---- figure 4: overconfidence ---------------------------------------------------------------

def plot_overconfidence(texts, costs, path) -> dict:
    label = "Python code"
    stories = [cost(p) for _, p, _ in flat(costs["stories_small"][label])]
    uniform_bits = cost(flat(costs["uniform_ascii"][label])[0][1])
    fig, ax = new_figure(8, 4)
    style(ax, "y")
    bins = np.arange(0, 22, 0.5)
    ax.hist(stories, bins=bins, color=MODEL_COLORS["stories_small"], edgecolor=SURFACE, linewidth=0.8,
            label="TinyStories-GPT")
    ax.axvline(uniform_bits, color=INK2, linewidth=1.5, linestyle="--")
    ax.text(uniform_bits + 0.3, ax.get_ylim()[1] * 0.4,
            f"Uniform ASCII pays\n{uniform_bits:.2f} bits for every char", color=INK2, fontsize=8)
    ax.set_yscale("log")
    ax.set_xlabel("cost of one character (bits)", color=INK2)
    ax.set_ylabel("characters (log scale)", color=INK2)
    floor = 16  # precision_bits: the rarest a character can be is 1 count in 2^16, so 16 bits is the most it can cost
    ax.annotate("16 bits: the coder's cap\n(1 count in 65,536)", xy=(floor + 0.25, ax.get_ylim()[1] * 0.5),
                xytext=(floor + 1.2, ax.get_ylim()[1] * 0.12), color=INK2, fontsize=8,
                arrowprops=dict(arrowstyle="-", color=MUTED, linewidth=0.8))
    title(ax, "Why TinyStories-GPT does worse than no model on Python code",
          "half its characters cost more than uniform; 'impossible' ones hit the coder's 16-bit cap")

    v = np.array(stories)
    over = v > uniform_bits
    # the single most expensive character, with its context
    worst, where = -1.0, ("", "")
    for t_idx, text in enumerate(costs["stories_small"][label]):
        for j, (ch, p, _) in enumerate(text or []):
            if cost(p) > worst:
                worst, where = cost(p), (texts[label][t_idx][max(0, j - 30): j], ch)
    save(fig, path)
    return {"uniform_bits": uniform_bits, "share_over_uniform": float(over.mean()),
            "bits_share_over_uniform": float(v[over].sum() / v.sum()), "mean": float(v.mean()),
            "worst_bits": worst, "worst_context": where[0], "worst_char": where[1]}


# ---- agreement between models ---------------------------------------------------------------

def rank(a: np.ndarray) -> np.ndarray:
    r = np.empty(len(a))
    r[np.argsort(a)] = np.arange(len(a))
    return r


def agreement(costs) -> dict[tuple[str, str], float]:
    """Spearman correlation of per-character cost between ASCII models over all shared text."""
    vectors = {m: np.array([cost(p) for label in costs[m] for _, p, _ in flat(costs[m][label])]) for m in ASCII_MODELS}
    out = {}
    for a in ASCII_MODELS:
        for b in ASCII_MODELS:
            out[(a, b)] = float(np.corrcoef(rank(vectors[a]), rank(vectors[b]))[0, 1])
    return out


# ---- main -------------------------------------------------------------------------------------

def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    texts, costs = load()

    # accuracy check: ideal bits (sum of -log2 p) vs real payload (sum of bits_added) per message
    gaps = [sum(b for *_, b in t) - sum(cost(p) for _, p, _ in t)
            for m in ALL_MODELS for label in costs[m] for t in costs[m][label] if t]

    classes = by_class(costs)
    plot_by_class(classes, RESULTS / "cost_by_char_class.png")
    dist = plot_distributions(costs, RESULTS / "surprise_distribution.png")
    sentence = plot_disagreement(texts, costs, RESULTS / "where_models_disagree.png")
    over = plot_overconfidence(texts, costs, RESULTS / "overconfidence.png")
    agree = agreement(costs)

    with open(RESULTS / "stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "text", "chars", "mean_bits", "median_bits", "p95_bits", "free_share", "over_8_bits_share",
                    "bits_in_costliest_10pct"])
        for (m, label), s in dist.items():
            w.writerow([MODEL_NAMES[m], label, s["chars"], f"{s['mean']:.3f}", f"{s['median']:.3f}", f"{s['p95']:.3f}",
                        f"{s['free_share']:.3f}", f"{s['over_raw_share']:.4f}", f"{s['bits_in_top10pct']:.3f}"])

    md = ["# Study 03 - stats (generated)", "",
          f"Accuracy check: real payload minus ideal bits per message: mean {np.mean(gaps):+.2f}, "
          f"min {min(gaps):+.2f}, max {max(gaps):+.2f} bits over {len(gaps)} messages.", "",
          "## Cost by character class (bits/char, all 6 kinds of text pooled)", "",
          "| class | " + " | ".join(MODEL_NAMES[m] for m in classes) + " |", "|---|" + "---:|" * len(classes)]
    for k in CHAR_CLASSES:
        md.append(f"| {k} | " + " | ".join(f"{classes[m].get(k, float('nan')):.2f}" for m in classes) + " |")
    md += ["", "## Distribution of per-character cost", "",
           "| model | text | mean | median | p95 | free (<0.1 bit) | >8 bits | bits in costliest 10% of chars |",
           "|---|---|---:|---:|---:|---:|---:|---:|"]
    for (m, label), s in dist.items():
        md.append(f"| {MODEL_NAMES[m]} | {label} | {s['mean']:.2f} | {s['median']:.2f} | {s['p95']:.2f} | "
                  f"{s['free_share']:.0%} | {s['over_raw_share']:.1%} | {s['bits_in_top10pct']:.0%} |")
    md += ["", f"## Overconfidence: TinyStories-GPT on Python code", "",
           f"- mean {over['mean']:.2f} bits/char vs uniform {over['uniform_bits']:.2f}",
           f"- {over['share_over_uniform']:.1%} of characters cost more than uniform; they carry "
           f"{over['bits_share_over_uniform']:.0%} of all bits",
           f"- worst: {over['worst_bits']:.1f} bits for {over['worst_char']!r} after {over['worst_context']!r}", "",
           "## Agreement (Spearman correlation of per-character cost, all shared text)", "",
           "| | " + " | ".join(MODEL_NAMES[m] for m in ASCII_MODELS) + " |", "|---|" + "---:|" * len(ASCII_MODELS)]
    for a in ASCII_MODELS:
        md.append(f"| {MODEL_NAMES[a]} | " + " | ".join(f"{agree[(a, b)]:.2f}" for b in ASCII_MODELS) + " |")
    md += ["", f"Sentence in where_models_disagree.png: {sentence!r}"]
    (RESULTS / "stats.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
