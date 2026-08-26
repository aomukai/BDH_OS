"""Persistent one-word generation claims for Campaign 36 replacement images.

One provider "shot" owns exactly one word and its current remaining deficit.  The
worker may retry the same prompt internally, but must finish or release the whole
shot before claiming another word.  Partial accepted images are retained.  A failed
Flux shot crosses over to ImageGen (and vice versa); after both fail, a revised prompt
starts one final provider cycle.  Exhausting both providers on that revised prompt
routes the word to the representation-ideas handoff.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import secrets
import sqlite3
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign36_word_generation (
    word TEXT PRIMARY KEY,
    concept_id TEXT NOT NULL,
    teaching_sense TEXT NOT NULL,
    ordinal INTEGER NOT NULL UNIQUE,
    target_count INTEGER NOT NULL CHECK(target_count > 0),
    accepted_count INTEGER NOT NULL CHECK(accepted_count >= 0),
    remaining_count INTEGER NOT NULL CHECK(remaining_count >= 0),
    status TEXT NOT NULL CHECK(status IN (
        'review_pending','unclaimed','leased','needs_other_provider',
        'needs_prompt_revision','unresolved','complete'
    )),
    prompt_cycle INTEGER NOT NULL DEFAULT 0 CHECK(prompt_cycle >= 0),
    prompt TEXT,
    max_prompt_revisions INTEGER NOT NULL DEFAULT 1 CHECK(max_prompt_revisions >= 1),
    claim_token TEXT UNIQUE,
    claimed_by TEXT,
    claimed_provider TEXT CHECK(claimed_provider IN ('flux','imagegen')),
    claim_expires_at TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS campaign36_word_generation_attempt (
    id INTEGER PRIMARY KEY,
    word TEXT NOT NULL REFERENCES campaign36_word_generation(word),
    prompt_cycle INTEGER NOT NULL,
    provider TEXT NOT NULL CHECK(provider IN ('flux','imagegen')),
    worker_id TEXT NOT NULL,
    claim_token TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL CHECK(status IN ('leased','finished','expired')),
    requested_count INTEGER NOT NULL,
    produced_count INTEGER,
    accepted_added INTEGER,
    prompt TEXT,
    claimed_at TEXT NOT NULL,
    lease_expires_at TEXT NOT NULL,
    finished_at TEXT,
    evidence_json TEXT,
    UNIQUE(word,prompt_cycle,provider)
);
CREATE INDEX IF NOT EXISTS idx_campaign36_word_generation_status
    ON campaign36_word_generation(status, ordinal);
"""


def now() -> datetime:
    return datetime.now(timezone.utc)


def stamp(value: datetime | None = None) -> str:
    return (value or now()).isoformat(timespec="microseconds").replace("+00:00", "Z")


def read_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def connect(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(path, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    db.executescript(SCHEMA)
    return db


def sync(
    db: sqlite3.Connection,
    *,
    replacement_map: Path,
    selected_assets: Path,
    reviews_complete: bool,
    target_count: int = 10,
) -> dict[str, Any]:
    selected = Counter(row["word"] for row in read_rows(selected_assets))
    contracts = sorted(read_rows(replacement_map), key=lambda row: int(row["ordinal"]))
    changed = 0
    timestamp = stamp()
    db.execute("BEGIN IMMEDIATE")
    try:
        for contract in contracts:
            word = contract["new_word"]
            observed = min(target_count, selected[word])
            existing = db.execute(
                "SELECT * FROM campaign36_word_generation WHERE word=?", (word,)
            ).fetchone()
            if existing is None:
                status = (
                    "complete"
                    if observed >= target_count
                    else "unclaimed"
                    if reviews_complete
                    else "review_pending"
                )
                db.execute(
                    """INSERT INTO campaign36_word_generation(
                           word,concept_id,teaching_sense,ordinal,target_count,
                           accepted_count,remaining_count,status,updated_at
                       ) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (
                        word,
                        contract["new_concept_id"],
                        contract["new_teaching_sense"],
                        int(contract["ordinal"]),
                        target_count,
                        observed,
                        target_count - observed,
                        status,
                        timestamp,
                    ),
                )
                changed += 1
                continue
            if existing["status"] == "leased":
                # Never rewrite a live claim's deficit underneath its worker.
                continue
            has_attempts = db.execute(
                "SELECT 1 FROM campaign36_word_generation_attempt WHERE word=? LIMIT 1",
                (word,),
            ).fetchone() is not None
            if not reviews_complete and not has_attempts:
                # Min-cost flow is allowed to reassign shared candidates while
                # review is open.  These counts are a live preview, not a durable
                # generation achievement, so both gains and regressions are valid.
                accepted = observed
                remaining = target_count - observed
                status = "complete" if remaining == 0 else "review_pending"
            else:
                # Once generation can run, admitted pixels are durable and the
                # accepted count is monotonic across reconciliation ticks.
                accepted = max(int(existing["accepted_count"]), observed)
                remaining = max(0, target_count - accepted)
                status = existing["status"]
                if remaining == 0:
                    status = "complete"
                elif status == "complete":
                    raise ValueError(f"completed word regressed below target: {word}")
                elif status == "review_pending" and reviews_complete:
                    status = "unclaimed"
            prior = (
                int(existing["accepted_count"]), int(existing["remaining_count"]),
                str(existing["status"]),
            )
            current = (accepted, remaining, status)
            cursor = db.execute(
                """UPDATE campaign36_word_generation
                   SET accepted_count=?,remaining_count=?,status=?,updated_at=?
                   WHERE word=?""",
                (accepted, remaining, status, timestamp, word),
            )
            changed += int(prior != current and cursor.rowcount == 1)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return status_summary(db, changed=changed)


def _provider_attempted(
    db: sqlite3.Connection, word: str, prompt_cycle: int, provider: str
) -> bool:
    return (
        db.execute(
            """SELECT 1 FROM campaign36_word_generation_attempt
               WHERE word=? AND prompt_cycle=? AND provider=?
                 AND status IN ('finished','expired')""",
            (word, prompt_cycle, provider),
        ).fetchone()
        is not None
    )


def expire(db: sqlite3.Connection) -> int:
    current = stamp()
    stale = db.execute(
        """SELECT word,claim_token FROM campaign36_word_generation
           WHERE status='leased' AND claim_expires_at<=?""",
        (current,),
    ).fetchall()
    for row in stale:
        db.execute(
            """UPDATE campaign36_word_generation_attempt
               SET status='expired',finished_at=?,evidence_json=COALESCE(
                   evidence_json,'{"reason":"lease_expired_before_finish"}')
               WHERE claim_token=? AND status='leased'""",
            (current, row["claim_token"]),
        )
        db.execute(
            """UPDATE campaign36_word_generation
               SET status='unclaimed',claim_token=NULL,claimed_by=NULL,
                   claimed_provider=NULL,claim_expires_at=NULL,updated_at=?
               WHERE word=? AND claim_token=?""",
            (current, row["word"], row["claim_token"]),
        )
    return len(stale)


def expire_worker_claim(db: sqlite3.Connection, worker_id: str) -> int:
    """Retire a claim left behind by an earlier process with this stable worker ID."""
    current = stamp()
    stale = db.execute(
        """SELECT word,claim_token FROM campaign36_word_generation
           WHERE status='leased' AND claimed_by=?""",
        (worker_id,),
    ).fetchall()
    for row in stale:
        db.execute(
            """UPDATE campaign36_word_generation_attempt
               SET status='expired',finished_at=?,evidence_json=COALESCE(
                   evidence_json,'{"reason":"worker_restarted_before_finish"}')
               WHERE claim_token=? AND status='leased'""",
            (current, row["claim_token"]),
        )
        db.execute(
            """UPDATE campaign36_word_generation
               SET status='unclaimed',claim_token=NULL,claimed_by=NULL,
                   claimed_provider=NULL,claim_expires_at=NULL,updated_at=?
               WHERE word=? AND claim_token=?""",
            (current, row["word"], row["claim_token"]),
        )
    return len(stale)


def claim(
    db: sqlite3.Connection,
    *,
    provider: str,
    worker_id: str,
    lease_seconds: int,
) -> dict[str, Any] | None:
    if provider not in {"flux", "imagegen"}:
        raise ValueError("provider must be flux or imagegen")
    if lease_seconds < 60:
        raise ValueError("lease must be at least 60 seconds")
    db.execute("BEGIN IMMEDIATE")
    try:
        expire(db)
        # Worker IDs are stable systemd instance IDs.  Seeing our own pre-existing
        # lease therefore means the former process died.  Expire it immediately,
        # record the provider attempt, and let the other provider take that word.
        expire_worker_claim(db, worker_id)
        candidates = db.execute(
            """SELECT * FROM campaign36_word_generation
               WHERE status IN ('unclaimed','needs_other_provider')
                 AND remaining_count>0 ORDER BY ordinal"""
        ).fetchall()
        chosen = next(
            (
                row
                for row in candidates
                if not _provider_attempted(
                    db, row["word"], int(row["prompt_cycle"]), provider
                )
            ),
            None,
        )
        if chosen is None:
            db.commit()
            return None
        token = secrets.token_urlsafe(32)
        claimed = now()
        expires_at = claimed + timedelta(seconds=lease_seconds)
        db.execute(
            """INSERT INTO campaign36_word_generation_attempt(
                   word,prompt_cycle,provider,worker_id,claim_token,status,
                   requested_count,prompt,claimed_at,lease_expires_at
               ) VALUES (?,?,?,?,?,'leased',?,?,?,?)""",
            (
                chosen["word"],
                int(chosen["prompt_cycle"]),
                provider,
                worker_id,
                token,
                int(chosen["remaining_count"]),
                chosen["prompt"],
                stamp(claimed),
                stamp(expires_at),
            ),
        )
        db.execute(
            """UPDATE campaign36_word_generation
               SET status='leased',claim_token=?,claimed_by=?,claimed_provider=?,
                   claim_expires_at=?,updated_at=? WHERE word=?""",
            (
                token,
                worker_id,
                provider,
                stamp(expires_at),
                stamp(claimed),
                chosen["word"],
            ),
        )
        db.commit()
        return {
            **dict(chosen),
            "provider": provider,
            "worker_id": worker_id,
            "claim_token": token,
            "requested_count": int(chosen["remaining_count"]),
            "claim_expires_at": stamp(expires_at),
        }
    except Exception:
        db.rollback()
        raise


def renew(
    db: sqlite3.Connection,
    *,
    claim_token: str,
    worker_id: str,
    lease_seconds: int,
) -> str:
    """Extend one live word-atomic claim and its matching attempt lease."""
    if lease_seconds < 60:
        raise ValueError("lease must be at least 60 seconds")
    db.execute("BEGIN IMMEDIATE")
    try:
        renewed_at = stamp()
        expires_at = stamp(now() + timedelta(seconds=lease_seconds))
        word_cursor = db.execute(
            """UPDATE campaign36_word_generation SET claim_expires_at=?,updated_at=?
               WHERE claim_token=? AND claimed_by=? AND status='leased'""",
            (expires_at, renewed_at, claim_token, worker_id),
        )
        attempt_cursor = db.execute(
            """UPDATE campaign36_word_generation_attempt SET lease_expires_at=?
               WHERE claim_token=? AND worker_id=? AND status='leased'""",
            (expires_at, claim_token, worker_id),
        )
        if word_cursor.rowcount != 1 or attempt_cursor.rowcount != 1:
            raise ValueError("claim is missing, expired, or owned by another worker")
        db.commit()
        return expires_at
    except Exception:
        db.rollback()
        raise


def finish(
    db: sqlite3.Connection,
    *,
    claim_token: str,
    worker_id: str,
    produced_count: int,
    accepted_added: int,
    evidence: dict[str, Any],
) -> dict[str, Any]:
    if produced_count < 0 or accepted_added < 0 or accepted_added > produced_count:
        raise ValueError("invalid produced/accepted counts")
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute(
            """SELECT * FROM campaign36_word_generation
               WHERE claim_token=? AND claimed_by=? AND status='leased'""",
            (claim_token, worker_id),
        ).fetchone()
        if row is None:
            raise ValueError("claim is missing, expired, or owned by another worker")
        attempt = db.execute(
            """SELECT * FROM campaign36_word_generation_attempt
               WHERE claim_token=? AND status='leased'""",
            (claim_token,),
        ).fetchone()
        accepted = min(int(row["target_count"]), int(row["accepted_count"]) + accepted_added)
        remaining = int(row["target_count"]) - accepted
        cycle = int(row["prompt_cycle"])
        provider = str(row["claimed_provider"])
        other = "imagegen" if provider == "flux" else "flux"
        if remaining == 0:
            status = "complete"
        elif not _provider_attempted(db, row["word"], cycle, other):
            status = "needs_other_provider"
        elif cycle < int(row["max_prompt_revisions"]):
            status = "needs_prompt_revision"
        else:
            status = "unresolved"
        finished_at = stamp()
        db.execute(
            """UPDATE campaign36_word_generation_attempt
               SET status='finished',produced_count=?,accepted_added=?,
                   finished_at=?,evidence_json=? WHERE id=?""",
            (
                produced_count,
                accepted_added,
                finished_at,
                json.dumps(evidence, ensure_ascii=False, sort_keys=True),
                attempt["id"],
            ),
        )
        db.execute(
            """UPDATE campaign36_word_generation
               SET accepted_count=?,remaining_count=?,status=?,claim_token=NULL,
                   claimed_by=NULL,claimed_provider=NULL,claim_expires_at=NULL,updated_at=?
               WHERE word=?""",
            (accepted, remaining, status, finished_at, row["word"]),
        )
        db.commit()
        return dict(
            db.execute(
                "SELECT * FROM campaign36_word_generation WHERE word=?", (row["word"],)
            ).fetchone()
        )
    except Exception:
        db.rollback()
        raise


def revise_prompt(db: sqlite3.Connection, *, word: str, prompt: str) -> dict[str, Any]:
    if not prompt.strip():
        raise ValueError("revised prompt must be non-empty")
    db.execute("BEGIN IMMEDIATE")
    try:
        row = db.execute(
            "SELECT * FROM campaign36_word_generation WHERE word=?", (word,)
        ).fetchone()
        if row is None or row["status"] != "needs_prompt_revision":
            raise ValueError("word is not awaiting prompt revision")
        cycle = int(row["prompt_cycle"]) + 1
        if cycle > int(row["max_prompt_revisions"]):
            raise ValueError("prompt revision allowance is exhausted")
        db.execute(
            """UPDATE campaign36_word_generation
               SET prompt_cycle=?,prompt=?,status='unclaimed',updated_at=? WHERE word=?""",
            (cycle, prompt.strip(), stamp(), word),
        )
        db.commit()
        return dict(
            db.execute(
                "SELECT * FROM campaign36_word_generation WHERE word=?", (word,)
            ).fetchone()
        )
    except Exception:
        db.rollback()
        raise


def append_unresolved_handoff(
    db: sqlite3.Connection, *, path: Path
) -> dict[str, Any]:
    unresolved = [
        dict(row)
        for row in db.execute(
            """SELECT * FROM campaign36_word_generation
               WHERE status='unresolved' ORDER BY ordinal"""
        )
    ]
    header = "# Words needing image ideas\n"
    if not unresolved:
        body = "\nNothing currently needs ideas.\n"
    else:
        blocks = []
        for row in unresolved:
            attempts = [
                dict(attempt)
                for attempt in db.execute(
                    """SELECT prompt_cycle,provider,produced_count,accepted_added,
                              prompt,evidence_json,finished_at
                       FROM campaign36_word_generation_attempt
                       WHERE word=? ORDER BY id""",
                    (row["word"],),
                )
            ]
            blocks.append(
                "\n".join(
                    [
                        f"## {row['word']}",
                        "",
                        f"- Teaching sense: {row['teaching_sense']}",
                        f"- Accepted: {row['accepted_count']}/{row['target_count']}",
                        f"- Still needed: {row['remaining_count']}",
                        f"- Prompt cycles exhausted: {row['prompt_cycle'] + 1}",
                        f"- Evidence: `{json.dumps(attempts, ensure_ascii=False, sort_keys=True)}`",
                    ]
                )
            )
        body = "\n\n" + "\n\n".join(blocks) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(header + body, encoding="utf-8")
    os.replace(temporary, path)
    return {"unresolved_words": len(unresolved), "path": str(path)}


def status_summary(db: sqlite3.Connection, *, changed: int = 0) -> dict[str, Any]:
    counts = {
        row["status"]: row["count"]
        for row in db.execute(
            """SELECT status,COUNT(*) count FROM campaign36_word_generation
               GROUP BY status ORDER BY status"""
        )
    }
    totals = db.execute(
        """SELECT COUNT(*) words,COALESCE(SUM(target_count),0) target_images,
                  COALESCE(SUM(accepted_count),0) accepted_images,
                  COALESCE(SUM(remaining_count),0) remaining_images
           FROM campaign36_word_generation"""
    ).fetchone()
    return {"changed": changed, "counts": counts, **dict(totals)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    sub = parser.add_subparsers(dest="command", required=True)
    sync_parser = sub.add_parser("sync")
    sync_parser.add_argument("--replacement-map", type=Path, required=True)
    sync_parser.add_argument("--selected-assets", type=Path, required=True)
    sync_parser.add_argument("--reviews-complete", action="store_true")
    claim_parser = sub.add_parser("claim")
    claim_parser.add_argument("--provider", choices=("flux", "imagegen"), required=True)
    claim_parser.add_argument("--worker-id", required=True)
    claim_parser.add_argument("--lease-seconds", type=int, default=1800)
    finish_parser = sub.add_parser("finish")
    finish_parser.add_argument("--claim-token", required=True)
    finish_parser.add_argument("--worker-id", required=True)
    finish_parser.add_argument("--produced-count", type=int, required=True)
    finish_parser.add_argument("--accepted-added", type=int, required=True)
    finish_parser.add_argument("--evidence-json", default="{}")
    revise_parser = sub.add_parser("revise-prompt")
    revise_parser.add_argument("--word", required=True)
    revise_parser.add_argument("--prompt", required=True)
    handoff_parser = sub.add_parser("write-handoff")
    handoff_parser.add_argument("--path", type=Path, required=True)
    sub.add_parser("status")
    args = parser.parse_args()
    with connect(args.db) as db:
        if args.command == "sync":
            result = sync(
                db,
                replacement_map=args.replacement_map,
                selected_assets=args.selected_assets,
                reviews_complete=args.reviews_complete,
            )
        elif args.command == "claim":
            result = claim(
                db,
                provider=args.provider,
                worker_id=args.worker_id,
                lease_seconds=args.lease_seconds,
            )
        elif args.command == "finish":
            result = finish(
                db,
                claim_token=args.claim_token,
                worker_id=args.worker_id,
                produced_count=args.produced_count,
                accepted_added=args.accepted_added,
                evidence=json.loads(args.evidence_json),
            )
        elif args.command == "revise-prompt":
            result = revise_prompt(db, word=args.word, prompt=args.prompt)
        elif args.command == "write-handoff":
            result = append_unresolved_handoff(db, path=args.path)
        else:
            result = status_summary(db)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
