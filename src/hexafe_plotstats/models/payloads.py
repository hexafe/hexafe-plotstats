from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from .common import SpecLimits
from .fits import DistributionFitResult
from .summaries import CapabilitySummary, DistributionSummary, NormalitySummary


@dataclass(frozen=True)
class TableRow:
    label: str
    value: str
    kind: str = "metric"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class HistogramPayload:
    values: tuple[float, ...]
    bin_edges: tuple[float, ...]
    bin_values: tuple[float, ...]
    density: bool
    summary: DistributionSummary
    capability: CapabilitySummary
    spec_limits: SpecLimits
    fit: DistributionFitResult | None = None
    normality: NormalitySummary | None = None
    table_rows: tuple[TableRow, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ViolinGroupPayload:
    label: str
    values: Sequence[float]
    summary: DistributionSummary
    annotations: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class ViolinPayload:
    groups: tuple[ViolinGroupPayload, ...]
    spec_limits: SpecLimits | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class IQRGroupPayload:
    label: str
    values: Sequence[float]
    summary: DistributionSummary
    outliers: tuple[float, ...] = ()


@dataclass(frozen=True)
class IQRPayload:
    groups: tuple[IQRGroupPayload, ...]
    spec_limits: SpecLimits | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScatterPayload:
    x: Sequence[float]
    y: Sequence[float]
    mode: str
    marker_size: float
    alpha: float
    rasterized: bool
    edgecolors: str
    gridsize: int
    include_trend: bool
    simplified_annotations: bool
    metadata: dict[str, Any] = field(default_factory=dict)
