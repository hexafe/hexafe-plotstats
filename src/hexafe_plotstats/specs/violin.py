from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
from scipy import stats

from ..models.payloads import ViolinPayload
from ..themes import theme_from_metadata
from .histogram import _format_number, _is_finite_number, _padded_range, _positive_dimension, _tick_count, _ticks
from .primitives import AxisSpec, Canvas, LineSpec, MarkerSpec, Rect, ResolvedViolinSpec, Size, TextSpec, ViolinGroupSpec


_EXACT_KDE_LIMIT = 50_000
_HISTOGRAM_DENSITY_BINS = 512


def violin_payload_to_resolved_spec(
    payload: ViolinPayload,
    *,
    width: float = 760,
    height: float = 480,
) -> ResolvedViolinSpec:
    theme = theme_from_metadata(payload.metadata)
    colors = dict(theme.get("colors") or {})
    canvas = Canvas(
        size=Size(width=_positive_dimension(width), height=_positive_dimension(height)),
        background=str(colors.get("background") or "#ffffff"),
    )
    plot_rect = Rect(x=72.0, y=62.0, width=max(canvas.size.width - 104.0, 48.0), height=max(canvas.size.height - 118.0, 48.0))
    groups = _group_specs(payload)
    markers = _annotation_markers(groups, show_extrema=bool(payload.metadata.get("show_extrema")))
    sigma_lines = _sigma_lines(payload, groups)
    y_min, y_max = _y_range(payload, groups, sigma_lines)

    ticks_count = _tick_count(payload.metadata, sample_count=sum(int(group.metadata.get("count") or 0) for group in groups))
    y_ticks = _ticks(y_min, y_max, ticks_count)
    axes = (
        AxisSpec(
            orientation="x",
            label="group",
            minimum=0.5,
            maximum=max(len(groups) + 0.5, 1.5),
            tick_values=tuple(group.position for group in groups),
            tick_labels=tuple(group.label for group in groups),
            scale="categorical",
            metadata={"ticks_count": len(groups)},
        ),
        AxisSpec(
            orientation="y",
            label="value",
            minimum=y_min,
            maximum=y_max,
            tick_values=y_ticks,
            tick_labels=tuple(_format_number(value) for value in y_ticks),
            metadata={"ticks_count": ticks_count},
        ),
    )

    return ResolvedViolinSpec(
        chart_type="violin",
        canvas=canvas,
        title=TextSpec(text="Violin", x=36.0, y=28.0, font_size=18.0, fill=str(colors.get("text") or "#111827"), weight="600", role="title"),
        plot_rect=plot_rect,
        axes=axes,
        groups=groups,
        annotation_markers=markers,
        spec_lines=_spec_lines(payload, y_min, y_max) + sigma_lines,
        metadata={
            "group_count": len(groups),
            "spec_limits": _spec_limit_metadata(payload),
            "payload_metadata": dict(payload.metadata),
            "theme": theme,
        },
    )


def _group_specs(payload: ViolinPayload) -> tuple[ViolinGroupSpec, ...]:
    groups: list[ViolinGroupSpec] = []
    for index, group in enumerate(payload.groups, start=1):
        values = _finite_array(group.values)
        body_points, body_metadata = _body_points(values, float(index))
        groups.append(
            ViolinGroupSpec(
                label=str(group.label),
                position=float(index),
                values=(),
                mean=group.summary.mean,
                q1=group.summary.q1,
                median=group.summary.median,
                q3=group.summary.q3,
                minimum=group.summary.minimum,
                maximum=group.summary.maximum,
                body_points=body_points,
                metadata={
                    "count": group.summary.count,
                    "index": index - 1,
                    "annotations": dict(group.annotations),
                    "raw_values_omitted": True,
                    **body_metadata,
                },
            )
        )
    return tuple(groups)


def _body_points(
    values: np.ndarray,
    position: float,
    *,
    width: float = 0.5,
    points: int = 100,
) -> tuple[tuple[tuple[float, float], ...], dict[str, Any]]:
    cleaned = values[np.isfinite(values)]
    if cleaned.size == 0:
        return (), {"density_method": "empty", "source_count": 0}

    minimum = float(np.min(cleaned))
    maximum = float(np.max(cleaned))
    coords = np.linspace(minimum, maximum, max(int(points), 2))
    if bool(np.all(cleaned[0] == cleaned)):
        densities = (cleaned[0] == coords).astype(float)
        method = "constant"
    else:
        densities, method = _density_values(cleaned, coords)

    densities = np.where(np.isfinite(densities), densities, 0.0)
    max_density = float(np.max(densities)) if densities.size else 0.0
    if max_density <= 0.0:
        return (), {"density_method": method, "source_count": int(cleaned.size)}

    scaled = 0.5 * width * densities / max_density
    left = tuple((float(position - offset), float(coord)) for offset, coord in zip(scaled, coords, strict=False))
    right = tuple((float(position + offset), float(coord)) for offset, coord in zip(reversed(scaled), reversed(coords), strict=False))
    return left + right, {"density_method": method, "source_count": int(cleaned.size)}


def _density_values(cleaned: np.ndarray, coords: np.ndarray) -> tuple[np.ndarray, str]:
    if cleaned.size > _EXACT_KDE_LIMIT:
        bins = min(_HISTOGRAM_DENSITY_BINS, max(64, int(np.sqrt(cleaned.size))))
        hist, edges = np.histogram(cleaned, bins=bins, range=(float(coords[0]), float(coords[-1])), density=True)
        centers = (edges[:-1] + edges[1:]) / 2.0
        if hist.size >= 5:
            kernel = np.asarray([1.0, 2.0, 3.0, 2.0, 1.0], dtype=float)
            hist = np.convolve(hist, kernel / np.sum(kernel), mode="same")
        return np.interp(coords, centers, hist, left=0.0, right=0.0), "histogram_density"

    try:
        return stats.gaussian_kde(cleaned)(coords), "gaussian_kde"
    except Exception:
        return np.zeros_like(coords), "density_failed"


def _finite_array(values: Iterable[Any]) -> np.ndarray:
    try:
        array = np.asarray(values, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        array = np.asarray(list(values), dtype=float).reshape(-1)
    return array[np.isfinite(array)]


def _annotation_markers(groups: tuple[ViolinGroupSpec, ...], *, show_extrema: bool = False) -> tuple[MarkerSpec, ...]:
    markers: list[MarkerSpec] = []
    for group in groups:
        annotations: tuple[tuple[str, float | None, str, float], ...] = (
            ("mean", group.mean, "#111827", 5.0),
            ("median", group.median, "#f97316", 4.5),
            ("q1", group.q1, "#f97316", 3.5),
            ("q3", group.q3, "#f97316", 3.5),
        )
        if show_extrema:
            annotations = annotations + (
                ("minimum", group.minimum, "#6b7280", 3.5),
                ("maximum", group.maximum, "#6b7280", 3.5),
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


def _y_range(payload: ViolinPayload, groups: tuple[ViolinGroupSpec, ...], sigma_lines: tuple[LineSpec, ...] = ()) -> tuple[float, float]:
    values: list[float] = []
    for group in groups:
        values.extend(group.values)
        for value in (group.mean, group.q1, group.median, group.q3, group.minimum, group.maximum):
            if _is_finite_number(value):
                values.append(float(value))
    for line in sigma_lines:
        values.extend((line.y0, line.y1))

    if payload.spec_limits is not None:
        for value in (payload.spec_limits.lsl, payload.spec_limits.nominal, payload.spec_limits.usl):
            if _is_finite_number(value):
                values.append(float(value))

    return _padded_range(values, default=(0.0, 1.0), pad_ratio=0.08)


def _sigma_lines(payload: ViolinPayload, groups: tuple[ViolinGroupSpec, ...]) -> tuple[LineSpec, ...]:
    policy = str(payload.metadata.get("sigma_policy") or "none")
    if policy not in {"plus_3_sigma", "both_3_sigma"}:
        return ()

    lines: list[LineSpec] = []
    for payload_group, group in zip(payload.groups, groups, strict=False):
        mean = payload_group.summary.mean
        std = payload_group.summary.std
        if not (_is_finite_number(mean) and _is_finite_number(std)) or float(std) <= 0.0:
            continue
        mean_value = float(mean)
        sigma = 3.0 * float(std)
        x0 = group.position - 0.22
        x1 = group.position + 0.22
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
                    x0=x0,
                    y0=y_value,
                    x1=x1,
                    y1=y_value,
                    label=label,
                    kind=kind,
                    stroke="#7c3aed",
                    stroke_width=0.9,
                    dash=(2.0, 2.0),
                    metadata={"group": group.label, "policy": policy},
                )
            )
    return tuple(lines)


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
