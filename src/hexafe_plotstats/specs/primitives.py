from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AxisOrientation = Literal["x", "y"]
TextAlign = Literal["left", "center", "right"]
TextBaseline = Literal["top", "middle", "bottom", "alphabetic"]


@dataclass(frozen=True)
class Size:
    width: float
    height: float


@dataclass(frozen=True)
class Canvas:
    size: Size
    background: str = "#ffffff"


@dataclass(frozen=True)
class Rect:
    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class TextSpec:
    text: str
    x: float
    y: float
    font_size: float = 12.0
    fill: str = "#111827"
    align: TextAlign = "left"
    baseline: TextBaseline = "alphabetic"
    weight: str = "normal"
    role: str = "label"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AxisSpec:
    orientation: AxisOrientation
    label: str
    minimum: float
    maximum: float
    tick_values: tuple[float, ...] = ()
    tick_labels: tuple[str, ...] = ()
    scale: str = "linear"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class LineSpec:
    x0: float
    y0: float
    x1: float
    y1: float
    label: str = ""
    kind: str = "line"
    stroke: str = "#111827"
    stroke_width: float = 1.0
    dash: tuple[float, ...] = ()
    coordinate_space: str = "data"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class BarSpec:
    x0: float
    x1: float
    y0: float
    y1: float
    label: str = ""
    fill: str = "#2563eb"
    stroke: str = "#1d4ed8"
    opacity: float = 0.82
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CurveSpec:
    x: tuple[float, ...]
    y: tuple[float, ...]
    label: str
    kind: str = "curve"
    stroke: str = "#f97316"
    stroke_width: float = 1.5
    dash: tuple[float, ...] = ()
    opacity: float = 1.0
    coordinate_space: str = "data"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TableCell:
    text: str
    kind: str = "value"
    align: TextAlign = "left"
    col_span: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TableRow:
    cells: tuple[TableCell, ...]
    kind: str = "row"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TableSpec:
    rect: Rect
    rows: tuple[TableRow, ...]
    column_widths: tuple[float, ...] = ()
    header: tuple[TableCell, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedChartSpec:
    chart_type: str
    canvas: Canvas
    title: TextSpec | None
    plot_rect: Rect
    axes: tuple[AxisSpec, ...]
    warnings: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ResolvedHistogramSpec(ResolvedChartSpec):
    table_rect: Rect | None = None
    bars: tuple[BarSpec, ...] = ()
    curves: tuple[CurveSpec, ...] = ()
    spec_lines: tuple[LineSpec, ...] = ()
    mean_line: LineSpec | None = None
    table: TableSpec | None = None
