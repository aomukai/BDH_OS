from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
from urllib.error import HTTPError

import pytest

from mission_hub.errors import ArtifactContractError, RemoteJobError, SafetyError
from mission_hub.handlers.visual_provider import ProviderFailure, VisualDecisionHandler, VisualPlanHandler, VisualReviewHandler, _codex, _http, _json_from_text


def test_codex_capacity_failure_preserves_plain_waitable_cause(tmp_path: Path, monkeypatch) -> None:
    schema = tmp_path / "schema.json"
    schema.write_text(json.dumps({"type": "object"}), encoding="utf-8")
    run_root = tmp_path / "run"
    run_root.mkdir()

    def at_capacity(command, **kwargs):
        return subprocess.CompletedProcess(
            command, 1, stdout="", stderr="ERROR: Selected model is at capacity. Please try a different model.\n",
        )

    monkeypatch.setattr(subprocess, "run", at_capacity)

    with pytest.raises(ProviderFailure) as caught:
        _codex(
            {"endpoint": "codex", "timeout_seconds": 30},
            {"exact_name": "gpt-test"}, "prompt", schema, [], run_root,
        )

    assert caught.value.code == "provider_capability_unavailable"
    assert caught.value.failure_class == "capability_transient"
    assert "model is at capacity" in str(caught.value)
    assert "waiting before retry should resolve it" in str(caught.value)


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

    handler.validate_inputs([*complete, {"kind": "visual_caption_report"}])
    with pytest.raises(SafetyError, match="one or two"):
        handler.validate_inputs([*complete, {"kind": "visual_caption_report"}, {"kind": "visual_caption_report"}])


def test_visual_decision_presents_two_caption_candidates_for_explicit_selection(tmp_path: Path) -> None:
    digest = "a" * 64
    reports = [
        ("visual_generation_report", "generation", {"items": [{"item_id": "dog", "sha256": digest}]}),
        ("visual_inspection_report", "inspection", {"items": [{"asset_sha256": digest, "result": {"description": "one dog"}}]}),
        ("visual_caption_report", "caption-a", {"items": [{"asset_sha256": digest, "result": {"teaching_caption": "animal"}}]}),
        ("visual_caption_report", "caption-b", {"items": [{"asset_sha256": digest, "result": {"teaching_caption": "one dog"}}]}),
    ]
    artifacts = []
    for kind, artifact_id, report in reports:
        path = tmp_path / f"{artifact_id}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        artifacts.append({
            "id": artifact_id, "kind": kind, "uri": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size,
        })

    texts = VisualDecisionHandler().prompt_texts(
        {"system": "Decide.", "template": "Use evidence."},
        {
            "specification": {"commission": {"items": [{"item_id": "dog"}]}},
            "limits": {},
        },
        artifacts, 8192,
    )

    task = json.loads(texts[0].split("Exact task data:\n", 1)[1])
    captions = [item for item in task["evidence"] if item["kind"] == "visual_caption_report"]
    assert [item["id"] for item in captions] == ["caption-a", "caption-b"]
    assert [item["caption_variant"] for item in captions] == [0, 1]
    assert "return its exact evidence artifact id" in task["decision_scope"]["caption_selection"]


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


def test_visual_decision_scopes_a_preserved_batch_receipt_to_one_commissioned_candidate(tmp_path: Path) -> None:
    reports = {
        "visual_generation_report": {"items": [
            {"item_id": "dog", "sha256": "a" * 64, "seed": 11},
            {"item_id": "cat", "sha256": "b" * 64, "seed": 12},
        ]},
        "visual_inspection_report": {"items": [
            {"asset_sha256": "b" * 64, "result": {"description": "one cat"}},
        ]},
        "visual_caption_report": {"items": [
            {"asset_sha256": "b" * 64, "result": {"teaching_caption": "cat"}},
        ]},
    }
    artifacts = []
    for kind, report in reports.items():
        path = tmp_path / f"{kind}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        artifacts.append({
            "id": kind, "kind": kind, "uri": str(path),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size,
        })
    payload = {
        "specification": {"commission": {"items": [{"item_id": "cat", "seeds": [12]}]}},
        "limits": {},
    }

    texts = VisualDecisionHandler().prompt_texts(
        {"system": "Decide.", "template": "Use evidence."}, payload, artifacts, 8192,
    )

    task = json.loads(texts[0].split("Exact task data:\n", 1)[1])
    generation = next(
        item for item in task["evidence"] if item["kind"] == "visual_generation_report"
    )
    assert generation["content"]["items"] == [reports["visual_generation_report"]["items"][1]]


def test_visual_decision_rejects_ambiguous_generation_identity_as_contract_failure(tmp_path: Path) -> None:
    reports = {
        "visual_generation_report": {"items": [
            {"item_id": "cat", "sha256": "a" * 64},
            {"item_id": "cat", "sha256": "b" * 64},
        ]},
        "visual_inspection_report": {"items": [{"asset_sha256": "b" * 64}]},
        "visual_caption_report": {"items": [{"asset_sha256": "b" * 64}]},
    }
    artifacts = []
    for kind, report in reports.items():
        path = tmp_path / f"{kind}.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        artifacts.append({"id": kind, "kind": kind, "uri": str(path)})

    with pytest.raises(ArtifactContractError, match="exact commissioned item"):
        VisualDecisionHandler().prompt_texts(
            {"system": "Decide.", "template": "Use evidence."},
            {"specification": {"commission": {"items": [{"item_id": "cat"}]}}, "limits": {}},
            artifacts, 8192,
        )


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


@pytest.mark.parametrize(("route_limit", "expected"), [(0, None), (1024, 1024), (4096, 2048)])
def test_http_zero_route_limit_uses_endpoint_default(route_limit: int, expected: int | None, monkeypatch) -> None:
    captured = {}

    class Response:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def read(self, _limit):
            return json.dumps({"choices": [{"message": {"content": "{}"}}]}).encode()

    def open_request(request, **_kwargs):
        captured.update(json.loads(request.data))
        return Response()

    monkeypatch.setattr("mission_hub.handlers.visual_provider.urllib.request.urlopen", open_request)
    _http(
        {"endpoint": "https://provider.test/chat/completions", "credential_env": "", "timeout_seconds": 30},
        {"exact_name": "provider/model", "output_tokens": 2048},
        "Generate structured output.", route_limit,
    )

    if expected is None:
        assert "max_tokens" not in captured
    else:
        assert captured["max_tokens"] == expected


@pytest.mark.parametrize("body,code", [("", "provider_empty_output"), ('{"plan_id":', "provider_output_truncated"), ("not json", "structured_response_invalid")])
def test_provider_output_faults_have_specific_codes(body: str, code: str) -> None:
    with pytest.raises(ProviderFailure) as failure:
        _json_from_text(body)
    assert failure.value.code == code


def test_empty_provider_output_falls_back_without_software_mutation(tmp_path: Path, monkeypatch) -> None:
    calls = []
    valid = {
        "plan_id": "fallback-plan", "teaching_goal": "teach a ball", "canonical_text": ["ball"],
        "items": [{
            "item_id": "ball", "prompt": "one red ball", "canonical_caption": "red ball",
            "seeds": [1], "width": 512, "height": 512, "steps": 4, "guidance_scale": 3.5,
        }], "provenance_requirements": ["hash"],
    }

    def provider(provider, model, prompt, token_limit):
        calls.append(model["id"])
        if len(calls) == 1:
            raise ProviderFailure("empty", "repairable_output", "provider_empty_output")
        return valid, {"provider": model["id"]}

    monkeypatch.setattr("mission_hub.handlers.visual_provider._http", provider)
    context = {
        "state_root": str(tmp_path / "state"), "artifact_roots": [str(tmp_path)], "artifacts": [],
        "run": {"id": "run-provider-fallback"}, "release_root": str(REPO),
        "route": {"id": "visual-planning", "max_total_tokens": 8192, "fallback_failure_classes": ["repairable_output"]},
        "route_models": [
            {"id": "primary", "exact_name": "primary", "provider": "p", "enabled": True, "output_tokens": 1024},
            {"id": "fallback", "exact_name": "fallback", "provider": "p", "enabled": True, "output_tokens": 1024},
        ],
        "providers": {"p": {"id": "p", "kind": "openai_compatible", "endpoint": "https://unused", "credential_env": "", "timeout_seconds": 30, "enabled": True}},
        "prompt": {"id": "visual-plan-v1", "version": 1, "system": "plan", "template": "x", "output_schema": "schemas/mission_hub/providers/visual-plan.response.schema.json"},
    }
    result = VisualPlanHandler().execute(
        {"input_artifact_ids": [], "specification": {"goal": "ball"}, "limits": {}}, context,
    )
    transcript_artifact = next(item for item in result["artifacts"] if item["kind"] == "provider_transcript")
    transcript = json.loads(Path(transcript_artifact["uri"]).read_text(encoding="utf-8"))
    assert calls == ["primary", "fallback"]
    assert transcript["attempts"][0]["failure_code"] == "provider_empty_output"
    assert transcript["attempts"][1]["status"] == "succeeded"
