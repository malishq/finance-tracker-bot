from __future__ import annotations

import io
import math
from datetime import date
from typing import List, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FuncFormatter

from .money import fmt_money
from .periods import MONTHS_SHORT

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
TAIL = "#b5b3ab"
ACCENT = SERIES[0]
MAX_SLICES = 6

plt.rcParams["font.family"] = "DejaVu Sans"


def _render(fig) -> bytes:
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", facecolor=SURFACE, dpi=160)
    plt.close(fig)
    return buffer.getvalue()


def _compact(value: float) -> str:
    sign = "−" if value < 0 else ""
    value = abs(value)
    if value >= 1_000_000:
        text = f"{value / 1_000_000:.1f}".rstrip("0").rstrip(".") + " млн"
    elif value >= 1000:
        text = f"{value / 1000:.1f}".rstrip("0").rstrip(".") + " тыс."
    else:
        text = f"{value:.0f}"
    return sign + text


def _new_figure(title: str, subtitle: str):
    fig, ax = plt.subplots(figsize=(9, 5.4), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.085, right=0.965, top=0.78, bottom=0.13)
    fig.text(0.06, 0.93, title, fontsize=16, fontweight="semibold", color=INK, ha="left", va="center")
    fig.text(0.06, 0.87, subtitle, fontsize=10.5, color=INK_SECONDARY, ha="left", va="center")
    for name in ("top", "right", "left"):
        ax.spines[name].set_visible(False)
    ax.spines["bottom"].set_color(AXIS)
    ax.spines["bottom"].set_linewidth(1)
    ax.tick_params(colors=INK_MUTED, labelsize=9, length=0, pad=6)
    ax.yaxis.grid(True, color=GRID, linewidth=0.8)
    ax.xaxis.grid(False)
    ax.set_axisbelow(True)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda value, _pos: _compact(value)))
    return fig, ax


def _date_ticks(ax, dates: Sequence[date]) -> None:
    count = len(dates)
    step = 5 if count > 14 else 1
    positions = list(range(count - 1, -1, -step))
    ax.set_xticks(positions)
    ax.set_xticklabels([f"{dates[i].day} {MONTHS_SHORT[dates[i].month - 1]}" for i in positions])
    ax.set_xlim(-0.7, count - 0.3)


def _empty(ax, text: str) -> None:
    ax.text(0.5, 0.5, text, transform=ax.transAxes, ha="center", va="center", fontsize=12, color=INK_MUTED)
    ax.set_yticks([])
    ax.set_xticks([])
    ax.spines["bottom"].set_visible(False)
    ax.yaxis.grid(False)


def pie_by_category(data: Sequence[Tuple[str, int]], title: str, subtitle: str, currency: str) -> bytes:
    rows = sorted([(name, amount) for name, amount in data if amount > 0], key=lambda item: -item[1])
    fig = plt.figure(figsize=(9, 5.4), dpi=160)
    fig.patch.set_facecolor(SURFACE)
    fig.text(0.06, 0.93, title, fontsize=16, fontweight="semibold", color=INK, ha="left", va="center")
    fig.text(0.06, 0.87, subtitle, fontsize=10.5, color=INK_SECONDARY, ha="left", va="center")
    if not rows:
        ax = fig.add_axes([0.05, 0.1, 0.9, 0.7])
        ax.axis("off")
        _empty(ax, "Расходов за этот период пока нет")
        return _render(fig)
    if len(rows) > MAX_SLICES:
        head = rows[: MAX_SLICES - 1]
        tail_total = sum(amount for _, amount in rows[MAX_SLICES - 1 :])
        rows = head + [("Остальное", tail_total)]
    total = sum(amount for _, amount in rows)
    colors = [SERIES[i] for i in range(len(rows))]
    if rows[-1][0] == "Остальное":
        colors[-1] = TAIL
    ax = fig.add_axes([0.02, 0.07, 0.5, 0.74])
    ax.set_facecolor(SURFACE)
    values = [amount / 100 for _, amount in rows]
    wedges, _texts = ax.pie(
        values,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.4, "edgecolor": SURFACE, "linewidth": 2},
    )
    ax.set_aspect("equal")
    for wedge, (name, amount), color in zip(wedges, rows, colors):
        share = amount / total
        if share < 0.08:
            continue
        angle = math.radians((wedge.theta1 + wedge.theta2) / 2)
        x, y = 0.8 * math.cos(angle), 0.8 * math.sin(angle)
        ink = INK if color == SERIES[3] else "#ffffff"
        ax.text(x, y, f"{round(share * 100)}%", ha="center", va="center", fontsize=9.5, color=ink, fontweight="semibold")
    ax.text(0, 0.1, fmt_money(total, currency), ha="center", va="center", fontsize=15, fontweight="semibold", color=INK)
    ax.text(0, -0.14, "расходы", ha="center", va="center", fontsize=10, color=INK_SECONDARY)
    legend = fig.add_axes([0.55, 0.08, 0.42, 0.72])
    legend.axis("off")
    step = 1 / max(len(rows), 1)
    for index, ((name, amount), color) in enumerate(zip(rows, colors)):
        y = 1 - step * index - step / 2
        legend.add_patch(Rectangle((0, y - 0.032), 0.045, 0.064, color=color, transform=legend.transAxes, clip_on=False))
        legend.text(0.08, y, name, ha="left", va="center", fontsize=11, color=INK, transform=legend.transAxes)
        detail = f"{fmt_money(amount, currency)} · {round(amount / total * 100)}%"
        legend.text(1.0, y, detail, ha="right", va="center", fontsize=10, color=INK_SECONDARY, transform=legend.transAxes)
    return _render(fig)


def bars_by_day(points: Sequence[Tuple[date, int]], title: str, subtitle: str, currency: str) -> bytes:
    fig, ax = _new_figure(title, subtitle)
    dates = [day for day, _ in points]
    values = [amount / 100 for _, amount in points]
    if not points or max(values) <= 0:
        _empty(ax, "Расходов за эти дни пока нет")
        return _render(fig)
    positions = list(range(len(points)))
    ax.bar(positions, values, width=0.62, color=ACCENT, zorder=3, linewidth=0)
    peak_index = max(range(len(values)), key=lambda i: values[i])
    ax.annotate(
        fmt_money(points[peak_index][1], currency),
        xy=(peak_index, values[peak_index]),
        xytext=(0, 5),
        textcoords="offset points",
        ha="center",
        va="bottom",
        fontsize=9,
        color=INK_SECONDARY,
    )
    average = sum(values) / len(values)
    ax.axhline(average, color=INK_MUTED, linewidth=1, zorder=4)
    ax.text(
        len(points) - 0.3,
        average,
        f"в среднем {fmt_money(round(average) * 100, currency)} в день",
        ha="right",
        va="bottom",
        fontsize=8.5,
        color=INK_SECONDARY,
        bbox={"facecolor": SURFACE, "edgecolor": "none", "pad": 2},
        zorder=6,
    )
    ax.set_ylim(0, max(values) * 1.22)
    _date_ticks(ax, dates)
    return _render(fig)


def balance_line(points: Sequence[Tuple[date, int]], title: str, subtitle: str, currency: str) -> bytes:
    fig, ax = _new_figure(title, subtitle)
    if not points:
        _empty(ax, "Записей пока нет")
        return _render(fig)
    dates = [day for day, _ in points]
    values = [amount / 100 for _, amount in points]
    positions = list(range(len(points)))
    low, high = min(values + [0]), max(values + [0])
    span = max(high - low, 1)
    ax.axhline(0, color=AXIS, linewidth=1, zorder=2)
    ax.fill_between(positions, values, 0, color=ACCENT, alpha=0.1, linewidth=0, zorder=3)
    ax.plot(positions, values, color=ACCENT, linewidth=2, solid_joinstyle="round", solid_capstyle="round", zorder=4)
    ax.plot(
        positions[-1],
        values[-1],
        marker="o",
        markersize=8,
        color=ACCENT,
        markeredgecolor=SURFACE,
        markeredgewidth=2,
        zorder=5,
    )
    ax.annotate(
        fmt_money(points[-1][1], currency, signed=True),
        xy=(positions[-1], values[-1]),
        xytext=(0, 10),
        textcoords="offset points",
        ha="right",
        va="bottom",
        fontsize=10,
        color=INK,
        fontweight="semibold",
    )
    ax.set_ylim(low - span * 0.15, high + span * 0.25)
    _date_ticks(ax, dates)
    return _render(fig)
