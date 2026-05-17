from __future__ import annotations

import math
from typing import Any

import numpy as np

from ...models.payloads import HistogramPayload
from ...models.render import RenderResult
from ...specs import histogram_payload_to_resolved_spec, to_mapping
from ._common import dash_name, line_trace, plotly_config, require_plotly_graph_objects, resolved_layout, rgba


def histogram_payload_to_plotly_spec(payload: HistogramPayload, *, static: bool = True) -> dict[str, Any]:
    resolved = to_mapping(histogram_payload_to_resolved_spec(payload))
    y_mode = _histogram_y_mode(payload)
    metadata = {
        "kind": "histogram",
        "backend": "plotly",
        "bar_count": len(resolved["bars"]),
        "curve_count": len(resolved["curves"]),
        "warning_count": len(resolved.get("warnings") or ()),
        "theme": resolved.get("metadata", {}).get("theme"),
        "default_render_mode": "static" if static else "interactive",
        "recommended_dashboard_mode": "static_snapshot" if static else "interactive_plotly",
        "interactive_enabled": not static,
        "histogram_y_mode": y_mode,
    }
    traces: list[dict[str, Any]] = []
    if resolved["bars"]:
        traces.append(_bar_trace(resolved["bars"], payload=payload, density=payload.density, y_mode=y_mode))
    curve_scale = _relative_curve_scale(payload) if y_mode == "relative_percent" else 1.0
    traces.extend(_curve_trace(curve, y_scale=curve_scale) for curve in resolved["curves"])
    traces.extend(line_trace(line) for line in resolved["spec_lines"])
    if resolved.get("mean_line") is not None:
        traces.append(line_trace(resolved["mean_line"]))
    if static and resolved.get("table") is not None:
        traces.append(_table_trace(resolved["table"]))

    layout = resolved_layout(resolved, metadata)
    if y_mode == "relative_percent":
        layout["yaxis"] = {
            **layout["yaxis"],
            "title": {"text": "Frequency (%)"},
            "tickformat": ".0%",
            "range": [0.0, _relative_y_axis_top(traces)],
        }
    if static and resolved.get("table") is not None:
        layout["xaxis"] = {**layout["xaxis"], "domain": [0.0, 0.72]}
    layout["barmode"] = "overlay"
    return {"data": traces, "layout": layout, "config": plotly_config(static=static), "metadata": metadata, "resolved": resolved}


def render_histogram_plotly(payload: HistogramPayload, *, static: bool = True) -> RenderResult:
    go = require_plotly_graph_objects()
    spec = histogram_payload_to_plotly_spec(payload, static=static)
    fig = go.Figure(data=spec["data"], layout=spec["layout"])
    return RenderResult(fig=fig, ax=None, metadata={**spec["metadata"], "plotly_config": spec["config"]})


def _histogram_y_mode(payload: HistogramPayload) -> str:
    raw = (
        payload.metadata.get("histogram_y_mode")
        or payload.metadata.get("y_mode")
        or payload.metadata.get("normalization")
    )
    if str(raw or "").strip().lower() in {"relative_percent", "frequency_percent", "percent"}:
        return "relative_percent"
    return "density" if payload.density else "count"


def _bar_trace(
    bars: list[dict[str, Any]],
    *,
    payload: HistogramPayload,
    density: bool,
    y_mode: str,
) -> dict[str, Any]:
    raw_values = [float(bar["y1"]) for bar in bars]
    if y_mode == "relative_percent":
        counts = _histogram_bin_counts(payload, bars) or raw_values
        total = sum(counts)
    else:
        counts = raw_values
        total = 0.0
    if y_mode == "relative_percent" and total > 0.0:
        y_values = [value / total for value in counts]
        customdata = [[bar["x0"], bar["x1"], count, value] for bar, count, value in zip(bars, counts, y_values, strict=False)]
        hovertemplate = (
            "bin=%{customdata[0]}..%{customdata[1]}<br>"
            "frequency=%{customdata[3]:.2%}<br>"
            "count=%{customdata[2]}<extra></extra>"
        )
    else:
        y_values = raw_values
        customdata = [[bar["x0"], bar["x1"], bar["y1"]] for bar in bars]
        hovertemplate = (
            "bin=%{customdata[0]}..%{customdata[1]}<br>"
            f"{'density' if density else 'count'}=%{{customdata[2]}}<extra></extra>"
        )
    return {
        "type": "bar",
        "name": "Histogram",
        "legendgroup": "histogram",
        "x": [(bar["x0"] + bar["x1"]) / 2.0 for bar in bars],
        "y": y_values,
        "width": [bar["x1"] - bar["x0"] for bar in bars],
        "marker": {
            "color": bars[0].get("fill") or "#2563eb",
            "line": {"color": bars[0].get("stroke") or "#1d4ed8", "width": 1},
        },
        "opacity": bars[0].get("opacity", 0.82),
        "customdata": customdata,
        "hovertemplate": hovertemplate,
    }


def _histogram_bin_counts(payload: HistogramPayload, bars: list[dict[str, Any]]) -> list[float]:
    try:
        values = np.asarray(payload.values, dtype=float).reshape(-1)
        edges = np.asarray(payload.bin_edges, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return []
    values = values[np.isfinite(values)]
    edges = edges[np.isfinite(edges)]
    if values.size == 0 or edges.size < 2:
        return []
    try:
        counts, _ = np.histogram(values, bins=edges)
    except ValueError:
        return []
    if len(counts) != len(bars):
        return []
    return [float(value) for value in counts]


def _relative_curve_scale(payload: HistogramPayload) -> float:
    try:
        edges = np.asarray(payload.bin_edges, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return 1.0
    edges = edges[np.isfinite(edges)]
    if edges.size < 2:
        return 1.0
    widths = np.diff(edges)
    positive_widths = widths[np.isfinite(widths) & (widths > 0.0)]
    if positive_widths.size == 0:
        return 1.0
    width = float(np.median(positive_widths))
    return width if math.isfinite(width) and width > 0.0 else 1.0


def _relative_y_axis_top(traces: list[dict[str, Any]]) -> float:
    values: list[float] = []
    for trace in traces:
        if trace.get("type") != "bar" and trace.get("meta", {}).get("data_policy") != "resolved_curve":
            continue
        for value in trace.get("y") or ():
            try:
                number = float(value)
            except (TypeError, ValueError):
                continue
            if math.isfinite(number) and number >= 0.0:
                values.append(number)
    if not values:
        return 1.0
    return min(max(max(values) * 1.16, 0.05), 1.0)


def _curve_trace(curve: dict[str, Any], *, y_scale: float = 1.0) -> dict[str, Any]:
    y_values = [float(value) * y_scale for value in curve["y"]]
    trace = {
        "type": "scatter",
        "mode": "lines",
        "name": curve["label"],
        "legendgroup": curve.get("kind") or curve["label"],
        "x": list(curve["x"]),
        "y": y_values,
        "line": {
            "color": curve.get("stroke") or "#f97316",
            "width": curve.get("stroke_width") or 1.5,
            "dash": dash_name(curve.get("dash") or ()),
        },
        "opacity": curve.get("opacity", 1.0),
        "hovertemplate": f"{curve['label']}<br>x=%{{x}}<br>y=%{{y}}<extra></extra>",
        "meta": {"kind": curve.get("kind"), "data_policy": "resolved_curve"},
    }
    if curve.get("fill_to_baseline"):
        trace["fill"] = "tozeroy"
        trace["fillcolor"] = rgba(curve.get("fill_color") or curve.get("stroke"), float(curve.get("fill_alpha") or 0.0))
    return trace


def _table_trace(table: dict[str, Any]) -> dict[str, Any]:
    labels: list[str] = []
    values: list[str] = []
    for row in table.get("rows", ()):
        cells = row.get("cells") or ()
        if len(cells) >= 2:
            labels.append(str(cells[0].get("text") or ""))
            values.append(str(cells[1].get("text") or ""))
    header = table.get("header") or ()
    header_values = [cell.get("text") for cell in header[:2]] if header else ["Metric", "Value"]
    return {
        "type": "table",
        "name": "Summary",
        "domain": {"x": [0.76, 1.0], "y": [0.0, 1.0]},
        "header": {
            "values": header_values,
            "fill": {"color": "#f3f4f6"},
            "align": ["left", "right"],
        },
        "cells": {
            "values": [labels, values],
            "fill": {"color": "#ffffff"},
            "align": ["left", "right"],
        },
        "meta": {"kind": "summary_table", "row_count": len(labels)},
    }
