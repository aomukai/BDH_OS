from __future__ import annotations

from pathlib import Path
import json
import subprocess

import pytest

from mission_hub.errors import RemoteJobError, SafetyError
from mission_hub.handlers.visual import VisualExperienceCompileHandler, VisualGenerateHandler, VisualPackFinalizeHandler


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
