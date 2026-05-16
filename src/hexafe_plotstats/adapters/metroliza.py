from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from typing import Any

from ._core import histogram_payload, summarize
from ..models.common import HistogramConfig, IQRConfig, SpecLimits
from ..models.payloads import HistogramPayload, TableRow
from ..payloads import build_histogram_payload, build_iqr_payload, build_violin_payload
from ..renderers.plotly import histogram_payload_to_plotly_spec, iqr_payload_to_plotly_spec, violin_payload_to_plotly_spec


def _values_from_object(obj: Any) -> tuple[float, ...]:
    for attribute in ("values", "data", "series"):
        if hasattr(obj, attribute):
            candidate = getattr(obj, attribute)
            try:
                return tuple(float(value) for value in candidate)
            except Exception:
                pass
    if hasattr(obj, "to_numpy"):
        try:
            return tuple(float(value) for value in obj.to_numpy().tolist())
        except Exception:
            pass
    if isinstance(obj, Iterable):
        return tuple(float(value) for value in obj)
    raise TypeError("could not extract numeric values from metroliza object")


def summarize_metroliza(obj: Any, spec_limits: SpecLimits | None = None):
    return summarize(_values_from_object(obj), spec_limits)


def histogram_from_metroliza(obj: Any, spec_limits: SpecLimits | None = None):
    return histogram_payload(_values_from_object(obj), spec_limits)


def histogram_from_metroliza_native_payload(payload: Mapping[str, Any]) -> HistogramPayload:
    """Build a reusable histogram payload from Metroliza's enriched native payload."""

    values = payload.get("values") or []
    limits = _spec_limits_from_payload(payload)
    bin_count = payload.get("bin_count")
    config = HistogramConfig(
        bins=max(1, int(bin_count)) if _is_positive_int_like(bin_count) else "auto",
        density=False,
        include_fit=False,
    )
    metadata = _histogram_metadata_from_native_payload(payload)
    hist = build_histogram_payload(values, limits, config=config, metadata=metadata)
    table_rows = _table_rows_from_payload(payload)
    if table_rows:
        hist = replace(hist, table_rows=table_rows)
    return hist


def plotly_spec_from_metroliza_dashboard_payload(
    payload: Mapping[str, Any],
    *,
    title: str = "",
    theme: str | Mapping[str, Any] | None = None,
    static: bool = True,
) -> dict[str, Any]:
    """Convert Metroliza dashboard chart payloads into plotstats Plotly specs.

    This adapter intentionally accepts plain mappings so Metroliza can pass the
    payload dictionaries it already stores in HTML dashboard manifests.
    Unsupported payloads return an empty mapping, allowing callers to keep their
    existing fallback renderer.
    """

    chart_type = str(payload.get("type") or "").strip().lower()
    if chart_type == "histogram":
        histogram_payload_mapping = {
            **dict(payload),
            "title": title or payload.get("title") or "Histogram",
        }
        histogram = histogram_from_metroliza_native_payload(histogram_payload_mapping)
        histogram = replace(histogram, metadata=_metadata_with_theme(histogram.metadata, theme))
        return histogram_payload_to_plotly_spec(histogram, static=static)

    if chart_type == "distribution":
        render_mode = str(payload.get("render_mode") or "violin").strip().lower()
        if render_mode != "violin":
            return {}
        groups = _groups_from_series_payload(payload)
        if not groups:
            return {}
        violin = build_violin_payload(groups, spec_limits=_spec_limits_from_payload(payload))
        violin = replace(violin, metadata=_metadata_with_theme(violin.metadata, theme))
        spec = violin_payload_to_plotly_spec(violin, static=static)
        _set_plotly_title(spec, title or str(payload.get("title") or "Violin"))
        return spec

    if chart_type == "iqr":
        groups = _groups_from_series_payload(payload)
        if not groups:
            return {}
        iqr = build_iqr_payload(
            groups,
            spec_limits=_spec_limits_from_payload(payload),
            config=IQRConfig(showfliers=False),
        )
        iqr = replace(iqr, metadata=_metadata_with_theme(iqr.metadata, theme))
        spec = iqr_payload_to_plotly_spec(iqr, static=static)
        _set_plotly_title(spec, title or str(payload.get("title") or "IQR"))
        return spec

    return {}


def _metadata_with_theme(metadata: Mapping[str, Any], theme: str | Mapping[str, Any] | None) -> dict[str, Any]:
    resolved = dict(metadata)
    if theme is not None:
        resolved["theme"] = theme
    return resolved


def _groups_from_series_payload(payload: Mapping[str, Any]) -> dict[str, Sequence[Any]]:
    labels = [str(label) for label in (payload.get("labels") or ())]
    series = payload.get("series") or ()
    groups: dict[str, Sequence[Any]] = {}
    for index, values in enumerate(series):
        label = labels[index] if index < len(labels) and labels[index] else f"Group {index + 1}"
        if isinstance(values, Sequence):
            groups[label] = values
        elif isinstance(values, Iterable):
            groups[label] = tuple(values)
    return groups


def _set_plotly_title(spec: dict[str, Any], title: str) -> None:
    layout = spec.get("layout")
    if isinstance(layout, dict):
        layout["title"] = {"text": title}


def _spec_limits_from_payload(payload: Mapping[str, Any]) -> SpecLimits:
    limits = payload.get("limits") if isinstance(payload.get("limits"), Mapping) else payload
    return SpecLimits(
        lsl=_coerce_float(limits.get("lsl")),
        nominal=_coerce_float(limits.get("nominal")),
        usl=_coerce_float(limits.get("usl")),
    )


def _histogram_metadata_from_native_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    style = payload.get("style") if isinstance(payload.get("style"), Mapping) else {}
    visual_metadata = payload.get("visual_metadata") if isinstance(payload.get("visual_metadata"), Mapping) else {}
    summary_table = visual_metadata.get("summary_stats_table") if isinstance(visual_metadata.get("summary_stats_table"), Mapping) else {}
    x_view = payload.get("x_view") if isinstance(payload.get("x_view"), Mapping) else None

    metadata = {
        "title": str(payload.get("title") or ""),
        "axis_labels": {
            "x": str(style.get("axis_label_x") or "Measurement"),
            "y": str(style.get("axis_label_y") or "Count"),
        },
        "summary_table_title": str(summary_table.get("title") or payload.get("summary_table_title") or "Parameter"),
        "mean_line": dict(payload.get("mean_line") or {}) if isinstance(payload.get("mean_line"), Mapping) else {},
        "annotation_rows": list(visual_metadata.get("annotation_rows") or payload.get("annotation_rows") or []),
        "specification_lines": list(visual_metadata.get("specification_lines") or payload.get("specification_lines") or []),
        "modeled_overlay_rows": list(
            ((visual_metadata.get("modeled_overlays") or {}).get("rows") if isinstance(visual_metadata.get("modeled_overlays"), Mapping) else None)
            or payload.get("modeled_overlay_rows")
            or []
        ),
        "visual_metadata": dict(visual_metadata),
    }
    if x_view is not None:
        metadata["x_view"] = {"min": _coerce_float(x_view.get("min")), "max": _coerce_float(x_view.get("max"))}
    return metadata


def _table_rows_from_payload(payload: Mapping[str, Any]) -> tuple[TableRow, ...]:
    raw_rows = payload.get("summary_table_rows") or []
    rows = []
    for raw in raw_rows:
        if isinstance(raw, Mapping):
            rows.append(
                TableRow(
                    label=str(raw.get("label") or ""),
                    value=str(raw.get("value") or ""),
                    kind=str(raw.get("row_kind") or "summary_metric"),
                    metadata={
                        key: value
                        for key, value in {
                            "badge_palette": raw.get("badge_palette"),
                            "section_break_before": bool(raw.get("section_break_before")),
                        }.items()
                        if value not in (None, "", False)
                    },
                )
            )
        elif isinstance(raw, (list, tuple)) and len(raw) >= 2:
            rows.append(TableRow(label=str(raw[0]), value=str(raw[1]), kind="summary_metric"))
    return tuple(rows)


def _is_positive_int_like(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _coerce_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and number not in (float("inf"), float("-inf")) else None
