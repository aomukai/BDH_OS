import hashlib
import json
import sqlite3

import pytest

from image_registry.campaign35_word_rerun import build_rerun


def _write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _fixture(tmp_path):
    db = sqlite3.connect(":memory:")
    db.row_factory = sqlite3.Row
    db.executescript(
        """
        CREATE TABLE asset (
          id INTEGER PRIMARY KEY, status TEXT, local_path TEXT, sha256 TEXT,
          source TEXT, source_id TEXT, width INTEGER, height INTEGER
        );
        CREATE TABLE campaign35_word_review_slot_binding (
          queue_name TEXT, slot_id TEXT, asset_id INTEGER, word TEXT, concept TEXT
        );
        """
    )
    decisions = []
    pools = []
    for ordinal in range(1, 2501):
        word = f"word-{ordinal}"
        candidates = []
        for exposure in range(1, 12):
            asset_id = (ordinal - 1) * 11 + exposure
            digest = hashlib.sha256(str(asset_id).encode()).hexdigest()
            status = "deleted_watermark" if (ordinal, exposure) == (1, 3) else "reviewed_usable"
            local_path = None if status.startswith("deleted_") else f"/images/{asset_id}.jpg"
            db.execute(
                "INSERT INTO asset VALUES (?,?,?,?,?,?,?,?)",
                (asset_id, status, local_path, digest, "test", str(asset_id), 10, 10),
            )
            candidates.append({
                "asset_id": asset_id, "sha256": digest, "caption": word,
                "source": "test", "source_id": str(asset_id), "path": local_path,
            })
        pools.append({"ordinal": ordinal, "word": word, "candidates": candidates})
        for exposure in range(1, 11):
            position = (ordinal - 1) * 10 + exposure
            disposition = "target_not_visible" if ordinal == 1 and exposure > 1 else "accepted"
            asset_id = (ordinal - 1) * 11 + exposure
            decisions.append({
                "slot_id": f"c{ordinal:04d}-i{exposure:02d}",
                "sequence_position": position, "ordinal": ordinal,
                "concept": word, "concept_id": word, "word": word,
                "exposure_index": exposure, "disposition": disposition,
                "asset_id": asset_id, "sha256": hashlib.sha256(str(asset_id).encode()).hexdigest(),
            })
            db.execute(
                "INSERT INTO campaign35_word_review_slot_binding VALUES (?,?,?,?,?)",
                ("prior", f"c{ordinal:04d}-i{exposure:02d}", asset_id, word, word),
            )
    db.commit()
    decisions_path = tmp_path / "decisions.jsonl"
    pools_path = tmp_path / "pools.jsonl"
    _write_jsonl(decisions_path, decisions)
    _write_jsonl(pools_path, pools)
    return db, decisions_path, pools_path


def test_rerun_protects_accepts_and_never_recycles_attempted_or_deleted(tmp_path):
    db, decisions, pools = _fixture(tmp_path)
    output = tmp_path / "round"
    summary = build_rerun(db, decisions, pools, output, prior_queues=["prior"])

    assert summary["protected_accepted_slots"] == 24_991
    assert summary["new_registry_review_slots"] == 1
    assert summary["external_wishlist_slots"] == 8
    proposal = [json.loads(line) for line in (output / "selection_proposal.jsonl").read_text().splitlines()]
    assert proposal[0]["asset_id"] == 11
    assert proposal[0]["asset_id"] != 3
    assert summary["exact_partition"] is True

    first = (output / "summary.json").read_bytes()
    summary2 = build_rerun(db, decisions, pools, output, prior_queues=["prior"])
    assert summary2 == summary
    assert (output / "summary.json").read_bytes() == first


def test_rerun_refuses_to_protect_a_deleted_accept(tmp_path):
    db, decisions, pools = _fixture(tmp_path)
    rows = [json.loads(line) for line in decisions.read_text().splitlines()]
    rows[0]["asset_id"] = 3
    rows[0]["sha256"] = hashlib.sha256(b"3").hexdigest()
    _write_jsonl(decisions, rows)
    with pytest.raises(ValueError, match="unavailable asset"):
        build_rerun(db, decisions, pools, tmp_path / "round", prior_queues=["prior"])
