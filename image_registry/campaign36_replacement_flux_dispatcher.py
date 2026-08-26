"""Claim Campaign 36 words and dispatch them to one persistent trainbox Flux GPU."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace
from typing import Any

from image_registry.campaign36_flux_streaming_luna import review_one
from image_registry.campaign36_imagegen_fallback import normalize_image
from image_registry.campaign36_replacement_generation_queue import (
    append_unresolved_handoff,
    claim,
    connect as generation_connect,
    finish,
    renew,
)
from image_registry.campaign36_replacement_imagegen_worker import (
    DEFAULT_HANDOFF,
    DEFAULT_ROOT,
    DEFAULT_STORE,
    admit,
    append_locked,
    digest,
    duplicate_hash,
)


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(command, text=True, capture_output=True, check=check)


def upload_request(args: argparse.Namespace, request: dict[str, Any]) -> Path:
    local = args.root / "flux-spool" / f"gpu{args.gpu}" / "requests"
    local.mkdir(parents=True, exist_ok=True)
    path = local / f"{request['request_id']}.json"
    temporary = path.with_suffix(".json.partial")
    temporary.write_text(
        json.dumps(request, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    run(["ssh", args.remote, "mkdir", "-p", f"{args.remote_root}/requests"])
    run(["rsync", "-a", "--partial", str(path), f"{args.remote}:{args.remote_root}/requests/"])
    return path


def wait_result(
    args: argparse.Namespace, request_id: str, *, claim_token: str,
) -> dict[str, Any]:
    local_root = args.root / "flux-spool" / f"gpu{args.gpu}"
    local_result = local_root / "results" / f"{request_id}.json"
    local_result.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + args.generation_timeout
    next_renewal = time.monotonic()
    while time.monotonic() < deadline:
        if time.monotonic() >= next_renewal:
            with generation_connect(args.db) as db:
                renew(
                    db, claim_token=claim_token, worker_id=args.worker_id,
                    lease_seconds=args.lease_seconds,
                )
            next_renewal = time.monotonic() + min(
                300, max(30, args.lease_seconds // 3)
            )
        completed = run(
            [
                "rsync",
                "-a",
                "--partial",
                f"{args.remote}:{args.remote_root}/results/{request_id}.json",
                str(local_result),
            ],
            check=False,
        )
        if completed.returncode == 0 and local_result.is_file():
            result = json.loads(local_result.read_text(encoding="utf-8"))
            local_images = local_root / "images"
            local_images.mkdir(parents=True, exist_ok=True)
            for row in result.get("produced", []):
                run(
                    [
                        "rsync",
                        "-a",
                        "--partial",
                        f"{args.remote}:{row['remote_path']}",
                        str(local_images / Path(row["remote_path"]).name),
                    ]
                )
            return result
        time.sleep(args.poll_seconds)
    raise TimeoutError(f"Flux request timed out: {request_id}")


def default_prompt(item: dict[str, Any]) -> str:
    return str(item.get("prompt") or "").strip() or (
        f'Create a clean educational photograph that directly and unambiguously depicts '
        f'the word "{item["word"]}" in this exact sense: {item["teaching_sense"]}. '
        "Make the target primary and recognizable without relying on a caption."
    )


def run_one(args: argparse.Namespace) -> dict[str, Any]:
    with generation_connect(args.db) as db:
        item = claim(
            db,
            provider="flux",
            worker_id=args.worker_id,
            lease_seconds=args.lease_seconds,
        )
    if item is None:
        return {"status": "idle", "worker_id": args.worker_id}
    request_prefix = (
        f"c36-repl-{int(item['ordinal']):04d}-p{int(item['prompt_cycle']):02d}-"
        f"flux-gpu{args.gpu}"
    )
    request_base = {
        "word": item["word"],
        "concept_id": item["concept_id"],
        "teaching_sense": item["teaching_sense"],
        "ordinal": int(item["ordinal"]),
        "prompt_cycle": int(item["prompt_cycle"]),
        "prompt": default_prompt(item),
        "attempts_per_needed": 3,
        "claim_token": item["claim_token"],
    }
    produced_count = 0
    accepted = 0
    evidence: list[dict[str, Any]] = []
    try:
        for shot_retry in range(1, args.attempts_per_needed + 1):
            deficit = int(item["requested_count"]) - accepted
            if deficit <= 0:
                break
            request_id = f"{request_prefix}-r{shot_retry:02d}"
            request = {
                **request_base,
                "request_id": request_id,
                "requested_count": deficit,
                "shot_retry": shot_retry,
            }
            upload_request(args, request)
            result = wait_result(args, request_id, claim_token=item["claim_token"])
            local_images = args.root / "flux-spool" / f"gpu{args.gpu}" / "images"
            for candidate in result.get("produced", []):
                produced_count += 1
                source = local_images / Path(candidate["remote_path"]).name
                normalized = args.root / "flux" / "accepted-staging" / source.name
                normalize_image(source, normalized)
                sha256 = digest(normalized)
                if duplicate_hash(args.db, sha256):
                    evidence.append({**candidate, "shot_retry": shot_retry, "status": "duplicate_hash", "sha256": sha256})
                    source.unlink(missing_ok=True)
                    normalized.unlink(missing_ok=True)
                    continue
                identifier = Path(candidate["remote_path"]).stem
                review_row = {
                    "schema_version": "ninereeds_campaign36_replacement_generated_v1",
                    "assignment_id": identifier,
                    "production_brief_id": identifier,
                    "variant_index": int(candidate["variant"]),
                    "generation_attempt": shot_retry,
                    "concept_ids": [item["concept_id"]],
                    "words": [item["word"]],
                    "evidence_by_concept": {item["concept_id"]: item["teaching_sense"]},
                    "grounding_mode": "direct",
                    "visible_text_policy": "reject",
                    "prompt": candidate["prompt"],
                    "local_path": str(normalized),
                    "sha256": sha256,
                    "width": 512,
                    "height": 384,
                    "provider": "flux2-klein-4b",
                }
                verdict = review_one(
                    review_row,
                    normalized,
                    SimpleNamespace(codex=args.codex, model=args.review_model, timeout=args.review_timeout),
                )
                with generation_connect(args.db) as db:
                    renew(
                        db, claim_token=item["claim_token"], worker_id=args.worker_id,
                        lease_seconds=args.lease_seconds,
                    )
                evidence.append(
                    {
                        **candidate,
                        "shot_retry": shot_retry,
                        "status": verdict["verdict"],
                        "sha256": sha256,
                        "failure_reasons": verdict.get("failure_reasons", []),
                        "recommission_instruction": verdict.get("recommission_instruction"),
                    }
                )
                if verdict["verdict"] != "accepted":
                    source.unlink(missing_ok=True)
                    normalized.unlink(missing_ok=True)
                    continue
                record = admit(
                    db_path=args.db,
                    store=args.store,
                    source_id=identifier,
                    image=normalized,
                    sha256=sha256,
                    prompt=candidate["prompt"],
                    item=item,
                    verdict=verdict,
                    provider="flux",
                )
                append_locked(args.root / "accepted-generated.jsonl", record)
                append_locked(args.root / "review-evidence.jsonl", {**record, "review": verdict})
                source.unlink(missing_ok=True)
                normalized.unlink(missing_ok=True)
                accepted += 1
            evidence.extend({**row, "shot_retry": shot_retry} for row in result.get("failures", []))
    except Exception as exc:
        evidence.append({"status": "dispatcher_exception", "type": type(exc).__name__, "message": str(exc)})
    with generation_connect(args.db) as db:
        state = finish(
            db,
            claim_token=item["claim_token"],
            worker_id=args.worker_id,
            produced_count=produced_count,
            accepted_added=accepted,
            evidence={"provider": "flux", "attempts": evidence},
        )
        if state["status"] == "unresolved":
            append_unresolved_handoff(db, path=args.handoff)
    return {
        "status": state["status"],
        "word": item["word"],
        "requested": int(item["requested_count"]),
        "produced": produced_count,
        "accepted": accepted,
        "remaining": state["remaining_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--gpu", type=int, choices=(0, 1), required=True)
    parser.add_argument("--remote", default="ninereeds-trainbox")
    parser.add_argument("--remote-root", required=True)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--review-model", default="gpt-5.6-luna")
    parser.add_argument("--lease-seconds", type=int, default=10800)
    parser.add_argument("--generation-timeout", type=int, default=10800)
    parser.add_argument("--review-timeout", type=int, default=600)
    parser.add_argument("--attempts-per-needed", type=int, default=3)
    parser.add_argument("--poll-seconds", type=float, default=10)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    while True:
        result = run_one(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        if not args.loop:
            return 0
        if result["status"] == "idle":
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
