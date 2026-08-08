from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError

import pytest

from mission_hub.errors import RemoteJobError, SafetyError
from mission_hub.handlers.visual_provider import VisualDecisionHandler, VisualPlanHandler, VisualReviewHandler


REPO = Path(__file__).resolve().parents[1]


def test_visual_decision_requires_complete_nonpixel_provenance() -> None:
    handler = VisualDecisionHandler()
    complete = [
        {"kind": "visual_generation_report"},
        {"kind": "visual_inspection_report"},
        {"kind": "visual_caption_report"},
    ]
    handler.validate_inputs(complete)

    with pytest.raises(SafetyError, match="generation, inspection, and caption"):
        handler.validate_inputs(complete[1:])
    with pytest.raises(SafetyError, match="may not receive pixels"):
        handler.validate_inputs([*complete, {"kind": "visual_candidate"}])


def test_visual_decision_partitions_large_exact_evidence_without_skipping_items(tmp_path: Path) -> None:
    commission_items, generation_items, inspection_items, caption_items = [], [], [], []
    for index in range(1, 41):
        item_id = f"item-{index:03d}"
        digest = f"{index:064x}"
        commission_items.append({
            "item_id": item_id, "canonical_caption": f"concept {index}",
            "prompt": "exact visual commission " + ("detail " * 25),
            "seeds": [index], "width": 512, "height": 512, "steps": 4,
        })
        generation_items.append({
            "item_id": item_id, "sha256": digest, "seed": index,
            "prompt": "exact generated prompt " + ("detail " * 25),
            "width": 512, "height": 512, "steps": 4,
        })
        inspection_items.append({
            "asset_sha256": digest,
            "result": {
                "description": "observed facts " + ("visible " * 20),
                "primary_subject": f"concept {index}", "proposed_decision": "accept",
                "uncertainty": [], "unwanted_text_or_watermark": False,
            },
        })
        caption_items.append({
            "asset_sha256": digest,
            "result": {
                "teaching_caption": f"concept {index}",
                "accessibility_caption": "caption facts " + ("visible " * 20),
                "preserved_visible_facts": ["fact"], "uncertainty": [],
            },
        })

    artifacts = []
    for kind, items in (
        ("visual_generation_report", generation_items),
        ("visual_inspection_report", inspection_items),
        ("visual_caption_report", caption_items),
    ):
        path = tmp_path / f"{kind}.json"
        path.write_text(json.dumps({"schema_version": f"test_{kind}", "items": items}), encoding="utf-8")
        artifacts.append({
            "id": f"art-{kind}", "kind": kind, "uri": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size, "manifest": {},
        })
    payload = {
        "input_artifact_ids": [item["id"] for item in artifacts],
        "specification": {
            "workflow_id": "visual-large",
            "commission": {
                "plan_id": "large-plan", "canonical_text": [item["canonical_caption"] for item in commission_items],
                "items": commission_items,
            },
        },
        "limits": {"max_pack_items": 40},
    }
    prompt = {"system": "Decide.", "template": "Use exact evidence."}

    texts = VisualDecisionHandler().prompt_texts(prompt, payload, artifacts, 4096)

    assert len(texts) > 1
    assert all(len(text.encode("utf-8")) <= 4096 for text in texts)
    covered = []
    for text in texts:
        body = json.loads(text.split("Exact task data:\n", 1)[1])
        covered.extend(item["item_id"] for item in body["specification"]["commission"]["items"])
        assert all(len(item["content"]["items"]) == len(body["specification"]["commission"]["items"]) for item in body["evidence"])
    assert covered == [item["item_id"] for item in commission_items]


def test_visual_decision_combines_partitions_with_conservative_bucket() -> None:
    combined = VisualDecisionHandler().combine_results([
        {"bucket": "accept", "evidence": ["first"], "uncertainty": [], "reason": "clear"},
        {"bucket": "check_again", "evidence": ["second"], "uncertainty": ["ambiguous"], "reason": "inspect again"},
        {"bucket": "reject", "evidence": ["third"], "uncertainty": [], "reason": "hard mismatch"},
    ])

    assert combined["bucket"] == "reject"
    assert combined["evidence"] == [
        "partition 1/3: first", "partition 2/3: second", "partition 3/3: third",
    ]
    assert combined["uncertainty"] == ["partition 2/3: ambiguous"]
    assert "worst-bucket aggregation" in combined["reason"]


def evidence(tmp_path: Path, artifact_id: str, kind: str) -> dict:
    path = tmp_path / f"{artifact_id}.json"
    path.write_text("{}\n", encoding="utf-8")
    return {"id": artifact_id, "kind": kind, "uri": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "byte_size": path.stat().st_size, "manifest": {}}


def test_sol_review_attaches_exact_pixels_and_records_admission(tmp_path: Path, monkeypatch) -> None:
    pixels = tmp_path / "candidate.png"
    pixels.write_bytes(b"bounded-pixel-fixture")
    digest = hashlib.sha256(pixels.read_bytes()).hexdigest()
    candidate = {
        "id": "art-candidate", "kind": "visual_candidate", "uri": str(pixels),
        "sha256": digest, "byte_size": pixels.stat().st_size, "manifest": {"item_id": "red-ball"},
    }
    def run(command, **kwargs):
        assert command[command.index("--image") + 1] == str(pixels)
        provider_schema = json.loads(Path(command[command.index("--output-schema") + 1]).read_text())
        assert "uniqueItems" not in provider_schema["properties"]["accepted_uses"]
        output_path = Path(command[command.index("--output-last-message") + 1])
        output_path.write_text(json.dumps({
            "asset_sha256": digest, "asset_status": "usable",
            "accepted_uses": ["a red ball"], "visible_facts": ["one red ball"],
            "uncertainty": [], "reason": "Pixels visibly support the exact use.",
        }), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr("mission_hub.handlers.visual_provider.subprocess.run", run)
    context = {
        "state_root": str(tmp_path / "state"), "artifact_roots": [str(tmp_path)],
        "artifacts": [candidate, evidence(tmp_path, "inspection", "visual_inspection_report"), evidence(tmp_path, "decision", "visual_decision_report")], "run": {"id": "run-review"}, "release_root": str(REPO),
        "route": {"id": "visual-final-review", "max_total_tokens": 8192, "fallback_failure_classes": []},
        "route_models": [{
            "id": "codex-sol", "exact_name": "gpt-sol", "provider": "codex-headless", "enabled": True,
        }],
        "providers": {"codex-headless": {
            "id": "codex-headless", "kind": "codex_cli", "endpoint": "/codex",
            "timeout_seconds": 30, "enabled": True,
        }},
        "prompt": {
            "id": "visual-review-v1", "version": 1, "system": "Review pixels.", "template": "{image}",
            "output_schema": "schemas/mission_hub/providers/visual-review.response.schema.json",
        },
    }
    result = VisualReviewHandler().execute(
        {"input_artifact_ids": ["art-candidate", "inspection", "decision"], "specification": {}, "limits": {}}, context,
    )
    review = next(item for item in result["artifacts"] if item["kind"] == "visual_review_report")
    assert review["manifest"]["reviewer"] == "sol"
    assert review["manifest"]["asset_sha256"] == digest


def test_sol_review_rejects_a_substituted_asset_hash(tmp_path: Path, monkeypatch) -> None:
    pixels = tmp_path / "candidate.png"
    pixels.write_bytes(b"pixels")
    digest = hashlib.sha256(pixels.read_bytes()).hexdigest()
    candidate = {"id": "a", "kind": "visual_candidate", "uri": str(pixels), "sha256": digest, "byte_size": 6, "manifest": {}}
    def run(command, **kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps({
            "asset_sha256": "f" * 64, "asset_status": "unusable", "accepted_uses": [],
            "visible_facts": [], "uncertainty": ["mismatch"], "reason": "wrong bytes",
        }), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")
    monkeypatch.setattr("mission_hub.handlers.visual_provider.subprocess.run", run)
    ctx = {
        "state_root": str(tmp_path / "state"), "artifact_roots": [str(tmp_path)], "artifacts": [candidate, evidence(tmp_path, "inspect-bad", "visual_inspection_report"), evidence(tmp_path, "decide-bad", "visual_decision_report")],
        "run": {"id": "run-bad"}, "release_root": str(REPO),
        "route": {"id": "visual-final-review", "max_total_tokens": 8192, "fallback_failure_classes": []},
        "route_models": [{"id": "sol", "exact_name": "sol", "provider": "p", "enabled": True}],
        "providers": {"p": {"id": "p", "kind": "codex_cli", "endpoint": "/codex", "timeout_seconds": 30, "enabled": True}},
        "prompt": {"id": "p", "version": 1, "system": "review", "template": "x", "output_schema": "schemas/mission_hub/providers/visual-review.response.schema.json"},
    }
    with pytest.raises(SafetyError, match="different asset hash"):
        VisualReviewHandler().execute({"input_artifact_ids": ["a", "inspect-bad", "decide-bad"], "specification": {}, "limits": {}}, ctx)


def test_http_429_survives_as_operator_visible_rate_limit(tmp_path: Path, monkeypatch) -> None:
    def rate_limited(*args, **kwargs):
        raise HTTPError("https://provider.test/chat/completions", 429, "rate limited", {}, None)
    monkeypatch.setattr("mission_hub.handlers.visual_provider.urllib.request.urlopen", rate_limited)
    context = {
        "state_root": str(tmp_path / "state"), "artifact_roots": [str(tmp_path)],
        "artifacts": [], "run": {"id": "run-rate-limit"}, "release_root": str(REPO),
        "route": {"id": "visual-planning", "max_total_tokens": 8192, "fallback_failure_classes": ["capability_transient"]},
        "route_models": [{"id": "remote", "exact_name": "remote/model", "provider": "remote-provider", "enabled": True, "output_tokens": 1024}],
        "providers": {"remote-provider": {"id": "remote-provider", "kind": "openai_compatible", "endpoint": "https://provider.test/chat/completions", "credential_env": "", "timeout_seconds": 30, "enabled": True}},
        "prompt": {"id": "visual-plan-v1", "version": 1, "system": "plan", "template": "x", "output_schema": "schemas/mission_hub/providers/visual-plan.response.schema.json"},
    }
    with pytest.raises(RemoteJobError) as failure:
        VisualPlanHandler().execute({"input_artifact_ids": [], "specification": {"goal": "x"}, "limits": {}}, context)
    assert failure.value.failure_class == "capability_transient"
    assert failure.value.code == "provider_rate_limited"
