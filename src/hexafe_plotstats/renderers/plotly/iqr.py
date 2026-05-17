from __future__ import annotations

from typing import Any

from ...models.payloads import IQRPayload
from ...models.render import RenderResult
from ...specs import iqr_payload_to_resolved_spec, to_mapping
from ._common import line_trace, plotly_config, require_plotly_graph_objects, resolved_layout


def iqr_payload_to_plotly_spec(payload: IQRPayload, *, static: bool = True) -> dict[str, Any]:
    resolved = to_mapping(iqr_payload_to_resolved_spec(payload))
    metadata = {
        "kind": "iqr",
        "backend": "plotly",
        "group_count": len(resolved["boxes"]),
        "data_policy": "resolved_box_statistics",
        "theme": resolved.get("metadata", {}).get("theme"),
        "default_render_mode": "static" if static else "interactive",
        "recommended_dashboard_mode": "static_snapshot" if static else "interactive_plotly",
        "interactive_enabled": not static,
    }
    traces: list[dict[str, Any]] = []
    if resolved["boxes"]:
        traces.append(_box_trace(resolved["boxes"]))
        traces.append(_mean_trace(resolved["boxes"]))
    if resolved["outlier_markers"]:
        traces.append(_outlier_trace(resolved["outlier_markers"]))
    traces.extend(line_trace(line) for line in resolved["spec_lines"])

    layout = resolved_layout(resolved, metadata)
    layout["boxmode"] = "group"
    return {"data": traces, "layout": layout, "config": plotly_config(static=static), "metadata": metadata, "resolved": resolved}


def render_iqr_plotly(payload: IQRPayload, *, static: bool = True) -> RenderResult:
    go = require_plotly_graph_objects()
    spec = iqr_payload_to_plotly_spec(payload, static=static)
    fig = go.Figure(data=spec["data"], layout=spec["layout"])
    return RenderResult(fig=fig, ax=None, metadata={**spec["metadata"], "plotly_config": spec["config"]})


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
        "customdata": [
            [
                box["metadata"].get("count"),
                box["label"],
                box["metadata"].get("mean"),
                box["metadata"].get("std"),
                box["metadata"].get("iqr"),
                box["lower_whisker"],
                box["upper_whisker"],
                box["metadata"].get("outlier_count"),
            ]
            for box in boxes
        ],
        "hovertemplate": (
            "group=%{customdata[1]}<br>"
            "n=%{customdata[0]}<br>"
            "mean=%{customdata[2]}<br>"
            "std=%{customdata[3]}<br>"
            "q1=%{q1}<br>median=%{median}<br>q3=%{q3}<br>"
            "iqr=%{customdata[4]}<br>"
            "whisker low=%{customdata[5]}<br>"
            "whisker high=%{customdata[6]}<br>"
            "outliers=%{customdata[7]}<extra></extra>"
        ),
        "meta": {"data_policy": "resolved_box_statistics", "contains_raw_points": False},
    }


def _mean_trace(boxes: list[dict[str, Any]]) -> dict[str, Any]:
    mean_boxes = [box for box in boxes if box.get("metadata", {}).get("mean") is not None]
    return {
        "type": "scatter",
        "mode": "markers",
        "name": "Mean",
        "legendgroup": "iqr_mean",
        "x": [box["position"] for box in mean_boxes],
        "y": [box["metadata"]["mean"] for box in mean_boxes],
        "marker": {"symbol": "diamond", "size": 7, "color": "#111827"},
        "customdata": [[box["label"], box["metadata"].get("count")] for box in mean_boxes],
        "hovertemplate": "group=%{customdata[0]}<br>mean=%{y}<br>n=%{customdata[1]}<extra></extra>",
        "meta": {"data_policy": "resolved_box_mean", "contains_raw_points": False},
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
