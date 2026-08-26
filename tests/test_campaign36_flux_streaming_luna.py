from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from image_registry.campaign36_flux_streaming_luna import (
    assignment_identity,
    attempt_identity,
    derive_verdict,
    load_jsonl,
    mechanical_check,
    retry_request,
    validate_luna,
)


def row(path: Path) -> dict:
    return {
        "production_brief_id": "scene-0001-a1-g1", "variant_index": 2,
        "generation_attempt": 1, "concept_ids": ["c-dog"], "words": ["dog"],
        "evidence_by_concept": {"c-dog": "one plainly visible dog"},
        "flux_prompt_template": "A dog runs on grass.",
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "width": 512, "height": 384,
    }


def result(**updates) -> dict:
    value = {
        "admission": "usable", "visible_text": False, "watermark": False,
        "quality_flags": [], "literal_caption": "A dog runs on grass.", "reason": "clear",
        "targets": [{"concept_id": "c-dog", "verdict": "present", "evidence": "dog visible"}],
        "uncertainties": [], "recommission_instruction": "none",
    }
    value.update(updates)
    return value


def test_mechanical_and_identities(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    Image.new("RGB", (512, 384), "green").save(image)
    item = row(image)
    assert mechanical_check(image, item)["passed"] is True
    assert assignment_identity(item) == "scene-0001-a1-g1-v02"
    assert attempt_identity(item) == "scene-0001-a1-g1-v02-a01"


def test_verdict_and_bounded_retry(tmp_path: Path) -> None:
    image = tmp_path / "image.png"
    Image.new("RGB", (512, 384), "green").save(image)
    item = row(image)
    validate_luna(item, result())
    assert derive_verdict(result()) == ("accepted", [])
    rejected = result(quality_flags=["malformed paw"], recommission_instruction="Fix the paw.")
    verdict, reasons = derive_verdict(rejected)
    assert verdict == "recommission"
    request = retry_request(item, {
        "verdict": verdict, "failure_reasons": reasons,
        "recommission_instruction": rejected["recommission_instruction"],
    }, 3)
    assert request is not None and request["generation_attempt"] == 2
    assert request["flux_prompt_template"] == "A dog runs on grass."
    item["generation_attempt"] = 3
    assert retry_request(item, {
        "verdict": verdict, "failure_reasons": reasons,
        "recommission_instruction": "Fix it.",
    }, 3) is None


def test_partial_tail_is_ignored(tmp_path: Path) -> None:
    path = tmp_path / "ledger.jsonl"
    path.write_text(json.dumps({"a": 1}) + "\n{" , encoding="utf-8")
    assert load_jsonl(path, tolerate_partial_tail=True) == [{"a": 1}]
