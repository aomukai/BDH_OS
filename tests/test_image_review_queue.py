import sqlite3
from datetime import timedelta
from pathlib import Path

import pytest

from image_registry.cli import connect
from image_registry.review_queue import (
    claim_batch,
    complete_claim,
    create_queue,
    export_filename_list,
    export_results,
    fail_claim,
    queue_status,
    register_worker,
    timestamp,
    utc_now,
)


def _registry(path: Path) -> sqlite3.Connection:
    db = connect(path)
    for ordinal in range(5):
        cursor = db.execute(
            """INSERT INTO asset(source, source_id, split, local_path, sha256)
               VALUES ('test', ?, 'validation', ?, ?)""",
            (f"image-{ordinal}", f"/images/{ordinal}.jpg", str(ordinal) * 64),
        )
        db.execute(
            "INSERT INTO selection VALUES ('all', ?, 'test', ?)",
            (cursor.lastrowid, ordinal),
        )
    db.commit()
    return db


def test_workers_claim_disjoint_bounded_batches(tmp_path: Path) -> None:
    with _registry(tmp_path / "registry.sqlite3") as db:
        assert create_queue(db, "review", "all") == 5
        register_worker(db, "review", "gpu0", "llama.cpp:gpu0", "gemma", 2)
        register_worker(db, "review", "gpu1", "llama.cpp:gpu1", "gemma", 2)
        first = claim_batch(db, "review", "gpu0")
        second = claim_batch(db, "review", "gpu1")
        assert [row["ordinal"] for row in first] == [0, 1]
        assert [row["ordinal"] for row in second] == [2, 3]
        assert not ({row["claim_token"] for row in first} & {row["claim_token"] for row in second})
        with pytest.raises(ValueError, match="must finish"):
            claim_batch(db, "review", "gpu0", 1)
        with pytest.raises(ValueError, match="exceed"):
            claim_batch(db, "review", "gpu1", 3)


def test_completion_unlocks_next_batch_and_wrong_worker_fails(tmp_path: Path) -> None:
    with _registry(tmp_path / "registry.sqlite3") as db:
        create_queue(db, "review", "all")
        register_worker(db, "review", "gpu0", "local", "gemma", 2)
        register_worker(db, "review", "gpu1", "local", "gemma", 2)
        claims = claim_batch(db, "review", "gpu0")
        with pytest.raises(ValueError, match="owned"):
            complete_claim(db, claims[0]["claim_token"], "gpu1", {"ok": True})
        for claim in claims:
            complete_claim(db, claim["claim_token"], "gpu0", {"source_id": claim["source_id"]})
        assert len(export_results(db, "review")) == 2
        assert len(export_filename_list(db, "review")) == 5
        assert [row["ordinal"] for row in claim_batch(db, "review", "gpu0", 1)] == [2]


def test_expired_and_retryable_claims_return_to_queue(tmp_path: Path) -> None:
    with _registry(tmp_path / "registry.sqlite3") as db:
        create_queue(db, "review", "all")
        register_worker(db, "review", "remote", "openrouter", "gemma", 1)
        register_worker(db, "review", "local", "llama.cpp", "gemma", 1)
        register_worker(db, "review", "rescue", "llama.cpp", "gemma", 1)
        claim = claim_batch(db, "review", "remote", lease_seconds=30)[0]
        db.execute(
            "UPDATE review_attempt SET lease_expires_at=? WHERE claim_token=?",
            (timestamp(utc_now() - timedelta(seconds=1)), claim["claim_token"]),
        )
        db.commit()
        replacement = claim_batch(db, "review", "local", lease_seconds=30)[0]
        assert replacement["source_id"] == claim["source_id"]
        assert replacement["attempt_number"] == 2
        fail_claim(db, replacement["claim_token"], "local", {"http": 503}, retry=True)
        retry = claim_batch(db, "review", "rescue", lease_seconds=30)[0]
        assert retry["source_id"] == claim["source_id"]
        assert queue_status(db, "review")["counts"]["leased"] == 1
