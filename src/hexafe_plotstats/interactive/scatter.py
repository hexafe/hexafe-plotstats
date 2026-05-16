from __future__ import annotations

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

import numpy as np

TemporalBucket = Literal["minute", "hour", "day", "week"]

_TEMPORAL_BUCKET_NS: dict[TemporalBucket, int] = {
    "minute": 60 * 1_000_000_000,
    "hour": 60 * 60 * 1_000_000_000,
    "day": 24 * 60 * 60 * 1_000_000_000,
    "week": 7 * 24 * 60 * 60 * 1_000_000_000,
}


@dataclass(frozen=True)
class InteractiveLegendSpec:
    label: str
    group: str
    show: bool = True
    visible: bool = True
    togglable: bool = True


@dataclass(frozen=True)
class ScatterAggregatePoint:
    x: float | str
    y: float
    count: int
    x_start: float | str
    x_end: float | str
    y_min: float
    y_max: float
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScatterInteractiveLayer:
    id: str
    role: Literal["interactive_aggregate", "static_raw_overlay"]
    data_policy: str
    legend: InteractiveLegendSpec
    points: tuple[ScatterAggregatePoint, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScatterInteractiveSpec:
    chart_type: str
    layers: tuple[ScatterInteractiveLayer, ...]
    schema_version: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


def select_temporal_bucket(
    start: Any,
    end: Any,
    *,
    target_points: int = 500,
) -> TemporalBucket:
    start_ns = _coerce_single_datetime_ns(start)
    end_ns = _coerce_single_datetime_ns(end)
    if start_ns is None or end_ns is None:
        raise ValueError("start and end must be datetime-like values")

    span_ns = abs(end_ns - start_ns)
    target = max(int(target_points), 1)
    for bucket, bucket_ns in _TEMPORAL_BUCKET_NS.items():
        generated = max(1, math.ceil(span_ns / bucket_ns))
        if generated <= target:
            return bucket
    return "week"


def build_scatter_interactive_spec(
    x: Iterable[Any],
    y: Iterable[Any],
    *,
    x_view: tuple[Any, Any] | Mapping[str, Any] | None = None,
    target_interactive_points: int = 500,
    large_threshold: int = 50_000,
    aggregate_label: str = "Aggregated data",
    raw_layer_label: str = "Raw points",
) -> ScatterInteractiveSpec:
    x_values = _as_array(x)
    y_values = _as_float_array(y)
    if x_values.size != y_values.size:
        raise ValueError("x and y must have the same length")

    temporal_ns = _as_datetime_ns_array(x_values)
    if temporal_ns is not None:
        return _build_temporal_interactive_spec(
            temporal_ns,
            y_values,
            x_view=x_view,
            target_interactive_points=target_interactive_points,
            large_threshold=large_threshold,
            aggregate_label=aggregate_label,
            raw_layer_label=raw_layer_label,
        )
    return _build_numeric_interactive_spec(
        x_values,
        y_values,
        x_view=x_view,
        target_interactive_points=target_interactive_points,
        large_threshold=large_threshold,
        aggregate_label=aggregate_label,
        raw_layer_label=raw_layer_label,
    )


def _build_temporal_interactive_spec(
    x_ns: np.ndarray,
    y_values: np.ndarray,
    *,
    x_view: tuple[Any, Any] | Mapping[str, Any] | None,
    target_interactive_points: int,
    large_threshold: int,
    aggregate_label: str,
    raw_layer_label: str,
) -> ScatterInteractiveSpec:
    mask = (~np.isnat(x_ns.astype("datetime64[ns]"))) & np.isfinite(y_values)
    x_ns = x_ns[mask].astype("datetime64[ns]").astype(np.int64)
    y_values = y_values[mask]
    point_count = int(x_ns.size)
    if point_count == 0:
        return _empty_interactive_spec("temporal")

    view_start, view_end = _temporal_view_ns(x_ns, x_view)
    view_min = min(view_start, view_end)
    view_max = max(view_start, view_end)
    view_mask = (x_ns >= view_min) & (x_ns <= view_max)
    x_ns = x_ns[view_mask]
    y_values = y_values[view_mask]
    in_view_count = int(x_ns.size)
    if in_view_count == 0:
        return _empty_interactive_spec("temporal", source_point_count=point_count)

    bucket = select_temporal_bucket(view_min, view_max, target_points=target_interactive_points)
    bucket_ns = _TEMPORAL_BUCKET_NS[bucket]
    origin_ns = (view_min // bucket_ns) * bucket_ns
    bucket_keys = (x_ns - origin_ns) // bucket_ns
    points = _aggregate_temporal_points(bucket_keys, y_values, origin_ns, bucket_ns)

    return ScatterInteractiveSpec(
        chart_type="scatter",
        layers=(
            ScatterInteractiveLayer(
                id="scatter_temporal_aggregate",
                role="interactive_aggregate",
                data_policy="aggregated_temporal",
                legend=InteractiveLegendSpec(label=aggregate_label, group="scatter_aggregated"),
                points=points,
                metadata={
                    "bucket": bucket,
                    "target_interactive_points": max(int(target_interactive_points), 1),
                    "generated_x_points": len(points),
                    "contains_raw_points": False,
                },
            ),
            _static_raw_layer(raw_layer_label, point_count=point_count, in_view_count=in_view_count),
        ),
        metadata={
            "x_axis_type": "temporal",
            "data_policy": "aggregated_temporal",
            "source_point_count": point_count,
            "in_view_point_count": in_view_count,
            "large_dataset": point_count >= large_threshold,
            "interactive_contains_raw_points": False,
        },
    )


def _build_numeric_interactive_spec(
    x_values: np.ndarray,
    y_values: np.ndarray,
    *,
    x_view: tuple[Any, Any] | Mapping[str, Any] | None,
    target_interactive_points: int,
    large_threshold: int,
    aggregate_label: str,
    raw_layer_label: str,
) -> ScatterInteractiveSpec:
    x_numeric = _as_float_array(x_values)
    mask = np.isfinite(x_numeric) & np.isfinite(y_values)
    x_numeric = x_numeric[mask]
    y_values = y_values[mask]
    point_count = int(x_numeric.size)
    if point_count == 0:
        return _empty_interactive_spec("numeric")

    view_min, view_max = _numeric_view(x_numeric, x_view)
    if view_min > view_max:
        view_min, view_max = view_max, view_min
    view_mask = (x_numeric >= view_min) & (x_numeric <= view_max)
    x_numeric = x_numeric[view_mask]
    y_values = y_values[view_mask]
    in_view_count = int(x_numeric.size)
    if in_view_count == 0:
        return _empty_interactive_spec("numeric", source_point_count=point_count)

    bin_count = max(min(int(target_interactive_points), in_view_count), 1)
    points = _aggregate_numeric_points(x_numeric, y_values, view_min, view_max, bin_count)

    return ScatterInteractiveSpec(
        chart_type="scatter",
        layers=(
            ScatterInteractiveLayer(
                id="scatter_numeric_aggregate",
                role="interactive_aggregate",
                data_policy="aggregated_numeric",
                legend=InteractiveLegendSpec(label=aggregate_label, group="scatter_aggregated"),
                points=points,
                metadata={
                    "target_interactive_points": max(int(target_interactive_points), 1),
                    "generated_x_points": len(points),
                    "contains_raw_points": False,
                },
            ),
            _static_raw_layer(raw_layer_label, point_count=point_count, in_view_count=in_view_count),
        ),
        metadata={
            "x_axis_type": "numeric",
            "data_policy": "aggregated_numeric",
            "source_point_count": point_count,
            "in_view_point_count": in_view_count,
            "large_dataset": point_count >= large_threshold,
            "interactive_contains_raw_points": False,
        },
    )


def _aggregate_temporal_points(
    bucket_keys: np.ndarray,
    y_values: np.ndarray,
    origin_ns: int,
    bucket_ns: int,
) -> tuple[ScatterAggregatePoint, ...]:
    unique_keys, inverse = np.unique(bucket_keys, return_inverse=True)
    counts = np.bincount(inverse)
    y_sum = np.bincount(inverse, weights=y_values)
    y_mean = y_sum / np.maximum(counts, 1)
    y_min = np.full(unique_keys.size, np.inf)
    y_max = np.full(unique_keys.size, -np.inf)
    np.minimum.at(y_min, inverse, y_values)
    np.maximum.at(y_max, inverse, y_values)

    points: list[ScatterAggregatePoint] = []
    for key, count, mean, minimum, maximum in zip(unique_keys, counts, y_mean, y_min, y_max, strict=False):
        start_ns = origin_ns + int(key) * bucket_ns
        end_ns = start_ns + bucket_ns
        center_ns = start_ns + bucket_ns // 2
        points.append(
            ScatterAggregatePoint(
                x=_datetime_ns_to_iso(center_ns),
                y=float(mean),
                count=int(count),
                x_start=_datetime_ns_to_iso(start_ns),
                x_end=_datetime_ns_to_iso(end_ns),
                y_min=float(minimum),
                y_max=float(maximum),
            )
        )
    return tuple(points)


def _aggregate_numeric_points(
    x_values: np.ndarray,
    y_values: np.ndarray,
    view_min: float,
    view_max: float,
    bin_count: int,
) -> tuple[ScatterAggregatePoint, ...]:
    if math.isclose(view_min, view_max):
        view_min -= 0.5
        view_max += 0.5
    edges = np.linspace(view_min, view_max, bin_count + 1)
    keys = np.searchsorted(edges, x_values, side="right") - 1
    keys = np.clip(keys, 0, bin_count - 1)
    unique_keys, inverse = np.unique(keys, return_inverse=True)
    counts = np.bincount(inverse)
    y_sum = np.bincount(inverse, weights=y_values)
    y_mean = y_sum / np.maximum(counts, 1)
    y_min = np.full(unique_keys.size, np.inf)
    y_max = np.full(unique_keys.size, -np.inf)
    np.minimum.at(y_min, inverse, y_values)
    np.maximum.at(y_max, inverse, y_values)

    points: list[ScatterAggregatePoint] = []
    for key, count, mean, minimum, maximum in zip(unique_keys, counts, y_mean, y_min, y_max, strict=False):
        start = float(edges[int(key)])
        end = float(edges[int(key) + 1])
        points.append(
            ScatterAggregatePoint(
                x=(start + end) / 2.0,
                y=float(mean),
                count=int(count),
                x_start=start,
                x_end=end,
                y_min=float(minimum),
                y_max=float(maximum),
            )
        )
    return tuple(points)


def _static_raw_layer(label: str, *, point_count: int, in_view_count: int) -> ScatterInteractiveLayer:
    return ScatterInteractiveLayer(
        id="raw_points_static",
        role="static_raw_overlay",
        data_policy="static_raw_overlay",
        legend=InteractiveLegendSpec(label=label, group="scatter_raw"),
        metadata={
            "rendering": "static_raster",
            "source_point_count": point_count,
            "in_view_point_count": in_view_count,
            "contains_raw_points": False,
        },
    )


def _empty_interactive_spec(x_axis_type: str, *, source_point_count: int = 0) -> ScatterInteractiveSpec:
    return ScatterInteractiveSpec(
        chart_type="scatter",
        layers=(),
        metadata={
            "x_axis_type": x_axis_type,
            "source_point_count": source_point_count,
            "in_view_point_count": 0,
            "interactive_contains_raw_points": False,
        },
    )


def _as_array(values: Iterable[Any]) -> np.ndarray:
    if isinstance(values, np.ndarray):
        return values.reshape(-1)
    try:
        return np.asarray(values).reshape(-1)
    except (TypeError, ValueError):
        return np.asarray(list(values), dtype=object).reshape(-1)


def _as_float_array(values: Iterable[Any]) -> np.ndarray:
    if isinstance(values, np.ndarray):
        return np.asarray(values, dtype=float).reshape(-1)
    try:
        return np.asarray(values, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        return np.asarray(list(values), dtype=float).reshape(-1)


def _as_datetime_ns_array(values: np.ndarray) -> np.ndarray | None:
    if np.issubdtype(values.dtype, np.datetime64):
        coerced = values.astype("datetime64[ns]")
    elif values.dtype == object and any(_is_temporal_value(value) for value in values[: min(values.size, 32)]):
        try:
            coerced = np.asarray(values, dtype="datetime64[ns]")
        except (TypeError, ValueError):
            return None
    else:
        return None
    if coerced.ndim != 1:
        coerced = coerced.reshape(-1)
    return coerced


def _is_temporal_value(value: Any) -> bool:
    return isinstance(value, (datetime, date, np.datetime64))


def _coerce_single_datetime_ns(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(np.datetime64(value, "ns").astype(np.int64))
    except (TypeError, ValueError):
        return None


def _temporal_view_ns(x_ns: np.ndarray, x_view: tuple[Any, Any] | Mapping[str, Any] | None) -> tuple[int, int]:
    if x_view is not None:
        start_raw, end_raw = _view_bounds(x_view)
        start_ns = _coerce_single_datetime_ns(start_raw)
        end_ns = _coerce_single_datetime_ns(end_raw)
        if start_ns is not None and end_ns is not None:
            return start_ns, end_ns
    return int(np.min(x_ns)), int(np.max(x_ns))


def _numeric_view(x_values: np.ndarray, x_view: tuple[Any, Any] | Mapping[str, Any] | None) -> tuple[float, float]:
    if x_view is not None:
        start_raw, end_raw = _view_bounds(x_view)
        try:
            start = float(start_raw)
            end = float(end_raw)
        except (TypeError, ValueError):
            start = end = float("nan")
        if math.isfinite(start) and math.isfinite(end):
            return start, end
    return float(np.min(x_values)), float(np.max(x_values))


def _view_bounds(x_view: tuple[Any, Any] | Mapping[str, Any]) -> tuple[Any, Any]:
    if isinstance(x_view, Mapping):
        return x_view.get("min", x_view.get("start")), x_view.get("max", x_view.get("end"))
    if len(x_view) != 2:
        raise ValueError("x_view must contain exactly two bounds")
    return x_view[0], x_view[1]


def _datetime_ns_to_iso(value: int) -> str:
    return str(np.datetime_as_string(np.datetime64(int(value), "ns"), unit="s"))
