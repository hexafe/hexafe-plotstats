use crate::spec::{ChartTransform, MarkerSpec, Point, RenderResult, ScatterSpec};
use crate::svg::{
    draw_axes, draw_line_spec, finish_chart, marker_point, render_surface, RasterCanvas,
    RenderedChart,
};

pub fn render(spec: &ScatterSpec) -> RenderResult<RenderedChart> {
    let (mut svg, mut raster, width, height) = render_surface(&spec.common)?;
    draw_axes(&mut svg, &mut raster, &spec.common);
    let transform = ChartTransform::from_common(&spec.common);

    if let Some(line) = &spec.trend_line {
        draw_line_spec(&mut svg, &mut raster, transform, line);
    }
    for cell in &spec.hex_cells {
        let points = cell
            .points
            .iter()
            .map(|point| transform.map(point.x, point.y))
            .collect::<Vec<_>>();
        if points.len() >= 3 && cell.count > 0 {
            svg.path(&points, &cell.fill, &cell.stroke, cell.opacity, 0.35);
            raster.fill_polygon(&points, &cell.fill, &cell.stroke, cell.opacity, 0.35);
        }
    }
    for marker in &spec.markers {
        let point = marker_point(transform, marker.x, marker.y, &marker.coordinate_space);
        let radius = marker.size.max(1.0) * 0.5;
        svg.circle(
            point,
            radius,
            &marker.fill,
            &marker.stroke,
            marker.opacity,
            0.8,
        );
    }
    draw_markers_batched(&mut raster, transform, &spec.markers);

    finish_chart(svg, raster, width, height)
}

fn draw_markers_batched(
    raster: &mut RasterCanvas,
    transform: ChartTransform,
    markers: &[MarkerSpec],
) {
    let Some(first) = markers.first() else {
        return;
    };
    let can_batch = markers.iter().all(|marker| {
        marker.fill == first.fill
            && marker.stroke == first.stroke
            && marker.coordinate_space == first.coordinate_space
            && (marker.size - first.size).abs() < f64::EPSILON
            && (marker.opacity - first.opacity).abs() < f64::EPSILON
    });
    if !can_batch {
        for marker in markers {
            let point = marker_point(transform, marker.x, marker.y, &marker.coordinate_space);
            let radius = marker.size.max(1.0) * 0.5;
            raster.circle(
                point,
                radius,
                &marker.fill,
                &marker.stroke,
                marker.opacity,
                0.8,
            );
        }
        return;
    }

    let points = markers
        .iter()
        .map(|marker| marker_point(transform, marker.x, marker.y, &marker.coordinate_space))
        .collect::<Vec<Point>>();
    let radius = first.size.max(1.0) * 0.5;
    if first.stroke == "none" {
        raster.stamp_circles(&points, radius, &first.fill, first.opacity);
    } else {
        raster.circles(
            &points,
            radius,
            &first.fill,
            &first.stroke,
            first.opacity,
            0.8,
        );
    }
}
