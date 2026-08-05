from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class ScriptFinalizeError(RuntimeError):
    pass


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def finalize_msm_script(
    proposed: dict[str, Any],
    *,
    repo_root: Path,
    orchestrator_plan_id: str,
    session_id: str,
    checkpoint: str,
    executor_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Replace environment-derived model guesses and compute real fingerprints."""
    script = copy.deepcopy(proposed)
    schema_path = repo_root / "training/pipeline/script_schema.json"
    try:
        import jsonschema
    except ImportError as exc:
        raise ScriptFinalizeError("python jsonschema is required") from exc
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(script, schema)
    except jsonschema.ValidationError as exc:
        raise ScriptFinalizeError(f"proposed script is invalid: {exc.message}") from exc
    for value, field in (
        (orchestrator_plan_id, "orchestrator_plan_id"),
        (session_id, "session_id"),
        (executor_id, "executor_id"),
    ):
        if not isinstance(value, str) or not value:
            raise ScriptFinalizeError(f"{field} must be non-empty")

    script["script_id"] = f"script-{session_id}"
    script["session_id"] = session_id
    script["orchestrator_plan_id"] = orchestrator_plan_id
    script["script_author"] = f"executor:{executor_id}"
    script["created_at"] = created_at or utc_now()
    script["checkpoint"] = checkpoint
    script["executor_context"] = {
        "executor_id": executor_id,
        "selection_method": "fixed",
        "meta_scratchpad_injected": False,
        "meta_scratchpad_path": None,
    }

    structural = {
        "schema_version": script["schema_version"],
        "concept": script["concept"],
        "session_mode": script["session_mode"],
        "intended_stage": script["intended_stage"],
        "intended_failure_targets": script["intended_failure_targets"],
        "items": [
            {
                "stage": item["stage"],
                "ask_after_correction": item["ask_after_correction"],
                "target_failure_modes": item["target_failure_modes"],
                "training_answer_max_bytes": item["training_answer_max_bytes"],
            }
            for item in script["items"]
        ],
    }
    prompts = [
        {
            "user_prompt": normalize_text(item["user_prompt"]),
            "teacher_correction": (
                normalize_text(item["teacher_correction"])
                if item["teacher_correction"] is not None
                else None
            ),
        }
        for item in script["items"]
    ]
    previous = script["script_fingerprint"]
    script["script_fingerprint"] = {
        "algorithm": "msm_script_fingerprint_v1",
        "structural_hash": hashlib.sha256(canonical(structural)).hexdigest(),
        "prompt_hash": hashlib.sha256(canonical(prompts)).hexdigest(),
        "question_type_sequence": [item["stage"] for item in script["items"]],
        "contrast_pairs": previous["contrast_pairs"],
    }
    try:
        jsonschema.validate(script, schema)
    except jsonschema.ValidationError as exc:
        raise ScriptFinalizeError(f"finalized script is invalid: {exc.message}") from exc
    for item in script["items"]:
        answer = item.get("teacher_correction")
        if not isinstance(answer, str) or not answer.strip():
            expected = (
                item.get("expected_after_correction")
                if item.get("ask_after_correction")
                else item.get("expected_original")
            )
            acceptable = expected.get("acceptable") if isinstance(expected, dict) else None
            answer = next(
                (
                    value.strip()
                    for value in (acceptable if isinstance(acceptable, list) else [])
                    if isinstance(value, str) and value.strip()
                ),
                None,
            )
        if answer is None:
            raise ScriptFinalizeError(
                f"{item['item_id']} has no usable training answer"
            )
        maximum = item["training_answer_max_bytes"]
        if len(answer.encode("utf-8")) > maximum:
            raise ScriptFinalizeError(
                f"{item['item_id']} training answer exceeds {maximum} bytes"
            )
    return script
