"""Non-negotiable training-order safety contract."""

from __future__ import annotations

from typing import Any

from .errors import SafetyError
from .lesson_policy import IDENTITY_SCOPES, policy_sha256


ORDER_POLICY = {
    "order_policy": "declared_only",
    "shuffle_allowed": False,
    "dependency_order_required": True,
}


def require_dependency_order(
    subject: dict[str, Any],
    validation: dict[str, Any] | None,
    policy: dict[str, Any],
    *,
    parent: dict[str, Any] | None,
    identity_policy: dict[str, Any],
    identity_scope: str,
) -> None:
    """Reject training unless exact subject bytes passed dependency validation."""

    if any(policy.get(key) != value for key, value in ORDER_POLICY.items()):
        raise SafetyError("training requires immutable declared dependency order")
    if validation is None or validation.get("kind") != "validation_report":
        raise SafetyError("training requires a dependency-order validation artifact")
    manifest = validation.get("manifest")
    if not isinstance(manifest, dict) or any(
        manifest.get(key) != value
        for key, value in {
            "schema_version": "ninereeds_dependency_order_validation_v1",
            "validation_scope": "dependency_order",
            "status": "passed",
            "subject_artifact_id": subject["id"],
            "subject_sha256": subject["sha256"],
            "parent_artifact_id": None if parent is None else parent["id"],
            "parent_sha256": None if parent is None else parent["sha256"],
            "order_policy": "declared_only",
            "shuffle_allowed": False,
            "dependency_order_required": True,
        }.items()
    ):
        raise SafetyError("dependency-order validation does not certify the exact training sequence")
    if identity_scope not in IDENTITY_SCOPES or any(
        manifest.get(key) != value
        for key, value in {
            "lesson_policy_status": "passed",
            "lesson_policy_id": identity_policy["id"],
            "lesson_policy_version": identity_policy["version"],
            "lesson_policy_sha256": policy_sha256(identity_policy),
            "identity_scope": identity_scope,
        }.items()
    ):
        raise SafetyError("training material did not pass the exact active identity and lesson policy")
    evidence_sha256 = manifest.get("dependency_evidence_sha256")
    if not isinstance(evidence_sha256, str) or len(evidence_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in evidence_sha256
    ):
        raise SafetyError("dependency-order validation lacks immutable prerequisite evidence")
