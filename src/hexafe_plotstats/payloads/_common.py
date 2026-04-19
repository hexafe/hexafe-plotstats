from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

from ..models.payloads import TableRow
from ..models.summaries import CapabilitySummary, DistributionSummary
from ..stats import compute_capability, fit_distribution, summarize_distribution
from ..utils import as_float_tuple, compact_float, normalize_label

__all__ = [
    "build_table_rows",
    "compute_capability",
    "finite_array",
    "fit_distribution",
    "histogram_bins",
    "normalize_group_values",
    "paired_finite_arrays",
    "summarize_distribution",
]


def finite_array(values: Iterable[Any]) -> np.ndarray:
    array = np.asarray(list(values), dtype=float).reshape(-1)
    return array[np.isfinite(array)]


def paired_finite_arrays(left: Iterable[Any], right: Iterable[Any]) -> tuple[np.ndarray, np.ndarray]:
    left_values = np.asarray(list(left), dtype=float).reshape(-1)
    right_values = np.asarray(list(right), dtype=float).reshape(-1)
    if left_values.size != right_values.size:
        raise ValueError("x and y must have the same length")

    mask = np.isfinite(left_values) & np.isfinite(right_values)
    return left_values[mask], right_values[mask]


def normalize_group_values(
    groups: Mapping[str, Iterable[Any]] | Sequence[tuple[str, Iterable[Any]]],
) -> tuple[tuple[str, tuple[float, ...]], ...]:
    items = groups.items() if isinstance(groups, Mapping) else groups
    normalized: list[tuple[str, tuple[float, ...]]] = []
    for label, values in items:
        array = finite_array(values)
        normalized.append((normalize_label(label), as_float_tuple(array)))
    return tuple(normalized)


def build_table_rows(summary: DistributionSummary, capability: CapabilitySummary) -> tuple[TableRow, ...]:
    return (
        TableRow(label="count", value=str(summary.count)),
        TableRow(label="mean", value=compact_float(summary.mean)),
        TableRow(label="std", value=compact_float(summary.std)),
        TableRow(label="cpk", value=compact_float(capability.cpk)),
    )


def histogram_bins(
    values: np.ndarray,
    bins: int | str,
    density: bool,
) -> tuple[np.ndarray, np.ndarray]:
    if values.size == 0:
        return np.zeros(1, dtype=float), np.asarray([0.0, 1.0], dtype=float)

    if bool(np.all(values == values[0])):
        center = float(values[0])
        height = 1.0 if density else float(values.size)
        return np.asarray([height], dtype=float), np.asarray([center - 0.5, center + 0.5], dtype=float)

    counts, edges = np.histogram(values, bins=bins, density=density)
    return np.asarray(counts, dtype=float), np.asarray(edges, dtype=float)

