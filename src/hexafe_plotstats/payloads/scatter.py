from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from ..models.common import ScatterConfig
from ..models.payloads import ScatterPayload
from ._common import paired_finite_arrays_with_counts
from ..policies.scatter_mode import resolve_alpha, resolve_marker_size, resolve_scatter_mode

_ARRAY_PAYLOAD_THRESHOLD = 50_000


def build_scatter_payload(
    x: Iterable[Any],
    y: Iterable[Any],
    config: ScatterConfig | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> ScatterPayload:
    config = config or ScatterConfig()
    x_values, y_values, raw_count, dropped_count = paired_finite_arrays_with_counts(x, y)

    count = int(x_values.size)
    mode = resolve_scatter_mode(config, count)
    marker_size = resolve_marker_size(config, count)
    alpha = resolve_alpha(config, count)
    rasterized = mode == "scatter_rasterized"
    simplified_annotations = count >= config.simplified_annotation_threshold

    payload_x: Any
    payload_y: Any
    if count >= _ARRAY_PAYLOAD_THRESHOLD:
        payload_x = x_values
        payload_y = y_values
    else:
        payload_x = tuple(float(value) for value in x_values)
        payload_y = tuple(float(value) for value in y_values)

    payload_metadata = dict(metadata or {})
    payload_metadata.update(
        {
            "raw_point_count": raw_count,
            "finite_point_count": count,
            "dropped_nonfinite_count": dropped_count,
        }
    )

    return ScatterPayload(
        x=payload_x,
        y=payload_y,
        mode=mode,
        marker_size=marker_size,
        alpha=alpha,
        rasterized=rasterized,
        edgecolors=config.edgecolors,
        gridsize=config.gridsize,
        include_trend=config.include_trend,
        simplified_annotations=simplified_annotations,
        metadata=payload_metadata,
    )
