from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.failures import CriticalFailureRecorder
from mission_hub.handlers.contracts import CheckpointCertifyHandler, CorpusBuildHandler


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
    old = Path(bundle.failure_logging["root"]) / "old" / "incident.json"
    old.parent.mkdir(parents=True)
    old.write_text("{}\n", encoding="utf-8")
    timestamp = (datetime.now(timezone.utc) - timedelta(days=8)).timestamp()
    os.utime(old, (timestamp, timestamp))
    advisory = {"assessment": "bounded", "likely_cause": "test", "operator_actions": ["inspect"], "safe_to_retry": False}

    def runner(command, **kwargs):
        assert "read-only" in command
        assert "no authority" in kwargs["input"]
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
    assert not old.exists()
