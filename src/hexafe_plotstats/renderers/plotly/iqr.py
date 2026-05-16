from __future__ import annotations

from typing import Any

from ...models.payloads import IQRPayload
from ...models.render import RenderResult
from ...specs import iqr_payload_to_resolved_spec, to_mapping
from ._common import line_trace, require_plotly_graph_objects, resolved_layout


def iqr_payload_to_plotly_spec(payload: IQRPayload) -> dict[str, Any]:
    resolved = to_mapping(iqr_payload_to_resolved_spec(payload))
    metadata = {
        "kind": "iqr",
        "backend": "plotly",
        "group_count": len(resolved["boxes"]),
        "data_policy": "resolved_box_statistics",
    }
    traces: list[dict[str, Any]] = []
    if resolved["boxes"]:
        traces.append(_box_trace(resolved["boxes"]))
    if resolved["outlier_markers"]:
        traces.append(_outlier_trace(resolved["outlier_markers"]))
    traces.extend(line_trace(line) for line in resolved["spec_lines"])

    layout = resolved_layout(resolved, metadata)
    layout["boxmode"] = "group"
    return {"data": traces, "layout": layout, "metadata": metadata, "resolved": resolved}


def render_iqr_plotly(payload: IQRPayload) -> RenderResult:
    go = require_plotly_graph_objects()
    spec = iqr_payload_to_plotly_spec(payload)
    fig = go.Figure(data=spec["data"], layout=spec["layout"])
    return RenderResult(fig=fig, ax=None, metadata=spec["metadata"])


def _box_trace(boxes: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "box",
        "name": "IQR",
        "legendgroup": "iqr",
        "x": [box["position"] for box in boxes],
        "q1": [box["q1"] for box in boxes],
        "median": [box["median"] for box in boxes],
        "q3": [box["q3"] for box in boxes],
        "lowerfence": [box["lower_whisker"] for box in boxes],
        "upperfence": [box["upper_whisker"] for box in boxes],
        "boxpoints": False,
        "fillcolor": boxes[0].get("fill") or "#2563eb",
        "line": {"color": boxes[0].get("stroke") or "#1d4ed8"},
        "opacity": boxes[0].get("opacity", 0.62),
        "customdata": [[box["metadata"].get("count"), box["label"]] for box in boxes],
        "hovertemplate": (
            "group=%{customdata[1]}<br>"
            "n=%{customdata[0]}<br>"
            "q1=%{q1}<br>median=%{median}<br>q3=%{q3}<extra></extra>"
        ),
        "meta": {"data_policy": "resolved_box_statistics", "contains_raw_points": False},
    }


def _outlier_trace(markers: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "scatter",
        "mode": "markers",
        "name": "Outliers",
        "legendgroup": "iqr_outliers",
        "x": [marker["x"] for marker in markers],
        "y": [marker["y"] for marker in markers],
        "marker": {
            "size": [marker.get("size") or 4.5 for marker in markers],
            "color": [marker.get("fill") or "#ffffff" for marker in markers],
            "line": {"color": "#dc2626", "width": 1},
        },
        "customdata": [[marker["metadata"].get("group")] for marker in markers],
        "hovertemplate": "group=%{customdata[0]}<br>outlier=%{y}<extra></extra>",
        "meta": {"data_policy": "resolved_outliers", "contains_raw_points": False},
    }
