"""Fulfil one Campaign 36 replacement-word claim with built-in ImageGen.

Each worker owns one word at a time, keeps every accepted partial result, and closes
the provider shot only after exhausting its bounded same-prompt retries.  Every image
passes the established mechanical and independent Luna pixel gate before admission.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
from pathlib import Path
import shutil
import time
from types import SimpleNamespace
from typing import Any

from image_registry.campaign36_flux_streaming_luna import review_one
from image_registry.campaign36_headless_imagegen import generate_one
from image_registry.campaign36_imagegen_fallback import normalize_image
from image_registry.campaign36_replacement_generation_queue import (
    append_unresolved_handoff,
    claim,
    connect as generation_connect,
    finish,
    renew,
)
from image_registry.cli import connect as registry_connect


SCHEMA_VERSION = "ninereeds_campaign36_replacement_generated_v1"
DEFAULT_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/visual-vocabulary-replacement-v1/generation-v1"
)
DEFAULT_STORE = Path("/media/aomukai/FILES/Ninereeds/image-corpus")
DEFAULT_HANDOFF = Path("/home/aomukai/Ninereeds/handoff/2026_08_22_image_representation_ideas_needed.md")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def append_locked(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        fcntl.flock(handle, fcntl.LOCK_UN)


def prompt_for(item: dict[str, Any], *, variant: int, retry: int) -> str:
    fixed = str(item.get("prompt") or "").strip()
    if not fixed:
        fixed = (
            f'Create a clean educational photograph that directly and unambiguously depicts '
            f'the word "{item["word"]}" in this exact sense: {item["teaching_sense"]}. '
            f'Make the target visually prominent and recognizable without relying on a caption.'
        )
    return " ".join(
        [
            fixed,
            f"This is distinct accepted-image candidate {variant}; use a fresh setting, subject, viewpoint, or incidental appearance while preserving the exact meaning.",
            f"Retry variation {retry}; do not reproduce earlier pixels.",
            "Natural coherent anatomy and object structure. No labels, explanatory text, logos, borders, collage panels, or watermarks.",
        ]
    )


def duplicate_hash(db_path: Path, sha256: str) -> bool:
    with registry_connect(db_path) as db:
        return db.execute("SELECT 1 FROM asset WHERE sha256=? LIMIT 1", (sha256,)).fetchone() is not None


def admit(
    *,
    db_path: Path,
    store: Path,
    source_id: str,
    image: Path,
    sha256: str,
    prompt: str,
    item: dict[str, Any],
    verdict: dict[str, Any],
    provider: str = "imagegen",
) -> dict[str, Any]:
    if provider not in {"imagegen", "flux"}:
        raise ValueError("generated provider must be imagegen or flux")
    destination = store / f"blobs/ninereeds_campaign36_replacement_generated/{provider}"
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f"{sha256}.png"
    if not target.exists():
        partial = target.with_suffix(".png.partial")
        shutil.copyfile(image, partial)
        if digest(partial) != sha256:
            partial.unlink(missing_ok=True)
            raise ValueError("copied generated image failed its hash check")
        partial.replace(target)
    with registry_connect(db_path) as db:
        db.execute(
            """INSERT INTO asset(source,source_id,split,original_url,author,title,
                   declared_bytes,local_path,sha256,width,height,status)
               VALUES ('ninereeds_campaign36_replacement_generated',?,'generated',?,
                ?,?,?,?,?,512,384,'reviewed_usable')
               ON CONFLICT(source,source_id) DO UPDATE SET
                   local_path=excluded.local_path,sha256=excluded.sha256,
                   declared_bytes=excluded.declared_bytes,status='reviewed_usable'""",
            (
                source_id,
                f"campaign36-{provider}:{source_id}",
                "Ninereeds / GPT Image" if provider == "imagegen" else "Ninereeds / FLUX.2-klein-4B",
                item["word"],
                target.stat().st_size,
                str(target),
                sha256,
            ),
        )
        asset_id = db.execute(
            """SELECT id FROM asset
               WHERE source='ninereeds_campaign36_replacement_generated' AND source_id=?""",
            (source_id,),
        ).fetchone()[0]
        payload = json.dumps(
            {"claim": item, "review": verdict, "prompt": prompt},
            ensure_ascii=False,
            sort_keys=True,
        )
        db.execute("DELETE FROM text_search WHERE asset_id=?", (asset_id,))
        db.execute("DELETE FROM text_record WHERE asset_id=?", (asset_id,))
        db.execute(
            """INSERT INTO text_record(asset_id,kind,text,author,model,payload_json)
               VALUES (?,'generation_prompt',?,?,?,?)""",
            (
                asset_id,
                prompt,
                f"campaign36_replacement_{provider}",
                "gpt-image" if provider == "imagegen" else "flux2-klein-4b",
                payload,
            ),
        )
        db.execute(
            "INSERT INTO text_search(asset_id,kind,text) VALUES (?,'generation_prompt',?)",
            (asset_id, prompt),
        )
        db.commit()
    luna = verdict.get("luna_result") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "disposition": "accepted",
        "candidate_pool": f"generated_{provider}",
        "candidate_tier": "generated_direct_luna_accepted",
        "candidate_rank": 1,
        "asset_id": asset_id,
        "source": "ninereeds_campaign36_replacement_generated",
        "source_id": source_id,
        "local_path": str(target),
        "sha256": sha256,
        "width": 512,
        "height": 384,
        "status": "reviewed_usable",
        "word": item["word"],
        "concept": item["word"],
        "concept_id": item["concept_id"],
        "teaching_sense": item["teaching_sense"],
        "ordinal": int(item["ordinal"]),
        "literal_caption": luna.get("literal_caption") or item["teaching_sense"],
        "source_caption": prompt,
        "target_evidence": item["teaching_sense"],
        "quality_flags": luna.get("quality_flags") or [],
        "uncertainties": luna.get("uncertainties") or [],
        "watermark": luna.get("watermark", False),
        "review_backend": verdict.get("review_backend"),
        "review_model": verdict.get("review_model"),
        "generation_provider": provider,
        "prompt_cycle": int(item["prompt_cycle"]),
        "prompt": prompt,
    }


def run_one(args: argparse.Namespace) -> dict[str, Any]:
    with generation_connect(args.db) as db:
        item = claim(
            db,
            provider="imagegen",
            worker_id=args.worker_id,
            lease_seconds=args.lease_seconds,
        )
    if item is None:
        return {"status": "idle", "worker_id": args.worker_id}
    output = args.root / "imagegen"
    output.mkdir(parents=True, exist_ok=True)
    accepted = 0
    produced = 0
    evidence: list[dict[str, Any]] = []
    requested = int(item["requested_count"])
    try:
        for variant in range(1, requested + 1):
            accepted_this_variant = False
            for retry in range(1, args.attempts_per_needed + 1):
                with generation_connect(args.db) as db:
                    renew(
                        db, claim_token=item["claim_token"], worker_id=args.worker_id,
                        lease_seconds=args.lease_seconds,
                    )
                identifier = (
                    f"c36-repl-{int(item['ordinal']):04d}-p{int(item['prompt_cycle']):02d}-"
                    f"{args.worker_id}-v{variant:02d}-r{retry:02d}"
                ).replace("/", "-")
                prompt = prompt_for(item, variant=variant, retry=retry)
                job = {
                    "job_id": identifier,
                    "assignment_id": identifier,
                    "provider_attempt": retry,
                    "flux_attempt_id": "replacement-word-queue",
                    "concept_ids": [item["concept_id"]],
                    "words": [item["word"]],
                    "prompt": prompt,
                    "status": "reserved",
                }
                result = generate_one(
                    job,
                    root=output,
                    repo=args.repo,
                    codex=args.codex,
                    model=args.model,
                    timeout=args.generation_timeout,
                )
                with generation_connect(args.db) as db:
                    renew(
                        db, claim_token=item["claim_token"], worker_id=args.worker_id,
                        lease_seconds=args.lease_seconds,
                    )
                if result["status"] != "generated":
                    evidence.append(
                        {"variant": variant, "retry": retry, "status": result["status"], "error": result.get("error")}
                    )
                    continue
                produced += 1
                normalized = output / "accepted-staging" / f"{identifier}.png"
                normalize_image(Path(result["image"]), normalized)
                sha256 = digest(normalized)
                if duplicate_hash(args.db, sha256):
                    evidence.append(
                        {"variant": variant, "retry": retry, "status": "duplicate_hash", "sha256": sha256}
                    )
                    Path(result["image"]).unlink(missing_ok=True)
                    normalized.unlink(missing_ok=True)
                    continue
                review_row = {
                    "schema_version": SCHEMA_VERSION,
                    "assignment_id": identifier,
                    "production_brief_id": identifier,
                    "variant_index": variant,
                    "generation_attempt": retry,
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
                    "provider": "codex-built-in-imagegen",
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
                        "variant": variant,
                        "retry": retry,
                        "status": verdict["verdict"],
                        "sha256": sha256,
                        "failure_reasons": verdict.get("failure_reasons", []),
                        "recommission_instruction": verdict.get("recommission_instruction"),
                    }
                )
                if verdict["verdict"] != "accepted":
                    Path(result["image"]).unlink(missing_ok=True)
                    normalized.unlink(missing_ok=True)
                    continue
                record = admit(
                    db_path=args.db,
                    store=args.store,
                    source_id=identifier,
                    image=normalized,
                    sha256=sha256,
                    prompt=prompt,
                    item=item,
                    verdict=verdict,
                )
                append_locked(args.root / "accepted-generated.jsonl", record)
                append_locked(args.root / "review-evidence.jsonl", {**record, "review": verdict})
                Path(result["image"]).unlink(missing_ok=True)
                normalized.unlink(missing_ok=True)
                accepted += 1
                accepted_this_variant = True
                break
            if not accepted_this_variant:
                # Continue to later requested variants: a partial word set is valuable.
                continue
    except Exception as exc:
        evidence.append({"status": "worker_exception", "type": type(exc).__name__, "message": str(exc)})
    with generation_connect(args.db) as db:
        state = finish(
            db,
            claim_token=item["claim_token"],
            worker_id=args.worker_id,
            produced_count=produced,
            accepted_added=accepted,
            evidence={"provider": "imagegen", "attempts": evidence},
        )
        if state["status"] == "unresolved":
            append_unresolved_handoff(db, path=args.handoff)
    return {
        "status": state["status"],
        "word": item["word"],
        "requested": requested,
        "produced": produced,
        "accepted": accepted,
        "remaining": state["remaining_count"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--repo", type=Path, default=Path("/home/aomukai/Ninereeds"))
    parser.add_argument("--codex", type=Path, default=Path("/home/aomukai/.local/bin/codex"))
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--review-model", default="gpt-5.6-luna")
    parser.add_argument("--lease-seconds", type=int, default=10800)
    parser.add_argument("--generation-timeout", type=int, default=900)
    parser.add_argument("--review-timeout", type=int, default=600)
    parser.add_argument("--attempts-per-needed", type=int, default=3)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--poll-seconds", type=float, default=15)
    parser.add_argument("--loop", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.attempts_per_needed <= 5:
        raise SystemExit("attempts-per-needed must be between 1 and 5")
    while True:
        result = run_one(args)
        print(json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
        if not args.loop:
            return 0
        if result["status"] == "idle":
            time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
