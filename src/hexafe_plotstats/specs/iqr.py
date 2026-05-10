from __future__ import annotations

from ..models.payloads import IQRPayload
from .histogram import _finite_tuple, _format_number, _is_finite_number, _padded_range, _positive_dimension, _ticks
from .primitives import AxisSpec, BoxPlotSpec, Canvas, LineSpec, MarkerSpec, Rect, ResolvedIQRSpec, Size, TextSpec


def iqr_payload_to_resolved_spec(
    payload: IQRPayload,
    *,
    width: float = 760,
    height: float = 480,
) -> ResolvedIQRSpec:
    canvas = Canvas(size=Size(width=_positive_dimension(width), height=_positive_dimension(height)))
    plot_rect = _plot_rect(canvas.size.width, canvas.size.height)
    boxes = _box_specs(payload)
    markers = _outlier_markers(boxes)
    y_min, y_max = _y_range(payload, boxes)

    axes = (
        AxisSpec(
            orientation="x",
            label="group",
            minimum=0.5,
            maximum=max(len(boxes) + 0.5, 1.5),
            tick_values=tuple(box.position for box in boxes),
            tick_labels=tuple(box.label for box in boxes),
            scale="categorical",
        ),
        AxisSpec(
            orientation="y",
            label="value",
            minimum=y_min,
            maximum=y_max,
            tick_values=_ticks(y_min, y_max),
            tick_labels=tuple(_format_number(value) for value in _ticks(y_min, y_max)),
        ),
    )

    return ResolvedIQRSpec(
        chart_type="iqr",
        canvas=canvas,
        title=TextSpec(text="IQR", x=36.0, y=28.0, font_size=18.0, weight="600", role="title"),
        plot_rect=plot_rect,
        axes=axes,
        boxes=boxes,
        outlier_markers=markers,
        spec_lines=_spec_lines(payload, y_min, y_max),
        metadata={
            "group_count": len(boxes),
            "spec_limits": _spec_limit_metadata(payload),
            "payload_metadata": dict(payload.metadata),
        },
    )


def _plot_rect(width: float, height: float) -> Rect:
    return Rect(x=72.0, y=62.0, width=max(width - 104.0, 48.0), height=max(height - 118.0, 48.0))


def _box_specs(payload: IQRPayload) -> tuple[BoxPlotSpec, ...]:
    boxes: list[BoxPlotSpec] = []
    whis = float(payload.metadata.get("whis", 1.5))
    for index, group in enumerate(payload.groups, start=1):
        values = _finite_tuple(group.values)
        lower_whisker = group.summary.minimum
        upper_whisker = group.summary.maximum
        if group.summary.q1 is not None and group.summary.q3 is not None and values:
            iqr = group.summary.q3 - group.summary.q1
            lower_bound = group.summary.q1 - whis * iqr
            upper_bound = group.summary.q3 + whis * iqr
            whisker_values = tuple(value for value in values if lower_bound <= value <= upper_bound)
            if whisker_values:
                lower_whisker = min(whisker_values)
                upper_whisker = max(whisker_values)
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
                metadata={"count": group.summary.count, "index": index - 1},
            )
        )
    return tuple(boxes)


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


def _y_range(payload: IQRPayload, boxes: tuple[BoxPlotSpec, ...]) -> tuple[float, float]:
    values: list[float] = []
    for box in boxes:
        for value in (box.lower_whisker, box.q1, box.median, box.q3, box.upper_whisker, *box.outliers):
            if _is_finite_number(value):
                values.append(float(value))

    if payload.spec_limits is not None:
        for value in (payload.spec_limits.lsl, payload.spec_limits.nominal, payload.spec_limits.usl):
            if _is_finite_number(value):
                values.append(float(value))

    return _padded_range(values, default=(0.0, 1.0), pad_ratio=0.08)


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
