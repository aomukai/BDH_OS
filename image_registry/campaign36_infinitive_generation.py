"""Bounded image-remediation ladder for Campaign 36 infinitive labels.

Stages are intentionally explicit and append-only:

1. Flux first prompt
2. Flux same prompt, fresh seed
3. GPT Image first attempt
4. GPT Image second attempt
5. Flux revised prompt
6. GPT Image final attempt

Every candidate is independently reviewed by Codex Luna before admission.  The
controller never overwrites the frozen manifest; accepted rows are reconciled by
slot only after the ladder finishes.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from typing import Any, Iterable

from image_registry.campaign36_flux_streaming_luna import review_one
from image_registry.campaign36_headless_imagegen import generate_one
from image_registry.campaign36_imagegen_fallback import normalize_image


SCHEMA_VERSION = "ninereeds_campaign36_infinitive_generation_v1"
LABEL_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/infinitive-label-v1"
)
DEFAULT_QUEUE = LABEL_ROOT / "pixel-preflight-v1/generation-queue.jsonl"
DEFAULT_MANIFEST = LABEL_ROOT / "accepted-assets.jsonl"
DEFAULT_ROOT = LABEL_ROOT / "remediation-generation-v1"
DEFAULT_STORE = Path("/media/aomukai/FILES/Ninereeds/image-corpus")
STAGES = (
    "flux_1", "flux_2", "gpt_image_1", "gpt_image_2", "flux_better", "gpt_image_3",
    "human_gpt_1",
    "human_flux_1",
)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def atomic_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def append_locked(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        fcntl.flock(stream, fcntl.LOCK_EX)
        stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
        fcntl.flock(stream, fcntl.LOCK_UN)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, text=True, capture_output=True, check=check)


def source_by_slot(path: Path) -> dict[str, dict[str, Any]]:
    rows = load_jsonl(path)
    result = {str(row["slot_id"]): row for row in rows}
    if len(result) != len(rows):
        raise ValueError("generation queue repeats a slot")
    return result


def prompts_by_slot(path: Path) -> dict[str, str]:
    rows = load_jsonl(path)
    result = {str(row["slot_id"]): str(row["prompt"]).strip() for row in rows}
    if len(result) != len(rows) or any(not prompt for prompt in result.values()):
        raise ValueError("prompt ledger contains duplicate slots or empty prompts")
    return result


def accepted_by_slot(root: Path) -> dict[str, dict[str, Any]]:
    accepted: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(root / "accepted.jsonl"):
        accepted[str(row["slot_id"])] = row
    return accepted


def attempts_by_key(root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    attempts: dict[tuple[str, str], dict[str, Any]] = {}
    for row in load_jsonl(root / "attempts.jsonl"):
        attempts[(str(row["slot_id"]), str(row["stage"]))] = row
    return attempts


def eligible_slots(root: Path, queue: dict[str, dict[str, Any]], stage: str) -> list[str]:
    if stage not in STAGES:
        raise ValueError(f"unknown stage: {stage}")
    index = STAGES.index(stage)
    accepted = accepted_by_slot(root)
    attempts = attempts_by_key(root)
    eligible = []
    for slot in sorted(queue):
        if slot in accepted or (slot, stage) in attempts:
            continue
        if index and (slot, STAGES[index - 1]) not in attempts:
            continue
        eligible.append(slot)
    return eligible


def request_id(slot: str, stage: str) -> str:
    return f"c36-inf-{slot}-{stage.replace('_', '-')}"


def dispatch_flux(args: argparse.Namespace) -> dict[str, Any]:
    if not args.prompts:
        raise ValueError("--prompts is required")
    queue = source_by_slot(args.queue)
    prompts = prompts_by_slot(args.prompts)
    eligible = eligible_slots(args.root, queue, args.stage)
    missing = sorted(set(eligible) - set(prompts))
    if missing:
        raise ValueError(f"prompt ledger is missing eligible slots: {missing[:5]}")
    dispatch_rows = []
    for position, slot in enumerate(eligible):
        gpu = position % 2
        item = queue[slot]
        identifier = request_id(slot, args.stage)
        request = {
            "schema_version": SCHEMA_VERSION,
            "request_id": identifier,
            "slot_id": slot,
            "word": item["word"],
            "concept_id": item["concept_id"],
            "teaching_sense": item["teaching_sense"],
            "ordinal": int(item["ordinal"]),
            "prompt_cycle": STAGES.index(args.stage) + 1,
            "prompt": prompts[slot],
            "requested_count": 1,
            "attempts_per_needed": 1,
        }
        local = args.root / "flux-spool" / args.stage / f"gpu{gpu}" / "requests"
        local.mkdir(parents=True, exist_ok=True)
        atomic_json(local / f"{identifier}.json", request)
        dispatch_rows.append({"slot_id": slot, "stage": args.stage, "gpu": gpu, **request})
    atomic_jsonl(args.root / "flux-spool" / args.stage / "dispatch.jsonl", dispatch_rows)
    for gpu in (0, 1):
        local = args.root / "flux-spool" / args.stage / f"gpu{gpu}" / "requests"
        if not local.is_dir():
            continue
        run(["ssh", args.remote, "mkdir", "-p", f"{args.remote_root}/gpu{gpu}/requests"])
        run([
            "rsync", "-a", "--partial", f"{local}/",
            f"{args.remote}:{args.remote_root}/gpu{gpu}/requests/",
        ])
    summary = {"stage": args.stage, "dispatched": len(dispatch_rows), "gpu0": sum(row["gpu"] == 0 for row in dispatch_rows), "gpu1": sum(row["gpu"] == 1 for row in dispatch_rows)}
    atomic_json(args.root / "flux-spool" / args.stage / "dispatch-summary.json", summary)
    return summary


def review_candidate(
    *,
    image: Path,
    item: dict[str, Any],
    stage: str,
    prompt: str,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], Path]:
    slot = str(item["slot_id"])
    normalized = args.root / "staging" / stage / f"{slot}.png"
    normalized.parent.mkdir(parents=True, exist_ok=True)
    normalize_image(image, normalized)
    sha256 = digest(normalized)
    row = {
        "assignment_id": request_id(slot, stage),
        "production_brief_id": request_id(slot, stage),
        "variant_index": 1,
        "generation_attempt": STAGES.index(stage) + 1,
        "concept_ids": [item["concept_id"]],
        "words": [item["word"]],
        "evidence_by_concept": {item["concept_id"]: item["teaching_sense"]},
        "grounding_mode": "direct",
        "visible_text_policy": "reject",
        "prompt": prompt,
        "local_path": str(normalized),
        "sha256": sha256,
        "width": 512,
        "height": 384,
    }
    verdict = review_one(
        row,
        normalized,
        SimpleNamespace(codex=args.codex, model=args.review_model, timeout=args.review_timeout),
    )
    return verdict, normalized


def record_review(
    *,
    item: dict[str, Any],
    stage: str,
    provider: str,
    prompt: str,
    verdict: dict[str, Any],
    normalized: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    slot = str(item["slot_id"])
    accepted = verdict["verdict"] == "accepted"
    attempt = {
        "schema_version": SCHEMA_VERSION,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "slot_id": slot,
        "ordinal": int(item["ordinal"]),
        "concept_id": item["concept_id"],
        "word": item["word"],
        "part_of_speech": item["part_of_speech"],
        "teaching_sense": item["teaching_sense"],
        "stage": stage,
        "provider": provider,
        "prompt": prompt,
        "sha256": digest(normalized),
        "local_path": str(normalized),
        "verdict": "accepted" if accepted else "rejected",
        "luna_review": verdict,
    }
    append_locked(args.root / "attempts.jsonl", attempt)
    if accepted:
        target = args.store / "blobs/ninereeds_campaign36_infinitive_remediation" / provider / f"{attempt['sha256']}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            partial = target.with_suffix(".png.partial")
            shutil.copyfile(normalized, partial)
            if digest(partial) != attempt["sha256"]:
                raise ValueError("accepted image copy failed hash validation")
            os.replace(partial, target)
        accepted_row = {**attempt, "local_path": str(target), "disposition": "accepted_luna_exact_sense"}
        append_locked(args.root / "accepted.jsonl", accepted_row)
    return attempt


def sync_flux_results(args: argparse.Namespace, dispatch: list[dict[str, Any]]) -> None:
    for gpu in (0, 1):
        local = args.root / "flux-spool" / args.stage / f"gpu{gpu}" / "results"
        local.mkdir(parents=True, exist_ok=True)
        run([
            "rsync", "-a", "--partial",
            f"{args.remote}:{args.remote_root}/gpu{gpu}/results/", f"{local}/",
        ], check=False)


def collect_flux(args: argparse.Namespace) -> dict[str, Any]:
    queue = source_by_slot(args.queue)
    dispatch_path = args.root / "flux-spool" / args.stage / "dispatch.jsonl"
    dispatch = load_jsonl(dispatch_path)
    sync_flux_results(args, dispatch)
    prior = attempts_by_key(args.root)
    ready = []
    pending = []
    for row in dispatch:
        key = (row["slot_id"], args.stage)
        if key in prior:
            continue
        result_path = args.root / "flux-spool" / args.stage / f"gpu{row['gpu']}" / "results" / f"{row['request_id']}.json"
        if result_path.is_file():
            ready.append((row, json.loads(result_path.read_text(encoding="utf-8"))))
        else:
            pending.append(row["slot_id"])

    def process(pair: tuple[dict[str, Any], dict[str, Any]]) -> dict[str, Any]:
        dispatch_row, result = pair
        item = queue[dispatch_row["slot_id"]]
        produced = result.get("produced") or []
        if not produced:
            synthetic = {
                "verdict": "recommission",
                "failure_reasons": ["generation_failed"],
                "recommission_instruction": "Generate a fresh direct image for the exact sense.",
                "review_backend": "generation",
                "review_model": None,
            }
            placeholder = args.root / "staging" / args.stage / f"{item['slot_id']}.failed"
            placeholder.parent.mkdir(parents=True, exist_ok=True)
            placeholder.write_bytes(b"generation failed")
            return record_review(item=item, stage=args.stage, provider="flux", prompt=dispatch_row["prompt"], verdict=synthetic, normalized=placeholder, args=args)
        candidate = produced[0]
        remote_path = str(candidate["remote_path"])
        local = args.root / "flux-spool" / args.stage / f"gpu{dispatch_row['gpu']}" / "images" / Path(remote_path).name
        local.parent.mkdir(parents=True, exist_ok=True)
        run(["rsync", "-a", "--partial", f"{args.remote}:{remote_path}", str(local)])
        verdict, normalized = review_candidate(image=local, item=item, stage=args.stage, prompt=candidate["prompt"], args=args)
        return record_review(item=item, stage=args.stage, provider="flux", prompt=candidate["prompt"], verdict=verdict, normalized=normalized, args=args)

    reviewed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, pair): pair[0]["slot_id"] for pair in ready}
        for index, future in enumerate(as_completed(futures), 1):
            row = future.result()
            reviewed.append(row)
            print(f"reviewed {index}/{len(ready)} {row['slot_id']} {row['verdict']}", flush=True)
    summary = {
        "stage": args.stage,
        "dispatched": len(dispatch),
        "reviewed_this_run": len(reviewed),
        "accepted_this_run": sum(row["verdict"] == "accepted" for row in reviewed),
        "pending_results": len(pending),
        "complete": not pending and len(attempts_by_key(args.root)) >= len(dispatch),
    }
    atomic_json(args.root / "flux-spool" / args.stage / "collect-summary.json", summary)
    return summary


def latest_correction(root: Path, slot: str) -> str:
    rows = [row for row in load_jsonl(root / "attempts.jsonl") if row["slot_id"] == slot]
    if not rows:
        return ""
    return str(rows[-1].get("luna_review", {}).get("recommission_instruction") or "")


def run_gpt(args: argparse.Namespace) -> dict[str, Any]:
    if not args.prompts:
        raise ValueError("--prompts is required")
    queue = source_by_slot(args.queue)
    prompts = prompts_by_slot(args.prompts)
    eligible = [
        slot for slot in eligible_slots(args.root, queue, args.stage) if slot in prompts
    ]
    if not eligible:
        raise ValueError("prompt ledger contains no currently eligible unresolved slots")

    def process(slot: str) -> dict[str, Any]:
        item = queue[slot]
        correction = latest_correction(args.root, slot)
        prompt = prompts[slot]
        if correction and correction.casefold() != "none":
            prompt = f"{prompt} Ensure this correction: {correction}"
        identifier = request_id(slot, args.stage)
        job = {
            "job_id": identifier,
            "assignment_id": identifier,
            "provider_attempt": STAGES.index(args.stage) + 1,
            "flux_attempt_id": "campaign36-infinitive-remediation",
            "concept_ids": [item["concept_id"]],
            "words": [item["word"]],
            "prompt": prompt,
            "status": "reserved",
        }
        result = generate_one(
            job,
            root=args.root / "gpt-image",
            repo=args.repo,
            codex=Path(args.codex),
            model=args.generation_model,
            timeout=args.generation_timeout,
        )
        if result["status"] != "generated":
            attempt = {
                "schema_version": SCHEMA_VERSION,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "slot_id": slot,
                "ordinal": int(item["ordinal"]),
                "concept_id": item["concept_id"],
                "word": item["word"],
                "part_of_speech": item["part_of_speech"],
                "teaching_sense": item["teaching_sense"],
                "stage": args.stage,
                "provider": "gpt-image-2",
                "prompt": prompt,
                "sha256": "",
                "local_path": "",
                "verdict": "rejected",
                "luna_review": {
                    "verdict": "recommission",
                    "failure_reasons": ["generation_failed"],
                    "recommission_instruction": "Generate a fresh direct image for the exact sense.",
                    "generation_error": result.get("error"),
                },
            }
            append_locked(args.root / "attempts.jsonl", attempt)
            return attempt
        verdict, normalized = review_candidate(image=Path(result["image"]), item=item, stage=args.stage, prompt=prompt, args=args)
        return record_review(item=item, stage=args.stage, provider="gpt-image-2", prompt=prompt, verdict=verdict, normalized=normalized, args=args)

    reviewed = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(process, slot): slot for slot in eligible}
        for index, future in enumerate(as_completed(futures), 1):
            row = future.result()
            reviewed.append(row)
            print(f"reviewed {index}/{len(eligible)} {row['slot_id']} {row['verdict']}", flush=True)
    summary = {"stage": args.stage, "attempted": len(reviewed), "accepted": sum(row["verdict"] == "accepted" for row in reviewed), "remaining": len(queue) - len(accepted_by_slot(args.root))}
    atomic_json(args.root / f"{args.stage}-summary.json", summary)
    return summary


def status(args: argparse.Namespace) -> dict[str, Any]:
    queue = source_by_slot(args.queue)
    accepted = accepted_by_slot(args.root)
    attempts = attempts_by_key(args.root)
    by_stage = {stage: Counter(row["verdict"] for (slot, recorded_stage), row in attempts.items() if recorded_stage == stage) for stage in STAGES}
    result = {
        "schema_version": SCHEMA_VERSION,
        "queue_slots": len(queue),
        "accepted_slots": len(accepted),
        "remaining_slots": len(queue) - len(accepted),
        "stage_counts": {stage: dict(counts) for stage, counts in by_stage.items()},
    }
    atomic_json(args.root / "status.json", result)
    return result


def reconcile(args: argparse.Namespace) -> dict[str, Any]:
    source_rows = load_jsonl(args.manifest)
    source = {str(row["slot_id"]): row for row in source_rows}
    queue = source_by_slot(args.queue)
    accepted = accepted_by_slot(args.root)
    unexpected = sorted(set(accepted) - set(queue))
    if unexpected:
        raise ValueError(f"accepted ledger contains unexpected slots: {unexpected[:5]}")
    terminal = sorted(set(queue) - set(accepted))
    attempts = attempts_by_key(args.root)
    output_rows = []
    for slot in sorted(source):
        old = source[slot]
        replacement = accepted.get(slot)
        if replacement is None:
            output_rows.append(old)
            continue
        path = Path(replacement["local_path"])
        if not path.is_file() or digest(path) != replacement["sha256"]:
            raise ValueError(f"accepted replacement file/hash invalid for {slot}")
        luna = replacement["luna_review"].get("luna_result") or {}
        targets = luna.get("targets") or []
        evidence = targets[0].get("evidence") if targets else replacement["teaching_sense"]
        output_rows.append({
            **old,
            "source": "ninereeds_campaign36_infinitive_remediation",
            "source_id": request_id(slot, replacement["stage"]),
            "local_path": str(path),
            "sha256": replacement["sha256"],
            "asset_sha256": replacement["sha256"],
            "width": 512,
            "height": 384,
            "status": "reviewed_usable",
            "disposition": replacement.get("disposition") or "accepted_luna_exact_sense_remediation",
            "literal_caption": luna.get("literal_caption") or replacement["teaching_sense"],
            "target_evidence": evidence,
            "quality_flags": luna.get("quality_flags") or [],
            "uncertainties": luna.get("uncertainties") or [],
            "watermark": luna.get("watermark", False),
            "review_backend": replacement["luna_review"].get("review_backend"),
            "review_model": replacement["luna_review"].get("review_model"),
            "generation_provider": replacement["provider"],
            "generation_stage": replacement["stage"],
            "generation_prompt": replacement["prompt"],
            "human_override": bool(replacement.get("human_override", False)),
            "human_override_reason": replacement.get("human_override_reason"),
            "replaced_local_path": old.get("local_path"),
            "replaced_sha256": old.get("sha256") or old.get("asset_sha256"),
        })
    if len(output_rows) != 25_000 or len({row["slot_id"] for row in output_rows}) != 25_000:
        raise ValueError("reconciled manifest is not exactly 25,000 unique slots")
    counts = Counter(int(str(row["slot_id"])[1:5]) for row in output_rows)
    if set(counts.values()) != {10}:
        raise ValueError("reconciled manifest does not retain ten slots per contract")
    hash_counts = Counter(str(row.get("sha256") or row.get("asset_sha256") or "") for row in output_rows)
    hash_counts.pop("", None)
    reconciliation = args.root / "reconciliation-v1"
    atomic_jsonl(reconciliation / "accepted-assets.jsonl", output_rows)

    terminal_rows = []
    for slot in terminal:
        item = queue[slot]
        latest = attempts.get((slot, STAGES[-1]), {})
        review = latest.get("luna_review") or {}
        terminal_rows.append({
            "schema_version": SCHEMA_VERSION,
            "slot_id": slot,
            "ordinal": int(item["ordinal"]),
            "concept_id": item["concept_id"],
            "word": item["word"],
            "part_of_speech": item["part_of_speech"],
            "teaching_sense": item["teaching_sense"],
            "attempts_exhausted": sum(
                (slot, stage) in attempts for stage in STAGES
            ),
            "final_failure_reasons": review.get("failure_reasons") or [],
            "final_recommission_instruction": review.get("recommission_instruction"),
        })
    atomic_jsonl(reconciliation / "terminal-failures.jsonl", terminal_rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_slots": len(source_rows),
        "remediation_queue_slots": len(queue),
        "replaced_slots": len(accepted),
        "terminal_failure_slots": len(terminal_rows),
        "terminal_failure_contracts": len({row["ordinal"] for row in terminal_rows}),
        "contracts": len(counts),
        "min_images_per_contract": min(counts.values()),
        "max_images_per_contract": max(counts.values()),
        "max_image_reuse": max(hash_counts.values(), default=0),
        "image_hashes_over_four_uses": sum(value > 4 for value in hash_counts.values()),
        "training_ready": not terminal_rows and max(hash_counts.values(), default=0) <= 4,
    }
    atomic_json(reconciliation / "summary.json", summary)
    return summary


def manual_override(args: argparse.Namespace) -> dict[str, Any]:
    if not args.slots or not args.source_stage:
        raise ValueError("manual-override requires --slots and --source-stage")
    queue = source_by_slot(args.queue)
    attempts = attempts_by_key(args.root)
    accepted = accepted_by_slot(args.root)
    recorded = []
    for slot in args.slots:
        if slot not in queue:
            raise ValueError(f"manual override references unknown queue slot: {slot}")
        if slot in accepted:
            continue
        attempt = attempts.get((slot, args.source_stage))
        if attempt is None:
            raise ValueError(f"no {args.source_stage} attempt exists for {slot}")
        source = Path(str(attempt.get("local_path") or ""))
        expected = str(attempt.get("sha256") or "")
        if not source.is_file() or not expected or digest(source) != expected:
            raise ValueError(f"override source image/hash invalid for {slot}")
        target = args.store / "blobs/ninereeds_campaign36_infinitive_remediation/manual-override" / f"{expected}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            partial = target.with_suffix(".png.partial")
            shutil.copyfile(source, partial)
            if digest(partial) != expected:
                raise ValueError(f"override copy failed hash validation for {slot}")
            os.replace(partial, target)
        override = {
            "schema_version": SCHEMA_VERSION,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "slot_id": slot,
            "ordinal": int(queue[slot]["ordinal"]),
            "concept_id": queue[slot]["concept_id"],
            "word": queue[slot]["word"],
            "part_of_speech": queue[slot]["part_of_speech"],
            "teaching_sense": queue[slot]["teaching_sense"],
            "stage": args.source_stage,
            "provider": attempt["provider"],
            "prompt": attempt["prompt"],
            "sha256": expected,
            "local_path": str(target),
            "verdict": "accepted",
            "disposition": "accepted_explicit_human_override_after_luna_rejection",
            "human_override": True,
            "human_override_reason": args.override_reason,
            "luna_review": attempt["luna_review"],
        }
        append_locked(args.root / "manual-overrides.jsonl", override)
        append_locked(args.root / "accepted.jsonl", override)
        recorded.append(override)
    return {
        "overrides_recorded": len(recorded),
        "slots": [row["slot_id"] for row in recorded],
        "remaining": len(queue) - len(accepted_by_slot(args.root)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("dispatch-flux", "collect-flux", "run-gpt", "status", "reconcile", "manual-override"))
    parser.add_argument("--stage", choices=STAGES)
    parser.add_argument("--queue", type=Path, default=DEFAULT_QUEUE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--prompts", type=Path)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--repo", type=Path, default=Path("/home/aomukai/Ninereeds"))
    parser.add_argument("--remote", default="ninereeds-trainbox")
    parser.add_argument("--remote-root", default="/mnt/ninereeds-runtime/visual/campaign36-infinitive-remediation-v1")
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--review-model", default="gpt-5.6-luna")
    parser.add_argument("--generation-model", default="gpt-5.6-luna")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--review-timeout", type=int, default=600)
    parser.add_argument("--generation-timeout", type=int, default=1200)
    parser.add_argument("--slots", nargs="+")
    parser.add_argument("--source-stage", choices=STAGES)
    parser.add_argument("--override-reason", default="Explicit user decision to accept after reviewing the intended representation despite Luna rejection.")
    args = parser.parse_args()
    if args.command not in {"status", "reconcile", "manual-override"} and not args.stage:
        raise ValueError("--stage is required")
    if args.command == "dispatch-flux":
        result = dispatch_flux(args)
    elif args.command == "collect-flux":
        result = collect_flux(args)
    elif args.command == "run-gpt":
        result = run_gpt(args)
    elif args.command == "reconcile":
        result = reconcile(args)
    elif args.command == "manual-override":
        result = manual_override(args)
    else:
        result = status(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
