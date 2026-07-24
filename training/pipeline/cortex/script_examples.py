from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class CortexScriptError(ValueError):
    pass


def validate_msm_script(script: Any, schema_path: Path) -> dict[str, Any]:
    if not isinstance(script, dict):
        raise CortexScriptError("MSM script must be a JSON object")
    try:
        import jsonschema
    except ImportError as exc:
        raise CortexScriptError("python jsonschema is required") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(script, schema)
    except jsonschema.ValidationError as exc:
        raise CortexScriptError(f"MSM script is invalid: {exc.message}") from exc
    return script


def examples_from_msm_script(
    script: Any,
    schema_path: Path,
) -> list[tuple[str, str]]:
    value = validate_msm_script(script, schema_path)
    examples: list[tuple[str, str]] = []
    for item in value["items"]:
        answer = item.get("teacher_correction")
        if not isinstance(answer, str) or not answer.strip():
            answer = (
                _first_acceptable(item.get("expected_after_correction"))
                if item["ask_after_correction"]
                else None
            )
        if answer is None:
            answer = _first_acceptable(item.get("expected_original"))
        if answer is None:
            raise CortexScriptError(
                f"{item['item_id']} has no teacher or acceptable training answer"
            )
        maximum = item["training_answer_max_bytes"]
        if len(answer.encode("utf-8")) > maximum:
            raise CortexScriptError(
                f"{item['item_id']} training answer exceeds {maximum} bytes"
            )
        examples.append((item["user_prompt"], answer))
    return examples


def _first_acceptable(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    acceptable = value.get("acceptable")
    if not isinstance(acceptable, list):
        return None
    return next(
        (
            answer.strip()
            for answer in acceptable
            if isinstance(answer, str) and answer.strip()
        ),
        None,
    )
