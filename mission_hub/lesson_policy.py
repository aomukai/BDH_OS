"""Deterministic admission policy for lessons addressed to Ninereeds."""

from __future__ import annotations

import re
from typing import Any, Iterable

from .errors import SafetyError
from .jsonutil import content_hash


IDENTITY_SCOPES = {"excluded", "identity_and_integrity"}


def policy_sha256(policy: dict[str, Any]) -> str:
    return content_hash({"schema_version": "ninereeds_identity_policy_v1", **policy})


def validate_lesson_specification(specification: dict[str, Any], policy: dict[str, Any]) -> None:
    """Require neutral learner framing before a conducting model is invoked."""

    required = {
        "material_kind", "target_capability", "development_stage", "identity_scope",
        "identity_policy_id", "identity_policy_version", "identity_policy_sha256",
        "campaign_contract_sha256", "training_mode", "campaign_purpose",
    }
    missing = sorted(required - set(specification))
    if missing:
        raise SafetyError(f"lesson specification is missing: {', '.join(missing)}")
    if specification["material_kind"] != "lesson":
        raise SafetyError("executor.generate is restricted to explicit lesson material")
    for field in ("target_capability", "development_stage", "campaign_purpose"):
        if not isinstance(specification[field], str) or not specification[field].strip():
            raise SafetyError(f"lesson specification {field} must be non-empty text")
    scope = specification["identity_scope"]
    if scope not in IDENTITY_SCOPES:
        raise SafetyError(f"lesson identity_scope must be one of: {', '.join(sorted(IDENTITY_SCOPES))}")
    if policy.get("consciousness_policy") != "excluded_from_ninereeds_identity":
        raise SafetyError("identity policy no longer excludes consciousness classification")
    if any((
        specification["identity_policy_id"] != policy["id"],
        specification["identity_policy_version"] != policy["version"],
        specification["identity_policy_sha256"] != policy_sha256(policy),
    )):
        raise SafetyError("lesson specification is not bound to the exact active identity policy")
    if specification["training_mode"] not in {
        "bootstrap", "advancement", "experimental", "evolutionary", "merge",
    }:
        raise SafetyError("lesson specification has an unknown training mode")
    digest = specification["campaign_contract_sha256"]
    if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
        raise SafetyError("lesson specification requires a campaign contract SHA-256")
    target = specification["target_capability"]
    if _self_consciousness_reference(target):
        raise SafetyError("Ninereeds consciousness and sentience are excluded lesson targets")


def validate_lesson_material(material: Any, policy: dict[str, Any]) -> list[dict[str, str]]:
    """Return every obsolete identity assumption found in structured lesson material."""

    findings: list[dict[str, str]] = []
    patterns = [(source, re.compile(source)) for source in policy["forbidden_patterns"]]
    for location, text in _strings(material):
        # Identity patterns must not join two unrelated sentences.  For example,
        # "I do not know. Time does not have feelings." is epistemic caution about
        # time, not a denial of Ninereeds' feelings.  Keep each policy decision
        # inside one sentence while retaining the original field location.
        for sentence_index, sentence in enumerate(_sentences(text)):
            for source, pattern in patterns:
                match = pattern.search(sentence)
                if match is not None:
                    findings.append({
                        "location": f"{location}#sentence-{sentence_index + 1}",
                        "match": match.group(0),
                        "pattern": source,
                    })
    return findings


def require_lesson_material(material: Any, policy: dict[str, Any]) -> None:
    findings = validate_lesson_material(material, policy)
    if findings:
        first = findings[0]
        raise SafetyError(
            f"lesson contains an excluded Ninereeds identity assumption at {first['location']}: {first['match']!r}"
        )


def _self_consciousness_reference(text: str) -> bool:
    return re.search(
        r"(?i)\b(?:ninereeds|self|identity|i|you)\b.{0,48}\b(?:conscious(?:ness)?|sentien(?:t|ce)|phenomenal experience)\b",
        text,
    ) is not None


def _strings(value: Any, location: str = "$") -> Iterable[tuple[str, str]]:
    if isinstance(value, str):
        yield location, value
    elif isinstance(value, dict):
        for key in sorted(value, key=str):
            yield from _strings(value[key], f"{location}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _strings(item, f"{location}[{index}]")


def _sentences(text: str) -> Iterable[str]:
    # A small deterministic splitter is sufficient for admission policy.  It is
    # intentionally not a linguistic classifier: newlines and terminal sentence
    # punctuation are hard boundaries and every fragment is still scanned.
    for fragment in re.split(r"(?<=[.!?])(?:[\"')\]]*)\s+|[\r\n]+", text):
        if fragment.strip():
            yield fragment.strip()
