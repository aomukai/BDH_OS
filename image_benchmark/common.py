from __future__ import annotations

import json
import re
from typing import Any


PROMPT = """Audit ONE image for use in a literal visual training corpus.
Reply with exactly one JSON object and no markdown or explanation. Use every key in this shape:
{"admission":"usable","visible_text":false,"watermark":false,"quality_flags":[],"objects":[{"name":"dog","count":1}],"relationships":[{"subject":"dog","predicate":"under","object":"table"}],"literal_caption":"A dog is under a table.","uncertainties":[]}
admission must be usable, unusable, or uncertain. Reject watermarks, severe blur, corruption, incoherent imagery, or misleading composites. visible_text and watermark are booleans. quality_flags and uncertainties are arrays of short strings. objects contains confidently visible object kinds with exact visible counts; omit uncountable/background things. relationships contains only plainly visible spatial or action relations. The caption must be concise, literal, and avoid unsupported claims."""


REQUIRED_KEYS = {
    "admission", "visible_text", "watermark", "quality_flags", "objects",
    "relationships", "literal_caption", "uncertainties",
}

SEVERE_QUALITY_MARKERS = {
    "corrupt",
    "corruption",
    "incoherent imagery",
    "severe artifact",
    "severe artifacts",
    "severe blur",
    "severely blurred",
}


def parse_response(raw: str) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    candidate = raw.strip()
    if candidate.startswith("```"):
        candidate = re.sub(r"^```(?:json)?\s*|\s*```$", "", candidate, flags=re.I | re.S)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return None, [f"json:{exc.msg}"]
    if not isinstance(value, dict):
        return None, ["root:not_object"]
    missing = REQUIRED_KEYS - value.keys()
    extra = value.keys() - REQUIRED_KEYS
    if missing:
        errors.append("missing:" + ",".join(sorted(missing)))
    if extra:
        errors.append("extra:" + ",".join(sorted(extra)))
    if value.get("admission") not in {"usable", "unusable", "uncertain"}:
        errors.append("admission:invalid")
    for key in ("visible_text", "watermark"):
        if not isinstance(value.get(key), bool):
            errors.append(f"{key}:not_boolean")
    for key in ("quality_flags", "objects", "relationships", "uncertainties"):
        if not isinstance(value.get(key), list):
            errors.append(f"{key}:not_array")
    if not isinstance(value.get("literal_caption"), str):
        errors.append("literal_caption:not_string")
    return value, errors


def semantic_contract_errors(value: dict[str, Any] | None) -> list[str]:
    if value is None:
        return []
    errors: list[str] = []
    flags = value.get("quality_flags") if isinstance(value.get("quality_flags"), list) else []
    if value.get("watermark") is True and value.get("admission") == "usable":
        errors.append("policy:usable_watermark")
    if "watermark" in flags and value.get("watermark") is not True:
        errors.append("policy:watermark_flag_disagrees")
    severe = {"severe blur", "corruption", "incoherent imagery"}
    if value.get("admission") == "usable" and severe.intersection(
        str(flag).casefold() for flag in flags
    ):
        errors.append("policy:usable_severe_defect")
    return errors


def admission_policy(
    value: dict[str, Any] | None,
    schema_errors: list[str] | None = None,
    watermark_adjudication: str | None = None,
) -> tuple[str, list[str]]:
    """Apply corpus policy to extracted evidence without trusting model judgement."""
    if value is None:
        return "unresolved", ["unparseable_response"]
    if schema_errors:
        return "unresolved", [f"schema:{error}" for error in schema_errors]

    if watermark_adjudication == "uncertain":
        return "unresolved", ["watermark_adjudication:uncertain"]

    reasons: list[str] = []
    confirmed_watermark = watermark_adjudication == "true_watermark_or_added_overlay"
    cleared_watermark = watermark_adjudication == "in_scene_text_or_branding"
    if confirmed_watermark or (value.get("watermark") is True and not cleared_watermark):
        reasons.append("watermark")

    flags = value.get("quality_flags")
    normalized_flags = {
        str(flag).strip().casefold().replace("_", "-")
        for flag in (flags if isinstance(flags, list) else [])
    }
    for flag in sorted(normalized_flags):
        words = flag.replace("-", " ")
        if words in SEVERE_QUALITY_MARKERS or (
            "severe" in words and any(term in words for term in ("blur", "artifact", "compression"))
        ):
            reasons.append(f"quality:{flag}")

    uncertainties = value.get("uncertainties")
    if isinstance(uncertainties, list) and uncertainties:
        reasons.extend(f"uncertainty:{item}" for item in uncertainties)

    hard_rejections = [reason for reason in reasons if not reason.startswith("uncertainty:")]
    if hard_rejections:
        return "unusable", reasons
    if reasons or value.get("admission") == "uncertain":
        return "unresolved", reasons or ["model_uncertain"]
    return "usable", []
