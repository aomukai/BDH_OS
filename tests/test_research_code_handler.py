from __future__ import annotations

import json
import hashlib
from pathlib import Path
import threading
from types import SimpleNamespace

import pytest

from mission_hub.config import load_config_bundle
from mission_hub.errors import SafetyError
import mission_hub.handlers.research_decision as research_decision_module
from mission_hub.handlers.research_code import ResearchCodeChangeHandler
from mission_hub.handlers.research_decision import ResearchDecisionHandler
from mission_hub.handlers.visual_provider import ProviderFailure
from mission_hub.schema import load_schema, validate


ROOT = Path(__file__).resolve().parents[1]


def code_action() -> dict:
    return {
        "kind": "modify_code",
        "advice_question": None,
        "dataset_acquisition": None,
        "experiment_title": None,
        "hypothesis": None,
        "dataset_id": None,
        "epochs": None,
        "max_records_per_epoch": None,
        "order_policy": None,
        "order_seed": None,
        "intervention_type": None,
        "control_experiment_id": None,
        "max_sessions": None,
        "max_events_per_session": None,
        "controls": None,
        "code_change_title": "Expose development telemetry",
        "code_change_hypothesis": "Publication drops executor development events.",
        "code_change_objective": "Expose explicit counts and rejection reasons.",
        "code_change_acceptance_criteria": ["Every stage has an explicit count."],
        "code_change_scopes": ["telemetry"],
        "campaign_report": None,
        "next_campaign_title": None,
        "next_campaign_goal": None,
    }


def advice_action() -> dict:
    action = code_action()
    action.update({
        "kind": "ask_for_advice",
        "advice_question": "What observation would best distinguish a hard gate from insufficient experience?",
        "code_change_title": None,
        "code_change_hypothesis": None,
        "code_change_objective": None,
        "code_change_acceptance_criteria": None,
        "code_change_scopes": None,
    })
    return action


def conclusion_action() -> dict:
    action = code_action()
    action.update({
        "kind": "conclude_campaign",
        "code_change_title": None,
        "code_change_hypothesis": None,
        "code_change_objective": None,
        "code_change_acceptance_criteria": None,
        "code_change_scopes": None,
        "campaign_report": "The bounded evidence resolves the current question.",
        "next_campaign_title": "Next mechanism boundary",
        "next_campaign_goal": "Test the next unresolved Mycelium mechanism.",
    })
    return action


def provider_response(action: dict, message: str) -> dict:
    return {
        "action": action,
        "message": message,
        "rationale": "The evidence warrants this bounded choice.",
        "updated_todo": {
            "focus": "Resolve the current mechanism boundary.",
            "current_hypothesis": "The boundary is experimentally distinguishable.",
            "next_questions": ["Which observation separates the alternatives?"],
            "constraints": ["Knowledge, not improvement."],
        },
    }


def test_modify_code_is_valid_only_when_authoritative_state_allows_it() -> None:
    ResearchDecisionHandler._validate_semantics(
        {"action": code_action()}, ["launch_experiment", "modify_code", "conclude_campaign"],
    )
    with pytest.raises(ProviderFailure, match="outside the authoritative state boundary"):
        ResearchDecisionHandler._validate_semantics(
            {"action": code_action()}, ["wait"],
        )


def test_modify_code_requires_complete_bounded_fields() -> None:
    action = code_action()
    action["code_change_acceptance_criteria"] = None
    with pytest.raises(ProviderFailure, match="omitted a required bounded code-change field"):
        ResearchDecisionHandler._validate_semantics(
            {"action": action}, ["modify_code"],
        )


def test_ask_for_advice_is_a_nonexecuting_deliberation_action() -> None:
    ResearchDecisionHandler._validate_semantics(
        {"action": advice_action()}, ["ask_for_advice", "launch_experiment"],
    )
    missing = advice_action()
    missing["advice_question"] = None
    with pytest.raises(ProviderFailure, match="omitted its exact question"):
        ResearchDecisionHandler._validate_semantics(
            {"action": missing}, ["ask_for_advice"],
        )


def test_advice_sampling_returns_only_three_anonymous_ideas_to_sol(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = load_config_bundle(ROOT / "config" / "mission_hub")
    state_root = tmp_path / "state"
    state_root.mkdir()
    calls: list[dict] = []
    final_prompts: list[str] = []
    lock = threading.Lock()
    ideas = {
        "gpt-5.6-terra": "Test whether the gate responds to deliberately independent contexts.",
        "gpt-5.6-luna": "Measure whether repeated exposure changes the first inactive stage.",
        "gpt-5.5": "Compare one long lineage with several short lineages at equal event count.",
        "gpt-5.4": "Probe whether residual coherence is telemetry rather than a causal gate.",
        "gpt-5.4-mini": "Try a tiny adversarial dataset that maximizes source-family contrast.",
        "gpt-5.3-codex-spark": "Instrument the exact transition immediately before candidate formation.",
    }

    def fake_codex(
        provider, model, prompt, schema_path, images, run_root, *, reasoning_effort=None,
    ):
        with lock:
            calls.append({
                "model": model["exact_name"], "effort": reasoning_effort,
                "prompt": prompt,
            })
        if model["exact_name"] == "gpt-5.6-sol":
            if '"anonymous_advice"' in prompt:
                with lock:
                    final_prompts.append(prompt)
                return provider_response(
                    conclusion_action(), "I am concluding this campaign and opening the next one.",
                ), {"mock": "conductor-final"}
            return provider_response(
                advice_action(), "I am sampling three anonymous ideas before deciding.",
            ), {"mock": "conductor-initial"}
        return {"idea": ideas[model["exact_name"]]}, {"mock": "advisor"}

    monkeypatch.setattr(research_decision_module, "_codex", fake_codex)
    payload = {
        "lab_id": "research-lab",
        "campaign_id": "campaign-45",
        "campaign_number": 45,
        "activation_id": "research-activation-45-9",
        "goal": "Map the candidate-formation boundary.",
        "todo": {"focus": "Identify the first inactive gate."},
        "observation": {"operating_state": "idle", "candidate_total": 0},
        "recent_reports": [],
        "available_datasets": [],
        "allowed_actions": [
            "ask_for_advice", "acquire_dataset", "launch_experiment",
            "modify_code", "conclude_campaign",
        ],
    }
    context = {
        "prompt": bundle.prompts["research-decision-v1"],
        "prompts": bundle.prompts,
        "route": bundle.routes["research-conductor"],
        "route_models": [bundle.models["codex-gpt-5.6-sol"]],
        "routes": bundle.routes,
        "models": bundle.models,
        "providers": bundle.providers,
        "release_root": str(ROOT),
        "state_root": str(state_root),
        "run": {"id": "run-advice-test"},
    }

    result = ResearchDecisionHandler().execute(payload, context)

    assert result["action"]["kind"] == "conclude_campaign"
    assert len(calls) == 5
    advisor_calls = [call for call in calls if call["model"] != "gpt-5.6-sol"]
    assert len(advisor_calls) == 3
    assert all(call["effort"] == "high" for call in advisor_calls)
    assert all(call["effort"] is None for call in calls if call["model"] == "gpt-5.6-sol")
    assert len(final_prompts) == 1
    continuation = json.loads(final_prompts[0].split(
        "Current activation data and anonymous ideas:\n", 1,
    )[1])
    assert len(continuation["anonymous_advice"]) == 3
    assert all(isinstance(idea, str) for idea in continuation["anonymous_advice"])
    assert "advisor_slot" not in final_prompts[0]
    assert not any(call["model"] in final_prompts[0] for call in advisor_calls)
    transcript_artifact = next(
        item for item in result["artifacts"] if item["kind"] == "provider_transcript"
    )
    transcript = json.loads(Path(transcript_artifact["uri"]).read_text(encoding="utf-8"))
    assert transcript["advice_sampled"] is True
    assert sum(attempt["phase"] == "advice" for attempt in transcript["attempts"]) == 3


def test_dataset_acquisition_requires_a_coherent_public_adapter() -> None:
    action = code_action()
    action.update({
        "kind": "acquire_dataset",
        "dataset_acquisition": {
            "dataset_name": "wikipedia-v1",
            "source_url": "https://example.org/wiki.jsonl",
            "source_page_url": "https://example.org/wiki",
            "license": "CC-BY-SA-4.0",
            "expected_sha256": None,
            "max_download_bytes": 1024,
            "dataset_format": "jsonl",
            "archive_format": "none",
            "records_member": None,
            "modality": "text",
            "objective": "continuation",
            "text_field": "text",
            "prompt_field": None,
            "completion_field": None,
            "image_field": None,
            "caption_field": None,
        },
        "code_change_title": None,
        "code_change_hypothesis": None,
        "code_change_objective": None,
        "code_change_acceptance_criteria": None,
        "code_change_scopes": None,
    })
    ResearchDecisionHandler._validate_semantics(
        {"action": action}, ["acquire_dataset"],
    )
    response = {
        "action": action,
        "message": "I am acquiring this bounded dataset now.",
        "rationale": "It discriminates a data-volume hypothesis.",
        "updated_todo": {
            "focus": "Map data-volume behavior.",
            "current_hypothesis": "More independent records may change development evidence.",
            "next_questions": ["Does candidate formation change?"],
            "constraints": ["Knowledge, not improvement."],
        },
    }
    schema = load_schema(
        ROOT, "schemas/mission_hub/providers/research-decision.response.schema.json",
    )
    assert validate(response, schema) == []

    action["dataset_acquisition"]["text_field"] = None
    with pytest.raises(ProviderFailure, match="inconsistent"):
        ResearchDecisionHandler._validate_semantics(
            {"action": action}, ["acquire_dataset"],
        )


def test_code_scope_allows_experimental_telemetry_and_tests() -> None:
    roots = ResearchCodeChangeHandler.allowed_roots(["telemetry"])
    ResearchCodeChangeHandler.validate_changed_files([
        "campaign36c/development.py",
        "mission_hub/handlers/campaign36c.py",
        "tests/test_campaign36c_development.py",
    ], roots)


def test_code_scope_refuses_conductor_configuration_and_training_data() -> None:
    roots = ResearchCodeChangeHandler.allowed_roots(["telemetry"])
    for path in (
        "mission_hub/research_lab.py",
        "config/mission_hub/base.toml",
        "schemas/mission_hub/jobs/generic.output.schema.json",
        "training_data/v8_curriculum/README.md",
    ):
        with pytest.raises(SafetyError, match="escaped its authorized scope"):
            ResearchCodeChangeHandler.validate_changed_files(
                [path, "tests/test_campaign36c_development.py"], roots,
            )


def test_code_scope_allows_bounded_test_only_diagnostics() -> None:
    roots = ResearchCodeChangeHandler.allowed_roots(["telemetry"])
    ResearchCodeChangeHandler.validate_changed_files(
        ["tests/test_campaign36c_development.py"], roots,
    )


def test_regression_fixtures_are_isolated_and_removed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "repository"
    workspace = tmp_path / "worktree"
    workspace.mkdir()

    campaign = repository / "config/mission_hub/campaigns/campaign.json"
    campaign.parent.mkdir(parents=True)
    campaign.write_text(json.dumps({
        "evaluation": "archive/evaluation.json",
        "material": "training_data/campaign/material",
    }) + "\n", encoding="utf-8")
    declared = {
        "archive/evaluation.json": "evaluation\n",
        "training_data/campaign/material/example.jsonl": "material\n",
        "archive/docs/history.md": "# History\n",
        "archive/registry.json": '{"registry": true}\n',
        "campaign36c/development.py": "canonical implementation\n",
        "config/mission_hub/campaign_material/README.md": "canonical readme\n",
        "config/mission_hub/campaign_material/campaign35/text.jsonl": "lesson\n",
    }
    for relative, body in declared.items():
        path = repository / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")

    research = repository / "mission_hub/research"
    (research / "intake").mkdir(parents=True)
    (research / "sources.json").write_text(json.dumps({
        "sources": [{"path": "archive/registry.json"}],
    }) + "\n", encoding="utf-8")
    (research / "intake/source-census.json").write_text(json.dumps({
        "candidates": [{"path": "archive/docs/history.md"}],
    }) + "\n", encoding="utf-8")

    existing_training = workspace / "training_data/v8_curriculum/README.md"
    existing_training.parent.mkdir(parents=True)
    existing_training.write_text("user curriculum\n", encoding="utf-8")
    existing_material = workspace / "config/mission_hub/campaign_material/README.md"
    existing_material.parent.mkdir(parents=True)
    existing_material.write_text("canonical readme\n", encoding="utf-8")
    candidate_source = workspace / "campaign36c/development.py"
    candidate_source.parent.mkdir(parents=True)
    candidate_source.write_text("Sol candidate implementation\n", encoding="utf-8")
    monkeypatch.setattr(
        "mission_hub.handlers.research_code.load_config_bundle",
        lambda _path: SimpleNamespace(recovery={"source_repository_root": str(repository)}),
    )

    handler = ResearchCodeChangeHandler()
    monkeypatch.setattr(handler, "_git_bytes", lambda _root, *_args: b"\0".join((
        b"campaign36c/development.py",
        b"config/mission_hub/campaign_material/README.md",
        b"training_data/v8_curriculum/README.md",
        b"",
    )))
    with handler._regression_fixtures(workspace):
        for relative in declared:
            target = workspace / relative
            assert target.is_file()
        assert candidate_source.read_text(encoding="utf-8") == "Sol candidate implementation\n"
        (workspace / "archive/evaluation.json").write_text("mutated\n", encoding="utf-8")
        assert (repository / "archive/evaluation.json").read_text(encoding="utf-8") == "evaluation\n"

    assert existing_training.read_text(encoding="utf-8") == "user curriculum\n"
    assert existing_material.read_text(encoding="utf-8") == "canonical readme\n"
    assert candidate_source.read_text(encoding="utf-8") == "Sol candidate implementation\n"
    assert not (workspace / "archive").exists()
    assert not (workspace / "training_data/campaign").exists()
    assert not (workspace / "config/mission_hub/campaign_material/campaign35").exists()


def test_registered_candidate_hash_is_refreshed_only_from_matching_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "worktree"
    source = workspace / "campaign36c/development.py"
    source.parent.mkdir(parents=True)
    source.write_text("candidate\n", encoding="utf-8")
    base = b"base\n"
    registry = workspace / "mission_hub/research/sources.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({
        "schema_version": "ninereeds_research_source_registry_v1",
        "sources": [{
            "id": "development", "path": "campaign36c/development.py",
            "sha256": hashlib.sha256(base).hexdigest(),
        }],
    }) + "\n", encoding="utf-8")
    handler = ResearchCodeChangeHandler()
    monkeypatch.setattr(handler, "_git_bytes", lambda _root, *_args: base)

    changed = handler._refresh_registered_source_hashes(
        workspace, ["campaign36c/development.py"],
    )

    assert changed == ["mission_hub/research/sources.json"]
    refreshed = json.loads(registry.read_text(encoding="utf-8"))
    assert refreshed["sources"][0]["sha256"] == hashlib.sha256(b"candidate\n").hexdigest()


def test_registered_candidate_hash_refuses_a_stale_base(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace = tmp_path / "worktree"
    source = workspace / "campaign36c/development.py"
    source.parent.mkdir(parents=True)
    source.write_text("candidate\n", encoding="utf-8")
    registry = workspace / "mission_hub/research/sources.json"
    registry.parent.mkdir(parents=True)
    registry.write_text(json.dumps({
        "sources": [{
            "path": "campaign36c/development.py", "sha256": "0" * 64,
        }],
    }) + "\n", encoding="utf-8")
    handler = ResearchCodeChangeHandler()
    monkeypatch.setattr(handler, "_git_bytes", lambda _root, *_args: b"base\n")

    with pytest.raises(SafetyError, match="registry was stale before"):
        handler._refresh_registered_source_hashes(
            workspace, ["campaign36c/development.py"],
        )
