from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_hub.config import load_config_bundle
import mission_hub.handlers.research_journal as journal_handler_module
from mission_hub.handlers.research_journal import ResearchJournalLibrarianHandler
from mission_hub.research_journal import ENRICHMENT_SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]


def journal_payload() -> dict:
    record = {
        "campaign_id": "campaign-45",
        "campaign_goal": "Map the candidate-formation boundary.",
        "experiment_id": "experiment-45-8",
        "sequence": 8,
        "title": "Exact-control gate telemetry baseline",
        "hypothesis": "Ownership may pass before dossier eligibility becomes active.",
        "state": "succeeded",
        "specification": {
            "kind": "organism_experiment",
            "intervention_type": "measurement",
            "dataset_id": "builtin:foundation-visual-3022-v1",
            "max_events_per_session": 20,
        },
        "result_summary": {
            "organism_status": "complete",
            "development_telemetry": {
                "candidate_total": 0,
                "observing_gate_counts": {"ownership": {"evaluated": 20, "passed": 20}},
            },
        },
        "result_sha256": "b" * 64,
        "repeat_fingerprint": "c" * 64,
    }
    return {
        "lab_id": "research-lab-45",
        "campaign_id": "campaign-45",
        "campaign_number": 45,
        "experiment_id": "experiment-45-8",
        "record_sha256": "a" * 64,
        "record": record,
    }


def test_luna_journal_enrichment_is_evidence_bound_and_has_no_authority(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = load_config_bundle(ROOT / "config" / "mission_hub")
    state_root = tmp_path / "state"
    state_root.mkdir()
    calls = []

    def fake_codex(provider, model, prompt, schema_path, images, run_root, *, reasoning_effort=None):
        calls.append({"model": model["id"], "prompt": prompt, "effort": reasoning_effort})
        return {
            "keywords": ["candidate-formation", "ownership", "eligibility"],
            "summary": "The exact-control run recorded ownership passing 20 of 20 evaluations and zero candidates.",
        }, {"mock": "luna"}

    monkeypatch.setattr(journal_handler_module, "_codex", fake_codex)
    context = {
        "prompt": bundle.prompts["research-journal-librarian-v1"],
        "route": bundle.routes["research-librarian"],
        "route_models": [bundle.models["codex-gpt-5.6-luna-librarian"]],
        "providers": bundle.providers,
        "release_root": str(ROOT),
        "state_root": str(state_root),
        "run": {"id": "run-journal-luna"},
    }

    output = ResearchJournalLibrarianHandler().execute(journal_payload(), context)

    assert output["status"] == "succeeded"
    assert output["metrics"]["authority"] == "none"
    assert len(calls) == 1
    assert calls[0]["model"] == "codex-gpt-5.6-luna-librarian"
    assert calls[0]["effort"] == "low"
    assert "zero-authority evidentiary librarian" in calls[0]["prompt"]
    artifact = next(
        item for item in output["artifacts"] if item["kind"] == "research_journal_enrichment"
    )
    enrichment = json.loads(Path(artifact["uri"]).read_text(encoding="utf-8"))
    assert enrichment["schema_version"] == ENRICHMENT_SCHEMA_VERSION
    assert enrichment["experiment_id"] == "experiment-45-8"
    assert enrichment["record_sha256"] == "a" * 64
    assert enrichment["keywords"] == ["candidate-formation", "ownership", "eligibility"]
    assert artifact["manifest"]["authority"] == "none"
