pub mod histogram;
pub mod iqr;
pub mod scatter;
pub mod violin;

use crate::spec::{parse_histogram, parse_iqr, parse_scatter, parse_violin, RenderResult};
use crate::svg::RenderedChart;
use serde_json::Value;
use std::time::Instant;

pub fn render_histogram(value: &Value) -> RenderResult<RenderedChart> {
    let parse_start = Instant::now();
    let spec = parse_histogram(value)?;
    let parse_ms = elapsed_ms(parse_start);
    let mut rendered = histogram::render(&spec)?;
    rendered
        .timings_ms
        .push(("native_resolved_parse_ms".to_string(), parse_ms));
    Ok(rendered)
}

pub fn render_scatter(value: &Value) -> RenderResult<RenderedChart> {
    let parse_start = Instant::now();
    let spec = parse_scatter(value)?;
    let parse_ms = elapsed_ms(parse_start);
    let mut rendered = scatter::render(&spec)?;
    rendered
        .timings_ms
        .push(("native_resolved_parse_ms".to_string(), parse_ms));
    Ok(rendered)
}

pub fn render_iqr(value: &Value) -> RenderResult<RenderedChart> {
    let parse_start = Instant::now();
    let spec = parse_iqr(value)?;
    let parse_ms = elapsed_ms(parse_start);
    let mut rendered = iqr::render(&spec)?;
    rendered
        .timings_ms
        .push(("native_resolved_parse_ms".to_string(), parse_ms));
    Ok(rendered)
}

pub fn render_violin(value: &Value) -> RenderResult<RenderedChart> {
    let parse_start = Instant::now();
    let spec = parse_violin(value)?;
    let parse_ms = elapsed_ms(parse_start);
    let mut rendered = violin::render(&spec)?;
    rendered
        .timings_ms
        .push(("native_resolved_parse_ms".to_string(), parse_ms));
    Ok(rendered)
}

fn elapsed_ms(start: Instant) -> f64 {
    start.elapsed().as_secs_f64() * 1_000.0
}
