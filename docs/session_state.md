# Session state

Last updated: 2026-05-10, functional native Rust renderer checkpoint

## Current goal

Build `hexafe-plotstats` as a standalone library-first package for statistical visualization payloads and renderer backends extracted from `metroliza`.

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

## Next steps

1. Add a direct native text renderer or lighter text overlay path so Rust is
   consistently faster on small/medium plots, not only functionally equivalent.
2. Broaden image-similarity parity checks to fixture snapshots and larger
   payloads, including hexbin-specific scatter cases.
3. Tune the native PNG compression default. It is configurable through
   `HEXAFE_PLOTSTATS_NATIVE_PNG_COMPRESSION`; current speed-first output is
   fast but large.
4. Fix maturin platform tagging/wheel packaging before publishing the native
   package.
5. Keep Matplotlib as the default backend until the native package is published
   and parity thresholds are green.

## Known non-goals for this checkpoint

- No metroliza integration changes yet.
- No native package release/tag yet.
- No GitHub push yet.
- No package release/tag yet.
