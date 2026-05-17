from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


SupportKind = Literal["real", "non_negative", "positive", "constant", "empty"]
FitCriterion = Literal["aic", "bic"]
ScatterMode = Literal["scatter", "scatter_rasterized", "hexbin", "line_scatter_trend"]


@dataclass(frozen=True)
class SpecLimits:
    """Measurement specification limits."""

    lsl: float | None = None
    nominal: float | None = None
    usl: float | None = None

    def __post_init__(self) -> None:
        if self.lsl is not None and self.usl is not None and self.lsl > self.usl:
            raise ValueError("lsl must be less than or equal to usl")

    @property
    def has_lower(self) -> bool:
        return self.lsl is not None

    @property
    def has_upper(self) -> bool:
        return self.usl is not None

    @property
    def has_two_sided_limits(self) -> bool:
        return self.has_lower and self.has_upper


@dataclass(frozen=True)
class SupportProfile:
    kind: SupportKind
    min_value: float | None
    max_value: float | None
    has_negative: bool
    has_zero: bool


@dataclass(frozen=True)
class DistributionConfig:
    candidates: tuple[str, ...] | None = None
    criterion: FitCriterion = "aic"
    include_kde_reference: bool = True
    validate_selected_only: bool = True
    run_gof: bool = False
    gof_statistic: str = "ad"
    gof_samples: int = 999
    kde_points: int = 256
    random_state: int | None = None


@dataclass(frozen=True)
class HistogramConfig:
    bins: int | str = "auto"
    density: bool = True
    include_fit: bool = True
    include_kde_reference: bool = True


@dataclass(frozen=True)
class ViolinConfig:
    show_mean: bool = True
    show_extrema: bool = True
    show_quartiles: bool = True
    sigma_policy: Literal["none", "plus_3_sigma", "both_3_sigma"] = "none"


@dataclass(frozen=True)
class IQRConfig:
    whis: float = 1.5
    showfliers: bool = True
    show_mean: bool = True
    show_extrema: bool = True
    sigma_policy: Literal["none", "plus_3_sigma", "both_3_sigma"] = "none"


@dataclass(frozen=True)
class ScatterConfig:
    mode: ScatterMode | Literal["auto"] = "auto"
    rasterized_threshold: int = 5_000
    hexbin_threshold: int = 50_000
    simplified_annotation_threshold: int = 250_000
    marker_size: float | None = None
    alpha: float | None = None
    edgecolors: str = "none"
    gridsize: int = 60
    include_trend: bool = False
