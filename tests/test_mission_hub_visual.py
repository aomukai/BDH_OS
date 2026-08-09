from __future__ import annotations

from pathlib import Path
import json
import subprocess

import pytest

from mission_hub.errors import RemoteJobError, SafetyError
from mission_hub.handlers.visual import (
    VisualCaptionHandler, VisualExperienceCompileHandler, VisualGenerateHandler,
    VisualPackFinalizeHandler, VisualReviewRuntimeHandler,
)


def context(tmp_path: Path, artifacts: list[dict], *, shadow: bool = False) -> dict:
    return {
        "state_root": str(tmp_path), "artifacts": artifacts,
        "visual_limits": {"shadow_mode": shadow, "max_pack_items": 8, "max_pack_bytes": 1024},
    }


def candidate(artifact_id: str, digest: str) -> dict:
    return {"id": artifact_id, "kind": "visual_candidate", "sha256": digest, "byte_size": 12, "manifest": {}}


def review(artifact_id: str, digest: str, *, status: str = "usable") -> dict:
    return {
        "id": artifact_id, "kind": "visual_review_report", "sha256": "f" * 64, "byte_size": 12,
        "manifest": {"asset_sha256": digest, "reviewer": "sol", "asset_status": status, "accepted_uses": ["a red ball"] if status == "usable" else []},
    }


def test_pack_finalization_requires_independent_usable_review(tmp_path: Path) -> None:
    digest = "a" * 64
    artifacts = [candidate("art-image", digest), review("art-review", digest)]
    output = VisualPackFinalizeHandler().execute(
        {"input_artifact_ids": ["art-image", "art-review"], "specification": {"pack_id": "pack-red"}, "limits": {}},
        context(tmp_path, artifacts),
    )
    assert output["status"] == "succeeded"
    assert output["artifacts"][0]["manifest"]["items"][0]["asset_sha256"] == digest

    with pytest.raises(SafetyError, match="requires candidate"):
        VisualPackFinalizeHandler().execute(
            {"input_artifact_ids": ["art-image"], "specification": {}, "limits": {}}, context(tmp_path, artifacts[:1]),
        )


def test_pack_finalization_uses_only_the_selected_usable_subset(tmp_path: Path) -> None:
    accepted_digest = "a" * 64
    rejected_digest = "b" * 64
    artifacts = [
        candidate("art-accepted", accepted_digest),
        review("review-accepted", accepted_digest),
        candidate("art-rejected", rejected_digest),
        review("review-rejected", rejected_digest, status="unusable"),
    ]
    ctx = context(tmp_path, artifacts)
    ctx["visual_limits"]["max_pack_items"] = 1

    output = VisualPackFinalizeHandler().execute(
        {
            "input_artifact_ids": ["art-accepted", "review-accepted"],
            "specification": {"pack_id": "pack-selected"}, "limits": {},
        },
        ctx,
    )

    assert [item["asset_artifact_id"] for item in output["artifacts"][0]["manifest"]["items"]] == ["art-accepted"]
    assert "art-rejected" not in output["artifacts"][0]["manifest"]["source_artifact_ids"]


def test_pack_finalization_accepts_selected_rows_from_one_batch_review(tmp_path: Path) -> None:
    accepted_digest = "a" * 64
    rejected_digest = "b" * 64
    batch_review = {
        "id": "review-batch", "kind": "visual_review_report",
        "sha256": "f" * 64, "byte_size": 12,
        "manifest": {
            "reviewer": "sol", "independent_review": True,
            "items": [
                {"asset_sha256": accepted_digest, "result": {
                    "asset_sha256": accepted_digest, "asset_status": "usable",
                    "accepted_uses": ["a red ball"],
                }},
                {"asset_sha256": rejected_digest, "result": {
                    "asset_sha256": rejected_digest, "asset_status": "unusable",
                    "accepted_uses": [],
                }},
            ],
        },
    }
    artifacts = [candidate("art-accepted", accepted_digest), batch_review]

    output = VisualPackFinalizeHandler().execute(
        {
            "input_artifact_ids": ["art-accepted", "review-batch"],
            "specification": {"pack_id": "pack-batch"}, "limits": {},
        },
        context(tmp_path, artifacts),
    )

    assert output["artifacts"][0]["manifest"]["items"][0]["review_artifact_id"] == "review-batch"


def test_shadow_mode_blocks_asset_admission(tmp_path: Path) -> None:
    with pytest.raises(SafetyError, match="shadow mode"):
        VisualPackFinalizeHandler().execute(
            {"input_artifact_ids": [], "specification": {}, "limits": {}}, context(tmp_path, [], shadow=True),
        )


def test_experience_compiler_accepts_only_pack_images_and_canonical_text(tmp_path: Path) -> None:
    digest = "a" * 64
    pack = {
        "id": "art-pack", "kind": "visual_pack", "sha256": "b" * 64, "byte_size": 42,
        "manifest": {"status": "accepted", "items": [{"asset_sha256": digest}]},
    }
    payload = {
        "input_artifact_ids": ["art-pack"], "limits": {},
        "specification": {"events": [{"type": "observe_image", "asset_sha256": digest}, {"type": "hear_or_read_text", "text": "A red ball."}]},
    }
    output = VisualExperienceCompileHandler().execute(payload, context(tmp_path, [pack]))
    assert output["metrics"]["events"] == 2

    payload["specification"]["events"][0]["asset_sha256"] = "c" * 64
    with pytest.raises(SafetyError, match="unaccepted image"):
        VisualExperienceCompileHandler().execute(payload, context(tmp_path, [pack]))


def test_visual_runtime_records_pinned_fallback_and_declares_outputs(tmp_path: Path, monkeypatch) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}\n", encoding="utf-8")
    plan = {"id": "plan", "kind": "visual_plan", "uri": str(plan_path), "sha256": __import__("hashlib").sha256(plan_path.read_bytes()).hexdigest(), "byte_size": plan_path.stat().st_size, "manifest": {}}
    calls = []
    environments = []
    def run(command, **kwargs):
        calls.append(command)
        environments.append(kwargs["env"])
        if len(calls) == 1:
            return subprocess.CompletedProcess(command, 69, "", "gpu unavailable")
        result_path = Path(command[command.index("--result") + 1])
        candidate_path = result_path.parent / "candidate.png"
        report_path = result_path.parent / "generation-report.json"
        candidate_path.write_bytes(b"png-test")
        report_path.write_text("{}\n", encoding="utf-8")
        result_path.write_text(json.dumps({
            "schema_version": "ninereeds_visual_runtime_result_v1", "stage": "visual.generate",
            "metrics": {"candidates": 1},
            "outputs": [
                {"kind": "visual_candidate", "uri": str(candidate_path), "manifest": {"seed": 7}},
                {"kind": "visual_generation_report", "uri": str(report_path), "manifest": {"candidate_count": 1}},
            ],
        }), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "ok", "")
    monkeypatch.setattr("mission_hub.handlers.visual.subprocess.run", run)
    visual_limits = {
        "shadow_mode": True, "max_pack_items": 8, "max_candidates_per_item": 2,
        "max_width": 1024, "max_height": 1024, "max_generation_steps": 16,
        "max_stage_seconds": 600, "max_pack_bytes": 1024, "minimum_free_bytes": 1,
        "store_root": str(tmp_path), "independent_review_required": True,
    }
    ctx = {
        "state_root": str(tmp_path), "artifact_roots": [str(tmp_path)], "artifacts": [plan],
        "visual_limits": visual_limits, "run": {"id": "run-visual"}, "timeout_seconds": 600,
        "route": {"id": "visual-generation", "fallback_failure_classes": ["capability_transient"]},
        "route_models": [
            {"id": "flux-a", "exact_name": "flux/a", "revision": "rev-a", "runtime": "/vision/python", "weights": "/models", "device": "cuda:0", "provider": "vision", "enabled": True},
            {"id": "flux-b", "exact_name": "flux/b", "revision": "rev-b", "runtime": "/vision/python", "weights": "/models", "device": "cuda:0", "provider": "vision", "enabled": True},
        ],
        "providers": {"vision": {"enabled": True}},
        "release_root": str(tmp_path),
        "deployment_environment": {"python_site_paths": ["/composite-site"]},
        "prompt": None,
    }
    result = VisualGenerateHandler().execute(
        {"input_artifact_ids": ["plan"], "specification": {"items": []}, "limits": {}}, ctx,
    )
    assert len(calls) == 2
    assert all(environment["PYTHONPATH"] == str(tmp_path.resolve()) for environment in environments)
    assert all(environment["PYTHONNOUSERSITE"] == "1" for environment in environments)
    assert all("composite-site" not in environment["PYTHONPATH"] for environment in environments)
    assert {item["kind"] for item in result["artifacts"]} == {"visual_candidate", "visual_generation_report", "log"}
    assert result["artifacts"][0]["manifest"]["model_revision"] == "rev-b"


def test_visual_runtime_classifies_disk_floor_as_operational_resource_failure(tmp_path: Path, monkeypatch) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}\n", encoding="utf-8")
    plan = {
        "id": "plan", "kind": "visual_plan", "uri": str(plan_path),
        "sha256": __import__("hashlib").sha256(plan_path.read_bytes()).hexdigest(),
        "byte_size": plan_path.stat().st_size, "manifest": {},
    }
    monkeypatch.setattr(
        "mission_hub.handlers.visual.subprocess.run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 75, "", "visual resource unavailable: free disk is below the safety floor",
        ),
    )
    ctx = {
        "state_root": str(tmp_path), "artifact_roots": [str(tmp_path)], "artifacts": [plan],
        "visual_limits": {"max_stage_seconds": 600}, "run": {"id": "run-disk-floor"},
        "timeout_seconds": 600,
        "route": {"id": "visual-generation", "fallback_failure_classes": ["operational_transient"]},
        "route_models": [{
            "id": "flux", "exact_name": "flux", "revision": "rev", "runtime": "/vision/python",
            "weights": "/models", "device": "cuda:0", "provider": "vision", "enabled": True,
        }],
        "providers": {"vision": {"enabled": True}}, "release_root": str(tmp_path),
        "deployment_environment": {}, "prompt": None,
    }
    with pytest.raises(RemoteJobError) as caught:
        VisualGenerateHandler().execute(
            {"input_artifact_ids": ["plan"], "specification": {}, "limits": {}}, ctx,
        )
    assert caught.value.failure_class == "operational_transient"
    assert caught.value.code == "resource_temporarily_unavailable"


def test_visual_runtime_preserves_byte_streams_from_timeout(tmp_path: Path, monkeypatch) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("{}\n", encoding="utf-8")
    plan = {
        "id": "plan", "kind": "visual_plan", "uri": str(plan_path),
        "sha256": __import__("hashlib").sha256(plan_path.read_bytes()).hexdigest(),
        "byte_size": plan_path.stat().st_size, "manifest": {},
    }

    def timeout(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs["timeout"], output=b"partial output", stderr=b"timed out")

    monkeypatch.setattr("mission_hub.handlers.visual.subprocess.run", timeout)
    ctx = {
        "state_root": str(tmp_path), "artifact_roots": [str(tmp_path)], "artifacts": [plan],
        "visual_limits": {"max_stage_seconds": 600}, "run": {"id": "run-timeout"},
        "timeout_seconds": 600,
        "route": {"id": "visual-generation", "fallback_failure_classes": []},
        "route_models": [{
            "id": "flux", "exact_name": "flux", "revision": "rev", "runtime": "/vision/python",
            "weights": "/models", "device": "cuda:0", "provider": "vision", "enabled": True,
        }],
        "providers": {"vision": {"enabled": True}}, "release_root": str(tmp_path),
        "deployment_environment": {}, "prompt": None,
    }

    with pytest.raises(RemoteJobError) as caught:
        VisualGenerateHandler().execute(
            {"input_artifact_ids": ["plan"], "specification": {}, "limits": {}}, ctx,
        )

    assert caught.value.failure_class == "operational_transient"
    assert caught.value.code == "resource_temporarily_unavailable"
    log = json.loads((tmp_path / "runs" / "run-timeout" / "visual-runtime-log.json").read_text())
    assert log["attempts"][0]["stdout"] == "partial output"
    assert log["attempts"][0]["stderr"] == "timed out"


def test_visual_caption_can_use_codex_image_input(tmp_path: Path, monkeypatch) -> None:
    pixels = tmp_path / "candidate.png"
    pixels.write_bytes(b"verified-image-fixture")
    digest = __import__("hashlib").sha256(pixels.read_bytes()).hexdigest()
    inspection_path = tmp_path / "inspection.json"
    inspection_path.write_text("{}\n", encoding="utf-8")
    inspection_digest = __import__("hashlib").sha256(inspection_path.read_bytes()).hexdigest()
    artifacts = [
        {"id": "candidate", "kind": "visual_candidate", "uri": str(pixels), "sha256": digest,
         "byte_size": pixels.stat().st_size, "manifest": {"item_id": "one"}},
        {"id": "inspection", "kind": "visual_inspection_report", "uri": str(inspection_path),
         "sha256": inspection_digest, "byte_size": inspection_path.stat().st_size, "manifest": {}},
    ]

    def run(command, **kwargs):
        assert command[command.index("--model") + 1] == "gpt-5.6-luna"
        assert command[command.index("--image") + 1] == str(pixels)
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps({
            "accessibility_caption": "One visible object.", "teaching_caption": "one",
            "preserved_visible_facts": ["one object"], "uncertainty": [],
        }), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("mission_hub.handlers.visual_provider.subprocess.run", run)
    ctx = {
        "state_root": str(tmp_path / "state"), "artifact_roots": [str(tmp_path)], "artifacts": artifacts,
        "visual_limits": {"max_stage_seconds": 600}, "run": {"id": "run-luna-caption"},
        "timeout_seconds": 600,
        "route": {"id": "visual-caption", "max_total_tokens": 4096, "fallback_failure_classes": []},
        "route_models": [{"id": "luna", "exact_name": "gpt-5.6-luna", "revision": "",
                          "runtime": "codex exec", "weights": "", "device": "remote",
                          "provider": "codex-headless", "enabled": True}],
        "providers": {"codex-headless": {"id": "codex-headless", "kind": "codex_cli",
                                           "endpoint": "/codex", "timeout_seconds": 30, "enabled": True}},
        "release_root": str(Path(__file__).resolve().parents[1]),
        "prompt": {"id": "visual-caption-v1", "version": 1, "system": "Caption visible facts.",
                   "template": "{evidence}",
                   "output_schema": "schemas/mission_hub/providers/visual-caption.response.schema.json"},
    }
    result = VisualCaptionHandler().execute(
        {"input_artifact_ids": ["candidate", "inspection"], "specification": {}, "limits": {}}, ctx,
    )
    assert result["status"] == "succeeded"
    assert {item["kind"] for item in result["artifacts"]} == {
        "visual_caption_report", "provider_transcript", "log",
    }
    report = next(item for item in result["artifacts"] if item["kind"] == "visual_caption_report")
    assert report["manifest"]["model_id"] == "gpt-5.6-luna"


def test_visual_review_emits_one_batch_artifact_for_multiple_candidates(tmp_path: Path, monkeypatch) -> None:
    artifacts = []
    digests = []
    for index in range(2):
        pixels = tmp_path / f"candidate-{index}.png"
        pixels.write_bytes(f"verified-image-{index}".encode())
        digest = __import__("hashlib").sha256(pixels.read_bytes()).hexdigest()
        digests.append(digest)
        artifacts.append({
            "id": f"candidate-{index}", "kind": "visual_candidate", "uri": str(pixels),
            "sha256": digest, "byte_size": pixels.stat().st_size,
            "manifest": {"item_id": f"item-{index}", "seed": index},
        })
    for artifact_id, kind in (("inspection", "visual_inspection_report"), ("decision", "visual_decision_report")):
        path = tmp_path / f"{artifact_id}.json"
        path.write_text("{}\n", encoding="utf-8")
        artifacts.append({
            "id": artifact_id, "kind": kind, "uri": str(path),
            "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
            "byte_size": path.stat().st_size, "manifest": {},
        })

    def run(command, **kwargs):
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps({
            "asset_sha256": "0" * 64, "asset_status": "usable",
            "accepted_uses": ["one object"], "visible_facts": ["one object"],
            "uncertainty": [], "reason": "The pixels support this use.",
        }), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("mission_hub.handlers.visual_provider.subprocess.run", run)
    repo = Path(__file__).resolve().parents[1]
    ctx = {
        "state_root": str(tmp_path / "state"), "artifact_roots": [str(tmp_path)],
        "artifacts": artifacts, "visual_limits": {"max_stage_seconds": 600},
        "run": {"id": "run-batch-review"}, "timeout_seconds": 600,
        "route": {"id": "visual-final-review", "max_total_tokens": 8192, "fallback_failure_classes": []},
        "route_models": [{
            "id": "sol", "exact_name": "gpt-5.6-sol", "revision": "", "runtime": "codex exec",
            "weights": "", "device": "remote", "provider": "codex-headless", "enabled": True,
        }],
        "providers": {"codex-headless": {
            "id": "codex-headless", "kind": "codex_cli", "endpoint": "/codex",
            "timeout_seconds": 30, "enabled": True,
        }},
        "release_root": str(repo),
        "prompt": {
            "id": "visual-review-v1", "version": 1, "system": "Review visible facts.",
            "template": "{evidence}",
            "output_schema": "schemas/mission_hub/providers/visual-review.response.schema.json",
        },
    }

    result = VisualReviewRuntimeHandler().execute({
        "input_artifact_ids": ["candidate-0", "candidate-1", "inspection", "decision"],
        "specification": {}, "limits": {},
    }, ctx)

    reviews = [item for item in result["artifacts"] if item["kind"] == "visual_review_report"]
    assert len(reviews) == 1
    assert reviews[0]["manifest"]["item_count"] == 2
    assert [item["asset_sha256"] for item in reviews[0]["manifest"]["items"]] == digests
