from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np

from ..models.common import DistributionConfig, HistogramConfig, ScatterConfig, SpecLimits
from ..payloads import build_histogram_payload, build_iqr_payload, build_scatter_payload, build_violin_payload
from ..renderers import render_histogram, render_scatter, render_violin
from ..stats import compute_capability, compute_normality, detect_support, fit_distribution, summarize_distribution

__all__ = [
    "capability",
    "fit_distribution",
    "histogram_payload",
    "iqr_payload",
    "normality_summary",
    "paired_finite_arrays",
    "render_histogram",
    "render_scatter",
    "render_violin",
    "scatter_payload",
    "summarize",
    "support_profile",
    "violin_payload",
]


def paired_finite_arrays(x: Iterable[Any], y: Iterable[Any]) -> tuple[np.ndarray, np.ndarray]:
    left = np.asarray(list(x), dtype=float).reshape(-1)
    right = np.asarray(list(y), dtype=float).reshape(-1)
    if left.size != right.size:
        raise ValueError("x and y must have the same length")
    mask = np.isfinite(left) & np.isfinite(right)
    return left[mask], right[mask]


def support_profile(values: Iterable[Any]):
    return detect_support(values)


def summarize(values: Iterable[Any], spec_limits: SpecLimits | None = None):
    return summarize_distribution(values, spec_limits)


def capability(values: Iterable[Any], spec_limits: SpecLimits | None = None):
    return compute_capability(values, spec_limits)


def normality_summary(values: Iterable[Any], alpha: float = 0.05):
    return compute_normality(values, alpha=alpha)


def histogram_payload(
    values: Iterable[Any],
    spec_limits: SpecLimits | None = None,
    *,
    histogram_config: HistogramConfig | None = None,
    distribution_config: DistributionConfig | None = None,
):
    return build_histogram_payload(values, spec_limits, histogram_config, distribution_config)


def violin_payload(groups, spec_limits: SpecLimits | None = None, *, config=None):
    return build_violin_payload(groups, spec_limits, config)


def iqr_payload(groups, spec_limits: SpecLimits | None = None, *, config=None):
    return build_iqr_payload(groups, spec_limits, config)


def scatter_payload(x: Iterable[Any], y: Iterable[Any], *, config: ScatterConfig | None = None):
    return build_scatter_payload(x, y, config)
