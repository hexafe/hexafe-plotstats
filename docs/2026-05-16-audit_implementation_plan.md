# Audit Implementation Plan

Date: 2026-05-16

## Scope

This plan reconciles the visible GPT-5.5 Pro audit summary with a fresh local audit of the current repository. The full attached audit files were not available in the workspace, so the external-audit input here is limited to the visible summary topics:

- interactive charts
- theme system
- 1M+ point performance
- axis improvements
- internationalization

Additional user requirement added after the audit: large Plotly scatter exports
must aggregate by default. Temporal buckets (`minute`, `hour`, `day`, `week`)
must be selected automatically from the requested X-axis view and the number of
generated X-axis data points. The interactive Plotly layer should contain only
aggregated data; raw points should be rendered as a static layer for performance
and memory, with a legend entry that lets users hide the raw-data layer.

## Local Audit Baseline

Current repository state is healthy:

- Branch: `codex/resolved-spec-rust-foundation`
- Python validation: `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest -q` -> `44 passed, 10 skipped`
- Compile validation: `python -m compileall -q src tests scripts examples` -> passed
- Rust validation: `cargo fmt --check`, `cargo test --locked` -> passed
- Native wheel build: `python -m maturin build --release --locked --out /tmp/hexafe-plotstats-audit-dist` -> passed, but emitted the expected non-uploadable local Linux wheel warning
- Native-enabled Python validation: `PYTHONPATH=/tmp/hexafe_plotstats_native_audit:src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest -q` -> `54 passed`
- Native `resvg` fallback validation: `PYTHONPATH=/tmp/hexafe_plotstats_native_audit:src HEXAFE_PLOTSTATS_NATIVE_TEXT=resvg MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest tests/test_native_renderer_smoke.py -q` -> `13 passed`
- Renderer comparison: `PYTHONPATH=/tmp/hexafe_plotstats_native_audit:src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python scripts/compare_renderers.py --output /tmp/hexafe_plotstats_audit_comparisons --threshold 15` -> all five comparisons passed

Current strengths:

- The package boundary is clean: core code has no Qt, workbook, Google export, or Metroliza runtime imports.
- Matplotlib remains the stable default backend while Rust is explicit and optional.
- The resolved-spec handoff is the right native boundary for static output parity.
- Native rendering is now functionally real, cross-chart, fast on benchmark fixtures, and guarded by tests plus CI.
- The Metroliza-style histogram adapter path exists and preserves enriched histogram metadata.

## Audit Findings

### 1. 1M+ Point Performance Is Not Solved End-to-End

Rust rendering is fast once it receives a resolved spec, but large scatter resolution is still Python-heavy.

Fresh 1,000,000-point hexbin smoke:

```text
payload_s=3.845
render_s=9.816
total_s=13.661
python_resolve_ms=9539.173
python_native_arg_ms=141.182
native_total_ms=118.988
peak_mb=160.7
```

Root cause:

- `build_scatter_payload(...)` stores all finite points as Python tuples.
- `scatter_payload_to_resolved_spec(...)` rebuilds finite tuples and a tuple of point pairs.
- Hexbin mode still materializes all point pairs before aggregating cells.
- JSON handoff is not the dominant 1M bottleneck; Python resolution is.

Conclusion: the GPT summary item about 1M+ optimization is valid, but the highest-value fix is not more Rust mark drawing. It is a large-data scatter/hexbin contract that avoids Python tuple-pair materialization.

### 2. Theme System Is Missing

Colors, fonts, table styling, title styling, and chart constants are hardcoded across Python specs, Matplotlib renderers, and Rust rendering.

Examples:

- `src/hexafe_plotstats/specs/primitives.py` defines default colors directly in dataclasses.
- `src/hexafe_plotstats/specs/histogram.py` and grouped chart specs emit fixed colors and layout constants.
- `src/hexafe_plotstats/renderers/matplotlib/histogram.py` duplicates badge colors.
- `native/hexafe-plotstats-native/src/svg.rs` owns native rendering choices separately.

Conclusion: the theme proposal is valid. It should be implemented as serializable style tokens in the resolved spec, not as Matplotlib-only `rcParams` or Rust-only constants.

### 3. Axis System Is Too Primitive

The current axis model is intentionally simple:

- linear scale only
- six evenly spaced ticks from `_ticks(...)`
- local `_format_number(...)` string formatting
- no formatter object or locale-aware labels
- no log/time/category axes
- no tick-collision policy

Conclusion: the axis proposal is valid and should be implemented before broad interactivity, because interactive charts and static renderers both need the same axis contract.

### 4. Internationalization Is Not Wired

End-user strings and number formats are currently hardcoded in English:

- histogram table rows: `Min`, `Max`, `Mean`, `Std Dev`, `NOK`, `Samples`, `Normality`, `Model`, `Fit quality`, `Warning`
- chart titles: `Histogram`, `Scatter`, `IQR`, `Violin`
- warnings and fit labels
- numeric formatting through f-strings and `_format_number(...)`

Conclusion: i18n is valid, but it must be implemented as a label/formatting layer before renderer handoff. The resolved spec should contain display-ready labels for renderers, while metadata should preserve stable semantic keys.

### 5. Interactive Charts Are Not a Core Renderer Feature Yet

Current public renderer outputs are:

- Matplotlib figure result: `RenderResult(fig, ax, metadata)`
- Rust/native PNG result: `ChartRenderResult(png_bytes, backend, metadata)`

There is no browser/HTML renderer, no hover/selection schema, and no event metadata contract.

For large scatter data, the required interactive behavior is more specific:

- Plotly should not receive raw 1M+ point traces by default.
- The hoverable/selectable Plotly layer should be an aggregation.
- Raw points should be rendered statically as a raster/PNG-style layer.
- The raw static layer must still be represented in the legend so users can
  disable it.
- If X is temporal, the aggregation bucket should be auto-selected from the
  requested X-axis view and the number of generated X points. Candidate buckets
  are `minute`, `hour`, `day`, and `week`.

Conclusion: the external audit's interactive chart direction is useful, but it should be staged behind a large-data interaction contract. Interactivity should consume resolved specs and produce an optional export artifact. It should not pull browser, Plotly, Qt, or dashboard runtime dependencies into the static renderer path.

### 6. Packaging Is Still Pre-Release

The native build works locally and CI builds wheels, but local Linux builds still warn that they use a non-uploadable `linux_x86_64` tag. The core package has no `rust` extra yet, and native release automation is not a published package path.

Conclusion: before any default-backend change or consumer adoption, add a release-grade native wheel workflow and an explicit version coupling policy between `hexafe-plotstats` and `hexafe-plotstats-native`.

### 7. Test Shape Is Good but Has Release Gaps

The tests are focused and meaningful, but remaining gaps are release-facing:

- no Rust unit tests inside the native crate beyond compilation
- no package wheel/sdist smoke for the pure-Python package
- no type-check gate despite `py.typed`
- no lint/format gate for Python
- CI currently targets one Python version for Python-only tests

Conclusion: add gates only where they protect public contracts. Avoid coverage padding.

## Implementation Plan

### Phase 0: Lock the Current Baseline

Goal: make the current fast/static Rust state a dependable baseline before widening scope.

Tasks:

- Add a short benchmark artifact format that records Python resolve, JSON handoff, native parse, draw, text, PNG encode, bytes, and peak memory for large scatter.
- Add a saved large-scatter benchmark case for 100k, 500k, and 1M points.
- Keep Matplotlib default and Rust explicit.
- Keep the current renderer-comparison threshold as the visual parity gate.

Acceptance:

- Pure Python tests, native tests, compileall, cargo fmt/check/test, renderer comparison, and benchmark smoke pass.
- The 1M benchmark is documented as a baseline and not treated as a passing performance goal yet.

### Phase 1: Large-Data Scatter Contract

Status: initial implementation complete on `feature-interactive-and-performance`
for the resolved-spec/interactivity contract. `build_scatter_payload(...)` keeps
large finite arrays as NumPy arrays, hexbin resolved-spec construction uses
vectorized aggregation, and `build_scatter_interactive_spec(...)` emits bounded
aggregated interactive layers plus a separate legend-controllable static raw
layer. The first Plotly scaffold now exposes `scatter_payload_to_plotly_spec(...)`
and `render_scatter(..., backend="plotly")` when the optional Plotly dependency
is installed; large scatter Plotly specs contain aggregated interactive traces
and a separate raw static legend trace, not raw point traces. Fresh 1M hexbin
smoke with the native renderer dropped from the audit baseline of about `13.7s`
total / `160.7 MB` peak to about `0.73s` total / `70.6 MB` peak on this machine.
Validation for this slice: pure-Python pytest `51 passed, 10 skipped`;
native-enabled pytest `61 passed`; native `resvg` smoke `13 passed`; renderer
comparison passed under threshold 15 for histogram, scatter, scatter trend, IQR,
and violin; `compileall`, `cargo fmt --check`, and `cargo test --locked`
passed.

Goal: make 1M+ scatter/hexbin practical end-to-end, including the future Plotly
interactive path.

Tasks:

- Introduce a large-data scatter path that keeps numeric arrays as arrays until aggregation.
- For `mode="hexbin"`, resolve hex cells from vectorized arrays without building a tuple of `(x, y)` pairs.
- For `mode="scatter_rasterized"`, add an explicit sampled marker batch contract with original count and sampling policy metadata.
- Add `ScatterResolvedDataPolicy` metadata: `full`, `sampled`, `aggregated_hexbin`, `aggregated_temporal`, `static_raw_overlay`.
- Add a temporal aggregation policy for scatter X axes. It should choose
  `minute`, `hour`, `day`, or `week` from the requested X-axis range and a
  target maximum number of interactive X buckets.
- Keep raw data out of interactive Plotly traces by default for large datasets.
  Interactive traces should use aggregated cells/buckets only.
- Add a static raw-data layer contract that can be rendered as a raster image
  and exposed as a legend-controlled layer named clearly enough for users to
  disable raw data.
- Preserve semantic metadata: original point count, finite point count, dropped nonfinite count, mode, gridsize, trend policy.
- Keep raw points out of resolved mappings once the display has aggregated or sampled them.

Acceptance:

- 1M hexbin total render path drops from about 13.7s to a target under 2.0s on this local machine, or the remaining bottleneck is measured and assigned.
- Peak traced memory for 1M hexbin is materially below the current 160.7 MB baseline.
- Existing scatter, trend, rasterized, and hexbin visual comparison tests still pass.
- Tests assert that 1M hexbin resolved mapping size is bounded by cell count, not point count.
- Tests assert that large temporal scatter produces bounded interactive bucket
  traces and does not serialize raw points into the interactive payload.
- Tests assert that the static raw-data layer has legend metadata so it can be
  hidden independently from the aggregated interactive layer.

### Phase 2: Axis and Scale Contract

Goal: make axes stable enough for themes, localization, and interactivity.

Tasks:

- Add `AxisScale` support for at least `linear`, `log`, and `category`.
- Add `TickSpec` with value, display label, major/minor role, and optional priority.
- Replace repeated `_ticks(...)` calls with a shared tick generator.
- Add formatter hooks for numeric precision, percentage, scientific notation, and fixed decimals.
- Add tick-density policies for small canvases and long labels.
- Ensure Matplotlib and Rust both render from the same tick specs.

Acceptance:

- Histogram, scatter, IQR, and violin specs contain explicit tick specs.
- Static output remains visually close to the current oracle.
- Log axis invalid-data behavior is deterministic and warning-backed.
- Tests cover small canvas, large/small magnitude numbers, and long labels.

### Phase 3: Theme Tokens

Goal: remove hardcoded styling drift between Python and Rust.

Tasks:

- Add a frozen `ChartTheme` model with palette, typography, strokes, fills, table styling, badge styles, and spacing.
- Add built-in themes: `default`, `compact_report`, `dark`.
- Resolve themes into explicit style tokens in chart specs.
- Move Matplotlib badge colors and native colors to shared tokens.
- Keep theme names stable in metadata and resolved concrete colors in the mapping.

Acceptance:

- The same theme drives Matplotlib and Rust outputs.
- No chart family keeps duplicated hardcoded badge palettes.
- Theme changes are visible in renderer-comparison fixtures without changing statistical semantics.
- Default theme preserves current visual output within parity tolerance.

### Phase 4: Display Labels and I18n

Goal: support localized chart text without making renderers language-aware.

Tasks:

- Add `LocaleConfig` or `DisplayLabels` with stable semantic keys and localized display strings.
- Move table row labels, chart titles, fit quality labels, and warning display text behind the display layer.
- Add locale-aware number formatting for table values and ticks.
- Start with `en` and `pl` because Metroliza usage likely needs Polish end-user labels.
- Preserve raw semantic metadata separately from display strings.

Acceptance:

- Renderers receive display-ready text in resolved specs.
- Tests verify English default parity and Polish display labels for histogram summary rows, axis labels, and warnings.
- Numeric formatting can use comma decimal separators without changing stored numeric metadata.

### Phase 5: Interactive Export Schema

Goal: add interactivity as an optional consumer of resolved specs, not as a new core dependency.

Tasks:

- Define `InteractiveChartSpec` metadata for tooltips, series IDs, data IDs, selection groups, and drilldown hints.
- Add interactive payload metadata for histogram bars, scatter cells/markers, box groups, and violin groups.
- For large Plotly scatter, default to aggregated interactive traces. Temporal X
  axes should use the Phase 1 bucket policy (`minute`/`hour`/`day`/`week`);
  non-temporal X axes should use bounded bins or hex cells.
- Add a static raw-points render layer for large scatter. The raw layer should
  be raster/static for memory and initial-render performance, but it must have a
  legend-controllable companion entry so users can disable raw data.
- Keep the aggregated layer and static raw layer as separate legend groups:
  toggling raw points must not hide the aggregated interactive layer.
- Add a lightweight JSON export helper first.
- Add an optional HTML renderer only after JSON schema stabilizes.
- Keep browser/Plotly/ECharts dependencies optional and outside the static renderer path.

Acceptance:

- Static rendering works without any interactive dependency.
- JSON export contains enough metadata for hover/selection on each chart family.
- Tests assert stable interactive keys and no raw 1M point leakage in aggregated views.
- Plotly scatter export for large data contains bounded aggregated traces for
  interaction and a separate legend-controllable static raw-data layer.

### Phase 6: Release Packaging and CI

Goal: make the package publishable and safe for downstream adoption.

Tasks:

- Add pure-Python wheel and sdist build smoke for `hexafe-plotstats`.
- Add manylinux-backed native wheel build/release workflow.
- Add a version policy for core/native compatibility.
- Add `rust` optional dependency only after native wheels are published.
- Expand Python test matrix to supported versions.
- Add Python lint/type gates if they catch real contract issues without large churn.

Acceptance:

- Linux/macOS/Windows native wheels are release-grade.
- Pure-Python install still works without Rust.
- Native install path can be tested from built wheels.
- CI artifacts make performance and comparison outputs inspectable.

## Priority Order

1. Large-data scatter contract.
2. Axis/tick contract.
3. Theme tokens.
4. Display labels and i18n.
5. Interactive export schema.
6. Packaging/release workflow.

Rationale: interactivity depends on semantic resolved specs, axis labels, and display text. Theme and i18n should be renderer-neutral. The 1M+ claim should be fixed before adding new surfaces because it currently fails at the Python resolution layer, not in Rust drawing.

## Next Slice

Start with Phase 1. The narrow first patch should:

- add a failing/performance-focused test or benchmark for large hexbin mapping size,
- add tests for automatic temporal bucket choice from requested X-axis range and
  generated bucket count,
- vectorize hexbin cell resolution in `src/hexafe_plotstats/specs/scatter.py`,
- avoid materializing point-pair tuples in hexbin mode,
- define the large-scatter interactive/static layer metadata contract before
  implementing the Plotly renderer,
- preserve current small scatter behavior,
- update `docs/session_state.md` and this plan with measured before/after numbers.

Implemented in the first slice:

- `src/hexafe_plotstats/payloads/_common.py` avoids list materialization for
  NumPy inputs and exposes paired finite array counts.
- `src/hexafe_plotstats/payloads/scatter.py` stores large scatter arrays without
  converting them to Python tuples.
- `src/hexafe_plotstats/specs/scatter.py` resolves hexbin cells with NumPy
  grouping and adds interaction-layer metadata.
- `src/hexafe_plotstats/interactive/scatter.py` defines temporal/numeric
  aggregation specs, automatic minute/hour/day/week bucket selection, and the
  static raw layer contract.
- `src/hexafe_plotstats/renderers/plotly/scatter.py` defines the first optional
  Plotly scatter conversion scaffold, using bounded aggregated traces for large
  data and a separate raw static legend trace.
- Tests cover temporal bucket selection, bounded interactive payloads, raw
  static legend metadata, bounded large hexbin mapping size, and large Plotly
  scatter specs that do not serialize raw points into interactive traces.

Implemented in the second continuation slice:

- Large Plotly scatter raw data now renders as a bounded `heatmap` raster trace
  (`static_raster_heatmap`) instead of only a placeholder legend entry. The raw
  raster trace has its own `scatter_raw` legend group and contains a bounded
  grid, not the raw point list.
- Plotly converters/renderers now exist for histogram, IQR, and violin in
  addition to scatter. They are optional at runtime: dict conversion does not
  require Plotly, while `render_*(..., backend="plotly")` raises
  `RendererBackendUnavailable` unless the `plotly` extra is installed.
- Histogram Plotly specs preserve bars, curves, spec/mean lines, axis labels,
  and summary tables from the resolved spec.
- IQR Plotly specs use resolved quartile/whisker statistics instead of sending
  all group values as raw Plotly box data.
- Violin Plotly specs use resolved body polygons and annotation markers instead
  of sending all raw group values.
- Focused validation for this slice:
  `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest tests/test_interactive_scatter.py tests/test_renderer_backends.py -q`
  -> `36 passed`; targeted `compileall` also passed.
- Full pure-Python validation:
  `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest -q`
  -> `56 passed, 10 skipped`; full `compileall` and `git diff --check`
  passed.
- Large Plotly hexbin spec smoke with 1M points completed in about `0.30s`,
  traced peak memory about `55.5 MB`, raw raster payload cells `24,576`,
  aggregate points `398`, and trace JSON about `0.18 MB`.
