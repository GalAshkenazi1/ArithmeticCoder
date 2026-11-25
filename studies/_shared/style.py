"""Chart style for the studies: dataviz reference palette (light mode), one fixed colour per model."""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE, INK, INK2, MUTED, GRID, AXIS = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7"

# categorical slots 1-6 in their fixed order; the uniform baseline is a neutral grey, not a series colour
MODEL_COLORS = {
    "shakespeare_char": "#2a78d6",
    "english_char": "#eb6834",
    "wiki_small": "#1baf7a",
    "stories_small": "#eda100",
    "web_small": "#e87ba4",
    "python_small": "#008300",
    "uniform_ascii": MUTED,
    # study 05 (tokenizations): slots 7-8, then slot 1 for GPT-2 (Shakespeare-GPT never appears there)
    "web_bytes": "#6250d6",
    "web_words": "#e34948",
    "gpt2": "#2a78d6",
    "wiki_bytes": "#199e70",
    "uniform_bytes": "#c3c2b7",
}

# sequential blue ramp (light -> dark) for costs: darker = more bits
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]


def new_figure(width: float, height: float, ncols: int = 1, nrows: int = 1, **kwargs):
    """A figure on the chart surface."""
    fig, axes = plt.subplots(nrows, ncols, figsize=(width, height), facecolor=SURFACE, **kwargs)
    return fig, axes


def style(ax, grid_axis: str | None = "both") -> None:
    """Recessive chrome: no top/right spines, hairline grid, muted ticks."""
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=MUTED, labelcolor=INK2)
    if grid_axis:
        ax.grid(axis=grid_axis, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def title(ax, text: str, sub: str | None = None) -> None:
    """Left-aligned title with an optional one-line subtitle."""
    ax.set_title(text + (f"\n{sub}" if sub else ""), loc="left", color=INK, fontsize=11)


def save(fig, path) -> None:
    fig.tight_layout()
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)
