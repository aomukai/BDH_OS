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
        "live_execution": False,
        "automatic_pruning": False,
        "automatic_campaign_rollover": False,
        "allow_git_mutation": False,
        "require_release_match": True,
        "require_config_match": True,
    }
    assert bundle.jobs["system.healthcheck"]["enabled"] is True
    assert all(
        not definition["enabled"]
        for job_type, definition in bundle.jobs.items()
        if job_type != "system.healthcheck"
    )
    assert bundle.machines["trainbox"]["maintenance_mode"] is True
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
