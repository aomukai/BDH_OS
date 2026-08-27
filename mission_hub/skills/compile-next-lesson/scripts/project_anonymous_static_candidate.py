#!/usr/bin/env python3
"""Project an assembled lesson into an identity-blind static-review candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


IDENTIFYING_BINDING_ROLES = {
    "prior_assembly_draft",
    "prior_authoring_receipt",
    "operator_review",
    "task_card",
    "accepted_pixel_review",
    "accepted_static_review",
    "story_comprehension_luna_medium_001",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lesson", type=Path, required=True)
    parser.add_argument("--pixel-review", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    lesson = json.loads(args.lesson.read_text(encoding="utf-8"))
    pixel_path = args.pixel_review.as_posix()
    pixel_sha = sha256(args.pixel_review)

    lesson["authoring"] = {
        "actor": "anonymous_builder",
        "prompt_path": None,
        "prompt_sha256": None,
        "receipt_path": None,
        "receipt_sha256": None,
    }
    lesson["independent_review"] = {
        "required": True,
        "reviewer_role": "independent_reviewer",
        "decision": "pending",
        "rubric_id": "anonymous-static-lesson-review-v1",
        "receipt_path": None,
        "receipt_sha256": None,
        "findings": [],
    }

    lesson["source_bindings"] = [
        binding
        for binding in lesson.get("source_bindings", [])
        if binding.get("role") not in IDENTIFYING_BINDING_ROLES
        and "luna" not in str(binding.get("role", "")).lower()
        and "luna" not in str(binding.get("path", "")).lower()
        and "sol" not in str(binding.get("role", "")).lower()
        and "sol" not in str(binding.get("path", "")).lower()
    ]

    for operation in lesson.get("visual_plan", {}).get("operations", []):
        operation["receipt_path"] = pixel_path
        operation["receipt_sha256"] = pixel_sha
        verification = operation.get("verification", {})
        verification["reviewer_role"] = "anonymous_pixel_reviewer"
        verification["receipt_path"] = pixel_path
        verification["receipt_sha256"] = pixel_sha

    for asset in lesson.get("assets", []):
        asset["review_receipt_id"] = "anonymous-pixel-review"

    rehearsal = lesson.get("rehearsal")
    if isinstance(rehearsal, dict):
        rehearsal["reason"] = (
            "Handhold mode requires rehearsal and independent review before readiness; "
            "this is the pre-gate draft."
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(lesson, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"projected anonymous candidate: {args.output}")
    print(f"candidate sha256: {sha256(args.output)}")
    print(f"pixel review sha256: {pixel_sha}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
