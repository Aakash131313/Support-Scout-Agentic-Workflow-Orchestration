"""Tolerant parsing of structured tool arguments.

A tool-calling model will send a JSON array or object as a *native* value
(`[]`, `{"a": 1}`) about as often as it sends a JSON *string* (`"[]"`). Declaring
such a parameter as `str` makes smolagents reject the native form with
"Argument X has type 'array' but should be 'string'" before the tool even runs,
which wastes a step and teaches the model nothing useful.

So structured parameters are declared `Any` and normalised here instead. The tool
accepts either form and validates the actual content, which is what matters.
"""
from __future__ import annotations

import json
from typing import Any


class ToolArgumentError(ValueError):
    """The argument could not be interpreted as the expected structure."""


def _parse_if_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    text = value.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ToolArgumentError(f"not valid JSON: {exc}") from exc


def coerce_json_object(value: Any, *, field: str) -> dict[str, Any]:
    """Return a dict from either a JSON object or a JSON-object string."""
    parsed = _parse_if_string(value)
    if parsed is None:
        raise ToolArgumentError(f"{field} is empty; a JSON object is required")
    if isinstance(parsed, dict):
        return parsed
    raise ToolArgumentError(
        f"{field} must be a JSON object, received {type(parsed).__name__}"
    )


def coerce_json_string_list(value: Any, *, field: str, allow_empty: bool = True) -> list[str]:
    """Return a list of strings from a JSON array, a JSON-array string, or one string."""
    if isinstance(value, str):
        text = value.strip()
        if not text:
            parsed = None
        elif text.startswith(("[", "{")):
            # Clearly intended as JSON, so a parse failure is a genuine error.
            parsed = _parse_if_string(text)
        else:
            # A bare string is a single item. Models do this when there is only one.
            parsed = [text]
    else:
        parsed = value

    if parsed is None:
        if allow_empty:
            return []
        raise ToolArgumentError(f"{field} is empty; a non-empty JSON array is required")

    if isinstance(parsed, str):
        parsed = [parsed]

    if not isinstance(parsed, list):
        raise ToolArgumentError(
            f"{field} must be a JSON array of strings, received {type(parsed).__name__}"
        )

    items = [str(item).strip() for item in parsed if str(item).strip()]

    if not items and not allow_empty:
        raise ToolArgumentError(f"{field} must contain at least one non-empty string")

    return items
