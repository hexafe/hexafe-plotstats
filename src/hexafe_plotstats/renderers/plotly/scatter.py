from __future__ import annotations

from typing import Any

from ...interactive import build_scatter_interactive_spec
from ...models.payloads import ScatterPayload
from ...models.render import RenderResult
from ...specs import scatter_payload_to_resolved_spec, to_mapping
from ..base import RendererBackendUnavailable

_LARGE_PLOTLY_SCATTER_THRESHOLD = 50_000


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
    if payload.mode == "hexbin":
        resolved = to_mapping(scatter_payload_to_resolved_spec(payload))
        aggregate_trace = _hexbin_trace(resolved)
        raw_trace = _raw_static_legend_trace(resolved["metadata"]["interactive_layers"][1])
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
                target_interactive_points=target_interactive_points,
            )
        )
        aggregate_layer = interactive["layers"][0]
        aggregate_trace = _aggregate_trace(aggregate_layer)
        raw_trace = _raw_static_legend_trace(interactive["layers"][1])
        metadata = {
            "mode": payload.mode,
            "data_policy": aggregate_layer["data_policy"],
            "interactive_contains_raw_points": False,
            "source_point_count": interactive["metadata"]["source_point_count"],
            "interactive_point_count": len(aggregate_layer["points"]),
        }

    return {
        "data": [aggregate_trace, raw_trace],
        "layout": {
            "hovermode": "closest",
            "legend": {"groupclick": "toggleitem"},
            "meta": metadata,
        },
        "metadata": metadata,
    }


def _raw_scatter_plotly_spec(payload: ScatterPayload) -> dict[str, Any]:
    metadata = {
        "mode": payload.mode,
        "data_policy": "full",
        "interactive_contains_raw_points": True,
        "source_point_count": len(payload.x),
        "interactive_point_count": len(payload.x),
    }
    return {
        "data": [
            {
                "type": "scattergl",
                "mode": "markers",
                "name": "Points",
                "legendgroup": "scatter_points",
                "x": list(payload.x),
                "y": list(payload.y),
                "marker": {"size": payload.marker_size, "opacity": payload.alpha},
                "hovertemplate": "x=%{x}<br>y=%{y}<extra></extra>",
            }
        ],
        "layout": {"hovermode": "closest", "meta": metadata},
        "metadata": metadata,
    }


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
        "meta": {"contains_raw_points": False, "data_policy": layer["data_policy"]},
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
