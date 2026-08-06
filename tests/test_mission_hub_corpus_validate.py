from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import SafetyError
from mission_hub.handlers.cortex import TrainingCorpusValidateHandler


REPO = Path(__file__).resolve().parents[1]


def _context(tmp_path: Path, corpus: Path) -> dict:
    bundle = load_config_bundle(REPO / "config/mission_hub")
    raw = corpus.read_bytes()
    return {
        "artifacts": [{
            "id": "art-1111111111111111", "kind": "corpus",
            "sha256": hashlib.sha256(raw).hexdigest(), "byte_size": len(raw),
            "lifecycle": "candidate", "manifest": {}, "uri": str(corpus),
        }],
        "state_root": str(tmp_path / "state"), "artifact_roots": [str(tmp_path)],
        "release_root": str(REPO), "deployment_environment": {},
        "run": {"id": "run-corpus-validation"},
        "training_policy": bundle.training, "identity_policy": bundle.identity_policy,
    }


def test_training_corpus_validator_binds_bytes_order_and_identity(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.jsonl"
    rows = [
        {"prompt": "What is a house?", "completion": "A house is a building.", "stage": "new", "concept": "house", "depends_on": []},
        {"prompt": "What is a doghouse?", "completion": "A doghouse is a house for a dog.", "stage": "new", "concept": "doghouse", "depends_on": ["dog", "house"]},
    ]
    corpus.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    payload = {
        "corpus_artifact_id": "art-1111111111111111", "expected_rows": 2,
        "identity_scope": "excluded",
        "ordered_concepts": [
            {"concept": "house", "depends_on": []},
            {"concept": "doghouse", "depends_on": ["dog", "house"]},
        ],
    }
    result = TrainingCorpusValidateHandler().execute(payload, _context(tmp_path, corpus))
    assert result["status"] == "succeeded"
    assert result["artifacts"][0]["manifest"]["shuffle_allowed"] is False

    payload["ordered_concepts"].reverse()
    with pytest.raises(SafetyError, match="concept order"):
        TrainingCorpusValidateHandler().execute(payload, _context(tmp_path, corpus))
