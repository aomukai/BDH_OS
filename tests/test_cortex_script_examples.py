from __future__ import annotations

from pathlib import Path

from tests.test_msm_trainer import script
from training.pipeline.cortex.script_examples import examples_from_msm_script


ROOT = Path(__file__).resolve().parents[1]


def test_finalized_msm_script_becomes_in_memory_cortex_examples() -> None:
    value = script("session-cortex")
    examples = examples_from_msm_script(
        value,
        ROOT / "training/pipeline/script_schema.json",
    )
    assert examples == [
        ("Is a box a container?", "A box is a container."),
    ]


def test_expected_answer_is_used_when_script_has_no_correction() -> None:
    value = script("session-anchor")
    item = value["items"][0]
    item["teacher_correction"] = None
    item["ask_after_correction"] = False
    item["expected_original"]["acceptable"] = ["Yes, a box is a container."]
    examples = examples_from_msm_script(
        value,
        ROOT / "training/pipeline/script_schema.json",
    )
    assert examples[0][1] == "Yes, a box is a container."
