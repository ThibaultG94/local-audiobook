"""Bootstrap settings loader with minimal YAML support for local defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency at runtime
    yaml = None


def _coerce_scalar(value: str) -> str | bool | int | float | None:
    cleaned = value.strip()
    unquoted = cleaned.strip('"').strip("'")

    lowered = unquoted.lower()
    if lowered in {"null", "none", "~"}:
        return None
    if lowered == "true":
        return True
    if lowered == "false":
        return False

    if unquoted.isdigit() or (unquoted.startswith("-") and unquoted[1:].isdigit()):
        return int(unquoted)

    try:
        if "." in unquoted:
            return float(unquoted)
    except ValueError:
        pass

    return unquoted


def _fallback_load_simple_yaml(path: str | Path) -> dict[str, Any]:
    """Load a simple, indentation-based YAML mapping (fallback parser)."""

    lines = Path(path).read_text(encoding="utf-8").splitlines()
    root: dict[str, Any] = {}
    stack: list[tuple[int, dict[str, Any]]] = [(-1, root)]

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue

        indent = len(line) - len(line.lstrip(" "))
        key_part, _, value_part = line.lstrip().partition(":")
        key = key_part.strip()
        value = value_part.strip()

        while stack and indent <= stack[-1][0]:
            stack.pop()

        current_dict = stack[-1][1]
        if value == "":
            child: dict[str, Any] = {}
            current_dict[key] = child
            stack.append((indent, child))
        else:
            current_dict[key] = _coerce_scalar(value)

    return root


def load_simple_yaml(path: str | Path) -> dict[str, Any]:
    """Load YAML configuration.

    Uses PyYAML when available; otherwise falls back to a small local parser.
    """

    if yaml is not None:
        content = Path(path).read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError("Root YAML document must be a mapping")
        return data

    return _fallback_load_simple_yaml(path)
