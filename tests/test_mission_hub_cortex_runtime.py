from __future__ import annotations

from pathlib import Path

from mission_hub.handlers.cortex import _cortex_command, _runtime


def test_cortex_subprocess_preserves_venv_and_adds_torch_after_startup(
    tmp_path: Path, monkeypatch,
) -> None:
    monkeypatch.delenv("PYTHONPATH", raising=False)
    context = {
        "release_root": str(tmp_path / "release"),
        "state_root": str(tmp_path / "state"),
        "run": {"id": "run-runtime"},
        "deployment_environment": {
            "python_executable": "/commissioned/cortex-venv/bin/python",
            "python_site_paths": ["/composite/unsloth/site-packages"],
        },
    }

    executable, environment, run_root = _runtime(context)
    command = _cortex_command(executable, context, "meta/scripts/probe_cortex_checkpoint.py")

    assert str(executable) == "/commissioned/cortex-venv/bin/python"
    assert environment["PYTHONPATH"] == str((tmp_path / "release").resolve())
    assert environment["NINEREEDS_TORCH_SITE"] == "/composite/unsloth/site-packages"
    assert command == [
        "/commissioned/cortex-venv/bin/python",
        str(tmp_path / "release" / "meta/scripts/cortex_runtime.py"),
        str(tmp_path / "release" / "meta/scripts/probe_cortex_checkpoint.py"),
    ]
    assert run_root.is_dir()
