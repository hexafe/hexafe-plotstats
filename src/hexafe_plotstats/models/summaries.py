from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class DistributionSummary:
    count: int
    mean: float | None
    std: float | None
    minimum: float | None
    maximum: float | None
    median: float | None
    q1: float | None
    q3: float | None
    iqr: float | None
    below_lsl_count: int = 0
    above_usl_count: int = 0
    nok_count: int = 0
    nok_rate: float | None = None
    nok_ppm: float | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CapabilitySummary:
    cp: float | None
    cpk: float | None
    cpl: float | None
    cpu: float | None
    sample_std: float | None
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class NormalitySummary:
    method: str
    statistic: float | None
    p_value: float | None
    is_normal: bool | None
    warnings: tuple[str, ...] = field(default_factory=tuple)

