from __future__ import annotations


def compact_float(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}g}"


def normalize_label(value: object) -> str:
    text = str(value).strip()
    return text or "unnamed"

