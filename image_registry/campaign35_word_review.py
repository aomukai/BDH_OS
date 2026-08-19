from __future__ import annotations

import json
import sqlite3
from typing import Any

from image_registry.review_queue import (
    create_queue,
    ensure_schema as ensure_review_queue_schema,
    queue_status,
)


BINDING_SCHEMA = """
CREATE TABLE IF NOT EXISTS campaign35_word_review_slot_binding (
    queue_name TEXT NOT NULL,
    slot_id TEXT NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    word TEXT NOT NULL,
    concept TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    exposure_index INTEGER NOT NULL,
    sequence_position INTEGER NOT NULL,
    source_caption TEXT,
    candidate_tier TEXT NOT NULL,
    PRIMARY KEY(queue_name, slot_id),
    UNIQUE(queue_name, sequence_position)
);
CREATE INDEX IF NOT EXISTS idx_campaign35_word_review_slot_binding_queue
    ON campaign35_word_review_slot_binding(queue_name, slot_id);
CREATE INDEX IF NOT EXISTS idx_campaign35_word_review_slot_binding_asset
    ON campaign35_word_review_slot_binding(queue_name, asset_id);
CREATE INDEX IF NOT EXISTS idx_campaign35_word_review_slot_binding_word
    ON campaign35_word_review_slot_binding(queue_name, word, sequence_position);
"""

REQUIRED_BINDING_KEYS = {
    "slot_id", "asset_id", "word", "concept", "ordinal",
    "exposure_index", "sequence_position", "candidate_tier",
}


def ensure_schema(db: sqlite3.Connection) -> None:
    db.executescript(BINDING_SCHEMA)


def _int(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int | str):
        raise ValueError(f"{name} must be an integer")
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be an integer") from exc
    if normalized < 0:
        raise ValueError(f"{name} must be non-negative")
    return normalized


def _normalize_bindings(bindings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for binding in bindings:
        missing = REQUIRED_BINDING_KEYS - set(binding)
        if missing:
            raise ValueError(f"binding missing required keys: {sorted(missing)}")
        slot_id = str(binding["slot_id"]).strip()
        if not slot_id:
            raise ValueError("slot_id must be non-empty")
        word = str(binding["word"]).strip()
        concept = str(binding["concept"]).strip()
        if not word or not concept:
            raise ValueError("binding word and concept must be non-empty")
        normalized.append({
            "slot_id": slot_id,
            "asset_id": _int(binding["asset_id"], "asset_id"),
            "word": word,
            "concept": concept,
            "ordinal": _int(binding["ordinal"], "ordinal"),
            "exposure_index": _int(binding["exposure_index"], "exposure_index"),
            "sequence_position": _int(binding["sequence_position"], "sequence_position"),
            "source_caption": binding.get("source_caption"),
            "candidate_tier": str(binding["candidate_tier"]).strip(),
        })
        if not normalized[-1]["candidate_tier"]:
            raise ValueError("candidate_tier must be non-empty")

    unique: list[dict[str, Any]] = []
    observed: dict[str, dict[str, Any]] = {}
    for binding in normalized:
        existing = observed.get(binding["slot_id"])
        if existing is None:
            observed[binding["slot_id"]] = binding
            unique.append(binding)
            continue
        if existing != binding:
            raise ValueError(f"slot_id appears multiple times with conflicting data: {binding['slot_id']}")
    return unique


def _selection_rows(bindings: list[dict[str, Any]]) -> list[tuple[int, int]]:
    by_asset: dict[int, int] = {}
    for binding in bindings:
        prior = by_asset.get(binding["asset_id"])
        if prior is None or binding["sequence_position"] < prior:
            by_asset[binding["asset_id"]] = binding["sequence_position"]
    return [
        (asset_id, ordinal)
        for ordinal, (_, asset_id) in enumerate(sorted(
            (sequence_position, asset_id)
            for asset_id, sequence_position in by_asset.items()
        ))
    ]


def _validate_assets(db: sqlite3.Connection, bindings: list[dict[str, Any]]) -> None:
    for binding in bindings:
        row = db.execute("SELECT id FROM asset WHERE id=?", (binding["asset_id"],)).fetchone()
        if row is None:
            raise ValueError(f"binding references unknown asset: {binding['asset_id']}")


def _snapshot_bindings(db: sqlite3.Connection, queue_name: str) -> list[tuple[Any, ...]]:
    return [
        (row["slot_id"], row["asset_id"], row["word"], row["concept"],
         row["ordinal"], row["exposure_index"], row["sequence_position"],
         row["source_caption"], row["candidate_tier"])
        for row in db.execute(
            """SELECT slot_id, asset_id, word, concept, ordinal, exposure_index,
                      sequence_position, source_caption, candidate_tier
               FROM campaign35_word_review_slot_binding
               WHERE queue_name=? ORDER BY slot_id""",
            (queue_name,),
        )
    ]


def initialize_queue(
    db: sqlite3.Connection,
    queue_name: str,
    bindings: list[dict[str, Any]],
    *,
    selection_name: str | None = None,
) -> dict[str, Any]:
    """Create a campaign-specific review queue from immutable slot bindings."""
    if not queue_name:
        raise ValueError("queue_name is required")
    selection = selection_name or queue_name
    normalized = _normalize_bindings(bindings)
    if not normalized:
        raise ValueError("bindings are required")

    ensure_schema(db)
    ensure_review_queue_schema(db)
    _validate_assets(db, normalized)

    expected_bindings = sorted(
        (
            row["slot_id"], row["asset_id"], row["word"], row["concept"],
            row["ordinal"], row["exposure_index"], row["sequence_position"],
            row.get("source_caption"), row["candidate_tier"],
        ) for row in normalized
    )
    snapshot = _snapshot_bindings(db, queue_name)
    if snapshot:
        if snapshot != expected_bindings:
            raise ValueError(f"immutable slot bindings differ for queue: {queue_name}")
        bindings_created = False
    else:
        db.executemany(
            "INSERT INTO campaign35_word_review_slot_binding("
            "queue_name,slot_id,asset_id,word,concept,ordinal,exposure_index,sequence_position,source_caption,candidate_tier)"
            " VALUES (?,?,?,?,?,?,?,?,?,?)",
            (
                (queue_name, *row)
                for row in (
                    (binding["slot_id"], binding["asset_id"], binding["word"], binding["concept"],
                     binding["ordinal"], binding["exposure_index"], binding["sequence_position"],
                     binding.get("source_caption"), binding["candidate_tier"])
                    for binding in sorted(normalized, key=lambda row: row["slot_id"])
                )
            ),
        )
        bindings_created = True

    expected_selection = _selection_rows(sorted(normalized, key=lambda row: row["slot_id"]))
    existing_selection = [
        (row["asset_id"], row["ordinal"])
        for row in db.execute(
            "SELECT asset_id, ordinal FROM selection WHERE name=? ORDER BY ordinal",
            (selection,),
        )
    ]
    if existing_selection:
        if existing_selection != expected_selection:
            raise ValueError(f"immutable selection differs: {selection}")
        selection_created = False
    else:
        db.executemany(
            "INSERT INTO selection(name, asset_id, stratum, ordinal) VALUES (?, ?, 'campaign35_word_review', ?)",
            ((selection, asset_id, ordinal) for asset_id, ordinal in expected_selection),
        )
        selection_created = True

    expected_queue = expected_selection
    existing_queue = [
        (row["asset_id"], row["ordinal"])
        for row in db.execute(
            "SELECT asset_id, ordinal FROM review_queue WHERE queue_name=? ORDER BY ordinal",
            (queue_name,),
        )
    ]
    if existing_queue:
        if existing_queue != expected_queue:
            raise ValueError(f"immutable queue differs: {queue_name}")
        queue_created = False
    else:
        create_queue(db, queue_name, selection)
        queue_created = True

    db.commit()
    return {
        "queue": queue_name,
        "selection": selection,
        "items": len(expected_selection),
        "slot_bindings": len(expected_bindings),
        "bindings_created": bindings_created,
        "selection_created": selection_created,
        "queue_created": queue_created,
        "status": queue_status(db, queue_name),
    }


def load_bindings_for_asset(
    db: sqlite3.Connection,
    queue_name: str,
    asset_id: int,
) -> list[dict[str, Any]]:
    rows = db.execute(
        """SELECT slot_id, word, concept, ordinal, exposure_index,
                  sequence_position, source_caption, candidate_tier
           FROM campaign35_word_review_slot_binding
           WHERE queue_name=? AND asset_id=?
           ORDER BY sequence_position, slot_id""",
        (queue_name, asset_id),
    ).fetchall()
    return [dict(row) for row in rows]


# Backwards-compatible alias for legacy callers.
create_review_queue = initialize_queue


def main() -> None:
    raise SystemExit(json.dumps({"status": "module-only"}))


if __name__ == "__main__":
    main()
