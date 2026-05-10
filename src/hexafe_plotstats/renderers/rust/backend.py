from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import is_dataclass
from functools import lru_cache
from importlib import import_module
from time import perf_counter_ns
from typing import Any, Callable, NoReturn

from ...models.payloads import HistogramPayload, IQRPayload, ScatterPayload, ViolinPayload
from ...models.render import ChartRenderResult
from ...specs import to_mapping
from ..base import NativeRenderProfile, RendererBackendUnavailable

_NATIVE_MODULE_NAMES = ("_hexafe_plotstats_native", "hexafe_plotstats_native")
_HISTOGRAM_RESOLVER_MODULE = "hexafe_plotstats.specs.histogram"
_IQR_RESOLVER_MODULE = "hexafe_plotstats.specs.iqr"
_SCATTER_RESOLVER_MODULE = "hexafe_plotstats.specs.scatter"
_VIOLIN_RESOLVER_MODULE = "hexafe_plotstats.specs.violin"
_NATIVE_RENDER_PROFILES = frozenset(("fast", "compact", "debug"))


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


@lru_cache(maxsize=1)
def _load_iqr_resolver() -> Any | None:
    try:
        module = import_module(_IQR_RESOLVER_MODULE)
    except ModuleNotFoundError as exc:
        if not _module_absent(exc, _IQR_RESOLVER_MODULE):
            raise
        return None

    return getattr(module, "iqr_payload_to_resolved_spec", None)


@lru_cache(maxsize=1)
def _load_violin_resolver() -> Any | None:
    try:
        module = import_module(_VIOLIN_RESOLVER_MODULE)
    except ModuleNotFoundError as exc:
        if not _module_absent(exc, _VIOLIN_RESOLVER_MODULE):
            raise
        return None

    return getattr(module, "violin_payload_to_resolved_spec", None)


@lru_cache(maxsize=1)
def _load_scatter_resolver() -> Any | None:
    try:
        module = import_module(_SCATTER_RESOLVER_MODULE)
    except ModuleNotFoundError as exc:
        if not _module_absent(exc, _SCATTER_RESOLVER_MODULE):
            raise
        return None

    return getattr(module, "scatter_payload_to_resolved_spec", None)


def _unavailable(chart: str) -> NoReturn:
    raise RendererBackendUnavailable(
        f"rust renderer for {chart} is not installed yet; use backend='matplotlib' "
        "or install hexafe-plotstats-native from a wheel built in native/hexafe-plotstats-native"
    )


def native_backend_available() -> bool:
    return _load_native_module() is not None


def native_backend_module_name() -> str | None:
    native_module = _load_native_module()
    if native_module is None:
        return None
    return str(getattr(native_module, "__name__", "") or "")


def _payload_mapping(payload: Any) -> dict[str, Any]:
    if is_dataclass(payload):
        mapping = to_mapping(payload)
        return dict(mapping)
    if isinstance(payload, Mapping):
        return dict(to_mapping(payload))
    raise TypeError(f"unsupported payload type for native renderer: {type(payload)!r}")


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


def _iqr_resolved_spec(payload: IQRPayload) -> dict[str, Any]:
    resolver = _load_iqr_resolver()
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


def _violin_resolved_spec(payload: ViolinPayload) -> dict[str, Any]:
    resolver = _load_violin_resolver()
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


def _scatter_resolved_spec(payload: ScatterPayload) -> dict[str, Any]:
    resolver = _load_scatter_resolver()
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


def _native_spec_argument(native_module: Any, mapping: Mapping[str, Any]) -> Mapping[str, Any] | str:
    if bool(getattr(native_module, "ACCEPTS_JSON_SPEC", False)):
        return json.dumps(mapping, allow_nan=False, separators=(",", ":"))
    return mapping


def _validate_profile(profile: str) -> NativeRenderProfile:
    if profile not in _NATIVE_RENDER_PROFILES:
        raise ValueError(f"unsupported native render profile: {profile!r}")
    return profile  # type: ignore[return-value]


def _mapping_with_profile(mapping: dict[str, Any], profile: NativeRenderProfile) -> dict[str, Any]:
    if profile == "fast":
        return mapping
    profiled = dict(mapping)
    metadata = dict(profiled.get("metadata", {}) if isinstance(profiled.get("metadata"), Mapping) else {})
    metadata["render_profile"] = profile
    profiled["metadata"] = metadata
    return profiled


def _elapsed_ms(start_ns: int) -> float:
    return (perf_counter_ns() - start_ns) / 1_000_000


def _render_native_png(
    payload: Any,
    *,
    chart: str,
    native_function: str,
    resolve_mapping: Callable[[Any], dict[str, Any]],
    profile: NativeRenderProfile = "fast",
) -> ChartRenderResult:
    total_start = perf_counter_ns()
    native_module = _load_native_module()
    if native_module is None:
        _unavailable(chart)

    native_renderer = getattr(native_module, native_function, None)
    if native_renderer is None:
        _unavailable(chart)

    profile = _validate_profile(profile)

    resolve_start = perf_counter_ns()
    mapping = _mapping_with_profile(resolve_mapping(payload), profile)
    python_resolve_ms = _elapsed_ms(resolve_start)

    arg_start = perf_counter_ns()
    native_argument = _native_spec_argument(native_module, mapping)
    python_native_arg_ms = _elapsed_ms(arg_start)

    call_start = perf_counter_ns()
    result = _coerce_chart_result(native_renderer(native_argument), chart=chart)
    python_native_call_ms = _elapsed_ms(call_start)
    python_total_ms = _elapsed_ms(total_start)

    metadata = dict(result.metadata)
    raw_timings = metadata.get("timings_ms", {})
    timings = dict(raw_timings) if isinstance(raw_timings, Mapping) else {}
    timings.update(
        {
            "python_resolve_ms": python_resolve_ms,
            "python_native_arg_ms": python_native_arg_ms,
            "python_native_call_ms": python_native_call_ms,
            "python_total_ms": python_total_ms,
        }
    )
    metadata["timings_ms"] = timings
    return ChartRenderResult(png_bytes=result.png_bytes, backend=result.backend, metadata=metadata)


def render_histogram_rust(payload: HistogramPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return render_histogram_png(payload, profile=profile)


def render_violin_rust(payload: ViolinPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return render_violin_png(payload, profile=profile)


def render_iqr_rust(payload: IQRPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return render_iqr_png(payload, profile=profile)


def render_scatter_rust(payload: ScatterPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return render_scatter_png(payload, profile=profile)


def render_histogram_png(payload: HistogramPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return _render_native_png(
        payload,
        chart="histogram",
        native_function="render_histogram_png",
        resolve_mapping=_histogram_resolved_spec,
        profile=profile,
    )


def render_violin_png(payload: ViolinPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return _render_native_png(
        payload,
        chart="violin",
        native_function="render_violin_png",
        resolve_mapping=_violin_resolved_spec,
        profile=profile,
    )


def render_iqr_png(payload: IQRPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return _render_native_png(
        payload,
        chart="iqr",
        native_function="render_iqr_png",
        resolve_mapping=_iqr_resolved_spec,
        profile=profile,
    )


def render_scatter_png(payload: ScatterPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return _render_native_png(
        payload,
        chart="scatter",
        native_function="render_scatter_png",
        resolve_mapping=_scatter_resolved_spec,
        profile=profile,
    )


def render_scatter_trend_png(payload: ScatterPayload, *, profile: NativeRenderProfile = "fast") -> ChartRenderResult:
    return _render_native_png(
        payload,
        chart="scatter trend",
        native_function="render_scatter_trend_png",
        resolve_mapping=_scatter_resolved_spec,
        profile=profile,
    )
