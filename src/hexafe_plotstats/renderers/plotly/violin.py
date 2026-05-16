from __future__ import annotations

from collections import defaultdict
from typing import Any

from ...models.payloads import ViolinPayload
from ...models.render import RenderResult
from ...specs import to_mapping, violin_payload_to_resolved_spec
from ._common import line_trace, plotly_config, require_plotly_graph_objects, resolved_layout, rgba


def violin_payload_to_plotly_spec(payload: ViolinPayload, *, static: bool = True) -> dict[str, Any]:
    resolved = to_mapping(violin_payload_to_resolved_spec(payload))
    metadata = {
        "kind": "violin",
        "backend": "plotly",
        "group_count": len(resolved["groups"]),
        "data_policy": "resolved_violin_body",
        "theme": resolved.get("metadata", {}).get("theme"),
        "default_render_mode": "static" if static else "interactive",
        "recommended_dashboard_mode": "static_snapshot" if static else "interactive_plotly",
        "interactive_enabled": not static,
    }
    traces: list[dict[str, Any]] = []
    traces.extend(_body_trace(group) for group in resolved["groups"] if group.get("body_points"))
    traces.extend(_marker_traces(resolved["annotation_markers"]))
    traces.extend(line_trace(line) for line in resolved["spec_lines"])

    layout = resolved_layout(resolved, metadata)
    layout["showlegend"] = True
    return {"data": traces, "layout": layout, "config": plotly_config(static=static), "metadata": metadata, "resolved": resolved}


def render_violin_plotly(payload: ViolinPayload, *, static: bool = True) -> RenderResult:
    go = require_plotly_graph_objects()
    spec = violin_payload_to_plotly_spec(payload, static=static)
    fig = go.Figure(data=spec["data"], layout=spec["layout"])
    return RenderResult(fig=fig, ax=None, metadata={**spec["metadata"], "plotly_config": spec["config"]})


def _body_trace(group: dict[str, Any]) -> dict[str, Any]:
    points = group["body_points"]
    return {
        "type": "scatter",
        "mode": "lines",
        "fill": "toself",
        "name": group["label"],
        "legendgroup": f"violin_{group['label']}",
        "x": [point[0] for point in points],
        "y": [point[1] for point in points],
        "line": {"color": group.get("stroke") or "#1d4ed8", "width": 1},
        "fillcolor": rgba(group.get("fill") or "#2563eb", float(group.get("opacity") or 0.72)),
        "hoverinfo": "skip",
        "meta": {
            "data_policy": "resolved_violin_body",
            "contains_raw_points": False,
            "count": group.get("metadata", {}).get("count"),
            "group": group["label"],
        },
    }


def _marker_traces(markers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for marker in markers:
        grouped[str(marker.get("kind") or "marker")].append(marker)

    traces: list[dict[str, Any]] = []
    for kind, items in grouped.items():
        traces.append(
            {
                "type": "scatter",
                "mode": "markers",
                "name": kind.replace("_", " ").title(),
                "legendgroup": f"violin_marker_{kind}",
                "x": [marker["x"] for marker in items],
                "y": [marker["y"] for marker in items],
                "marker": {
                    "size": [marker.get("size") or 4.0 for marker in items],
                    "color": [marker.get("fill") or "#111827" for marker in items],
                    "line": {"color": [marker.get("stroke") or "#111827" for marker in items], "width": 1},
                },
                "customdata": [[marker.get("metadata", {}).get("group"), marker.get("kind")] for marker in items],
                "hovertemplate": "group=%{customdata[0]}<br>%{customdata[1]}=%{y}<extra></extra>",
                "meta": {"data_policy": "resolved_violin_markers", "contains_raw_points": False, "kind": kind},
            }
        )
    return traces
