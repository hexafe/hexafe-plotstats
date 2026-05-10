# Rust renderer implementation plan

Last updated: 2026-05-10

## Live progress

- 2026-05-10: Started full Rust renderer implementation.
- 2026-05-10: Completed the first contract-hardening step by adding
  `schema_version` to resolved chart mappings and capability regression coverage
  for missing, one-sided, and two-sided specification limits.
- 2026-05-10: Validated the first contract-hardening step with
  `python -m pytest tests/test_adapters.py tests/test_renderer_backends.py -q`
  (`33 passed`) and `python -m compileall -q src tests examples`.
- 2026-05-10: Added the initial optional PyO3/maturin native package scaffold
  at `native/hexafe-plotstats-native`, built an abi3 wheel, installed it into a
  temporary target directory, and verified that Python can call
  `render_histogram_png(...)` through the existing backend loader.
- 2026-05-10: Completed a Matplotlib/resolved-spec parity audit. The updated
  implementation plan now treats hexbin scatter geometry, violin density
  polygons, and horizontal IQR/violin spec-limit semantics as required before
  strict 1:1 parity claims.
- 2026-05-10: Integrated the native Rust source split under
  `native/hexafe-plotstats-native/src/` (`spec`, `svg`, and per-chart modules),
  with PyO3 entry points for histogram, scatter, scatter trend, IQR, and
  violin PNG rendering.
- 2026-05-10: Switched the Python/native handoff to compact JSON when the
  installed native module advertises `ACCEPTS_JSON_SPEC`, while keeping mapping
  dispatch compatible with tests and alternate native modules.
- 2026-05-10: Added native smoke tests, deterministic resolved-spec JSON
  fixtures, and `scripts/benchmark_renderers.py` for Matplotlib-vs-Rust PNG
  timing.
- 2026-05-10: Replaced the first full-SVG render path with a hybrid renderer:
  tiny-skia draws chart marks directly, resvg overlays text labels, and PNG
  encoding uses speed-first compression.
- 2026-05-10: Corrected Matplotlib IQR/violin spec-limit semantics to horizontal
  y-value lines and added regression coverage.
- 2026-05-10: Made PNG compression configurable through
  `HEXAFE_PLOTSTATS_NATIVE_PNG_COMPRESSION` (`none`, `fastest`, `fast`,
  `balanced`, `high`), with speed-first `none` as the current native default.
- 2026-05-10: Latest equal-canvas benchmark
  (`PYTHONPATH=/tmp/hexafe_plotstats_native_hexbin:src python scripts/benchmark_renderers.py --repeats 5 --warmups 1`):
  histogram Matplotlib 151.20 ms vs Rust 161.12 ms, scatter 148.28 ms vs Rust
  146.72 ms, IQR 74.80 ms vs Rust 71.14 ms, violin 186.38 ms vs Rust
  165.95 ms.
- 2026-05-10: Added explicit violin body polygons and scatter hexbin cells to
  the resolved schema. Matplotlib now consumes those same resolved polygons,
  and Rust renders the same polygons instead of recomputing chart-specific
  shapes independently.
- 2026-05-10: Applied resolved canvas, plot rectangle, axis limits, and ticks to
  Matplotlib renderers. Added native visual parity smoke coverage that compares
  equal-size Matplotlib and Rust PNGs with an image-difference threshold.
- 2026-05-10: Promoted the Rust backend flag from unavailable stubs to the
  native PNG renderer when `_hexafe_plotstats_native` is installed. The
  Matplotlib backend remains the default, and Rust still reports
  `RendererBackendUnavailable` when the native module is absent.
- 2026-05-10: Ported Metroliza-style histogram summary rows into standalone
  payloads: Min/Max/Mean/Median/Std Dev, Cp/Cpk or Cpu/Cpl, NOK with side
  split, NOK %, Samples with low-n metadata, Normality, Model, Est. NOK %, Fit
  quality, and Warning rows. Matplotlib and Rust render table section breaks and
  row badges from the same resolved table metadata.
- 2026-05-10: Added `scripts/compare_renderers.py` for repeatable
  Matplotlib-vs-Rust PNG comparisons. Latest run:
  `PYTHONPATH=/tmp/hexafe_plotstats_native_current:src python scripts/compare_renderers.py --output /tmp/hexafe_plotstats_renderer_comparisons --threshold 15`
  passed for histogram, scatter, scatter trend, IQR, and violin. Mean absolute
  differences: histogram 6.560, scatter 3.923, scatter trend 6.564, IQR 6.393,
  violin 4.557.
- 2026-05-10: Latest benchmark run:
  `PYTHONPATH=/tmp/hexafe_plotstats_native_current:src python scripts/benchmark_renderers.py --repeats 7 --warmups 2`
  measured histogram Matplotlib 176.69 ms / Rust 258.39 ms, scatter 109.17 ms /
  Rust 169.59 ms, IQR 73.34 ms / Rust 101.98 ms, violin 170.00 ms / Rust
  164.98 ms. Rust is functional and parity-green, but the current text overlay
  and PNG encoding path is not yet faster for every chart.

## Goal

Build a full Rust rendering implementation for `hexafe-plotstats` while keeping
Matplotlib as the default backend until Rust output is fast, packaged, and close
enough to the current Matplotlib output.

The intended end state is:

- Python remains the public API and statistical payload layer.
- Rust owns chart rendering for all supported chart families.
- Matplotlib remains available as a fallback, debug path, and parity oracle.
- The Rust renderer returns image bytes and render metadata without importing
  matplotlib, Qt, workbook code, or Metroliza runtime modules.
- The package can still be installed without Rust/native dependencies unless
  the user opts into the native renderer.

## Recommendation

Use a staged Rust renderer, not a large third-party chart framework.

The first production candidate should be:

```text
Resolved Python payload/spec mapping -> Rust serde structs -> tiny-skia marks
with resvg text overlay -> PNG bytes
```

Reasoning:

- The project already has its own resolved chart spec boundary.
- The Rust renderer should draw resolved primitives, not decide chart layout
  independently.
- `tiny-skia` gives direct, dependency-light raster drawing for bars, lines,
  boxes, polygons, and high-volume scatter markers.
- `resvg` remains useful for text rendering and optional debug SVG output.
- The hybrid path is materially faster than full SVG rendering and still keeps
  a deterministic resolved-spec contract.

Plotters should be kept as a short comparison spike only. It is a strong Rust
plotting library, but using its high-level chart layout would create a second
layout engine and make 1:1 Matplotlib parity harder.

## Research basis

- PyO3 provides Rust bindings for Python extension modules:
  https://pyo3.rs/
- Maturin supports PyO3 bindings and wheel building:
  https://www.maturin.rs/bindings
- `resvg` renders static SVG files as a Rust library/CLI and uses `tiny-skia`:
  https://docs.rs/crate/resvg/latest
- `tiny-skia` exposes a `Pixmap` with PNG encode/save and path fill/stroke
  primitives:
  https://doc.servo.org/tiny_skia/pixmap/struct.Pixmap.html
- Plotters is a pure-Rust plotting/drawing library with bitmap, SVG, and other
  backends:
  https://docs.rs/plotters/latest/plotters/

## Current state

`hexafe-plotstats` already has the correct Python-side seam:

- `backend="matplotlib"` is implemented and remains default.
- `backend="rust"` is explicit and becomes available when
  `_hexafe_plotstats_native`/`hexafe_plotstats_native` is installed.
- `render_histogram_png(...)`, `render_violin_png(...)`,
  `render_iqr_png(...)`, `render_scatter_png(...)`, and
  `render_scatter_trend_png(...)` are the byte-oriented native targets.
- The Rust loader searches for `_hexafe_plotstats_native` or
  `hexafe_plotstats_native`.
- The PNG helpers resolve payloads to mappings and pass compact JSON to native
  modules that advertise `ACCEPTS_JSON_SPEC`.
- The working-tree resolved-spec layer includes histogram, violin, IQR, and
  scatter helpers plus deterministic fixture snapshots.

## Architecture

### Python core package

Keep the pure-Python package installable without native code:

```text
hexafe_plotstats/
  models/
  stats/
  payloads/
  specs/
  renderers/
    matplotlib/
    rust/
```

Responsibilities:

- Build and validate statistical payloads.
- Keep Matplotlib rendering as the default figure-returning backend.
- Resolve payloads into JSON-friendly chart specs.
- Probe native availability and surface clear fallback errors.
- Keep renderer capabilities visible through
  `renderer_backend_capabilities()`.

### Native Rust distribution

Prefer a separate optional Python distribution:

```text
native/hexafe-plotstats-native/
  pyproject.toml
  Cargo.toml
  src/lib.rs
  src/spec.rs
  src/svg.rs
  src/render.rs
  src/charts/
```

It should build a Python extension module named `_hexafe_plotstats_native`.

Reasons to keep it separate:

- `pip install hexafe-plotstats` stays pure Python.
- Native wheels can be built and released independently.
- Core package import never depends on Rust, maturin, or platform wheel support.
- The existing Python loader already supports this layout.

Later, the core package can expose:

```toml
[project.optional-dependencies]
rust = ["hexafe-plotstats-native==<matching-version>"]
```

### Native API

Keep the first public native API narrow:

```python
render_histogram_png(mapping: dict) -> dict
render_scatter_png(mapping: dict) -> dict
render_scatter_trend_png(mapping: dict) -> dict
render_iqr_png(mapping: dict) -> dict
render_violin_png(mapping: dict) -> dict
```

Return shape:

```python
{
    "png_bytes": b"...",
    "backend": "rust",
    "metadata": {
        "chart": "histogram",
        "renderer": "resvg",
        "schema_version": 1,
        "width": 960,
        "height": 540,
    },
}
```

Add `render_*_svg(mapping)` only as a debug/testing API. It should not be the
main user-facing contract.

## Schema contract

Add an explicit schema version to every resolved mapping before Rust is wired:

```json
{
  "schema_version": 1,
  "chart_type": "histogram",
  "canvas": {},
  "plot_rect": {},
  "axes": [],
  "metadata": {}
}
```

Rules:

- Rust rejects unsupported `schema_version` values with a clear error.
- Python tests snapshot representative mappings as JSON fixtures.
- Rust tests load the same fixtures.
- Additive fields are allowed within a schema version.
- Renames, coordinate changes, or semantic changes require a new schema version.

## Dependency choices

### Required native dependencies

- `pyo3`: Python extension boundary.
- `serde`, `serde_json`: parse Python mappings into Rust structs.
- `thiserror`: renderer error typing.
- `resvg`, `usvg`, `tiny-skia`: SVG-to-PNG render path.

### Optional or later dependencies

- `plotters`: comparison spike only.
- `png` or `image`: test-only PNG decoding if Python-side tests are not enough.
- Direct `tiny-skia` drawing: later performance renderer after SVG parity.

### Avoid in the core native path

- Browser/WebDriver-based renderers.
- Plotly/ECharts/Vega runtimes for static PNG generation.
- Matplotlib or Python callbacks inside Rust.
- Qt/workbook/Metroliza imports.
- GPU-only stacks for the first implementation.

## Phase 0: freeze current contract

Status: complete for schema v1. `schema_version`, capability regression
coverage, and deterministic JSON fixture snapshots are implemented and
validated.

1. Commit or otherwise preserve current resolved-spec work.
2. Run:

```bash
python -m pytest -q
python -m compileall -q src tests examples
```

3. Add direct capability regression tests:
   - no spec limits
   - LSL only
   - USL only
   - two-sided limits
4. Add JSON snapshot fixtures:
   - simple histogram
   - Metroliza-style enriched histogram
   - scatter with trend
   - IQR with outliers
   - violin with multiple groups
5. Add a schema-version field to the mapping output.

Acceptance:

- Existing tests pass.
- Snapshot fixtures are deterministic across runs.
- `json.dumps(to_mapping(...), sort_keys=True)` is stable.

## Phase 1: native package scaffold

Status: complete. The native package builds an abi3 wheel and exposes the
planned chart PNG entry points. The current implementation renders all four
chart families from resolved specs.

Create `native/hexafe-plotstats-native`.

Initial files:

```text
native/hexafe-plotstats-native/pyproject.toml
native/hexafe-plotstats-native/Cargo.toml
native/hexafe-plotstats-native/src/lib.rs
native/hexafe-plotstats-native/src/error.rs
native/hexafe-plotstats-native/src/spec.rs
native/hexafe-plotstats-native/src/render.rs
```

Expose:

```rust
#[pyfunction]
fn render_histogram_png(py: Python<'_>, mapping: &Bound<'_, PyAny>) -> PyResult<PyObject>;
```

Implementation for the first scaffold:

- Parse Python mapping to `serde_json::Value`.
- Validate `chart_type == "histogram"`.
- Return a tiny valid PNG generated from a blank canvas.
- Include metadata.

Acceptance:

- `maturin develop` installs `_hexafe_plotstats_native` locally.
- `renderer_backend_available("rust")` becomes true when installed.
- `render_histogram_png(payload)` returns valid PNG bytes.
- Existing unavailable behavior still works when the native package is absent.

## Phase 2: Rust spec model

Mirror the resolved Python primitives in Rust:

```rust
struct Canvas { size: Size, background: String }
struct Rect { x: f64, y: f64, width: f64, height: f64 }
struct TextSpec { text: String, x: f64, y: f64, ... }
struct AxisSpec { orientation: String, minimum: f64, maximum: f64, ... }
struct LineSpec { x0: f64, y0: f64, x1: f64, y1: f64, ... }
struct BarSpec { x0: f64, x1: f64, y0: f64, y1: f64, ... }
struct CurveSpec { x: Vec<f64>, y: Vec<f64>, ... }
```

Add chart-specific structs:

- `HistogramSpec`
- `ScatterSpec`
- `IqrSpec`
- `ViolinSpec`

Validation rules:

- finite numeric coordinates only
- positive canvas dimensions
- non-negative stroke widths
- valid plot rectangle
- valid RGB/hex colors or fallback color
- no panics on missing optional metadata

Acceptance:

- Rust unit tests parse all Python snapshot fixtures.
- Invalid specs return Python `ValueError` with useful messages.
- Unknown optional fields are ignored.

## Phase 3: common rendering primitives

Implement shared geometry helpers before chart-specific code:

- coordinate transforms: data -> pixel
- plot-area clipping
- color parsing
- stroke style and dash conversion
- text anchor/baseline mapping
- path generation for curves
- axis/tick drawing
- title drawing
- warning metadata propagation

The current renderer uses direct raster drawing for chart marks and a small SVG
overlay for text:

```text
Spec primitives -> tiny-skia pixmap + SVG text overlay via resvg -> PNG bytes
```

Keep SVG output deterministic:

- stable element ordering
- fixed float formatting
- no timestamps
- no random IDs
- stable font family list

Acceptance:

- a debug SVG from the same spec is byte-stable across runs.
- PNG dimensions match the requested canvas.
- image is nonblank for representative fixtures.

## Phase 4: histogram renderer

Status: implemented for current resolved spec. Strict pixel parity is not yet
claimed because the Matplotlib renderer and Rust renderer still use different
layout engines and table/text metrics.

Implement histogram completely first.

Required primitives:

- canvas background
- title
- plot rectangle
- x/y axes
- tick labels
- bars
- fit curve
- KDE curve
- LSL/nominal/USL lines
- mean line
- annotations
- summary table
- warning metadata

Testing:

- unit tests for Rust SVG element generation
- Python integration test for `render_histogram_png`
- nonblank PNG test
- structural test that output changes when bars/spec lines change
- visual parity comparison against Matplotlib oracle

Benchmark cases:

- small histogram: 50 values
- normal report histogram: 1k-10k values
- large histogram: 100k+ values, with rendering measured after payload/spec build

Acceptance:

- Rust histogram renders every snapshot fixture.
- Rust output is visibly equivalent to Matplotlib for the current report style.
- Rust render time is consistently below Matplotlib render time for PNG export.

## Phase 5: scatter and trend renderer

Status: implemented for normal scatter, trend line, and hexbin cells. The hot
path batches uniform markers and stamps fill-only markers directly into the
pixmap. Hexbin cells are explicit in schema v1 and both Matplotlib and Rust draw
the resolved cell polygons.

Implement scatter second because speed impact is likely highest.

Strict parity requirement: before claiming scatter parity, represent hexbin
cells explicitly in the resolved spec. The current scatter resolver preserves
the mode metadata but still emits point markers, which is not enough to match
Matplotlib hexbin output.

Required primitives:

- markers
- optional trend line
- axes and labels
- large-dataset style metadata
- opacity
- simplified annotation policy

Performance rules:

- Batch SVG marker generation where possible.
- For very large scatter plots, consider direct `tiny-skia` raster paths earlier
  than for other chart families.
- Preserve current scatter mode policy semantics from Python.

Acceptance:

- normal scatter renders.
- rasterized/large scatter cases render without excessive memory growth.
- trend line matches Matplotlib oracle within tolerance.
- large scatter shows a clear speedup over Matplotlib PNG export.

## Phase 6: IQR renderer

Status: implemented for boxes, whiskers, outliers, labels, and horizontal
spec-limit lines. Matplotlib has been corrected to use horizontal y-value
spec-limit lines for IQR, matching the resolved-spec semantics.

Implement boxplot/IQR after scatter.

Strict parity requirement: specification limits for IQR are y-value limits and
must render as horizontal lines. The current shared Matplotlib helper draws
vertical `axvline(...)` markers, so either the Matplotlib renderer needs a
horizontal-limit fix or Rust must explicitly preserve the current bug until the
oracle is corrected. The preferred path is to correct Matplotlib and Rust to the
resolved-spec horizontal semantics together.

Required primitives:

- boxes
- whiskers
- median lines
- outlier markers
- group labels
- spec lines
- axes

Acceptance:

- multiple groups render.
- outliers render at the right positions.
- spec lines match Matplotlib output.
- empty/degenerate groups do not panic.

## Phase 7: violin renderer

Status: implemented for grouped violin bodies, summary markers, extrema, labels,
and horizontal spec-limit lines. Violin body polygons are explicit in schema v1
and both Matplotlib and Rust draw those resolved polygons.

Violin is last because density/shape parity is more sensitive.

Strict parity requirement: before claiming violin body parity, add explicit
violin density/outline polygons to the resolved spec. Raw group values and
summary markers are enough for semantic tests, but not enough to reproduce the
KDE-shaped Matplotlib body.

Near-term approach:

- Keep Python responsible for resolved group values and summary metadata.
- Add explicit violin outline/density polygons to the resolved spec before Rust
  renderer parity work begins.
- Rust draws polygons, summary markers, quartile/median markers, and spec lines.

Later full-Rust approach:

- Port violin density generation into Rust after Python and Rust outputs match.
- Keep the same resolved polygon output so tests continue to compare the same
  rendering contract.

Acceptance:

- grouped violins render.
- means/quartiles/medians match the current semantic positions.
- output is visually close enough for report/dashboard use.

## Phase 8: direct renderer performance path

Status: partially complete. Direct tiny-skia rendering is now the default native
path for marks. PNG encoding is configurable through
`HEXAFE_PLOTSTATS_NATIVE_PNG_COMPRESSION`; the default is currently speed-first
and produces larger PNGs.

After `resvg` parity is green, decide whether direct `tiny-skia` is needed.

Use direct `tiny-skia` for:

- high-volume scatter markers
- simple bars/lines where SVG serialization overhead is measurable
- potentially full histogram rendering if it gives meaningful speedup

Keep SVG/resvg for:

- debug output
- fallback native renderer
- complex text/table rendering until direct text handling is mature

Acceptance:

- direct path is faster on measured hot cases.
- direct path and SVG path pass the same semantic tests.
- direct path does not regress text/table quality.

## Phase 9: move geometry/layout into Rust

At this point, Rust draws all chart families from resolved specs. The next step
toward a fuller Rust implementation is moving chart geometry resolution into
Rust.

Order:

1. histogram geometry
2. scatter/trend geometry
3. IQR geometry
4. violin density/polygon geometry
5. shared tick generation
6. shared table layout

Keep Python and Rust geometry in parallel during migration:

- Python produces current resolved spec.
- Rust can produce an equivalent resolved spec from the payload mapping.
- Tests compare Python-resolved and Rust-resolved specs structurally.

Acceptance:

- Rust-generated resolved specs match Python-generated specs for fixtures.
- Python can choose `resolve="python"` or `resolve="rust"` in tests.
- No user-facing default changes until all chart families pass.

## Phase 10: final Rust rendering API

When Rust owns all chart rendering, expose a clearer public API:

```python
render_histogram_png(payload, backend="rust")
render_scatter_png(payload, backend="rust")
render_iqr_png(payload, backend="rust")
render_violin_png(payload, backend="rust")
```

Keep Matplotlib figure APIs:

```python
render_histogram(payload, backend="matplotlib")
```

Do not make Matplotlib-style figure objects from Rust. Rust should return image
bytes, SVG debug strings, and metadata. If a generic API is needed, add a new
result union instead of pretending PNG bytes are a Matplotlib figure.

## Phase 11: packaging and CI

Native package:

- `hexafe-plotstats-native`
- built with maturin
- module name `_hexafe_plotstats_native`
- Python ABI target: choose `abi3-py310` if compatible with required PyO3
  features and package support policy
- wheels for Windows, macOS, and Linux

Core package:

- keep `hexafe-plotstats` pure Python by default
- add `rust` extra after native wheels are published
- keep clear unavailable-backend messages

CI:

- Python test job without native package
- native Rust unit test job
- `maturin develop` integration job
- wheel build smoke on Windows/macOS/Linux
- image parity job, allowed to be advisory at first

## Phase 12: benchmarks and release gates

Add benchmark scripts that measure:

- payload build time
- Python spec resolution time
- Rust spec parse time
- Rust render time
- Matplotlib render time
- PNG byte size
- peak memory for large scatter

Acceptance gates before calling Rust production-ready:

- all chart families supported
- no native dependency required for pure-Python install
- no Matplotlib import in Rust path
- no Metroliza import in Rust path
- deterministic PNG dimensions and metadata
- visibly correct against Matplotlib oracle
- faster than Matplotlib for PNG/export scenarios that matter
- Windows wheel smoke passes

## Task breakdown

### Slice 1: contract hardening

- Add `schema_version`.
- Add JSON fixtures.
- Add exact capability regression tests.
- Update docs/session state.

### Slice 2: native scaffold

- Add `native/hexafe-plotstats-native`.
- Add PyO3/maturin config.
- Return a blank valid PNG from `render_histogram_png`.
- Wire existing Python loader in tests.

### Slice 3: SVG/resvg primitive renderer

- Parse `HistogramSpec`.
- Generate deterministic SVG.
- Rasterize through `resvg`.
- Return PNG bytes.

### Slice 4: full histogram

- Draw bars, axes, ticks, curves, spec lines, title, annotations, and table.
- Add visual parity and benchmark tests.

### Slice 5: scatter/trend

- Draw markers and trend lines.
- Add large-dataset benchmarks.
- Consider direct `tiny-skia` hot path if SVG is too slow.

### Slice 6: IQR

- Draw boxes, whiskers, medians, outliers, and spec lines.

### Slice 7: violin

- Add explicit violin polygon/outline spec.
- Draw groups and annotations.

### Slice 8: direct renderer

- Add direct `tiny-skia` implementation for measured hot paths.
- Keep SVG as debug/fallback.

### Slice 9: Rust geometry migration

- Move chart geometry resolution into Rust chart by chart.
- Keep Python resolver until Rust resolver parity is proven.

### Slice 10: packaging and default strategy

- Publish native wheels.
- Add `rust` extra.
- Keep Matplotlib default until a release explicitly changes that policy.

## Open decisions

- Whether the native distribution lives inside the same repository or a separate
  repository.
- Whether `abi3-py310` is acceptable for all planned PyO3 interactions.
- Whether image parity tests should use Python-only tools or Rust-side PNG
  decoding.
- Whether direct `tiny-skia` should be implemented only for scatter or for all
  chart families.
- When to flip any export path from Matplotlib to Rust by default.

## Non-goals for the first native milestone

- Do not make Rust the default backend.
- Do not remove Matplotlib.
- Do not port statistics into Rust.
- Do not adopt Plotly/ECharts/Vega/Charton as the core renderer.
- Do not require a browser, WebDriver, Qt, or Metroliza runtime import.
