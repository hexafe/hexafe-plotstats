use crate::spec::{RenderError, RenderResult, TextSpec};
use fontdb::{Database, Family, Query, Stretch, Style, Weight};
use std::collections::HashMap;
use std::sync::{Mutex, OnceLock};
use tiny_skia::{FillRule, Paint, Path, PathBuilder, Pixmap, Transform};
use ttf_parser::{Face, OutlineBuilder};

#[derive(Clone)]
struct FontFaceData {
    data: Vec<u8>,
    index: u32,
}

struct FontSet {
    normal: FontFaceData,
    semibold: FontFaceData,
}

#[derive(Clone, Eq, Hash, PartialEq)]
struct TextPathKey {
    semibold: bool,
    text: String,
}

#[derive(Clone)]
struct TextPath {
    path: Path,
    advance_units: f64,
}

pub fn render_texts(pixmap: &mut Pixmap, texts: &[TextSpec]) -> RenderResult<bool> {
    if texts.is_empty() {
        return Ok(true);
    }
    if std::env::var("HEXAFE_PLOTSTATS_NATIVE_TEXT")
        .map(|value| value.eq_ignore_ascii_case("resvg"))
        .unwrap_or(false)
    {
        return Ok(false);
    }

    let Some(fonts) = font_set() else {
        return Ok(false);
    };

    for text in texts {
        render_text(pixmap, text, fonts)?;
    }
    Ok(true)
}

fn font_set() -> Option<&'static FontSet> {
    static FONT_SET: OnceLock<Option<FontSet>> = OnceLock::new();
    FONT_SET
        .get_or_init(|| {
            let mut database = Database::new();
            database.load_system_fonts();
            database.set_sans_serif_family(default_font_family());
            let normal = load_face(&database, Weight::NORMAL)?;
            let semibold = load_face(&database, Weight::SEMIBOLD).unwrap_or_else(|| normal.clone());
            Some(FontSet { normal, semibold })
        })
        .as_ref()
}

fn load_face(database: &Database, weight: Weight) -> Option<FontFaceData> {
    let query = Query {
        families: &[Family::SansSerif],
        weight,
        stretch: Stretch::Normal,
        style: Style::Normal,
    };
    let id = database
        .query(&query)
        .or_else(|| database.faces().next().map(|face| face.id))?;
    database.with_face_data(id, |data, index| FontFaceData {
        data: data.to_vec(),
        index,
    })
}

fn render_text(pixmap: &mut Pixmap, text: &TextSpec, fonts: &FontSet) -> RenderResult<()> {
    if text.text.is_empty() || text.font_size <= 0.0 {
        return Ok(());
    }

    let (face_data, semibold) = face_data_for(text, fonts);
    let face = Face::parse(&face_data.data, face_data.index)
        .map_err(|exc| RenderError::Invalid(format!("failed to parse native text font: {exc}")))?;
    let units = f64::from(face.units_per_em()).max(1.0);
    let scale = text.font_size / units;
    let Some(text_path) = text_path(&face, &text.text, semibold) else {
        return Ok(());
    };
    let text_width = text_path.advance_units * scale;
    let cursor_x = match text.align.as_str() {
        "center" => text.x - text_width * 0.5,
        "right" => text.x - text_width,
        _ => text.x,
    };
    let baseline_y = baseline_y(&face, text, scale);
    let paint = text_paint(&text.fill);
    let transform = Transform::from_row(
        scale as f32,
        0.0,
        0.0,
        -scale as f32,
        cursor_x as f32,
        baseline_y as f32,
    );
    pixmap.fill_path(&text_path.path, &paint, FillRule::Winding, transform, None);

    Ok(())
}

fn face_data_for<'a>(text: &TextSpec, fonts: &'a FontSet) -> (&'a FontFaceData, bool) {
    if text
        .weight
        .parse::<u16>()
        .map(|weight| weight >= 600)
        .unwrap_or_else(|_| text.weight.eq_ignore_ascii_case("bold"))
    {
        (&fonts.semibold, true)
    } else {
        (&fonts.normal, false)
    }
}

fn baseline_y(face: &Face<'_>, text: &TextSpec, scale: f64) -> f64 {
    let ascender = f64::from(face.ascender());
    let descender = f64::from(face.descender());
    match text.baseline.as_str() {
        "top" => text.y + ascender * scale,
        "middle" => text.y + (ascender + descender) * scale * 0.5,
        "bottom" => text.y + descender * scale,
        _ => text.y,
    }
}

fn text_path(face: &Face<'_>, text: &str, semibold: bool) -> Option<TextPath> {
    let key = TextPathKey {
        semibold,
        text: text.to_string(),
    };
    let cache = text_path_cache();
    if let Some(path) = cache.lock().ok()?.get(&key).cloned() {
        return path;
    }

    let mut builder = GlyphPathBuilder {
        builder: PathBuilder::new(),
        offset_x: 0.0,
    };
    let mut advance_units = 0.0;
    for ch in text.chars() {
        let Some(glyph_id) = face.glyph_index(ch) else {
            continue;
        };
        builder.offset_x = advance_units as f32;
        let _ = face.outline_glyph(glyph_id, &mut builder);
        advance_units += f64::from(face.glyph_hor_advance(glyph_id).unwrap_or(0));
    }
    let path = builder.builder.finish().map(|path| TextPath {
        path,
        advance_units,
    });
    if let Ok(mut cache) = cache.lock() {
        cache.insert(key, path.clone());
    }
    path
}

fn text_path_cache() -> &'static Mutex<HashMap<TextPathKey, Option<TextPath>>> {
    static TEXT_PATH_CACHE: OnceLock<Mutex<HashMap<TextPathKey, Option<TextPath>>>> =
        OnceLock::new();
    TEXT_PATH_CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

struct GlyphPathBuilder {
    builder: PathBuilder,
    offset_x: f32,
}

impl OutlineBuilder for GlyphPathBuilder {
    fn move_to(&mut self, x: f32, y: f32) {
        self.builder.move_to(x + self.offset_x, y);
    }

    fn line_to(&mut self, x: f32, y: f32) {
        self.builder.line_to(x + self.offset_x, y);
    }

    fn quad_to(&mut self, x1: f32, y1: f32, x: f32, y: f32) {
        self.builder
            .quad_to(x1 + self.offset_x, y1, x + self.offset_x, y);
    }

    fn curve_to(&mut self, x1: f32, y1: f32, x2: f32, y2: f32, x: f32, y: f32) {
        self.builder.cubic_to(
            x1 + self.offset_x,
            y1,
            x2 + self.offset_x,
            y2,
            x + self.offset_x,
            y,
        );
    }

    fn close(&mut self) {
        self.builder.close();
    }
}

fn text_paint(fill: &str) -> Paint<'static> {
    let mut paint = Paint::default();
    let (red, green, blue) = parse_hex_color(fill).unwrap_or((17, 24, 39));
    paint.set_color_rgba8(red, green, blue, 255);
    paint.anti_alias = true;
    paint
}

fn parse_hex_color(value: &str) -> Option<(u8, u8, u8)> {
    let raw = value.strip_prefix('#')?;
    if raw.len() != 6 {
        return None;
    }
    let red = u8::from_str_radix(&raw[0..2], 16).ok()?;
    let green = u8::from_str_radix(&raw[2..4], 16).ok()?;
    let blue = u8::from_str_radix(&raw[4..6], 16).ok()?;
    Some((red, green, blue))
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
