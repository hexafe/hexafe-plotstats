from __future__ import annotations

from typing import Mapping


_TRANSLATIONS: dict[str, dict[str, str]] = {
    "en": {
        "min": "Min",
        "max": "Max",
        "mean": "Mean",
        "median": "Median",
        "std_dev": "Std Dev",
        "model": "Model",
        "fit_quality": "Fit quality",
        "warning": "Warning",
        "normality": "Normality",
        "samples": "Samples",
        "count": "Count",
        "density": "Density",
        "group": "group",
        "value": "value",
    },
    "pl": {
        "min": "Min",
        "max": "Maks",
        "mean": "Srednia",
        "median": "Mediana",
        "std_dev": "Odch. std",
        "model": "Model",
        "fit_quality": "Jakosc dopasowania",
        "warning": "Ostrzezenie",
        "normality": "Normalnosc",
        "samples": "Probki",
        "count": "Liczba",
        "density": "Gestosc",
        "group": "grupa",
        "value": "wartosc",
    },
    "de": {
        "min": "Min",
        "max": "Max",
        "mean": "Mittelwert",
        "median": "Median",
        "std_dev": "Std. Abw.",
        "model": "Modell",
        "fit_quality": "Anpassung",
        "warning": "Warnung",
        "normality": "Normalitat",
        "samples": "Stichproben",
        "count": "Anzahl",
        "density": "Dichte",
        "group": "Gruppe",
        "value": "Wert",
    },
}

_current_locale = "en"


def available_locales() -> tuple[str, ...]:
    return tuple(_TRANSLATIONS)


def set_locale(locale: str | Mapping[str, str]) -> str:
    global _current_locale
    if isinstance(locale, Mapping):
        _TRANSLATIONS["custom"] = {str(key): str(value) for key, value in locale.items()}
        _current_locale = "custom"
        return _current_locale
    locale_key = str(locale or "en").split(".", maxsplit=1)[0].replace("-", "_").casefold()
    language = locale_key.split("_", maxsplit=1)[0]
    if language not in _TRANSLATIONS:
        valid = ", ".join(available_locales())
        raise ValueError(f"unknown locale {locale!r}; choose one of: {valid}")
    _current_locale = language
    return _current_locale


def get_locale() -> str:
    return _current_locale


def translate(key: str, default: str | None = None) -> str:
    locale_map = _TRANSLATIONS.get(_current_locale, {})
    return locale_map.get(key, _TRANSLATIONS["en"].get(key, default if default is not None else key))
