use crate::spec::{ChartTransform, HistogramSpec, Point, Rect, RenderResult, TextSpec};
use crate::svg::{
    draw_axes, draw_line_spec, draw_text_spec, finish_chart, render_surface, RasterCanvas,
    RenderedChart, SvgDocument,
};
use std::time::Instant;

pub fn render(spec: &HistogramSpec) -> RenderResult<RenderedChart> {
    let draw_start = Instant::now();
    let (mut svg, mut raster, width, height) = render_surface(&spec.common)?;
    let axes_start = Instant::now();
    draw_axes(&mut svg, &mut raster, &spec.common);
    let axes_ms = elapsed_ms(axes_start);
    let transform = ChartTransform::from_common(&spec.common);

    let bars_start = Instant::now();
    for bar in &spec.bars {
        let p0 = transform.map(bar.x0, bar.y0);
        let p1 = transform.map(bar.x1, bar.y1);
        let rect = Rect {
            x: p0.x.min(p1.x),
            y: p0.y.min(p1.y),
            width: (p0.x - p1.x).abs().max(1.0),
            height: (p0.y - p1.y).abs().max(1.0),
        };
        svg.rect(rect, &bar.fill, &bar.stroke, bar.opacity, 0.8);
        raster.rect(rect, &bar.fill, "none", bar.opacity, 0.0);
    }
    let bars_ms = elapsed_ms(bars_start);

    let curves_start = Instant::now();
    for curve in &spec.curves {
        let count = curve.x.len().min(curve.y.len());
        let points = (0..count)
            .map(|idx| {
                if curve.coordinate_space == "canvas" {
                    Point {
                        x: curve.x[idx],
                        y: curve.y[idx],
                    }
                } else {
                    transform.map(curve.x[idx], curve.y[idx])
                }
            })
            .collect::<Vec<_>>();
        if curve.fill_to_baseline && curve.fill_alpha > 0.0 && points.len() >= 2 {
            let mut fill_points = points.clone();
            if curve.coordinate_space == "canvas" {
                fill_points.push(Point {
                    x: points.last().map(|point| point.x).unwrap_or(0.0),
                    y: spec.common.plot_rect.y + spec.common.plot_rect.height,
                });
                fill_points.push(Point {
                    x: points.first().map(|point| point.x).unwrap_or(0.0),
                    y: spec.common.plot_rect.y + spec.common.plot_rect.height,
                });
            } else {
                let last_x = curve.x[count - 1];
                let first_x = curve.x[0];
                fill_points.push(transform.map(last_x, 0.0));
                fill_points.push(transform.map(first_x, 0.0));
            }
            let fill_color = curve.fill_color.as_deref().unwrap_or(&curve.stroke);
            svg.path(&fill_points, fill_color, "none", curve.fill_alpha, 0.0);
            raster.fill_polygon(&fill_points, fill_color, "none", curve.fill_alpha, 0.0);
        }
        svg.polyline(
            &points,
            &curve.stroke,
            curve.stroke_width,
            &curve.dash,
            curve.opacity,
        );
        let raster_points = decimate_smooth_curve(&points);
        raster.stroke_polyline(
            &raster_points,
            &curve.stroke,
            curve.stroke_width,
            curve.opacity,
        );
    }
    let curves_ms = elapsed_ms(curves_start);

    let lines_start = Instant::now();
    for line in &spec.spec_lines {
        draw_line_spec(&mut svg, &mut raster, transform, line);
    }
    if let Some(line) = &spec.mean_line {
        draw_line_spec(&mut svg, &mut raster, transform, line);
    }
    for line in &spec.annotation_lines {
        draw_line_spec(&mut svg, &mut raster, transform, line);
    }
    for annotation in &spec.annotations {
        draw_text_spec(&mut svg, transform, annotation);
    }
    let lines_ms = elapsed_ms(lines_start);

    let table_start = Instant::now();
    draw_table(spec, &mut svg, &mut raster);
    let table_ms = elapsed_ms(table_start);

    let mut rendered = finish_chart(svg, raster, width, height, draw_start)?;
    rendered
        .timings_ms
        .push(("native_histogram_axes_ms".to_string(), axes_ms));
    rendered
        .timings_ms
        .push(("native_histogram_bars_ms".to_string(), bars_ms));
    rendered
        .timings_ms
        .push(("native_histogram_curves_ms".to_string(), curves_ms));
    rendered
        .timings_ms
        .push(("native_histogram_lines_ms".to_string(), lines_ms));
    rendered
        .timings_ms
        .push(("native_histogram_table_ms".to_string(), table_ms));
    Ok(rendered)
}

fn elapsed_ms(start: Instant) -> f64 {
    start.elapsed().as_secs_f64() * 1_000.0
}

fn decimate_smooth_curve(points: &[Point]) -> Vec<Point> {
    if points.len() <= 180 {
        return points.to_vec();
    }
    let mut decimated = Vec::with_capacity(points.len() / 2 + 2);
    for (index, point) in points.iter().enumerate() {
        if index == 0 || index + 1 == points.len() || index % 2 == 0 {
            decimated.push(*point);
        }
    }
    decimated
}

fn draw_table(spec: &HistogramSpec, svg: &mut SvgDocument, raster: &mut RasterCanvas) {
    let Some(table) = &spec.table else {
        if let Some(rect) = spec.table_rect {
            svg.rect(rect, "#ffffff", "#d1d5db", 1.0, 1.0);
            raster.rect(rect, "#ffffff", "#d1d5db", 1.0, 1.0);
        }
        return;
    };

    svg.rect(table.rect, "#ffffff", "#d1d5db", 1.0, 1.0);
    raster.rect(table.rect, "#ffffff", "#d1d5db", 1.0, 1.0);

    let mut y = table.rect.y + 16.0;
    if !table.header.is_empty() {
        draw_table_text(
            svg,
            table.rect,
            y,
            table
                .header
                .get(0)
                .map(|cell| cell.text.clone())
                .unwrap_or_default(),
            table
                .header
                .get(1)
                .map(|cell| cell.text.clone())
                .unwrap_or_default(),
            "600",
            "#111827",
        );
        y += 16.0;
        let separator_y = y - 4.0;
        svg.line(
            Point {
                x: table.rect.x,
                y: separator_y,
            },
            Point {
                x: table.rect.x + table.rect.width,
                y: separator_y,
            },
            "#e5e7eb",
            1.0,
            &[],
            1.0,
        );
        raster.line(
            Point {
                x: table.rect.x,
                y: separator_y,
            },
            Point {
                x: table.rect.x + table.rect.width,
                y: separator_y,
            },
            "#e5e7eb",
            1.0,
            1.0,
        );
    }

    for row in &table.rows {
        if row.section_break_before {
            let separator_y = y - 7.0;
            svg.line(
                Point {
                    x: table.rect.x,
                    y: separator_y,
                },
                Point {
                    x: table.rect.x + table.rect.width,
                    y: separator_y,
                },
                "#d1d5db",
                1.0,
                &[],
                1.0,
            );
            raster.line(
                Point {
                    x: table.rect.x,
                    y: separator_y,
                },
                Point {
                    x: table.rect.x + table.rect.width,
                    y: separator_y,
                },
                "#d1d5db",
                1.0,
                1.0,
            );
        }
        let value_color = if let Some(palette) = &row.badge_palette {
            let (background, text_color) = badge_colors(palette);
            let badge_rect = Rect {
                x: table.rect.x + 3.0,
                y: y - 8.0,
                width: (table.rect.width - 6.0).max(0.0),
                height: 16.0,
            };
            svg.rect(badge_rect, background, "none", 0.94, 0.0);
            raster.rect(badge_rect, background, "none", 0.94, 0.0);
            text_color
        } else {
            "#111827"
        };
        let label = row
            .cells
            .get(0)
            .map(|cell| cell.text.clone())
            .unwrap_or_default();
        let value = row
            .cells
            .get(1)
            .map(|cell| cell.text.clone())
            .unwrap_or_default();
        draw_table_text(svg, table.rect, y, label, value, "normal", value_color);
        y += 18.0;
        if y > table.rect.y + table.rect.height - 8.0 {
            break;
        }
    }
}

fn draw_table_text(
    svg: &mut SvgDocument,
    rect: Rect,
    y: f64,
    label: String,
    value: String,
    weight: &str,
    value_color: &str,
) {
    svg.text(&TextSpec {
        text: label,
        x: rect.x + 8.0,
        y,
        font_size: 10.0,
        fill: if value_color == "#111827" {
            "#374151".to_string()
        } else {
            value_color.to_string()
        },
        align: "left".to_string(),
        baseline: "middle".to_string(),
        weight: weight.to_string(),
        coordinate_space_x: "canvas".to_string(),
        coordinate_space_y: "canvas".to_string(),
    });
    svg.text(&TextSpec {
        text: value,
        x: rect.x + rect.width - 8.0,
        y,
        font_size: 10.0,
        fill: value_color.to_string(),
        align: "right".to_string(),
        baseline: "middle".to_string(),
        weight: weight.to_string(),
        coordinate_space_x: "canvas".to_string(),
        coordinate_space_y: "canvas".to_string(),
    });
}

fn badge_colors(palette: &str) -> (&'static str, &'static str) {
    match palette {
        "quality_capable" | "fit_quality_high" | "normality_normal" => ("#dcfce7", "#166534"),
        "quality_good" => ("#dbeafe", "#1e3a8a"),
        "quality_marginal" | "fit_quality_medium" => ("#fef3c7", "#92400e"),
        "quality_risk" | "fit_quality_low" | "normality_not_normal" => ("#fee2e2", "#991b1b"),
        _ => ("#e5e7eb", "#374151"),
    }
}
