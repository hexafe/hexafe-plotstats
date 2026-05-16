from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping


_BUILTIN_THEMES: dict[str, dict[str, Any]] = {
    "default": {
        "name": "default",
        "font_family": "DejaVu Sans",
        "font_size": 12,
        "colors": {
            "background": "#ffffff",
            "plot_background": "#ffffff",
            "text": "#111827",
            "muted_text": "#6b7280",
            "grid": "#e5e7eb",
            "axis": "#374151",
            "bar": "#2563eb",
            "bar_outline": "#1d4ed8",
            "fit": "#f97316",
            "spec_limit": "#dc2626",
            "nominal": "#16a34a",
        },
    },
    "compact_report": {
        "name": "compact_report",
        "font_family": "DejaVu Sans",
        "font_size": 11,
        "colors": {
            "background": "#ffffff",
            "plot_background": "#f8fafc",
            "text": "#0f172a",
            "muted_text": "#475569",
            "grid": "#cbd5e1",
            "axis": "#334155",
            "bar": "#0f766e",
            "bar_outline": "#115e59",
            "fit": "#ea580c",
            "spec_limit": "#b91c1c",
            "nominal": "#15803d",
        },
    },
    "dark": {
        "name": "dark",
        "font_family": "DejaVu Sans",
        "font_size": 12,
        "colors": {
            "background": "#111827",
            "plot_background": "#1f2937",
            "text": "#f9fafb",
            "muted_text": "#d1d5db",
            "grid": "#4b5563",
            "axis": "#e5e7eb",
            "bar": "#60a5fa",
            "bar_outline": "#93c5fd",
            "fit": "#fb923c",
            "spec_limit": "#f87171",
            "nominal": "#4ade80",
        },
    },
}

_current_theme: dict[str, Any] = deepcopy(_BUILTIN_THEMES["default"])


def available_themes() -> tuple[str, ...]:
    return tuple(_BUILTIN_THEMES)


def set_theme(name_or_dict: str | Mapping[str, Any]) -> dict[str, Any]:
    global _current_theme
    _current_theme = resolve_theme(name_or_dict)
    return get_theme()


def get_theme() -> dict[str, Any]:
    return deepcopy(_current_theme)


def resolve_theme(name_or_dict: str | Mapping[str, Any] | None = None) -> dict[str, Any]:
    if name_or_dict is None:
        return get_theme()
    if isinstance(name_or_dict, str):
        try:
            return deepcopy(_BUILTIN_THEMES[name_or_dict])
        except KeyError as exc:
            valid = ", ".join(available_themes())
            raise ValueError(f"unknown theme {name_or_dict!r}; choose one of: {valid}") from exc
    base_name = str(name_or_dict.get("base") or name_or_dict.get("name") or "default")
    base = deepcopy(_BUILTIN_THEMES.get(base_name, _BUILTIN_THEMES["default"]))
    override = deepcopy(dict(name_or_dict))
    colors = dict(base.get("colors") or {})
    colors.update(dict(override.pop("colors", {}) or {}))
    base.update(override)
    base["colors"] = colors
    base.setdefault("name", "custom")
    return base


def theme_from_metadata(metadata: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(metadata, Mapping):
        return get_theme()
    override = metadata.get("theme_override")
    if isinstance(override, Mapping):
        return resolve_theme(override)
    theme = metadata.get("theme")
    if isinstance(theme, (str, Mapping)):
        return resolve_theme(theme)
    return get_theme()
