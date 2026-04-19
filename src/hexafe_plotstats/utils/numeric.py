from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np


def clean_numeric(values: Iterable[Any]) -> np.ndarray:
    """Return finite numeric values as a 1D float array."""

    array = np.asarray(list(values), dtype=float).reshape(-1)
    return array[np.isfinite(array)]


def as_float_tuple(values: Iterable[Any]) -> tuple[float, ...]:
    return tuple(float(value) for value in values)

