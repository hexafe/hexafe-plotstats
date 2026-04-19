from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .common import SpecLimits
from .fits import CurvePayload, DistributionFitResult
from .summaries import CapabilitySummary, DistributionSummary


@dataclass(frozen=True)
class TableRow:
    label: str
    value: str
    kind: str = "metric"


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
    table_rows: tuple[TableRow, ...] = ()
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ViolinGroupPayload:
    label: str
    values: tuple[float, ...]
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
    values: tuple[float, ...]
    summary: DistributionSummary
    outliers: tuple[float, ...] = ()


@dataclass(frozen=True)
class IQRPayload:
    groups: tuple[IQRGroupPayload, ...]
    spec_limits: SpecLimits | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScatterPayload:
    x: tuple[float, ...]
    y: tuple[float, ...]
    mode: str
    marker_size: float
    alpha: float
    rasterized: bool
    edgecolors: str
    gridsize: int
    include_trend: bool
    simplified_annotations: bool
    metadata: dict[str, Any] = field(default_factory=dict)

