from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from ..models.payloads import ScatterPayload
from ..themes import theme_from_metadata
from .histogram import _format_number, _padded_range, _positive_dimension, _tick_count, _ticks
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
    theme = theme_from_metadata(payload.metadata)
    colors = dict(theme.get("colors") or {})
    canvas = Canvas(
        size=Size(width=_positive_dimension(width), height=_positive_dimension(height)),
        background=str(colors.get("background") or "#ffffff"),
    )
    plot_rect = Rect(x=72.0, y=62.0, width=max(canvas.size.width - 104.0, 48.0), height=max(canvas.size.height - 118.0, 48.0))
    x_values, y_values = _finite_arrays(payload)
    point_count = int(x_values.size)
    trend_line = _trend_line_from_arrays(payload, x_values, y_values)
    x_min, x_max = _axis_range_array(x_values, trend_line, axis="x")
    reference_lines = _reference_lines_from_metadata(payload, x_min, x_max)
    y_min, y_max = _axis_range_array(
        y_values,
        trend_line,
        axis="y",
        extra_values=tuple(value for line in reference_lines for value in (line.y0, line.y1)),
    )

    if payload.mode == "hexbin":
        markers = ()
        marker_batches = ()
        hex_cells = _hex_cells_from_arrays(payload, x_values, y_values, x_min, x_max, y_min, y_max)
        data_policy = "aggregated_hexbin"
    else:
        point_pairs = _point_pairs_from_arrays(x_values, y_values)
        markers = _marker_specs(payload, point_pairs) if _use_marker_specs(payload, point_pairs) else ()
        marker_batches = _marker_batch_specs(payload, point_pairs) if _use_marker_batches(payload, point_pairs) else ()
        hex_cells = ()
        data_policy = "full" if markers else "sampled" if payload.rasterized else "full"

    ticks_count = _tick_count(payload.metadata, sample_count=point_count)
    x_ticks = _ticks(x_min, x_max, ticks_count)
    y_ticks = _ticks(y_min, y_max, ticks_count)
    y_tick_decimals = _infer_tick_decimals(y_values)
    axis_labels = _axis_labels(payload)
    axes = (
        AxisSpec(
            orientation="x",
            label=axis_labels["x"],
            minimum=x_min,
            maximum=x_max,
            tick_values=x_ticks,
            tick_labels=tuple(_format_number(value) for value in x_ticks),
            metadata={"ticks_count": ticks_count},
        ),
        AxisSpec(
            orientation="y",
            label=axis_labels["y"],
            minimum=y_min,
            maximum=y_max,
            tick_values=y_ticks,
            tick_labels=tuple(_format_tick_with_decimals(value, decimals=y_tick_decimals) for value in y_ticks),
            metadata={"ticks_count": ticks_count, "inferred_decimals": y_tick_decimals},
        ),
    )

    return ResolvedScatterSpec(
        chart_type="scatter",
        canvas=canvas,
        title=TextSpec(
            text=_scatter_title(payload),
            x=36.0,
            y=28.0,
            font_size=18.0,
            fill=str(colors.get("text") or "#111827"),
            weight="600",
            role="title",
        ),
        plot_rect=plot_rect,
        axes=axes,
        markers=markers,
        marker_batches=marker_batches,
        hex_cells=hex_cells,
        trend_line=trend_line,
        reference_lines=reference_lines,
        metadata={
            "mode": payload.mode,
            "point_count": point_count,
            "hex_cell_count": len(hex_cells),
            "include_trend": payload.include_trend,
            "rasterized": payload.rasterized,
            "simplified_annotations": payload.simplified_annotations,
            "data_policy": data_policy,
            "raw_point_count": payload.metadata.get("raw_point_count", point_count),
            "finite_point_count": payload.metadata.get("finite_point_count", point_count),
            "dropped_nonfinite_count": payload.metadata.get("dropped_nonfinite_count", 0),
            "interactive_layers": _interactive_layer_metadata(payload, point_count, len(hex_cells), data_policy),
            "theme": theme,
        },
    )


def _scatter_title(payload: ScatterPayload) -> str:
    for key in ("characteristic_title", "characteristic", "characteristic_name", "metric_label", "title"):
        value = payload.metadata.get(key)
        if value:
            return str(value)
    return "Scatter"


def _axis_labels(payload: ScatterPayload) -> dict[str, str]:
    axis_labels = payload.metadata.get("axis_labels")
    if isinstance(axis_labels, dict):
        x_axis = axis_labels.get("x")
        y_axis = axis_labels.get("y")
        if x_axis or y_axis:
            return {
                "x": str(x_axis or "Sample number"),
                "y": str(y_axis or _default_y_axis_label(payload)),
            }
    return {
        "x": str(payload.metadata.get("x_label") or "Sample number"),
        "y": _default_y_axis_label(payload),
    }


def _default_y_axis_label(payload: ScatterPayload) -> str:
    for key in ("y_label", "characteristic_title", "characteristic", "characteristic_name", "metric_label"):
        value = payload.metadata.get(key)
        if value:
            return str(value)
    return "Characteristic"


def _infer_tick_decimals(values: np.ndarray, *, max_decimals: int = 6) -> int:
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return 3
    for decimals in range(max_decimals + 1):
        rounded = np.round(finite, decimals)
        tolerance = max(1e-12, 10.0 ** (-(decimals + 3)))
        if np.allclose(finite, rounded, rtol=0.0, atol=tolerance):
            return decimals
    return max_decimals


def _format_tick_with_decimals(value: float, *, decimals: int) -> str:
    if value == 0.0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 10_000 or magnitude < 0.001:
        return f"{value:.3g}"
    precision = max(0, min(int(decimals), 8))
    formatted = f"{value:.{precision}f}"
    if "." in formatted:
        formatted = formatted.rstrip("0").rstrip(".")
    if formatted in {"-0", "-0.0"}:
        return "0"
    return formatted


def _as_float_array(values: Sequence[float]) -> np.ndarray:
    return np.asarray(values, dtype=float).reshape(-1)


def _finite_arrays(payload: ScatterPayload) -> tuple[np.ndarray, np.ndarray]:
    x_values = _as_float_array(payload.x)
    y_values = _as_float_array(payload.y)
    size = min(x_values.size, y_values.size)
    if size == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    x_values = x_values[:size]
    y_values = y_values[:size]
    mask = np.isfinite(x_values) & np.isfinite(y_values)
    return x_values[mask], y_values[mask]


def _point_pairs_from_arrays(x_values: np.ndarray, y_values: np.ndarray) -> tuple[tuple[float, float], ...]:
    return tuple((float(x), float(y)) for x, y in zip(x_values, y_values, strict=False))


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


def _hex_cells_from_arrays(
    payload: ScatterPayload,
    x_values: np.ndarray,
    y_values: np.ndarray,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> tuple[HexCellSpec, ...]:
    if x_values.size == 0 or y_values.size == 0:
        return ()
    nx = max(int(payload.gridsize), 1)
    ny = max(int(round(nx / math.sqrt(3.0))), 1)
    x_span = max(x_max - x_min, np.finfo(float).eps)
    y_span = max(y_max - y_min, np.finfo(float).eps)
    dx = x_span / nx
    dy = y_span / ny

    rows = np.floor((y_values - y_min) / dy).astype(np.int64)
    rows = np.clip(rows, 0, ny - 1)
    offsets = np.where(rows % 2 == 1, 0.5, 0.0)
    cols = np.floor((x_values - x_min) / dx - offsets).astype(np.int64)
    cols = np.clip(cols, 0, nx - 1)

    keys = rows * nx + cols
    unique_keys, counts = np.unique(keys, return_counts=True)
    if unique_keys.size == 0:
        return ()

    max_count = int(np.max(counts))
    cells: list[HexCellSpec] = []
    for key, count_value in zip(unique_keys, counts, strict=False):
        row = int(key // nx)
        col = int(key % nx)
        count = int(count_value)
        cx = x_min + (col + 0.5 + (0.5 if row % 2 else 0.0)) * dx
        cy = y_min + (row + 0.5) * dy
        rx = dx * 0.48
        ry = dy * 0.48
        intensity = count / max_count if max_count else 0.0
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


def _trend_line_from_arrays(payload: ScatterPayload, x_values: np.ndarray, y_values: np.ndarray) -> LineSpec | None:
    if not payload.include_trend:
        return None
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


def _reference_lines_from_metadata(payload: ScatterPayload, x_min: float, x_max: float) -> tuple[LineSpec, ...]:
    raw_items: list[Any] = []
    for key in ("reference_lines", "horizontal_reference_lines"):
        candidate = payload.metadata.get(key)
        if isinstance(candidate, (list, tuple)):
            raw_items.extend(candidate)

    lines: list[LineSpec] = []
    for index, raw in enumerate(raw_items, start=1):
        line = _reference_line_from_raw(raw, index=index, x_min=x_min, x_max=x_max)
        if line is not None:
            lines.append(line)
    return tuple(lines)


def _reference_line_from_raw(raw: Any, *, index: int, x_min: float, x_max: float) -> LineSpec | None:
    if isinstance(raw, dict):
        value = raw.get("value", raw.get("y", raw.get("y0")))
        label = str(raw.get("label") or raw.get("name") or raw.get("kind") or f"Reference {index}")
        kind = str(raw.get("kind") or label).strip().lower().replace(" ", "_")
        stroke = str(raw.get("color") or raw.get("stroke") or _reference_line_color(kind))
        width = float(raw.get("width") or raw.get("stroke_width") or 1.0)
        dash = raw.get("dash") if isinstance(raw.get("dash"), (list, tuple)) else (6.0, 4.0)
    elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
        label = str(raw[0] or f"Reference {index}")
        value = raw[1]
        kind = label.strip().lower().replace(" ", "_")
        stroke = _reference_line_color(kind)
        width = 1.0
        dash = (6.0, 4.0)
    else:
        return None

    if not _is_finite_number(value):
        return None
    y_value = float(value)
    return LineSpec(
        x0=x_min,
        y0=y_value,
        x1=x_max,
        y1=y_value,
        label=label,
        kind=f"reference_{kind}",
        stroke=stroke,
        stroke_width=width,
        dash=tuple(float(item) for item in dash),
        metadata={"source": "metadata", "index": index},
    )


def _reference_line_color(kind: str) -> str:
    normalized = kind.strip().lower()
    if normalized in {"lsl", "usl", "lower_spec", "upper_spec"}:
        return "#dc2626"
    if normalized in {"nominal", "target"}:
        return "#16a34a"
    if normalized == "mean":
        return "#111827"
    return "#7c3aed"


def _axis_range_array(
    values: np.ndarray,
    trend_line: LineSpec | None,
    *,
    axis: str,
    extra_values: Sequence[float] = (),
) -> tuple[float, float]:
    range_values = values[np.isfinite(values)]
    extras: tuple[float, ...] = tuple(float(value) for value in extra_values if _is_finite_number(value))
    if trend_line is not None:
        extras = extras + ((trend_line.x0, trend_line.x1) if axis == "x" else (trend_line.y0, trend_line.y1))

    finite_extras = tuple(float(value) for value in extras if math.isfinite(float(value)))
    if range_values.size == 0:
        return _padded_range(finite_extras, default=(0.0, 1.0), pad_ratio=0.06)

    minimum = float(np.min(range_values))
    maximum = float(np.max(range_values))
    for value in finite_extras:
        minimum = min(minimum, value)
        maximum = max(maximum, value)
    return _padded_range_from_bounds(minimum, maximum, default=(0.0, 1.0), pad_ratio=0.06)


def _is_finite_number(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _padded_range_from_bounds(
    minimum: float,
    maximum: float,
    *,
    default: tuple[float, float],
    pad_ratio: float,
) -> tuple[float, float]:
    if not math.isfinite(minimum) or not math.isfinite(maximum):
        return default
    if minimum == maximum:
        pad = max(abs(minimum) * 0.1, 0.5)
        return minimum - pad, maximum + pad
    pad = (maximum - minimum) * pad_ratio
    return minimum - pad, maximum + pad


def _interactive_layer_metadata(
    payload: ScatterPayload,
    point_count: int,
    hex_cell_count: int,
    data_policy: str,
) -> tuple[dict[str, object], ...]:
    if payload.mode == "hexbin":
        return (
            {
                "id": "aggregated_hexbin",
                "role": "interactive_aggregate",
                "data_policy": "aggregated_hexbin",
                "point_count": hex_cell_count,
                "source_point_count": point_count,
                "contains_raw_points": False,
                "legend": {
                    "label": "Aggregated density",
                    "group": "scatter_aggregated",
                    "show": True,
                    "visible": True,
                    "togglable": True,
                },
            },
            {
                "id": "raw_points_static",
                "role": "static_raw_overlay",
                "data_policy": "static_raw_overlay",
                "point_count": point_count,
                "contains_raw_points": False,
                "rendering": "static_raster",
                "legend": {
                    "label": "Raw points",
                    "group": "scatter_raw",
                    "show": True,
                    "visible": True,
                    "togglable": True,
                },
            },
        )
    return (
        {
            "id": "scatter_points",
            "role": "interactive_points",
            "data_policy": data_policy,
            "point_count": point_count,
            "contains_raw_points": data_policy == "full",
            "legend": {
                "label": "Points",
                "group": "scatter_points",
                "show": True,
                "visible": True,
                "togglable": True,
            },
        },
    )
