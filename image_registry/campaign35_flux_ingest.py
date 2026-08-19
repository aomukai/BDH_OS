"""Ingest generated Campaign 35 Flux pixels and emit exact slot-binding proposals."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Iterable

from .cli import DEFAULT_DB, DEFAULT_STORE, connect


DEFAULT_SOURCE = "ninereeds_flux_campaign35"


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--source", default=DEFAULT_SOURCE)
    parser.add_argument("--selection", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    generated = [row for path in args.ledger for row in load_jsonl(path)]
    identities = [(row["production_brief_id"], int(row["variant_index"])) for row in generated]
    if len(identities) != len(set(identities)):
        raise ValueError("generation ledgers contain duplicate brief variants")
    hashes = [row["sha256"] for row in generated]
    if len(hashes) != len(set(hashes)):
        raise ValueError("generation ledgers contain pixel-identical variants")
    generated.sort(key=lambda row: (row["production_brief_id"], int(row["variant_index"])))
    inventory = {row["concept_id"]: row for row in load_jsonl(args.inventory)}

    occurrences: dict[str, list[dict[str, Any]]] = {}
    for row in generated:
        for concept_id in row["concept_ids"]:
            occurrences.setdefault(concept_id, []).append(row)
    for concept_id, rows in occurrences.items():
        need = inventory.get(concept_id)
        if need is None or need["route"] != "single_image":
            raise ValueError(f"generated concept is outside authoritative single-image route: {concept_id}")
        if len(rows) != int(need["missing_slots"]):
            raise ValueError(f"generated occurrence count differs for {concept_id}: {len(rows)} != {need['missing_slots']}")
    expected_concepts = {item for item, row in inventory.items() if row["route"] == "single_image"}
    if set(occurrences) != expected_concepts:
        raise ValueError("generated concept partition does not exactly cover authoritative single-image needs")

    source = args.source
    destination = args.store / "blobs" / source / "generated"
    destination.mkdir(parents=True, exist_ok=True)
    args.output.mkdir(parents=True, exist_ok=True)
    asset_ids: dict[tuple[str, int], int] = {}
    with connect(args.db) as db:
        existing_selection = db.execute(
            "SELECT COUNT(*) FROM selection WHERE name=?", (args.selection,),
        ).fetchone()[0]
        if existing_selection:
            raise ValueError(f"selection already exists: {args.selection}")
        for ordinal, row in enumerate(generated):
            variant = int(row["variant_index"])
            source_id = f"{row['production_brief_id']}-v{variant:02d}"
            source_path = args.image_root / f"{source_id}.png"
            if not source_path.is_file() or sha256(source_path) != row["sha256"]:
                raise ValueError(f"generated pixels are missing or hash-mismatched: {source_id}")
            target = destination / f"{row['sha256']}.png"
            if not target.exists():
                partial = target.with_suffix(".png.partial")
                shutil.copyfile(source_path, partial)
                if sha256(partial) != row["sha256"]:
                    partial.unlink(missing_ok=True)
                    raise RuntimeError(f"copied pixel hash mismatch: {source_id}")
                partial.replace(target)
            elif sha256(target) != row["sha256"]:
                raise RuntimeError(f"existing corpus pixel hash mismatch: {target}")
            db.execute(
                """INSERT INTO asset(source,source_id,split,original_url,author,title,
                       declared_bytes,local_path,sha256,width,height,status)
                   VALUES (?,?,'generated',?,'Ninereeds / FLUX.2-klein-4B',?,?,?,?,?,?,'downloaded')
                   ON CONFLICT(source,source_id) DO UPDATE SET local_path=excluded.local_path,
                       sha256=excluded.sha256,declared_bytes=excluded.declared_bytes,
                       width=excluded.width,height=excluded.height,status='downloaded'""",
                (source, source_id, f"campaign35-flux:{source_id}", source_id,
                 target.stat().st_size, str(target), row["sha256"], row["width"], row["height"]),
            )
            asset_id = db.execute(
                "SELECT id FROM asset WHERE source=? AND source_id=?", (source, source_id),
            ).fetchone()[0]
            asset_ids[(row["production_brief_id"], variant)] = asset_id
            db.execute("DELETE FROM text_search WHERE asset_id=?", (asset_id,))
            db.execute("DELETE FROM text_record WHERE asset_id=?", (asset_id,))
            payload = json.dumps(row, ensure_ascii=False, sort_keys=True)
            db.execute(
                """INSERT INTO text_record(asset_id,kind,text,author,model,payload_json)
                   VALUES (?,'generation_prompt',?,'campaign35_flux_generate',?,?)""",
                (asset_id, row["prompt"], row["model"], payload),
            )
            db.execute(
                "INSERT INTO text_search(asset_id,kind,text) VALUES (?,'generation_prompt',?)",
                (asset_id, row["prompt"]),
            )
            db.execute(
                "INSERT INTO selection(name,asset_id,stratum,ordinal) VALUES (?,?,'generated_flux',?)",
                (args.selection, asset_id, ordinal),
            )
        db.commit()

    proposals: list[dict[str, Any]] = []
    for concept_id, rows in sorted(occurrences.items(), key=lambda item: inventory[item[0]]["ordinal"]):
        need = inventory[concept_id]
        slots = need["missing_slot_ids"]
        for row, slot_id in zip(rows, slots, strict=True):
            exposure = int(slot_id.rsplit("-i", 1)[1])
            proposals.append({
                "source": source,
                "source_image_id": f"{row['production_brief_id']}-v{int(row['variant_index']):02d}",
                "slot_id": slot_id, "word": need["word"], "concept": need["word"],
                "concept_id": concept_id, "ordinal": need["ordinal"],
                "exposure_index": exposure,
                "sequence_position": (int(need["ordinal"]) - 1) * 10 + exposure,
                "caption": row["prompt"], "candidate_tier": "generated_flux_coherent_scene",
            })
    proposals.sort(key=lambda row: (row["sequence_position"], row["slot_id"]))
    proposal_path = args.output / "slot_proposals.jsonl"
    proposal_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in proposals),
        encoding="utf-8",
    )
    summary = {
        "schema_version": "ninereeds_campaign35_flux_ingest_v1",
        "assets": len(generated), "slot_proposals": len(proposals),
        "concepts": len(occurrences), "selection": args.selection, "source": source,
        "status": "ingested_pending_mechanical_and_semantic_review",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
