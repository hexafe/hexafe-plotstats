# Session state

Last updated: 2026-04-19, remote integration checkpoint

## Current goal

Build `hexafe-plotstats` as a standalone library-first package for statistical visualization payloads and renderer backends extracted from `metroliza`.

## Current decisions

- Repository path: `/home/hexaf/Projects/hexafe-plotstats`
- Package name: `hexafe-plotstats`
- Import package: `hexafe_plotstats`
- Default renderer backend: `matplotlib`
- Secondary renderer backend: `rust`, exposed through backend selection but currently scaffolded as unavailable until the metroliza Rust/native extraction is ported.
- Core stays free of workbook, Qt, thread, Google, and dashboard concerns.
- `hexafe-groupstats` remains responsible for group significance tests and Monte Carlo stability semantics.

## Current implementation state

- Git repo initialized locally.
- Core models and configs exist under `src/hexafe_plotstats/models`.
- Stats core exists under `src/hexafe_plotstats/stats`.
- Payload builders exist under `src/hexafe_plotstats/payloads`.
- Matplotlib renderers exist under `src/hexafe_plotstats/renderers/matplotlib`.
- Renderer selection API exists under `src/hexafe_plotstats/renderers/api.py`.
- Rust renderer package exists under `src/hexafe_plotstats/renderers/rust`, currently raising `RendererBackendUnavailable`.
- Optional adapters exist under `src/hexafe_plotstats/adapters`.
- README, examples, and initial tests exist.
- README now documents backend selection and the current Rust/native scaffold state.
- Dedicated Rust/native extraction plan added at `docs/rust_renderer_plan.md`.

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

## Next steps

1. Push integrated `main` to GitHub.
2. Start Rust/native port foundation with histogram resolved spec first.
3. Keep updating this file after each implementation checkpoint.

## Known non-goals for this checkpoint

- No metroliza integration changes yet.
- No actual Rust/native renderer port yet.
- No GitHub push yet.
- No package release/tag yet.
