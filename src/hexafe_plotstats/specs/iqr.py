from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from ..models.payloads import IQRPayload
from ..themes import theme_from_metadata
from .histogram import _finite_tuple, _format_number, _is_finite_number, _padded_range, _positive_dimension, _tick_count, _ticks
from .primitives import AxisSpec, BoxPlotSpec, Canvas, LineSpec, MarkerSpec, Rect, ResolvedIQRSpec, Size, TextSpec


def iqr_payload_to_resolved_spec(
    payload: IQRPayload,
    *,
    width: float = 760,
    height: float = 480,
) -> ResolvedIQRSpec:
    theme = theme_from_metadata(payload.metadata)
    colors = dict(theme.get("colors") or {})
    canvas = Canvas(
        size=Size(width=_positive_dimension(width), height=_positive_dimension(height)),
        background=str(colors.get("background") or "#ffffff"),
    )
    plot_rect = _plot_rect(canvas.size.width, canvas.size.height)
    boxes = _box_specs(payload)
    outlier_markers = _outlier_markers(boxes)
    annotation_markers = _annotation_markers(
        boxes,
        show_mean=bool(payload.metadata.get("show_mean", True)),
        show_extrema=bool(payload.metadata.get("show_extrema", True)),
    )
    sigma_lines = _sigma_lines(payload, boxes)
    y_min, y_max = _y_range(payload, boxes, annotation_markers, sigma_lines)
    axis_labels = _axis_labels(payload)

    ticks_count = _tick_count(payload.metadata, sample_count=sum(int(box.metadata.get("count") or 0) for box in boxes))
    y_ticks = _ticks(y_min, y_max, ticks_count)
    axes = (
        AxisSpec(
            orientation="x",
            label=axis_labels["x"],
            minimum=0.5,
            maximum=max(len(boxes) + 0.5, 1.5),
            tick_values=tuple(box.position for box in boxes),
            tick_labels=tuple(box.label for box in boxes),
            scale="categorical",
            metadata={"ticks_count": len(boxes)},
        ),
        AxisSpec(
            orientation="y",
            label=axis_labels["y"],
            minimum=y_min,
            maximum=y_max,
            tick_values=y_ticks,
            tick_labels=tuple(_format_number(value) for value in y_ticks),
            metadata={"ticks_count": ticks_count},
        ),
    )

    return ResolvedIQRSpec(
        chart_type="iqr",
        canvas=canvas,
        title=TextSpec(
            text=str(payload.metadata.get("title") or "IQR"),
            x=36.0,
            y=28.0,
            font_size=18.0,
            fill=str(colors.get("text") or "#111827"),
            weight="600",
            role="title",
        ),
        plot_rect=plot_rect,
        axes=axes,
        boxes=boxes,
        outlier_markers=outlier_markers,
        annotation_markers=annotation_markers,
        spec_lines=_spec_lines(payload, y_min, y_max) + sigma_lines,
        metadata={
            "group_count": len(boxes),
            "spec_limits": _spec_limit_metadata(payload),
            "payload_metadata": dict(payload.metadata),
            "axis_labels": axis_labels,
            "theme": theme,
        },
    )


def _plot_rect(width: float, height: float) -> Rect:
    return Rect(x=72.0, y=62.0, width=max(width - 104.0, 48.0), height=max(height - 118.0, 48.0))


def _box_specs(payload: IQRPayload) -> tuple[BoxPlotSpec, ...]:
    boxes: list[BoxPlotSpec] = []
    whis = float(payload.metadata.get("whis", 1.5))
    for index, group in enumerate(payload.groups, start=1):
        values = _finite_array(group.values)
        lower_whisker = group.summary.minimum
        upper_whisker = group.summary.maximum
        if group.summary.q1 is not None and group.summary.q3 is not None and values.size:
            iqr = group.summary.q3 - group.summary.q1
            lower_bound = group.summary.q1 - whis * iqr
            upper_bound = group.summary.q3 + whis * iqr
            whisker_values = values[(values >= lower_bound) & (values <= upper_bound)]
            if whisker_values.size:
                lower_whisker = float(np.min(whisker_values))
                upper_whisker = float(np.max(whisker_values))
        boxes.append(
            BoxPlotSpec(
                label=str(group.label),
                position=float(index),
                lower_whisker=lower_whisker,
                q1=group.summary.q1,
                median=group.summary.median,
                q3=group.summary.q3,
                upper_whisker=upper_whisker,
                outliers=_finite_tuple(group.outliers),
                metadata={
                    "count": group.summary.count,
                    "index": index - 1,
                    "mean": group.summary.mean,
                    "std": group.summary.std,
                    "minimum": group.summary.minimum,
                    "maximum": group.summary.maximum,
                    "iqr": group.summary.iqr,
                    "outlier_count": len(group.outliers),
                },
            )
        )
    return tuple(boxes)


def _finite_array(values: Iterable[Any]) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        array = np.asarray(list(values), dtype=float).reshape(-1)
    return array[np.isfinite(array)]


def _outlier_markers(boxes: tuple[BoxPlotSpec, ...]) -> tuple[MarkerSpec, ...]:
    markers: list[MarkerSpec] = []
    for box in boxes:
        for value in box.outliers:
            markers.append(
                MarkerSpec(
                    x=box.position,
                    y=value,
                    label=f"{box.label} outlier",
                    kind="outlier",
                    fill="#ffffff",
                    stroke="#dc2626",
                    size=4.5,
                    opacity=1.0,
                    metadata={"group": box.label},
                )
            )
    return tuple(markers)


def _annotation_markers(
    boxes: tuple[BoxPlotSpec, ...],
    *,
    show_mean: bool,
    show_extrema: bool,
) -> tuple[MarkerSpec, ...]:
    markers: list[MarkerSpec] = []
    for box in boxes:
        annotations: list[tuple[str, Any, str, float]] = []
        if show_mean:
            annotations.append(("mean", box.metadata.get("mean"), "#111827", 5.0))
        if show_extrema:
            annotations.extend(
                (
                    ("minimum", box.metadata.get("minimum"), "#6b7280", 4.0),
                    ("maximum", box.metadata.get("maximum"), "#6b7280", 4.0),
                )
            )
        for kind, value, fill, size in annotations:
            if not _is_finite_number(value):
                continue
            markers.append(
                MarkerSpec(
                    x=box.position,
                    y=float(value),
                    label=f"{box.label} {kind}",
                    kind=kind,
                    fill=fill,
                    stroke=fill,
                    size=size,
                    opacity=1.0,
                    metadata={"group": box.label},
                )
            )
    return tuple(markers)


def _y_range(
    payload: IQRPayload,
    boxes: tuple[BoxPlotSpec, ...],
    annotation_markers: tuple[MarkerSpec, ...],
    sigma_lines: tuple[LineSpec, ...],
) -> tuple[float, float]:
    values: list[float] = []
    for box in boxes:
        for value in (box.lower_whisker, box.q1, box.median, box.q3, box.upper_whisker, *box.outliers):
            if _is_finite_number(value):
                values.append(float(value))
        for value in (box.metadata.get("mean"), box.metadata.get("minimum"), box.metadata.get("maximum")):
            if _is_finite_number(value):
                values.append(float(value))
    for marker in annotation_markers:
        values.append(marker.y)
    for line in sigma_lines:
        values.extend((line.y0, line.y1))

    if payload.spec_limits is not None:
        for value in (payload.spec_limits.lsl, payload.spec_limits.nominal, payload.spec_limits.usl):
            if _is_finite_number(value):
                values.append(float(value))

    return _padded_range(values, default=(0.0, 1.0), pad_ratio=0.08)


def _sigma_lines(payload: IQRPayload, boxes: tuple[BoxPlotSpec, ...]) -> tuple[LineSpec, ...]:
    policy = str(payload.metadata.get("sigma_policy") or "none")
    if policy not in {"plus_3_sigma", "both_3_sigma"}:
        return ()

    lines: list[LineSpec] = []
    for box in boxes:
        mean = box.metadata.get("mean")
        std = box.metadata.get("std")
        if not (_is_finite_number(mean) and _is_finite_number(std)) or float(std) <= 0.0:
            continue
        mean_value = float(mean)
        sigma = 3.0 * float(std)
        candidates: tuple[tuple[str, float, str], ...]
        if policy == "both_3_sigma":
            candidates = (
                ("sigma_lower", mean_value - sigma, "-3 sigma"),
                ("sigma_upper", mean_value + sigma, "+3 sigma"),
            )
        else:
            candidates = (("sigma_upper", mean_value + sigma, "+3 sigma"),)
        for kind, y_value, label in candidates:
            lines.append(
                LineSpec(
                    x0=box.position - 0.22,
                    y0=y_value,
                    x1=box.position + 0.22,
                    y1=y_value,
                    label=label,
                    kind=kind,
                    stroke="#7c3aed",
                    stroke_width=0.9,
                    dash=(2.0, 2.0),
                    metadata={"group": box.label, "policy": policy},
                )
            )
    return tuple(lines)


def _spec_lines(payload: IQRPayload, y_min: float, y_max: float) -> tuple[LineSpec, ...]:
    if payload.spec_limits is None:
        return ()

    lines: list[LineSpec] = []
    x_min = 0.5
    x_max = max(len(payload.groups) + 0.5, 1.5)
    specs = (
        ("lsl", payload.spec_limits.lsl, "#dc2626", "LSL", (6.0, 4.0)),
        ("nominal", payload.spec_limits.nominal, "#16a34a", "Nominal", (2.0, 3.0)),
        ("usl", payload.spec_limits.usl, "#dc2626", "USL", (6.0, 4.0)),
    )
    for kind, value, stroke, label, dash in specs:
        if not _is_finite_number(value):
            continue
        y = min(max(float(value), y_min), y_max)
        lines.append(
            LineSpec(
                x0=x_min,
                y0=y,
                x1=x_max,
                y1=y,
                label=label,
                kind=f"spec_{kind}",
                stroke=stroke,
                dash=dash,
            )
        )
    return tuple(lines)


def _spec_limit_metadata(payload: IQRPayload) -> dict[str, float | None]:
    if payload.spec_limits is None:
        return {"lsl": None, "nominal": None, "usl": None}
    return {
        "lsl": payload.spec_limits.lsl,
        "nominal": payload.spec_limits.nominal,
        "usl": payload.spec_limits.usl,
    }


def _axis_labels(payload: IQRPayload) -> dict[str, str]:
    axis_labels = payload.metadata.get("axis_labels")
    if isinstance(axis_labels, dict):
        return {
            "x": str(axis_labels.get("x") or "Groups"),
            "y": str(axis_labels.get("y") or "Measurement"),
        }
    return {
        "x": str(payload.metadata.get("x_label") or "Groups"),
        "y": str(payload.metadata.get("y_label") or "Measurement"),
    }
