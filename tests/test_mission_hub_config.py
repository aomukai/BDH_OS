from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from mission_hub.config import load_config_bundle, model_supports_route
from mission_hub.errors import ConfigError
from mission_hub.schema import load_schema, validate


REPO = Path(__file__).resolve().parents[1]


def test_repository_configuration_is_valid_with_protected_retention_only() -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    assert bundle.base["safety"] == {
        "live_execution": True,
        "automatic_pruning": True,
        "automatic_campaign_rollover": False,
        "allow_git_mutation": False,
        "require_release_match": True,
        "require_config_match": True,
    }
    assert bundle.jobs["system.healthcheck"]["enabled"] is True
    assert {job_type for job_type, definition in bundle.jobs.items() if definition["enabled"]} == {
            "system.healthcheck", "corpus.build", "corpus.assemble_generated", "corpus.validate", "checkpoint.certify", "checkpoint.probe",
            "model.train", "model.evaluate", "model.chat", "checkpoint.compare",
            "visual.plan", "visual.generate", "visual.inspect", "visual.caption", "visual.decide",
            "visual.review", "visual.pack_finalize", "visual.encode", "visual.features_finalize", "visual.experience_compile",
            "visual.plan_exact", "model.initialize", "model.multimodal_train", "model.multimodal_evaluate", "model.merge",
            "campaign.decide",
            "operations.respond",
    }
    assert bundle.jobs["corpus.build"]["executor_role"] == "mission_hub"
    assert bundle.base["safety"]["live_execution"] is True
    assert bundle.retention["mode"] == "protected_registry_automatic"
    assert bundle.retention["deletion_requires_decision"] is False
    assert bundle.retention["inventory_timeout_seconds"] == 3600
    assert bundle.training == {
        "order_policy": "declared_only", "shuffle_allowed": False,
        "dependency_order_required": True,
        "max_examples_per_session": 10000,
        "max_completion_utf8_bytes": 512,
        "observer_fixture": {
            "id": "gate-credit-v1", "version": 1, "required": True,
            "log_every_n_steps": 50, "max_sampled_steps": 64,
        },
    }
    assert bundle.evaluation == {
        "basis": ["behavioral_chat", "mri_activation"],
        "loss_role": "telemetry_only",
    }
    assert bundle.identity_policy["consciousness_policy"] == "excluded_from_ninereeds_identity"
    assert "I am a mind." in bundle.identity_policy["identity_axioms"]
    assert any("recorded past statement" in item for item in bundle.identity_policy["revision_capabilities"])
    assert bundle.failure_logging["retention_days"] == 7
    assert bundle.emergency["mode"] == "disabled"
    assert bundle.routes["operational-response"]["ordered_model_ids"] == [
        "codex-gpt-5.6-sol", "codex-gpt-5.6-luna",
    ]
    assert bundle.routes["strategic-decision"]["ordered_model_ids"] == [
        "deepseek-v4-flash-official", "codex-gpt-5.6-sol",
    ]
    assert bundle.jobs["campaign.decide"]["artifact_types"] == ["strategic_decision"]
    assert "principal strategic-decision role" in bundle.prompts["campaign-decision-v1"]["system"]
    assert bundle.routes["visual-observation"]["ordered_model_ids"] == [
        "codex-gpt-5.6-luna", "codex-gpt-5.6-sol",
    ]
    assert bundle.routes["visual-caption"]["ordered_model_ids"] == [
        "codex-gpt-5.6-luna", "codex-gpt-5.6-sol",
    ]
    assert bundle.routes["visual-final-review"]["ordered_model_ids"] == [
        "codex-gpt-5.6-luna", "codex-gpt-5.6-sol",
    ]
    assert bundle.jobs["visual.inspect"]["executor_role"] == "mission_hub"
    assert bundle.jobs["visual.caption"]["executor_role"] == "mission_hub"
    assert bundle.jobs["operations.respond"]["enabled"] is True
    assert bundle.machines["trainbox"]["maintenance_mode"] is False
    assert not any(schedule["enabled"] for schedule in bundle.schedules.values())
    assert len(bundle.documents) >= 19
    assert bundle.models["deepseek-v4-flash-0731-openrouter"]["exact_name"] == "deepseek/deepseek-v4-flash-0731"
    assert bundle.jobs["system.healthcheck"]["prompt_id"] == "system-healthcheck-v1"
    assert "without changing it" in bundle.prompts["system-healthcheck-v1"]["system"]
    assert "{include_gpu}" in bundle.prompts["system-healthcheck-v1"]["template"]


def test_model_compatibility_is_capability_based() -> None:
    assert model_supports_route("vision_language", ["text"])
    assert not model_supports_route("text", ["vision_language"])
    assert not model_supports_route("image_generation", ["text"])
    assert not model_supports_route("text", ["image_generation"])
    assert not model_supports_route("vision_language", ["vision_encoder"])


def test_unknown_configuration_key_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "config"
    shutil.copytree(REPO / "config" / "mission_hub", root)
    base = root / "base.toml"
    base.write_text(base.read_text() + "\nunknown = true\n", encoding="utf-8")
    with pytest.raises(ConfigError, match="unknown keys"):
        load_config_bundle(root)


def test_job_contract_validator_rejects_unknown_and_missing_fields() -> None:
    schema = load_schema(REPO, "schemas/mission_hub/jobs/model.train.input.schema.json")
    errors = validate({"architecture": "cortex", "surprise": True}, schema)
    assert any("missing required" in error for error in errors)
    assert any("unknown property 'surprise'" in error for error in errors)


def test_commissioning_schema_enforces_array_and_numeric_bounds() -> None:
    schema = load_schema(REPO, "schemas/mission_hub/jobs/system.gpu_probe.input.schema.json")
    errors = validate(
        {"device_indices": [], "matrix_size": 4097, "iterations": 1, "duration_limit_seconds": 1, "seed": 0},
        schema,
    )
    assert any("fewer than 1 items" in error for error in errors)
    assert any("above maximum 4096" in error for error in errors)
