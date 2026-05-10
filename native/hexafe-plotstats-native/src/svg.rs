use crate::spec::{
    ChartTransform, CommonSpec, LineSpec, Point, Rect, RenderError, RenderResult, TextSpec,
};
use std::sync::{Arc, OnceLock};
use tiny_skia::{FillRule, Paint, PathBuilder, Pixmap, Stroke, Transform};

pub struct RenderedChart {
    pub png_bytes: Vec<u8>,
    pub svg: String,
    pub width: u32,
    pub height: u32,
    pub primitive_count: usize,
}

pub struct SvgDocument {
    buffer: String,
    primitive_count: usize,
    debug_shapes: bool,
}

impl SvgDocument {
    pub fn new(width: u32, height: u32, _background: &str) -> Self {
        let debug_shapes = std::env::var_os("HEXAFE_PLOTSTATS_NATIVE_DEBUG_SVG").is_some();
        let mut buffer = String::new();
        buffer.push_str(r#"<?xml version="1.0" encoding="UTF-8"?>"#);
        buffer.push_str(&format!(
            r#"<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">"#
        ));
        if debug_shapes {
            buffer.push_str(&format!(
                r#"<rect x="0" y="0" width="{width}" height="{height}" fill="{}"/>"#,
                sanitize_color(_background)
            ));
        }
        Self {
            buffer,
            primitive_count: 1,
            debug_shapes,
        }
    }

    pub fn rect(&mut self, rect: Rect, fill: &str, stroke: &str, opacity: f64, stroke_width: f64) {
        if rect.width <= 0.0 || rect.height <= 0.0 {
            return;
        }
        self.primitive_count += 1;
        if !self.debug_shapes {
            return;
        }
        self.buffer.push_str(&format!(
            r#"<rect x="{}" y="{}" width="{}" height="{}" fill="{}" stroke="{}" stroke-width="{}" opacity="{}"/>"#,
            fmt(rect.x),
            fmt(rect.y),
            fmt(rect.width),
            fmt(rect.height),
            sanitize_color(fill),
            sanitize_color(stroke),
            fmt(stroke_width),
            fmt(opacity.clamp(0.0, 1.0))
        ));
    }

    pub fn line(
        &mut self,
        p0: Point,
        p1: Point,
        stroke: &str,
        stroke_width: f64,
        dash: &[f64],
        opacity: f64,
    ) {
        self.primitive_count += 1;
        if !self.debug_shapes {
            return;
        }
        self.buffer.push_str(&format!(
            r#"<line x1="{}" y1="{}" x2="{}" y2="{}" stroke="{}" stroke-width="{}" opacity="{}""#,
            fmt(p0.x),
            fmt(p0.y),
            fmt(p1.x),
            fmt(p1.y),
            sanitize_color(stroke),
            fmt(stroke_width),
            fmt(opacity.clamp(0.0, 1.0))
        ));
        if !dash.is_empty() {
            self.buffer
                .push_str(&format!(r#" stroke-dasharray="{}""#, dash_attr(dash)));
        }
        self.buffer.push_str("/>");
    }

    pub fn circle(
        &mut self,
        center: Point,
        radius: f64,
        fill: &str,
        stroke: &str,
        opacity: f64,
        stroke_width: f64,
    ) {
        if radius <= 0.0 {
            return;
        }
        self.primitive_count += 1;
        if !self.debug_shapes {
            return;
        }
        self.buffer.push_str(&format!(
            r#"<circle cx="{}" cy="{}" r="{}" fill="{}" stroke="{}" stroke-width="{}" opacity="{}"/>"#,
            fmt(center.x),
            fmt(center.y),
            fmt(radius),
            sanitize_color(fill),
            sanitize_color(stroke),
            fmt(stroke_width),
            fmt(opacity.clamp(0.0, 1.0))
        ));
    }

    pub fn polyline(
        &mut self,
        points: &[Point],
        stroke: &str,
        stroke_width: f64,
        dash: &[f64],
        opacity: f64,
    ) {
        if points.len() < 2 {
            return;
        }
        self.primitive_count += 1;
        if !self.debug_shapes {
            return;
        }
        self.buffer.push_str(&format!(
            r#"<polyline fill="none" stroke="{}" stroke-width="{}" opacity="{}" points=""#,
            sanitize_color(stroke),
            fmt(stroke_width),
            fmt(opacity.clamp(0.0, 1.0))
        ));
        for point in points {
            self.buffer
                .push_str(&format!("{},{} ", fmt(point.x), fmt(point.y)));
        }
        self.buffer.push('"');
        if !dash.is_empty() {
            self.buffer
                .push_str(&format!(r#" stroke-dasharray="{}""#, dash_attr(dash)));
        }
        self.buffer.push_str("/>");
    }

    pub fn path(
        &mut self,
        points: &[Point],
        fill: &str,
        stroke: &str,
        opacity: f64,
        stroke_width: f64,
    ) {
        if points.len() < 3 {
            return;
        }
        self.primitive_count += 1;
        if !self.debug_shapes {
            return;
        }
        self.buffer.push_str(&format!(
            "{}{} {}",
            r#"<path d="M "#,
            fmt(points[0].x),
            fmt(points[0].y)
        ));
        for point in &points[1..] {
            self.buffer
                .push_str(&format!(" L {} {}", fmt(point.x), fmt(point.y)));
        }
        self.buffer.push_str(&format!(
            r#" Z" fill="{}" stroke="{}" stroke-width="{}" opacity="{}"/>"#,
            sanitize_color(fill),
            sanitize_color(stroke),
            fmt(stroke_width),
            fmt(opacity.clamp(0.0, 1.0))
        ));
    }

    pub fn text(&mut self, text: &TextSpec) {
        if text.text.is_empty() {
            return;
        }
        self.primitive_count += 1;
        self.buffer.push_str(&format!(
            r#"<text x="{}" y="{}" fill="{}" font-size="{}" font-family="sans-serif" font-weight="{}" text-anchor="{}" dominant-baseline="{}">{}</text>"#,
            fmt(text.x),
            fmt(text.y),
            sanitize_color(&text.fill),
            fmt(text.font_size),
            escape(&text.weight),
            anchor(&text.align),
            baseline(&text.baseline),
            escape(&text.text)
        ));
    }

    pub fn finish(mut self) -> (String, usize) {
        self.buffer.push_str("</svg>");
        (self.buffer, self.primitive_count)
    }
}

pub struct RasterCanvas {
    pixmap: Pixmap,
}

impl RasterCanvas {
    pub fn new(width: u32, height: u32, background: &str) -> RenderResult<Self> {
        let mut pixmap = Pixmap::new(width, height).ok_or_else(|| {
            RenderError::Invalid("failed to allocate native render pixmap".to_string())
        })?;
        pixmap.fill(color(background, 1.0));
        Ok(Self { pixmap })
    }

    pub fn rect(&mut self, rect: Rect, fill: &str, stroke: &str, opacity: f64, stroke_width: f64) {
        if let Some(tiny_rect) = tiny_skia::Rect::from_xywh(
            rect.x as f32,
            rect.y as f32,
            rect.width as f32,
            rect.height as f32,
        ) {
            if fill != "none" {
                self.pixmap.fill_rect(
                    tiny_rect,
                    &paint(fill, opacity),
                    Transform::identity(),
                    None,
                );
            }
            if stroke != "none" && stroke_width > 0.0 {
                self.stroke_polyline(
                    &[
                        Point {
                            x: rect.x,
                            y: rect.y,
                        },
                        Point {
                            x: rect.x + rect.width,
                            y: rect.y,
                        },
                        Point {
                            x: rect.x + rect.width,
                            y: rect.y + rect.height,
                        },
                        Point {
                            x: rect.x,
                            y: rect.y + rect.height,
                        },
                        Point {
                            x: rect.x,
                            y: rect.y,
                        },
                    ],
                    stroke,
                    stroke_width,
                    1.0,
                );
            }
        }
    }

    pub fn line(&mut self, p0: Point, p1: Point, stroke: &str, stroke_width: f64, opacity: f64) {
        self.stroke_polyline(&[p0, p1], stroke, stroke_width, opacity);
    }

    pub fn circle(
        &mut self,
        center: Point,
        radius: f64,
        fill: &str,
        stroke: &str,
        opacity: f64,
        stroke_width: f64,
    ) {
        if radius <= 0.0 {
            return;
        }
        let mut builder = PathBuilder::new();
        builder.push_circle(center.x as f32, center.y as f32, radius as f32);
        if let Some(path) = builder.finish() {
            if fill != "none" {
                self.pixmap.fill_path(
                    &path,
                    &paint(fill, opacity),
                    FillRule::Winding,
                    Transform::identity(),
                    None,
                );
            }
            if stroke != "none" && stroke_width > 0.0 {
                self.pixmap.stroke_path(
                    &path,
                    &paint(stroke, 1.0),
                    &stroke_style(stroke_width),
                    Transform::identity(),
                    None,
                );
            }
        }
    }

    pub fn circles(
        &mut self,
        centers: &[Point],
        radius: f64,
        fill: &str,
        stroke: &str,
        opacity: f64,
        stroke_width: f64,
    ) {
        if centers.is_empty() || radius <= 0.0 {
            return;
        }
        let mut builder = PathBuilder::new();
        for center in centers {
            builder.push_circle(center.x as f32, center.y as f32, radius as f32);
        }
        if let Some(path) = builder.finish() {
            if fill != "none" {
                self.pixmap.fill_path(
                    &path,
                    &paint(fill, opacity),
                    FillRule::Winding,
                    Transform::identity(),
                    None,
                );
            }
            if stroke != "none" && stroke_width > 0.0 {
                self.pixmap.stroke_path(
                    &path,
                    &paint(stroke, 1.0),
                    &stroke_style(stroke_width),
                    Transform::identity(),
                    None,
                );
            }
        }
    }

    pub fn stamp_circles(&mut self, centers: &[Point], radius: f64, fill: &str, opacity: f64) {
        if centers.is_empty() || radius <= 0.0 || fill == "none" {
            return;
        }
        let (red, green, blue) = parse_hex_color(fill).unwrap_or((17, 24, 39));
        let width = self.pixmap.width() as i32;
        let height = self.pixmap.height() as i32;
        let radius_i = radius.ceil().max(1.0) as i32;
        let radius_sq = radius * radius;
        let data = self.pixmap.data_mut();
        for center in centers {
            let cx = center.x.round() as i32;
            let cy = center.y.round() as i32;
            for y in (cy - radius_i)..=(cy + radius_i) {
                if y < 0 || y >= height {
                    continue;
                }
                for x in (cx - radius_i)..=(cx + radius_i) {
                    if x < 0 || x >= width {
                        continue;
                    }
                    let dx = x as f64 - center.x;
                    let dy = y as f64 - center.y;
                    if dx * dx + dy * dy > radius_sq {
                        continue;
                    }
                    let index = ((y as usize) * (width as usize) + x as usize) * 4;
                    blend_pixel(&mut data[index..index + 4], red, green, blue, opacity);
                }
            }
        }
    }

    pub fn stroke_polyline(
        &mut self,
        points: &[Point],
        stroke: &str,
        stroke_width: f64,
        opacity: f64,
    ) {
        if points.len() < 2 || stroke == "none" {
            return;
        }
        let mut builder = PathBuilder::new();
        builder.move_to(points[0].x as f32, points[0].y as f32);
        for point in &points[1..] {
            builder.line_to(point.x as f32, point.y as f32);
        }
        if let Some(path) = builder.finish() {
            self.pixmap.stroke_path(
                &path,
                &paint(stroke, opacity),
                &stroke_style(stroke_width),
                Transform::identity(),
                None,
            );
        }
    }

    pub fn fill_polygon(
        &mut self,
        points: &[Point],
        fill: &str,
        stroke: &str,
        opacity: f64,
        stroke_width: f64,
    ) {
        if points.len() < 3 {
            return;
        }
        let mut builder = PathBuilder::new();
        builder.move_to(points[0].x as f32, points[0].y as f32);
        for point in &points[1..] {
            builder.line_to(point.x as f32, point.y as f32);
        }
        builder.close();
        if let Some(path) = builder.finish() {
            if fill != "none" {
                self.pixmap.fill_path(
                    &path,
                    &paint(fill, opacity),
                    FillRule::Winding,
                    Transform::identity(),
                    None,
                );
            }
            if stroke != "none" && stroke_width > 0.0 {
                self.pixmap.stroke_path(
                    &path,
                    &paint(stroke, 1.0),
                    &stroke_style(stroke_width),
                    Transform::identity(),
                    None,
                );
            }
        }
    }

    pub fn encode_png(self) -> RenderResult<Vec<u8>> {
        let width = self.pixmap.width();
        let height = self.pixmap.height();
        let demultiplied = self.pixmap.take_demultiplied();
        let mut data = Vec::new();
        {
            let mut encoder = png::Encoder::new(&mut data, width, height);
            encoder.set_color(png::ColorType::Rgba);
            encoder.set_depth(png::BitDepth::Eight);
            encoder.set_compression(png_compression());
            let mut writer = encoder
                .write_header()
                .map_err(|exc| RenderError::Encode(exc.to_string()))?;
            writer
                .write_image_data(&demultiplied)
                .map_err(|exc| RenderError::Encode(exc.to_string()))?;
        }
        Ok(data)
    }

    pub fn overlay_svg(&mut self, svg: &str) -> RenderResult<()> {
        if svg.is_empty() {
            return Ok(());
        }
        let mut options = resvg::usvg::Options::default();
        let font_family = default_font_family();
        options.font_family = font_family.to_string();
        options.fontdb = font_database().clone();
        let tree = resvg::usvg::Tree::from_str(svg, &options).map_err(|exc| {
            RenderError::Invalid(format!("failed to parse native text SVG: {exc}"))
        })?;
        resvg::render(&tree, Transform::identity(), &mut self.pixmap.as_mut());
        Ok(())
    }
}

fn font_database() -> &'static Arc<resvg::usvg::fontdb::Database> {
    static FONT_DB: OnceLock<Arc<resvg::usvg::fontdb::Database>> = OnceLock::new();
    FONT_DB.get_or_init(|| {
        let font_family = default_font_family();
        let mut fontdb = resvg::usvg::fontdb::Database::new();
        fontdb.load_system_fonts();
        fontdb.set_sans_serif_family(font_family);
        Arc::new(fontdb)
    })
}

fn default_font_family() -> &'static str {
    #[cfg(target_os = "windows")]
    {
        "Arial"
    }
    #[cfg(target_os = "macos")]
    {
        "Helvetica"
    }
    #[cfg(all(not(target_os = "windows"), not(target_os = "macos")))]
    {
        "Liberation Sans"
    }
}

pub fn finish_chart(
    svg: SvgDocument,
    mut raster: RasterCanvas,
    width: u32,
    height: u32,
) -> RenderResult<RenderedChart> {
    let (svg, primitive_count) = svg.finish();
    raster.overlay_svg(&svg)?;
    let png_bytes = raster.encode_png()?;
    Ok(RenderedChart {
        png_bytes,
        svg,
        width,
        height,
        primitive_count,
    })
}

pub fn render_surface(common: &CommonSpec) -> RenderResult<(SvgDocument, RasterCanvas, u32, u32)> {
    let width = common.canvas.width.round().max(1.0) as u32;
    let height = common.canvas.height.round().max(1.0) as u32;
    let mut svg = SvgDocument::new(width, height, &common.background);
    let mut raster = RasterCanvas::new(width, height, &common.background)?;
    svg.rect(common.plot_rect, "#ffffff", "#d1d5db", 1.0, 1.0);
    raster.rect(common.plot_rect, "#ffffff", "#d1d5db", 1.0, 1.0);
    if let Some(title) = &common.title {
        svg.text(title);
    }
    Ok((svg, raster, width, height))
}

pub fn draw_axes(svg: &mut SvgDocument, raster: &mut RasterCanvas, common: &CommonSpec) {
    let transform = ChartTransform::from_common(common);
    let plot = common.plot_rect;
    for axis in &common.axes {
        if axis.orientation == "x" {
            for (idx, tick) in axis.tick_values.iter().enumerate() {
                let x = transform.x.map(*tick);
                let p0 = Point { x, y: plot.y };
                let p1 = Point {
                    x,
                    y: plot.y + plot.height,
                };
                svg.line(p0, p1, "#e5e7eb", 0.7, &[], 1.0);
                raster.line(p0, p1, "#e5e7eb", 0.7, 1.0);
                svg.text(&TextSpec {
                    text: axis
                        .tick_labels
                        .get(idx)
                        .cloned()
                        .unwrap_or_else(|| fmt(*tick)),
                    x,
                    y: plot.y + plot.height + 17.0,
                    font_size: 10.0,
                    fill: "#374151".to_string(),
                    align: "center".to_string(),
                    baseline: "middle".to_string(),
                    weight: "normal".to_string(),
                    coordinate_space_x: "canvas".to_string(),
                    coordinate_space_y: "canvas".to_string(),
                });
            }
            let p0 = Point {
                x: plot.x,
                y: plot.y + plot.height,
            };
            let p1 = Point {
                x: plot.x + plot.width,
                y: plot.y + plot.height,
            };
            svg.line(p0, p1, "#374151", 1.0, &[], 1.0);
            raster.line(p0, p1, "#374151", 1.0, 1.0);
            svg.text(&TextSpec {
                text: axis.label.clone(),
                x: plot.x + plot.width * 0.5,
                y: common.canvas.height - 18.0,
                font_size: 12.0,
                fill: "#111827".to_string(),
                align: "center".to_string(),
                baseline: "middle".to_string(),
                weight: "normal".to_string(),
                coordinate_space_x: "canvas".to_string(),
                coordinate_space_y: "canvas".to_string(),
            });
        } else if axis.orientation == "y" {
            for (idx, tick) in axis.tick_values.iter().enumerate() {
                let y = transform.y.map(*tick);
                let p0 = Point { x: plot.x, y };
                let p1 = Point {
                    x: plot.x + plot.width,
                    y,
                };
                svg.line(p0, p1, "#e5e7eb", 0.7, &[], 1.0);
                raster.line(p0, p1, "#e5e7eb", 0.7, 1.0);
                svg.text(&TextSpec {
                    text: axis
                        .tick_labels
                        .get(idx)
                        .cloned()
                        .unwrap_or_else(|| fmt(*tick)),
                    x: plot.x - 8.0,
                    y,
                    font_size: 10.0,
                    fill: "#374151".to_string(),
                    align: "right".to_string(),
                    baseline: "middle".to_string(),
                    weight: "normal".to_string(),
                    coordinate_space_x: "canvas".to_string(),
                    coordinate_space_y: "canvas".to_string(),
                });
            }
            let p0 = Point {
                x: plot.x,
                y: plot.y,
            };
            let p1 = Point {
                x: plot.x,
                y: plot.y + plot.height,
            };
            svg.line(p0, p1, "#374151", 1.0, &[], 1.0);
            raster.line(p0, p1, "#374151", 1.0, 1.0);
            svg.text(&TextSpec {
                text: axis.label.clone(),
                x: 16.0,
                y: plot.y + plot.height * 0.5,
                font_size: 12.0,
                fill: "#111827".to_string(),
                align: "center".to_string(),
                baseline: "middle".to_string(),
                weight: "normal".to_string(),
                coordinate_space_x: "canvas".to_string(),
                coordinate_space_y: "canvas".to_string(),
            });
        }
    }
}

pub fn draw_line_spec(
    svg: &mut SvgDocument,
    raster: &mut RasterCanvas,
    transform: ChartTransform,
    line: &LineSpec,
) {
    let (p0, p1) = if line.coordinate_space == "canvas" {
        (
            Point {
                x: line.x0,
                y: line.y0,
            },
            Point {
                x: line.x1,
                y: line.y1,
            },
        )
    } else {
        (
            transform.map(line.x0, line.y0),
            transform.map(line.x1, line.y1),
        )
    };
    svg.line(p0, p1, &line.stroke, line.stroke_width, &line.dash, 1.0);
    raster.line(p0, p1, &line.stroke, line.stroke_width, 1.0);
    if !line.label.is_empty() {
        svg.text(&TextSpec {
            text: line.label.clone(),
            x: p1.x + 4.0,
            y: p1.y + 11.0,
            font_size: 10.0,
            fill: line.stroke.clone(),
            align: "left".to_string(),
            baseline: "middle".to_string(),
            weight: "normal".to_string(),
            coordinate_space_x: "canvas".to_string(),
            coordinate_space_y: "canvas".to_string(),
        });
    }
}

pub fn draw_text_spec(svg: &mut SvgDocument, transform: ChartTransform, text: &TextSpec) {
    let mut mapped = text.clone();
    if text.coordinate_space_x == "data" {
        mapped.x = transform.x.map(text.x);
    } else if text.coordinate_space_x == "axes" {
        mapped.x = transform.plot.x + text.x * transform.plot.width;
    }
    if text.coordinate_space_y == "data" {
        mapped.y = transform.y.map(text.y);
    } else if text.coordinate_space_y == "axes" {
        mapped.y = transform.plot.y + transform.plot.height - text.y * transform.plot.height;
    }
    svg.text(&mapped);
}

pub fn marker_point(transform: ChartTransform, x: f64, y: f64, coordinate_space: &str) -> Point {
    if coordinate_space == "canvas" {
        Point { x, y }
    } else {
        transform.map(x, y)
    }
}

pub fn fmt(value: f64) -> String {
    let mut text = format!("{value:.3}");
    while text.contains('.') && text.ends_with('0') {
        text.pop();
    }
    if text.ends_with('.') {
        text.pop();
    }
    if text == "-0" {
        "0".to_string()
    } else {
        text
    }
}

fn dash_attr(dash: &[f64]) -> String {
    dash.iter()
        .map(|item| fmt(*item))
        .collect::<Vec<_>>()
        .join(" ")
}

fn escape(value: &str) -> String {
    value
        .replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

fn anchor(align: &str) -> &'static str {
    match align {
        "center" => "middle",
        "right" => "end",
        _ => "start",
    }
}

fn baseline(value: &str) -> &'static str {
    match value {
        "top" => "text-before-edge",
        "middle" => "central",
        "bottom" => "text-after-edge",
        _ => "auto",
    }
}

fn sanitize_color(color: &str) -> String {
    if color == "none" {
        return "none".to_string();
    }
    if parse_hex_color(color).is_some() {
        return color.to_string();
    }
    "#111827".to_string()
}

fn paint(color_text: &str, opacity: f64) -> Paint<'static> {
    let mut paint = Paint::default();
    paint.set_color(color(color_text, opacity));
    paint
}

fn color(color_text: &str, opacity: f64) -> tiny_skia::Color {
    let (r, g, b) = parse_hex_color(color_text).unwrap_or((17, 24, 39));
    tiny_skia::Color::from_rgba8(r, g, b, (opacity.clamp(0.0, 1.0) * 255.0).round() as u8)
}

fn parse_hex_color(color: &str) -> Option<(u8, u8, u8)> {
    let hex = color.strip_prefix('#')?;
    if hex.len() == 6 {
        return Some((
            u8::from_str_radix(&hex[0..2], 16).ok()?,
            u8::from_str_radix(&hex[2..4], 16).ok()?,
            u8::from_str_radix(&hex[4..6], 16).ok()?,
        ));
    }
    if hex.len() == 3 {
        return Some((
            u8::from_str_radix(&hex[0..1].repeat(2), 16).ok()?,
            u8::from_str_radix(&hex[1..2].repeat(2), 16).ok()?,
            u8::from_str_radix(&hex[2..3].repeat(2), 16).ok()?,
        ));
    }
    None
}

fn stroke_style(width: f64) -> Stroke {
    let mut stroke = Stroke::default();
    stroke.width = width.max(0.1) as f32;
    stroke
}

pub fn png_compression_label() -> &'static str {
    match std::env::var("HEXAFE_PLOTSTATS_NATIVE_PNG_COMPRESSION")
        .ok()
        .as_deref()
    {
        Some("fastest") => "fastest",
        Some("fast") => "fast",
        Some("balanced") => "balanced",
        Some("high") => "high",
        _ => "none",
    }
}

fn png_compression() -> png::Compression {
    match png_compression_label() {
        "fastest" => png::Compression::Fastest,
        "fast" => png::Compression::Fast,
        "balanced" => png::Compression::Balanced,
        "high" => png::Compression::High,
        _ => png::Compression::NoCompression,
    }
}

fn blend_pixel(pixel: &mut [u8], red: u8, green: u8, blue: u8, opacity: f64) {
    let src_alpha = (opacity.clamp(0.0, 1.0) * 255.0).round() as u32;
    if src_alpha == 0 {
        return;
    }
    let inv_alpha = 255 - src_alpha;
    let src_red = (red as u32 * src_alpha + 127) / 255;
    let src_green = (green as u32 * src_alpha + 127) / 255;
    let src_blue = (blue as u32 * src_alpha + 127) / 255;
    pixel[0] = (src_red + (pixel[0] as u32 * inv_alpha + 127) / 255).min(255) as u8;
    pixel[1] = (src_green + (pixel[1] as u32 * inv_alpha + 127) / 255).min(255) as u8;
    pixel[2] = (src_blue + (pixel[2] as u32 * inv_alpha + 127) / 255).min(255) as u8;
    pixel[3] = (src_alpha + (pixel[3] as u32 * inv_alpha + 127) / 255).min(255) as u8;
}
