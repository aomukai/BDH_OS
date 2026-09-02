from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile

import pytest

from cortex.config import CortexConfig
from mission_hub.config import load_config_bundle
from mission_hub.errors import SafetyError
from mission_hub.handlers.campaign36c import (
    Campaign36CCellLabHandler,
    Campaign36CDevelopmentLabHandler,
    Campaign36CHygieneLabHandler,
    Campaign36CLearningLabHandler,
    Campaign36COrganismArchiveHandler,
    Campaign36COrganismBootstrapHandler,
    Campaign36COrganismStatusHandler,
    Campaign36CPersistenceLabHandler,
    Campaign36CStructuralLabHandler,
    Campaign36CWaveLabHandler,
)
from mission_hub.schema import load_schema, validate


ROOT = Path(__file__).resolve().parents[1]


def payload() -> dict:
    return {
        "mode": "synthetic",
        "latent_task_artifact_id": None,
        "pair_counts": [1, 2, 4, 8, 16, 32],
        "training_steps": 64,
        "learning_rate": 0.003,
        "benchmark_warmup": 3,
        "benchmark_iterations": 10,
        "residual_scale": 0.25,
        "mechanical_tolerance": 0.02,
        "minimum_improvement_fraction": 0.01,
        "seed": 36_003,
        "device_indices": [0, 1],
        "dtype": "bfloat16",
        "synthetic": {
            "width": 512,
            "sequence_length": 16,
            "training_examples": 16,
            "evaluation_examples": 8,
            "teacher_pairs": 8,
        },
    }


def context(tmp_path: Path) -> dict:
    return {
        "state_root": str(tmp_path),
        "run": {"id": "run-campaign36c-test"},
        "release_root": str(ROOT),
        "deployment_environment": {
            "python_executable": "/test/python",
            "python_site_paths": [],
            "required_model_paths": [
                {
                    "id": "siglip2-base-patch16-naflex",
                    "path": "/models/siglip2/b53b807d",
                }
            ],
        },
        "timeout_seconds": 60,
        "artifacts": [],
        "artifact_roots": [str(ROOT)],
    }


def wave_payload() -> dict:
    return {
        "width": 512,
        "rotary_pairs": 2,
        "sequence_length": 16,
        "disconnected_cell_counts": [0, 256, 4096],
        "benchmark_warmup": 5,
        "benchmark_iterations": 25,
        "maximum_material_latency_ratio": 3.0,
        "maximum_serviceable_p95_ms": 5000.0,
        "seed": 36_200,
        "device_indices": [0, 1],
        "dtype": "bfloat16",
    }


def learning_payload() -> dict:
    return {
        "width": 512,
        "rotary_pairs": 2,
        "sequence_length": 16,
        "training_examples": 12,
        "evaluation_examples": 6,
        "training_steps": 64,
        "black_swan_steps": 32,
        "common_replay_steps": 16,
        "disconnected_cells": 64,
        "learning_rate": 0.03,
        "minimum_heldout_improvement_fraction": 0.01,
        "seed": 36_300,
        "device_indices": [0, 1],
        "dtype": "bfloat16",
    }


def development_payload() -> dict:
    return {
        "width": 512,
        "rotary_pairs": 2,
        "sequence_length": 16,
        "training_examples": 6,
        "evaluation_examples": 3,
        "shadow_training_steps": 128,
        "disconnected_cells": 64,
        "learning_rate": 0.001,
        "minimum_shadow_improvement_fraction": 0.005,
        "minimum_residual_coherence": 0.35,
        "seed": 36_400,
        "device_indices": [0, 1],
        "dtype": "bfloat16",
    }


def persistence_payload() -> dict:
    return {
        "width": 512,
        "rotary_pairs": 2,
        "sequence_length": 16,
        "disconnected_cells": 200,
        "page_capacities": [2, 20, 200],
        "access_set_sizes": [2, 20, 200],
        "dirty_update_events": 8,
        "seed": 36_500,
        "device_indices": [0, 1],
        "dtype": "bfloat16",
    }


def structural_payload() -> dict:
    return {
        "width": 512,
        "rotary_pairs": 2,
        "sequence_length": 16,
        "benchmark_warmup": 3,
        "benchmark_iterations": 20,
        "page_capacity": 2,
        "maximum_composite_leaves": 2,
        "behavior_tolerance": 0.02,
        "maximum_seam_regression": 0.0001,
        "seed": 36_600,
        "device_indices": [0, 1],
        "dtype": "bfloat16",
    }


def hygiene_payload() -> dict:
    return {
        "width": 512,
        "rotary_pairs": 2,
        "sequence_length": 16,
        "page_capacity": 2,
        "senescence_interval": 2,
        "minimum_senescence_sweeps": 1,
        "maximum_revival_candidates": 2,
        "minimum_revival_similarity": 0.8,
        "minimum_revival_improvement_fraction": 0.05,
        "maximum_revival_regression": 0.01,
        "seed": 36_700,
        "device_indices": [0, 1],
        "dtype": "bfloat16",
    }


def organism_bootstrap_payload(*, mode: str = "smoke") -> dict:
    return {
        "mode": mode,
        "resume": False,
        "device_indices": [0, 1],
        "dtype": "bfloat16",
    }


def test_multimodal_bootstrap_packages_and_attests_all_three_organs() -> None:
    bundle = load_config_bundle(ROOT / "config/mission_hub")
    definition = bundle.jobs["model.organism_bootstrap"]
    deployment = bundle.deployment_roles["trainbox-agent-release"]
    models = {item["id"]: item for item in deployment["required_model_paths"]}

    assert definition["version"] == 3
    assert "text-and-visual" in definition["description"]
    assert "cortex" in deployment["include_roots"]
    assert "campaign36c" in deployment["include_roots"]
    assert models["lfm2.5-encoder-230m"]["revision"] == CortexConfig().encoder_revision
    assert models["lfm2.5-230m"]["revision"] == CortexConfig().lfm_revision
    assert models["siglip2-base-patch16-naflex"]["revision"] == (
        "b53b807d3a2d5e2b3911292f2d69e5341cdc064c"
    )


def test_cell_lab_is_packaged_for_trainbox_but_disabled_until_commissioning() -> None:
    bundle = load_config_bundle(ROOT / "config/mission_hub")
    definition = bundle.jobs["model.cell_lab"]
    deployment = bundle.deployment_roles["trainbox-agent-release"]

    assert definition["enabled"] is False
    assert definition["approval"] == "operator"
    assert "model.cell_lab" in bundle.machines["trainbox"]["allowed_job_types"]
    assert "campaign36c" in deployment["include_roots"]
    assert "meta/scripts/run_campaign36c_cell_lab.py" in deployment["required_paths"]
    assert "cell_lab_report" in bundle.artifact_types


def test_cell_lab_input_contract_accepts_the_bounded_two_gpu_sweep() -> None:
    schema = load_schema(
        ROOT,
        "schemas/mission_hub/jobs/model.cell_lab.input.schema.json",
    )

    assert validate(payload(), schema) == []


def test_wave_lab_is_packaged_but_disabled_until_commissioning() -> None:
    bundle = load_config_bundle(ROOT / "config/mission_hub")
    definition = bundle.jobs["model.wave_lab"]
    deployment = bundle.deployment_roles["trainbox-agent-release"]

    assert definition["enabled"] is False
    assert definition["approval"] == "operator"
    assert "model.wave_lab" in bundle.machines["trainbox"]["allowed_job_types"]
    assert "meta/scripts/run_campaign36c_wave_lab.py" in deployment["required_paths"]
    assert "campaign36c/wave.py" in deployment["required_paths"]
    assert "wave_lab_report" in bundle.artifact_types


def test_wave_lab_input_contract_accepts_bounded_two_gpu_run() -> None:
    schema = load_schema(
        ROOT,
        "schemas/mission_hub/jobs/model.wave_lab.input.schema.json",
    )

    assert validate(wave_payload(), schema) == []


def test_learning_lab_is_packaged_but_disabled_until_commissioning() -> None:
    bundle = load_config_bundle(ROOT / "config/mission_hub")
    definition = bundle.jobs["model.learning_lab"]
    deployment = bundle.deployment_roles["trainbox-agent-release"]

    assert definition["enabled"] is False
    assert definition["approval"] == "operator"
    assert "model.learning_lab" in bundle.machines["trainbox"]["allowed_job_types"]
    assert "meta/scripts/run_campaign36c_learning_lab.py" in deployment["required_paths"]
    assert "campaign36c/learning.py" in deployment["required_paths"]
    assert "learning_lab_report" in bundle.artifact_types


def test_learning_lab_input_contract_accepts_bounded_two_gpu_run() -> None:
    schema = load_schema(
        ROOT,
        "schemas/mission_hub/jobs/model.learning_lab.input.schema.json",
    )

    assert validate(learning_payload(), schema) == []


def test_development_lab_is_packaged_but_disabled_until_commissioning() -> None:
    bundle = load_config_bundle(ROOT / "config/mission_hub")
    definition = bundle.jobs["model.development_lab"]
    deployment = bundle.deployment_roles["trainbox-agent-release"]

    assert definition["enabled"] is False
    assert definition["approval"] == "operator"
    assert "model.development_lab" in bundle.machines["trainbox"]["allowed_job_types"]
    assert "meta/scripts/run_campaign36c_development_lab.py" in deployment["required_paths"]
    assert "campaign36c/development.py" in deployment["required_paths"]
    assert "development_lab_report" in bundle.artifact_types


def test_development_lab_input_contract_accepts_bounded_two_gpu_run() -> None:
    schema = load_schema(
        ROOT,
        "schemas/mission_hub/jobs/model.development_lab.input.schema.json",
    )

    assert validate(development_payload(), schema) == []


def test_persistence_lab_is_packaged_but_disabled_until_commissioning() -> None:
    bundle = load_config_bundle(ROOT / "config/mission_hub")
    definition = bundle.jobs["model.persistence_lab"]
    deployment = bundle.deployment_roles["trainbox-agent-release"]

    assert definition["enabled"] is False
    assert definition["approval"] == "operator"
    assert "model.persistence_lab" in bundle.machines["trainbox"]["allowed_job_types"]
    assert "meta/scripts/run_campaign36c_persistence_lab.py" in deployment["required_paths"]
    assert "campaign36c/persistence.py" in deployment["required_paths"]
    assert "campaign36c/residency.py" in deployment["required_paths"]
    assert "persistence_lab_report" in bundle.artifact_types


def test_persistence_lab_input_contract_accepts_bounded_two_gpu_run() -> None:
    schema = load_schema(
        ROOT,
        "schemas/mission_hub/jobs/model.persistence_lab.input.schema.json",
    )

    assert validate(persistence_payload(), schema) == []


def test_structural_lab_is_packaged_but_disabled_until_commissioning() -> None:
    bundle = load_config_bundle(ROOT / "config/mission_hub")
    definition = bundle.jobs["model.structural_lab"]
    deployment = bundle.deployment_roles["trainbox-agent-release"]

    assert definition["enabled"] is False
    assert definition["approval"] == "operator"
    assert "model.structural_lab" in bundle.machines["trainbox"]["allowed_job_types"]
    assert "meta/scripts/run_campaign36c_structural_lab.py" in deployment["required_paths"]
    assert "campaign36c/structural.py" in deployment["required_paths"]
    assert "campaign36c/structural_laboratory.py" in deployment["required_paths"]
    assert "structural_lab_report" in bundle.artifact_types


def test_structural_lab_input_contract_accepts_bounded_two_gpu_run() -> None:
    schema = load_schema(
        ROOT,
        "schemas/mission_hub/jobs/model.structural_lab.input.schema.json",
    )

    assert validate(structural_payload(), schema) == []


def test_hygiene_lab_is_packaged_and_enabled_for_commissioning() -> None:
    bundle = load_config_bundle(ROOT / "config/mission_hub")
    definition = bundle.jobs["model.hygiene_lab"]
    deployment = bundle.deployment_roles["trainbox-agent-release"]

    assert definition["enabled"] is True
    assert definition["approval"] == "operator"
    assert "model.hygiene_lab" in bundle.machines["trainbox"]["allowed_job_types"]
    assert "meta/scripts/run_campaign36c_hygiene_lab.py" in deployment["required_paths"]
    assert "campaign36c/hygiene.py" in deployment["required_paths"]
    assert "campaign36c/hygiene_laboratory.py" in deployment["required_paths"]
    assert "hygiene_lab_report" in bundle.artifact_types


def test_hygiene_lab_input_contract_accepts_bounded_two_gpu_run() -> None:
    schema = load_schema(
        ROOT,
        "schemas/mission_hub/jobs/model.hygiene_lab.input.schema.json",
    )

    assert validate(hygiene_payload(), schema) == []


def test_handler_rejects_a_mixed_synthetic_and_artifact_mode(tmp_path: Path) -> None:
    mixed = payload()
    mixed["latent_task_artifact_id"] = "art-not-allowed"

    with pytest.raises(SafetyError, match="no latent-task artifact"):
        Campaign36CCellLabHandler().execute(mixed, context(tmp_path))


def test_handler_emits_hashed_report_and_log_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        commissioned = payload()
        output.write_text(
            json.dumps({
                "schema_version": "ninereeds_campaign36c_cell_lab_result_v0",
                "task": {
                    "width": 512,
                    "metadata": {
                        "behavioral_evidence": False,
                        "kind": "deterministic_synthetic_mechanical_smoke",
                    },
                },
                "execution": {
                    "devices": [
                        {"device": "cuda:0", "dtype": "torch.bfloat16"},
                        {"device": "cuda:1", "dtype": "torch.bfloat16"},
                    ]
                },
                "lab_config": {
                    "pair_counts": commissioned["pair_counts"],
                    "training_steps": commissioned["training_steps"],
                    "benchmark_warmup": commissioned["benchmark_warmup"],
                    "benchmark_iterations": commissioned["benchmark_iterations"],
                    "residual_scale": commissioned["residual_scale"],
                    "seed": commissioned["seed"],
                    "mechanical_tolerance": commissioned["mechanical_tolerance"],
                    "minimum_improvement_fraction": commissioned[
                        "minimum_improvement_fraction"
                    ],
                },
                "optimizer_config": {
                    "learning_rate": commissioned["learning_rate"],
                    "betas": [0.9, 0.999],
                    "epsilon": 1e-8,
                    "weight_decay": 0.0,
                    "amsgrad": False,
                    "policy": "torch_adamw_uid_local_full_moments_v1",
                },
                "trials": [
                    {"rotary_pairs": value}
                    for value in commissioned["pair_counts"]
                ],
                "selection": {
                    "selected_rotary_pairs": 2,
                    "stage1_exit_gate_met": False,
                },
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)

    result = Campaign36CCellLabHandler().execute(payload(), context(tmp_path))

    assert result["status"] == "succeeded"
    assert result["metrics"]["trial_count"] == 6
    assert [artifact["kind"] for artifact in result["artifacts"]] == [
        "cell_lab_report",
        "log",
    ]
    assert all(len(artifact["sha256"]) == 64 for artifact in result["artifacts"])


def test_wave_handler_emits_hashed_report_and_log_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        commissioned = wave_payload()
        output.write_text(
            json.dumps({
                "schema_version": "ninereeds_campaign36c_wave_lab_result_v0",
                "lab_config": {
                    key: commissioned[key]
                    for key in (
                        "width",
                        "rotary_pairs",
                        "sequence_length",
                        "disconnected_cell_counts",
                        "benchmark_warmup",
                        "benchmark_iterations",
                        "maximum_material_latency_ratio",
                        "maximum_serviceable_p95_ms",
                        "seed",
                    )
                },
                "execution": {
                    "devices": [
                        {"device": "cuda:0", "dtype": "torch.bfloat16"},
                        {"device": "cuda:1", "dtype": "torch.bfloat16"},
                    ]
                },
                "selection": {"stage2_exit_gate_met": True},
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    wave_context = context(tmp_path)
    wave_context["run"] = {"id": "run-campaign36c-wave-test"}

    result = Campaign36CWaveLabHandler().execute(wave_payload(), wave_context)

    assert result["status"] == "succeeded"
    assert result["metrics"]["stage2_exit_gate_met"] is True
    assert result["metrics"]["maximum_disconnected_cells"] == 4096
    assert [artifact["kind"] for artifact in result["artifacts"]] == [
        "wave_lab_report",
        "log",
    ]
    assert all(len(artifact["sha256"]) == 64 for artifact in result["artifacts"])


def test_learning_handler_emits_hashed_report_and_log_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        commissioned = learning_payload()
        output.write_text(
            json.dumps({
                "schema_version": "ninereeds_campaign36c_learning_lab_result_v0",
                "lab_config": {
                    key: commissioned[key]
                    for key in (
                        "width",
                        "rotary_pairs",
                        "sequence_length",
                        "training_examples",
                        "evaluation_examples",
                        "training_steps",
                        "black_swan_steps",
                        "common_replay_steps",
                        "disconnected_cells",
                        "learning_rate",
                        "minimum_heldout_improvement_fraction",
                        "seed",
                    )
                },
                "execution": {
                    "devices": [
                        {"device": "cuda:0", "dtype": "torch.bfloat16"},
                        {"device": "cuda:1", "dtype": "torch.bfloat16"},
                    ]
                },
                "selection": {"stage3_exit_gate_met": True},
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    learning_context = context(tmp_path)
    learning_context["run"] = {"id": "run-campaign36c-learning-test"}

    result = Campaign36CLearningLabHandler().execute(
        learning_payload(), learning_context
    )

    assert result["status"] == "succeeded"
    assert result["metrics"]["stage3_exit_gate_met"] is True
    assert result["metrics"]["disconnected_cells"] == 64
    assert [artifact["kind"] for artifact in result["artifacts"]] == [
        "learning_lab_report",
        "log",
    ]
    assert all(len(artifact["sha256"]) == 64 for artifact in result["artifacts"])


def test_development_handler_emits_hashed_report_and_log_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    executor_telemetry = {
        "event_total": 10,
        "stage_records": [
            {
                "sequence": index,
                "stage": stage,
                "candidate_total": 0,
                "rejection_total": int(stage == "rejected"),
            }
            for index, stage in enumerate((
                "observing", "embryonic", "shadow", "rejected", "embryonic",
                "shadow", "probationary", "admitted", "mature", "observing",
            ), start=1)
        ],
        "candidate_total": 0,
        "rejection_counts": {
            "shadow_gate": 0,
            "harm_gate": 1,
            "admission_regression": 0,
        },
    }

    def run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        commissioned = development_payload()
        output.write_text(
            json.dumps({
                "schema_version": "ninereeds_campaign36c_development_lab_result_v0",
                "lab_config": {
                    key: commissioned[key]
                    for key in (
                        "width",
                        "rotary_pairs",
                        "sequence_length",
                        "training_examples",
                        "evaluation_examples",
                        "shadow_training_steps",
                        "disconnected_cells",
                        "learning_rate",
                        "minimum_shadow_improvement_fraction",
                        "minimum_residual_coherence",
                        "seed",
                    )
                },
                "execution": {
                    "devices": [
                        {"device": "cuda:0", "dtype": "torch.bfloat16"},
                        {"device": "cuda:1", "dtype": "torch.bfloat16"},
                    ]
                },
                "selection": {"stage4_exit_gate_met": True},
                "development_telemetry": executor_telemetry,
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    development_context = context(tmp_path)
    development_context["run"] = {"id": "run-campaign36c-development-test"}

    result = Campaign36CDevelopmentLabHandler().execute(
        development_payload(), development_context
    )

    assert result["status"] == "succeeded"
    assert result["metrics"]["stage4_exit_gate_met"] is True
    assert result["metrics"]["disconnected_cells"] == 64
    assert result["metrics"]["development_telemetry"] == executor_telemetry
    assert result["artifacts"][0]["manifest"]["development_telemetry"] == executor_telemetry
    persisted_telemetry = json.loads(
        Path(result["artifacts"][0]["uri"]).read_text(encoding="utf-8")
    )["development_telemetry"]
    assert result["metrics"]["development_telemetry"] == persisted_telemetry
    assert persisted_telemetry == executor_telemetry
    assert [record["stage"] for record in persisted_telemetry["stage_records"]] == [
        "observing",
        "embryonic",
        "shadow",
        "rejected",
        "embryonic",
        "shadow",
        "probationary",
        "admitted",
        "mature",
        "observing",
    ]
    assert all(
        set(record) == {"sequence", "stage", "candidate_total", "rejection_total"}
        for record in persisted_telemetry["stage_records"]
    )
    assert persisted_telemetry["candidate_total"] == 0
    assert persisted_telemetry["rejection_counts"] == {
        "shadow_gate": 0,
        "harm_gate": 1,
        "admission_regression": 0,
    }
    assert [artifact["kind"] for artifact in result["artifacts"]] == [
        "development_lab_report",
        "log",
    ]
    assert all(len(artifact["sha256"]) == 64 for artifact in result["artifacts"])


def test_persistence_handler_emits_hashed_report_and_log_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        commissioned = persistence_payload()
        output.write_text(
            json.dumps({
                "schema_version": "ninereeds_campaign36c_persistence_lab_result_v0",
                "lab_config": {
                    key: commissioned[key]
                    for key in (
                        "width",
                        "rotary_pairs",
                        "sequence_length",
                        "disconnected_cells",
                        "page_capacities",
                        "access_set_sizes",
                        "dirty_update_events",
                        "seed",
                    )
                },
                "execution": {
                    "devices": [
                        {"device": "cuda:0", "dtype": "torch.bfloat16"},
                        {"device": "cuda:1", "dtype": "torch.bfloat16"},
                    ]
                },
                "selection": {
                    "selected_page_capacities": [2, 2],
                    "stage5_exit_gate_met": True,
                },
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    persistence_context = context(tmp_path)
    persistence_context["run"] = {"id": "run-campaign36c-persistence-test"}

    result = Campaign36CPersistenceLabHandler().execute(
        persistence_payload(), persistence_context
    )

    assert result["status"] == "succeeded"
    assert result["metrics"]["stage5_exit_gate_met"] is True
    assert result["metrics"]["selected_page_capacities"] == [2, 2]
    assert [artifact["kind"] for artifact in result["artifacts"]] == [
        "persistence_lab_report",
        "log",
    ]
    assert all(len(artifact["sha256"]) == 64 for artifact in result["artifacts"])


def test_structural_handler_emits_hashed_report_and_log_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        commissioned = structural_payload()
        output.write_text(
            json.dumps({
                "schema_version": "ninereeds_campaign36c_structural_lab_result_v0",
                "lab_config": {
                    key: commissioned[key]
                    for key in (
                        "width",
                        "rotary_pairs",
                        "sequence_length",
                        "benchmark_warmup",
                        "benchmark_iterations",
                        "page_capacity",
                        "maximum_composite_leaves",
                        "behavior_tolerance",
                        "maximum_seam_regression",
                        "seed",
                    )
                },
                "execution": {
                    "devices": [
                        {"device": "cuda:0", "dtype": "torch.bfloat16"},
                        {"device": "cuda:1", "dtype": "torch.bfloat16"},
                    ]
                },
                "selection": {"stage6_exit_gate_met": True},
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    structural_context = context(tmp_path)
    structural_context["run"] = {"id": "run-campaign36c-structural-test"}

    result = Campaign36CStructuralLabHandler().execute(
        structural_payload(), structural_context
    )

    assert result["status"] == "succeeded"
    assert result["metrics"]["stage6_exit_gate_met"] is True
    assert result["metrics"]["maximum_composite_leaves"] == 2
    assert [artifact["kind"] for artifact in result["artifacts"]] == [
        "structural_lab_report",
        "log",
    ]
    assert all(len(artifact["sha256"]) == 64 for artifact in result["artifacts"])


def test_hygiene_handler_emits_hashed_report_and_log_artifacts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    def run(command, **_kwargs):
        output = Path(command[command.index("--output") + 1])
        commissioned = hygiene_payload()
        output.write_text(
            json.dumps({
                "schema_version": "ninereeds_campaign36c_hygiene_lab_result_v0",
                "lab_config": {
                    key: commissioned[key]
                    for key in (
                        "width",
                        "rotary_pairs",
                        "sequence_length",
                        "page_capacity",
                        "senescence_interval",
                        "minimum_senescence_sweeps",
                        "maximum_revival_candidates",
                        "minimum_revival_similarity",
                        "minimum_revival_improvement_fraction",
                        "maximum_revival_regression",
                        "seed",
                    )
                },
                "execution": {
                    "devices": [
                        {"device": "cuda:0", "dtype": "torch.bfloat16"},
                        {"device": "cuda:1", "dtype": "torch.bfloat16"},
                    ]
                },
                "selection": {"stage7_exit_gate_met": True},
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    hygiene_context = context(tmp_path)
    hygiene_context["run"] = {"id": "run-campaign36c-hygiene-test"}

    result = Campaign36CHygieneLabHandler().execute(
        hygiene_payload(), hygiene_context
    )

    assert result["status"] == "succeeded"
    assert result["metrics"]["stage7_exit_gate_met"] is True
    assert result["metrics"]["maximum_revival_candidates"] == 2
    assert [artifact["kind"] for artifact in result["artifacts"]] == [
        "hygiene_lab_report",
        "log",
    ]
    assert all(len(artifact["sha256"]) == 64 for artifact in result["artifacts"])


def test_multimodal_organism_bootstrap_requires_complete_organ_smoke(
    tmp_path: Path,
    monkeypatch,
) -> None:
    material = tmp_path / "foundation-visual-3022-v1-input"
    material.mkdir()
    (material / "manifest.json").write_text(
        json.dumps({
            "schema_version": "ninereeds_foundation_visual_material_v1",
            "input_manifest_sha256": (
                "e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb"
            ),
            "event_count": 30_220,
            "session_count": 31,
            "order_policy": "declared_only",
            "shuffle_allowed": False,
        }),
        encoding="utf-8",
    )
    donor = tmp_path / "campaign36b" / "amorphous-root.pt"
    donor.parent.mkdir()
    donor.write_bytes(b"organ initialization")
    observed_command: list[str] = []

    def run(command, **_kwargs):
        observed_command.extend(str(item) for item in command)
        output_root = Path(command[command.index("--output-dir") + 1])
        (output_root / "organism").mkdir(parents=True)
        (output_root / "organism" / "latest.json").write_text(
            json.dumps({"snapshot_name": "session-00"}), encoding="utf-8"
        )
        (output_root / "progress.json").write_text(
            json.dumps({
                "status": "training",
                "events_consumed": 11,
                "visual_events_consumed": 10,
                "text_events_consumed": 1,
                "events_in_bootstrap": 33_242,
                "organ_preflight": {"status": "passed", "latent_width": 512},
            }),
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, stdout="{}", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    result = Campaign36COrganismBootstrapHandler().execute(
        organism_bootstrap_payload(), context(tmp_path)
    )

    assert result["status"] == "succeeded"
    assert result["metrics"]["events_consumed"] == 11
    assert "--max-events-per-session" in observed_command
    assert observed_command[observed_command.index("--max-events-per-session") + 1] == "10"
    assert observed_command[observed_command.index("--visual-receptor-snapshot") + 1] == (
        "/models/siglip2/b53b807d"
    )
    receipt_path = Path(result["artifacts"][0]["uri"])
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["schema_version"] == (
        "ninereeds_campaign36c_multimodal_bootstrap_launch_v3"
    )
    assert receipt["progress"]["organ_preflight"]["status"] == "passed"


def test_organism_status_observes_progress_without_gpu_ownership(
    tmp_path: Path,
    monkeypatch,
) -> None:
    course = tmp_path / "campaign36c-bootstrap" / "course-v2"
    organism = course / "organism"
    organism.mkdir(parents=True)
    (course / "progress.json").write_text(
        json.dumps({
            "status": "training",
            "events_consumed": 120,
            "events_in_bootstrap": 33_242,
            "visual_events_consumed": 110,
            "text_events_consumed": 10,
            "active_uid_count": 9,
            "last_loss": 1.25,
        }),
        encoding="utf-8",
    )
    (organism / "latest.json").write_text(
        json.dumps({"snapshot_name": "session-00"}),
        encoding="utf-8",
    )

    def run(command, **_kwargs):
        if command[0] == "systemctl":
            return subprocess.CompletedProcess(
                command,
                0,
                stdout=(
                    "ActiveState=active\nSubState=running\n"
                    "Result=success\nExecMainStatus=0\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="0, 1024, 75, 58\n1, 768, 61, 55\n",
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", run)
    result = Campaign36COrganismStatusHandler().execute(
        {"launch_run_id": "run-b11fb1ee-11ef-49b9-8176-db91e8c2ff4c"},
        {"state_root": str(tmp_path)},
    )

    assert result["status"] == "succeeded"
    assert result["artifacts"] == []
    assert result["metrics"]["organism_status"] == "training"
    assert result["metrics"]["progress"]["events_consumed"] == 120
    assert result["metrics"]["latest_snapshot"]["snapshot_name"] == "session-00"
    assert [item["memory_used_mib"] for item in result["metrics"]["gpu"]] == [1024, 768]


def test_research_launch_uses_isolated_output_and_exact_mycelium_controls(
    tmp_path: Path,
    monkeypatch,
) -> None:
    material = tmp_path / "foundation-visual-3022-v1-input"
    material.mkdir()
    (material / "manifest.json").write_text(json.dumps({
        "schema_version": "ninereeds_foundation_visual_material_v1",
        "input_manifest_sha256": (
            "e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb"
        ),
        "event_count": 30_220,
        "session_count": 31,
        "order_policy": "declared_only",
        "shuffle_allowed": False,
    }), encoding="utf-8")
    donor = tmp_path / "campaign36b" / "amorphous-root.pt"
    donor.parent.mkdir()
    donor.write_bytes(b"organ initialization")
    observed: list[list[str]] = []

    def run(command, **_kwargs):
        command = [str(item) for item in command]
        observed.append(command)
        if command[0] == "systemctl":
            return subprocess.CompletedProcess(command, 0, stdout="active\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="launched\n", stderr="")

    monkeypatch.setattr(subprocess, "run", run)
    payload = {
        "mode": "launch",
        "resume": False,
        "campaign_id": "campaign-36-mycelium-laboratory-v1",
        "experiment_id": "experiment-36-1",
        "max_sessions": 2,
        "max_events_per_session": 20,
        "controls": {
            "seed": 36,
            "learning_rate": 0.0001,
            "cell_learning_rate": 0.002,
            "weight_decay": 0.01,
            "seed_ingress_cells": 6,
            "cell_rotary_pairs": 3,
            "initial_route_energy": 48.0,
            "branch_energy_floor": 0.2,
            "max_waves": 24,
            "max_total_activations": 192,
            "max_degree": 12,
            "max_fanout": 3,
            "minimum_observations": 5,
            "minimum_independent_lineages": 5,
            "minimum_source_families": 2,
            "minimum_residual_coherence": 0.75,
            "shadow_training_steps": 48,
            "shadow_learning_rate": 0.02,
        },
        "device_indices": [0, 1],
        "dtype": "bfloat16",
    }
    launch_context = context(tmp_path)
    launch_context["run"] = {"id": "run-11111111-1111-4111-8111-111111111111"}

    result = Campaign36COrganismBootstrapHandler().execute(payload, launch_context)

    systemd = observed[0]
    assert "--unit=ninereeds-lab-run-11111111-1111-4111-8111-111111111111" in systemd
    assert systemd[systemd.index("--max-sessions") + 1] == "2"
    assert systemd[systemd.index("--initial-route-energy") + 1] == "48.0"
    receipt = json.loads(Path(result["artifacts"][0]["uri"]).read_text(encoding="utf-8"))
    assert receipt["experiment_id"] == "experiment-36-1"
    assert receipt["output_root"].endswith(
        "/research-lab/campaign-36-mycelium-laboratory-v1/experiment-36-1"
    )
    assert receipt["controls"] == payload["controls"]


def test_organism_archive_binds_completed_snapshot_and_source_release(
    tmp_path: Path,
) -> None:
    state_root = tmp_path / "state"
    course = state_root / "campaign36c-bootstrap" / "course-v1"
    organism = course / "organism"
    shared = organism / "shared" / "session-30.pt"
    shared.parent.mkdir(parents=True)
    shared.write_bytes(b"shared-state")
    shared_sha256 = hashlib.sha256(shared.read_bytes()).hexdigest()
    progress = {
        "status": "complete",
        "events_consumed": 30_220,
        "events_in_bootstrap": 30_220,
        "sessions_completed": 31,
    }
    (course / "progress.json").write_text(json.dumps(progress), encoding="utf-8")
    latest = {
        "snapshot_name": "session-30",
        "shared_path": str(shared),
        "shared_sha256": shared_sha256,
        "progress": progress,
    }
    (organism / "latest.json").write_text(json.dumps(latest), encoding="utf-8")
    (course / "events.jsonl").write_text("{}\n", encoding="utf-8")

    releases = tmp_path / "releases"
    source_release = releases / "release-afa741658d11-594a0e9342e8"
    source_release.mkdir(parents=True)
    (source_release / "RELEASE-MANIFEST.json").write_text("{}\n", encoding="utf-8")
    (source_release / "campaign36c.py").write_text("# exact source\n", encoding="utf-8")
    os.utime(source_release / "RELEASE-MANIFEST.json", (0, 0))
    archives = tmp_path / "ninereeds-archives"
    archive_context = {
        "state_root": str(state_root),
        "artifact_roots": [str(archives)],
        "release_root": str(releases / "release-current-test"),
        "campaign_id": "campaign-36c-sparse-cellular-organism-v1",
        "run": {"id": "run-campaign36c-archive-test"},
    }
    archive_name = "campaign36c-original-visual-only-20260902.zip"
    result = Campaign36COrganismArchiveHandler().execute(
        {
            "launch_run_id": "run-b11fb1ee-11ef-49b9-8176-db91e8c2ff4c",
            "source_release_id": "release-afa741658d11-594a0e9342e8",
            "snapshot_name": "session-30",
            "shared_sha256": shared_sha256,
            "archive_name": archive_name,
        },
        archive_context,
    )

    assert result["status"] == "succeeded"
    assert result["metrics"]["snapshot_name"] == "session-30"
    assert [item["kind"] for item in result["artifacts"]] == [
        "organism_archive",
        "organism_archive_manifest",
    ]
    with zipfile.ZipFile(archives / archive_name) as archive:
        names = set(archive.namelist())
        assert "ARCHIVE-MANIFEST.json" in names
        assert "organism-course/organism/shared/session-30.pt" in names
        assert "source-release/RELEASE-MANIFEST.json" in names
        embedded = json.loads(archive.read("ARCHIVE-MANIFEST.json"))
    assert embedded["shared_sha256"] == shared_sha256
    assert embedded["file_count"] == 6
