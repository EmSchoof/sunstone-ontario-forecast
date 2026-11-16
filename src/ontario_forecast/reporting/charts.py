"""Final chart styling (matplotlib; analysis/reporting only, never imported by the model).

Encoding: one measure per chart -> one hue (blue). Actuals solid, central forecast
dashed, P10-P90 band as a 10% wash with thin edge lines. Text is ink-colored, never
the series color. The three outcomes are direct-labeled at the right edge.
"""

from __future__ import annotations

import textwrap
from collections.abc import Callable

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Patch, Rectangle
from matplotlib.ticker import FuncFormatter, MaxNLocator

from ontario_forecast.modeling.scenarios import Fan

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
        "svg.hashsalt": "ontario-forecast",  # fixed element IDs -> reproducible SVGs
    }
)


def usd(v: float) -> str:
    """'$1.3M', '$85K', '−$0.2M'. The $ is escaped: matplotlib reads text between two
    unescaped $ signs as a math formula (it rendered '−0.2*M*(' on the pathway page)."""
    sign = "−" if v < 0 else ""
    a = abs(v)
    body = f"{a / 1e6:,.1f}M" if a >= 1e6 else f"{a / 1e3:,.0f}K"
    return f"{sign}\\${body}"


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
    fig, ax = _new_figure()

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

    _style_axes(ax, fmt, x_label)
    ax.set_xlim(hist_x[0] - 0.5, xf[-1] + 0.4)
    _forecast_divider(ax, hist_x[-1])

    names = [
        f"Upside (P{int(hi_q * 100)})",
        f"Central (P{int(mid_q * 100)})",
        f"Downside (P{int(lo_q * 100)})",
    ]
    _end_labels(ax, xf[-1], [hi[-1], mid[-1], lo[-1]], names, fmt)
    _frame(fig, title, subtitle, source, legend_ax=ax, ncol=4)
    return fig


# ---------------------------------------------------------------------------
# Shared chart scaffolding (every chart below uses these)
# ---------------------------------------------------------------------------
# Categorical slots 1-4 (validated order), one per recommendation; never cycled.
REC_COLORS = {"R1": "#2a78d6", "R2": "#eb6834", "R3": "#1baf7a", "R4": "#eda100", "SYN": "#e87ba4"}
BASELINE = "#8a8984"  # neutral gray for the status quo
DIVERGE_LOW, DIVERGE_HIGH = "#e34948", "#2a78d6"  # red <-> blue poles


def _new_figure(right: float = 0.80):
    """Top and bottom margins are set later by _frame, once the text heights are known."""
    fig, ax = plt.subplots(figsize=(10, 6.2))
    fig.subplots_adjust(left=0.08, right=right)
    return fig, ax


def _style_axes(
    ax, fmt: Callable[[float], str], x_label: Callable[[float], str] | None = None, value_axis: str = "y"
) -> None:
    """Recessive hairline grid on the value axis, no box, formatted ticks."""
    getattr(ax, f"{value_axis}axis").grid(True, color=GRID, lw=1)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    getattr(ax, f"{value_axis}axis").set_major_formatter(FuncFormatter(lambda v, _: fmt(v)))
    if x_label is not None:
        ax.xaxis.set_major_locator(MaxNLocator(integer=True, nbins=12))
        ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _: x_label(v)))


def _forecast_divider(ax, x: float, text: str = "Forecast →") -> None:
    ax.axvline(x, color=GRID, lw=1, zorder=0)
    ax.text(x + 0.15, ax.get_ylim()[1], text, color=INK_2, fontsize=9, va="top")


def _end_labels(ax, x: float, values: list[float], names: list[str], fmt) -> None:
    """Direct labels at the right edge, spread so they never collide.

    Labels are two lines tall, so they're kept >= 11% of the axis apart. If spreading pushes
    the lowest label below the axis, the axis is extended so it never meets the tick labels.
    """
    ymin, ymax = ax.get_ylim()
    gap = 0.11 * (ymax - ymin)
    ys = _spread(values, gap=gap)
    if min(ys) - gap / 2 < ymin:
        ax.set_ylim(min(ys) - gap / 2, ymax)
    for name, v, y in zip(names, values, ys, strict=True):
        ax.annotate(
            f"{name}\n{fmt(v)}",
            xy=(x, v),
            xytext=(x + 0.6, y),
            textcoords="data",
            va="center",
            ha="left",
            fontsize=9.5,
            color=INK,
            annotation_clip=False,
            arrowprops=dict(arrowstyle="-", color=GRID, lw=1, shrinkA=0, shrinkB=4),
        )


def _wrap(text: str, width: int) -> str:
    """Wrap each paragraph to `width` characters (explicit newlines are kept)."""
    return "\n".join(textwrap.fill(p, width) if p else "" for p in text.split("\n"))


def _frame(
    fig,
    title: str,
    subtitle: str,
    source: str,
    *,
    legend_ax=None,
    legend_handles=None,
    ncol: int = 3,
    adjust: bool = True,
) -> tuple[float, float]:
    """Title, subtitle, legend and footnote, with the plot area sized so nothing overlaps.

    Text is wrapped to the figure width up front (not left to matplotlib), so the number
    of lines is known and the axes are placed below the subtitle and above the legend
    and footnote. Returns (top, bottom) of the free area in figure fractions.
    """
    w, h = fig.get_size_inches()
    pt = 1 / (72 * h)  # one typographic point as a fraction of the figure height
    left = 0.08
    sub, src = _wrap(subtitle, int(w * 10.5)), _wrap(source, int(w * 15))
    n_sub, n_src = sub.count("\n") + 1, src.count("\n") + 1

    title_y = 1 - 24 * pt
    fig.text(left, title_y, title, fontsize=15, fontweight="bold", color=INK, ha="left", va="top")
    sub_y = title_y - 26 * pt
    fig.text(left, sub_y, sub, fontsize=10, color=INK_2, ha="left", va="top", linespacing=1.35)
    src_y = 10 * pt
    fig.text(left, src_y, src, fontsize=7.5, color=INK_2, ha="left", va="bottom", linespacing=1.3)
    src_top = src_y + n_src * 10 * pt

    handles = legend_handles
    labels = [hd.get_label() for hd in handles] if handles else None
    if handles is None and legend_ax is not None:
        handles, labels = legend_ax.get_legend_handles_labels()
    rows = 0
    if handles:
        rows = -(-len(handles) // ncol)
        fig.legend(
            handles,
            labels,
            loc="lower left",
            bbox_to_anchor=(left, src_top + 6 * pt),
            ncol=ncol,
            frameon=False,
            fontsize=8.5,
            labelcolor=INK_2,
            borderaxespad=0,
        )

    top = sub_y - n_sub * 13.5 * pt - 26 * pt  # clearance for in-plot labels and panel titles
    bottom = src_top + 6 * pt + rows * 16 * pt + 36 * pt  # legend rows + x tick labels
    if adjust:
        fig.subplots_adjust(top=top, bottom=bottom)
    return top, bottom


# ---------------------------------------------------------------------------
# Impact-model charts
# ---------------------------------------------------------------------------
def compare_fan_chart(
    years,
    base: np.ndarray,
    program: np.ndarray,
    hist_x,
    hist_y,
    *,
    title: str,
    subtitle: str,
    source: str,
    fmt,
    x_label,
    q=(0.10, 0.50, 0.90),
    program_label: str = "With recommendations",
):
    """Status quo (gray band) vs with-program (blue band), each P10-P90 with a median line."""
    fig, ax = _new_figure()
    xf = np.concatenate([[hist_x[-1]], years])
    pts = {}
    for name, samples, color in (("Status quo", base, BASELINE), (program_label, program, SERIES)):
        lo, mid, hi = (np.concatenate([[hist_y[-1]], v]) for v in np.quantile(samples, q, axis=0))
        ax.fill_between(xf, lo, hi, color=color, alpha=0.10, linewidth=0)
        ax.plot(xf, mid, color=color, lw=2, ls=(0, (4, 3)), label=f"{name} (median; band = P10-P90)")
        pts[name] = mid[-1]
    ax.plot(hist_x, hist_y, color=INK_2, lw=2, solid_capstyle="round", label="Actual")
    _style_axes(ax, fmt, x_label)
    ax.set_xlim(hist_x[0] - 0.5, xf[-1] + 0.4)
    _forecast_divider(ax, hist_x[-1])
    _end_labels(ax, xf[-1], list(pts.values()), list(pts), fmt)
    _frame(fig, title, subtitle, source, legend_ax=ax, ncol=3)
    return fig


def recommendation_lines_chart(
    years,
    medians: dict[str, np.ndarray],
    names: dict[str, str],
    total: np.ndarray,
    *,
    title: str,
    subtitle: str,
    source: str,
    fmt,
    x_label,
    q=(0.10, 0.50, 0.90),
):
    """Annual net impact per recommendation (median lines) + total P10-P90 band.
    Full names in a legend below the plot; short codes as direct labels at the right edge."""
    fig, ax = _new_figure(right=0.86)
    lo, mid, hi = np.quantile(total, q, axis=0)
    ax.fill_between(years, lo, hi, color=INK_2, alpha=0.08, linewidth=0, label="All recommendations, P10-P90")
    ax.plot(years, mid, color=INK, lw=2, label="All recommendations (median)")
    for rec, m in medians.items():
        ax.plot(years, m, color=REC_COLORS[rec], lw=2, solid_capstyle="round", label=names[rec])
    ax.axhline(0, color=INK_2, lw=1)
    _style_axes(ax, fmt, x_label)
    ax.set_xlim(years[0] - 0.5, years[-1] + 0.4)
    short = {r: names[r].split(" ")[0] for r in medians}  # "R1", "R2", ..., "R1→R4"
    _end_labels(
        ax,
        years[-1],
        [m[-1] for m in medians.values()] + [mid[-1]],
        [short[r] for r in medians] + ["All"],
        fmt,
    )
    _frame(fig, title, subtitle, source, legend_ax=ax, ncol=3)
    return fig


def window_bars_chart(
    rows: list[dict],
    windows: list[str],
    names: dict[str, str],
    *,
    title: str,
    subtitle: str,
    source: str,
    fmt,
    ref_x: float = 0.0,
    ref_label: str | None = None,
):
    """Small multiples (one panel per time window): median per group with P10-P90 whiskers.
    rows: {rec, window, p10, p50, p90}. ref_x draws the reference line (0 for net dollars,
    1 for benefit-cost ratios)."""
    fig, axes = plt.subplots(1, len(windows), figsize=(10, 6.2), sharex=True)
    fig.subplots_adjust(left=0.31, right=0.95, wspace=0.22)
    recs = list(names)
    for ax, w in zip(np.atleast_1d(axes), windows, strict=True):
        sub = {r["rec"]: r for r in rows if r["window"] == w}
        y = np.arange(len(recs))[::-1]
        for yi, rec in zip(y, recs, strict=True):
            r = sub[rec]
            ax.barh(yi, r["p50"], height=0.45, color=REC_COLORS.get(rec, INK_2), edgecolor=SURFACE, lw=2)
            ax.plot([r["p10"], r["p90"]], [yi, yi], color=INK, lw=1.25, solid_capstyle="round")
            # median label just past the right end of the bar/whisker, never on top of it
            ax.annotate(
                fmt(r["p50"]),
                xy=(max(r["p90"], r["p50"], ref_x), yi),
                xytext=(5, 0),
                textcoords="offset points",
                va="center",
                ha="left",
                fontsize=8.5,
                color=INK,
            )
        ax.axvline(ref_x, color=INK_2, lw=1)
        if ref_label:
            ax.annotate(
                ref_label,
                xy=(ref_x, 1.0),
                xycoords=("data", "axes fraction"),
                xytext=(4, -2),
                textcoords="offset points",
                va="top",
                ha="left",
                fontsize=8,
                color=INK_2,
            )
        ax.set_yticks(y, [names[r] for r in recs] if ax is np.atleast_1d(axes)[0] else [""] * len(recs))
        ax.set_title(w, fontsize=10.5, color=INK, loc="left", pad=10)
        _style_axes(ax, fmt, value_axis="x")
    # Room on the right for the value labels (shared x, so once is enough), and fewer ticks so
    # tick labels never touch at this width.
    first = np.atleast_1d(axes)[0]
    x0, x1 = first.get_xlim()
    first.set_xlim(x0 - 0.04 * (x1 - x0), x1 + 0.28 * (x1 - x0))
    for ax in np.atleast_1d(axes):
        ax.xaxis.set_major_locator(MaxNLocator(nbins=4 if len(windows) > 1 else 7))
    _frame(fig, title, subtitle, source)
    return fig


def pathway_chart(rows: list[dict], headers: tuple[str, ...], *, title: str, subtitle: str, source: str):
    """One-page logic model: recommendation | how it works | KPI | short-term | long-term.

    rows: {rec, name, chain, kpi, short, long}. Color bar = recommendation identity
    (same slots as every other impact chart); all text in ink.
    """
    fig = plt.figure(figsize=(12, 7.2))
    free_top, free_bottom = _frame(fig, title, subtitle, source, adjust=False)
    header_h = 34 / (72 * 7.2)  # two-line column headers sit above the table
    ax = fig.add_axes(
        [0.04, free_bottom - 20 / (72 * 7.2), 0.93, free_top - header_h - free_bottom + 20 / (72 * 7.2)]
    )
    ax.axis("off")
    xs, widths = (0.0, 0.19, 0.54, 0.75, 0.875), (24, 50, 28, 16, 16)
    for h, x in zip(headers, xs, strict=True):
        ax.text(x, 1.03, h, fontsize=9.5, fontweight="bold", color=INK, va="bottom", transform=ax.transAxes)
    step = 1.0 / len(rows)
    for i, r in enumerate(rows):
        top = 1.0 - i * step
        ax.plot([0, 1], [top, top], color=GRID, lw=1, transform=ax.transAxes)
        ax.add_patch(
            Rectangle(
                (-0.015, top - step + 0.02),
                0.007,
                step - 0.04,
                color=REC_COLORS.get(r["rec"], INK_2),
                transform=ax.transAxes,
                clip_on=False,
            )
        )
        for key, x, w in zip(("name", "chain", "kpi", "short", "long"), xs, widths, strict=True):
            ax.text(
                x,
                top - 0.02,
                textwrap.fill(str(r[key]), w),
                fontsize=8.6,
                va="top",
                color=INK if key in ("name", "short", "long") else INK_2,
                fontweight="bold" if key == "name" else "normal",
                transform=ax.transAxes,
            )
    return fig


def tornado_chart(
    rows: list[tuple[str, float, float, float]],
    labels: dict[str, str],
    *,
    title: str,
    subtitle: str,
    source: str,
    fmt,
    top: int = 12,
):
    """One-at-a-time sensitivity: bars from the all-mode result to the low/high result.

    Input labels are never truncated: long ones wrap onto extra lines, and the figure grows
    by ~0.5 in per row so wrapped labels never touch the row above or below.
    """
    rows = rows[:top]
    label_width = 34  # characters per line in the left label column
    wrapped = [textwrap.fill(labels.get(k, k), label_width) for k, *_ in rows]
    max_lines = max((w.count("\n") + 1 for w in wrapped), default=1)
    fig, ax = plt.subplots(figsize=(10, 3.2 + len(rows) * (0.22 + 0.14 * max_lines)))
    fig.subplots_adjust(left=0.33, right=0.95)
    base = rows[0][3] if rows else 0.0
    y = np.arange(len(rows))[::-1]
    for yi, (_, lo, hi, _base) in zip(y, rows, strict=True):
        ax.barh(yi, lo - base, left=base, height=0.55, color=DIVERGE_LOW, edgecolor=SURFACE, lw=2)
        ax.barh(yi, hi - base, left=base, height=0.55, color=DIVERGE_HIGH, edgecolor=SURFACE, lw=2)
    ax.axvline(base, color=INK, lw=1)
    ax.set_yticks(y, wrapped, fontsize=8.5, linespacing=1.15)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    _style_axes(ax, fmt, value_axis="x")
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    _frame(
        fig,
        title,
        subtitle,
        source,
        ncol=2,
        legend_handles=[
            Patch(color=DIVERGE_LOW, label="input at its low value"),
            Patch(color=DIVERGE_HIGH, label="input at its high value"),
        ],
    )
    return fig
