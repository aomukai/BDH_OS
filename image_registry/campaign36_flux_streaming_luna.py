"""Stream completed Flux images through mechanical checks and Luna review.

This is a provisional, append-only gate.  It does not mutate the image registry or
replace the final exact-coverage reconciliation.  Rejected attempts become bounded
recommission requests; accepted attempts are frozen by identity and SHA-256.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any, Iterable

from PIL import Image, ImageOps

from image_benchmark.luna_watermark_worker import structured_codex_review


SCHEMA_VERSION = "ninereeds_campaign36_flux_streaming_luna_v1"
RETRY_SCHEMA_VERSION = "ninereeds_campaign36_flux_recommission_request_v1"
TEXT_REQUIRED_EVIDENCE = re.compile(
    r"\b(?:written|text|word|phrase|sentence|label(?:ed|led)?|reads?|title|"
    r"spelling|apostrophe|equation|formula|speech bubble)\b",
    re.IGNORECASE,
)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def load_jsonl(path: Path, *, tolerate_partial_tail: bool = False) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            if tolerate_partial_tail and index == len(lines) - 1:
                continue
            raise
    return rows


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def effective_visible_text_policy(row: dict[str, Any]) -> str:
    """Return the explicit policy or infer it from an explicitly textual contract.

    The default remains rejection.  Inference is deliberately narrow: it applies only
    when the frozen evidence itself requests writing, a label, a title, a formula, or
    another named textual feature.  Ordinary incidental writing remains disallowed.
    """
    explicit = row.get("visible_text_policy")
    if explicit in {"reject", "required_evidence"}:
        return explicit
    evidence = row.get("evidence_by_concept") or {}
    return (
        "required_evidence"
        if any(TEXT_REQUIRED_EVIDENCE.search(str(claim)) for claim in evidence.values())
        else "reject"
    )


def effective_visible_text_note(row: dict[str, Any]) -> str:
    if row.get("visible_text_note"):
        return str(row["visible_text_note"])
    evidence = row.get("evidence_by_concept") or {}
    textual = [str(claim) for claim in evidence.values() if TEXT_REQUIRED_EVIDENCE.search(str(claim))]
    return " | ".join(textual) or "verify all requested writing exactly"


def attempt_identity(row: dict[str, Any]) -> str:
    brief = str(row["production_brief_id"])
    variant = int(row["variant_index"])
    attempt = int(row.get("generation_attempt", 1))
    return f"{brief}-v{variant:02d}-a{attempt:02d}"


def assignment_identity(row: dict[str, Any]) -> str:
    return f"{row['production_brief_id']}-v{int(row['variant_index']):02d}"


def mechanical_check(path: Path, row: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    actual_hash = digest(path)
    if actual_hash != row["sha256"]:
        reasons.append("sha256_mismatch")
    image_format = image_mode = perceptual_hash = None
    width = height = None
    try:
        with Image.open(path) as image:
            image.load()
            image_format = image.format
            image_mode = image.mode
            width, height = image.size
            if image_format != "PNG":
                reasons.append("unexpected_format")
            if (width, height) != (int(row["width"]), int(row["height"])):
                reasons.append("dimension_mismatch")
            if min(width, height) < 256:
                reasons.append("small_dimension")
            gray = ImageOps.fit(image.convert("L"), (8, 8))
            pixels = list(gray.getdata())
            mean = sum(pixels) / len(pixels)
            bits = sum((value >= mean) << index for index, value in enumerate(pixels))
            perceptual_hash = f"{bits:016x}"
    except Exception as exc:
        reasons.append(f"decode_error:{type(exc).__name__}")
    return {
        "passed": not reasons,
        "reasons": reasons,
        "sha256": actual_hash,
        "format": image_format,
        "mode": image_mode,
        "width": width,
        "height": height,
        "perceptual_hash": perceptual_hash,
    }


def schema_for(row: dict[str, Any]) -> dict[str, Any]:
    ids = list(row["concept_ids"])
    return {
        "type": "object",
        "properties": {
            "admission": {"type": "string", "enum": ["usable", "unusable", "uncertain"]},
            "visible_text": {"type": "boolean"},
            "watermark": {"type": "boolean"},
            "quality_flags": {"type": "array", "items": {"type": "string"}},
            "literal_caption": {"type": "string", "minLength": 1, "maxLength": 500},
            "reason": {"type": "string", "minLength": 1, "maxLength": 500},
            "targets": {
                "type": "array", "minItems": len(ids), "maxItems": len(ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "concept_id": {"type": "string", "enum": ids},
                        "verdict": {"type": "string", "enum": ["present", "absent", "uncertain"]},
                        "evidence": {"type": "string", "minLength": 1, "maxLength": 500},
                    },
                    "required": ["concept_id", "verdict", "evidence"],
                    "additionalProperties": False,
                },
            },
            "uncertainties": {"type": "array", "items": {"type": "string"}},
            "recommission_instruction": {"type": "string", "minLength": 1, "maxLength": 600},
        },
        "required": [
            "admission", "visible_text", "watermark", "quality_flags", "literal_caption",
            "reason", "targets", "uncertainties", "recommission_instruction",
        ],
        "additionalProperties": False,
    }


def prompt_for(row: dict[str, Any]) -> str:
    targets = []
    evidence = row.get("evidence_by_concept") or {}
    words = list(row.get("words") or row["concept_ids"])
    for index, concept_id in enumerate(row["concept_ids"]):
        word = words[index] if index < len(words) else concept_id
        targets.append(f"- {concept_id} ({word}): {evidence.get(concept_id, 'direct visible evidence')}")
    grounding_mode = row.get("grounding_mode", "direct")
    if grounding_mode == "contextual_transfer":
        grounding_instruction = (
            "This is explicitly a contextual transfer anchor that will be paired with its word "
            "and caption during teaching. Do not demand that it function as a standalone visual "
            "dictionary definition. Require the stated artifact, scene, or relation to be plainly "
            "visible and relevant, and reject a generic or misleading association."
        )
    else:
        grounding_instruction = (
            "This is direct grounding. Each target must be direct, salient, and unambiguous "
            "without relying on outside context."
        )
    visible_text_policy = effective_visible_text_policy(row)
    if visible_text_policy == "required_evidence":
        visible_text_instruction = (
            "Visible writing is required teaching evidence for this assignment. Do not reject "
            "it merely for being present. Accept it only when the requested scripts or strings "
            "are accurate, legible, and directly support the target; reject malformed, incorrect, "
            "or unrelated writing. Required-text note: "
            + effective_visible_text_note(row)
        )
    else:
        visible_text_instruction = (
            "Visible writing is not required evidence, but its presence is not an automatic "
            "failure. Accept natural in-scene writing when it is coherent, correctly spelled "
            "where legible, relevant or harmless, and not misleading. Reject malformed "
            "pseudo-writing, incorrect labels, unwanted overlays, logos that create a material "
            "problem, or writing that weakens or substitutes for the visual teaching evidence."
        )
    answer_text_rule = (
        "Do not reject accurate required in-scene writing merely because it spells or names "
        "the target; judge it only within the explicitly declared artifact or scene."
        if visible_text_policy == "required_evidence" else
        "Reject text that merely spells the answer instead of depicting the target."
    )
    return """Inspect this generated educational image using only its visible pixels.

It is intended to teach these exact concepts without a caption:
{targets}

{grounding_instruction}

For each concept, report present only if the intended evidence is direct, salient, and
unambiguous. Reject mere association, a related scene, hidden state, or an imagined before/after
event. {answer_text_rule} Also inspect anatomy, object integrity, spatial coherence,
duplication, malformed details, blur, collage structure, borders, visible writing, logos, and
watermarks. A small stylistic imperfection is not by itself disqualifying, but anything that can
mis-teach the concept is. `recommission_instruction` must be a concise concrete correction if
anything fails; if everything passes, write `none`.

{visible_text_instruction}

Return exactly the required JSON.
""".format(
    targets="\n".join(targets), grounding_instruction=grounding_instruction,
    answer_text_rule=answer_text_rule,
    visible_text_instruction=visible_text_instruction,
)


def validate_luna(row: dict[str, Any], result: dict[str, Any]) -> None:
    expected = list(row["concept_ids"])
    observed = [item["concept_id"] for item in result["targets"]]
    if len(observed) != len(set(observed)) or set(observed) != set(expected):
        raise ValueError("Luna changed the exact concept partition")


def derive_verdict(result: dict[str, Any], row: dict[str, Any] | None = None) -> tuple[str, list[str]]:
    reasons: list[str] = []
    if result["admission"] != "usable":
        reasons.append(f"admission:{result['admission']}")
    # Visible text is an observation, not an independent veto. Luna has already inspected
    # spelling, relevance, overlays, labels, and whether text improperly substitutes for the
    # requested evidence; material problems appear in admission, quality flags, target
    # verdicts, uncertainties, or watermark.
    if result["watermark"]:
        reasons.append("watermark")
    reasons.extend(f"quality:{flag}" for flag in result["quality_flags"])
    reasons.extend(
        f"target:{item['concept_id']}:{item['verdict']}"
        for item in result["targets"] if item["verdict"] != "present"
    )
    reasons.extend(f"uncertain:{item}" for item in result["uncertainties"])
    return ("accepted", []) if not reasons else ("recommission", reasons)


def review_one(row: dict[str, Any], image: Path, args: argparse.Namespace) -> dict[str, Any]:
    mechanical = mechanical_check(image, row)
    if not mechanical["passed"]:
        return {
            "schema_version": SCHEMA_VERSION,
            "attempt_id": attempt_identity(row), "assignment_id": assignment_identity(row),
            "production_brief_id": row["production_brief_id"],
            "variant_index": int(row["variant_index"]),
            "generation_attempt": int(row.get("generation_attempt", 1)),
            "sha256": row["sha256"], "local_path": str(image),
            "mechanical": mechanical, "verdict": "recommission",
            "failure_reasons": mechanical["reasons"],
            "recommission_instruction": "Regenerate a clean decodable image at the required dimensions.",
            "review_backend": "mechanical", "review_model": None,
        }
    result, transcript = structured_codex_review(
        image, executable=args.codex, model=args.model, timeout=args.timeout,
        prompt=prompt_for(row), schema=schema_for(row),
        temporary_prefix="ninereeds-c36-flux-luna-",
    )
    validate_luna(row, result)
    verdict, reasons = derive_verdict(result, row)
    return {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": attempt_identity(row), "assignment_id": assignment_identity(row),
        "production_brief_id": row["production_brief_id"],
        "variant_index": int(row["variant_index"]),
        "generation_attempt": int(row.get("generation_attempt", 1)),
        "concept_ids": row["concept_ids"], "sha256": row["sha256"],
        "local_path": str(image), "mechanical": mechanical,
        "verdict": verdict, "failure_reasons": reasons,
        "recommission_instruction": result["recommission_instruction"],
        "luna_result": result, "review_backend": "codex",
        "review_model": args.model, "transcript": transcript,
    }


def retry_request(row: dict[str, Any], verdict: dict[str, Any], max_attempts: int) -> dict[str, Any] | None:
    attempt = int(row.get("generation_attempt", 1))
    if verdict["verdict"] == "accepted" or attempt >= max_attempts:
        return None
    request = {
        "schema_version": RETRY_SCHEMA_VERSION,
        "request_id": f"{assignment_identity(row)}-a{attempt + 1:02d}",
        "production_brief_id": row["production_brief_id"],
        "variant_index": int(row["variant_index"]),
        "generation_attempt": attempt + 1,
        "concept_ids": row["concept_ids"], "words": row.get("words", row["concept_ids"]),
        "evidence_by_concept": row.get("evidence_by_concept", {}),
        "flux_prompt_template": row.get("flux_prompt_template") or row["prompt"],
        "failure_reasons": verdict["failure_reasons"],
        "recommission_instruction": verdict["recommission_instruction"],
        "rejected_sha256": row["sha256"],
        "seed_namespace": "campaign36-flux-v1-recommission",
    }
    policy = effective_visible_text_policy(row)
    if policy == "required_evidence":
        request["visible_text_policy"] = policy
        request["visible_text_note"] = effective_visible_text_note(row)
    return request


def sync_remote(args: argparse.Namespace) -> None:
    args.incoming.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "rsync", "-a", "--partial", f"{args.remote}:{args.remote_root}/generated/",
        f"{args.incoming}/",
    ], check=True)
    subprocess.run([
        "rsync", "-a", "--partial", f"{args.remote}:{args.remote_root}/recommissioned/",
        f"{args.incoming}/recommissioned/",
    ], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def upload_requests(args: argparse.Namespace, requests_path: Path) -> None:
    if not requests_path.is_file():
        return
    subprocess.run([
        "rsync", "-a", "--partial", str(requests_path),
        f"{args.remote}:{args.remote_root}/recommission-requests.jsonl",
    ], check=True)


def source_rows(args: argparse.Namespace) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for ledger in sorted(args.incoming.glob("generation-shard-*.jsonl")):
        for row in load_jsonl(ledger, tolerate_partial_tail=True):
            row = {**row, "generation_attempt": 1}
            rows[attempt_identity(row)] = row
    for ledger in sorted((args.incoming / "recommissioned").glob("recommission-*.jsonl")):
        for row in load_jsonl(ledger, tolerate_partial_tail=True):
            rows[attempt_identity(row)] = row
    return rows


def image_for(row: dict[str, Any], incoming: Path) -> Path:
    if int(row.get("generation_attempt", 1)) == 1:
        return incoming / f"{assignment_identity(row)}.png"
    return incoming / "recommissioned" / f"{attempt_identity(row)}.png"


def summarize(args: argparse.Namespace, rows: dict[str, dict[str, Any]], decisions: dict[str, dict[str, Any]]) -> dict[str, Any]:
    latest: dict[str, dict[str, Any]] = {}
    for result in decisions.values():
        assignment = result["assignment_id"]
        if assignment not in latest or result["generation_attempt"] > latest[assignment]["generation_attempt"]:
            latest[assignment] = result
    summary = {
        "schema_version": SCHEMA_VERSION,
        "expected_initial_images": args.expected_images,
        "observed_attempts": len(rows), "reviewed_attempts": len(decisions),
        "accepted_assignments": sum(row["verdict"] == "accepted" for row in latest.values()),
        "pending_assignments": args.expected_images - len(latest),
        "recommission_assignments": sum(row["verdict"] == "recommission" for row in latest.values()),
        "exhausted_assignments": sum(
            row["verdict"] == "recommission" and row["generation_attempt"] >= args.max_generation_attempts
            for row in latest.values()
        ),
        "model": args.model,
        "status": "streaming_review_active",
    }
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--remote", default="ninereeds-trainbox")
    parser.add_argument("--remote-root", required=True)
    parser.add_argument("--incoming", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-images", type=int, required=True)
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--poll-seconds", type=float, default=30)
    parser.add_argument("--max-generation-attempts", type=int, default=3)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.expected_images < 1 or not 1 <= args.workers <= 32:
        raise ValueError("invalid expected image or worker count")
    args.output.mkdir(parents=True, exist_ok=True)
    decisions_path = args.output / "decisions.jsonl"
    requests_path = args.output / "recommission-requests.jsonl"
    while True:
        sync_remote(args)
        rows = source_rows(args)
        prior = {row["attempt_id"]: row for row in load_jsonl(decisions_path)}
        requested = {row["request_id"] for row in load_jsonl(requests_path)}
        # Recover a durable request if the process stopped after recording a
        # rejection but before appending/uploading its recommission request.
        for attempt_id, verdict in prior.items():
            source = rows.get(attempt_id)
            if source is None:
                continue
            request = retry_request(source, verdict, args.max_generation_attempts)
            if request is not None and request["request_id"] not in requested:
                append_jsonl(requests_path, request)
                requested.add(request["request_id"])
        upload_requests(args, requests_path)
        pending = [row for key, row in rows.items() if key not in prior and image_for(row, args.incoming).is_file()]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(review_one, row, image_for(row, args.incoming), args): row for row in pending}
            for completed, future in enumerate(as_completed(futures), 1):
                row = futures[future]
                try:
                    verdict = future.result()
                except Exception as exc:
                    print(f"review failed {attempt_identity(row)}: {type(exc).__name__}: {exc}", flush=True)
                    continue
                append_jsonl(decisions_path, verdict)
                prior[verdict["attempt_id"]] = verdict
                request = retry_request(row, verdict, args.max_generation_attempts)
                if request is not None and request["request_id"] not in requested:
                    append_jsonl(requests_path, request)
                    requested.add(request["request_id"])
                    if len(requested) % 20 == 0:
                        upload_requests(args, requests_path)
                print(
                    f"reviewed {completed}/{len(pending)} {verdict['attempt_id']} {verdict['verdict']}",
                    flush=True,
                )
        upload_requests(args, requests_path)
        summary = summarize(args, rows, prior)
        print(json.dumps(summary, sort_keys=True), flush=True)
        if args.once:
            return 0
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
