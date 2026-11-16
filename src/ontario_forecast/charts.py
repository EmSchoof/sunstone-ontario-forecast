"""Final chart styling (matplotlib; analysis/reporting only, never imported by the model).

Encoding: one measure per chart -> one hue (blue). Actuals solid, central forecast
dashed, P10-P90 band as a 10% wash with thin edge lines. Text is ink-colored, never
the series color. The three outcomes are direct-labeled at the right edge.
"""

from __future__ import annotations

from collections.abc import Callable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import FuncFormatter, MaxNLocator

from ontario_forecast.scenarios import Fan

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e6e5e1"
SERIES = "#2a78d6"  # categorical slot 1 / sequential 450
SERIES_EDGE = "#6da7ec"  # sequential 300: band edges

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.size": 10,
        "axes.edgecolor": GRID,
        "axes.labelcolor": INK_2,
        "xtick.color": INK_2,
        "ytick.color": INK_2,
        "figure.facecolor": SURFACE,
        "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE,
        "svg.fonttype": "none",
    }
)


def usd_m(v: float) -> str:
    return f"${v / 1e6:,.1f}M"


def pct(v: float) -> str:
    return f"{v:.1%}"


def _spread(ys: list[float], gap: float) -> list[float]:
    """Nudge label y-positions apart (top to bottom) so they never overlap."""
    order = np.argsort(ys)[::-1]
    out = np.array(ys, float)
    for i in range(1, len(order)):
        above, here = order[i - 1], order[i]
        out[here] = min(out[here], out[above] - gap)
    return out.tolist()


def fan_chart(
    fan: Fan,
    hist_x: np.ndarray,
    hist_y: np.ndarray,
    *,
    title: str,
    subtitle: str,
    fmt: Callable[[float], str],
    source: str,
    x_label: Callable[[float], str],
    reference: tuple[float, float, str] | None = None,
):
    lo_q, mid_q, hi_q = fan.quantiles
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.08, right=0.80, top=0.80, bottom=0.17)

    # Anchor the forecast to the last actual so the lines connect
    xf = np.concatenate([[hist_x[-1]], fan.years])
    anchor = lambda v: np.concatenate([[hist_y[-1]], v])  # noqa: E731
    lo, mid, hi = anchor(fan.q(lo_q)), anchor(fan.q(mid_q)), anchor(fan.q(hi_q))

    ax.fill_between(
        xf,
        lo,
        hi,
        color=SERIES,
        alpha=0.10,
        linewidth=0,
        label=f"{int((hi_q - lo_q) * 100)}% of simulated outcomes",
    )
    ax.plot(xf, hi, color=SERIES_EDGE, lw=1.25, solid_capstyle="round")
    ax.plot(xf, lo, color=SERIES_EDGE, lw=1.25, solid_capstyle="round")
    ax.plot(hist_x, hist_y, color=SERIES, lw=2, solid_capstyle="round", label="Actual")
    ax.plot(xf, mid, color=SERIES, lw=2, ls=(0, (4, 3)), label="Central forecast (median)")
    dot = dict(marker="o", ms=8, color=SERIES, mec=SURFACE, mew=2, zorder=5, ls="none")
    ax.plot(hist_x[-1], hist_y[-1], **dot)  # last actual
    ax.plot([xf[-1]] * 3, [lo[-1], mid[-1], hi[-1]], **dot)  # three outcomes

    if reference is not None:
        rx, ry, rlabel = reference
        ax.plot(rx, ry, "D", ms=8, color=INK_2, mec=SURFACE, mew=2, zorder=6, label=rlabel)

    # Axes: recessive hairline grid, no box
    ax.yaxis.grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: fmt(v)))
    ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=12))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: x_label(v)))
    ax.set_xlim(hist_x[0] - 0.5, xf[-1] + 0.4)

    ymin, ymax = ax.get_ylim()
    ax.axvline(hist_x[-1], color=GRID, lw=1, zorder=0)
    ax.text(hist_x[-1] + 0.15, ymax, "Forecast →", color=INK_2, fontsize=9, va="top")

    # Direct labels for the three outcomes, right of the plot
    names = [f"Upside (P{int(hi_q*100)})", f"Central (P{int(mid_q*100)})", f"Downside (P{int(lo_q*100)})"]
    vals = [hi[-1], mid[-1], lo[-1]]
    ys = _spread(vals, gap=0.09 * (ymax - ymin))
    for name, v, y in zip(names, vals, ys, strict=True):
        ax.annotate(
            f"{name}\n{fmt(v)}",
            xy=(xf[-1], v),
            xytext=(xf[-1] + 0.6, y),
            textcoords="data",
            va="center",
            ha="left",
            fontsize=9.5,
            color=INK,
            annotation_clip=False,
            arrowprops=dict(arrowstyle="-", color=GRID, lw=1, shrinkA=0, shrinkB=4),
        )

    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK_2)
    fig.text(0.08, 0.93, title, fontsize=15, fontweight="bold", color=INK, ha="left")
    fig.text(0.08, 0.875, subtitle, fontsize=10, color=INK_2, ha="left", va="top", wrap=True)
    fig.text(0.08, 0.035, source, fontsize=7.5, color=INK_2, ha="left", va="bottom", wrap=True)
    return fig
