from __future__ import annotations

import warnings as py_warnings

import numpy as np
from scipy import stats

from ..models.summaries import NormalitySummary
from ._cleaning import clean_numeric_with_warnings


def compute_normality(values: object, alpha: float = 0.05) -> NormalitySummary:
    """Run a normality check with small-sample safeguards."""

    if alpha <= 0.0 or alpha >= 1.0:
        raise ValueError("alpha must be between 0 and 1")

    cleaned, warnings = clean_numeric_with_warnings(values)  # type: ignore[arg-type]
    count = int(cleaned.size)

    if count < 3:
        return NormalitySummary(
            method="not_run",
            statistic=None,
            p_value=None,
            is_normal=None,
            warnings=warnings + ("normality testing requires at least three values",),
        )

    if bool(np.all(cleaned == cleaned[0])):
        return NormalitySummary(
            method="not_run",
            statistic=None,
            p_value=None,
            is_normal=None,
            warnings=warnings + ("normality testing is undefined for constant values",),
        )

    method = "shapiro" if count < 8 else "normaltest"
    try:
        with py_warnings.catch_warnings(record=True) as caught:
            py_warnings.simplefilter("always")
            if method == "shapiro":
                result = stats.shapiro(cleaned)
            else:
                result = stats.normaltest(cleaned)
    except Exception as exc:  # pragma: no cover - scipy error messages vary by version
        return NormalitySummary(
            method=method,
            statistic=None,
            p_value=None,
            is_normal=None,
            warnings=warnings + (f"{method} failed: {exc}",),
        )

    scipy_warnings = tuple(str(item.message) for item in caught)
    statistic = float(result.statistic)
    p_value = float(result.pvalue)
    if not np.isfinite(statistic) or not np.isfinite(p_value):
        return NormalitySummary(
            method=method,
            statistic=None,
            p_value=None,
            is_normal=None,
            warnings=warnings + scipy_warnings + (f"{method} returned a non-finite result",),
        )

    return NormalitySummary(
        method=method,
        statistic=statistic,
        p_value=p_value,
        is_normal=bool(p_value >= alpha),
        warnings=warnings + scipy_warnings,
    )

