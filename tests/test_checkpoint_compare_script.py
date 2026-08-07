from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

torch = pytest.importorskip(
    "torch", reason="Cortex tests run in the isolated ninereeds-cortex environment",
)


REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "meta/scripts/compare_cortex_checkpoints.py"


def _checkpoint(path: Path, tensor: torch.Tensor, *, metadata: dict) -> None:
    torch.save({
        "schema_version": "ninereeds_cortex_checkpoint_v2",
        "core_config": {"n_layer": 1}, "cortex_config": {"model": "test"},
        "parent": "same-parent",
        "trainable_state": {"core": {"weight": tensor}},
        "optimizer_state": {"state": {0: {"exp_avg": tensor.clone()}}, "param_groups": [{"lr": 1e-3}]},
        "metadata": metadata,
    }, path)


def test_checkpoint_comparison_ignores_metadata_but_detects_learned_change(tmp_path: Path) -> None:
    control = tmp_path / "control.pt"
    observed = tmp_path / "observed.pt"
    value = torch.arange(8, dtype=torch.bfloat16)
    _checkpoint(control, value, metadata={"diagnostics": False})
    _checkpoint(observed, value.clone(), metadata={"diagnostics": True})
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--control", str(control), "--observed", str(observed)],
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 0
    changed = value.clone()
    changed[3] += 1
    _checkpoint(observed, changed, metadata={"diagnostics": True})
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--control", str(control), "--observed", str(observed)],
        text=True, capture_output=True, check=False,
    )
    assert completed.returncode == 2
