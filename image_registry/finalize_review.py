"""Project completed Gemma/Luna evidence into the canonical image registry."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Iterable

from .cli import DEFAULT_DB, DEFAULT_STORE, connect
from .review_queue import ensure_schema, timestamp, utc_now


MAIN_QUEUE = "visual-corpus-review-v1"
WATERMARK_QUEUE = "visual-corpus-watermark-luna-v1"
USABILITY_QUEUE = "visual-corpus-unusable-luna-v1"
DECISION_VERSION = "final-review-v1"
USABLE_COMMIT_BATCH = 250


FINALIZATION_SCHEMA = """
CREATE TABLE IF NOT EXISTS review_decision (
    asset_id INTEGER PRIMARY KEY REFERENCES asset(id),
    decision_version TEXT NOT NULL,
    admission TEXT NOT NULL CHECK(admission IN ('usable','unusable')),
    reason TEXT NOT NULL,
    decision_json TEXT NOT NULL,
    decision_sha256 TEXT NOT NULL,
    decided_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS corpus_removal (
    asset_id INTEGER PRIMARY KEY REFERENCES asset(id),
    source_id TEXT NOT NULL,
    original_path TEXT NOT NULL,
    quarantine_path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    reason TEXT NOT NULL,
    adjudication_queue TEXT NOT NULL,
    adjudication_json TEXT NOT NULL,
    removed_at TEXT NOT NULL
);
"""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_overrides(path: Path | None) -> dict[str, dict[str, str]]:
    if path is None:
        return {}
    value = json.loads(path.read_text(encoding="utf-8"))
    if value.get("schema_version") != "ninereeds_image_review_overrides_v1":
        raise ValueError("unknown final-review override schema")
    result: dict[str, dict[str, str]] = {}
    for row in value.get("overrides", []):
        if row.get("admission") not in {"usable", "unusable"}:
            raise ValueError("override admission must be usable or unusable")
        source_id = str(row.get("source_id", "")).strip()
        reason = str(row.get("reason", "")).strip()
        if not source_id or not reason or source_id in result:
            raise ValueError("override requires a unique source_id and reason")
        result[source_id] = {"admission": row["admission"], "reason": reason}
    return result


def _completed(db: sqlite3.Connection, queue: str) -> dict[int, dict[str, Any]]:
    counts = {
        row["status"]: row["count"]
        for row in db.execute(
            "SELECT status,COUNT(*) count FROM review_queue WHERE queue_name=? GROUP BY status",
            (queue,),
        )
    }
    if not counts or set(counts) != {"completed"}:
        raise ValueError(f"queue is not completely reconciled: {queue} {counts}")
    return {
        row["asset_id"]: json.loads(row["result_json"])
        for row in db.execute(
            "SELECT asset_id,result_json FROM review_queue WHERE queue_name=?",
            (queue,),
        )
    }


def collect_decisions(
    db: sqlite3.Connection,
    overrides: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    ensure_schema(db)
    main = _completed(db, MAIN_QUEUE)
    watermark = _completed(db, WATERMARK_QUEUE)
    usability = _completed(db, USABILITY_QUEUE)
    known_source_ids = {
        row["source_id"]
        for row in db.execute(
            """SELECT a.source_id FROM asset a
               JOIN review_queue q ON q.asset_id=a.id
               WHERE q.queue_name=?""",
            (MAIN_QUEUE,),
        )
    }
    unknown_overrides = sorted(set(overrides) - known_source_ids)
    if unknown_overrides:
        raise ValueError("override source_id is not in the completed main queue: " + ", ".join(unknown_overrides))

    decisions: list[dict[str, Any]] = []
    used_overrides: set[str] = set()
    for asset_id, main_record in sorted(main.items(), key=lambda item: item[1]["ordinal"]):
        asset = db.execute("SELECT * FROM asset WHERE id=?", (asset_id,)).fetchone()
        parsed = main_record.get("parsed") or {}
        watermark_record = watermark.get(asset_id)
        usability_record = usability.get(asset_id)
        alarm = None if watermark_record is None else watermark_record.get("alarm")
        luna_usability = None if usability_record is None else usability_record.get("usability")
        admission: str | None = None
        reason: str | None = None
        evidence_route: str

        if alarm == "true_watermark_or_added_overlay":
            admission, reason, evidence_route = "unusable", "confirmed_watermark_or_overlay", "luna_watermark"
        elif alarm == "uncertain":
            evidence_route = "manual_override_required"
        elif parsed.get("admission") == "unusable":
            evidence_route = "luna_usability"
            if luna_usability == "usable":
                admission, reason = "usable", "luna_cleared_gemma_usability_alarm"
            elif luna_usability == "unusable":
                admission, reason = "unusable", "luna_confirmed_visual_unusable"
            elif luna_usability == "uncertain":
                evidence_route = "manual_override_required"
            else:
                raise ValueError(f"missing Luna usability evidence for asset {asset_id}")
        elif parsed.get("admission") == "uncertain":
            evidence_route = "manual_override_required"
        elif parsed.get("admission") == "usable":
            admission, reason, evidence_route = "usable", "gemma_usable", "gemma"
        else:
            raise ValueError(f"invalid Gemma admission for asset {asset_id}")

        if admission is None:
            override = overrides.get(asset["source_id"])
            if override is None:
                raise ValueError(f"unresolved asset requires an explicit override: {asset['source_id']}")
            admission, reason, evidence_route = override["admission"], override["reason"], "manual_override"
            used_overrides.add(asset["source_id"])

        document = {
            "schema_version": "ninereeds_image_review_decision_v1",
            "decision_version": DECISION_VERSION,
            "asset_id": asset_id,
            "source": asset["source"],
            "source_id": asset["source_id"],
            "sha256": asset["sha256"],
            "admission": admission,
            "reason": reason,
            "evidence_route": evidence_route,
            "main_review": main_record,
            "watermark_review": watermark_record,
            "usability_review": usability_record,
        }
        decisions.append({"asset": dict(asset), "document": document})
    if used_overrides != set(overrides):
        raise ValueError("an override did not resolve an uncertain final decision")
    return decisions


def summarize(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    admissions = Counter(row["document"]["admission"] for row in decisions)
    routes = Counter(row["document"]["evidence_route"] for row in decisions)
    return {
        "total": len(decisions),
        "usable": admissions["usable"],
        "unusable": admissions["unusable"],
        "routes": dict(sorted(routes.items())),
    }


def _quarantine_path(store_root: Path, asset: dict[str, Any]) -> Path:
    source = Path(asset["local_path"])
    try:
        relative = source.resolve().relative_to(store_root.resolve())
    except ValueError as exc:
        raise ValueError(f"asset is outside the corpus store: {source}") from exc
    return store_root / "quarantine" / DECISION_VERSION / relative


def _existing_removal(db: sqlite3.Connection, asset: dict[str, Any]) -> sqlite3.Row | None:
    removal = db.execute("SELECT * FROM corpus_removal WHERE asset_id=?", (asset["id"],)).fetchone()
    if removal is None:
        return None
    quarantine = Path(removal["quarantine_path"])
    if removal["sha256"] != asset["sha256"] or not quarantine.is_file():
        raise ValueError(f"invalid prior quarantine record: {asset['source_id']}")
    if _sha256(quarantine) != asset["sha256"]:
        raise ValueError(f"quarantined asset bytes changed: {asset['source_id']}")
    return removal


def _restore_prior_quarantine(
    db: sqlite3.Connection,
    asset: dict[str, Any],
    removal: sqlite3.Row,
) -> Path:
    source = Path(removal["original_path"])
    quarantine = Path(removal["quarantine_path"])
    source.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        if not source.is_file() or _sha256(source) != asset["sha256"]:
            raise ValueError(f"cannot restore over changed asset: {asset['source_id']}")
    else:
        shutil.move(str(quarantine), str(source))
    db.execute("DELETE FROM corpus_removal WHERE asset_id=?", (asset["id"],))
    db.execute("UPDATE asset SET local_path=? WHERE id=?", (str(source), asset["id"]))
    return source


def _caption_and_provenance(document: dict[str, Any]) -> tuple[str, str, str]:
    main = document["main_review"]
    caption = str((main.get("parsed") or {}).get("literal_caption") or "").strip()
    if caption:
        return caption, main["worker_id"], main["model"]
    usability = document.get("usability_review") or {}
    if usability.get("usability") == "usable":
        caption = str(usability.get("reason") or "").strip()
        if caption.lower().startswith("usable:"):
            caption = caption.split(":", 1)[1].strip()
        if caption:
            return caption, usability["worker_id"], usability["model"]
    raise ValueError(f"usable asset has no reviewed caption: {document['source_id']}")


def apply_decisions(
    db: sqlite3.Connection,
    decisions: list[dict[str, Any]],
    store_root: Path,
) -> None:
    db.executescript(FINALIZATION_SCHEMA)
    pending_usable = 0
    for row in decisions:
        asset, document = row["asset"], row["document"]
        encoded = _canonical(document)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
        existing = db.execute("SELECT * FROM review_decision WHERE asset_id=?", (asset["id"],)).fetchone()
        if existing is not None:
            if existing["decision_sha256"] != digest:
                raise ValueError(f"final decision changed for asset {asset['id']}")
            continue
        removal = _existing_removal(db, asset)
        if removal is not None and document["admission"] == "usable":
            source = _restore_prior_quarantine(db, asset, removal)
            removal = None
        else:
            source = Path(asset["local_path"] or "")
        if removal is None and (not source.is_file() or _sha256(source) != asset["sha256"]):
            raise ValueError(f"asset bytes are missing or changed: {asset['source_id']}")
        now = timestamp(utc_now())
        if document["admission"] == "usable":
            caption, caption_author, caption_model = _caption_and_provenance(document)
            db.execute("DELETE FROM text_search WHERE asset_id=? AND kind='reviewed_caption'", (asset["id"],))
            db.execute("DELETE FROM text_record WHERE asset_id=? AND kind='reviewed_caption'", (asset["id"],))
            db.execute(
                """INSERT INTO text_record(asset_id,kind,text,author,model,payload_json)
                   VALUES (?,'reviewed_caption',?,?,?,?)""",
                (asset["id"], caption, caption_author, caption_model, encoded),
            )
            db.execute(
                "INSERT INTO text_search(asset_id,kind,text) VALUES (?,'reviewed_caption',?)",
                (asset["id"], caption),
            )
            db.execute("UPDATE asset SET status='reviewed_usable' WHERE id=?", (asset["id"],))
        else:
            if removal is not None:
                target = Path(removal["quarantine_path"])
            else:
                target = _quarantine_path(store_root, asset)
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists():
                    if _sha256(target) != asset["sha256"]:
                        raise ValueError(f"quarantine collision: {target}")
                else:
                    shutil.move(str(source), str(target))
                db.execute(
                    """INSERT INTO corpus_removal(asset_id,source_id,original_path,quarantine_path,
                           sha256,reason,adjudication_queue,adjudication_json,removed_at)
                       VALUES (?,?,?,?,?,?,?,?,?)""",
                    (asset["id"], asset["source_id"], str(source), str(target), asset["sha256"],
                     document["reason"], DECISION_VERSION, encoded, now),
                )
            db.execute(
                """UPDATE corpus_removal SET reason=?,adjudication_queue=?,adjudication_json=?
                   WHERE asset_id=?""",
                (document["reason"], DECISION_VERSION, encoded, asset["id"]),
            )
            db.execute("DELETE FROM text_search WHERE asset_id=? AND kind='reviewed_caption'", (asset["id"],))
            db.execute("DELETE FROM text_record WHERE asset_id=? AND kind='reviewed_caption'", (asset["id"],))
            db.execute("UPDATE asset SET local_path=NULL,status='quarantined_unusable' WHERE id=?", (asset["id"],))
        db.execute(
            "INSERT INTO review_decision VALUES (?,?,?,?,?,?,?)",
            (asset["id"], DECISION_VERSION, document["admission"], document["reason"], encoded, digest, now),
        )
        if document["admission"] == "unusable":
            # Keep filesystem moves and their recovery ledger atomically adjacent.
            db.commit()
            pending_usable = 0
        else:
            pending_usable += 1
            if pending_usable >= USABLE_COMMIT_BATCH:
                db.commit()
                pending_usable = 0
    db.commit()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--store-root", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--overrides", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--expected-usable", type=int)
    parser.add_argument("--expected-unusable", type=int)
    args = parser.parse_args(list(argv) if argv is not None else None)
    overrides = load_overrides(args.overrides)
    with connect(args.db) as db:
        decisions = collect_decisions(db, overrides)
        summary = summarize(decisions)
        for key in ("usable", "unusable"):
            expected = getattr(args, f"expected_{key}")
            if expected is not None and summary[key] != expected:
                raise ValueError(f"{key} frontier changed: expected {expected}, found {summary[key]}")
        if args.apply:
            if args.expected_usable is None or args.expected_unusable is None:
                raise ValueError("--apply requires both expected counts")
            apply_decisions(db, decisions, args.store_root)
    receipt = {
        "schema_version": "ninereeds_image_review_finalization_receipt_v1",
        "applied": args.apply,
        "decision_version": DECISION_VERSION,
        **summary,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
