from __future__ import annotations


def require_equal_length(left: object, right: object, *, left_name: str = "x", right_name: str = "y") -> None:
    if len(left) != len(right):  # type: ignore[arg-type]
        raise ValueError(f"{left_name} and {right_name} must have the same length")

