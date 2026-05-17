from __future__ import annotations

import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle
from matplotlib.ticker import PercentFormatter

from ...models.payloads import HistogramPayload
from ...models.render import RenderResult
from ...specs import ResolvedHistogramSpec, TableRow, TableSpec
from ...specs import histogram_payload_to_resolved_spec
from .._common import apply_resolved_layout, style_spec_limits

_BADGE_COLORS = {
    "quality_capable": ("#dcfce7", "#166534"),
    "quality_good": ("#dbeafe", "#1e3a8a"),
    "quality_marginal": ("#fef3c7", "#92400e"),
    "quality_risk": ("#fee2e2", "#991b1b"),
    "quality_unknown": ("#e5e7eb", "#374151"),
    "fit_quality_high": ("#dcfce7", "#166534"),
    "fit_quality_medium": ("#fef3c7", "#92400e"),
    "fit_quality_low": ("#fee2e2", "#991b1b"),
    "normality_normal": ("#dcfce7", "#166534"),
    "normality_not_normal": ("#fee2e2", "#991b1b"),
}


def render_histogram_matplotlib(payload: HistogramPayload) -> RenderResult:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots()
    resolved = histogram_payload_to_resolved_spec(payload)
    edges = np.asarray(payload.bin_edges, dtype=float)
    heights = np.asarray(payload.bin_values, dtype=float)
    y_mode = str(
        payload.metadata.get("histogram_y_mode")
        or payload.metadata.get("y_mode")
        or payload.metadata.get("normalization")
        or ""
    ).strip().lower()
    relative_frequency = y_mode in {"relative_percent", "frequency_percent", "percent"}

    if edges.size >= 2 and heights.size:
        widths = np.diff(edges)
        if relative_frequency:
            counts, _ = np.histogram(np.asarray(payload.values, dtype=float), bins=edges)
            total = float(np.sum(counts))
            if total > 0.0:
                heights = counts.astype(float) / total
        ax.bar(edges[:-1], heights, width=widths, align="edge", alpha=0.8, color="tab:blue")

    curve_y_scale = 1.0
    if relative_frequency and edges.size >= 2:
        widths = np.diff(edges)
        positive_widths = widths[np.isfinite(widths) & (widths > 0.0)]
        if positive_widths.size:
            curve_y_scale = float(np.median(positive_widths))
    for curve in resolved.curves:
        curve_y = np.asarray(curve.y, dtype=float) * curve_y_scale
        if curve.fill_to_baseline and curve.fill_alpha > 0.0:
            ax.fill_between(curve.x, curve_y, 0.0, color=curve.fill_color or curve.stroke, alpha=curve.fill_alpha, linewidth=0.0)
        ax.plot(
            curve.x,
            curve_y,
            color=curve.stroke,
            linewidth=curve.stroke_width,
            linestyle="--" if curve.dash else "-",
            alpha=curve.opacity,
        )

    style_spec_limits(ax, payload.spec_limits)
    if relative_frequency:
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1.0))
    axis_labels = payload.metadata.get("axis_labels") if isinstance(payload.metadata.get("axis_labels"), dict) else {}
    ax.set_ylabel(str(axis_labels.get("y") or payload.metadata.get("y_label") or ("density" if payload.density else "count")))
    ax.set_xlabel(str(axis_labels.get("x") or payload.metadata.get("x_label") or "value"))
    if payload.metadata.get("title"):
        ax.set_title(str(payload.metadata["title"]))
    apply_resolved_layout(fig, ax, resolved)
    canvas = resolved.canvas.size
    for line in resolved.annotation_lines:
        fig.add_artist(
            Line2D(
                [line.x0 / canvas.width, line.x1 / canvas.width],
                [1.0 - (line.y0 / canvas.height), 1.0 - (line.y1 / canvas.height)],
                color=line.stroke,
                linewidth=line.stroke_width,
                alpha=0.72,
                transform=fig.transFigure,
            )
        )
    _draw_resolved_table(fig, resolved)
    return RenderResult(fig=fig, ax=ax, metadata={"kind": "histogram", "warnings": payload.warnings})


def _draw_resolved_table(fig, spec: ResolvedHistogramSpec) -> None:
    table = spec.table
    if table is None:
        return

    canvas = spec.canvas.size
    if canvas.width <= 0.0 or canvas.height <= 0.0:
        return

    rect = table.rect
    table_ax = fig.add_axes(
        [
            rect.x / canvas.width,
            1.0 - ((rect.y + rect.height) / canvas.height),
            rect.width / canvas.width,
            rect.height / canvas.height,
        ]
    )
    table_ax.set_xlim(0.0, 1.0)
    table_ax.set_ylim(0.0, 1.0)
    table_ax.set_xticks([])
    table_ax.set_yticks([])
    table_ax.set_facecolor("#ffffff")
    for spine in table_ax.spines.values():
        spine.set_color("#d1d5db")
        spine.set_linewidth(1.0)

    y = 16.0
    if table.header:
        _draw_table_row(table_ax, table, y, table.header, weight="600")
        y += 16.0
        separator_y = 1.0 - ((y - 4.0) / rect.height)
        table_ax.axhline(separator_y, color="#e5e7eb", linewidth=1.0)

    for row in table.rows:
        if y > rect.height - 8.0:
            break
        if row.metadata.get("section_break_before"):
            separator_y = 1.0 - ((y - 7.0) / rect.height)
            table_ax.axhline(separator_y, color="#d1d5db", linewidth=1.0)
        _draw_table_row(table_ax, table, y, row)
        y += 18.0


def _draw_table_row(table_ax, table: TableSpec, y: float, row, *, weight: str = "normal") -> None:
    if table.rect.width <= 0.0 or table.rect.height <= 0.0:
        return
    cells = row.cells if isinstance(row, TableRow) else row
    metadata = row.metadata if isinstance(row, TableRow) else {}
    y_axis = 1.0 - (y / table.rect.height)
    label = str(cells[0].text) if len(cells) >= 1 else ""
    value = str(cells[1].text) if len(cells) >= 2 else ""
    text_color = "#111827"
    badge_palette = metadata.get("badge_palette")
    if isinstance(badge_palette, str) and badge_palette in _BADGE_COLORS:
        background, text_color = _BADGE_COLORS[badge_palette]
        row_height = min(16.0 / table.rect.height, 0.12)
        table_ax.add_patch(
            Rectangle(
                (3.0 / table.rect.width, y_axis - row_height * 0.5),
                1.0 - (6.0 / table.rect.width),
                row_height,
                transform=table_ax.transAxes,
                facecolor=background,
                edgecolor="none",
                alpha=0.94,
                zorder=0,
            )
        )
    table_ax.text(
        8.0 / table.rect.width,
        y_axis,
        label,
        ha="left",
        va="center",
        fontsize=10,
        fontweight=weight,
        color=text_color if badge_palette else "#374151",
    )
    table_ax.text(
        1.0 - (8.0 / table.rect.width),
        y_axis,
        value,
        ha="right",
        va="center",
        fontsize=10,
        fontweight=weight,
        color=text_color,
    )
