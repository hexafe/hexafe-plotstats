from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from ..models.payloads import HistogramPayload
from .primitives import (
    AxisSpec,
    BarSpec,
    Canvas,
    CurveSpec,
    LineSpec,
    Rect,
    ResolvedHistogramSpec,
    Size,
    TableCell,
    TableRow,
    TableSpec,
    TextSpec,
)


def histogram_payload_to_resolved_spec(
    payload: HistogramPayload,
    *,
    width: float = 900,
    height: float = 520,
) -> ResolvedHistogramSpec:
    canvas = Canvas(size=Size(width=_positive_dimension(width), height=_positive_dimension(height)))
    plot_rect, table_rect = _histogram_layout(canvas.size.width, canvas.size.height)

    bars = _bar_specs(payload)
    fit_curve = _curve_spec(payload.fit.curve, kind="fit", stroke="#f97316", width=1.5) if payload.fit and payload.fit.curve else None
    kde_curve = (
        _curve_spec(payload.fit.kde_reference, kind="kde", stroke="#6b7280", width=1.0, dash=(4.0, 3.0))
        if payload.fit and payload.fit.kde_reference
        else None
    )
    curves = tuple(curve for curve in (fit_curve, kde_curve) if curve is not None)

    x_min, x_max = _x_range(payload, bars, curves)
    y_min, y_max = _y_range(bars, curves)
    axis_labels = _axis_labels(payload)

    axes = (
        AxisSpec(
            orientation="x",
            label=axis_labels["x"],
            minimum=x_min,
            maximum=x_max,
            tick_values=_ticks(x_min, x_max),
            tick_labels=tuple(_format_number(value) for value in _ticks(x_min, x_max)),
        ),
        AxisSpec(
            orientation="y",
            label=axis_labels["y"],
            minimum=y_min,
            maximum=y_max,
            tick_values=_ticks(y_min, y_max),
            tick_labels=tuple(_format_number(value) for value in _ticks(y_min, y_max)),
        ),
    )

    spec_lines = _spec_lines(payload, y_max)
    mean_line = _mean_line(payload, y_max)
    annotations = _annotations(payload)
    table = _table_spec(payload, table_rect)

    return ResolvedHistogramSpec(
        chart_type="histogram",
        canvas=canvas,
        title=TextSpec(
            text=str(payload.metadata.get("title") or "Histogram"),
            x=36.0,
            y=28.0,
            font_size=18.0,
            weight="600",
            role="title",
        ),
        plot_rect=plot_rect,
        table_rect=table_rect,
        axes=axes,
        bars=bars,
        curves=curves,
        spec_lines=spec_lines,
        mean_line=mean_line,
        annotations=annotations,
        table=table,
        warnings=_warnings(payload),
        metadata={**_metadata(payload), "axis_labels": axis_labels},
    )


def _histogram_layout(width: float, height: float) -> tuple[Rect, Rect]:
    if width >= 720.0:
        table_width = min(max(width * 0.27, 190.0), 260.0)
        left = 72.0
        top = 64.0
        gap = 24.0
        right = 32.0
        bottom = 56.0
        plot_width = max(width - left - gap - table_width - right, 48.0)
        plot_height = max(height - top - bottom, 48.0)
        plot_rect = Rect(x=left, y=top, width=plot_width, height=plot_height)
        table_rect = Rect(x=left + plot_width + gap, y=top, width=table_width, height=plot_height)
        return plot_rect, table_rect

    left = 56.0
    top = 58.0
    right = 32.0
    bottom = 36.0
    gap = 16.0
    table_height = min(max(height * 0.28, 96.0), 142.0)
    plot_width = max(width - left - right, 48.0)
    plot_height = max(height - top - gap - table_height - bottom, 48.0)
    plot_rect = Rect(x=left, y=top, width=plot_width, height=plot_height)
    table_rect = Rect(x=left, y=top + plot_height + gap, width=plot_width, height=table_height)
    return plot_rect, table_rect


def _bar_specs(payload: HistogramPayload) -> tuple[BarSpec, ...]:
    edges = _finite_tuple(payload.bin_edges)
    heights = _finite_tuple(payload.bin_values)
    if len(edges) < 2 or not heights:
        return ()

    bars: list[BarSpec] = []
    for index, height in enumerate(heights[: len(edges) - 1]):
        x0 = edges[index]
        x1 = edges[index + 1]
        if x0 == x1:
            continue
        bars.append(
            BarSpec(
                x0=x0,
                x1=x1,
                y0=0.0,
                y1=max(0.0, height),
                label=f"bin {index + 1}",
                metadata={"index": index},
            )
        )
    return tuple(bars)


def _curve_spec(curve: Any, *, kind: str, stroke: str, width: float, dash: tuple[float, ...] = ()) -> CurveSpec:
    points = tuple(
        (x, y)
        for x, y in zip(_finite_tuple(curve.x), _finite_tuple(curve.y), strict=False)
        if math.isfinite(x) and math.isfinite(y)
    )
    x_values = tuple(point[0] for point in points)
    y_values = tuple(point[1] for point in points)
    return CurveSpec(
        x=x_values,
        y=y_values,
        label=str(curve.label),
        kind=kind,
        stroke=stroke,
        stroke_width=width,
        dash=dash,
        metadata=dict(getattr(curve, "metadata", {}) or {}),
    )


def _x_range(payload: HistogramPayload, bars: tuple[BarSpec, ...], curves: tuple[CurveSpec, ...]) -> tuple[float, float]:
    x_view = payload.metadata.get("x_view")
    if isinstance(x_view, dict):
        minimum = x_view.get("min")
        maximum = x_view.get("max")
        if _is_finite_number(minimum) and _is_finite_number(maximum) and float(minimum) != float(maximum):
            return float(minimum), float(maximum)

    values: list[float] = []
    values.extend(value for bar in bars for value in (bar.x0, bar.x1))
    for curve in curves:
        values.extend(curve.x)

    spec_limits = payload.spec_limits
    for value in (spec_limits.lsl, spec_limits.nominal, spec_limits.usl, payload.summary.mean):
        if _is_finite_number(value):
            values.append(float(value))

    return _padded_range(values, default=(0.0, 1.0), pad_ratio=0.04)


def _y_range(bars: tuple[BarSpec, ...], curves: tuple[CurveSpec, ...]) -> tuple[float, float]:
    values: list[float] = [0.0]
    values.extend(bar.y1 for bar in bars)
    for curve in curves:
        values.extend(max(0.0, value) for value in curve.y)

    _, maximum = _padded_range(values, default=(0.0, 1.0), pad_ratio=0.12)
    return 0.0, maximum


def _spec_lines(payload: HistogramPayload, y_max: float) -> tuple[LineSpec, ...]:
    custom_lines = payload.metadata.get("specification_lines")
    if isinstance(custom_lines, (list, tuple)):
        lines = tuple(_custom_spec_line(item, y_max) for item in custom_lines if isinstance(item, dict))
        return tuple(line for line in lines if line is not None)

    lines: list[LineSpec] = []
    specs = (
        ("lsl", payload.spec_limits.lsl, "#dc2626", "LSL", (6.0, 4.0)),
        ("nominal", payload.spec_limits.nominal, "#16a34a", "Nominal", (2.0, 3.0)),
        ("usl", payload.spec_limits.usl, "#dc2626", "USL", (6.0, 4.0)),
    )
    for kind, value, stroke, label, dash in specs:
        if not _is_finite_number(value):
            continue
        x = float(value)
        lines.append(
            LineSpec(
                x0=x,
                y0=0.0,
                x1=x,
                y1=y_max,
                label=label,
                kind=f"spec_{kind}",
                stroke=stroke,
                stroke_width=1.0,
                dash=dash,
            )
        )
    return tuple(lines)


def _custom_spec_line(raw: dict[str, Any], y_max: float) -> LineSpec | None:
    if raw.get("enabled") is False:
        return None
    value = raw.get("value")
    if not _is_finite_number(value):
        return None
    role = str(raw.get("id") or raw.get("role") or raw.get("kind") or "spec")
    label = str(raw.get("label") or role.upper())
    style = raw.get("style_hint") if isinstance(raw.get("style_hint"), dict) else {}
    dash = raw.get("dash") if isinstance(raw.get("dash"), (list, tuple)) else ()
    return LineSpec(
        x0=float(value),
        y0=0.0,
        x1=float(value),
        y1=y_max,
        label=label,
        kind=f"spec_{role}",
        stroke=str(raw.get("color") or style.get("color") or "#dc2626"),
        stroke_width=float(raw.get("width") or style.get("linewidth") or 1.0),
        dash=tuple(float(item) for item in dash),
        metadata={"source": "metadata", "raw": dict(raw)},
    )


def _mean_line(payload: HistogramPayload, y_max: float) -> LineSpec | None:
    mean_meta = payload.metadata.get("mean_line") if isinstance(payload.metadata.get("mean_line"), dict) else {}
    value = mean_meta.get("value", payload.summary.mean)
    if not _is_finite_number(value):
        return None

    mean = float(value)
    dash = mean_meta.get("dash") if isinstance(mean_meta.get("dash"), (list, tuple)) else (4.0, 2.0)
    return LineSpec(
        x0=mean,
        y0=0.0,
        x1=mean,
        y1=y_max,
        label=str(mean_meta.get("label") or "Mean"),
        kind="mean",
        stroke=str(mean_meta.get("color") or "#111827"),
        stroke_width=float(mean_meta.get("linewidth") or mean_meta.get("stroke_width") or 1.0),
        dash=tuple(float(item) for item in dash),
        metadata={"source": "metadata" if mean_meta else "summary"},
    )


def _table_spec(payload: HistogramPayload, rect: Rect) -> TableSpec:
    table_title = str(payload.metadata.get("table_title") or payload.metadata.get("summary_table_title") or "Metric")
    rows = tuple(
        TableRow(
            cells=(
                TableCell(text=str(row.label), kind="label", align="left"),
                TableCell(text=str(row.value), kind="value", align="right"),
            ),
            kind=row.kind,
            metadata=dict(row.metadata),
        )
        for row in payload.table_rows
    ) + _modeled_overlay_table_rows(payload)
    return TableSpec(
        rect=rect,
        rows=rows,
        column_widths=(0.58, 0.42),
        header=(
            TableCell(text=table_title, kind="header", align="left"),
            TableCell(text="Value", kind="header", align="right"),
        ),
    )


def _modeled_overlay_table_rows(payload: HistogramPayload) -> tuple[TableRow, ...]:
    raw_rows = payload.metadata.get("modeled_overlay_rows")
    if not isinstance(raw_rows, (list, tuple)):
        return ()

    rows: list[TableRow] = []
    for index, raw in enumerate(raw_rows):
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or raw.get("text") or raw.get("kind") or "").strip()
        if not label:
            continue
        value = str(raw.get("value") or raw.get("note") or "")
        rows.append(
            TableRow(
                cells=(
                    TableCell(text=label, kind="label", align="left"),
                    TableCell(text=value, kind="value", align="right"),
                ),
                kind=str(raw.get("kind") or "modeled_overlay"),
                metadata={
                    "section_break_before": bool(raw.get("section_break_before", index == 0)),
                    "source": "modeled_overlay_rows",
                    "raw": dict(raw),
                },
            )
        )
    return tuple(rows)


def _annotations(payload: HistogramPayload) -> tuple[TextSpec, ...]:
    raw_annotations = payload.metadata.get("annotation_rows")
    if not isinstance(raw_annotations, (list, tuple)):
        return ()

    annotations: list[TextSpec] = []
    for index, raw in enumerate(raw_annotations):
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or raw.get("label") or "").strip()
        x_value = raw.get("x")
        if not text or not _is_finite_number(x_value):
            continue
        row_index = int(raw.get("row_index") or index)
        annotations.append(
            TextSpec(
                text=text,
                x=float(x_value),
                y=float(raw.get("text_y_axes") or (1.01 + (row_index * 0.045))),
                font_size=float(raw.get("font_size") or 9.0),
                fill=str(raw.get("color") or "#111827"),
                align=str((raw.get("placement_hint") or {}).get("ha") or "center")
                if isinstance(raw.get("placement_hint"), dict)
                else "center",
                baseline="bottom",
                role=str(raw.get("kind") or "histogram_annotation"),
                metadata={"coordinate_space": {"x": "data", "y": "axes"}, "row_index": row_index, "raw": dict(raw)},
            )
        )
    return tuple(annotations)


def _axis_labels(payload: HistogramPayload) -> dict[str, str]:
    axis_labels = payload.metadata.get("axis_labels")
    if isinstance(axis_labels, dict):
        return {
            "x": str(axis_labels.get("x") or "value"),
            "y": str(axis_labels.get("y") or ("density" if payload.density else "count")),
        }
    return {
        "x": str(payload.metadata.get("x_label") or "value"),
        "y": str(payload.metadata.get("y_label") or ("density" if payload.density else "count")),
    }


def _metadata(payload: HistogramPayload) -> dict[str, Any]:
    fit = payload.fit
    fit_metadata: dict[str, Any] | None = None
    if fit is not None:
        tail_risk = fit.tail_risk
        fit_metadata = {
            "selected": fit.selected,
            "quality": fit.quality,
            "params": dict(fit.params),
            "log_likelihood": fit.log_likelihood,
            "aic": fit.aic,
            "bic": fit.bic,
            "gof_statistic": fit.gof_statistic,
            "gof_p_value": fit.gof_p_value,
            "tail_risk": None
            if tail_risk is None
            else {
                "below_lsl_probability": tail_risk.below_lsl_probability,
                "above_usl_probability": tail_risk.above_usl_probability,
                "total_probability": tail_risk.total_probability,
                "ppm": tail_risk.ppm,
            },
            "candidates_ranked": fit.candidates_ranked,
        }

    normality_metadata: dict[str, Any] | None = None
    if payload.normality is not None:
        normality_metadata = {
            "method": payload.normality.method,
            "statistic": payload.normality.statistic,
            "p_value": payload.normality.p_value,
            "is_normal": payload.normality.is_normal,
            "warnings": payload.normality.warnings,
        }

    return {
        "density": payload.density,
        "value_count": len(payload.values),
        "bin_count": max(len(payload.bin_edges) - 1, 0),
        "summary": {
            "count": payload.summary.count,
            "mean": payload.summary.mean,
            "std": payload.summary.std,
            "minimum": payload.summary.minimum,
            "maximum": payload.summary.maximum,
            "median": payload.summary.median,
            "q1": payload.summary.q1,
            "q3": payload.summary.q3,
            "iqr": payload.summary.iqr,
            "nok_count": payload.summary.nok_count,
            "nok_rate": payload.summary.nok_rate,
            "nok_ppm": payload.summary.nok_ppm,
        },
        "capability": {
            "cp": payload.capability.cp,
            "cpk": payload.capability.cpk,
            "cpl": payload.capability.cpl,
            "cpu": payload.capability.cpu,
            "sample_std": payload.capability.sample_std,
        },
        "normality": normality_metadata,
        "spec_limits": {
            "lsl": payload.spec_limits.lsl,
            "nominal": payload.spec_limits.nominal,
            "usl": payload.spec_limits.usl,
        },
        "fit": fit_metadata,
        "payload_metadata": dict(payload.metadata),
    }


def _warnings(payload: HistogramPayload) -> tuple[str, ...]:
    warnings: list[str] = []
    warnings.extend(str(warning) for warning in payload.warnings)
    if payload.fit is not None:
        warnings.extend(str(warning) for warning in payload.fit.warnings)

    deduped: list[str] = []
    for warning in warnings:
        if warning not in deduped:
            deduped.append(warning)
    return tuple(deduped)


def _positive_dimension(value: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 1.0
    return number if math.isfinite(number) and number > 0.0 else 1.0


def _finite_tuple(values: Iterable[Any]) -> tuple[float, ...]:
    finite: list[float] = []
    for value in values:
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if math.isfinite(number):
            finite.append(number)
    return tuple(finite)


def _is_finite_number(value: Any) -> bool:
    try:
        return value is not None and math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def _padded_range(values: Iterable[float], *, default: tuple[float, float], pad_ratio: float) -> tuple[float, float]:
    finite = _finite_tuple(values)
    if not finite:
        return default

    minimum = min(finite)
    maximum = max(finite)
    if minimum == maximum:
        pad = max(abs(minimum) * 0.1, 0.5)
        return minimum - pad, maximum + pad

    pad = (maximum - minimum) * pad_ratio
    return minimum - pad, maximum + pad


def _ticks(minimum: float, maximum: float, count: int = 6) -> tuple[float, ...]:
    if count <= 1 or minimum == maximum:
        return (minimum,)

    step = (maximum - minimum) / float(count - 1)
    return tuple(round(minimum + step * index, 12) for index in range(count))


def _format_number(value: float) -> str:
    if value == 0.0:
        return "0"
    magnitude = abs(value)
    if magnitude >= 10_000 or magnitude < 0.001:
        return f"{value:.3g}"
    return f"{value:.6g}"
