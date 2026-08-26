from __future__ import annotations

import json
import os
import time

from image_registry.campaign36_headless_imagegen import (
    cleanup_own_generated_cache_copy,
    representation_conflict,
)
from image_registry.campaign36_flux_streaming_luna import derive_verdict, effective_visible_text_policy
from image_registry.campaign36_flux_streaming_luna import prompt_for as review_prompt_for
from image_registry.campaign36_imagegen_fallback import (
    active_override,
    brainstorm_state,
    provider_attempts,
    select_next,
)


def test_gemma_ideas_receive_three_attempts_each(tmp_path):
    output = tmp_path / "imagegen-v1"
    output.mkdir()
    assert brainstorm_state(output, "a", 2) == (None, None)
    assert brainstorm_state(output, "a", 3) == (None, 3)
    record = {
        "assignment_id": "a",
        "after_attempt": 3,
        "ideas": [{"title": str(index), "prompt": "p"} for index in range(5)],
    }
    (output / "brainstorms.jsonl").write_text(json.dumps(record) + "\n", encoding="utf-8")
    active, due = brainstorm_state(output, "a", 3)
    assert active == record and due is None
    active, due = brainstorm_state(output, "a", 17)
    assert active == record and due is None
    assert brainstorm_state(output, "a", 18) == (None, -1)


def test_cache_cleanup_removes_only_matching_artifact_created_by_job(tmp_path):
    cache = tmp_path / "generated_images"
    old = cache / "old" / "old.png"
    new = cache / "new" / "new.png"
    output = tmp_path / "staging.png"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"same generated pixels")
    os.utime(old, ns=(1, 1))
    cutoff = time.time_ns()
    new.parent.mkdir(parents=True)
    new.write_bytes(b"same generated pixels")
    output.write_bytes(b"same generated pixels")
    removed = cleanup_own_generated_cache_copy(
        output, not_before_ns=cutoff, cache_root=cache,
    )
    assert removed == [str(new)]
    assert old.is_file()
    assert not new.exists()


def test_text_dependent_contract_is_not_quarantined():
    source = {"evidence_by_concept": {"contraction": "The written phrase has an apostrophe."}}
    assert representation_conflict(source) is None


def test_required_visible_text_is_scoped_exception():
    source = {
        "evidence_by_concept": {"translatable": "Exact words in two languages."},
        "visible_text_policy": "required_evidence",
    }
    assert representation_conflict(source) is None
    result = {
        "admission": "usable", "visible_text": True, "watermark": False,
        "quality_flags": [], "uncertainties": [],
        "targets": [{"concept_id": "translatable", "verdict": "present"}],
    }
    assert derive_verdict(result, source) == ("accepted", [])
    assert derive_verdict(result, {}) == ("accepted", [])


def test_explicitly_labeled_artifact_infers_required_text_policy():
    source = {
        "evidence_by_concept": {
            "yeast": "Risen dough and a packet labeled 'yeast' show the ingredient."
        }
    }
    assert effective_visible_text_policy(source) == "required_evidence"
    assert representation_conflict(source) is None
    result = {
        "admission": "usable", "visible_text": True, "watermark": False,
        "quality_flags": [], "uncertainties": [],
        "targets": [{"concept_id": "yeast", "verdict": "present"}],
    }
    assert derive_verdict(result, source) == ("accepted", [])


def test_explicit_reject_policy_wins_over_textual_inference():
    source = {
        "evidence_by_concept": {"x": "a packet labeled x"},
        "visible_text_policy": "reject",
    }
    assert effective_visible_text_policy(source) == "reject"


def test_contextual_transfer_is_explicit_in_review_prompt():
    row = {
        "concept_ids": ["translatable"], "words": ["translatable"],
        "evidence_by_concept": {"translatable": "The Rosetta Stone shows multiple scripts."},
        "grounding_mode": "contextual_transfer",
    }
    prompt = review_prompt_for(row)
    assert "contextual transfer anchor" in prompt
    assert "standalone visual dictionary definition" in prompt


def test_manual_override_gets_one_bounded_three_attempt_cycle(tmp_path):
    output = tmp_path / "imagegen-v1"
    output.mkdir()
    record = {
        "assignment_id": "a",
        "after_attempt": 15,
        "allowed_attempts": 3,
        "evidence_by_concept": {"continuity": "damaged but still operating"},
    }
    (output / "representation-overrides.jsonl").write_text(
        json.dumps(record) + "\n", encoding="utf-8"
    )
    assert active_override(output, "a", 15) == record
    assert active_override(output, "a", 17) == record
    assert active_override(output, "a", 18) is None


def test_failed_headless_generation_consumes_provider_attempt(tmp_path):
    output = tmp_path / "imagegen-v1"
    output.mkdir()
    rows = [
        {"assignment_id": "a", "provider_attempt": 1, "status": "generation_failed"},
        {"assignment_id": "a", "provider_attempt": 2, "status": "reserved"},
        {"assignment_id": "b", "provider_attempt": 3, "status": "generated"},
    ]
    (output / "headless-jobs.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8"
    )
    assert provider_attempts(output) == {"a": 1, "b": 3}


def test_user_override_bypasses_pending_brainstorm_gate(tmp_path):
    root = tmp_path
    streaming = root / "streaming-luna"
    output = root / "imagegen-v1"
    (streaming / "incoming" / "recommissioned").mkdir(parents=True)
    output.mkdir()
    source = {
        "production_brief_id": "a", "variant_index": 0, "generation_attempt": 3,
        "concept_ids": ["x"], "evidence_by_concept": {"x": "visible x"},
    }
    (streaming / "incoming" / "recommissioned" / "recommission-00.jsonl").write_text(
        json.dumps(source) + "\n", encoding="utf-8"
    )
    decision = {
        "attempt_id": "a-v00-a03", "assignment_id": "a-v00", "generation_attempt": 3,
        "verdict": "recommission", "sha256": "0" * 64,
    }
    (streaming / "decisions.jsonl").write_text(json.dumps(decision) + "\n", encoding="utf-8")
    failed = {"assignment_id": "a-v00", "provider_attempt": 3, "status": "generation_failed"}
    (output / "headless-jobs.jsonl").write_text(json.dumps(failed) + "\n", encoding="utf-8")
    override = {
        "assignment_id": "a-v00", "after_attempt": 3, "allowed_attempts": 3,
        "evidence_by_concept": {"x": "neutral visual paraphrase"},
        "representation_prompt": "neutral visual paraphrase",
    }
    (output / "representation-overrides.jsonl").write_text(
        json.dumps(override) + "\n", encoding="utf-8"
    )
    assert select_next(root, "a-v00") == (source, decision)


def test_third_generated_attempt_can_enter_review_before_brainstorm(tmp_path):
    root = tmp_path
    streaming = root / "streaming-luna"
    output = root / "imagegen-v1"
    (streaming / "incoming" / "recommissioned").mkdir(parents=True)
    output.mkdir()
    source = {
        "production_brief_id": "a", "variant_index": 0, "generation_attempt": 3,
        "concept_ids": ["x"], "evidence_by_concept": {"x": "visible x"},
    }
    (streaming / "incoming" / "recommissioned" / "recommission-00.jsonl").write_text(
        json.dumps(source) + "\n", encoding="utf-8"
    )
    decision = {
        "attempt_id": "a-v00-a03", "assignment_id": "a-v00", "generation_attempt": 3,
        "verdict": "recommission", "sha256": "0" * 64,
    }
    (streaming / "decisions.jsonl").write_text(json.dumps(decision) + "\n", encoding="utf-8")
    generated = {"assignment_id": "a-v00", "provider_attempt": 3, "status": "generated"}
    (output / "headless-jobs.jsonl").write_text(json.dumps(generated) + "\n", encoding="utf-8")
    assert select_next(root, "a-v00", current_provider_attempt=3) == (source, decision)
