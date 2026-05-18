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
    metadata = axis.get("metadata") if isinstance(axis.get("metadata"), dict) else {}
    layout: dict[str, Any] = {
        "title": {"text": str(axis.get("label") or "")},
        "range": [axis.get("minimum"), axis.get("maximum")],
        "tickmode": "array",
        "tickvals": list(axis.get("tick_values") or ()),
        "ticktext": list(axis.get("tick_labels") or ()),
    }
    if metadata.get("ticks_count"):
        layout["nticks"] = int(metadata["ticks_count"])
    if axis.get("scale") == "log":
        layout["type"] = "log"
    return layout


def axis_by_orientation(resolved: dict[str, Any], orientation: str) -> dict[str, Any]:
    for axis in resolved.get("axes", ()):
        if axis.get("orientation") == orientation:
            return axis
    return {}


_VALUE_LEGEND_LABELS = {"lsl", "usl", "mean", "median", "q1", "q3"}


def line_trace(line: dict[str, Any], *, showlegend: bool = True) -> dict[str, Any]:
    label = str(line.get("label") or line.get("kind") or "line")
    return {
        "type": "scatter",
        "mode": "lines",
        "name": value_label(label, line_value(line)),
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


def reference_annotation(line: dict[str, Any], *, axis: str) -> dict[str, Any] | None:
    label = str(line.get("label") or line.get("kind") or "").strip()
    if label.strip().casefold() not in _VALUE_LEGEND_LABELS:
        return None
    value = line_value(line)
    if value is None:
        return None
    color = str(line.get("stroke") or "#111827")
    annotation: dict[str, Any] = {
        "text": value_label(label, value),
        "showarrow": False,
        "font": {"size": 11, "color": color},
        "bgcolor": "#ffffff",
        "bordercolor": "#cbd5e1",
        "borderwidth": 1,
        "borderpad": 3,
        "opacity": 1.0,
    }
    if axis == "x":
        annotation.update({"xref": "x", "yref": "paper", "x": value, "y": 1.04, "yanchor": "bottom"})
    else:
        annotation.update({"xref": "paper", "yref": "y", "x": 1.0, "y": value, "xanchor": "right"})
    return annotation


def value_label(label: str, value: float | None) -> str:
    clean_label = str(label or "").strip()
    if value is None or clean_label.casefold() not in _VALUE_LEGEND_LABELS:
        return clean_label
    return f"{clean_label}={format_compact_number(value)}"


def line_value(line: dict[str, Any]) -> float | None:
    for first, second in (("x0", "x1"), ("y0", "y1")):
        try:
            left = float(line.get(first))
            right = float(line.get(second))
        except (TypeError, ValueError):
            continue
        if math.isfinite(left) and math.isfinite(right) and math.isclose(left, right):
            return left
    return None


def format_compact_number(value: float) -> str:
    if not math.isfinite(value):
        return str(value)
    magnitude = abs(value)
    if magnitude >= 10_000 or (0.0 < magnitude < 0.001):
        return f"{value:.4g}"
    text = f"{value:.6f}".rstrip("0").rstrip(".")
    return "0" if text in {"-0", ""} else text


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
    theme = metadata.get("theme") if isinstance(metadata.get("theme"), dict) else {}
    colors = theme.get("colors") if isinstance(theme.get("colors"), dict) else {}
    is_dark = str(theme.get("name") or "").casefold() == "dark"
    return {
        "template": "plotly_dark" if is_dark else "plotly_white",
        "title": {"text": str(title.get("text") or resolved.get("chart_type") or "")},
        "hovermode": "closest",
        "xaxis": axis_layout(axis_by_orientation(resolved, "x")),
        "yaxis": axis_layout(axis_by_orientation(resolved, "y")),
        "legend": {"groupclick": "toggleitem"},
        "paper_bgcolor": colors.get("background"),
        "plot_bgcolor": colors.get("plot_background"),
        "font": {
            "family": theme.get("font_family"),
            "size": theme.get("font_size"),
            "color": colors.get("text"),
        },
        "meta": metadata,
    }
