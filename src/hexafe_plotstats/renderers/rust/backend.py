from __future__ import annotations

from collections.abc import Mapping
from dataclasses import is_dataclass
from functools import lru_cache
from importlib import import_module
from typing import Any, NoReturn

from ...models.payloads import HistogramPayload, IQRPayload, ScatterPayload, ViolinPayload
from ...models.render import ChartRenderResult
from ...specs import to_mapping
from ..base import RendererBackendUnavailable

_NATIVE_MODULE_NAMES = ("_hexafe_plotstats_native", "hexafe_plotstats_native")
_HISTOGRAM_RESOLVER_MODULE = "hexafe_plotstats.specs.histogram"


def _module_absent(exc: ModuleNotFoundError, module_name: str) -> bool:
    missing_name = exc.name or ""
    return missing_name == module_name or module_name.startswith(f"{missing_name}.")


@lru_cache(maxsize=None)
def _load_native_module() -> Any | None:
    for module_name in _NATIVE_MODULE_NAMES:
        try:
            return import_module(module_name)
        except ModuleNotFoundError as exc:
            if not _module_absent(exc, module_name):
                raise
    return None


@lru_cache(maxsize=1)
def _load_histogram_resolver() -> Any | None:
    try:
        module = import_module(_HISTOGRAM_RESOLVER_MODULE)
    except ModuleNotFoundError as exc:
        if not _module_absent(exc, _HISTOGRAM_RESOLVER_MODULE):
            raise
        return None

    return getattr(module, "histogram_payload_to_resolved_spec", None)


def _unavailable(chart: str) -> NoReturn:
    raise RendererBackendUnavailable(
        f"rust renderer for {chart} is not installed yet; use backend='matplotlib' "
        "or install the future rust backend extra once it is available"
    )


def _payload_mapping(payload: Any) -> dict[str, Any]:
    if is_dataclass(payload):
        mapping = to_mapping(payload)
        return dict(mapping)
    if isinstance(payload, Mapping):
        return dict(to_mapping(payload))
    raise TypeError(f"unsupported payload type for native renderer: {type(payload)!r}")


def _render_native_png(chart: str, payload: Any, function_name: str) -> ChartRenderResult:
    native_module = _load_native_module()
    if native_module is None:
        _unavailable(chart)

    native_renderer = getattr(native_module, function_name, None)
    if native_renderer is None:
        _unavailable(chart)

    return _coerce_chart_result(native_renderer(_payload_mapping(payload)), chart=chart)


def _histogram_resolved_spec(payload: HistogramPayload) -> dict[str, Any]:
    resolver = _load_histogram_resolver()
    if resolver is None:
        return _payload_mapping(payload)

    resolved_spec = resolver(payload)
    if resolved_spec is None:
        return {}
    if isinstance(resolved_spec, Mapping):
        return dict(to_mapping(resolved_spec))
    if is_dataclass(resolved_spec):
        return dict(to_mapping(resolved_spec))
    return dict(to_mapping(resolved_spec))


def _coerce_chart_result(value: Any, *, chart: str) -> ChartRenderResult:
    if isinstance(value, ChartRenderResult):
        return value
    if isinstance(value, bytes):
        return ChartRenderResult(png_bytes=value, backend="rust", metadata={"chart": chart})
    if isinstance(value, bytearray):
        return ChartRenderResult(png_bytes=bytes(value), backend="rust", metadata={"chart": chart})
    if isinstance(value, Mapping) and "png_bytes" in value:
        return ChartRenderResult(
            png_bytes=bytes(value["png_bytes"]),
            backend=str(value.get("backend", "rust")),
            metadata=dict(value.get("metadata", {"chart": chart})),
        )
    raise TypeError(f"native renderer returned unsupported result for {chart}: {type(value)!r}")


def render_histogram_rust(payload: HistogramPayload) -> NoReturn:
    _unavailable("histogram")


def render_violin_rust(payload: ViolinPayload) -> NoReturn:
    _unavailable("violin")


def render_iqr_rust(payload: IQRPayload) -> NoReturn:
    _unavailable("iqr")


def render_scatter_rust(payload: ScatterPayload) -> NoReturn:
    _unavailable("scatter")


def render_histogram_png(payload: HistogramPayload) -> ChartRenderResult:
    native_module = _load_native_module()
    if native_module is None:
        _unavailable("histogram")

    native_renderer = getattr(native_module, "render_histogram_png", None)
    if native_renderer is None:
        _unavailable("histogram")

    return _coerce_chart_result(native_renderer(_histogram_resolved_spec(payload)), chart="histogram")


def render_violin_png(payload: ViolinPayload) -> ChartRenderResult:
    return _render_native_png("violin", payload, "render_violin_png")


def render_iqr_png(payload: IQRPayload) -> ChartRenderResult:
    return _render_native_png("iqr", payload, "render_iqr_png")


def render_scatter_png(payload: ScatterPayload) -> ChartRenderResult:
    return _render_native_png("scatter", payload, "render_scatter_png")


def render_scatter_trend_png(payload: ScatterPayload) -> ChartRenderResult:
    return _render_native_png("scatter trend", payload, "render_scatter_trend_png")
