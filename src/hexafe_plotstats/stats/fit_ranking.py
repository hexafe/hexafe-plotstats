from __future__ import annotations

from collections.abc import Iterable
from typing import TypedDict

from ..models.common import FitCriterion


class FitRecord(TypedDict):
    name: str
    log_likelihood: float
    aic: float
    bic: float


def rank_fit_records(records: Iterable[FitRecord], criterion: FitCriterion) -> tuple[FitRecord, ...]:
    """Sort successful fit records by the configured information criterion."""

    return tuple(sorted(records, key=lambda record: (record[criterion], record["name"])))

