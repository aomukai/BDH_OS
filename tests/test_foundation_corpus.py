from __future__ import annotations

import json
from pathlib import Path

from training.pipeline.control.ledger import (
    MAX_ENVELOPE_BYTES,
    ControlLedger,
    canonical_json,
)
from training.pipeline.cortex.foundation_corpus import (
    FOUNDATION_BLOCK_SIZE,
    FOUNDATION_CHUNK_SIZE,
    build_foundation_replay_script,
    foundation_replay_chunks,
)
from training.pipeline.cortex.script_examples import validate_msm_script


ROOT = Path(__file__).resolve().parents[1]


def test_foundation_replay_script_has_operator_mix_and_fits_transport(
    tmp_path: Path,
) -> None:
    script = build_foundation_replay_script(
        ROOT,
        campaign_id="foundation-test",
        block_index=1,
        parent_checkpoint="core/cortex/parent.pt",
        orchestrator_plan_id="plan-eval-parent",
    )
    validate_msm_script(script, ROOT / "training/pipeline/script_schema.json")

    stages = [item["stage"] for item in script["items"]]
    assert len(stages) == FOUNDATION_BLOCK_SIZE
    assert stages.count("replay") == 325
    assert stages.count("new") == 125
    assert stages.count("special") == 25
    assert stages.count("special_de") == 12
    assert stages.count("special_ja") == 13

    chunks = foundation_replay_chunks(script)
    assert len(chunks) == FOUNDATION_BLOCK_SIZE // FOUNDATION_CHUNK_SIZE
    assert sum(len(chunk["examples"]) for chunk in chunks) == FOUNDATION_BLOCK_SIZE
    assert len({chunk["curriculum_sha256"] for chunk in chunks}) == 1

    ledger = ControlLedger(tmp_path / "control")
    for chunk in chunks:
        plan = ledger.create_plan(
            kind="cortex_corpus_chunk",
            mode="live",
            payload={
                "curriculum_id": "foundation-test",
                **chunk,
                "output_path": (
                    "core/cortex/curricula/foundation-test/"
                    f"chunk-{chunk['chunk_index']:04d}.jsonl"
                ),
            },
            created_by="orchestrator:test",
            plan_id=f"plan-foundation-chunk-{chunk['chunk_index']:04d}",
        )
        assert len(canonical_json(plan)) < MAX_ENVELOPE_BYTES // 4
