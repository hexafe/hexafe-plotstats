from __future__ import annotations

import numpy as np

from ..models.common import SpecLimits
from ..models.summaries import DistributionSummary
from ._cleaning import clean_numeric_with_warnings


def summarize_distribution(
    values: object,
    spec_limits: SpecLimits | None = None,
) -> DistributionSummary:
    """Summarize finite numeric values and optional specification violations."""

    cleaned, warnings = clean_numeric_with_warnings(values)  # type: ignore[arg-type]
    count = int(cleaned.size)

    if count == 0:
        return DistributionSummary(
            count=0,
            mean=None,
            std=None,
            minimum=None,
            maximum=None,
            median=None,
            q1=None,
            q3=None,
            iqr=None,
            warnings=warnings + ("no finite numeric values",),
        )

    q1, median, q3 = np.percentile(cleaned, [25, 50, 75])
    sample_std = float(np.std(cleaned, ddof=1)) if count >= 2 else None
    if count < 2:
        warnings = warnings + ("sample standard deviation requires at least two values",)

    below_lsl_count = 0
    above_usl_count = 0
    if spec_limits is not None:
        if spec_limits.lsl is not None:
            below_lsl_count = int(np.count_nonzero(cleaned < spec_limits.lsl))
        if spec_limits.usl is not None:
            above_usl_count = int(np.count_nonzero(cleaned > spec_limits.usl))

    nok_count = below_lsl_count + above_usl_count
    has_limits = spec_limits is not None and (spec_limits.has_lower or spec_limits.has_upper)
    nok_rate = (nok_count / count) if has_limits else None

    return DistributionSummary(
        count=count,
        mean=float(np.mean(cleaned)),
        std=sample_std,
        minimum=float(np.min(cleaned)),
        maximum=float(np.max(cleaned)),
        median=float(median),
        q1=float(q1),
        q3=float(q3),
        iqr=float(q3 - q1),
        below_lsl_count=below_lsl_count,
        above_usl_count=above_usl_count,
        nok_count=nok_count,
        nok_rate=nok_rate,
        nok_ppm=(nok_rate * 1_000_000.0) if nok_rate is not None else None,
        warnings=warnings,
    )

