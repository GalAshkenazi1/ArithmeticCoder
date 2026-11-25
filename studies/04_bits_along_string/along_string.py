"""How does the cost per character change along a message?

30 held-out messages of 400 chars per corpus; each model on its own kind of text (plus Web-GPT, the
generalist, on every kind). Uses the real coder's per-character numbers (studies/_shared/surprisal.py):
ideal cost -log2(prob) for smooth curves, and bits_added for the real payload length.

Run (from the project root):
    uv run --group studies python studies/04_bits_along_string/along_string.py
"""
import csv
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
sys.path.insert(0, str(HERE.parent))
from _shared.style import INK2, MODEL_COLORS, MUTED, SURFACE, new_figure, save, style, title  # noqa: E402
from _shared.surprisal import CORPORA, MODEL_NAMES, OWN_TEXT, char_costs, cost, held_out_snippets  # noqa: E402

N_MESSAGES, LENGTH, CONTEXT = 30, 400, 128
CHECKPOINTS = [10, 20, 50, 100, 200, 400]


def load() -> tuple[dict, dict]:
    """texts[label] = messages; costs[model] = per-message costs on its own text."""
    texts = {label: held_out_snippets(c, k, n=N_MESSAGES, length=LENGTH) for c, k, label in CORPORA}
    costs = {m: char_costs(m, texts[label]) for m, label in OWN_TEXT.items()}
    return texts, costs


def by_position(messages: list) -> tuple[np.ndarray, np.ndarray]:
    """Mean ideal cost at each position, and the mean running real bits/char (k_i / i)."""
    n = max(len(t) for t in messages if t)
    costs = np.full((len(messages), n), np.nan)
    running = np.full((len(messages), n), np.nan)
    for r, text in enumerate(messages):
        if not text:
            continue
        costs[r, : len(text)] = [cost(p) for _, p, _ in text]
        k = np.cumsum([b for *_, b in text])
        running[r, : len(text)] = k / np.arange(1, len(text) + 1)
    # keep only positions that at least 80% of the messages reach (snippets are trimmed, so a few are shorter)
    covered = (~np.isnan(costs)).sum(axis=0) >= 0.8 * (~np.isnan(costs[:, 0])).sum()
    n_valid = int(np.argmin(covered)) if not covered.all() else n
    return np.nanmean(costs, axis=0)[:n_valid], np.nanmean(running, axis=0)[:n_valid]


def smooth(y: np.ndarray, width: int = 5) -> np.ndarray:
    """Centred moving average; the first few positions are kept raw so the sharp start stays visible."""
    out = np.convolve(y, np.ones(width) / width, mode="same")
    out[:width] = y[:width]
    out[-width:] = y[-width:]
    return out


def label_line_ends(ax, ends: dict[str, float], x: float) -> None:
    """Direct labels at the right end of each line, nudged apart so they don't overlap."""
    placed: list[float] = []
    span = ax.get_ylim()[1] - ax.get_ylim()[0]
    for m, y in sorted(ends.items(), key=lambda kv: kv[1]):
        while any(abs(y - p) < span * 0.045 for p in placed):
            y += span * 0.045
        placed.append(y)
        ax.text(x, y, " " + MODEL_NAMES[m], color=INK2, fontsize=8, va="center")


def plot_position(curves, path) -> None:
    fig, ax = new_figure(9.5, 4.6)
    style(ax)
    ax.set_xscale("log")
    for m, (mean_cost, _) in curves.items():
        y = smooth(mean_cost)
        ax.plot(np.arange(1, len(y) + 1), y, color=MODEL_COLORS[m], linewidth=1.8, label=MODEL_NAMES[m])
    ax.axvline(CONTEXT, color=MUTED, linestyle=":", linewidth=1)
    ax.text(CONTEXT * 1.04, 8.3, "128: context\nwindow full", color=MUTED, fontsize=8, va="top")
    ax.set_xticks([1, 2, 5, 10, 20, 50, 100, 200, 400], ["1", "2", "5", "10", "20", "50", "100", "200", "400"])
    ax.set_xlim(1, LENGTH)
    ax.set_ylim(0, 9)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=8, loc="upper center", ncols=3)  # empty area above the curves
    ax.set_xlabel("position in the message (characters, log scale)", color=INK2)
    ax.set_ylabel("mean cost at that position (bits)", color=INK2)
    title(ax, "Only the first character or two are expensive; after that the cost is flat",
          f"each model on its own kind of text, {N_MESSAGES} held-out messages (5-char moving average after position 5)")
    save(fig, path)


def plot_cumulative(curves, path) -> None:
    fig, ax = new_figure(9.5, 4.6)
    style(ax)
    ax.set_xscale("log")
    ends = {}
    for m, (_, running) in curves.items():
        x = np.arange(1, len(running) + 1)
        ax.plot(x, running, color=MODEL_COLORS[m], linewidth=1.8)
        ends[m] = float(running[-1])
    for c in CHECKPOINTS:
        ax.axvline(c, color="#e1e0d9", linewidth=0.8, zorder=0)
    ax.set_xticks(CHECKPOINTS, [str(c) for c in CHECKPOINTS])
    ax.set_xlim(1, LENGTH * 2.2)
    ax.set_ylim(0, min(12, ax.get_ylim()[1]))
    label_line_ends(ax, ends, LENGTH * 1.03)
    ax.set_xlabel("message length (characters, log scale)", color=INK2)
    ax.set_ylabel("real payload bits / characters so far", color=INK2)
    title(ax, "Short messages cost more per character",
          "running bits per character of the actual payload, averaged over messages")
    save(fig, path)


def plot_staircase(text: str, path) -> dict:
    """Real payload length after each character of one message, under a few models."""
    models = ["stories_small", "web_small", "wiki_small", "uniform_ascii"]
    shown = text[:64]
    fig, ax = new_figure(12, 4.4)
    style(ax)
    totals = {}
    for m in models:
        steps = char_costs(m, [text])[0][: len(shown)]
        k = np.cumsum([0] + [b for *_, b in steps])
        ax.step(np.arange(len(k)), k, where="post", color=MODEL_COLORS[m], linewidth=1.8,
                linestyle="--" if m == "uniform_ascii" else "-")
        totals[m] = (int(k[-1]), sum(1 for *_, b in steps if b == 0))
    # end labels, nudged apart where lines finish close together
    placed: list[float] = []
    for m, (bits, free) in sorted(totals.items(), key=lambda kv: kv[1][0]):
        y = float(bits)
        while any(abs(y - p) < 18 for p in placed):
            y += 18
        placed.append(y)
        ax.text(len(shown) + 0.5, y, f" {MODEL_NAMES[m]}: {bits} bits, {free} free chars", color=INK2,
                fontsize=8, va="center")
    ax.set_xticks(np.arange(len(shown)) + 0.5, ["␣" if c == " " else ("↵" if c == "\n" else c) for c in shown],
                  fontsize=7, family="monospace")
    ax.tick_params(axis="x", length=0)
    ax.set_xlim(0, len(shown) + 22)
    ax.set_ylabel("payload so far (bits)", color=INK2)
    title(ax, "The payload grows in steps: flat stretches are characters that cost 0 extra bits",
          "one TinyStories message, first 64 characters")
    save(fig, path)
    return totals


WORD_CATEGORIES = ["1st letter", "2nd letter", "3rd letter", "4th letter", "5th+ letter", "space", "newline", "punctuation/other"]


def word_position_category(text: str, i: int) -> str:
    """Where character i sits: its position inside a word (letters/digits), or what else it is."""
    c = text[i]
    if c.isalnum():
        j = i
        while j > 0 and text[j - 1].isalnum():
            j -= 1
        return WORD_CATEGORIES[min(i - j, 4)]
    return "space" if c == " " else "newline" if c == "\n" else "punctuation/other"


def by_word_position(texts, costs) -> tuple[dict, dict]:
    table, first_share = {}, {}
    for m, label in OWN_TEXT.items():
        sums, counts = {k: 0.0 for k in WORD_CATEGORIES}, {k: 0 for k in WORD_CATEGORIES}
        for text, steps in zip(texts[label], costs[m]):
            if not steps:
                continue
            for i, (_, p, _) in enumerate(steps):
                k = word_position_category(text, i)
                sums[k] += cost(p)
                counts[k] += 1
        table[m] = {k: sums[k] / counts[k] for k in WORD_CATEGORIES if counts[k]}
        total_bits, total_chars = sum(sums.values()), sum(counts.values())
        first_share[m] = (sums["1st letter"] / total_bits, counts["1st letter"] / total_chars)
    return table, first_share


def plot_word_position(table, path) -> None:
    fig, ax = new_figure(10.5, 4.4)
    style(ax, "x")
    cats = WORD_CATEGORIES[::-1]
    for offset, m in zip(np.linspace(-0.27, 0.27, len(table)), table):
        xs = [table[m].get(k, np.nan) for k in cats]
        ax.scatter(xs, [i + offset for i in range(len(cats))], s=40, color=MODEL_COLORS[m], edgecolor=SURFACE,
                   linewidth=1.2, zorder=3, label=MODEL_NAMES[m])
    ax.set_yticks(range(len(cats)), cats)
    ax.set_xlabel("mean cost (bits per character)", color=INK2)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=8, loc="center left", bbox_to_anchor=(1.01, 0.5))
    title(ax, "Inside a word, the first letter carries the information",
          "each model on its own kind of text; later letters are mostly predictable")
    save(fig, path)


def main() -> None:
    RESULTS.mkdir(exist_ok=True)
    texts, costs = load()
    curves = {m: by_position(costs[m]) for m in OWN_TEXT}
    plot_position(curves, RESULTS / "cost_by_position.png")
    plot_cumulative(curves, RESULTS / "cumulative_bpc.png")
    staircase = plot_staircase(texts["TinyStories"][3], RESULTS / "staircase_example.png")
    words, first_share = by_word_position(texts, costs)
    plot_word_position(words, RESULTS / "cost_by_word_position.png")

    # the generalist on every kind of text: start vs plateau
    general = {}
    for label in texts:
        mean_cost, running = by_position(char_costs("web_small", texts[label]))
        general[label] = (mean_cost[0], float(np.mean(mean_cost[:10])), float(np.mean(mean_cost[CONTEXT:])), running[-1])

    with open(RESULTS / "stats.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["model", "text"] + [f"bpc_at_{c}_chars" for c in CHECKPOINTS] + ["first_char_bits", "mean_first_10", "mean_after_128"])
        for m, (mean_cost, running) in curves.items():
            w.writerow([MODEL_NAMES[m], OWN_TEXT[m]] + [f"{running[min(c, len(running)) - 1]:.3f}" for c in CHECKPOINTS]
                       + [f"{mean_cost[0]:.2f}", f"{np.mean(mean_cost[:10]):.2f}", f"{np.mean(mean_cost[CONTEXT:]):.2f}"])

    md = ["# Study 04 - stats (generated)", "", "## Running real bits/char by message length (own kind of text)", "",
          "| model | text | " + " | ".join(f"{c} chars" for c in CHECKPOINTS) + " | 1st char | first 10 | after 128 |",
          "|---|---|" + "---:|" * (len(CHECKPOINTS) + 3)]
    for m, (mean_cost, running) in curves.items():
        md.append(f"| {MODEL_NAMES[m]} | {OWN_TEXT[m]} | " + " | ".join(f"{running[min(c, len(running)) - 1]:.2f}" for c in CHECKPOINTS)
                  + f" | {mean_cost[0]:.2f} | {np.mean(mean_cost[:10]):.2f} | {np.mean(mean_cost[CONTEXT:]):.2f} |")
    md += ["", "## Web-GPT on every kind of text (ideal bits)", "",
           "| text | 1st char | first 10 chars | after 128 chars | 400-char message (real bits/char) |", "|---|---:|---:|---:|---:|"]
    for label, (c0, c10, plateau, final) in general.items():
        md.append(f"| {label} | {c0:.2f} | {c10:.2f} | {plateau:.2f} | {final:.2f} |")
    md += ["", "## Cost by position inside a word (bits/char)", "",
           "| model | " + " | ".join(WORD_CATEGORIES) + " | share of bits on 1st letters | share of chars that are 1st letters |",
           "|---|" + "---:|" * (len(WORD_CATEGORIES) + 2)]
    for m, row in words.items():
        bits_share, char_share = first_share[m]
        md.append(f"| {MODEL_NAMES[m]} | " + " | ".join(f"{row.get(k, float('nan')):.2f}" for k in WORD_CATEGORIES)
                  + f" | {bits_share:.0%} | {char_share:.0%} |")
    md += ["", "## Staircase example (first 64 chars of one TinyStories message)", "",
           "| model | payload bits | characters that cost 0 extra bits |", "|---|---:|---:|"]
    for m, (bits, free) in staircase.items():
        md.append(f"| {MODEL_NAMES[m]} | {bits} | {free} of 64 |")
    (RESULTS / "stats.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
