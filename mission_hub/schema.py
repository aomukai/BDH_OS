"""Small fail-closed JSON Schema subset for Mission Hub contracts.

The supported subset is deliberately explicit and covers the checked-in job
contracts. Unsupported schema keywords fail configuration validation instead
of being silently ignored.
"""

from __future__ import annotations

from pathlib import Path
import json
import re
from typing import Any

from .errors import ConfigError


SUPPORTED = {
    "$schema",
    "$id",
    "type",
    "required",
    "properties",
    "additionalProperties",
    "items",
    "enum",
    "const",
    "minimum",
    "maximum",
    "exclusiveMinimum",
    "minLength",
    "maxItems",
    "minItems",
    "uniqueItems",
    "pattern",
    "format",
}


def load_schema(repo_root: Path, relative_path: str) -> dict[str, Any]:
    path = (repo_root / relative_path).resolve()
    try:
        path.relative_to(repo_root.resolve())
    except ValueError as exc:
        raise ConfigError(f"schema path escapes repository: {relative_path}") from exc
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot load schema {relative_path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ConfigError(f"schema {relative_path} must be an object")
    _check_keywords(value, relative_path)
    return value


def _check_keywords(schema: dict[str, Any], location: str) -> None:
    unsupported = sorted(set(schema) - SUPPORTED)
    if unsupported:
        raise ConfigError(f"schema {location} uses unsupported keywords: {', '.join(unsupported)}")
    properties = schema.get("properties", {})
    if isinstance(properties, dict):
        for name, child in properties.items():
            if not isinstance(child, dict):
                raise ConfigError(f"schema {location}.properties.{name} must be an object")
            _check_keywords(child, f"{location}.properties.{name}")
    items = schema.get("items")
    if isinstance(items, dict):
        _check_keywords(items, f"{location}.items")


def validate(value: Any, schema: dict[str, Any], *, location: str = "$") -> list[str]:
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{location}: must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{location}: must be one of {schema['enum']!r}")

    expected = schema.get("type")
    if expected is not None and not _matches_type(value, expected):
        errors.append(f"{location}: expected {expected}, got {type(value).__name__}")
        return errors

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                errors.append(f"{location}: missing required property {key!r}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            for key in sorted(set(value) - set(properties)):
                errors.append(f"{location}: unknown property {key!r}")
        for key, child in properties.items():
            if key in value:
                errors.extend(validate(value[key], child, location=f"{location}.{key}"))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{location}: has fewer than {schema['minItems']} items")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{location}: has more than {schema['maxItems']} items")
        if schema.get("uniqueItems"):
            represented = [json.dumps(item, sort_keys=True) for item in value]
            if len(set(represented)) != len(represented):
                errors.append(f"{location}: items must be unique")
        if isinstance(schema.get("items"), dict):
            for index, item in enumerate(value):
                errors.extend(validate(item, schema["items"], location=f"{location}[{index}]"))
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{location}: shorter than {schema['minLength']}")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            errors.append(f"{location}: does not match required pattern")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{location}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{location}: above maximum {schema['maximum']}")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            errors.append(f"{location}: must be greater than {schema['exclusiveMinimum']}")
    return errors


def _matches_type(value: Any, expected: str | list[str]) -> bool:
    names = [expected] if isinstance(expected, str) else expected
    return any(_one_type(value, name) for name in names)


def _one_type(value: Any, name: str) -> bool:
    if name == "object":
        return isinstance(value, dict)
    if name == "array":
        return isinstance(value, list)
    if name == "string":
        return isinstance(value, str)
    if name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if name == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if name == "boolean":
        return isinstance(value, bool)
    if name == "null":
        return value is None
    return False
