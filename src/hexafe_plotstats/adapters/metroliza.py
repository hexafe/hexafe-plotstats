from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import replace
from typing import Any

from ._core import histogram_payload, summarize
from ..models.common import HistogramConfig, SpecLimits
from ..models.payloads import HistogramPayload, TableRow
from ..payloads import build_histogram_payload


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
