from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np


def clean_numeric_with_warnings(values: Iterable[Any]) -> tuple[np.ndarray, tuple[str, ...]]:
    """Return finite numeric values and warnings about discarded values."""

    warnings: list[str] = []

    try:
        array = np.asarray(values, dtype=float).reshape(-1)
        invalid_count = int(array.size - np.count_nonzero(np.isfinite(array)))
        cleaned = array[np.isfinite(array)]
    except (TypeError, ValueError):
        raw_values = list(values)
        numeric_values: list[float] = []
        invalid_count = 0
        for value in raw_values:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                invalid_count += 1
                continue
            if np.isfinite(numeric):
                numeric_values.append(numeric)
            else:
                invalid_count += 1
        cleaned = np.asarray(numeric_values, dtype=float)

    if invalid_count:
        warnings.append(f"dropped {invalid_count} non-finite or non-numeric value(s)")

    return cleaned, tuple(warnings)
