"""Fulfil bounded visual-material requests from reviewed registry assets first."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sqlite3
from typing import Any, Iterable

from jsonschema import Draft202012Validator

from .cli import DEFAULT_DB, connect


REQUEST_SCHEMA = Path(__file__).resolve().parents[1] / "mission_hub" / "research" / "schemas" / "visual-material-request.schema.json"


def load_request(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator(json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))).validate(value)
    return value


def _excluded_asset_ids(db: sqlite3.Connection, selections: list[str]) -> set[int]:
    if not selections:
        return set()
    placeholders = ",".join("?" for _ in selections)
    return {
        row[0] for row in db.execute(
            f"SELECT DISTINCT asset_id FROM selection WHERE name IN ({placeholders})",
            selections,
        )
    }


def _query_candidates(
    db: sqlite3.Connection,
    query: str,
    allowed_sources: list[str],
    excluded: set[int],
    already_chosen: set[int],
    limit: int,
) -> list[sqlite3.Row]:
    source_clause = ""
    parameters: list[Any] = [query]
    if allowed_sources:
        source_clause = f" AND a.source IN ({','.join('?' for _ in allowed_sources)})"
        parameters.extend(allowed_sources)
    parameters.append(max(limit * 20, 100))
    rows = db.execute(
        f"""SELECT a.id, a.source, a.source_id, a.local_path, a.sha256,
                   a.width, a.height, ts.kind, ts.text, bm25(text_search) AS score
            FROM text_search ts JOIN asset a ON a.id=ts.asset_id
            WHERE text_search MATCH ? AND a.status='reviewed_usable'
              AND a.local_path IS NOT NULL AND a.sha256 IS NOT NULL
              {source_clause}
            ORDER BY score, a.id LIMIT ?""",
        parameters,
    )
    selected: list[sqlite3.Row] = []
    seen = set(excluded) | set(already_chosen)
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        selected.append(row)
        if len(selected) == limit:
            break
    return selected


def _asset_context(db: sqlite3.Connection, asset_id: int) -> dict[str, Any]:
    labels = [
        row[0] for row in db.execute(
            "SELECT DISTINCT name FROM label WHERE asset_id=? AND confidence=1 ORDER BY name LIMIT 30",
            (asset_id,),
        )
    ]
    relationships = [
        {"subject": row[0], "predicate": row[1], "object": row[2]}
        for row in db.execute(
            "SELECT subject, predicate, object FROM relationship WHERE asset_id=? ORDER BY id LIMIT 30",
            (asset_id,),
        )
    ]
    return {"labels": labels, "relationships": relationships}


def fulfil_request(
    db: sqlite3.Connection,
    request: dict[str, Any],
    selection_name: str,
) -> dict[str, Any]:
    if db.execute("SELECT 1 FROM selection WHERE name=? LIMIT 1", (selection_name,)).fetchone():
        raise ValueError(f"selection already exists and is immutable: {selection_name}")
    excluded = _excluded_asset_ids(db, request["exclude_selections"])
    chosen: list[tuple[sqlite3.Row, dict[str, str]]] = []
    chosen_ids: set[int] = set()
    for query in request["candidate_queries"]:
        remaining = request["required_count"] - len(chosen)
        if remaining <= 0:
            break
        rows = _query_candidates(
            db, query["fts_query"], request["allowed_sources"], excluded,
            chosen_ids, remaining,
        )
        chosen.extend((row, query) for row in rows)
        chosen_ids.update(row["id"] for row in rows)

    if chosen:
        db.executemany(
            "INSERT INTO selection(name, asset_id, stratum, ordinal) VALUES (?, ?, ?, ?)",
            (
                (selection_name, row["id"], query["tier"], ordinal)
                for ordinal, (row, query) in enumerate(chosen)
            ),
        )
        db.commit()

    assets = []
    for ordinal, (row, query) in enumerate(chosen):
        assets.append({
            "ordinal": ordinal,
            "asset_id": row["id"],
            "source": row["source"],
            "source_id": row["source_id"],
            "local_path": row["local_path"],
            "sha256": row["sha256"],
            "width": row["width"],
            "height": row["height"],
            "match_tier": query["tier"],
            "matched_query": query["fts_query"],
            "matched_text_kind": row["kind"],
            "matched_text": row["text"],
            **_asset_context(db, row["id"]),
        })
    missing = max(0, request["required_count"] - len(assets))
    manifest: dict[str, Any] = {
        "schema_version": "ninereeds_visual_material_fulfilment_v1",
        "request_id": request["request_id"],
        "selection_name": selection_name if assets else None,
        "status": "fulfilled_from_registry" if missing == 0 else "residual_gap",
        "teaching_claim": request["teaching_claim"],
        "intended_partition": request["intended_partition"],
        "required_count": request["required_count"],
        "selected_count": len(assets),
        "missing_count": missing,
        "selection_rule": "reviewed_usable assets only; ordered by request query tier, FTS rank, and asset identity",
        "assets": assets,
        "acceptance_criteria": request["acceptance_criteria"],
        "commissioning_request": None,
    }
    if missing:
        fallbacks = [item for item in request["fallback_order"] if item != "registry_only"]
        manifest["commissioning_request"] = {
            "schema_version": "ninereeds_visual_material_gap_v1",
            "request_id": f'{request["request_id"]}-gap',
            "teaching_claim": request["teaching_claim"],
            "target_concepts": request["target_concepts"],
            "missing_count": missing,
            "fallback_order": fallbacks,
            "reference_asset_ids": [item["asset_id"] for item in assets],
            "acceptance_criteria": request["acceptance_criteria"],
            "authorization_status": "proposed_not_authorized",
            "generation_dispatched": False,
        }
    return manifest


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("request", type=Path)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    request = load_request(args.request)
    with connect(args.db) as db:
        manifest = fulfil_request(db, request, args.selection)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": manifest["status"],
        "selected": manifest["selected_count"],
        "missing": manifest["missing_count"],
        "manifest": str(args.output),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
