from __future__ import annotations

import math
from typing import Any

from ..base import RendererBackendUnavailable


def require_plotly_graph_objects() -> Any:
    try:
        import plotly.graph_objects as go
    except ModuleNotFoundError as exc:
        raise RendererBackendUnavailable(
            "plotly renderer is not installed; install hexafe-plotstats with the plotly extra"
        ) from exc
    return go


def plotly_config(*, static: bool = False) -> dict[str, Any]:
    config: dict[str, Any] = {
        "responsive": True,
        "scrollZoom": False,
        "displaylogo": False,
        "modeBarButtonsToRemove": [
            "lasso2d",
            "select2d",
            "autoScale2d",
            "toggleSpikelines",
        ],
    }
    if static:
        config["staticPlot"] = True
        config["displayModeBar"] = False
    return config


def axis_layout(axis: dict[str, Any]) -> dict[str, Any]:
    layout: dict[str, Any] = {
        "title": {"text": str(axis.get("label") or "")},
        "range": [axis.get("minimum"), axis.get("maximum")],
        "tickmode": "array",
        "tickvals": list(axis.get("tick_values") or ()),
        "ticktext": list(axis.get("tick_labels") or ()),
    }
    if axis.get("scale") == "log":
        layout["type"] = "log"
    return layout


def axis_by_orientation(resolved: dict[str, Any], orientation: str) -> dict[str, Any]:
    for axis in resolved.get("axes", ()):
        if axis.get("orientation") == orientation:
            return axis
    return {}


def line_trace(line: dict[str, Any], *, showlegend: bool = True) -> dict[str, Any]:
    return {
        "type": "scatter",
        "mode": "lines",
        "name": line.get("label") or line.get("kind") or "line",
        "legendgroup": line.get("kind") or line.get("label") or "line",
        "showlegend": showlegend,
        "x": [line.get("x0"), line.get("x1")],
        "y": [line.get("y0"), line.get("y1")],
        "line": {
            "color": line.get("stroke") or "#111827",
            "width": line.get("stroke_width") or 1.0,
            "dash": dash_name(line.get("dash") or ()),
        },
        "hovertemplate": f"{line.get('label') or 'line'}<extra></extra>",
        "meta": {"kind": line.get("kind")},
    }


def dash_name(dash: Any) -> str:
    if not dash:
        return "solid"
    try:
        values = [float(value) for value in dash]
    except (TypeError, ValueError):
        return "dash"
    if len(values) >= 2 and values[0] <= values[1]:
        return "dot"
    return "dash"


def rgba(color: str | None, alpha: float) -> str:
    if not color:
        color = "#2563eb"
    color = color.strip()
    if len(color) == 7 and color.startswith("#"):
        try:
            red = int(color[1:3], 16)
            green = int(color[3:5], 16)
            blue = int(color[5:7], 16)
        except ValueError:
            red, green, blue = 37, 99, 235
        return f"rgba({red}, {green}, {blue}, {clamp(alpha, 0.0, 1.0):.3f})"
    return color


def clamp(value: float, minimum: float, maximum: float) -> float:
    if not math.isfinite(value):
        return minimum
    return max(minimum, min(maximum, value))


def resolved_layout(resolved: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    title = resolved.get("title") or {}
    return {
        "template": "plotly_white",
        "title": {"text": str(title.get("text") or resolved.get("chart_type") or "")},
        "hovermode": "closest",
        "xaxis": axis_layout(axis_by_orientation(resolved, "x")),
        "yaxis": axis_layout(axis_by_orientation(resolved, "y")),
        "legend": {"groupclick": "toggleitem"},
        "meta": metadata,
    }
