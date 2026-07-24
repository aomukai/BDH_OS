from __future__ import annotations

import json
from pathlib import Path

from training.pipeline.control.msm_trainer import MsmTrainer


ROOT = Path(__file__).resolve().parents[1]


def setup_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    pipeline = repo / "training/pipeline"
    pipeline.mkdir(parents=True)
    for name in ("script_schema.json", "raw_chat_line_schema.json"):
        (pipeline / name).write_bytes((ROOT / "training/pipeline" / name).read_bytes())
    return repo


def script(session_id: str = "session-test") -> dict:
    return {
        "schema_version": "msm_script_v1",
        "script_id": "script-test",
        "session_id": session_id,
        "orchestrator_plan_id": "plan-test",
        "script_author": "executor:test",
        "created_at": "2026-07-25T00:00:00Z",
        "concept": "container",
        "card_id": "card-test",
        "checkpoint": "core/test.pt",
        "session_mode": "contrast_session",
        "intended_stage": "test",
        "intended_failure_targets": [],
        "executor_context": {
            "executor_id": "gemma",
            "selection_method": "fixed",
            "meta_scratchpad_injected": False,
            "meta_scratchpad_path": None,
        },
        "script_fingerprint": {
            "algorithm": "msm_script_fingerprint_v1",
            "structural_hash": "test",
            "prompt_hash": "test",
            "question_type_sequence": ["recognition"],
            "contrast_pairs": [["box", "cloud"]],
        },
        "trainer_contract": {
            "send_user_prompt": True,
            "record_original_answer": True,
            "send_teacher_correction": True,
            "record_after_correction_answer": True,
            "do_not_grade": True,
            "do_not_modify_items": True,
        },
        "items": [
            {
                "item_id": "item-1",
                "stage": "recognition",
                "user_prompt": "Is a box a container?",
                "teacher_correction": "A box is a container.",
                "ask_after_correction": True,
                "expected_original": {"acceptable": ["yes"], "forbidden": ["no"]},
                "expected_after_correction": {
                    "acceptable": ["yes"],
                    "forbidden": ["no"],
                },
                "target_failure_modes": [],
                "training_answer_max_bytes": 64,
            }
        ],
    }


def inference() -> dict:
    return {
        "max_new_tokens": 32,
        "temperature": 0.0,
        "top_k": None,
        "device": "cpu",
    }


def test_shadow_session_materializes_script_without_inference(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    trainer = MsmTrainer(
        repo_root=repo,
        inference_factory=lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("shadow mode must not load inference")
        ),
    )
    result, hashes = trainer.run(
        script=script(),
        mode="shadow",
        checkpoint_path=None,
        inference=inference(),
    )
    assert result["status"] == "planned"
    assert result["event_count"] == 0
    assert result["artifacts"]["raw_log"] is None
    assert len(hashes) == 2
    replay, replay_hashes = trainer.run(
        script=script(),
        mode="shadow",
        checkpoint_path=None,
        inference=inference(),
    )
    assert replay == result
    assert replay_hashes == hashes


def test_live_session_records_exact_order_without_grading(tmp_path: Path) -> None:
    repo = setup_repo(tmp_path)
    checkpoint = repo / "core/test.pt"
    checkpoint.parent.mkdir()
    checkpoint.write_bytes(b"checkpoint")

    class Model:
        calls = 0

        def generate_text(self, _prompt):
            self.calls += 1
            return "original" if self.calls == 1 else "after"

    trainer = MsmTrainer(repo_root=repo, inference_factory=lambda **_kwargs: Model())
    result, _ = trainer.run(
        script=script("session-live"),
        mode="live",
        checkpoint_path="core/test.pt",
        inference=inference(),
    )
    assert result["status"] == "completed"
    raw = repo / result["artifacts"]["raw_log"]
    events = [json.loads(line) for line in raw.read_text().splitlines()]
    assert [event["event_type"] for event in events] == [
        "user_prompt",
        "ninereeds_original_answer",
        "teacher_correction",
        "ninereeds_after_correction_answer",
    ]
    assert events[0]["text"] == "Is a box a container?"
    assert "grade" not in result
