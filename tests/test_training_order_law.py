from __future__ import annotations

from pathlib import Path

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import SafetyError
from mission_hub.lesson_policy import policy_sha256
from mission_hub.training_order import ORDER_POLICY, require_dependency_order


REPO = Path(__file__).resolve().parents[1]


def test_no_commissioned_training_script_contains_a_shuffle_path() -> None:
    forbidden = (
        ".shuffle(", "RandomSampler", "SubsetRandomSampler",
        "WeightedRandomSampler", "np.random.permutation",
    )
    scripts = sorted((REPO / "meta" / "scripts").glob("train*.py"))
    assert scripts
    for path in scripts:
        source = path.read_text(encoding="utf-8")
        assert not any(token in source for token in forbidden), path


def test_dependency_certificate_is_bound_to_sequence_and_parent() -> None:
    identity_policy = load_config_bundle(REPO / "config/mission_hub").identity_policy
    subject = {"id": "art-subject", "sha256": "a" * 64}
    parent = {"id": "art-parent", "sha256": "b" * 64}
    validation = {"kind": "validation_report", "manifest": {
        "schema_version": "ninereeds_dependency_order_validation_v1",
        "validation_scope": "dependency_order", "status": "passed",
        "subject_artifact_id": subject["id"], "subject_sha256": subject["sha256"],
        "parent_artifact_id": parent["id"], "parent_sha256": parent["sha256"],
        **ORDER_POLICY, "dependency_evidence_sha256": "c" * 64,
        "lesson_policy_status": "passed", "lesson_policy_id": identity_policy["id"],
        "lesson_policy_version": identity_policy["version"],
        "lesson_policy_sha256": policy_sha256(identity_policy), "identity_scope": "excluded",
    }}

    require_dependency_order(
        subject, validation, ORDER_POLICY, parent=parent,
        identity_policy=identity_policy, identity_scope="excluded",
    )

    wrong_parent = {"id": "art-other", "sha256": "d" * 64}
    with pytest.raises(SafetyError, match="exact training sequence"):
        require_dependency_order(
            subject, validation, ORDER_POLICY, parent=wrong_parent,
            identity_policy=identity_policy, identity_scope="excluded",
        )


def test_training_reports_declare_the_global_order_policy() -> None:
    for relative in ("meta/scripts/train_cortex.py", "meta/scripts/train_visual_projector.py"):
        source = (REPO / relative).read_text(encoding="utf-8")
        assert '"example_order": "declared"' in source
        assert '"shuffle_allowed": False' in source
