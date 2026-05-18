from __future__ import annotations

import math
from typing import Any

import numpy as np

from ...interactive import build_scatter_interactive_spec
from ...models.payloads import ScatterPayload
from ...models.render import RenderResult
from ...specs import scatter_payload_to_resolved_spec, to_mapping
from ..base import RendererBackendUnavailable
from ._common import line_trace, plotly_config, reference_annotation, resolved_layout

_LARGE_PLOTLY_SCATTER_THRESHOLD = 50_000
_STATIC_RASTER_BINS = 192


def scatter_payload_to_plotly_spec(
    payload: ScatterPayload,
    *,
    target_interactive_points: int = 500,
) -> dict[str, Any]:
    point_count = len(payload.x)
    if payload.mode == "hexbin" or point_count >= _LARGE_PLOTLY_SCATTER_THRESHOLD:
        return _large_scatter_plotly_spec(payload, target_interactive_points=target_interactive_points)
    return _raw_scatter_plotly_spec(payload)


def render_scatter_plotly(
    payload: ScatterPayload,
    *,
    target_interactive_points: int = 500,
) -> RenderResult:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError as exc:
        raise RendererBackendUnavailable(
            "plotly renderer is not installed; install hexafe-plotstats with the plotly extra"
        ) from exc

    spec = scatter_payload_to_plotly_spec(payload, target_interactive_points=target_interactive_points)
    fig = go.Figure(data=spec["data"], layout=spec["layout"])
    return RenderResult(fig=fig, ax=None, metadata={"kind": "scatter", "backend": "plotly", **spec["metadata"]})


def _large_scatter_plotly_spec(payload: ScatterPayload, *, target_interactive_points: int) -> dict[str, Any]:
    resolved = to_mapping(scatter_payload_to_resolved_spec(payload))
    if payload.mode == "hexbin":
        aggregate_trace = _hexbin_trace(resolved)
        raw_trace = _raw_static_raster_trace(
            payload,
            resolved["metadata"]["interactive_layers"][1],
            x_range=_axis_range(resolved, "x"),
            y_range=_axis_range(resolved, "y"),
        )
        metadata = {
            "mode": payload.mode,
            "data_policy": "aggregated_hexbin",
            "interactive_contains_raw_points": False,
            "source_point_count": resolved["metadata"]["point_count"],
            "interactive_point_count": len(resolved["hex_cells"]),
        }
    else:
        interactive = to_mapping(
            build_scatter_interactive_spec(
                payload.x,
                payload.y,
                x_view=payload.metadata.get("x_view"),
                target_interactive_points=target_interactive_points,
            )
        )
        aggregate_layer = interactive["layers"][0]
        aggregate_trace = _aggregate_trace(aggregate_layer)
        raw_trace = _raw_static_raster_trace(payload, interactive["layers"][1])
        metadata = {
            "mode": payload.mode,
            "data_policy": aggregate_layer["data_policy"],
            "interactive_contains_raw_points": False,
            "source_point_count": interactive["metadata"]["source_point_count"],
            "interactive_point_count": len(aggregate_layer["points"]),
        }

    data = [raw_trace, aggregate_trace]
    trend_trace = _trend_trace_from_resolved(resolved)
    if trend_trace is not None:
        data.append(trend_trace)
    data.extend(_reference_line_traces(resolved))
    layout = resolved_layout(resolved, metadata)
    layout["annotations"] = _reference_annotations(resolved)

    return {
        "data": data,
        "layout": layout,
        "config": plotly_config(static=False),
        "metadata": metadata,
    }


def _raw_scatter_plotly_spec(payload: ScatterPayload) -> dict[str, Any]:
    resolved = to_mapping(scatter_payload_to_resolved_spec(payload))
    metadata = {
        "mode": payload.mode,
        "data_policy": "full",
        "interactive_contains_raw_points": True,
        "source_point_count": len(payload.x),
        "interactive_point_count": len(payload.x),
    }
    data = [
        {
            "type": "scattergl",
            "mode": "markers",
            "name": "Points",
            "legendgroup": "scatter_points",
            "x": list(payload.x),
            "y": list(payload.y),
            "marker": {"size": payload.marker_size, "opacity": payload.alpha},
            **_raw_scatter_hover_fields(payload),
        }
    ]
    trend_trace = _trend_trace_from_resolved(resolved)
    if trend_trace is not None:
        data.append(trend_trace)
    data.extend(_reference_line_traces(resolved))
    return {
        "data": data,
        "layout": {
            **resolved_layout(resolved, metadata),
            "annotations": _reference_annotations(resolved),
        },
        "config": plotly_config(static=False),
        "metadata": metadata,
    }


def _raw_scatter_hover_fields(payload: ScatterPayload) -> dict[str, Any]:
    labels = _x_display_labels(payload)
    if labels is None:
        return {"hovertemplate": "x=%{x}<br>y=%{y}<extra></extra>"}
    return {
        "customdata": [[label] for label in labels],
        "hovertemplate": "sample=%{customdata[0]}<br>x=%{x}<br>y=%{y}<extra></extra>",
        "meta": {"x_display_label_source": "x_display_labels"},
    }


def _x_display_labels(payload: ScatterPayload) -> tuple[str, ...] | None:
    raw_labels = payload.metadata.get("x_display_labels")
    if isinstance(raw_labels, (str, bytes)) or not isinstance(raw_labels, (list, tuple)):
        return None
    labels = tuple(str(label) for label in raw_labels)
    return labels if len(labels) == len(payload.x) else None


def _trend_trace_from_resolved(resolved: dict[str, Any]) -> dict[str, Any] | None:
    line = resolved.get("trend_line")
    if not isinstance(line, dict):
        return None
    return {
        "type": "scatter",
        "mode": "lines",
        "name": line.get("label") or "Trend",
        "legendgroup": "scatter_trend",
        "x": [line.get("x0"), line.get("x1")],
        "y": [line.get("y0"), line.get("y1")],
        "line": {"color": line.get("stroke") or "#f97316", "width": 1.1, "dash": "dash"},
        "opacity": 0.35,
        "hovertemplate": "Trend<extra></extra>",
        "meta": {"kind": "trend", "data_policy": "least_squares"},
    }


def _reference_line_traces(resolved: dict[str, Any]) -> list[dict[str, Any]]:
    return [line_trace(line) for line in resolved.get("reference_lines") or () if isinstance(line, dict)]


def _reference_annotations(resolved: dict[str, Any]) -> list[dict[str, Any]]:
    annotations: list[dict[str, Any]] = []
    for line in resolved.get("reference_lines") or ():
        if not isinstance(line, dict):
            continue
        annotation = reference_annotation(line, axis="y")
        if annotation is not None:
            annotations.append(annotation)
    return annotations


def _hexbin_trace(resolved: dict[str, Any]) -> dict[str, Any]:
    cells = resolved["hex_cells"]
    return {
        "type": "scattergl",
        "mode": "markers",
        "name": "Aggregated density",
        "legendgroup": "scatter_aggregated",
        "x": [_cell_center(cell, axis=0) for cell in cells],
        "y": [_cell_center(cell, axis=1) for cell in cells],
        "customdata": [[cell["count"]] for cell in cells],
        "marker": {
            "size": 8,
            "color": [cell["count"] for cell in cells],
            "colorscale": "Blues",
            "colorbar": {"title": "points per cell"},
            "showscale": True,
        },
        "hovertemplate": "points per cell=%{customdata[0]}<extra></extra>",
        "legendrank": 10,
        "meta": {"contains_raw_points": False, "data_policy": "aggregated_hexbin"},
    }


def _aggregate_trace(layer: dict[str, Any]) -> dict[str, Any]:
    points = layer["points"]
    return {
        "type": "scattergl",
        "mode": "lines+markers",
        "name": layer["legend"]["label"],
        "legendgroup": layer["legend"]["group"],
        "x": [point["x"] for point in points],
        "y": [point["y"] for point in points],
        "customdata": [[point["count"], point["y_min"], point["y_max"]] for point in points],
        "hovertemplate": "x=%{x}<br>mean=%{y}<br>count=%{customdata[0]}<br>min=%{customdata[1]}<br>max=%{customdata[2]}<extra></extra>",
        "legendrank": 10,
        "meta": {"contains_raw_points": False, "data_policy": layer["data_policy"]},
    }


def _raw_static_raster_trace(
    payload: ScatterPayload,
    layer: dict[str, Any],
    *,
    x_range: tuple[float, float] | None = None,
    y_range: tuple[float, float] | None = None,
) -> dict[str, Any]:
    legend = layer["legend"]
    x_values, y_values = _finite_numeric_arrays(payload)
    source_point_count = int(x_values.size)
    if source_point_count == 0:
        return _raw_static_legend_trace(layer)

    x_min, x_max = x_range or _value_range(x_values)
    y_min, y_max = y_range or _value_range(y_values)
    if not _valid_range(x_min, x_max) or not _valid_range(y_min, y_max):
        return _raw_static_legend_trace(layer)

    x_values, y_values = _filter_range(x_values, y_values, x_min, x_max, y_min, y_max)
    raster_point_count = int(x_values.size)
    if raster_point_count == 0:
        return _raw_static_legend_trace(layer)

    x_bins, y_bins = _raster_bin_counts(x_min, x_max, y_min, y_max)
    counts, x_edges, y_edges = np.histogram2d(
        x_values,
        y_values,
        bins=(x_bins, y_bins),
        range=((x_min, x_max), (y_min, y_max)),
    )
    z_values = np.log1p(counts.T)
    z = [[float(value) if value > 0.0 else None for value in row] for row in z_values]

    return {
        "type": "heatmap",
        "name": legend["label"],
        "legendgroup": legend["group"],
        "showlegend": legend["show"],
        "visible": legend["visible"],
        "x": _edge_centers(x_edges),
        "y": _edge_centers(y_edges),
        "z": z,
        "showscale": False,
        "colorscale": [
            [0.0, "rgba(37, 99, 235, 0.00)"],
            [1.0, "rgba(37, 99, 235, 0.32)"],
        ],
        "hoverinfo": "skip",
        "legendrank": 20,
        "meta": {
            "role": "static_raw_overlay",
            "contains_raw_points": False,
            "rendering": "static_raster_heatmap",
            "source_point_count": source_point_count,
            "raster_point_count": raster_point_count,
            "raster_bins": {"x": x_bins, "y": y_bins},
            "raster_payload_cell_count": x_bins * y_bins,
        },
    }


def _raw_static_legend_trace(layer: dict[str, Any]) -> dict[str, Any]:
    legend = layer["legend"]
    return {
        "type": "scattergl",
        "mode": "markers",
        "name": legend["label"],
        "legendgroup": legend["group"],
        "x": [],
        "y": [],
        "showlegend": legend["show"],
        "visible": legend["visible"],
        "hoverinfo": "skip",
        "legendrank": 20,
        "meta": {
            "role": "static_raw_overlay",
            "contains_raw_points": False,
            "rendering": layer.get("rendering") or layer.get("metadata", {}).get("rendering"),
            "source_point_count": layer.get("point_count") or layer.get("metadata", {}).get("source_point_count"),
        },
    }


def _cell_center(cell: dict[str, Any], *, axis: int) -> float:
    values = [float(point[axis]) for point in cell["points"]]
    return sum(values) / len(values)


def _finite_numeric_arrays(payload: ScatterPayload) -> tuple[np.ndarray, np.ndarray]:
    x_values = np.asarray(payload.x, dtype=float).reshape(-1)
    y_values = np.asarray(payload.y, dtype=float).reshape(-1)
    size = min(x_values.size, y_values.size)
    if size == 0:
        return np.asarray([], dtype=float), np.asarray([], dtype=float)
    x_values = x_values[:size]
    y_values = y_values[:size]
    mask = np.isfinite(x_values) & np.isfinite(y_values)
    return x_values[mask], y_values[mask]


def _axis_range(resolved: dict[str, Any], orientation: str) -> tuple[float, float] | None:
    for axis in resolved.get("axes", ()):
        if axis.get("orientation") == orientation:
            minimum = axis.get("minimum")
            maximum = axis.get("maximum")
            if _is_finite_number(minimum) and _is_finite_number(maximum):
                return float(minimum), float(maximum)
    return None


def _value_range(values: np.ndarray) -> tuple[float, float]:
    minimum = float(np.min(values))
    maximum = float(np.max(values))
    if math.isclose(minimum, maximum):
        pad = max(abs(minimum) * 0.1, 0.5)
        return minimum - pad, maximum + pad
    return minimum, maximum


def _filter_range(
    x_values: np.ndarray,
    y_values: np.ndarray,
    x_min: float,
    x_max: float,
    y_min: float,
    y_max: float,
) -> tuple[np.ndarray, np.ndarray]:
    x_low, x_high = sorted((x_min, x_max))
    y_low, y_high = sorted((y_min, y_max))
    mask = (x_values >= x_low) & (x_values <= x_high) & (y_values >= y_low) & (y_values <= y_high)
    return x_values[mask], y_values[mask]


def _raster_bin_counts(x_min: float, x_max: float, y_min: float, y_max: float) -> tuple[int, int]:
    x_span = abs(x_max - x_min)
    y_span = abs(y_max - y_min)
    if x_span <= 0.0 or y_span <= 0.0:
        return _STATIC_RASTER_BINS, _STATIC_RASTER_BINS
    ratio = math.sqrt(x_span / y_span)
    x_bins = int(round(_STATIC_RASTER_BINS * min(max(ratio, 0.5), 2.0)))
    y_bins = int(round(_STATIC_RASTER_BINS * min(max(1.0 / ratio, 0.5), 2.0)))
    return max(32, min(x_bins, 256)), max(32, min(y_bins, 256))


def _edge_centers(edges: np.ndarray) -> list[float]:
    centers = (edges[:-1] + edges[1:]) / 2.0
    return [float(value) for value in centers]


def _valid_range(minimum: float, maximum: float) -> bool:
    return math.isfinite(minimum) and math.isfinite(maximum) and not math.isclose(minimum, maximum)


def _is_finite_number(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False
