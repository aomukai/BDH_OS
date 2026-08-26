"""Append-only bridge from Codex ImageGen outputs into Campaign 36 Luna review.

The built-in ImageGen tool is intentionally invoked by Codex one asset at a time.  This
module does not call an image API.  It freezes the chosen exhausted Flux assignment,
normalizes the generated bitmap to the corpus contract, records prompt and provenance,
and runs the same mechanical/Luna gate used for Flux attempts.  Three rejected provider
attempts route the assignment to local Gemma prompt brainstorming and human selection;
they never authorize a blind fourth attempt.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import Any

from PIL import Image, ImageOps

from image_registry.campaign36_flux_streaming_luna import (
    append_jsonl,
    assignment_identity,
    effective_visible_text_note,
    effective_visible_text_policy,
    load_jsonl,
    review_one,
)


SCHEMA_VERSION = "ninereeds_campaign36_imagegen_fallback_v1"
MAX_PROVIDER_ATTEMPTS = 3
POST_CAP_ROUTE = "gemma_prompt_brainstorm_then_new_three_attempt_cycle"
DEFAULT_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/flux-specialist-v1"
)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def source_attempts(streaming_root: Path) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    incoming = streaming_root / "incoming"
    for ledger in sorted(incoming.glob("generation-shard-*.jsonl")):
        for row in load_jsonl(ledger, tolerate_partial_tail=True):
            row = {**row, "generation_attempt": 1}
            rows[f"{assignment_identity(row)}-a01"] = row
    for ledger in sorted((incoming / "recommissioned").glob("recommission-*.jsonl")):
        for row in load_jsonl(ledger, tolerate_partial_tail=True):
            rows[
                f"{assignment_identity(row)}-a{int(row.get('generation_attempt', 1)):02d}"
            ] = row
    return rows


def exhausted_assignments(streaming_root: Path) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(streaming_root / "decisions.jsonl"):
        assignment = row["assignment_id"]
        if assignment not in latest or row["generation_attempt"] > latest[assignment]["generation_attempt"]:
            latest[assignment] = row
    return sorted(
        (
            row
            for row in latest.values()
            if row["verdict"] == "recommission" and int(row["generation_attempt"]) >= 3
        ),
        key=lambda row: row["assignment_id"],
    )


def completed_assignments(output_root: Path) -> set[str]:
    accepted = {
        row["assignment_id"]
        for row in load_jsonl(output_root / "decisions.jsonl")
        if row["verdict"] == "accepted"
    }
    accepted.update(
        row["assignment_id"]
        for row in load_jsonl(
            output_root / "policy-recoveries.jsonl", tolerate_partial_tail=True
        )
        if row.get("verdict") == "accepted"
    )
    return accepted


def superseded_assignments(output_root: Path) -> set[str]:
    """Assignments invalidated by a later frozen curriculum/lexicon contract."""
    return {
        str(row["assignment_id"])
        for row in load_jsonl(
            output_root / "superseded-assignments.jsonl", tolerate_partial_tail=True
        )
    }


def provider_attempts(output_root: Path) -> dict[str, int]:
    """Return the highest recorded built-in ImageGen attempt per assignment."""
    attempts: dict[str, int] = {}
    for row in load_jsonl(output_root / "imports.jsonl"):
        assignment = row["assignment_id"]
        attempts[assignment] = max(attempts.get(assignment, 0), int(row["provider_attempt"]))
    # A provider call still consumes an attempt when it fails before import.  Counting
    # terminal headless events prevents a safety-blocked or otherwise poisoned job
    # from being reclaimed forever with the same attempt number.
    for row in load_jsonl(output_root / "headless-jobs.jsonl", tolerate_partial_tail=True):
        if row.get("status") not in {
            "generation_failed", "generated", "reviewed", "import_failed",
        }:
            continue
        assignment = row["assignment_id"]
        attempts[assignment] = max(
            attempts.get(assignment, 0), int(row["provider_attempt"])
        )
    return attempts


def brainstorms(output_root: Path) -> dict[tuple[str, int], dict[str, Any]]:
    return {
        (row["assignment_id"], int(row["after_attempt"])): row
        for row in load_jsonl(output_root / "brainstorms.jsonl", tolerate_partial_tail=True)
    }


def representation_overrides(output_root: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(output_root / "representation-overrides.jsonl", tolerate_partial_tail=True):
        latest[row["assignment_id"]] = row
    return latest


def active_override(
    output_root: Path, assignment: str, recorded_attempts: int,
    overrides_by_assignment: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    if overrides_by_assignment is None:
        overrides_by_assignment = representation_overrides(output_root)
    override = overrides_by_assignment.get(assignment)
    if not override:
        return None
    after = int(override["after_attempt"])
    allowed = int(override.get("allowed_attempts", MAX_PROVIDER_ATTEMPTS))
    return override if after <= recorded_attempts < after + allowed else None


def brainstorm_state(
    output_root: Path, assignment: str, recorded_attempts: int,
    records_by_cycle: dict[tuple[str, int], dict[str, Any]] | None = None,
) -> tuple[dict[str, Any] | None, int | None]:
    """Return the active Gemma brainstorm or the attempt count after which one is due.

    The initial prompt receives three attempts.  Every Gemma idea then receives its own
    three attempts, so a five-idea brainstorm authorizes fifteen recovery generations.
    """
    if recorded_attempts < MAX_PROVIDER_ATTEMPTS:
        return None, None
    if records_by_cycle is None:
        records_by_cycle = brainstorms(output_root)
    records = [
        row for (candidate, after), row in records_by_cycle.items()
        if candidate == assignment and after <= recorded_attempts
    ]
    if not records:
        return None, MAX_PROVIDER_ATTEMPTS
    latest = max(records, key=lambda row: int(row["after_attempt"]))
    ideas = latest.get("ideas") or []
    if not ideas:
        return None, -1
    authorized_until = int(latest["after_attempt"]) + MAX_PROVIDER_ATTEMPTS * len(ideas)
    if recorded_attempts >= authorized_until:
        return None, -1
    return latest, None


def prompt_for(source: dict[str, Any], decision: dict[str, Any]) -> str:
    evidence = source.get("evidence_by_concept") or {}
    words = list(source.get("words") or source["concept_ids"])
    targets = []
    for index, concept_id in enumerate(source["concept_ids"]):
        word = words[index] if index < len(words) else concept_id
        targets.append(f'- "{word}": {evidence.get(concept_id, "direct visible evidence")}')
    correction = decision.get("recommission_instruction") or "Make every target direct and unambiguous."
    if correction.strip().lower() == "none":
        correction = "Make every target direct, salient, and unambiguous."
    text_policy = effective_visible_text_policy(source)
    text_instruction = (
        "Required in-scene writing: include the exact writing requested by the teaching "
        f"contract and render it accurately and legibly. {effective_visible_text_note(source)}"
        if text_policy == "required_evidence" else
        "Visible writing is not required; avoid labels, explanatory writing, and pseudo-text."
    )
    return "\n".join(
        [
            "Use case: scientific-educational",
            "Asset type: visual-language foundation training image",
            "Primary request: Create one clean educational image that teaches the exact target concepts below without relying on a caption.",
            "Teaching targets:",
            *targets,
            f"Required correction after three rejected attempts: {correction}",
            "Style/medium: natural photorealistic educational photograph unless the teaching evidence inherently requires a clean diagrammatic representation.",
            "Composition/framing: one coherent scene; make every required subject, action, property, and relation prominent and immediately readable.",
            "Constraints: preserve every teaching claim exactly; coherent anatomy, objects, scale, perspective, and spatial relations; no unrelated objects.",
            text_instruction,
            "Avoid: unrelated writing, logos, watermarks, decorative borders, UI, and accidental collage panels.",
        ]
    )


def select_next(
    root: Path, assignment: str | None, current_provider_attempt: int | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    streaming = root / "streaming-luna"
    output = root / "imagegen-v1"
    exhausted = exhausted_assignments(streaming)
    done = completed_assignments(output)
    attempts_by_assignment = provider_attempts(output)
    brainstorm_by_cycle = brainstorms(output)
    overrides_by_assignment = representation_overrides(output)
    if assignment:
        decision = next((row for row in exhausted if row["assignment_id"] == assignment), None)
        if decision is None:
            raise SystemExit(f"assignment is not currently exhausted: {assignment}")
        if assignment in done:
            raise SystemExit(f"assignment is already accepted: {assignment}")
        prior_attempts = attempts_by_assignment.get(assignment, 0)
        # During import the current generation is already terminal in the headless
        # ledger, but it has not been reviewed yet.  Apply post-cap gates only to
        # attempts that preceded the image currently entering review.
        if current_provider_attempt is not None:
            prior_attempts = min(prior_attempts, current_provider_attempt - 1)
        active_brainstorm, required_after = brainstorm_state(
            output, assignment, prior_attempts, brainstorm_by_cycle
        )
        override = active_override(
            output, assignment, prior_attempts, overrides_by_assignment
        )
        if required_after is not None and override is None:
            if required_after == -1:
                raise SystemExit(
                    f"assignment exhausted its Gemma recovery prompts and requires manual "
                    f"representation triage: {assignment}"
                )
            else:
                brainstorm = brainstorm_by_cycle.get((assignment, required_after))
                if not brainstorm or not brainstorm.get("ideas"):
                    raise SystemExit(
                        f"assignment requires a successful local Gemma brainstorm after "
                        f"ImageGen attempt {required_after}: {assignment}"
                    )
    else:
        decision = next(
            (
                row
                for row in exhausted
                if row["assignment_id"] not in done
                and (
                    brainstorm_state(
                        output, row["assignment_id"],
                        attempts_by_assignment.get(row["assignment_id"], 0),
                        brainstorm_by_cycle,
                    )[1] is None
                    or active_override(
                        output, row["assignment_id"],
                        attempts_by_assignment.get(row["assignment_id"], 0),
                        overrides_by_assignment,
                    ) is not None
                )
            ),
            None,
        )
        if decision is None:
            raise SystemExit("no exhausted assignments are currently eligible for ImageGen")
    attempts = source_attempts(streaming)
    source = attempts[decision["attempt_id"]]
    return source, decision


def command_next(args: argparse.Namespace) -> int:
    source, decision = select_next(args.root, args.assignment)
    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "assignment_id": decision["assignment_id"],
                "flux_attempt_id": decision["attempt_id"],
                "concept_ids": source["concept_ids"],
                "words": source.get("words", source["concept_ids"]),
                "prompt": prompt_for(source, decision),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def normalize_image(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image.load()
        normalized = ImageOps.fit(
            image.convert("RGB"), (512, 384), method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        with tempfile.NamedTemporaryFile(suffix=".png", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
        try:
            normalized.save(temporary, format="PNG", optimize=True)
            temporary.replace(target)
        finally:
            temporary.unlink(missing_ok=True)


def command_import_review(args: argparse.Namespace) -> int:
    if args.provider_attempt < 1:
        raise SystemExit("provider attempt must be positive")
    source, decision = select_next(
        args.root, args.assignment, current_provider_attempt=args.provider_attempt
    )
    output = args.root / "imagegen-v1"
    images = output / "images"
    assignment = decision["assignment_id"]
    target = images / f"{assignment}-ig{args.provider_attempt:02d}.png"
    normalize_image(args.image, target)
    prompt = args.prompt_file.read_text(encoding="utf-8") if args.prompt_file else prompt_for(source, decision)
    override = active_override(
        output, assignment, provider_attempts(output).get(assignment, 0)
    )
    if override:
        source = {
            **source,
            "evidence_by_concept": override["evidence_by_concept"],
            "words": override.get("words") or source.get("words"),
            "grounding_mode": override.get(
                "grounding_mode", source.get("grounding_mode", "direct")
            ),
            "visible_text_policy": override.get("visible_text_policy", "reject"),
            "visible_text_note": override.get("visible_text_note"),
        }
    row = {
        **source,
        "schema_version": SCHEMA_VERSION,
        "generation_attempt": 3 + args.provider_attempt,
        "provider_attempt": args.provider_attempt,
        "provider": "codex-built-in-imagegen",
        "source_flux_attempt_id": decision["attempt_id"],
        "source_flux_sha256": decision["sha256"],
        "prompt": prompt,
        "representation_override": override,
        "width": 512,
        "height": 384,
        "local_path": str(target),
        "sha256": sha256(target),
    }
    review_args = SimpleNamespace(codex=args.codex, model=args.model, timeout=args.timeout)
    verdict = review_one(row, target, review_args)
    import_record = {
        "schema_version": SCHEMA_VERSION,
        "assignment_id": assignment,
        "provider_attempt": args.provider_attempt,
        "source_image": str(args.image),
        "normalized_image": str(target),
        "sha256": row["sha256"],
        "prompt": prompt,
        "flux_exhaustion_decision": decision,
        "review_verdict": verdict["verdict"],
    }
    append_jsonl(output / "imports.jsonl", import_record)
    append_jsonl(output / "generation.jsonl", row)
    append_jsonl(output / "decisions.jsonl", verdict)
    print(json.dumps(import_record, ensure_ascii=False, indent=2))
    return 0 if verdict["verdict"] == "accepted" else 2


def command_summary(args: argparse.Namespace) -> int:
    output = args.root / "imagegen-v1"
    exhausted = exhausted_assignments(args.root / "streaming-luna")
    completed = completed_assignments(output)
    superseded = superseded_assignments(output)
    imports = load_jsonl(output / "imports.jsonl")
    attempts_by_assignment = provider_attempts(output)
    brainstorm_by_cycle = brainstorms(output)
    overrides_by_assignment = representation_overrides(output)
    exhausted_ids = {row["assignment_id"] for row in exhausted}
    remaining_required = exhausted_ids - completed - superseded
    latest: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(output / "decisions.jsonl"):
        if (
            row["assignment_id"] not in latest
            or row["generation_attempt"] > latest[row["assignment_id"]]["generation_attempt"]
        ):
            latest[row["assignment_id"]] = row
    decisions = list(latest.values())
    print(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "currently_exhausted_flux_assignments": len(exhausted),
                "imagegen_imports": len(imports),
                "accepted_imagegen": sum(row["verdict"] == "accepted" for row in decisions),
                "accepted_policy_recoveries": len({
                    row["assignment_id"]
                    for row in load_jsonl(
                        output / "policy-recoveries.jsonl", tolerate_partial_tail=True
                    )
                    if row.get("verdict") == "accepted"
                }),
                "accepted_total": len(completed),
                "superseded_exhausted_assignments": len(exhausted_ids & superseded),
                "remaining_exhausted_assignments": len(remaining_required),
                "latest_imagegen_rejections": sum(
                    row["verdict"] != "accepted"
                    and row["assignment_id"] in remaining_required
                    for row in decisions
                ),
                "manual_representation_triage": sum(
                    assignment in remaining_required
                    and brainstorm_state(
                        output, assignment, attempt, brainstorm_by_cycle
                    )[1] == -1
                    and active_override(
                        output, assignment, attempt, overrides_by_assignment
                    ) is None
                    for assignment, attempt in attempts_by_assignment.items()
                ),
                "gemma_brainstorm_pending": sum(
                    assignment in remaining_required
                    and (state := brainstorm_state(
                        output, assignment, attempt, brainstorm_by_cycle
                    ))[1] is not None
                    and state[1] != -1
                    and brainstorm_by_cycle.get((assignment, state[1])) is None
                    for assignment, attempt in attempts_by_assignment.items()
                ),
                "attempts_per_prompt_cycle": MAX_PROVIDER_ATTEMPTS,
                "post_cap_route": POST_CAP_ROUTE,
            },
            indent=2,
        )
    )
    return 0


def command_resolve(args: argparse.Namespace) -> int:
    output = args.root / "imagegen-v1"
    attempts = provider_attempts(output)
    recorded = attempts.get(args.assignment, 0)
    exhausted_ids = {
        row["assignment_id"] for row in exhausted_assignments(args.root / "streaming-luna")
    }
    if args.assignment not in exhausted_ids:
        raise SystemExit(f"assignment is not in the exhausted Flux set: {args.assignment}")
    evidence = json.loads(args.evidence_json)
    if not isinstance(evidence, dict) or not evidence:
        raise SystemExit("evidence JSON must be a non-empty object")
    row = {
        "schema_version": SCHEMA_VERSION,
        "assignment_id": args.assignment,
        "after_attempt": recorded,
        "allowed_attempts": MAX_PROVIDER_ATTEMPTS,
        "evidence_by_concept": evidence,
        "words": json.loads(args.words_json) if args.words_json else None,
        "grounding_mode": args.grounding_mode,
        "representation_prompt": args.representation_prompt,
        "reason": args.reason,
        "authority": "user-approved-manual-representation-triage",
        "visible_text_policy": args.visible_text_policy,
        "visible_text_note": args.visible_text_note,
    }
    append_jsonl(output / "representation-overrides.jsonl", row)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    subparsers = parser.add_subparsers(dest="command", required=True)
    next_parser = subparsers.add_parser("next")
    next_parser.add_argument("--assignment")
    next_parser.set_defaults(func=command_next)
    import_parser = subparsers.add_parser("import-review")
    import_parser.add_argument("--assignment", required=True)
    import_parser.add_argument("--image", type=Path, required=True)
    import_parser.add_argument("--prompt-file", type=Path)
    import_parser.add_argument("--provider-attempt", type=int, default=1)
    import_parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    import_parser.add_argument("--model", default="gpt-5.6-luna")
    import_parser.add_argument("--timeout", type=int, default=600)
    import_parser.set_defaults(func=command_import_review)
    summary_parser = subparsers.add_parser("summary")
    summary_parser.set_defaults(func=command_summary)
    resolve_parser = subparsers.add_parser("resolve")
    resolve_parser.add_argument("--assignment", required=True)
    resolve_parser.add_argument("--evidence-json", required=True)
    resolve_parser.add_argument("--words-json")
    resolve_parser.add_argument(
        "--grounding-mode", choices=("direct", "contextual_transfer"), default="direct"
    )
    resolve_parser.add_argument("--representation-prompt", required=True)
    resolve_parser.add_argument("--reason", required=True)
    resolve_parser.add_argument(
        "--visible-text-policy", choices=("reject", "required_evidence"), default="reject"
    )
    resolve_parser.add_argument("--visible-text-note")
    resolve_parser.set_defaults(func=command_resolve)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
