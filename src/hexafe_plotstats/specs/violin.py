from __future__ import annotations

import numpy as np
from scipy import stats

from ..models.payloads import ViolinPayload
from .histogram import _finite_tuple, _format_number, _is_finite_number, _padded_range, _positive_dimension, _ticks
from .primitives import AxisSpec, Canvas, LineSpec, MarkerSpec, Rect, ResolvedViolinSpec, Size, TextSpec, ViolinGroupSpec


def violin_payload_to_resolved_spec(
    payload: ViolinPayload,
    *,
    width: float = 760,
    height: float = 480,
) -> ResolvedViolinSpec:
    canvas = Canvas(size=Size(width=_positive_dimension(width), height=_positive_dimension(height)))
    plot_rect = Rect(x=72.0, y=62.0, width=max(canvas.size.width - 104.0, 48.0), height=max(canvas.size.height - 118.0, 48.0))
    groups = _group_specs(payload)
    markers = _annotation_markers(groups)
    y_min, y_max = _y_range(payload, groups)

    axes = (
        AxisSpec(
            orientation="x",
            label="group",
            minimum=0.5,
            maximum=max(len(groups) + 0.5, 1.5),
            tick_values=tuple(group.position for group in groups),
            tick_labels=tuple(group.label for group in groups),
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

    return ResolvedViolinSpec(
        chart_type="violin",
        canvas=canvas,
        title=TextSpec(text="Violin", x=36.0, y=28.0, font_size=18.0, weight="600", role="title"),
        plot_rect=plot_rect,
        axes=axes,
        groups=groups,
        annotation_markers=markers,
        spec_lines=_spec_lines(payload, y_min, y_max),
        metadata={
            "group_count": len(groups),
            "spec_limits": _spec_limit_metadata(payload),
            "payload_metadata": dict(payload.metadata),
        },
    )


def _group_specs(payload: ViolinPayload) -> tuple[ViolinGroupSpec, ...]:
    groups: list[ViolinGroupSpec] = []
    for index, group in enumerate(payload.groups, start=1):
        groups.append(
            ViolinGroupSpec(
                label=str(group.label),
                position=float(index),
                values=_finite_tuple(group.values),
                mean=group.summary.mean,
                q1=group.summary.q1,
                median=group.summary.median,
                q3=group.summary.q3,
                minimum=group.summary.minimum,
                maximum=group.summary.maximum,
                body_points=_body_points(_finite_tuple(group.values), float(index)),
                metadata={"count": group.summary.count, "index": index - 1, "annotations": dict(group.annotations)},
            )
        )
    return tuple(groups)


def _body_points(values: tuple[float, ...], position: float, *, width: float = 0.5, points: int = 100) -> tuple[tuple[float, float], ...]:
    cleaned = np.asarray(values, dtype=float)
    cleaned = cleaned[np.isfinite(cleaned)]
    if cleaned.size == 0:
        return ()

    minimum = float(np.min(cleaned))
    maximum = float(np.max(cleaned))
    coords = np.linspace(minimum, maximum, max(int(points), 2))
    if bool(np.all(cleaned[0] == cleaned)):
        densities = (cleaned[0] == coords).astype(float)
    else:
        try:
            densities = stats.gaussian_kde(cleaned)(coords)
        except Exception:
            return ()

    densities = np.where(np.isfinite(densities), densities, 0.0)
    max_density = float(np.max(densities)) if densities.size else 0.0
    if max_density <= 0.0:
        return ()

    scaled = 0.5 * width * densities / max_density
    left = tuple((float(position - offset), float(coord)) for offset, coord in zip(scaled, coords, strict=False))
    right = tuple((float(position + offset), float(coord)) for offset, coord in zip(reversed(scaled), reversed(coords), strict=False))
    return left + right


def _annotation_markers(groups: tuple[ViolinGroupSpec, ...]) -> tuple[MarkerSpec, ...]:
    markers: list[MarkerSpec] = []
    for group in groups:
        annotations = (
            ("mean", group.mean, "#111827", 5.0),
            ("median", group.median, "#f97316", 4.5),
            ("q1", group.q1, "#f97316", 3.5),
            ("q3", group.q3, "#f97316", 3.5),
        )
        for kind, value, fill, size in annotations:
            if not _is_finite_number(value):
                continue
            markers.append(
                MarkerSpec(
                    x=group.position,
                    y=float(value),
                    label=f"{group.label} {kind}",
                    kind=kind,
                    fill=fill,
                    stroke=fill,
                    size=size,
                    opacity=1.0,
                    metadata={"group": group.label},
                )
            )
    return tuple(markers)


def _y_range(payload: ViolinPayload, groups: tuple[ViolinGroupSpec, ...]) -> tuple[float, float]:
    values: list[float] = []
    for group in groups:
        values.extend(group.values)
        for value in (group.mean, group.q1, group.median, group.q3, group.minimum, group.maximum):
            if _is_finite_number(value):
                values.append(float(value))

    if payload.spec_limits is not None:
        for value in (payload.spec_limits.lsl, payload.spec_limits.nominal, payload.spec_limits.usl):
            if _is_finite_number(value):
                values.append(float(value))

    return _padded_range(values, default=(0.0, 1.0), pad_ratio=0.08)


def _spec_lines(payload: ViolinPayload, y_min: float, y_max: float) -> tuple[LineSpec, ...]:
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


def _spec_limit_metadata(payload: ViolinPayload) -> dict[str, float | None]:
    if payload.spec_limits is None:
        return {"lsl": None, "nominal": None, "usl": None}
    return {
        "lsl": payload.spec_limits.lsl,
        "nominal": payload.spec_limits.nominal,
        "usl": payload.spec_limits.usl,
    }
