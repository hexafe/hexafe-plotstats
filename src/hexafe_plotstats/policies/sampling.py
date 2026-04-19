from __future__ import annotations

from collections.abc import Sequence

import numpy as np


def deterministic_sample_indices(size: int, limit: int, *, seed: int = 0) -> np.ndarray:
    if size <= limit:
        return np.arange(size, dtype=int)
    if limit <= 0:
        return np.empty(0, dtype=int)

    # Evenly spaced sampling keeps ordering stable and is deterministic without RNG state.
    return np.unique(np.linspace(0, size - 1, limit, dtype=int))


def deterministic_downsample(values: Sequence[float], limit: int, *, seed: int = 0) -> tuple[float, ...]:
    indices = deterministic_sample_indices(len(values), limit, seed=seed)
    return tuple(float(values[index]) for index in indices)

