from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import time
import subprocess
from types import SimpleNamespace

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.failures import CriticalFailureRecorder
from mission_hub.handlers.contracts import CheckpointCertifyHandler, CorpusBuildHandler
from mission_hub.service import MissionHubService
from mission_hub.store import MissionHubStore


REPO = Path(__file__).resolve().parents[1]


def test_corpus_build_is_deterministic_and_manifests_every_source(tmp_path: Path) -> None:
    library = tmp_path / "training_data"
    library.mkdir()
    (library / "b.md").write_bytes(b"second\r\n")
    (library / "a.md").write_bytes(b"first\n")
    context = {
        "state_root": str(tmp_path / "state"),
        "contract_limits": {
            "training_library_root": str(library), "corpus_max_source_files": 8,
            "corpus_max_source_bytes": 1024, "checkpoint_max_bytes": 1024,
            "checkpoint_roots": [str(tmp_path / "checkpoints")],
        },
    }
    payload = {
        "corpus_name": "bounded-test", "source_paths": ["b.md", "a.md"],
        "normalization": "utf8_lf", "record_format": "ninereeds_document_v1",
    }

    first = CorpusBuildHandler().execute(payload, context)
    second = CorpusBuildHandler().execute(payload, context)

    assert first["metrics"] == second["metrics"]
    assert [item["kind"] for item in first["artifacts"]] == ["corpus", "corpus_manifest"]
    corpus_lines = Path(first["artifacts"][0]["uri"]).read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["source_path"] for line in corpus_lines] == ["a.md", "b.md"]
    manifest = json.loads(Path(first["artifacts"][1]["uri"]).read_text(encoding="utf-8"))
    assert [item["path"] for item in manifest["sources"]] == ["a.md", "b.md"]
    assert manifest["corpus_sha256"] == hashlib.sha256(Path(first["artifacts"][0]["uri"]).read_bytes()).hexdigest()


def test_corpus_build_refuses_path_escape(tmp_path: Path) -> None:
    library = tmp_path / "training_data"
    library.mkdir()
    context = {
        "state_root": str(tmp_path / "state"),
        "contract_limits": {
            "training_library_root": str(library), "corpus_max_source_files": 8,
            "corpus_max_source_bytes": 1024, "checkpoint_max_bytes": 1024,
            "checkpoint_roots": [str(tmp_path / "checkpoints")],
        },
    }
    with pytest.raises(Exception, match="relative path"):
        CorpusBuildHandler().execute(
            {"corpus_name": "x", "source_paths": ["../secret"], "normalization": "utf8_lf", "record_format": "ninereeds_document_v1"},
            context,
        )


def test_checkpoint_certification_hashes_without_deserialization(tmp_path: Path) -> None:
    root = tmp_path / "checkpoints"
    root.mkdir()
    checkpoint = root / "candidate.pt"
    checkpoint.write_bytes(b"not-a-pickle-but-byte-certifiable")
    context = {
        "state_root": str(tmp_path / "state"),
        "contract_limits": {
            "training_library_root": str(tmp_path / "training_data"), "corpus_max_source_files": 8,
            "corpus_max_source_bytes": 1024, "checkpoint_max_bytes": 1024,
            "checkpoint_roots": [str(root)],
        },
    }

    output = CheckpointCertifyHandler().execute(
        {"checkpoint_path": str(checkpoint), "lineage_label": "test-lineage", "format": "pytorch_checkpoint", "parent_checkpoint_artifact_id": None},
        context,
    )

    assert output["metrics"]["checkpoint_sha256"] == hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    manifest = json.loads(Path(output["artifacts"][1]["uri"]).read_text(encoding="utf-8"))
    assert manifest["deserialized"] is False
    assert manifest["compatibility_certified"] is False


def test_critical_failure_log_prunes_seven_days_and_sol_is_advisory(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    bundle.failure_logging["root"] = str(tmp_path / "critical-failures")
    bundle.emergency["mode"] = "sol_advisory"
    bundle.emergency["invoke_on_critical_failure"] = True
    old = Path(bundle.failure_logging["root"]) / "old" / "incident.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}\n", encoding="utf-8")
    timestamp = (datetime.now(timezone.utc) - timedelta(days=8)).timestamp()
    os.utime(old, (timestamp, timestamp))
    advisory = {"assessment": "bounded", "likely_cause": "test", "operator_actions": ["inspect"], "safe_to_retry": False}
    commands = []

    def runner(command, **kwargs):
        commands.append(command)
        assert "read-only" in command
        assert "no authority" in kwargs["input"]
        sol_home = Path(kwargs["env"]["CODEX_HOME"])
        assert sol_home == tmp_path / "sol-codex-home"
        assert sol_home.is_dir()
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(advisory), stderr="")

    recorder = CriticalFailureRecorder(bundle, runner=runner)
    path = recorder.record(
        job={"id": "job-x", "job_type": "corpus.build", "job_version": 2, "input_sha256": "a" * 64},
        run={"id": "run-x", "attempt": 1, "machine_id": "mission-hub", "deployment_id": "dep-x"},
        failure={"class": "deterministic_specification", "code": "job_spec_invalid", "message": "boom"},
        actor="test", phase="run_failure",
    )

    assert path is not None and path.is_file()
    incident = json.loads(path.read_text(encoding="utf-8"))
    assert incident["emergency"] == {"mode": "sol_advisory", "invoked": True, "advisory": advisory}
    assert commands[0][1] == "exec"
    assert "--ask-for-approval" not in commands[0]
    assert "--skip-git-repo-check" in commands[0]
    assert not old.exists()


def test_shared_local_dispatch_boundary_closes_and_logs_handler_failure(tmp_path: Path) -> None:
    bundle = load_config_bundle(REPO / "config" / "mission_hub")
    state = tmp_path / "state"
    library = tmp_path / "training_data"
    library.mkdir()
    bundle.machines["mission-hub"]["state_root"] = str(state)
    bundle.machines["mission-hub"]["artifact_roots"] = [str(library)]
    bundle.contracts["training_library_root"] = str(library)
    bundle.failure_logging["root"] = str(state / "critical-failures")
    store = MissionHubStore(tmp_path / "hub.sqlite3")
    store.initialize()
    config_id = store.activate_config(bundle, actor="test")
    store.request_pipeline_state("running", actor="test")
    store.apply_pipeline_state(actor="test-daemon")
    deployment_id = store.register_deployment(
        {
            "schema_version": "ninereeds_deployment_manifest_v1", "machine_id": "mission-hub",
            "role": "mission_hub", "release_id": "release-test", "source_sha256": "1" * 64,
            "environment_sha256": "2" * 64, "config_snapshot_id": config_id, "environment": {},
        },
        actor="test", activate=True,
    )
    job = store.create_job(
        bundle, job_type="corpus.build",
        input_payload={
            "corpus_name": "failure", "source_paths": ["missing.md"],
            "normalization": "utf8_lf", "record_format": "ninereeds_document_v1",
        },
        idempotency_key="failure", created_by="test", requested_machine_id="mission-hub",
        approved=True,
    )
    service = MissionHubService(store, bundle)
    envelope = service.lease_envelope(machine_id="mission-hub", deployment_id=deployment_id, actor="test")
    assert envelope is not None
    store.start_run(envelope["run"]["id"], envelope["lease"]["token"], actor="test")

    status = service.execute_and_record("mission-hub", envelope, actor="test")

    assert status == "failed"
    assert store.list_rows("jobs", limit=1)[0]["status"] == "failed"
    run = store.list_rows("runs", limit=1)[0]
    assert run["status"] == "failed"
    assert run["failure_code"] == "safety_policy_refused"
    logs = list((state / "critical-failures").glob("*/*.json"))
    assert len(logs) == 1
    assert json.loads(logs[0].read_text(encoding="utf-8"))["run"]["id"] == run["id"]
def test_long_local_execution_renews_its_lease(monkeypatch) -> None:
    heartbeats = []

    class Store:
        def heartbeat_run(self, run_id, token, **kwargs):
            heartbeats.append((run_id, token, kwargs))

        def run_cancelled(self, run_id):
            return False

    bundle = SimpleNamespace(
        machines={"mission-hub": {"transport": "local"}},
        base={"scheduler": {"lease_seconds": 900}},
    )
    service = MissionHubService(Store(), bundle)
    monkeypatch.setattr(service, "_local_heartbeat_interval", lambda: 0.01)
    monkeypatch.setattr(
        service, "execute_envelope",
        lambda machine_id, envelope: (time.sleep(0.035) or {"result": "ok"}),
    )
    monkeypatch.setattr(service, "accept_result", lambda envelope, result, actor: None)
    envelope = {"run": {"id": "run-local-long"}, "lease": {"token": "lease-token"}}

    assert service.execute_and_record("mission-hub", envelope, actor="test") == "succeeded"
    assert heartbeats
    assert {item[0] for item in heartbeats} == {"run-local-long"}
    assert {item[1] for item in heartbeats} == {"lease-token"}
