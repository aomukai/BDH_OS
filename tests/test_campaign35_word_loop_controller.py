import json
from pathlib import Path

import pytest

from image_registry.campaign35_word_loop_controller import (
    Controller, LoopConfig, SCHEMA_VERSION, exclusive_controller, initial_state, parse_config,
)


def _jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _config(tmp_path):
    decisions = tmp_path / "decisions.jsonl"
    _jsonl(decisions, [
        {"slot_id": "a", "disposition": "accepted"},
        {"slot_id": "b", "disposition": "missing_candidate"},
    ])
    return LoopConfig(
        run_id="test-loop", root=tmp_path / "run", db=tmp_path / "db.sqlite3",
        store=tmp_path / "store", curriculum=tmp_path / "curriculum.jsonl",
        requirements=tmp_path / "requirements.jsonl", initial_decisions=decisions,
        initial_prior_queues=("prior",),
    )


def test_initial_state_is_durable_and_counts_acceptance(tmp_path):
    config = _config(tmp_path)
    state = initial_state(config)
    assert state["phase"] == "local_discover"
    assert state["accepted_slots"] == 1
    controller = Controller(config)
    assert json.loads(config.state_path.read_text())["run_id"] == "test-loop"
    controller2 = Controller(config)
    assert controller2.state == controller.state


def test_controller_lock_refuses_second_owner(tmp_path):
    root = tmp_path / "run"
    with exclusive_controller(root):
        with pytest.raises(RuntimeError, match="already owns"):
            with exclusive_controller(root):
                pass


def test_unknown_phase_emits_terminal_blocker(tmp_path):
    config = _config(tmp_path)
    controller = Controller(config)
    controller.state["phase"] = "impossible"
    controller.step()
    assert controller.state["phase"] == "blocked"
    blocker = json.loads((config.root / "blocker.json").read_text())
    assert blocker["reason"] == "unknown controller phase"


def test_parse_config_rejects_unknown_schema(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"schema_version": "wrong"}))
    with pytest.raises(ValueError, match="unknown"):
        parse_config(path)


def test_worker_generation_has_unique_claim_identities(tmp_path):
    config = _config(tmp_path)
    controller = Controller(config)
    controller.state["queues"] = {
        "semantic": "s", "watermark": "w", "usability": "u",
        "word_fit": "f", "sol": "z",
    }
    first = {name for name, _ in controller.worker_commands(1)}
    second = {name for name, _ in controller.worker_commands(2)}
    assert first
    assert first.isdisjoint(second)
    assert any("sol" in name for name in first)


def test_local_round_uses_luna_as_primary_candidate_reviewer(tmp_path):
    controller = Controller(_config(tmp_path))
    controller.state["mode"] = "local"
    controller.state["queues"] = {
        "semantic": "s", "watermark": "w", "usability": "u",
        "word_fit": "f", "sol": "z",
    }

    commands = controller.worker_commands(1)
    primary = [(name, command) for name, command in commands if "local-luna" in name]

    assert len(primary) == 4
    assert all("image_benchmark.luna_campaign_word_worker" in command for _, command in primary)
    assert not any("llama.cpp" in " ".join(command) for _, command in commands)


def test_provider_credentials_do_not_enable_online_bulk_review_by_default(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENROUTER_API_KEY", "present-but-not-authorized")
    monkeypatch.setenv("NVIDIA_API_KEY", "present-but-not-authorized")
    controller = Controller(_config(tmp_path))
    controller.state["queues"] = {
        "semantic": "s", "watermark": "w", "usability": "u",
        "word_fit": "f", "sol": "z",
    }

    names = {name for name, _ in controller.worker_commands(1)}

    assert not any("openrouter" in name or "nvidia" in name for name in names)


def test_online_bulk_review_requires_frozen_config_opt_in(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "authorized-by-config")
    monkeypatch.setenv("NVIDIA_API_KEY", "authorized-by-config")
    base = _config(tmp_path)
    config = LoopConfig(**{**base.__dict__, "allow_online_bulk_review": True})
    controller = Controller(config)
    controller.state["queues"] = {
        "semantic": "s", "watermark": "w", "usability": "u",
        "word_fit": "f", "sol": "z",
    }

    names = {name for name, _ in controller.worker_commands(1)}

    assert any("openrouter" in name for name in names)
    assert any("nvidia" in name for name in names)


def test_local_no_progress_routes_to_external_sources(tmp_path: Path, monkeypatch):
    config = _config(tmp_path)
    controller = Controller(config)
    controller.state.update({
        "mode": "local",
        "accepted_slots": 1,
        "residual_slots": 1,
        "authoritative_decisions": str(config.initial_decisions),
        "prior_review_queues": [],
        "queues": {
            "semantic": "s", "watermark": "w", "usability": "u",
            "word_fit": "f", "sol": "z",
        },
    })
    capped = controller.round_root() / "reconciled-cap"
    capped.mkdir(parents=True)
    (capped / "summary.json").write_text(
        json.dumps({"accepted_slots": 1, "residual_slots": 1}), encoding="utf-8"
    )
    monkeypatch.setattr(controller, "module", lambda *args: None)

    controller.round_finalize()

    assert controller.state["phase"] == "external_discover"
    assert controller.state["status"] == "active"
    assert controller.state["external_no_progress_rounds"] == 0
