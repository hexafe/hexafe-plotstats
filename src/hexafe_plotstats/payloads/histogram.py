from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import numpy as np

from ..models.common import DistributionConfig, HistogramConfig, SpecLimits
from ..models.payloads import HistogramPayload
from ..stats import compute_normality
from ._common import build_table_rows, compute_capability, fit_distribution, finite_array, histogram_bins, summarize_distribution


def build_histogram_payload(
    values: Iterable[Any],
    spec_limits: SpecLimits | None = None,
    config: HistogramConfig | None = None,
    distribution_config: DistributionConfig | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> HistogramPayload:
    config = config or HistogramConfig()
    array = finite_array(values)
    summary = summarize_distribution(array, spec_limits)
    capability = compute_capability(array, spec_limits)
    normality = compute_normality(array)
    bin_values, bin_edges = histogram_bins(array, config.bins, config.density)
    fit = fit_distribution(array, spec_limits=spec_limits, config=distribution_config) if config.include_fit else None
    warnings = tuple(
        dict.fromkeys(
            summary.warnings
            + capability.warnings
            + normality.warnings
            + (fit.warnings if fit is not None else ())
        )
    )

    return HistogramPayload(
        values=tuple(float(value) for value in array),
        bin_edges=tuple(float(value) for value in bin_edges),
        bin_values=tuple(float(value) for value in bin_values),
        density=config.density,
        summary=summary,
        capability=capability,
        spec_limits=spec_limits or SpecLimits(),
        fit=fit,
        normality=normality,
        table_rows=build_table_rows(summary, capability, normality=normality, fit=fit, spec_limits=spec_limits),
        warnings=warnings,
        metadata=dict(metadata or {}),
    )
