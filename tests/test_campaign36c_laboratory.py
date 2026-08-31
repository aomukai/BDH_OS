from __future__ import annotations

import pytest

torch = pytest.importorskip(
    "torch", reason="Campaign 36C lab tests require the Cortex torch environment",
)

from campaign36c import (
    CAMPAIGN36C_CELL_LAB_RESULT_SCHEMA,
    CellLabConfig,
    CellOptimizerConfig,
    load_latent_task,
    merge_cell_lab_results,
    run_cell_laboratory,
    save_latent_task,
    synthetic_latent_task,
)


def test_latent_task_bundle_round_trip(tmp_path) -> None:
    task = synthetic_latent_task(
        width=8,
        sequence_length=4,
        training_examples=3,
        evaluation_examples=2,
        teacher_pairs=2,
    )
    path = tmp_path / "task.pt"
    save_latent_task(path, task)
    restored = load_latent_task(path)

    assert restored.metadata == task.metadata
    torch.testing.assert_close(restored.training.root_state, task.training.root_state)
    torch.testing.assert_close(restored.evaluation.target_state, task.evaluation.target_state)


def test_small_laboratory_reports_all_required_controls_and_mechanics() -> None:
    task = synthetic_latent_task(
        width=8,
        sequence_length=4,
        training_examples=4,
        evaluation_examples=3,
        teacher_pairs=2,
    )
    result = run_cell_laboratory(
        task,
        config=CellLabConfig(
            pair_counts=(1, 2),
            training_steps=2,
            benchmark_warmup=0,
            benchmark_iterations=1,
        ),
        optimizer_config=CellOptimizerConfig(learning_rate=0.01),
    )

    assert result["schema_version"] == CAMPAIGN36C_CELL_LAB_RESULT_SCHEMA
    assert result["controls"]["extra_core_tick_available"] is False
    assert result["selection"]["stage1_exit_gate_met"] is False
    assert [trial["rotary_pairs"] for trial in result["trials"]] == [1, 2]
    for trial in result["trials"]:
        assert trial["mechanics"]["within_tolerance"] is True
        assert trial["cell"]["storage"]["optimizer_tensor_bytes"] > 0
        assert trial["cell"]["estimated_evaluation_forward_macs"] > 0
        assert trial["parameter_nearest_36b_residual_control"]["parameters"] > 0


def test_independent_device_shards_merge_without_losing_pair_order() -> None:
    task = synthetic_latent_task(
        width=8,
        sequence_length=3,
        training_examples=2,
        evaluation_examples=2,
        teacher_pairs=2,
    )
    full = CellLabConfig(
        pair_counts=(1, 2),
        training_steps=1,
        benchmark_warmup=0,
        benchmark_iterations=1,
    )
    shards = [
        run_cell_laboratory(
            task,
            config=CellLabConfig(
                pair_counts=(pair_count,),
                training_steps=1,
                benchmark_warmup=0,
                benchmark_iterations=1,
            ),
        )
        for pair_count in full.pair_counts
    ]

    merged = merge_cell_lab_results(shards, config=full)

    assert merged["execution"]["parallel_shards"] == 2
    assert [trial["rotary_pairs"] for trial in merged["trials"]] == [1, 2]
