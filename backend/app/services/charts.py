"""Matplotlib charts for the PDF report (and the /reports/charts/*.png endpoints).

The mobile app should draw its own interactive charts from the /trends JSON; these
static PNGs are for print/PDF and quick previews.

Colors follow a validated categorical order (CVD-safe for adjacent series) and a
single-hue blue ramp for magnitude. Print is light-mode only.
"""

from __future__ import annotations

import io
from datetime import timedelta

import matplotlib
import numpy as np

matplotlib.use("Agg")  # headless; must precede pyplot import
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402

from .summary import SummaryReport  # noqa: E402
from .trends import date_range  # noqa: E402

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
SEQ_BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
NO_DATA = "#f1f0ec"

_SEVERITY_CMAP = LinearSegmentedColormap.from_list("severity", SEQ_BLUE).with_extremes(bad=NO_DATA)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9,
    "axes.edgecolor": GRID,
    "axes.labelcolor": TEXT_SECONDARY,
    "axes.titlecolor": TEXT_PRIMARY,
    "axes.titlesize": 11,
    "axes.titleweight": "bold",
    "axes.titlelocation": "left",
    "xtick.color": TEXT_SECONDARY,
    "ytick.color": TEXT_SECONDARY,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": SURFACE,
    "axes.facecolor": SURFACE,
    "legend.frameon": False,
})


def _to_png(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _date_axis(ax, span_days: int) -> None:
    if span_days <= 14:
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
    elif span_days <= 62:
        ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.MO))
    else:
        ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))


def symptom_trend_chart(report: SummaryReport, max_series: int = 5) -> bytes | None:
    """7-day rolling average for the most severe symptoms. One axis, 0-10."""
    series = [s for s in report.symptoms.symptoms if s.series][:max_series]
    if not series:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    for i, s in enumerate(series):
        xs = [p.date for p in s.series]
        ax.plot(xs, [p.value for p in s.series], "o", color=SERIES[i], alpha=0.25, markersize=3)
        ax.plot(xs, [p.rolling_avg_7d for p in s.series], "-", color=SERIES[i], linewidth=2, label=s.label)
    ax.set_ylim(0, 10.3)
    ax.set_xlim(report.start, report.end + timedelta(days=1))
    ax.set_ylabel("Severity (0-10)")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    _date_axis(ax, report.days_in_period)
    ax.set_title("Symptom severity - 7-day rolling average")
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0), labelcolor=TEXT_PRIMARY)
    return _to_png(fig)


def symptom_heatmap(report: SummaryReport, max_rows: int = 12) -> bytes | None:
    """Day-by-day severity grid; shows clustering and gaps that averages hide."""
    rows = [s for s in report.symptoms.symptoms if s.series][:max_rows]
    if not rows:
        return None
    days = date_range(report.start, report.end)
    idx = {d: i for i, d in enumerate(days)}


    grid = np.full((len(rows), len(days)), np.nan)
    for r, s in enumerate(rows):
        for p in s.series:
            grid[r, idx[p.date]] = p.value
    masked = np.ma.masked_invalid(grid)

    fig, ax = plt.subplots(figsize=(7.2, 0.32 * len(rows) + 1.2))
    im = ax.imshow(masked, aspect="auto", cmap=_SEVERITY_CMAP, vmin=0, vmax=10, interpolation="nearest")
    ax.set_yticks(range(len(rows)), [s.label for s in rows])
    step = max(1, len(days) // 8)
    ticks = list(range(0, len(days), step))
    ax.set_xticks(ticks, [days[i].strftime("%b %d") for i in ticks])
    # 2px-ish surface gap between cells
    ax.set_xticks([x - 0.5 for x in range(1, len(days))], minor=True)
    ax.set_yticks([y - 0.5 for y in range(1, len(rows))], minor=True)
    ax.grid(which="minor", color=SURFACE, linewidth=1.2)
    ax.tick_params(which="minor", length=0)
    for spine in ax.spines.values():
        spine.set_visible(False)
    cbar = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Severity", color=TEXT_SECONDARY)
    cbar.outline.set_visible(False)
    ax.set_title("Daily symptom log (gray = not logged)")
    return _to_png(fig)


def adherence_chart(report: SummaryReport, target_pct: float = 90.0) -> bytes | None:
    daily = report.adherence.daily
    if not daily:
        return None
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    ax.bar([d.date for d in daily], [d.adherence_pct for d in daily], width=0.8,
           color=SERIES[0], edgecolor=SURFACE, linewidth=1)
    ax.axhline(target_pct, color=TEXT_SECONDARY, linestyle="--", linewidth=1)
    ax.text(report.end + timedelta(days=1), target_pct, f" {target_pct:g}%", va="center",
            color=TEXT_SECONDARY, fontsize=8)
    ax.set_ylim(0, 105)
    ax.set_xlim(report.start - timedelta(days=1), report.end + timedelta(days=1))
    ax.set_ylabel("% of scheduled doses")
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    _date_axis(ax, report.days_in_period)
    title = "Daily medication adherence"
    if report.adherence.overall_pct is not None:
        title += f" - {report.adherence.overall_pct:g}% overall"
    ax.set_title(title)
    return _to_png(fig)


def lab_chart(report: SummaryReport, max_tests: int = 4) -> bytes | None:
    """Small multiples, one test per panel, so each keeps its own honest scale."""
    labs = [l for l in report.labs.labs if l.series][:max_tests]
    if not labs:
        return None
    cols = 2 if len(labs) > 1 else 1
    nrows = (len(labs) + 1) // 2
    fig, axes = plt.subplots(nrows, cols, figsize=(7.2, 2.3 * nrows), squeeze=False)
    for ax in axes.flat[len(labs):]:
        ax.set_visible(False)
    for ax, lab in zip(axes.flat, labs):
        xs = [p.date for p in lab.series]
        ys = [p.value for p in lab.series]
        lo, hi = lab.series[-1].reference_low, lab.series[-1].reference_high
        if lo is not None and hi is not None:
            ax.axhspan(lo, hi, color=SEQ_BLUE[0], alpha=0.6, linewidth=0, label="Reference range")
        ax.plot(xs, ys, "-o", color=SERIES[0], linewidth=2, markersize=6,
                markeredgecolor=SURFACE, markeredgewidth=1.5)
        last = lab.series[-1]
        ax.annotate(f"{last.value:g}", (xs[-1], ys[-1]), textcoords="offset points", xytext=(6, 4),
                    color=TEXT_PRIMARY, fontsize=8)
        unit = f" ({last.unit})" if last.unit else ""
        ax.set_title(lab.label + unit, fontsize=10)
        ax.grid(axis="y", color=GRID, linewidth=0.6)
        ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=2, maxticks=4))
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %d"))
        ax.tick_params(axis="x", labelsize=7)
        ax.margins(x=0.15)
    fig.tight_layout()
    return _to_png(fig)


CHARTS = {
    "symptoms": symptom_trend_chart,
    "heatmap": symptom_heatmap,
    "adherence": adherence_chart,
    "labs": lab_chart,
}
