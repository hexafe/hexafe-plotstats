# Session state

Last updated: 2026-05-16, repository audit and post-audit implementation plan

## Current goal

Build `hexafe-plotstats` as a standalone library-first package for statistical visualization payloads and renderer backends extracted from `metroliza`.

## Current continuation pointer

- Start with `docs/2026-05-16-audit_implementation_plan.md` for the latest
  audit reconciliation and implementation order.
- The latest implementation slice covers the large grouped-data path, reusable
  benchmark tooling, theme tokens, tick-count policy, and locale API. The next
  recommended consumer slice is to update Metroliza's `hexafe-plotstats`
  dependency from commit `168edf1...` to this branch/next release, then switch
  its two HTML dashboard modules to
  `plotly_spec_from_metroliza_dashboard_payload(...)` for histogram,
  violin, and IQR specs.
- Large Plotly scatter should aggregate by default. Temporal X axes should pick
  minute/hour/day/week buckets automatically from the requested X-axis range and
  target point count. Interactive traces should contain only aggregated data;
  raw points should be a static legend-controllable layer.
- First implementation slice on branch `feature-interactive-and-performance`:
  large scatter payloads keep NumPy arrays, hexbin resolved specs aggregate
  vectorially, and `build_scatter_interactive_spec(...)` emits aggregated
  interactive layers plus a static raw-points layer. The first optional Plotly
  scatter scaffold emits aggregated traces plus a raw static legend trace for
  large data. Fresh 1M native hexbin smoke measured about `0.73s` total and
  `70.6 MB` peak on this machine.
- Second continuation slice on the same branch: large Plotly
  scatter now renders raw points as a bounded static-raster heatmap trace with
  its own `scatter_raw` legend group, and Plotly converters/renderers now exist
  for histogram, IQR, and violin. Histogram preserves bars/curves/spec
  lines/tables from the resolved spec; IQR uses resolved quartile/whisker
  summaries; violin uses resolved body polygons and annotation markers.
- Metroliza dashboard audit for the next migration step: `modules/export_html_dashboard.py`
  still owns local Plotly spec builders and should be the reference for
  theme/layout/reference-line annotations and histogram detail cards;
  `modules/industrial_analytics_dashboard.py` already uses the Metroliza
  plotstats adapter for single histogram PNGs/stats, but multi-group histogram,
  violin, and box static images are still local Matplotlib. Production/CSV
  histogram and violin charts are static image cards by default.
- Third continuation slice: histogram and violin Plotly spec
  helpers now default to static dashboard configs and metadata, with
  `static=False` available as an explicit opt-in. Scatter remains interactive
  by default.
- Fourth continuation slice: large IQR/violin builders keep NumPy arrays for
  large groups, `clean_numeric_with_warnings(...)` avoids list materialization
  for numeric arrays, resolved violin specs omit raw values and serialize
  bounded body polygons, and large violin density uses a histogram-density
  approximation instead of exact KDE. `scripts/benchmark_large_dataset.py`
  now benchmarks 1M x 5 data across histogram, scatter hexbin, scatter trend,
  IQR, and violin for Matplotlib, Rust/native, and Plotly spec generation.
- Theme and locale foundation is implemented through `set_theme(...)`,
  `get_theme(...)`, `set_locale(...)`, and `translate(...)`. Resolved specs
  carry concrete theme tokens and explicit axis `ticks_count` metadata; default
  output remains Matplotlib-first and Rust/native remains explicit opt-in.
- Metroliza adapter foundation: `plotly_spec_from_metroliza_dashboard_payload(...)`
  converts Metroliza-style dashboard payload mappings into plotstats static
  Plotly specs for histogram, violin distribution, and IQR charts. This keeps
  the consumer migration small once Metroliza points at this branch/release.
- Current large benchmark on this machine with cached native module
  (`PYTHONPATH=/tmp/hexafe_plotstats_native_bench:src python scripts/benchmark_large_dataset.py --rows 1000000 --columns 5 --repeats 1`):
  histogram build `0.320s`, Matplotlib `0.506s`, Rust `0.105s`, Plotly spec
  `0.005s`; scatter hexbin build `0.022s`, Matplotlib `4.147s`, Rust `0.351s`,
  Plotly spec `0.456s`; scatter hexbin trend build `0.024s`, Matplotlib
  `3.710s`, Rust `0.610s`, Plotly spec `0.509s`; IQR build `0.299s`,
  Matplotlib `0.700s`, Rust `2.053s`, Plotly spec `1.338s`; violin build
  `0.331s`, Matplotlib `0.712s`, Rust `0.161s`, Plotly spec `0.159s`.
- Validation for this slice: pure-Python pytest `51 passed, 10 skipped`;
  native-enabled pytest `61 passed`; native `resvg` smoke `13 passed`;
  renderer comparison passed under threshold 15 for histogram, scatter,
  scatter trend, IQR, and violin; `compileall`, `cargo fmt --check`, and
  `cargo test --locked` passed.
- Focused validation for the Plotly continuation slice:
  `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest tests/test_interactive_scatter.py tests/test_renderer_backends.py -q`
  -> `36 passed`; targeted `compileall` also passed.
- Full pure-Python validation for the Plotly continuation slice:
  `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest -q`
  -> `56 passed, 10 skipped`; `python -m compileall -q src tests scripts examples`
  and `git diff --check` passed.
- 1M Plotly hexbin spec smoke for the continuation slice: about `0.30s`,
  `55.5 MB` traced peak, raw raster payload cells `24,576`, aggregate points
  `398`, and trace JSON about `0.18 MB`.
- Validation for the static histogram/violin policy slice:
  `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest tests/test_interactive_scatter.py tests/test_renderer_backends.py -q`
  -> `37 passed`; full pure-Python suite
  `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest -q`
  -> `57 passed, 10 skipped`; full `compileall` and `git diff --check` passed.
- Keep Matplotlib as the default backend and Rust/native as explicit opt-in
  while release packaging remains pre-release.
- Release prep branch version: core package `0.1.0a1`, native Python package
  `0.1.0a1`, native Rust crate `0.1.0-alpha.1`.
- Release prep validation: `python -m pytest -q` -> `60 passed,
  10 skipped`; `python -m compileall -q src tests scripts examples` passed;
  `cargo fmt --check`, `cargo check --locked`, and `cargo test --locked`
  passed; `python -m build --outdir /tmp/hexafe-plotstats-release-dist`
  built `hexafe_plotstats-0.1.0a1`; native `maturin build --release --locked`
  built a local Linux wheel with the expected non-PyPI `linux_x86_64` warning.

## Current decisions

- Repository path: `/home/hexaf/Projects/hexafe-plotstats`
- Package name: `hexafe-plotstats`
- Import package: `hexafe_plotstats`
- Default renderer backend: `matplotlib`
- Secondary renderer backend: `rust`, exposed through backend selection and
  available when the optional `_hexafe_plotstats_native` extension is installed.
- Core stays free of workbook, Qt, thread, Google, and dashboard concerns.
- `hexafe-groupstats` remains responsible for group significance tests and Monte Carlo stability semantics.

## Current implementation state

- Git repo initialized locally.
- Core models and configs exist under `src/hexafe_plotstats/models`.
- Stats core exists under `src/hexafe_plotstats/stats`.
- Payload builders exist under `src/hexafe_plotstats/payloads`.
- Matplotlib renderers exist under `src/hexafe_plotstats/renderers/matplotlib`.
- Renderer selection API exists under `src/hexafe_plotstats/renderers/api.py`.
- Rust renderer package exists under `src/hexafe_plotstats/renderers/rust`; PNG
  helpers dispatch to the optional native extension when installed and raise
  `RendererBackendUnavailable` when absent.
- Optional adapters exist under `src/hexafe_plotstats/adapters`.
- README, examples, and initial tests exist.
- README now documents backend selection and the current Rust/native scaffold state.
- README now documents renderer capability probing, the supported chart matrix, and current resolved-spec helpers.
- Dedicated Rust/native extraction plan added at `docs/rust_renderer_plan.md`.
- `docs/rust_renderer_plan.md` now records the full staged Rust renderer plan:
  keep Matplotlib default for now, implement a separate optional
  `_hexafe_plotstats_native` PyO3/maturin distribution, start with
  resolved-spec-to-SVG-to-`resvg` PNG rendering, then move hot paths and chart
  geometry into Rust after parity is proven.
- Native package exists under `native/hexafe-plotstats-native`; it builds a
  PyO3/maturin abi3 wheel named `hexafe-plotstats-native`, exposes
  `_hexafe_plotstats_native`, accepts compact JSON specs, and renders
  histogram, scatter, IQR, and violin PNGs through Rust.
- Public renderer capability APIs exist:
  - `renderer_backend_available(...)`
  - `renderer_backend_capabilities()`
  - `RendererBackendCapability`
- Histogram payloads now accept optional metadata for title, axis labels, x-view, mean-line, annotation, table, and resolved-spec handoff semantics.
- The Metroliza adapter exposes `histogram_from_metroliza_native_payload(...)` for enriched native histogram payload dictionaries.
- Matplotlib IQR and violin spec-limit lines now use horizontal y-value
  semantics, matching the resolved spec and Rust renderer.

## Integration notes

- Subagents were used after explicit user request:
  - docs/adapters/tests worker
  - payload/policies/renderers worker
  - stats/fitting worker
- Initial workers passed isolated tests, then integration started.
- Adapter and payload helper duplication was removed so package code delegates to the stats, payload, and renderer layers.
- A read-only explorer audited `/home/hexaf/Projects/metroliza` for Rust/native rendering extraction points.
- Important Rust/native audit result: `metroliza` uses `modules/chart_renderer.py` as the runtime backend boundary, `modules/chart_render_spec.py` as resolved-spec construction, `modules/native_chart_compositor.py` for native PNG rendering, and `modules/native/chart_renderer/src/lib.rs` as a PyO3 wrapper over Python compositor functions.
- Recommended Rust boundary: keep backend selection in Python, preserve `resolved_render_spec` as the parity handoff, and make Rust consume pure mapping specs instead of matplotlib figures.

## Current verification

- Isolated worker tests previously passed: `8 passed`.
- Full package verification passed after backend-selection integration:
  - `PYTHONPATH=src python -m pytest -q` -> `9 passed`
  - root import/render smoke passed
- Example verification passed:
  - `PYTHONPATH=src python examples/basic_usage.py`
  - `PYTHONPATH=src python examples/pandas_usage.py`
- Compile verification passed:
  - `python -m compileall -q src tests examples`
- Root import/render smoke emitted an environment-level Qt style warning, but exited successfully.
- Local commit created:
  - `Scaffold hexafe plotstats package`
  - Run `git rev-parse --short HEAD` for the exact current hash.
- GitHub remote configured:
  - `origin` -> `git@github.com:hexafe/hexafe-plotstats.git`
- Remote `main` initially contained a GitHub-created `LICENSE` commit.
- Local scaffold merged `origin/main` with `--allow-unrelated-histories` to preserve the remote license.
- Integrated `main` pushed to `origin/main`.
- Active implementation branch:
  - `codex/resolved-spec-rust-foundation`
- Resolved spec foundation added:
  - `src/hexafe_plotstats/specs`
  - `histogram_payload_to_resolved_spec`
  - `iqr_payload_to_resolved_spec`
  - `scatter_payload_to_resolved_spec`
  - `violin_payload_to_resolved_spec`
  - primitive mapping helper `to_mapping`
- Rust/native PNG API foundation added:
  - `render_histogram_png`
  - `render_violin_png`
  - `render_iqr_png`
  - `render_scatter_png`
  - `render_scatter_trend_png`
  - `ChartRenderResult`
- Native module is still absent; rust PNG helpers raise `RendererBackendUnavailable`.
- Rust PNG helpers now resolve histogram, violin, IQR, and scatter payloads to pure mappings before native dispatch when a native module is installed.
- Verification after integration:
  - `PYTHONPATH=src python -m pytest -q` -> `12 passed`
  - root import/render/spec smoke passed
  - `python -m compileall -q src tests examples`
  - `PYTHONPATH=src python examples/basic_usage.py`
  - `PYTHONPATH=src python examples/pandas_usage.py`
- Verification after the 2026-05-01 local checkpoint:
  - initial renderer-contract pass: `python -m pytest -q` -> `24 passed`
  - `python -m compileall -q src tests examples`
- Verification after full chart resolved-spec and histogram parity contract work:
  - first histogram parity pass: `python -m pytest -q` -> `31 passed`
  - `python -m compileall -q src tests examples`
- Verification after Metroliza histogram adapter work:
  - `python -m pytest -q` -> `32 passed`
  - `python -m compileall -q src tests examples`
- Verification after native package scaffold:
  - `cargo check` in `native/hexafe-plotstats-native` -> passed with PyO3
    deprecation warnings for `downcast`
  - `maturin build --quiet` in `native/hexafe-plotstats-native` -> built
    `hexafe_plotstats_native-0.1.0a0-cp310-abi3-manylinux_2_34_x86_64.whl`
  - temporary wheel install under `/tmp/hexafe_plotstats_native_test` plus
    `PYTHONPATH=/tmp/hexafe_plotstats_native_test:src python -c ...` -> rust
    backend available and `render_histogram_png(...)` returned valid PNG bytes
- Verification after functional native renderer implementation:
  - `cargo fmt --check` in `native/hexafe-plotstats-native` -> passed
  - `cargo check` in `native/hexafe-plotstats-native` -> passed
  - `cargo test` in `native/hexafe-plotstats-native` -> passed, 0 Rust unit tests
  - `maturin build --quiet` in `native/hexafe-plotstats-native` -> built
    `hexafe_plotstats_native-0.1.0a0-cp310-abi3-linux_x86_64.whl`; maturin
    warned that the wheel uses a `linux` tag and is not PyPI-uploadable as-is
  - pure-Python install path: `python -m pytest -q` -> `39 passed, 5 skipped`
  - native-enabled path:
    `PYTHONPATH=/tmp/hexafe_plotstats_native_text:src python -m pytest -q`
    -> `44 passed`
  - compile check: `python -m compileall -q src tests scripts examples`
  - equal-canvas benchmark:
    `PYTHONPATH=/tmp/hexafe_plotstats_native_hexbin:src python scripts/benchmark_renderers.py --repeats 5 --warmups 1`
    -> histogram Matplotlib 151.20 ms / Rust 161.12 ms; scatter 148.28 ms /
    Rust 146.72 ms; IQR 74.80 ms / Rust 71.14 ms; violin 186.38 ms / Rust
    165.95 ms
- Verification after schema parity tightening:
  - explicit scatter hexbin cells added to resolved specs and Rust parser
  - explicit violin body polygons added to resolved specs and Rust parser
  - Matplotlib renderers now apply resolved canvas, plot rectangle, axes, and
    ticks
  - native visual parity smoke tests compare equal-size Matplotlib/Rust PNGs
  - pure-Python path: `python -m pytest -q` -> `40 passed, 9 skipped`
  - native-enabled path:
    `PYTHONPATH=/tmp/hexafe_plotstats_native_hexbin:src python -m pytest -q`
    -> `49 passed`
- Verification after histogram stats visual check:
  - Rust SVG text rasterization now loads system fonts and maps the generic
    `sans-serif` family to an OS-specific system font before `resvg` parsing.
  - Histogram stats tables are drawn from the resolved spec in both Matplotlib
    and Rust.
  - Native smoke tests now assert that the PNG title band contains rendered text
    pixels, not only that SVG metadata contains `<text>`.
  - rebuilt wheel install:
    `/tmp/hexafe_plotstats_native_fontfix`
  - native-enabled path:
    `PYTHONPATH=/tmp/hexafe_plotstats_native_fontfix:src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest -q`
    -> `49 passed`
  - generated histogram comparison artifacts:
    `/tmp/hexafe_plotstats_histogram_stats/histogram_stats_matplotlib.png`,
    `/tmp/hexafe_plotstats_histogram_stats/histogram_stats_rust.png`, and
    `/tmp/hexafe_plotstats_histogram_stats/histogram_stats_comparison.png`
- Verification after Metroliza-style histogram parity and backend flag wiring:
  - Standalone histogram payloads now emit display-ready Metroliza-style table
    rows: Min, Max, Mean, Median, Std Dev, Cp/Cpk or one-sided Cpu/Cpl, NOK
    with side split, NOK %, Samples, Normality, Model, Est. NOK %, Fit quality,
    and Warning.
  - Matplotlib and Rust histogram renderers now use the same resolved table row
    metadata for section breaks and quality badges.
  - `render_*(..., backend="rust")` now dispatches to the native PNG renderer
    when `_hexafe_plotstats_native` is installed. It still raises
    `RendererBackendUnavailable` without the native module.
  - Added `scripts/compare_renderers.py`; latest comparison output:
    `/tmp/hexafe_plotstats_renderer_comparisons/summary.md`
  - Visual comparison pass at threshold 15 mean absolute diff:
    histogram 6.560, scatter 3.923, scatter trend 6.564, IQR 6.393, violin
    4.557.
  - Latest benchmark:
    `PYTHONPATH=/tmp/hexafe_plotstats_native_current:src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python scripts/benchmark_renderers.py --repeats 7 --warmups 2`
    -> histogram Matplotlib 176.69 ms / Rust 258.39 ms; scatter 109.17 ms /
    Rust 169.59 ms; IQR 73.34 ms / Rust 101.98 ms; violin 170.00 ms / Rust
    164.98 ms.
  - Current performance status: Rust is functional and visual-parity green, but
    not yet faster for every chart because the native text overlay and PNG
    encoding path still dominate small/medium plots.
  - Validation:
    `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest -q`
    -> `40 passed, 9 skipped`;
    `PYTHONPATH=/tmp/hexafe_plotstats_native_current:src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python -m pytest -q`
    -> `49 passed`;
    `python -m compileall -q src tests scripts examples` -> passed;
    `cargo fmt --check`, `cargo check`, and `cargo test` in
    `native/hexafe-plotstats-native` -> passed.
  - Added `.github/workflows/ci.yml` with two jobs:
    pure-Python tests/compileall and native Rust renderer fmt/check/test/wheel
    build/native-enabled pytest.
- Feature branch committed and pushed:
  - branch: `codex/resolved-spec-rust-foundation`
  - commit: `Add resolved spec rust renderer foundation`
  - remote: `origin/codex/resolved-spec-rust-foundation`
- Draft PR opened:
  - https://github.com/hexafe/hexafe-plotstats/pull/1
- Follow-up performance/parity slice:
  - Added native PNG render profiles: `fast` default, `compact` for smaller
    PNGs, and `debug` for SVG metadata. The profile is passed through
    `render_*_png(..., profile=...)` and resolved spec metadata.
  - Expanded `scripts/benchmark_renderers.py` with synthetic/realistic suites,
    individual realistic cases, and `--profile`. Realistic cases include the
    Metroliza native histogram adapter path with modeled overlays, large
    process histograms, dense scatter, hexbin scatter, many-group IQR, and
    many-group violin.
  - Histogram modeled overlays are now drawable curve primitives, including
    filled tail regions. Histogram annotation rows now emit separate leader
    lines in addition to annotation text.
  - Violin `sigma_policy` now emits explicit `+3 sigma` and `-3 sigma` lines.
    Native violin rendering preserves marker kind and draws extrema as distinct
    ticks instead of generic dots.
  - Native CI was expanded to Linux/macOS/Windows release wheel builds with
    locked Rust dependencies, direct-text native smoke/backend tests, resvg
    fallback smoke tests, and a Linux benchmark smoke.
  - Local host PyPI-compatible Linux wheel validation still fails because the
    host GLIBC symbols are too new; release wheels must be built in a
    manylinux container/action. A normal local Linux wheel remains valid for
    test execution.
  - Validation:
    `PYTHONPATH=src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats pytest -q`
    -> `44 passed, 10 skipped`;
    `PYTHONPATH=/tmp/hexafe_plotstats_native_current:src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats pytest -q`
    -> `54 passed`;
    `PYTHONPATH=/tmp/hexafe_plotstats_native_current:src HEXAFE_PLOTSTATS_NATIVE_TEXT=resvg MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats pytest tests/test_native_renderer_smoke.py -q`
    -> `13 passed`;
    `cargo fmt --check`, `cargo check --locked`, and `cargo test` in
    `native/hexafe-plotstats-native` -> passed;
    `python -m compileall -q src tests scripts examples` -> passed.
  - Renderer comparison:
    `PYTHONPATH=/tmp/hexafe_plotstats_native_current:src MPLBACKEND=Agg MPLCONFIGDIR=/tmp/matplotlib-hexafe-plotstats python scripts/compare_renderers.py --output /tmp/hexafe_plotstats_renderer_comparisons --threshold 15`
    -> all comparisons passed; mean abs diffs were histogram 6.419, scatter
    3.921, scatter trend 6.563, IQR 6.393, violin 4.563.
  - Latest synthetic benchmark medians:
    histogram Matplotlib 178.13 ms / Rust 8.05 ms; scatter 105.80 / 11.49;
    IQR 76.48 / 3.39; violin 197.12 / 37.92.
  - Latest realistic benchmark medians:
    Metroliza table histogram 212.56 / 10.66; Metroliza adapter histogram
    152.64 / 10.65; large process histogram 200.60 / 7.11; dense scatter
    332.38 / 94.46; hexbin scatter 828.92 / 139.78; many-group IQR
    160.46 / 6.09; many-group violin 450.12 / 52.32.

## Next steps

1. Run full local validation, renderer comparison, and updated benchmark
   commands with the freshly built native wheel.
2. Push the branch and verify the expanded GitHub CI matrix.
3. Move native wheel publishing to a manylinux-backed release workflow before
   exposing a PyPI `rust` extra.
4. Keep Matplotlib as the default backend until native wheels are published and
   parity thresholds stay green on CI.

## Known non-goals for this checkpoint

- No metroliza integration changes yet.
- No native package release/tag yet.
- No package release/tag yet.
