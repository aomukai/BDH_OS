"""Import and review a provenance-tracked supplemental Campaign 36 image candidate."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
from types import SimpleNamespace

from PIL import Image

from image_registry.campaign36_flux_streaming_luna import append_jsonl, review_one
from image_registry.campaign36_imagegen_fallback import normalize_image
from image_registry.cli import connect


SCHEMA_VERSION = "ninereeds_campaign36_external_candidate_v1"
OVERRIDE_SCHEMA_VERSION = "ninereeds_campaign36_external_candidate_human_override_v1"
DEFAULT_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/flux-specialist-v1/imagegen-v1/external"
)
DEFAULT_DB = Path("training_data/image_registry/registry.sqlite3")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def existing_candidate(ledger: Path, candidate_id: str, original_sha256: str) -> dict | None:
    if not ledger.is_file():
        return None
    for line in ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("candidate_id") == candidate_id:
            if row.get("original_sha256") != original_sha256:
                raise SystemExit(f"candidate ID collision with different source bytes: {candidate_id}")
            return row
    return None


def register(db_path: Path, row: dict, verdict: dict) -> int:
    status = "reviewed_usable" if verdict["verdict"] == "accepted" else "reviewed_unusable"
    payload = json.dumps({"candidate": row, "verdict": verdict}, ensure_ascii=False, sort_keys=True)
    with connect(db_path) as db:
        db.execute(
            """INSERT INTO asset(
                   source,source_id,split,original_url,landing_url,license_url,author,title,
                   declared_bytes,local_path,sha256,width,height,status
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(source,source_id) DO UPDATE SET
                   original_url=excluded.original_url,landing_url=excluded.landing_url,
                   license_url=excluded.license_url,author=excluded.author,title=excluded.title,
                   declared_bytes=excluded.declared_bytes,local_path=excluded.local_path,
                   sha256=excluded.sha256,width=excluded.width,height=excluded.height,
                   status=excluded.status""",
            (
                row["source"], row["source_id"], "campaign36_supplemental",
                row["original_url"], row["landing_url"], row["license_url"], row["author"],
                row["title"], row["original_bytes"], row["local_path"], row["sha256"],
                row["width"], row["height"], status,
            ),
        )
        asset_id = int(db.execute(
            "SELECT id FROM asset WHERE source=? AND source_id=?",
            (row["source"], row["source_id"]),
        ).fetchone()[0])
        db.execute(
            """INSERT OR REPLACE INTO label(asset_id,name,confidence,annotation_source)
               VALUES(?,?,?,?)""",
            (asset_id, row["word"], 1.0, "human-approved-campaign36-supplemental"),
        )
        prior = db.execute(
            "SELECT 1 FROM text_record WHERE asset_id=? AND kind=? AND payload_json=?",
            (asset_id, "campaign36_external_candidate_review", payload),
        ).fetchone()
        if prior is None:
            cursor = db.execute(
                """INSERT INTO text_record(asset_id,kind,text,author,model,payload_json)
                   VALUES(?,?,?,?,?,?)""",
                (
                    asset_id, "campaign36_external_candidate_review", row["evidence"],
                    "human+gpt-5.6-luna", verdict.get("review_model"), payload,
                ),
            )
            db.execute(
                "INSERT INTO text_search(asset_id,kind,text) VALUES(?,?,?)",
                (asset_id, "campaign36_external_candidate_review", row["evidence"]),
            )
        return asset_id


def apply_human_override(
    db_path: Path,
    root: Path,
    row: dict,
    *,
    admission: str,
    reason: str,
    approver: str,
) -> int:
    """Record an explicit human disposition without erasing the model review."""
    status = "reviewed_usable" if admission == "usable" else "reviewed_unusable"
    override = {
        "schema_version": OVERRIDE_SCHEMA_VERSION,
        "candidate_id": row["candidate_id"],
        "source": row["source"],
        "source_id": row["source_id"],
        "original_sha256": row["original_sha256"],
        "admission": admission,
        "reason": reason,
        "approver": approver,
        "prior_model_verdict": row.get("review_verdict"),
        "decided_at": datetime.now(timezone.utc).isoformat(),
    }
    override_ledger = root / "human-overrides.jsonl"
    prior_override = None
    if override_ledger.is_file():
        for line in override_ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            candidate = json.loads(line)
            if (
                candidate.get("candidate_id") == row["candidate_id"]
                and candidate.get("original_sha256") == row["original_sha256"]
                and candidate.get("admission") == admission
                and candidate.get("reason") == reason
            ):
                prior_override = candidate
                break
    if prior_override is None:
        append_jsonl(override_ledger, override)
    else:
        override = prior_override

    payload = json.dumps(override, ensure_ascii=False, sort_keys=True)
    with connect(db_path) as db:
        asset = db.execute(
            "SELECT id FROM asset WHERE source=? AND source_id=?",
            (row["source"], row["source_id"]),
        ).fetchone()
        if asset is None:
            raise SystemExit("cannot override an external candidate that is not registered")
        asset_id = int(asset[0])
        db.execute("UPDATE asset SET status=? WHERE id=?", (status, asset_id))
        if db.execute(
            "SELECT 1 FROM text_record WHERE asset_id=? AND kind=? AND payload_json=?",
            (asset_id, "campaign36_external_candidate_human_override", payload),
        ).fetchone() is None:
            db.execute(
                """INSERT INTO text_record(asset_id,kind,text,author,model,payload_json)
                   VALUES(?,?,?,?,?,?)""",
                (
                    asset_id, "campaign36_external_candidate_human_override", reason,
                    approver, None, payload,
                ),
            )
            db.execute(
                "INSERT INTO text_search(asset_id,kind,text) VALUES(?,?,?)",
                (asset_id, "campaign36_external_candidate_human_override", reason),
            )
    return asset_id


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--word", required=True)
    parser.add_argument("--concept-id", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--author", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--original-url", required=True)
    parser.add_argument("--landing-url", required=True)
    parser.add_argument("--license-url", required=True)
    parser.add_argument("--grounding-mode", choices=("direct", "contextual_transfer"), default="direct")
    parser.add_argument("--visible-text-policy", choices=("reject", "required_evidence"), default="reject")
    parser.add_argument("--visible-text-note")
    parser.add_argument("--human-override-admission", choices=("usable", "unusable"))
    parser.add_argument("--human-override-reason")
    parser.add_argument("--human-override-approver", default="operator")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    if bool(args.human_override_admission) != bool(args.human_override_reason):
        parser.error("human override admission and reason must be supplied together")

    original_sha = sha256(args.image)
    ledger = args.root / "candidates.jsonl"
    if prior := existing_candidate(ledger, args.candidate_id, original_sha):
        result = {"candidate": prior}
        if args.human_override_admission:
            result["asset_id"] = apply_human_override(
                args.db, args.root, prior,
                admission=args.human_override_admission,
                reason=args.human_override_reason,
                approver=args.human_override_approver,
            )
            result["human_override"] = args.human_override_admission
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    originals = args.root / "originals"
    images = args.root / "images"
    originals.mkdir(parents=True, exist_ok=True)
    images.mkdir(parents=True, exist_ok=True)
    original_target = originals / f"{args.source_id}{args.image.suffix.lower()}"
    normalized_target = images / f"{args.candidate_id}.png"
    shutil.copy2(args.image, original_target)
    normalize_image(original_target, normalized_target)
    with Image.open(normalized_target) as image:
        image.load()
        width, height = image.size
    row = {
        "schema_version": SCHEMA_VERSION,
        "candidate_id": args.candidate_id,
        "production_brief_id": f"supplemental-{args.candidate_id}",
        "variant_index": 0,
        "generation_attempt": 1,
        "concept_ids": [args.concept_id],
        "words": [args.word],
        "word": args.word,
        "evidence": args.evidence,
        "evidence_by_concept": {args.concept_id: args.evidence},
        "grounding_mode": args.grounding_mode,
        "visible_text_policy": args.visible_text_policy,
        "visible_text_note": args.visible_text_note,
        "provider": "user-supplied-external-photo",
        "source": args.source,
        "source_id": args.source_id,
        "author": args.author,
        "title": args.title,
        "original_url": args.original_url,
        "landing_url": args.landing_url,
        "license_url": args.license_url,
        "original_path": str(original_target),
        "original_sha256": original_sha,
        "original_bytes": original_target.stat().st_size,
        "local_path": str(normalized_target),
        "sha256": sha256(normalized_target),
        "width": width,
        "height": height,
    }
    verdict = review_one(
        row, normalized_target,
        SimpleNamespace(codex=args.codex, model=args.model, timeout=args.timeout),
    )
    row["review_verdict"] = verdict["verdict"]
    append_jsonl(ledger, row)
    append_jsonl(args.root / "decisions.jsonl", verdict)
    asset_id = register(args.db, row, verdict)
    result = {"asset_id": asset_id, "candidate": row, "verdict": verdict}
    if args.human_override_admission:
        apply_human_override(
            args.db, args.root, row,
            admission=args.human_override_admission,
            reason=args.human_override_reason,
            approver=args.human_override_approver,
        )
        result["human_override"] = args.human_override_admission
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if verdict["verdict"] == "accepted" or args.human_override_admission else 2


if __name__ == "__main__":
    raise SystemExit(main())
