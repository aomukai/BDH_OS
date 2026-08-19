import argparse
import json
from pathlib import Path

from image_registry.campaign35_flux_specialist_controller import SpecialistController
from image_registry.campaign35_flux_generate import seed_for


def _json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_existing_review_advances_to_zero_residual_completion_gate(tmp_path: Path, monkeypatch) -> None:
    decisions = tmp_path / "decisions.jsonl"
    decisions.write_text("", encoding="utf-8")
    review_result = tmp_path / "review" / "result.json"
    _json(review_result, {
        "status": "reviewed_and_reconciled", "authoritative_decisions": str(decisions),
    })
    config = tmp_path / "config.json"
    _json(config, {
        "schema_version": "ninereeds_campaign35_word_image_loop_v1",
        "run_id": "base", "root": str(tmp_path / "base"),
        "db": str(tmp_path / "registry.sqlite3"), "store": str(tmp_path / "store"),
        "curriculum": str(tmp_path / "curriculum.jsonl"),
        "requirements": str(tmp_path / "requirements.jsonl"),
        "initial_decisions": str(decisions), "initial_prior_queues": [],
    })
    evidence = tmp_path / "representation.jsonl"
    evidence.write_text("", encoding="utf-8")
    args = argparse.Namespace(
        base_config=config, root=tmp_path / "controller", loop_root=tmp_path / "loop",
        initial_cycle=2, initial_review_result=review_result,
        initial_generated_root=tmp_path / "generated",
        representation_reconciliation=[evidence], remote="test", remote_root="/remote",
        remote_python="python", remote_model="model", poll_seconds=0.01,
    )
    controller = SpecialistController(args)
    controller.wait_review()
    assert controller.state["phase"] == "plan"
    assert controller.state["cycle"] == 3

    def fake_module(_name: str, *arguments: str) -> None:
        output = Path(arguments[arguments.index("--output") + 1])
        _json(output / "summary.json", {"confirmed_single_image_generation_slots": 0})
        (output / "gap_inventory.jsonl").write_text("", encoding="utf-8")

    monkeypatch.setattr(controller, "module", fake_module)
    controller.plan()
    assert controller.state["phase"] == "complete"
    assert controller.state["final_inventory"].endswith("gap_inventory.jsonl")


def test_flux_seed_namespace_changes_pixels_between_cycles() -> None:
    assert seed_for("campaign35-flux-v6", "scene-0001", 0) == seed_for(
        "campaign35-flux-v6", "scene-0001", 0,
    )
    assert seed_for("campaign35-flux-v6", "scene-0001", 0) != seed_for(
        "campaign35-flux-v7", "scene-0001", 0,
    )
