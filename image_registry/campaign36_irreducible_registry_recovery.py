"""Review existing registry photographs for Campaign 36 irreducible deficits.

The ordinary replacement loop deliberately stops after both generators exhaust a
revised prompt.  This bounded recovery path does not weaken that evidence: it lets
an operator nominate already-held real photographs, runs the same independent Luna
pixel gate, and publishes accepted rows into the generated-candidate ledger used by
the deterministic reconciler.  It is append-only and idempotent by word and hash.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace
from typing import Any

from image_registry.campaign36_flux_streaming_luna import review_one
from image_registry.campaign36_imagegen_fallback import normalize_image
from image_registry.campaign36_replacement_generation_queue import connect as generation_connect
from image_registry.campaign36_replacement_imagegen_worker import (
    DEFAULT_STORE,
    append_locked,
    digest,
)
from image_registry.cli import connect as registry_connect


def ledger_keys(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    keys: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        keys.add((str(row.get("word") or ""), str(row.get("sha256") or "")))
    return keys


def parse_candidate(value: str) -> tuple[str, int]:
    word, separator, raw_id = value.rpartition("=")
    if not separator or not word.strip():
        raise argparse.ArgumentTypeError("candidate must be WORD=ASSET_ID")
    try:
        asset_id = int(raw_id)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("asset id must be an integer") from exc
    return word.strip(), asset_id


def recover(args: argparse.Namespace) -> dict[str, int]:
    accepted_path = args.root / "accepted-generated.jsonl"
    evidence_path = args.root / "irreducible-registry-recovery-evidence.jsonl"
    known = ledger_keys(accepted_path)
    counts = {"reviewed": 0, "accepted": 0, "rejected": 0, "already_present": 0, "errors": 0}

    for word, asset_id in args.candidate:
        try:
            with generation_connect(args.db) as db:
                contract_raw = db.execute(
                    "SELECT * FROM campaign36_word_generation WHERE word=?", (word,)
                ).fetchone()
            if contract_raw is None:
                raise ValueError(f"no generation contract for {word!r}")
            contract = dict(contract_raw)
            with registry_connect(args.db) as db:
                asset_raw = db.execute("SELECT * FROM asset WHERE id=?", (asset_id,)).fetchone()
                caption_raw = db.execute(
                    """SELECT text FROM text_record WHERE asset_id=?
                       ORDER BY CASE kind WHEN 'caption' THEN 0 ELSE 1 END,id LIMIT 1""",
                    (asset_id,),
                ).fetchone()
            if asset_raw is None:
                raise ValueError(f"missing asset {asset_id}")
            asset = dict(asset_raw)
            source_image = Path(asset["local_path"])
            if not source_image.is_file():
                raise FileNotFoundError(source_image)
            staging = args.root / "irreducible-registry-staging" / f"{word}-{asset_id}.png"
            staging.parent.mkdir(parents=True, exist_ok=True)
            normalize_image(source_image, staging)
            image_digest = digest(staging)
            if (word, image_digest) in known:
                staging.unlink(missing_ok=True)
                counts["already_present"] += 1
                continue
            source_caption = str(caption_raw[0] if caption_raw else "")
            assignment = f"c36-irreducible-{word}-{asset_id}".replace("/", "-")
            review_row = {
                "schema_version": "ninereeds_campaign36_irreducible_registry_recovery_v1",
                "assignment_id": assignment,
                "production_brief_id": assignment,
                "variant_index": 1,
                "generation_attempt": 1,
                "concept_ids": [contract["concept_id"]],
                "words": [word],
                "evidence_by_concept": {contract["concept_id"]: contract["teaching_sense"]},
                "grounding_mode": "direct",
                "visible_text_policy": "reject",
                "prompt": source_caption,
                "local_path": str(staging),
                "sha256": image_digest,
                "width": 512,
                "height": 384,
                "provider": "existing-image-registry",
            }
            verdict = review_one(
                review_row,
                staging,
                SimpleNamespace(codex=args.codex, model=args.review_model, timeout=args.review_timeout),
            )
            counts["reviewed"] += 1
            append_locked(evidence_path, {
                "schema_version": "ninereeds_campaign36_irreducible_registry_recovery_v1",
                "word": word,
                "asset_id": asset_id,
                "sha256": image_digest,
                "verdict": verdict,
            })
            if verdict.get("verdict") != "accepted":
                staging.unlink(missing_ok=True)
                counts["rejected"] += 1
                continue
            destination = args.store / "blobs/ninereeds_campaign36_irreducible_recovery"
            destination.mkdir(parents=True, exist_ok=True)
            target = destination / f"{image_digest}.png"
            if not target.exists():
                partial = target.with_suffix(".png.partial")
                shutil.copyfile(staging, partial)
                if digest(partial) != image_digest:
                    partial.unlink(missing_ok=True)
                    raise ValueError("copied recovery image failed its hash check")
                partial.replace(target)
            luna = verdict.get("luna_result") or {}
            recovery_source_id = f"{word}:{asset_id}"
            with registry_connect(args.db) as db:
                db.execute(
                    """INSERT INTO asset(source,source_id,split,original_url,author,title,
                           declared_bytes,local_path,sha256,width,height,status)
                       VALUES ('ninereeds_campaign36_irreducible_recovery',?,'derived',?,
                               ?,?,?,?,?,512,384,'reviewed_usable')
                       ON CONFLICT(source,source_id) DO UPDATE SET
                           local_path=excluded.local_path,sha256=excluded.sha256,
                           declared_bytes=excluded.declared_bytes,status='reviewed_usable'""",
                    (
                        recovery_source_id,
                        f"registry-asset:{asset_id}",
                        str(asset.get("author") or asset["source"]),
                        word,
                        target.stat().st_size,
                        str(target),
                        image_digest,
                    ),
                )
                recovered_asset_id = db.execute(
                    """SELECT id FROM asset
                       WHERE source='ninereeds_campaign36_irreducible_recovery'
                         AND source_id=?""",
                    (recovery_source_id,),
                ).fetchone()[0]
                payload = json.dumps(
                    {"source_asset_id": asset_id, "review": verdict, "word": word},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                db.execute("DELETE FROM text_search WHERE asset_id=?", (recovered_asset_id,))
                db.execute("DELETE FROM text_record WHERE asset_id=?", (recovered_asset_id,))
                db.execute(
                    """INSERT INTO text_record(asset_id,kind,text,author,model,payload_json)
                       VALUES (?,'irreducible_recovery_caption',?,?,?,?)""",
                    (
                        recovered_asset_id,
                        source_caption,
                        "campaign36_irreducible_registry_recovery",
                        args.review_model,
                        payload,
                    ),
                )
                db.execute(
                    """INSERT INTO text_search(asset_id,kind,text)
                       VALUES (?,'irreducible_recovery_caption',?)""",
                    (recovered_asset_id, source_caption),
                )
                db.commit()
            row: dict[str, Any] = {
                "schema_version": "ninereeds_campaign36_replacement_generated_v1",
                "disposition": "accepted",
                "candidate_pool": "existing_registry_irreducible_recovery",
                "candidate_tier": "existing_registry_direct_luna_accepted",
                "candidate_rank": 1,
                "asset_id": recovered_asset_id,
                "source": "ninereeds_campaign36_irreducible_recovery",
                "source_id": recovery_source_id,
                "local_path": str(target),
                "sha256": image_digest,
                "width": 512,
                "height": 384,
                "status": "reviewed_usable",
                "word": word,
                "concept": word,
                "concept_id": contract["concept_id"],
                "teaching_sense": contract["teaching_sense"],
                "ordinal": int(contract["ordinal"]),
                "literal_caption": luna.get("literal_caption") or source_caption,
                "source_caption": source_caption,
                "target_evidence": contract["teaching_sense"],
                "quality_flags": luna.get("quality_flags") or [],
                "uncertainties": luna.get("uncertainties") or [],
                "watermark": luna.get("watermark", False),
                "review_backend": verdict.get("review_backend"),
                "review_model": verdict.get("review_model"),
                "generation_provider": "existing_registry_recovery",
                "prompt_cycle": int(contract["prompt_cycle"]),
                "prompt": source_caption,
            }
            append_locked(accepted_path, row)
            known.add((word, image_digest))
            staging.unlink(missing_ok=True)
            counts["accepted"] += 1
        except Exception as exc:
            append_locked(evidence_path, {
                "schema_version": "ninereeds_campaign36_irreducible_registry_recovery_v1",
                "word": word,
                "asset_id": asset_id,
                "status": "error",
                "type": type(exc).__name__,
                "message": str(exc),
            })
            counts["errors"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--candidate", action="append", type=parse_candidate, required=True)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--review-model", default="gpt-5.6-luna")
    parser.add_argument("--review-timeout", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(recover(args), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
