"""Bootstrap settings loader with minimal YAML support for local defaults."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _coerce_scalar(value: str) -> str | bool:
    cleaned = value.strip()
    if cleaned.lower() == "true":
        return True
    if cleaned.lower() == "false":
        return False
    return cleaned.strip('"').strip("'")


def load_simple_yaml(path: str | Path) -> dict[str, Any]:
    """Load a simple, indentation-based YAML mapping.

    Supports the subset used in Story 1.1 configuration files.
    """

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

