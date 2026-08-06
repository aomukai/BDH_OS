from __future__ import annotations

import json
import hashlib
from pathlib import Path

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.campaign_contract import campaign_contract_sha256
from mission_hub.errors import ConflictError, SafetyError
from mission_hub.jsonutil import canonical_json
from mission_hub.lesson_policy import policy_sha256
from mission_hub.service import MissionHubService
from mission_hub.store import MissionHubStore, utc_now


REPO = Path(__file__).resolve().parents[1]


def _campaign_metadata(*, starting_checkpoint: str | None = None) -> dict:
    value = {
        "campaign_contract": {
            "schema_version": "ninereeds_campaign_contract_v1",
            "mode": "advancement",
            "development_stage": "test fixture",
            "purpose": "Exercise the campaign and knowledge contracts.",
            "success_criteria": ["The declared fixture operation succeeds."],
            "failure_criteria": ["A safety contract is violated."],
            "expected_regressions": [],
            "branches": [],
            "merge_sources": [],
            "target_capabilities": ["test fixture behavior"],
            "bootstrap_milestones": [],
            "hypothesis": "",
            "observations_sought": [],
        }
    }
    if starting_checkpoint is not None:
        value["starting_checkpoint_artifact_id"] = starting_checkpoint
    return value


def _checkpoint(store: MissionHubStore, artifact_id: str, digest: str) -> None:
    with store.transaction() as db:
        db.execute(
            """INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at)
               VALUES(?,'checkpoint',?,1,'candidate','{}',?)""",
            (artifact_id, digest, utc_now()),
        )


def _artifact(store: MissionHubStore, artifact_id: str, kind: str, digest: str, manifest: dict | None = None) -> None:
    with store.transaction() as db:
        db.execute(
            """INSERT INTO artifacts(id,kind,sha256,byte_size,lifecycle,manifest_json,created_at)
               VALUES(?,?,?,?, 'candidate',?,?)""",
            (artifact_id, kind, digest, 1, canonical_json(manifest or {}), utc_now()),
        )


def test_checkpoint_knowledge_inherits_and_campaign_views_are_grep_friendly(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "mission-hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    _checkpoint(store, "art-parent000000000", "a" * 64)
    store.create_campaign(
        campaign_id="campaign-a", name="A", objective="Teach prerequisites.",
        metadata=_campaign_metadata(), actor="test",
    )
    store.append_checkpoint_knowledge(
        checkpoint_artifact_id="art-parent000000000",
        parent_checkpoint_artifact_id=None,
        campaign_id="campaign-a", session_id="session-a",
        concepts=["dog", "house", "police", "car"], evidence=["art-script-a"], actor="test",
    )

    store.create_campaign(
        campaign_id="campaign-b", name="B", objective="Teach compounds.",
        metadata=_campaign_metadata(starting_checkpoint="art-parent000000000"), actor="test",
    )
    kickoff = store.campaign_knowledge("campaign-b")["known_at_start"]
    assert [item["concept_key"] for item in kickoff] == ["car", "dog", "house", "police"]

    _checkpoint(store, "art-child0000000000", "b" * 64)
    store.append_checkpoint_knowledge(
        checkpoint_artifact_id="art-child0000000000",
        parent_checkpoint_artifact_id="art-parent000000000",
        campaign_id="campaign-b", session_id="session-b",
        concepts=["doghouse", "police car", "police dog"], evidence=["art-script-b"], actor="test",
    )
    assert [item["concept_key"] for item in store.checkpoint_knowledge("art-child0000000000")] == [
        "car", "dog", "doghouse", "house", "police", "police car", "police dog",
    ]

    root = tmp_path / "knowledge"
    global_lines = (root / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    dog_hits = [json.loads(line) for line in global_lines if "dog" in line.casefold()]
    assert {item["concept_key"] for item in dog_hits} == {"dog", "doghouse", "police dog"}
    known = (root / "campaigns/campaign-b/known-at-start.jsonl").read_text(encoding="utf-8")
    trained = (root / "campaigns/campaign-b/trained-during.jsonl").read_text(encoding="utf-8")
    assert '"concept_key":"dog"' in known
    assert '"concept_key":"doghouse"' not in known
    assert '"concept_key":"doghouse"' in trained


def test_knowledge_session_replay_is_idempotent_and_conflicting_replay_is_refused(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "mission-hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    _checkpoint(store, "art-seed00000000000", "f" * 64)
    store.create_campaign(
        campaign_id="knowledge-idempotency", name="knowledge", objective="knowledge",
        metadata=_campaign_metadata(), actor="test",
    )
    first = store.append_checkpoint_knowledge(
        checkpoint_artifact_id="art-seed00000000000", parent_checkpoint_artifact_id=None,
        campaign_id="knowledge-idempotency", session_id="baseline-seed",
        concepts=["dog", "house"], evidence=["inventory-sha256"], actor="test",
    )
    repeated = store.append_checkpoint_knowledge(
        checkpoint_artifact_id="art-seed00000000000", parent_checkpoint_artifact_id=None,
        campaign_id="knowledge-idempotency", session_id="baseline-seed",
        concepts=["dog", "house"], evidence=["inventory-sha256"], actor="test",
    )
    assert [item["sha256"] for item in repeated] == [item["sha256"] for item in first]
    with pytest.raises(ConflictError, match="already has different evidence"):
        store.append_checkpoint_knowledge(
            checkpoint_artifact_id="art-seed00000000000", parent_checkpoint_artifact_id=None,
            campaign_id="knowledge-idempotency", session_id="baseline-seed",
            concepts=["dog", "kennel"], evidence=["inventory-sha256"], actor="test",
        )


def test_unrelated_branch_knowledge_is_not_inherited(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    store = MissionHubStore(tmp_path / "mission-hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    _checkpoint(store, "art-root00000000000", "c" * 64)
    _checkpoint(store, "art-branch000000000", "d" * 64)
    _checkpoint(store, "art-other0000000000", "e" * 64)
    store.create_campaign(campaign_id="campaign-root", name="root", objective="root", metadata=_campaign_metadata(), actor="test")
    store.append_checkpoint_knowledge(
        checkpoint_artifact_id="art-root00000000000", parent_checkpoint_artifact_id=None,
        campaign_id="campaign-root", session_id="root", concepts=["dog"], evidence=[], actor="test",
    )
    store.append_checkpoint_knowledge(
        checkpoint_artifact_id="art-branch000000000", parent_checkpoint_artifact_id="art-root00000000000",
        campaign_id="campaign-root", session_id="branch", concepts=["house"], evidence=[], actor="test",
    )
    store.append_checkpoint_knowledge(
        checkpoint_artifact_id="art-other0000000000", parent_checkpoint_artifact_id="art-root00000000000",
        campaign_id="campaign-root", session_id="other", concepts=["police"], evidence=[], actor="test",
    )
    assert [item["concept_key"] for item in store.checkpoint_knowledge("art-branch000000000")] == ["dog", "house"]
    assert [item["concept_key"] for item in store.checkpoint_knowledge("art-other0000000000")] == ["dog", "police"]


def test_training_job_requires_dependency_check_and_atomic_session_list(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["safety"]["live_execution"] = True
    bundle.jobs["model.train"]["enabled"] = True
    store = MissionHubStore(tmp_path / "mission-hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")
    parent_id = "art-1111111111111111"
    corpus_id = "art-2222222222222222"
    validation_id = "art-3333333333333333"
    _checkpoint(store, parent_id, "1" * 64)
    store.create_campaign(campaign_id="seed-knowledge", name="seed", objective="seed", metadata=_campaign_metadata(), actor="test")
    store.append_checkpoint_knowledge(
        checkpoint_artifact_id=parent_id, parent_checkpoint_artifact_id=None,
        campaign_id="seed-knowledge", session_id="seed", concepts=["dog"], evidence=[], actor="test",
    )
    store.create_campaign(
        campaign_id="compound-campaign", name="compounds", objective="teach compounds",
        metadata=_campaign_metadata(starting_checkpoint=parent_id), state="active", actor="test",
    )
    _artifact(store, corpus_id, "corpus", "2" * 64)
    parameters = {
        "epochs": 1, "batch_size": 1, "max_examples": 3, "learning_rate": 0.001,
        "weight_decay": 0.0, "seed": 1, "ingress_device": "cpu", "core_device": "cpu",
        "train_scope": "all", "rms_clip": 1.0, "stochastic_rounding": False,
        "local_files_only": True, "probe_max_new_tokens": 16, "source_concept": "compound-test",
    }
    payload = {
        "architecture": "bdh", "parent_artifact_id": parent_id, "corpus_artifact_id": corpus_id,
        "order_validation_artifact_id": validation_id, "parameters": parameters,
        "training_session": {"id": "session-01", "campaign_contract_sha256": campaign_contract_sha256(_campaign_metadata()["campaign_contract"]), "training_mode": "advancement", "branch_id": None, "identity_scope": "excluded", "ordered_concepts": [
            {"concept": "doghouse", "depends_on": ["dog", "house"]},
        ]},
    }
    with pytest.raises(SafetyError, match="missing house"):
        store.preview_training_session_plan(
            bundle, job_type="model.train", input_payload=payload, campaign_id="compound-campaign",
        )
    payload["training_session"]["ordered_concepts"] = [
        {"concept": "house", "depends_on": []},
        {"concept": "doghouse", "depends_on": ["dog", "house"]},
    ]
    plan = store.preview_training_session_plan(
        bundle, job_type="model.train", input_payload=payload, campaign_id="compound-campaign",
    )
    certificate = {
        "schema_version": "ninereeds_dependency_order_validation_v1",
        "validation_scope": "dependency_order", "status": "passed",
        "subject_artifact_id": corpus_id, "subject_sha256": "2" * 64,
        "parent_artifact_id": parent_id, "parent_sha256": "1" * 64,
        "order_policy": "declared_only", "shuffle_allowed": False,
        "dependency_order_required": True, "dependency_evidence_sha256": "4" * 64,
        "session_plan_sha256": plan["plan_sha256"],
        "parent_knowledge_sha256": plan["parent_knowledge_sha256"],
        "lesson_policy_status": "passed", "lesson_policy_id": bundle.identity_policy["id"],
        "lesson_policy_version": bundle.identity_policy["version"],
        "lesson_policy_sha256": policy_sha256(bundle.identity_policy), "identity_scope": "excluded",
    }
    _artifact(store, validation_id, "validation_report", "3" * 64, certificate)
    job = store.create_job(
        bundle, job_type="model.train", input_payload=payload, idempotency_key="compound-session-01",
        created_by="test", campaign_id="compound-campaign", approved=True,
    )
    assert job["status"] == "queued"
    with store._connect() as db:
        admitted = db.execute("SELECT * FROM training_session_plans WHERE job_id=?", (job["id"],)).fetchone()
        assert admitted["status"] == "admitted"
        assert admitted["plan_sha256"] == plan["plan_sha256"]
        assert [item["concept_label"] for item in json.loads(admitted["ordered_concepts_json"])] == ["house", "doghouse"]


def test_service_emits_certificate_that_admits_the_exact_training_bytes(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.base["safety"]["live_execution"] = True
    bundle.jobs["model.train"]["enabled"] = True
    state_root = tmp_path / "state"
    bundle.machines["mission-hub"]["state_root"] = str(state_root)
    bundle.machines["mission-hub"]["artifact_roots"] = [str(state_root), str(tmp_path)]
    store = MissionHubStore(tmp_path / "mission-hub.sqlite3")
    store.initialize()
    store.activate_config(bundle, actor="test")

    parent_path = tmp_path / "parent.pt"
    parent_path.write_bytes(b"parent")
    parent_id = store.register_artifact(
        bundle, kind="checkpoint", sha256=hashlib.sha256(b"parent").hexdigest(),
        byte_size=6, lifecycle="candidate", manifest={}, producing_run_id=None,
        machine_id="mission-hub", uri=str(parent_path), actor="test",
    )
    corpus_path = tmp_path / "lesson.jsonl"
    corpus_path.write_text(
        json.dumps({"prompt": "What is a house?", "completion": "A house is a building.", "stage": "lesson", "concept": "house", "depends_on": []}) + "\n"
        + json.dumps({"prompt": "What is a doghouse?", "completion": "A doghouse is a house for a dog.", "stage": "lesson", "concept": "doghouse", "depends_on": ["dog", "house"]}) + "\n",
        encoding="utf-8",
    )
    corpus_bytes = corpus_path.read_bytes()
    corpus_id = store.register_artifact(
        bundle, kind="corpus", sha256=hashlib.sha256(corpus_bytes).hexdigest(),
        byte_size=len(corpus_bytes), lifecycle="candidate", manifest={}, producing_run_id=None,
        machine_id="mission-hub", uri=str(corpus_path), actor="test",
    )
    seed_metadata = _campaign_metadata()
    store.create_campaign(campaign_id="certificate-seed", name="seed", objective="seed", metadata=seed_metadata, actor="test")
    store.append_checkpoint_knowledge(
        checkpoint_artifact_id=parent_id, parent_checkpoint_artifact_id=None,
        campaign_id="certificate-seed", session_id="seed", concepts=["dog"], evidence=[], actor="test",
    )
    metadata = _campaign_metadata(starting_checkpoint=parent_id)
    store.create_campaign(
        campaign_id="certificate-campaign", name="certificate", objective="certificate",
        metadata=metadata, state="active", actor="test",
    )
    payload = {
        "architecture": "bdh", "parent_artifact_id": parent_id,
        "corpus_artifact_id": corpus_id,
        "order_validation_artifact_id": "art-0000000000000000",
        "training_session": {
            "id": "certificate-session", "campaign_contract_sha256": campaign_contract_sha256(metadata["campaign_contract"]),
            "training_mode": "advancement", "branch_id": None, "identity_scope": "excluded",
            "ordered_concepts": [
                {"concept": "house", "depends_on": []},
                {"concept": "doghouse", "depends_on": ["dog", "house"]},
            ],
        },
        "parameters": {
            "epochs": 1, "batch_size": 1, "max_examples": 2, "learning_rate": 0.001,
            "weight_decay": 0.0, "seed": 1, "ingress_device": "cpu", "core_device": "cpu",
            "train_scope": "all", "rms_clip": 1.0, "stochastic_rounding": False,
            "local_files_only": True, "probe_max_new_tokens": 16, "source_concept": "compound-test",
        },
    }
    certificate = MissionHubService(store, bundle).certify_training_order(
        job_type="model.train", input_payload=payload,
        campaign_id="certificate-campaign", actor="test",
    )
    payload["order_validation_artifact_id"] = certificate["artifact_id"]
    job = store.create_job(
        bundle, job_type="model.train", input_payload=payload,
        idempotency_key="certified-session", created_by="test",
        campaign_id="certificate-campaign", approved=True,
    )
    assert job["status"] == "queued"
    assert certificate["manifest"]["material_evidence"]["row_count"] == 2
    assert certificate["manifest"]["subject_sha256"] == hashlib.sha256(corpus_bytes).hexdigest()
