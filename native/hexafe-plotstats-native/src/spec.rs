use serde_json::Value;
use thiserror::Error;

pub const SCHEMA_VERSION: u64 = 1;

#[derive(Debug, Error)]
pub enum RenderError {
    #[error("{0}")]
    Invalid(String),
    #[error("failed to encode native PNG: {0}")]
    Encode(String),
}

pub type RenderResult<T> = Result<T, RenderError>;

#[derive(Clone, Copy, Debug)]
pub struct Size {
    pub width: f64,
    pub height: f64,
}

#[derive(Clone, Copy, Debug)]
pub struct Rect {
    pub x: f64,
    pub y: f64,
    pub width: f64,
    pub height: f64,
}

#[derive(Clone, Copy, Debug)]
pub struct Point {
    pub x: f64,
    pub y: f64,
}

#[derive(Clone, Debug)]
pub struct TextSpec {
    pub text: String,
    pub x: f64,
    pub y: f64,
    pub font_size: f64,
    pub fill: String,
    pub align: String,
    pub baseline: String,
    pub weight: String,
    pub coordinate_space_x: String,
    pub coordinate_space_y: String,
}

#[derive(Clone, Debug)]
pub struct AxisSpec {
    pub orientation: String,
    pub label: String,
    pub minimum: f64,
    pub maximum: f64,
    pub tick_values: Vec<f64>,
    pub tick_labels: Vec<String>,
}

#[derive(Clone, Debug)]
pub struct LineSpec {
    pub x0: f64,
    pub y0: f64,
    pub x1: f64,
    pub y1: f64,
    pub label: String,
    pub stroke: String,
    pub stroke_width: f64,
    pub dash: Vec<f64>,
    pub coordinate_space: String,
}

#[derive(Clone, Debug)]
pub struct BarSpec {
    pub x0: f64,
    pub x1: f64,
    pub y0: f64,
    pub y1: f64,
    pub fill: String,
    pub stroke: String,
    pub opacity: f64,
}

#[derive(Clone, Debug)]
pub struct CurveSpec {
    pub x: Vec<f64>,
    pub y: Vec<f64>,
    pub stroke: String,
    pub stroke_width: f64,
    pub dash: Vec<f64>,
    pub opacity: f64,
    pub coordinate_space: String,
    pub fill_to_baseline: bool,
    pub fill_color: Option<String>,
    pub fill_alpha: f64,
}

#[derive(Clone, Debug)]
pub struct MarkerSpec {
    pub x: f64,
    pub y: f64,
    pub kind: String,
    pub fill: String,
    pub stroke: String,
    pub size: f64,
    pub opacity: f64,
    pub coordinate_space: String,
}

#[derive(Clone, Debug)]
pub struct MarkerBatchSpec {
    pub x: Vec<f64>,
    pub y: Vec<f64>,
    pub fill: String,
    pub stroke: String,
    pub size: f64,
    pub opacity: f64,
    pub coordinate_space: String,
}

#[derive(Clone, Debug)]
pub struct HexCellSpec {
    pub points: Vec<Point>,
    pub count: usize,
    pub fill: String,
    pub stroke: String,
    pub opacity: f64,
}

#[derive(Clone, Debug)]
pub struct BoxPlotSpec {
    pub position: f64,
    pub lower_whisker: Option<f64>,
    pub q1: Option<f64>,
    pub median: Option<f64>,
    pub q3: Option<f64>,
    pub upper_whisker: Option<f64>,
    pub fill: String,
    pub stroke: String,
    pub opacity: f64,
}

#[derive(Clone, Debug)]
pub struct ViolinGroupSpec {
    pub position: f64,
    pub values: Vec<f64>,
    pub body_points: Vec<Point>,
    pub q1: Option<f64>,
    pub median: Option<f64>,
    pub q3: Option<f64>,
    pub minimum: Option<f64>,
    pub maximum: Option<f64>,
    pub fill: String,
    pub stroke: String,
    pub opacity: f64,
}

#[derive(Clone, Debug)]
pub struct TableCell {
    pub text: String,
}

#[derive(Clone, Debug)]
pub struct TableRow {
    pub cells: Vec<TableCell>,
    pub badge_palette: Option<String>,
    pub section_break_before: bool,
}

#[derive(Clone, Debug)]
pub struct TableSpec {
    pub rect: Rect,
    pub header: Vec<TableCell>,
    pub rows: Vec<TableRow>,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum RenderProfile {
    Fast,
    Compact,
    Debug,
}

impl RenderProfile {
    pub fn label(self) -> &'static str {
        match self {
            Self::Fast => "fast",
            Self::Compact => "compact",
            Self::Debug => "debug",
        }
    }
}

#[derive(Clone, Debug)]
pub struct CommonSpec {
    pub canvas: Size,
    pub background: String,
    pub title: Option<TextSpec>,
    pub plot_rect: Rect,
    pub axes: Vec<AxisSpec>,
    pub render_profile: RenderProfile,
}

#[derive(Clone, Debug)]
pub struct HistogramSpec {
    pub common: CommonSpec,
    pub table_rect: Option<Rect>,
    pub bars: Vec<BarSpec>,
    pub curves: Vec<CurveSpec>,
    pub spec_lines: Vec<LineSpec>,
    pub mean_line: Option<LineSpec>,
    pub annotation_lines: Vec<LineSpec>,
    pub annotations: Vec<TextSpec>,
    pub table: Option<TableSpec>,
}

#[derive(Clone, Debug)]
pub struct ScatterSpec {
    pub common: CommonSpec,
    pub markers: Vec<MarkerSpec>,
    pub marker_batches: Vec<MarkerBatchSpec>,
    pub hex_cells: Vec<HexCellSpec>,
    pub trend_line: Option<LineSpec>,
}

#[derive(Clone, Debug)]
pub struct IqrSpec {
    pub common: CommonSpec,
    pub boxes: Vec<BoxPlotSpec>,
    pub outlier_markers: Vec<MarkerSpec>,
    pub spec_lines: Vec<LineSpec>,
}

#[derive(Clone, Debug)]
pub struct ViolinSpec {
    pub common: CommonSpec,
    pub groups: Vec<ViolinGroupSpec>,
    pub annotation_markers: Vec<MarkerSpec>,
    pub spec_lines: Vec<LineSpec>,
}

#[derive(Clone, Copy, Debug)]
pub struct LinearScale {
    domain_min: f64,
    domain_max: f64,
    range_min: f64,
    range_max: f64,
}

impl LinearScale {
    pub fn new(domain_min: f64, domain_max: f64, range_min: f64, range_max: f64) -> Self {
        Self {
            domain_min,
            domain_max,
            range_min,
            range_max,
        }
    }

    pub fn map(self, value: f64) -> f64 {
        let span = self.domain_max - self.domain_min;
        if !span.is_finite() || span.abs() < f64::EPSILON {
            return (self.range_min + self.range_max) * 0.5;
        }
        self.range_min + ((value - self.domain_min) / span) * (self.range_max - self.range_min)
    }
}

#[derive(Clone, Copy, Debug)]
pub struct ChartTransform {
    pub plot: Rect,
    pub x: LinearScale,
    pub y: LinearScale,
}

impl ChartTransform {
    pub fn from_common(common: &CommonSpec) -> Self {
        let x_axis = axis(common, "x");
        let y_axis = axis(common, "y");
        let x_min = x_axis.map(|axis| axis.minimum).unwrap_or(0.0);
        let x_max = x_axis.map(|axis| axis.maximum).unwrap_or(1.0);
        let y_min = y_axis.map(|axis| axis.minimum).unwrap_or(0.0);
        let y_max = y_axis.map(|axis| axis.maximum).unwrap_or(1.0);
        Self {
            plot: common.plot_rect,
            x: LinearScale::new(
                x_min,
                x_max,
                common.plot_rect.x,
                common.plot_rect.x + common.plot_rect.width,
            ),
            y: LinearScale::new(
                y_min,
                y_max,
                common.plot_rect.y + common.plot_rect.height,
                common.plot_rect.y,
            ),
        }
    }

    pub fn map(self, x: f64, y: f64) -> Point {
        Point {
            x: self.x.map(x),
            y: self.y.map(y),
        }
    }
}

pub fn axis<'a>(common: &'a CommonSpec, orientation: &str) -> Option<&'a AxisSpec> {
    common
        .axes
        .iter()
        .find(|axis| axis.orientation == orientation)
}

pub fn parse_histogram(value: &Value) -> RenderResult<HistogramSpec> {
    Ok(HistogramSpec {
        common: parse_common(value, "histogram")?,
        table_rect: optional_rect(value.get("table_rect"))?,
        bars: array(value, "bars")?
            .iter()
            .map(parse_bar)
            .collect::<RenderResult<Vec<_>>>()?,
        curves: array(value, "curves")?
            .iter()
            .map(parse_curve)
            .collect::<RenderResult<Vec<_>>>()?,
        spec_lines: array(value, "spec_lines")?
            .iter()
            .map(parse_line)
            .collect::<RenderResult<Vec<_>>>()?,
        mean_line: optional_object(value.get("mean_line"), parse_line)?,
        annotation_lines: array(value, "annotation_lines")?
            .iter()
            .map(parse_line)
            .collect::<RenderResult<Vec<_>>>()?,
        annotations: array(value, "annotations")?
            .iter()
            .map(parse_text)
            .collect::<RenderResult<Vec<_>>>()?,
        table: optional_object(value.get("table"), parse_table)?,
    })
}

pub fn parse_scatter(value: &Value) -> RenderResult<ScatterSpec> {
    Ok(ScatterSpec {
        common: parse_common(value, "scatter")?,
        markers: array(value, "markers")?
            .iter()
            .map(parse_marker)
            .collect::<RenderResult<Vec<_>>>()?,
        marker_batches: array(value, "marker_batches")?
            .iter()
            .map(parse_marker_batch)
            .collect::<RenderResult<Vec<_>>>()?,
        hex_cells: array(value, "hex_cells")?
            .iter()
            .map(parse_hex_cell)
            .collect::<RenderResult<Vec<_>>>()?,
        trend_line: optional_object(value.get("trend_line"), parse_line)?,
    })
}

pub fn parse_iqr(value: &Value) -> RenderResult<IqrSpec> {
    Ok(IqrSpec {
        common: parse_common(value, "iqr")?,
        boxes: array(value, "boxes")?
            .iter()
            .map(parse_box)
            .collect::<RenderResult<Vec<_>>>()?,
        outlier_markers: array(value, "outlier_markers")?
            .iter()
            .map(parse_marker)
            .collect::<RenderResult<Vec<_>>>()?,
        spec_lines: array(value, "spec_lines")?
            .iter()
            .map(parse_line)
            .collect::<RenderResult<Vec<_>>>()?,
    })
}

pub fn parse_violin(value: &Value) -> RenderResult<ViolinSpec> {
    Ok(ViolinSpec {
        common: parse_common(value, "violin")?,
        groups: array(value, "groups")?
            .iter()
            .map(parse_violin_group)
            .collect::<RenderResult<Vec<_>>>()?,
        annotation_markers: array(value, "annotation_markers")?
            .iter()
            .map(parse_marker)
            .collect::<RenderResult<Vec<_>>>()?,
        spec_lines: array(value, "spec_lines")?
            .iter()
            .map(parse_line)
            .collect::<RenderResult<Vec<_>>>()?,
    })
}

fn parse_common(value: &Value, expected_chart: &str) -> RenderResult<CommonSpec> {
    let chart_type = string(value, "chart_type", "")?;
    if chart_type.is_empty() {
        return Err(RenderError::Invalid(
            "resolved spec is missing chart_type".to_string(),
        ));
    }
    if chart_type != expected_chart {
        return Err(RenderError::Invalid(format!(
            "expected {expected_chart} resolved spec, got {chart_type}"
        )));
    }
    let schema_version = value
        .get("schema_version")
        .and_then(Value::as_u64)
        .unwrap_or(SCHEMA_VERSION);
    if schema_version != SCHEMA_VERSION {
        return Err(RenderError::Invalid(format!(
            "unsupported resolved spec schema_version: {schema_version}"
        )));
    }
    let canvas = object(value.get("canvas"), "canvas")?;
    let size = object(canvas.get("size"), "canvas.size")?;
    let width = finite_number(size, "width", 900.0)?;
    let height = finite_number(size, "height", 520.0)?;
    if width <= 0.0 || height <= 0.0 {
        return Err(RenderError::Invalid(
            "resolved spec canvas dimensions must be positive finite numbers".to_string(),
        ));
    }
    let metadata = value.get("metadata");
    Ok(CommonSpec {
        canvas: Size { width, height },
        background: string(canvas, "background", "#ffffff")?,
        title: optional_object(value.get("title"), parse_text)?,
        plot_rect: parse_rect(object(value.get("plot_rect"), "plot_rect")?)?,
        axes: array(value, "axes")?
            .iter()
            .map(parse_axis)
            .collect::<RenderResult<Vec<_>>>()?,
        render_profile: parse_render_profile(
            metadata
                .and_then(|item| item.get("render_profile"))
                .or_else(|| value.get("render_profile")),
        )?,
    })
}

fn parse_render_profile(value: Option<&Value>) -> RenderResult<RenderProfile> {
    match value.and_then(Value::as_str).unwrap_or("fast") {
        "fast" => Ok(RenderProfile::Fast),
        "compact" => Ok(RenderProfile::Compact),
        "debug" => Ok(RenderProfile::Debug),
        other => Err(RenderError::Invalid(format!(
            "unsupported native render profile: {other}"
        ))),
    }
}

fn parse_axis(value: &Value) -> RenderResult<AxisSpec> {
    Ok(AxisSpec {
        orientation: string(value, "orientation", "")?,
        label: string(value, "label", "")?,
        minimum: finite_number(value, "minimum", 0.0)?,
        maximum: finite_number(value, "maximum", 1.0)?,
        tick_values: numbers(value.get("tick_values")),
        tick_labels: strings(value.get("tick_labels")),
    })
}

fn parse_rect(value: &Value) -> RenderResult<Rect> {
    Ok(Rect {
        x: finite_number(value, "x", 0.0)?,
        y: finite_number(value, "y", 0.0)?,
        width: finite_number(value, "width", 0.0)?.max(0.0),
        height: finite_number(value, "height", 0.0)?.max(0.0),
    })
}

fn parse_text(value: &Value) -> RenderResult<TextSpec> {
    let coordinate_space = value
        .get("metadata")
        .and_then(|metadata| metadata.get("coordinate_space"));
    Ok(TextSpec {
        text: string(value, "text", "")?,
        x: finite_number(value, "x", 0.0)?,
        y: finite_number(value, "y", 0.0)?,
        font_size: finite_number(value, "font_size", 12.0)?.max(1.0),
        fill: string(value, "fill", "#111827")?,
        align: string(value, "align", "left")?,
        baseline: string(value, "baseline", "alphabetic")?,
        weight: string(value, "weight", "normal")?,
        coordinate_space_x: coordinate_space
            .and_then(|item| item.get("x"))
            .and_then(Value::as_str)
            .unwrap_or("canvas")
            .to_string(),
        coordinate_space_y: coordinate_space
            .and_then(|item| item.get("y"))
            .and_then(Value::as_str)
            .unwrap_or("canvas")
            .to_string(),
    })
}

fn parse_line(value: &Value) -> RenderResult<LineSpec> {
    Ok(LineSpec {
        x0: finite_number(value, "x0", 0.0)?,
        y0: finite_number(value, "y0", 0.0)?,
        x1: finite_number(value, "x1", 0.0)?,
        y1: finite_number(value, "y1", 0.0)?,
        label: string(value, "label", "")?,
        stroke: string(value, "stroke", "#111827")?,
        stroke_width: finite_number(value, "stroke_width", 1.0)?.max(0.1),
        dash: numbers(value.get("dash")),
        coordinate_space: string(value, "coordinate_space", "data")?,
    })
}

fn parse_bar(value: &Value) -> RenderResult<BarSpec> {
    Ok(BarSpec {
        x0: finite_number(value, "x0", 0.0)?,
        x1: finite_number(value, "x1", 0.0)?,
        y0: finite_number(value, "y0", 0.0)?,
        y1: finite_number(value, "y1", 0.0)?,
        fill: string(value, "fill", "#2563eb")?,
        stroke: string(value, "stroke", "#1d4ed8")?,
        opacity: finite_number(value, "opacity", 0.82)?.clamp(0.0, 1.0),
    })
}

fn parse_curve(value: &Value) -> RenderResult<CurveSpec> {
    Ok(CurveSpec {
        x: numbers(value.get("x")),
        y: numbers(value.get("y")),
        stroke: string(value, "stroke", "#f97316")?,
        stroke_width: finite_number(value, "stroke_width", 1.5)?.max(0.1),
        dash: numbers(value.get("dash")),
        opacity: finite_number(value, "opacity", 1.0)?.clamp(0.0, 1.0),
        coordinate_space: string(value, "coordinate_space", "data")?,
        fill_to_baseline: value
            .get("fill_to_baseline")
            .and_then(Value::as_bool)
            .unwrap_or(false),
        fill_color: string_option(value.get("fill_color")),
        fill_alpha: finite_number(value, "fill_alpha", 0.0)?.clamp(0.0, 1.0),
    })
}

fn parse_marker(value: &Value) -> RenderResult<MarkerSpec> {
    Ok(MarkerSpec {
        x: finite_number(value, "x", 0.0)?,
        y: finite_number(value, "y", 0.0)?,
        kind: string(value, "kind", "point")?,
        fill: string(value, "fill", "#2563eb")?,
        stroke: string(value, "stroke", "#1d4ed8")?,
        size: finite_number(value, "size", 4.0)?.max(0.5),
        opacity: finite_number(value, "opacity", 0.82)?.clamp(0.0, 1.0),
        coordinate_space: string(value, "coordinate_space", "data")?,
    })
}

fn parse_marker_batch(value: &Value) -> RenderResult<MarkerBatchSpec> {
    Ok(MarkerBatchSpec {
        x: numbers(value.get("x")),
        y: numbers(value.get("y")),
        fill: string(value, "fill", "#2563eb")?,
        stroke: string(value, "stroke", "#1d4ed8")?,
        size: finite_number(value, "size", 4.0)?.max(0.5),
        opacity: finite_number(value, "opacity", 0.82)?.clamp(0.0, 1.0),
        coordinate_space: string(value, "coordinate_space", "data")?,
    })
}

fn parse_hex_cell(value: &Value) -> RenderResult<HexCellSpec> {
    Ok(HexCellSpec {
        points: points(value.get("points")),
        count: value.get("count").and_then(Value::as_u64).unwrap_or(0) as usize,
        fill: string(value, "fill", "#2563eb")?,
        stroke: string(value, "stroke", "#ffffff")?,
        opacity: finite_number(value, "opacity", 0.72)?.clamp(0.0, 1.0),
    })
}

fn parse_box(value: &Value) -> RenderResult<BoxPlotSpec> {
    Ok(BoxPlotSpec {
        position: finite_number(value, "position", 0.0)?,
        lower_whisker: optional_number(value.get("lower_whisker")),
        q1: optional_number(value.get("q1")),
        median: optional_number(value.get("median")),
        q3: optional_number(value.get("q3")),
        upper_whisker: optional_number(value.get("upper_whisker")),
        fill: string(value, "fill", "#2563eb")?,
        stroke: string(value, "stroke", "#1d4ed8")?,
        opacity: finite_number(value, "opacity", 0.62)?.clamp(0.0, 1.0),
    })
}

fn parse_violin_group(value: &Value) -> RenderResult<ViolinGroupSpec> {
    Ok(ViolinGroupSpec {
        position: finite_number(value, "position", 0.0)?,
        values: numbers(value.get("values")),
        body_points: points(value.get("body_points")),
        q1: optional_number(value.get("q1")),
        median: optional_number(value.get("median")),
        q3: optional_number(value.get("q3")),
        minimum: optional_number(value.get("minimum")),
        maximum: optional_number(value.get("maximum")),
        fill: string(value, "fill", "#2563eb")?,
        stroke: string(value, "stroke", "#1d4ed8")?,
        opacity: finite_number(value, "opacity", 0.72)?.clamp(0.0, 1.0),
    })
}

fn parse_table(value: &Value) -> RenderResult<TableSpec> {
    Ok(TableSpec {
        rect: parse_rect(object(value.get("rect"), "table.rect")?)?,
        header: array(value, "header")?
            .iter()
            .map(parse_table_cell)
            .collect::<RenderResult<Vec<_>>>()?,
        rows: array(value, "rows")?
            .iter()
            .map(parse_table_row)
            .collect::<RenderResult<Vec<_>>>()?,
    })
}

fn parse_table_row(value: &Value) -> RenderResult<TableRow> {
    let metadata = value.get("metadata");
    Ok(TableRow {
        cells: array(value, "cells")?
            .iter()
            .map(parse_table_cell)
            .collect::<RenderResult<Vec<_>>>()?,
        badge_palette: string_option(value.get("badge_palette"))
            .or_else(|| string_option(metadata.and_then(|item| item.get("badge_palette")))),
        section_break_before: value
            .get("section_break_before")
            .and_then(Value::as_bool)
            .or_else(|| {
                metadata
                    .and_then(|item| item.get("section_break_before"))
                    .and_then(Value::as_bool)
            })
            .unwrap_or(false),
    })
}

fn parse_table_cell(value: &Value) -> RenderResult<TableCell> {
    Ok(TableCell {
        text: string(value, "text", "")?,
    })
}

fn optional_rect(value: Option<&Value>) -> RenderResult<Option<Rect>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(item) => parse_rect(item).map(Some),
    }
}

fn optional_object<T>(
    value: Option<&Value>,
    parser: fn(&Value) -> RenderResult<T>,
) -> RenderResult<Option<T>> {
    match value {
        None | Some(Value::Null) => Ok(None),
        Some(item) => parser(item).map(Some),
    }
}

fn array<'a>(value: &'a Value, key: &str) -> RenderResult<&'a Vec<Value>> {
    match value.get(key) {
        Some(Value::Array(items)) => Ok(items),
        None | Some(Value::Null) => {
            static EMPTY: Vec<Value> = Vec::new();
            Ok(&EMPTY)
        }
        _ => Err(RenderError::Invalid(format!("{key} must be an array"))),
    }
}

fn object<'a>(value: Option<&'a Value>, path: &str) -> RenderResult<&'a Value> {
    match value {
        Some(Value::Object(_)) => Ok(value.unwrap()),
        _ => Err(RenderError::Invalid(format!(
            "resolved spec is missing {path}"
        ))),
    }
}

fn finite_number(value: &Value, key: &str, default: f64) -> RenderResult<f64> {
    match value.get(key) {
        None | Some(Value::Null) => Ok(default),
        Some(item) => optional_number(Some(item))
            .ok_or_else(|| RenderError::Invalid(format!("{key} must be a finite numeric value"))),
    }
}

fn optional_number(value: Option<&Value>) -> Option<f64> {
    value
        .and_then(Value::as_f64)
        .filter(|number| number.is_finite())
}

fn numbers(value: Option<&Value>) -> Vec<f64> {
    match value {
        Some(Value::Array(items)) => items
            .iter()
            .filter_map(|item| optional_number(Some(item)))
            .collect(),
        _ => Vec::new(),
    }
}

fn strings(value: Option<&Value>) -> Vec<String> {
    match value {
        Some(Value::Array(items)) => items
            .iter()
            .map(|item| {
                item.as_str()
                    .map(str::to_owned)
                    .unwrap_or_else(|| item.to_string())
            })
            .collect(),
        _ => Vec::new(),
    }
}

fn string_option(value: Option<&Value>) -> Option<String> {
    value.and_then(Value::as_str).map(ToString::to_string)
}

fn points(value: Option<&Value>) -> Vec<Point> {
    match value {
        Some(Value::Array(items)) => items
            .iter()
            .filter_map(|item| match item {
                Value::Array(pair) if pair.len() >= 2 => Some(Point {
                    x: optional_number(pair.first())?,
                    y: optional_number(pair.get(1))?,
                }),
                Value::Object(_) => Some(Point {
                    x: optional_number(item.get("x"))?,
                    y: optional_number(item.get("y"))?,
                }),
                _ => None,
            })
            .collect(),
        _ => Vec::new(),
    }
}

fn string(value: &Value, key: &str, default: &str) -> RenderResult<String> {
    Ok(match value.get(key) {
        Some(Value::String(text)) => text.clone(),
        Some(Value::Null) | None => default.to_string(),
        Some(other) => other.to_string(),
    })
}
