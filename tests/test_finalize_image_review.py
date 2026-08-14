import json
from pathlib import Path

from image_registry.cli import connect
from image_registry.finalize_review import (
    FINALIZATION_SCHEMA,
    MAIN_QUEUE, USABILITY_QUEUE, WATERMARK_QUEUE,
    apply_decisions, collect_decisions, load_overrides, summarize,
)
from image_registry.review_queue import ensure_schema


def _asset(db, root: Path, source_id: str, parsed: dict) -> int:
    path = root / f"{source_id}.jpg"
    path.write_bytes(source_id.encode())
    import hashlib
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    aid = db.execute("""INSERT INTO asset(source,source_id,split,local_path,sha256,status)
        VALUES ('test',?,'train',?,?,'mechanically_valid')""", (source_id, str(path), digest)).lastrowid
    result = {"ordinal": aid, "source_id": source_id, "worker_id": "gemma", "model": "gemma",
              "parsed": parsed, "schema_errors": []}
    db.execute("INSERT INTO review_queue(queue_name,asset_id,ordinal,status,result_json) VALUES (?,?,?,'completed',?)",
               (MAIN_QUEUE, aid, aid, json.dumps(result)))
    return aid


def _secondary(db, queue: str, aid: int, value: dict) -> None:
    db.execute("INSERT INTO review_queue(queue_name,asset_id,ordinal,status,result_json) VALUES (?,?,?,'completed',?)",
               (queue, aid, aid, json.dumps(value)))


def test_finalizer_applies_luna_overrides_and_quarantines_recoverably(tmp_path: Path) -> None:
    db_path, store = tmp_path / "registry.sqlite3", tmp_path / "store"
    store.mkdir()
    parsed = lambda admission, watermark=False: {
        "admission": admission, "watermark": watermark, "visible_text": False,
        "quality_flags": [], "uncertainties": [], "objects": [], "relationships": [],
        "literal_caption": "A test object.",
    }
    with connect(db_path) as db:
        ensure_schema(db)
        good = _asset(db, store, "good", parsed("usable"))
        cleared_parsed = parsed("unusable")
        cleared_parsed["literal_caption"] = ""
        cleared = _asset(db, store, "cleared", cleared_parsed)
        bad = _asset(db, store, "bad", parsed("usable", True))
        uncertain = _asset(db, store, "uncertain", parsed("usable", True))
        _secondary(db, WATERMARK_QUEUE, bad, {"alarm": "true_watermark_or_added_overlay"})
        _secondary(db, WATERMARK_QUEUE, uncertain, {"alarm": "uncertain"})
        _secondary(db, USABILITY_QUEUE, cleared, {
            "usability": "usable", "reason": "A clear fallback caption.",
            "worker_id": "luna", "model": "luna",
        })
        db.executescript(FINALIZATION_SCHEMA)
        cleared_path = store / "cleared.jpg"
        cleared_quarantine = store / "quarantine" / "earlier-review" / "cleared.jpg"
        cleared_quarantine.parent.mkdir(parents=True)
        cleared_path.rename(cleared_quarantine)
        cleared_sha = db.execute("SELECT sha256 FROM asset WHERE id=?", (cleared,)).fetchone()[0]
        db.execute("UPDATE asset SET local_path=NULL,status='quarantined_unusable' WHERE id=?", (cleared,))
        db.execute(
            """INSERT INTO corpus_removal VALUES (?,?,?,?,?,?,?,?,?)""",
            (cleared, "cleared", str(cleared_path), str(cleared_quarantine), cleared_sha,
             "earlier alarm", "earlier-review", "{}", "2026-08-14T00:00:00Z"),
        )
        db.commit()
        decisions = collect_decisions(db, {"uncertain": {"admission": "usable", "reason": "manual clear"}})
        assert summarize(decisions) == {
            "total": 4, "usable": 3, "unusable": 1,
            "routes": {"gemma": 1, "luna_usability": 1, "luna_watermark": 1, "manual_override": 1},
        }
        apply_decisions(db, decisions, store)
        assert db.execute("select status from asset where id=?", (good,)).fetchone()[0] == "reviewed_usable"
        removed = db.execute("select status,local_path from asset where id=?", (bad,)).fetchone()
        assert tuple(removed) == ("quarantined_unusable", None)
        assert cleared_path.read_bytes() == b"cleared"
        assert not cleared_quarantine.exists()
        assert db.execute("select count(*) from corpus_removal where asset_id=?", (cleared,)).fetchone()[0] == 0
        quarantine = Path(db.execute("select quarantine_path from corpus_removal where asset_id=?", (bad,)).fetchone()[0])
        assert quarantine.read_bytes() == b"bad"
        assert db.execute("select count(*) from text_record where kind='reviewed_caption'").fetchone()[0] == 3
        fallback = db.execute(
            "select text,author,model from text_record where asset_id=? and kind='reviewed_caption'",
            (cleared,),
        ).fetchone()
        assert tuple(fallback) == ("A clear fallback caption.", "luna", "luna")
        apply_decisions(db, decisions, store)
