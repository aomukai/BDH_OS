"""Recover accepted Campaign 36 generated-image ledgers from the image registry.

Registry admission commits before append-only ledger publication.  If a worker dies
inside that narrow interval, this projection reconstructs the accepted record from
the stored claim, prompt, and Luna verdict.  Re-running it is idempotent.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from image_registry.campaign36_replacement_imagegen_worker import append_locked
from image_registry.cli import connect


SCHEMA_VERSION = "ninereeds_campaign36_replacement_generated_v1"


def load_keys(path: Path) -> set[tuple[str, str]]:
    if not path.is_file():
        return set()
    keys: set[tuple[str, str]] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        keys.add((str(row.get("source_id") or ""), str(row.get("sha256") or "")))
    return keys


def reconstruct(asset: dict[str, Any], payload: dict[str, Any], prompt: str) -> dict[str, Any] | None:
    claim = payload.get("claim") or {}
    verdict = payload.get("review") or {}
    if verdict.get("verdict") != "accepted" or not claim.get("word"):
        return None
    original_url = str(asset.get("original_url") or "")
    provider = "flux" if original_url.startswith("campaign36-flux:") else "imagegen"
    luna = verdict.get("luna_result") or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "disposition": "accepted",
        "candidate_pool": f"generated_{provider}",
        "candidate_tier": "generated_direct_luna_accepted",
        "candidate_rank": 1,
        "asset_id": int(asset["id"]),
        "source": asset["source"],
        "source_id": asset["source_id"],
        "local_path": asset["local_path"],
        "sha256": asset["sha256"],
        "width": int(asset["width"]),
        "height": int(asset["height"]),
        "status": asset["status"],
        "word": claim["word"],
        "concept": claim["word"],
        "concept_id": claim["concept_id"],
        "teaching_sense": claim["teaching_sense"],
        "ordinal": int(claim["ordinal"]),
        "literal_caption": luna.get("literal_caption") or claim["teaching_sense"],
        "source_caption": prompt,
        "target_evidence": claim["teaching_sense"],
        "quality_flags": luna.get("quality_flags") or [],
        "uncertainties": luna.get("uncertainties") or [],
        "watermark": luna.get("watermark", False),
        "review_backend": verdict.get("review_backend"),
        "review_model": verdict.get("review_model"),
        "generation_provider": provider,
        "prompt_cycle": int(claim["prompt_cycle"]),
        "prompt": prompt,
    }


def recover(db_path: Path, root: Path) -> dict[str, int]:
    accepted_path = root / "accepted-generated.jsonl"
    evidence_path = root / "review-evidence.jsonl"
    accepted_keys = load_keys(accepted_path)
    evidence_keys = load_keys(evidence_path)
    recovered_accepted = 0
    recovered_evidence = 0
    with connect(db_path) as db:
        records = db.execute(
            """SELECT a.*,t.text prompt,t.payload_json
               FROM asset a JOIN text_record t ON t.asset_id=a.id
               WHERE a.source='ninereeds_campaign36_replacement_generated'
                 AND t.kind='generation_prompt'
               ORDER BY a.id,t.id"""
        ).fetchall()
    for raw in records:
        asset = dict(raw)
        try:
            payload = json.loads(asset.pop("payload_json"))
            prompt = str(asset.pop("prompt"))
            row = reconstruct(asset, payload, prompt)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if row is None or not Path(row["local_path"]).is_file():
            continue
        key = (row["source_id"], row["sha256"])
        if key not in accepted_keys:
            append_locked(accepted_path, row)
            accepted_keys.add(key)
            recovered_accepted += 1
        if key not in evidence_keys:
            append_locked(evidence_path, {**row, "review": payload["review"]})
            evidence_keys.add(key)
            recovered_evidence += 1
    return {
        "registry_generated_assets": len(records),
        "recovered_accepted_records": recovered_accepted,
        "recovered_evidence_records": recovered_evidence,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(recover(args.db, args.root), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
