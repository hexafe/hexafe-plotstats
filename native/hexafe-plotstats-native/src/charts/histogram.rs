use crate::spec::{ChartTransform, HistogramSpec, Point, Rect, RenderResult, TextSpec};
use crate::svg::{
    draw_axes, draw_line_spec, draw_text_spec, finish_chart, render_surface, RasterCanvas,
    RenderedChart, SvgDocument,
};

pub fn render(spec: &HistogramSpec) -> RenderResult<RenderedChart> {
    let (mut svg, mut raster, width, height) = render_surface(&spec.common)?;
    draw_axes(&mut svg, &mut raster, &spec.common);
    let transform = ChartTransform::from_common(&spec.common);

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
        raster.rect(rect, &bar.fill, &bar.stroke, bar.opacity, 0.8);
    }

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
        svg.polyline(
            &points,
            &curve.stroke,
            curve.stroke_width,
            &curve.dash,
            curve.opacity,
        );
        raster.stroke_polyline(&points, &curve.stroke, curve.stroke_width, curve.opacity);
    }

    for line in &spec.spec_lines {
        draw_line_spec(&mut svg, &mut raster, transform, line);
    }
    if let Some(line) = &spec.mean_line {
        draw_line_spec(&mut svg, &mut raster, transform, line);
    }
    for annotation in &spec.annotations {
        draw_text_spec(&mut svg, transform, annotation);
    }

    draw_table(spec, &mut svg, &mut raster);

    finish_chart(svg, raster, width, height)
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
