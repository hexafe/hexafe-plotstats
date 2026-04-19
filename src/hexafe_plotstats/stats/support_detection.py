from __future__ import annotations

import numpy as np

from ..models.common import SupportProfile
from ._cleaning import clean_numeric_with_warnings


def detect_support(values: object) -> SupportProfile:
    """Infer the empirical support of finite numeric values."""

    cleaned, _warnings = clean_numeric_with_warnings(values)  # type: ignore[arg-type]
    if cleaned.size == 0:
        return SupportProfile(
            kind="empty",
            min_value=None,
            max_value=None,
            has_negative=False,
            has_zero=False,
        )

    minimum = float(np.min(cleaned))
    maximum = float(np.max(cleaned))
    has_negative = bool(np.any(cleaned < 0.0))
    has_zero = bool(np.any(cleaned == 0.0))

    if bool(np.all(cleaned == cleaned[0])):
        kind = "constant"
    elif has_negative:
        kind = "real"
    elif has_zero:
        kind = "non_negative"
    else:
        kind = "positive"

    return SupportProfile(
        kind=kind,
        min_value=minimum,
        max_value=maximum,
        has_negative=has_negative,
        has_zero=has_zero,
    )

