use crate::spec::{ChartTransform, IqrSpec, Point, Rect, RenderResult};
use crate::svg::{
    draw_axes, draw_line_spec, finish_chart, marker_point, render_surface, RenderedChart,
};

pub fn render(spec: &IqrSpec) -> RenderResult<RenderedChart> {
    let (mut svg, mut raster, width, height) = render_surface(&spec.common)?;
    draw_axes(&mut svg, &mut raster, &spec.common);
    let transform = ChartTransform::from_common(&spec.common);
    let box_width =
        (transform.plot.width / (spec.boxes.len().max(1) as f64 + 1.0) * 0.42).clamp(12.0, 38.0);

    for line in &spec.spec_lines {
        draw_line_spec(&mut svg, &mut raster, transform, line);
    }

    for item in &spec.boxes {
        let x = transform.x.map(item.position);
        if let (Some(q1), Some(q3)) = (item.q1, item.q3) {
            let y1 = transform.y.map(q1);
            let y3 = transform.y.map(q3);
            let rect = Rect {
                x: x - box_width * 0.5,
                y: y1.min(y3),
                width: box_width,
                height: (y1 - y3).abs().max(1.0),
            };
            svg.rect(rect, &item.fill, &item.stroke, item.opacity, 1.0);
            raster.rect(rect, &item.fill, &item.stroke, item.opacity, 1.0);
        }
        if let Some(median) = item.median {
            let y = transform.y.map(median);
            let p0 = Point {
                x: x - box_width * 0.55,
                y,
            };
            let p1 = Point {
                x: x + box_width * 0.55,
                y,
            };
            svg.line(p0, p1, &item.stroke, 1.4, &[], 1.0);
            raster.line(p0, p1, &item.stroke, 1.4, 1.0);
        }
        if let (Some(lower), Some(upper)) = (item.lower_whisker, item.upper_whisker) {
            let p0 = Point {
                x,
                y: transform.y.map(lower),
            };
            let p1 = Point {
                x,
                y: transform.y.map(upper),
            };
            svg.line(p0, p1, &item.stroke, 1.0, &[], 1.0);
            raster.line(p0, p1, &item.stroke, 1.0, 1.0);
            for cap in [p0, p1] {
                let left = Point {
                    x: x - box_width * 0.32,
                    y: cap.y,
                };
                let right = Point {
                    x: x + box_width * 0.32,
                    y: cap.y,
                };
                svg.line(left, right, &item.stroke, 1.0, &[], 1.0);
                raster.line(left, right, &item.stroke, 1.0, 1.0);
            }
        }
    }

    for marker in &spec.outlier_markers {
        let point = marker_point(transform, marker.x, marker.y, &marker.coordinate_space);
        let radius = marker.size.max(1.0) * 0.5;
        svg.circle(
            point,
            radius,
            &marker.fill,
            &marker.stroke,
            marker.opacity,
            0.9,
        );
        raster.circle(
            point,
            radius,
            &marker.fill,
            &marker.stroke,
            marker.opacity,
            0.9,
        );
    }

    finish_chart(svg, raster, width, height)
}
