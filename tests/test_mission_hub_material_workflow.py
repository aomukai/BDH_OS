from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_hub.campaign_contract import campaign_contract_sha256
from mission_hub.config import load_config_bundle
from mission_hub.handlers.contracts import GeneratedCorpusAssembleHandler
from mission_hub.handlers.generative import require_bounded_material_output
from mission_hub.handlers.visual_provider import ProviderFailure
from mission_hub.lesson_policy import policy_sha256
from mission_hub.material_workflow import MaterialWorkflowCoordinator
from mission_hub.store import MissionHubStore, require_bounded_material_unit


REPO = Path(__file__).resolve().parents[1]


def _unit(unit_id: str) -> dict:
    return {
        "unit_id": unit_id,
        "specification": {"target": unit_id},
        "input_artifact_ids": [],
        "output_contract": {"type": "object"},
        "limits": {"max_output_items": 4},
    }


def test_material_workflow_restart_skips_successful_unit_and_creates_only_next() -> None:
    workflow = {
        "id": "material-test", "campaign_id": "campaign-test", "created_by": "operator",
        "specification": {"units": [_unit("lesson-000"), _unit("lesson-001")], "corpus": {"corpus_name": "lessons"}},
        "jobs": [{"stage_key": "unit/000000", "id": "job-0", "status": "succeeded"}],
    }
    calls = []

    class Store:
        @staticmethod
        def workflow_job_artifacts(job_id):
            assert job_id == "job-0"
            return ({}, [{"id": "art-0", "kind": "generated_material"}], "2026-08-09T00:00:00Z")

        @staticmethod
        def campaign_blocks(campaign_id, *, active_only):
            return []

        @staticmethod
        def create_job(bundle, **kwargs):
            calls.append(kwargs)
            return {"id": "job-1", "status": "queued"}

        @staticmethod
        def link_material_workflow_job(*args, **kwargs):
            return None

    coordinator = MaterialWorkflowCoordinator.__new__(MaterialWorkflowCoordinator)
    coordinator.store = Store()
    coordinator.bundle = SimpleNamespace(machines={
        "worker": {"enabled": True, "role": "trainbox"},
        "control": {"enabled": True, "role": "mission_hub"},
    })
    result = coordinator._advance(workflow, actor="test")

    assert result == {"status": "queued", "stage": "unit/000001", "job_id": "job-1"}
    assert len(calls) == 1
    assert calls[0]["input_payload"]["specification"] == {
        "target": "lesson-001", "work_unit_id": "lesson-001",
    }
    assert calls[0]["idempotency_key"] == "material-workflow:material-test:unit/000001"


def test_generated_material_fan_in_is_ordered_and_deterministic(tmp_path: Path) -> None:
    artifacts = []
    for index, value in enumerate(({"caption": "first"}, {"caption": "second"})):
        path = tmp_path / f"unit-{index}.json"
        raw = (json.dumps(value, sort_keys=True) + "\n").encode()
        path.write_bytes(raw)
        artifacts.append({
            "id": f"art-{index}", "kind": "generated_material", "uri": str(path),
            "sha256": hashlib.sha256(raw).hexdigest(), "byte_size": len(raw), "manifest": {},
        })
    state = tmp_path / "state"
    result = GeneratedCorpusAssembleHandler().execute(
        {"input_artifact_ids": ["art-1", "art-0"], "unit_ids": ["b", "a"], "corpus_name": "ordered"},
        {"artifacts": artifacts, "state_root": str(state), "artifact_roots": [str(tmp_path)]},
    )
    corpus = next(item for item in result["artifacts"] if item["kind"] == "corpus")
    rows = [json.loads(line) for line in Path(corpus["uri"]).read_text().splitlines()]
    assert [(row["ordinal"], row["unit_id"], row["material"]["caption"]) for row in rows] == [
        (0, "b", "second"), (1, "a", "first"),
    ]
    assert result["metrics"]["records"] == 2


def test_material_unit_bound_rejects_hidden_large_repetition() -> None:
    unit = _unit("too-large")
    unit["specification"]["captures"] = list(range(5))
    with pytest.raises(ValueError, match="larger than its unit bound"):
        require_bounded_material_unit(unit)


def test_material_output_bound_rejects_provider_batch_before_artifact_commit() -> None:
    with pytest.raises(ProviderFailure) as caught:
        require_bounded_material_output({"captures": [{"caption": str(i)} for i in range(5)]}, 4)
    assert caught.value.failure_class == "repairable_output"
    assert caught.value.code == "output_schema_invalid"


def test_fresh_store_tick_does_not_duplicate_queued_material_unit(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.jobs["executor.generate"]["enabled"] = True
    bundle.prompts["executor-generate-v1"]["enabled"] = True
    bundle.routes["local-generation"]["enabled"] = True
    bundle.models["qwen3.6-35b-a3b-turboquant"]["enabled"] = True
    bundle.providers["trainbox-local"]["enabled"] = True
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    contract = {
        "schema_version": "ninereeds_campaign_contract_v1", "mode": "advancement",
        "development_stage": "bounded material test", "purpose": "Write independent lesson units.",
        "success_criteria": ["Every unit is independently valid."],
        "failure_criteria": ["A required unit is missing."], "expected_regressions": [],
        "branches": [], "merge_sources": [], "target_capabilities": ["bounded writing"],
        "bootstrap_milestones": [], "hypothesis": "", "observations_sought": [],
    }
    store.create_campaign(
        campaign_id="campaign-material", name="material", objective="bounded writing",
        metadata={"campaign_contract": contract}, state="active", actor="test",
    )
    specification = {
        "material_kind": "lesson", "target_capability": "bounded writing",
        "development_stage": contract["development_stage"], "identity_scope": "excluded",
        "identity_policy_id": bundle.identity_policy["id"],
        "identity_policy_version": bundle.identity_policy["version"],
        "identity_policy_sha256": policy_sha256(bundle.identity_policy),
        "campaign_contract_sha256": campaign_contract_sha256(contract),
        "training_mode": contract["mode"], "campaign_purpose": contract["purpose"],
    }
    workflow = store.create_material_workflow(bundle, {
        "campaign_id": "campaign-material",
        "units": [{**_unit("lesson-000"), "specification": specification}],
        "corpus": {"corpus_name": "lessons"},
    }, actor="test")

    first = MaterialWorkflowCoordinator(store, bundle).tick(actor="test-daemon")
    second = MaterialWorkflowCoordinator(
        MissionHubStore(store.path), bundle,
    ).tick(actor="fresh-daemon")

    assert first[0]["stage"] == "unit/000000"
    assert second == []
    assert len(store.material_workflow(workflow["id"])["jobs"]) == 1
