from __future__ import annotations

import math

import numpy as np

from ..models.payloads import ScatterPayload
from .histogram import _finite_tuple, _format_number, _padded_range, _positive_dimension, _ticks
from .primitives import (
    AxisSpec,
    Canvas,
    HexCellSpec,
    LineSpec,
    MarkerBatchSpec,
    MarkerSpec,
    Rect,
    ResolvedScatterSpec,
    Size,
    TextSpec,
)

_MARKER_BATCH_THRESHOLD = 256


def scatter_payload_to_resolved_spec(
    payload: ScatterPayload,
    *,
    width: float = 760,
    height: float = 480,
) -> ResolvedScatterSpec:
    canvas = Canvas(size=Size(width=_positive_dimension(width), height=_positive_dimension(height)))
    plot_rect = Rect(x=72.0, y=62.0, width=max(canvas.size.width - 104.0, 48.0), height=max(canvas.size.height - 118.0, 48.0))
    point_pairs = _point_pairs(payload)
    markers = _marker_specs(payload, point_pairs) if _use_marker_specs(payload, point_pairs) else ()
    marker_batches = _marker_batch_specs(payload, point_pairs) if _use_marker_batches(payload, point_pairs) else ()
    trend_line = _trend_line(payload)
    x_min, x_max = _axis_range(tuple(point[0] for point in point_pairs), trend_line, axis="x")
    y_min, y_max = _axis_range(tuple(point[1] for point in point_pairs), trend_line, axis="y")
    hex_cells = _hex_cells(payload, point_pairs, x_min, x_max, y_min, y_max) if payload.mode == "hexbin" else ()

    axes = (
        AxisSpec(
            orientation="x",
            label=str(payload.metadata.get("x_label") or "x"),
            minimum=x_min,
            maximum=x_max,
            tick_values=_ticks(x_min, x_max),
            tick_labels=tuple(_format_number(value) for value in _ticks(x_min, x_max)),
        ),
        AxisSpec(
            orientation="y",
            label=str(payload.metadata.get("y_label") or "y"),
            minimum=y_min,
            maximum=y_max,
            tick_values=_ticks(y_min, y_max),
            tick_labels=tuple(_format_number(value) for value in _ticks(y_min, y_max)),
        ),
    )

    return ResolvedScatterSpec(
        chart_type="scatter",
        canvas=canvas,
        title=TextSpec(text="Scatter", x=36.0, y=28.0, font_size=18.0, weight="600", role="title"),
        plot_rect=plot_rect,
        axes=axes,
        markers=markers,
        marker_batches=marker_batches,
        hex_cells=hex_cells,
        trend_line=trend_line,
        metadata={
            "mode": payload.mode,
            "point_count": len(point_pairs),
            "hex_cell_count": len(hex_cells),
            "include_trend": payload.include_trend,
            "rasterized": payload.rasterized,
            "simplified_annotations": payload.simplified_annotations,
        },
    )


def _point_pairs(payload: ScatterPayload) -> tuple[tuple[float, float], ...]:
    return tuple(
        (x, y)
        for x, y in zip(_finite_tuple(payload.x), _finite_tuple(payload.y), strict=False)
        if math.isfinite(x) and math.isfinite(y)
    )


def _marker_specs(payload: ScatterPayload, points: tuple[tuple[float, float], ...]) -> tuple[MarkerSpec, ...]:
    return tuple(
        MarkerSpec(
            x=x,
            y=y,
            label=f"point {index + 1}",
            kind=payload.mode,
            fill="#2563eb",
            stroke="#1d4ed8" if payload.edgecolors != "none" else "none",
            size=payload.marker_size,
            opacity=payload.alpha,
            metadata={"index": index},
        )
        for index, (x, y) in enumerate(points)
    )


def _marker_batch_specs(payload: ScatterPayload, points: tuple[tuple[float, float], ...]) -> tuple[MarkerBatchSpec, ...]:
    if not points:
        return ()
    return (
        MarkerBatchSpec(
            x=tuple(point[0] for point in points),
            y=tuple(point[1] for point in points),
            label=f"{len(points)} points",
            kind=payload.mode,
            fill="#2563eb",
            stroke="#1d4ed8" if payload.edgecolors != "none" else "none",
            size=payload.marker_size,
            opacity=payload.alpha,
            metadata={"count": len(points)},
        ),
    )


def _use_marker_specs(payload: ScatterPayload, points: tuple[tuple[float, float], ...]) -> bool:
    return payload.mode != "hexbin" and len(points) <= _MARKER_BATCH_THRESHOLD


def _use_marker_batches(payload: ScatterPayload, points: tuple[tuple[float, float], ...]) -> bool:
    return payload.mode != "hexbin" and len(points) > _MARKER_BATCH_THRESHOLD


def _hex_cells(
    payload: ScatterPayload,
    points: tuple[tuple[float, float], ...],
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> tuple[HexCellSpec, ...]:
    if not points:
        return ()
    nx = max(int(payload.gridsize), 1)
    ny = max(int(round(nx / math.sqrt(3.0))), 1)
    x_span = max(x_max - x_min, np.finfo(float).eps)
    y_span = max(y_max - y_min, np.finfo(float).eps)
    dx = x_span / nx
    dy = y_span / ny

    counts: dict[tuple[int, int], int] = {}
    for x, y in points:
        row = min(max(int((y - y_min) / dy), 0), ny - 1)
        offset = 0.5 if row % 2 else 0.0
        col = min(max(int((x - x_min) / dx - offset), 0), nx - 1)
        counts[(row, col)] = counts.get((row, col), 0) + 1

    if not counts:
        return ()
    max_count = max(counts.values())
    cells: list[HexCellSpec] = []
    for (row, col), count in sorted(counts.items()):
        cx = x_min + (col + 0.5 + (0.5 if row % 2 else 0.0)) * dx
        cy = y_min + (row + 0.5) * dy
        rx = dx * 0.48
        ry = dy * 0.48
        intensity = count / max_count
        opacity = 0.28 + 0.52 * intensity
        cells.append(
            HexCellSpec(
                points=(
                    (cx - rx, cy),
                    (cx - rx * 0.5, cy - ry),
                    (cx + rx * 0.5, cy - ry),
                    (cx + rx, cy),
                    (cx + rx * 0.5, cy + ry),
                    (cx - rx * 0.5, cy + ry),
                ),
                count=count,
                label=f"{count} points",
                fill="#2563eb",
                stroke="#ffffff",
                opacity=opacity,
                metadata={"row": row, "col": col},
            )
        )
    return tuple(cells)


def _trend_line(payload: ScatterPayload) -> LineSpec | None:
    if not payload.include_trend:
        return None

    x_values = np.asarray(_finite_tuple(payload.x), dtype=float)
    y_values = np.asarray(_finite_tuple(payload.y), dtype=float)
    if x_values.size < 2 or y_values.size < 2 or x_values.size != y_values.size:
        return None
    if np.allclose(x_values, x_values[0]):
        return None

    slope, intercept = np.polyfit(x_values, y_values, 1)
    x0 = float(np.min(x_values))
    x1 = float(np.max(x_values))
    return LineSpec(
        x0=x0,
        y0=float(slope * x0 + intercept),
        x1=x1,
        y1=float(slope * x1 + intercept),
        label="Trend",
        kind="trend",
        stroke="#f97316",
        stroke_width=1.4,
    )


def _axis_range(values: tuple[float, ...], trend_line: LineSpec | None, *, axis: str) -> tuple[float, float]:
    range_values = list(values)
    if trend_line is not None:
        if axis == "x":
            range_values.extend((trend_line.x0, trend_line.x1))
        else:
            range_values.extend((trend_line.y0, trend_line.y1))
    return _padded_range(range_values, default=(0.0, 1.0), pad_ratio=0.06)
