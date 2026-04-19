from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DistributionCandidate:
    name: str
    support: tuple[str, ...]


@dataclass(frozen=True)
class CurvePayload:
    x: tuple[float, ...]
    y: tuple[float, ...]
    label: str
    kind: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TailRiskEstimate:
    below_lsl_probability: float | None
    above_usl_probability: float | None
    total_probability: float | None
    ppm: float | None


@dataclass(frozen=True)
class DistributionFitResult:
    selected: str | None
    scipy_params: tuple[float, ...] = ()
    params: dict[str, float] = field(default_factory=dict)
    log_likelihood: float | None = None
    aic: float | None = None
    bic: float | None = None
    quality: str = "not_run"
    gof_statistic: float | None = None
    gof_p_value: float | None = None
    tail_risk: TailRiskEstimate | None = None
    curve: CurvePayload | None = None
    kde_reference: CurvePayload | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)
    candidates_ranked: tuple[dict[str, float | str], ...] = ()

