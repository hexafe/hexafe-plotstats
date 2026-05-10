use crate::spec::{ChartTransform, Point, RenderResult, ViolinGroupSpec, ViolinSpec};
use crate::svg::{
    draw_axes, draw_line_spec, finish_chart, marker_point, render_surface, RasterCanvas,
    RenderedChart, SvgDocument,
};

pub fn render(spec: &ViolinSpec) -> RenderResult<RenderedChart> {
    let (mut svg, mut raster, width, height) = render_surface(&spec.common)?;
    draw_axes(&mut svg, &mut raster, &spec.common);
    let transform = ChartTransform::from_common(&spec.common);
    let max_width =
        (transform.plot.width / (spec.groups.len().max(1) as f64 + 1.0) * 0.34).clamp(10.0, 34.0);

    for line in &spec.spec_lines {
        draw_line_spec(&mut svg, &mut raster, transform, line);
    }

    for group in &spec.groups {
        let points = violin_points(group, transform, max_width);
        if points.len() >= 3 {
            svg.path(&points, &group.fill, &group.stroke, group.opacity, 1.0);
            raster.fill_polygon(&points, &group.fill, &group.stroke, group.opacity, 1.0);
        }
        draw_summary_markers(group, transform, &mut svg, &mut raster, max_width);
    }

    for marker in &spec.annotation_markers {
        let point = marker_point(transform, marker.x, marker.y, &marker.coordinate_space);
        let radius = marker.size.max(1.0) * 0.5;
        svg.circle(
            point,
            radius,
            &marker.fill,
            &marker.stroke,
            marker.opacity,
            0.7,
        );
        raster.circle(
            point,
            radius,
            &marker.fill,
            &marker.stroke,
            marker.opacity,
            0.7,
        );
    }

    finish_chart(svg, raster, width, height)
}

fn violin_points(group: &ViolinGroupSpec, transform: ChartTransform, max_width: f64) -> Vec<Point> {
    if !group.body_points.is_empty() {
        return group
            .body_points
            .iter()
            .map(|point| transform.map(point.x, point.y))
            .collect();
    }

    let mut values = group
        .values
        .iter()
        .copied()
        .filter(|value| value.is_finite())
        .collect::<Vec<_>>();
    values.sort_by(|left, right| left.total_cmp(right));
    if values.is_empty() {
        return Vec::new();
    }

    let minimum = group.minimum.unwrap_or(values[0]);
    let maximum = group.maximum.unwrap_or(*values.last().unwrap_or(&minimum));
    let center = transform.x.map(group.position);
    if (maximum - minimum).abs() < f64::EPSILON {
        let y = transform.y.map(minimum);
        return vec![
            Point {
                x: center - max_width * 0.35,
                y,
            },
            Point {
                x: center,
                y: y - 5.0,
            },
            Point {
                x: center + max_width * 0.35,
                y,
            },
            Point {
                x: center,
                y: y + 5.0,
            },
        ];
    }

    let samples = 36usize;
    let bandwidth =
        ((maximum - minimum) / (values.len() as f64).sqrt()).max((maximum - minimum) / 28.0);
    let mut densities = Vec::with_capacity(samples);
    for idx in 0..samples {
        let t = idx as f64 / (samples - 1) as f64;
        let y = minimum + t * (maximum - minimum);
        let density = values
            .iter()
            .map(|value| {
                let z = (y - value) / bandwidth;
                (-0.5 * z * z).exp()
            })
            .sum::<f64>();
        densities.push((y, density));
    }
    let max_density = densities
        .iter()
        .map(|(_, density)| *density)
        .fold(0.0_f64, f64::max)
        .max(f64::EPSILON);

    let mut left = Vec::with_capacity(samples);
    let mut right = Vec::with_capacity(samples);
    for (y, density) in densities {
        let half_width = (density / max_density) * max_width;
        let screen_y = transform.y.map(y);
        left.push(Point {
            x: center - half_width,
            y: screen_y,
        });
        right.push(Point {
            x: center + half_width,
            y: screen_y,
        });
    }
    right.reverse();
    left.extend(right);
    left
}

fn draw_summary_markers(
    group: &ViolinGroupSpec,
    transform: ChartTransform,
    svg: &mut SvgDocument,
    raster: &mut RasterCanvas,
    width: f64,
) {
    let center = transform.x.map(group.position);
    for value in [group.q1, group.median, group.q3].into_iter().flatten() {
        let y = transform.y.map(value);
        let left = Point {
            x: center - width * 0.32,
            y,
        };
        let right = Point {
            x: center + width * 0.32,
            y,
        };
        svg.line(left, right, "#111827", 1.0, &[], 1.0);
        raster.line(left, right, "#111827", 1.0, 1.0);
    }
}
