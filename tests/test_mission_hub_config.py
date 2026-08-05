from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import ConfigError
from mission_hub.schema import load_schema, validate


REPO = Path(__file__).resolve().parents[1]


def test_repository_configuration_is_valid_and_fail_closed() -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    assert bundle.base["safety"] == {
        "live_execution": True,
        "automatic_pruning": False,
        "automatic_campaign_rollover": False,
        "allow_git_mutation": False,
        "require_release_match": True,
        "require_config_match": True,
    }
    # This committed snapshot is the bounded artifact/GPU commissioning window.
    assert {job_type for job_type, definition in bundle.jobs.items() if definition["enabled"]} == {
        "system.healthcheck", "system.artifact_roundtrip", "system.gpu_probe",
    }
    assert bundle.machines["trainbox"]["maintenance_mode"] is False
    assert len(bundle.documents) >= 19


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
