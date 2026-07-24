from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .ledger import canonical_json, utc_now


class GradeFinalizeError(RuntimeError):
    pass


def finalize_grade(
    proposed: dict[str, Any],
    *,
    repo_root: Path,
    script_path: str,
    raw_log_path: str,
    artifact_path: str,
) -> tuple[dict[str, Any], dict[str, str]]:
    repo = repo_root.resolve()
    script_file = _safe_session_path(repo, script_path)
    raw_file = _safe_session_path(repo, raw_log_path)
    grade_file = _safe_session_path(repo, artifact_path, must_exist=False)
    if grade_file.name != "grading_result.json":
        raise GradeFinalizeError("canonical grade artifact must be grading_result.json")
    if grade_file.parent != script_file.parent or grade_file.parent != raw_file.parent:
        raise GradeFinalizeError("script, raw log, and grade must share one session directory")
    script = _read_json(script_file)
    _validate_json(
        proposed,
        repo / "training/pipeline/grading_result_schema.json",
    )
    if proposed["session_id"] != script["session_id"]:
        raise GradeFinalizeError("grade session_id does not match the fixed script")
    if proposed["script_id"] != script["script_id"]:
        raise GradeFinalizeError("grade script_id does not match the fixed script")
    expected_ids = [item["item_id"] for item in script["items"]]
    actual_ids = [item["item_id"] for item in proposed["item_grades"]]
    if actual_ids != expected_ids or len(actual_ids) != len(set(actual_ids)):
        raise GradeFinalizeError("item grades must match fixed script order exactly")
    _validate_raw_log(raw_file, script, expected_ids)
    turn_grades = grade_file.parent / "turn_grades.jsonl"
    report_md = grade_file.parent / "report.md"
    if grade_file.exists():
        existing = _read_json(grade_file)
        replay_model = {
            key: existing.get(
                "model_recommended_action" if key == "recommended_action" else key
            )
            for key in proposed
        }
        if replay_model != proposed:
            raise GradeFinalizeError("immutable artifact conflict: grading_result.json")
        paths = (grade_file, turn_grades, report_md)
        if not all(path.is_file() for path in paths):
            raise GradeFinalizeError("canonical grade evidence is incomplete")
        return existing, {
            path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in paths
        }

    grade = dict(proposed)
    grade["finalized_at"] = utc_now()
    grade["source_artifacts"] = {
        "script": script_path,
        "raw_log": raw_log_path,
    }
    grade["counts"] = _counts(grade["item_grades"])
    grade["model_recommended_action"] = grade.pop("recommended_action")
    deterministic = _deterministic_decision(grade)
    grade["decision"] = deterministic
    grade["session_passed"] = deterministic in {"PASS_AUTONEXT", "PASS_BUT_BUFFER"}
    grade["content_sha256"] = hashlib.sha256(canonical_json(grade)).hexdigest()

    _write_once(grade_file, json.dumps(grade, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write_once(
        turn_grades,
        "".join(
            json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n"
            for item in grade["item_grades"]
        ),
    )
    _write_once(report_md, _markdown(grade))
    paths = (grade_file, turn_grades, report_md)
    return grade, {
        path.relative_to(repo).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in paths
    }


def _deterministic_decision(grade: dict[str, Any]) -> str:
    items = grade["item_grades"]
    statuses = [
        item[field]
        for item in items
        for field in ("original_status", "after_correction_status")
        if item[field] != "not_applicable"
    ]
    any_correct = "correct" in statuses
    unsafe = (
        any(status in {"wrong_off_topic", "ungradable"} for status in statuses)
        or any(item["malformed"] or item["repetition_collapse"] for item in items)
        or any(float(item["confidence"]) < 0.70 for item in items)
    )
    recommendation = grade["model_recommended_action"]
    if unsafe or not any_correct:
        return "ESCALATE_ORCHESTRATOR"
    if grade["requires_orchestrator"]:
        return "ESCALATE_ORCHESTRATOR"
    if recommendation == "PASS_AUTONEXT":
        return "PASS_AUTONEXT"
    if recommendation == "PASS_BUT_BUFFER":
        return "PASS_BUT_BUFFER"
    if recommendation == "RETRY_SAME_WORD":
        return "RETRY_SAME_WORD"
    return "ESCALATE_ORCHESTRATOR"


def _counts(items: list[dict[str, Any]]) -> dict[str, int]:
    result = {
        "items": len(items),
        "original_correct": 0,
        "after_correction_correct": 0,
        "wrong_off_topic": 0,
        "ungradable": 0,
        "malformed": 0,
        "repetition_collapse": 0,
    }
    for item in items:
        result["original_correct"] += item["original_status"] == "correct"
        result["after_correction_correct"] += (
            item["after_correction_status"] == "correct"
        )
        result["wrong_off_topic"] += sum(
            item[field] == "wrong_off_topic"
            for field in ("original_status", "after_correction_status")
        )
        result["ungradable"] += sum(
            item[field] == "ungradable"
            for field in ("original_status", "after_correction_status")
        )
        result["malformed"] += item["malformed"]
        result["repetition_collapse"] += item["repetition_collapse"]
    return result


def _validate_raw_log(
    path: Path, script: dict[str, Any], expected_ids: list[str]
) -> None:
    if not path.is_file():
        raise GradeFinalizeError("raw trainer log is missing")
    seen_prompts: list[str] = []
    last_sequence = -1
    for line in path.read_text(encoding="utf-8").splitlines():
        event = json.loads(line)
        if event.get("session_id") != script["session_id"]:
            raise GradeFinalizeError("raw log session differs from fixed script")
        sequence = event.get("sequence_index")
        if not isinstance(sequence, int) or sequence != last_sequence + 1:
            raise GradeFinalizeError("raw log sequence is not contiguous")
        last_sequence = sequence
        if event.get("event_type") == "user_prompt":
            seen_prompts.append(str(event.get("item_id")))
    if seen_prompts != expected_ids:
        raise GradeFinalizeError("raw log does not contain every scripted prompt in order")


def _markdown(grade: dict[str, Any]) -> str:
    lines = [
        f"# Session grade: {grade['session_id']}",
        "",
        f"- Decision: `{grade['decision']}`",
        f"- Model recommendation: `{grade['model_recommended_action']}`",
        f"- Passed: `{str(grade['session_passed']).lower()}`",
        f"- Summary: {grade['summary']}",
        "",
        "## Item grades",
        "",
    ]
    for item in grade["item_grades"]:
        lines.append(
            f"- `{item['item_id']}`: original `{item['original_status']}`, "
            f"after correction `{item['after_correction_status']}`, "
            f"confidence {item['confidence']:.2f} — {item['rationale']}"
        )
    return "\n".join(lines) + "\n"


def _safe_session_path(repo: Path, relative: str, *, must_exist: bool = True) -> Path:
    if not isinstance(relative, str) or not relative:
        raise GradeFinalizeError("session artifact path must be non-empty")
    path = (repo / relative).resolve()
    sessions = (repo / "training/pipeline/msm/sessions").resolve()
    if sessions not in path.parents:
        raise GradeFinalizeError("session artifact escapes the sessions root")
    if must_exist and not path.is_file():
        raise GradeFinalizeError(f"session artifact does not exist: {relative}")
    return path


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise GradeFinalizeError(f"{path.name} must contain a JSON object")
    return value


def _validate_json(value: dict[str, Any], schema_path: Path) -> None:
    try:
        import jsonschema
    except ImportError as exc:
        raise GradeFinalizeError("python jsonschema is required") from exc
    schema = _read_json(schema_path)
    try:
        jsonschema.validate(value, schema)
    except jsonschema.ValidationError as exc:
        raise GradeFinalizeError(f"{schema_path.name}: {exc.message}") from exc


def _write_once(path: Path, content: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    encoded = content.encode("utf-8")
    if path.exists():
        if path.read_bytes() != encoded:
            raise GradeFinalizeError(f"immutable artifact conflict: {path.name}")
        return
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
