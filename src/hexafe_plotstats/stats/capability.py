from __future__ import annotations

import numpy as np

from ..models.common import SpecLimits
from ..models.summaries import CapabilitySummary
from ._cleaning import clean_numeric_with_warnings


def compute_capability(values: object, spec_limits: SpecLimits | None = None) -> CapabilitySummary:
    """Compute basic process capability indices from finite numeric values."""

    cleaned, warnings = clean_numeric_with_warnings(values)  # type: ignore[arg-type]
    if cleaned.size < 2:
        return CapabilitySummary(
            cp=None,
            cpk=None,
            cpl=None,
            cpu=None,
            sample_std=None,
            warnings=warnings + ("capability requires at least two finite numeric values",),
        )

    if spec_limits is None or (not spec_limits.has_lower and not spec_limits.has_upper):
        warnings = warnings + ("no specification limits supplied",)
        return CapabilitySummary(
            cp=None,
            cpk=None,
            cpl=None,
            cpu=None,
            sample_std=sample_std,
            warnings=warnings,
        )

    mean = float(np.mean(cleaned))
    sample_std = float(np.std(cleaned, ddof=1))
    if sample_std <= 0.0 or not np.isfinite(sample_std):
        return CapabilitySummary(
            cp=None,
            cpk=None,
            cpl=None,
            cpu=None,
            sample_std=sample_std,
            warnings=warnings + ("capability is undefined for zero sample standard deviation",),
        )

    cp = None
    cpl = None
    cpu = None
    if spec_limits.has_two_sided_limits:
        cp = float((spec_limits.usl - spec_limits.lsl) / (6.0 * sample_std))  # type: ignore[operator]
    if spec_limits.lsl is not None:
        cpl = float((mean - spec_limits.lsl) / (3.0 * sample_std))
    if spec_limits.usl is not None:
        cpu = float((spec_limits.usl - mean) / (3.0 * sample_std))

    one_sided_values = [value for value in (cpl, cpu) if value is not None]
    cpk = float(min(one_sided_values)) if one_sided_values else None

    return CapabilitySummary(
        cp=cp,
        cpk=cpk,
        cpl=cpl,
        cpu=cpu,
        sample_std=sample_std,
        warnings=warnings,
    )
