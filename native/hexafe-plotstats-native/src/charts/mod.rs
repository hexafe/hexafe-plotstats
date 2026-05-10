pub mod histogram;
pub mod iqr;
pub mod scatter;
pub mod violin;

use crate::spec::{parse_histogram, parse_iqr, parse_scatter, parse_violin, RenderResult};
use crate::svg::RenderedChart;
use serde_json::Value;

pub fn render_histogram(value: &Value) -> RenderResult<RenderedChart> {
    histogram::render(&parse_histogram(value)?)
}

pub fn render_scatter(value: &Value) -> RenderResult<RenderedChart> {
    scatter::render(&parse_scatter(value)?)
}

pub fn render_iqr(value: &Value) -> RenderResult<RenderedChart> {
    iqr::render(&parse_iqr(value)?)
}

pub fn render_violin(value: &Value) -> RenderResult<RenderedChart> {
    violin::render(&parse_violin(value)?)
}
