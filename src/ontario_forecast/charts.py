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

    names = [f"Upside (P{int(hi_q*100)})", f"Central (P{int(mid_q*100)})", f"Downside (P{int(lo_q*100)})"]
    _end_labels(ax, xf[-1], [hi[-1], mid[-1], lo[-1]], names, fmt)
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK_2)
    _frame(fig, title, subtitle, source)
    return fig


# ---------------------------------------------------------------------------
# Shared chart scaffolding (every chart below uses these)
# ---------------------------------------------------------------------------
# Categorical slots 1-4 (validated order), one per recommendation; never cycled.
REC_COLORS = {"R1": "#2a78d6", "R2": "#eb6834", "R3": "#1baf7a", "R4": "#eda100", "SYN": "#e87ba4"}
BASELINE = "#8a8984"  # neutral gray for the status quo
DIVERGE_LOW, DIVERGE_HIGH = "#e34948", "#2a78d6"  # red <-> blue poles


def _new_figure(right: float = 0.80):
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.08, right=right, top=0.80, bottom=0.17)
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
    """Direct labels at the right edge, spread so they never collide."""
    ymin, ymax = ax.get_ylim()
    ys = _spread(values, gap=0.09 * (ymax - ymin))
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


def _frame(fig, title: str, subtitle: str, source: str) -> None:
    fig.text(0.08, 0.93, title, fontsize=15, fontweight="bold", color=INK, ha="left")
    fig.text(0.08, 0.875, subtitle, fontsize=10, color=INK_2, ha="left", va="top", wrap=True)
    fig.text(0.08, 0.035, source, fontsize=7.5, color=INK_2, ha="left", va="bottom", wrap=True)


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
    ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=INK_2)
    _frame(fig, title, subtitle, source)
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
    """Annual net impact per recommendation (median lines) + total P10-P90 band."""
    fig, ax = _new_figure(right=0.76)
    lo, mid, hi = np.quantile(total, q, axis=0)
    ax.fill_between(years, lo, hi, color=INK_2, alpha=0.08, linewidth=0, label="All recommendations, P10-P90")
    ax.plot(years, mid, color=INK, lw=2, label="All recommendations (median)")
    for rec, m in medians.items():
        ax.plot(years, m, color=REC_COLORS[rec], lw=2, solid_capstyle="round", label=names[rec])
    ax.axhline(0, color=INK_2, lw=1)
    _style_axes(ax, fmt, x_label)
    ax.set_xlim(years[0] - 0.5, years[-1] + 0.4)
    _end_labels(
        ax,
        years[-1],
        [m[-1] for m in medians.values()] + [mid[-1]],
        [names[r] for r in medians] + ["All"],
        fmt,
    )
    ax.legend(loc="upper left", frameon=False, fontsize=8.5, labelcolor=INK_2)
    _frame(fig, title, subtitle, source)
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
):
    """Small multiples (one panel per time window): median cumulative net per recommendation
    with P10-P90 whiskers. rows: {rec, window, p10, p50, p90}."""
    fig, axes = plt.subplots(1, len(windows), figsize=(10, 5.6), sharex=True)
    fig.subplots_adjust(left=0.22, right=0.97, top=0.78, bottom=0.17, wspace=0.12)
    recs = list(names)
    for ax, w in zip(np.atleast_1d(axes), windows, strict=True):
        sub = {r["rec"]: r for r in rows if r["window"] == w}
        y = np.arange(len(recs))[::-1]
        for yi, rec in zip(y, recs, strict=True):
            r = sub[rec]
            ax.barh(yi, r["p50"], height=0.45, color=REC_COLORS.get(rec, INK_2), edgecolor=SURFACE, lw=2)
            ax.plot([r["p10"], r["p90"]], [yi, yi], color=INK, lw=1.25, solid_capstyle="round")
            ax.text(r["p90"], yi + 0.32, fmt(r["p50"]), fontsize=8.5, color=INK, ha="right")
        ax.axvline(0, color=INK_2, lw=1)
        ax.set_yticks(y, [names[r] for r in recs] if ax is np.atleast_1d(axes)[0] else [""] * len(recs))
        ax.set_title(w, fontsize=10.5, color=INK, loc="left")
        _style_axes(ax, fmt, value_axis="x")
    _frame(fig, title, subtitle, source)
    return fig


def pathway_chart(rows: list[dict], headers: tuple[str, ...], *, title: str, subtitle: str, source: str):
    """One-page logic model: recommendation | how it works | KPI | short-term | long-term.

    rows: {rec, name, chain, kpi, short, long}. Color bar = recommendation identity
    (same slots as every other impact chart); all text in ink.
    """
    import textwrap

    from matplotlib.patches import Rectangle

    fig = plt.figure(figsize=(12, 6.6))
    ax = fig.add_axes([0.04, 0.12, 0.93, 0.68])
    ax.axis("off")
    xs, widths = (0.0, 0.19, 0.56, 0.78, 0.89), (24, 52, 30, 14, 14)
    for h, x in zip(headers, xs, strict=True):
        ax.text(x, 1.02, h, fontsize=9.5, fontweight="bold", color=INK, va="bottom", transform=ax.transAxes)
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
    _frame(fig, title, subtitle, source)
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
    """One-at-a-time sensitivity: bars from the all-mode result to the low/high result."""
    rows = rows[:top]
    fig, ax = plt.subplots(figsize=(10, 5.6))
    fig.subplots_adjust(left=0.34, right=0.95, top=0.80, bottom=0.17)
    base = rows[0][3] if rows else 0.0
    y = np.arange(len(rows))[::-1]
    for yi, (_, lo, hi, _base) in zip(y, rows, strict=True):
        ax.barh(yi, lo - base, left=base, height=0.55, color=DIVERGE_LOW, edgecolor=SURFACE, lw=2)
        ax.barh(yi, hi - base, left=base, height=0.55, color=DIVERGE_HIGH, edgecolor=SURFACE, lw=2)
    ax.axvline(base, color=INK, lw=1)
    ax.set_yticks(y, [labels.get(k, k) for k, *_ in rows], fontsize=8.5)
    ax.barh([], [], color=DIVERGE_LOW, label="input at its low value")
    ax.barh([], [], color=DIVERGE_HIGH, label="input at its high value")
    ax.legend(loc="lower right", frameon=False, fontsize=8.5, labelcolor=INK_2)
    _style_axes(ax, fmt, value_axis="x")
    _frame(fig, title, subtitle, source)
    return fig
