from __future__ import annotations

from typing import Any

from ._core import capability, histogram_payload, paired_finite_arrays, scatter_payload, summarize, violin_payload
from ..models.common import SpecLimits

try:  # pragma: no cover - import availability is environment dependent
    import pandas as pd
except Exception:  # pragma: no cover - handled by exported guard
    pd = None  # type: ignore[assignment]


def _require_pandas() -> None:
    if pd is None:  # type: ignore[truthy-bool]
        raise ImportError("pandas is not installed; install hexafe-plotstats[pandas] to use this adapter")


def series_to_values(series: Any) -> tuple[float, ...]:
    _require_pandas()
    return tuple(float(value) for value in pd.to_numeric(series, errors="coerce").dropna().tolist())


def frame_column_to_values(frame: Any, column: str) -> tuple[float, ...]:
    _require_pandas()
    return series_to_values(frame[column])


def series_summary(series: Any, spec_limits: SpecLimits | None = None):
    return summarize(series_to_values(series), spec_limits)


def series_capability(series: Any, spec_limits: SpecLimits | None = None):
    return capability(series_to_values(series), spec_limits)


def series_histogram_payload(series: Any, spec_limits: SpecLimits | None = None):
    return histogram_payload(series_to_values(series), spec_limits)


def grouped_violin_payload(frame: Any, value_column: str, group_column: str, *, spec_limits: SpecLimits | None = None):
    _require_pandas()
    groups = []
    for label, group in frame.groupby(group_column, sort=True):
        groups.append((str(label), series_to_values(group[value_column])))
    return violin_payload(groups, spec_limits)


def scatter_from_frame(frame: Any, x_column: str, y_column: str):
    _require_pandas()
    x = pd.to_numeric(frame[x_column], errors="coerce").to_numpy()
    y = pd.to_numeric(frame[y_column], errors="coerce").to_numpy()
    x_values, y_values = paired_finite_arrays(x, y)
    return scatter_payload(x_values, y_values)
