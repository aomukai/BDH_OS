from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import shutil
import sqlite3
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable


DEFAULT_DB = Path("training_data/image_registry/registry.sqlite3")
DEFAULT_STORE = Path("/media/aomukai/FILES/Ninereeds/image-corpus")


SCHEMA = """
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS asset (
    id INTEGER PRIMARY KEY,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL,
    split TEXT NOT NULL,
    original_url TEXT,
    landing_url TEXT,
    thumbnail_url TEXT,
    license_url TEXT,
    author TEXT,
    title TEXT,
    declared_bytes INTEGER,
    declared_md5 TEXT,
    rotation INTEGER,
    local_path TEXT,
    sha256 TEXT,
    width INTEGER,
    height INTEGER,
    status TEXT NOT NULL DEFAULT 'metadata_only',
    UNIQUE(source, source_id)
);
CREATE TABLE IF NOT EXISTS label (
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    confidence REAL NOT NULL,
    annotation_source TEXT NOT NULL,
    PRIMARY KEY(asset_id, name, confidence, annotation_source)
);
CREATE TABLE IF NOT EXISTS object_box (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    xmin REAL NOT NULL, xmax REAL NOT NULL,
    ymin REAL NOT NULL, ymax REAL NOT NULL,
    occluded INTEGER NOT NULL,
    truncated INTEGER NOT NULL,
    group_of INTEGER NOT NULL,
    depiction INTEGER NOT NULL,
    inside INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS relationship (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    predicate TEXT NOT NULL,
    object TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS text_record (
    id INTEGER PRIMARY KEY,
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    text TEXT NOT NULL,
    author TEXT NOT NULL,
    model TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE VIRTUAL TABLE IF NOT EXISTS text_search USING fts5(
    asset_id UNINDEXED, kind, text, tokenize='unicode61'
);
CREATE TABLE IF NOT EXISTS selection (
    name TEXT NOT NULL,
    asset_id INTEGER NOT NULL REFERENCES asset(id) ON DELETE CASCADE,
    stratum TEXT NOT NULL,
    ordinal INTEGER NOT NULL,
    PRIMARY KEY(name, asset_id),
    UNIQUE(name, ordinal)
);
CREATE TABLE IF NOT EXISTS mechanical_check (
    asset_id INTEGER PRIMARY KEY REFERENCES asset(id) ON DELETE CASCADE,
    decoded INTEGER NOT NULL,
    image_format TEXT,
    image_mode TEXT,
    perceptual_hash TEXT,
    reasons_json TEXT NOT NULL DEFAULT '[]',
    checked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_asset_source_id ON asset(source, source_id);
CREATE INDEX IF NOT EXISTS idx_label_name ON label(name);
CREATE INDEX IF NOT EXISTS idx_box_name ON object_box(name);
CREATE INDEX IF NOT EXISTS idx_relation_predicate ON relationship(predicate);
CREATE INDEX IF NOT EXISTS idx_selection_name ON selection(name, ordinal);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA busy_timeout = 30000")
    db.execute("PRAGMA journal_mode = WAL")
    db.executescript(SCHEMA)
    return db


def _class_names(path: Path) -> dict[str, str]:
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return {row["LabelName"]: row["DisplayName"] for row in csv.DictReader(handle)}


def _asset_ids(db: sqlite3.Connection, source: str) -> dict[str, int]:
    return {
        row["source_id"]: row["id"]
        for row in db.execute("SELECT id, source_id FROM asset WHERE source = ?", (source,))
    }


def import_open_images(db: sqlite3.Connection, metadata_dir: Path) -> None:
    source = "open_images_v7"
    classes = _class_names(metadata_dir / "classes_boxable.csv")
    attributes: dict[str, str] = {}
    with (metadata_dir / "attribute_names.csv").open(newline="", encoding="utf-8") as handle:
        for mid, name, *_ in csv.reader(handle):
            attributes[mid] = name
    names = classes | attributes

    with (metadata_dir / "image_metadata.csv").open(newline="", encoding="utf-8") as handle:
        rows = []
        for row in csv.DictReader(handle):
            rotation = row["Rotation"].strip()
            rows.append((
                source, row["ImageID"], row["Subset"], row["OriginalURL"],
                row["OriginalLandingURL"], row["Thumbnail300KURL"], row["License"],
                row["Author"], row["Title"], int(row["OriginalSize"] or 0),
                row["OriginalMD5"], int(float(rotation)) if rotation else None,
            ))
        db.executemany(
            """INSERT INTO asset(
                   source, source_id, split, original_url, landing_url, thumbnail_url,
                   license_url, author, title, declared_bytes, declared_md5, rotation
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(source, source_id) DO UPDATE SET
                   original_url=excluded.original_url, landing_url=excluded.landing_url,
                   thumbnail_url=excluded.thumbnail_url, license_url=excluded.license_url,
                   author=excluded.author, title=excluded.title,
                   declared_bytes=excluded.declared_bytes, declared_md5=excluded.declared_md5,
                   rotation=excluded.rotation""",
            rows,
        )
    ids = _asset_ids(db, source)

    # A source import is a reproducible projection of downloaded metadata. Clear
    # that projection so reruns cannot duplicate boxes or relationships.
    source_asset_ids = tuple(ids.values())
    if source_asset_ids:
        db.execute("DELETE FROM label WHERE asset_id IN (SELECT id FROM asset WHERE source=?)", (source,))
        db.execute("DELETE FROM object_box WHERE asset_id IN (SELECT id FROM asset WHERE source=?)", (source,))
        db.execute("DELETE FROM relationship WHERE asset_id IN (SELECT id FROM asset WHERE source=?)", (source,))

    with (metadata_dir / "image_labels.csv").open(newline="", encoding="utf-8") as handle:
        rows = (
            (ids[row["ImageID"]], names.get(row["LabelName"], row["LabelName"]),
             float(row["Confidence"]), row["Source"])
            for row in csv.DictReader(handle) if row["ImageID"] in ids
        )
        db.executemany("INSERT OR IGNORE INTO label VALUES (?, ?, ?, ?)", rows)

    with (metadata_dir / "boxes.csv").open(newline="", encoding="utf-8") as handle:
        rows = (
            (ids[row["ImageID"]], names.get(row["LabelName"], row["LabelName"]),
             float(row["XMin"]), float(row["XMax"]), float(row["YMin"]), float(row["YMax"]),
             int(row["IsOccluded"]), int(row["IsTruncated"]), int(row["IsGroupOf"]),
             int(row["IsDepiction"]), int(row["IsInside"]))
            for row in csv.DictReader(handle) if row["ImageID"] in ids
        )
        db.executemany(
            """INSERT INTO object_box(
                   asset_id, name, xmin, xmax, ymin, ymax,
                   occluded, truncated, group_of, depiction, inside
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )

    with (metadata_dir / "relationships.csv").open(newline="", encoding="utf-8") as handle:
        rows = (
            (ids[row["ImageID"]], names.get(row["LabelName1"], row["LabelName1"]),
             row["RelationshipLabel"], names.get(row["LabelName2"], row["LabelName2"]))
            for row in csv.DictReader(handle) if row["ImageID"] in ids
        )
        db.executemany(
            "INSERT INTO relationship(asset_id, subject, predicate, object) VALUES (?, ?, ?, ?)",
            rows,
        )

    # Source metadata is searchable immediately; reviewed captions append later.
    db.execute("DELETE FROM text_search WHERE kind = 'source_terms'")
    db.execute("DELETE FROM text_record WHERE kind = 'source_terms'")
    terms: dict[int, set[str]] = defaultdict(set)
    for row in db.execute("SELECT asset_id, name FROM label WHERE confidence = 1"):
        terms[row["asset_id"]].add(row["name"])
    for row in db.execute("SELECT asset_id, subject, predicate, object FROM relationship"):
        terms[row["asset_id"]].add(f'{row["subject"]} {row["predicate"]} {row["object"]}')
    records = [(asset_id, "source_terms", "; ".join(sorted(values)), "open_images")
               for asset_id, values in terms.items()]
    db.executemany(
        "INSERT INTO text_record(asset_id, kind, text, author) VALUES (?, ?, ?, ?)", records
    )
    db.executemany(
        "INSERT INTO text_search(asset_id, kind, text) VALUES (?, ?, ?)",
        ((asset_id, kind, text) for asset_id, kind, text, _ in records),
    )
    db.commit()


def select_candidates(db: sqlite3.Connection, name: str, size: int, seed: int) -> None:
    if size < 10:
        raise ValueError("selection size must be at least 10")
    rng = random.Random(seed)
    db.execute("DELETE FROM selection WHERE name = ?", (name,))
    chosen: set[int] = set()
    strata: list[tuple[str, int, list[int]]] = []

    relation_n = round(size * 0.35)
    count_n = round(size * 0.25)
    relation_ids = [row[0] for row in db.execute(
        """SELECT asset_id FROM relationship GROUP BY asset_id
           HAVING COUNT(*) >= 2 ORDER BY asset_id"""
    )]
    rng.shuffle(relation_ids)
    strata.append(("relationship", relation_n, relation_ids))

    count_ids = [row[0] for row in db.execute(
        """SELECT asset_id FROM object_box WHERE group_of=0 AND depiction=0
           GROUP BY asset_id, name HAVING COUNT(*) BETWEEN 2 AND 5 ORDER BY asset_id"""
    )]
    rng.shuffle(count_ids)
    strata.append(("exact_count", count_n, count_ids))

    diverse_ids = [row[0] for row in db.execute(
        """SELECT asset_id FROM label WHERE confidence=1 GROUP BY asset_id
           HAVING COUNT(DISTINCT name) >= 4 ORDER BY asset_id"""
    )]
    rng.shuffle(diverse_ids)
    strata.append(("diverse_scene", size - relation_n - count_n, diverse_ids))

    ordinal = 0
    for stratum, wanted, candidates in strata:
        added = 0
        for asset_id in candidates:
            if asset_id in chosen:
                continue
            chosen.add(asset_id)
            db.execute("INSERT INTO selection VALUES (?, ?, ?, ?)",
                       (name, asset_id, stratum, ordinal))
            ordinal += 1
            added += 1
            if added == wanted:
                break
        if added != wanted:
            raise RuntimeError(f"not enough candidates for {stratum}: {added}/{wanted}")
    db.commit()


def select_production(
    db: sqlite3.Connection,
    name: str,
    source: str,
    exclude_selection: str,
) -> int:
    existing = db.execute(
        "SELECT COUNT(*) FROM selection WHERE name=?", (name,)
    ).fetchone()[0]
    if existing:
        raise ValueError(f"selection already exists: {name}")
    excluded = db.execute(
        "SELECT COUNT(*) FROM selection WHERE name=?", (exclude_selection,)
    ).fetchone()[0]
    if not excluded:
        raise ValueError(f"excluded selection is empty or missing: {exclude_selection}")
    rows = db.execute(
        """SELECT a.id FROM asset a
           WHERE a.source=? AND NOT EXISTS (
               SELECT 1 FROM selection excluded
               WHERE excluded.name=? AND excluded.asset_id=a.id
           ) ORDER BY a.source_id""",
        (source, exclude_selection),
    ).fetchall()
    db.executemany(
        "INSERT INTO selection VALUES (?, ?, 'production', ?)",
        ((name, row["id"], ordinal) for ordinal, row in enumerate(rows)),
    )
    db.commit()
    return len(rows)


def import_flux_artifacts(
    db: sqlite3.Connection,
    mission_hub_db: Path,
    store: Path,
    selection_name: str,
) -> int:
    source = "ninereeds_flux"
    destination = store / "blobs" / source / "generated"
    destination.mkdir(parents=True, exist_ok=True)
    mission = sqlite3.connect(mission_hub_db)
    mission.row_factory = sqlite3.Row
    rows = mission.execute(
        """SELECT a.id, a.sha256, a.byte_size, a.manifest_json, l.uri
           FROM artifacts a JOIN artifact_locations l ON l.artifact_id=a.id
           WHERE a.kind='visual_candidate' AND l.machine_id='mission-hub'
             AND l.available=1
           ORDER BY a.created_at, a.id"""
    ).fetchall()
    if not rows:
        raise ValueError("Mission Hub has no locally available FLUX visual candidates")
    distinct = {row["id"]: row for row in rows}
    selection_names = [selection_name, f"{selection_name}-accepted", f"{selection_name}-pending"]
    # Imports are resumable. Existing rows retain deterministic ordinals and
    # are refreshed from the authoritative Mission Hub evidence below.

    evidence: dict[str, dict[str, dict[str, object]]] = {
        "visual_inspection_report": {}, "visual_review_report": {},
    }
    for kind in evidence:
        reports = mission.execute(
            """SELECT a.id, a.created_at, a.manifest_json, l.uri
               FROM artifacts a JOIN artifact_locations l ON l.artifact_id=a.id
               WHERE a.kind=? AND l.machine_id='mission-hub' AND l.available=1
               ORDER BY a.created_at, a.id""",
            (kind,),
        )
        for report in reports:
            try:
                document = json.loads(Path(report["uri"]).read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                document = json.loads(report["manifest_json"])
            items = document.get("items", [])
            if not items and document.get("asset_sha256"):
                items = [document]
            for item in items:
                result = item.get("result", item)
                digest = item.get("asset_sha256") or result.get("asset_sha256")
                if digest:
                    evidence[kind][digest] = {
                        "artifact_id": report["id"], "created_at": report["created_at"],
                        "result": result,
                    }
    mission.close()

    for ordinal, row in enumerate(distinct.values()):
        manifest = json.loads(row["manifest_json"])
        source_path = Path(row["uri"])
        if (
            not source_path.is_file()
            or source_path.stat().st_size != row["byte_size"]
            or _sha256_file(source_path) != row["sha256"]
        ):
            raise RuntimeError(f"Mission Hub artifact identity mismatch: {row['id']}")
        target = destination / f'{row["sha256"]}.png'
        if not target.exists():
            partial = target.with_suffix(".png.partial")
            shutil.copyfile(source_path, partial)
            if partial.stat().st_size != row["byte_size"] or _sha256_file(partial) != row["sha256"]:
                partial.unlink(missing_ok=True)
                raise RuntimeError(f"copied FLUX artifact identity mismatch: {row['id']}")
            partial.replace(target)
        elif target.stat().st_size != row["byte_size"] or _sha256_file(target) != row["sha256"]:
            raise RuntimeError(f"existing FLUX corpus file identity mismatch: {row['id']}")

        db.execute(
            """INSERT INTO asset(
                   source, source_id, split, original_url, author, title,
                   declared_bytes, local_path, sha256, width, height, status
               ) VALUES (?, ?, 'generated', ?, ?, ?, ?, ?, ?, ?, ?, 'downloaded')
               ON CONFLICT(source, source_id) DO UPDATE SET
                   original_url=excluded.original_url, author=excluded.author,
                   title=excluded.title, declared_bytes=excluded.declared_bytes,
                   local_path=excluded.local_path, sha256=excluded.sha256,
                   width=excluded.width, height=excluded.height, status='downloaded'""",
            (
                source, row["id"], f'mission-hub-artifact:{row["id"]}',
                "Ninereeds / FLUX.2-klein-4B", manifest.get("item_id", row["id"]),
                row["byte_size"], str(target), row["sha256"],
                manifest.get("width"), manifest.get("height"),
            ),
        )
        asset_id = db.execute(
            "SELECT id FROM asset WHERE source=? AND source_id=?", (source, row["id"])
        ).fetchone()[0]
        db.execute("DELETE FROM text_search WHERE asset_id=?", (asset_id,))
        db.execute("DELETE FROM text_record WHERE asset_id=?", (asset_id,))
        prompt = manifest.get("prompt", "")
        db.execute(
            """INSERT INTO text_record(asset_id, kind, text, author, model, payload_json)
               VALUES (?, 'generation_prompt', ?, 'mission_hub', ?, ?)""",
            (asset_id, prompt, manifest.get("model_id"), row["manifest_json"]),
        )
        db.execute(
            "INSERT INTO text_search(asset_id, kind, text) VALUES (?, 'generation_prompt', ?)",
            (asset_id, prompt),
        )
        inspection = evidence["visual_inspection_report"].get(row["sha256"])
        review = evidence["visual_review_report"].get(row["sha256"])
        for kind, record in (("prior_inspection", inspection), ("prior_final_review", review)):
            if not record:
                continue
            result = record["result"]
            searchable = json.dumps(result, ensure_ascii=False, sort_keys=True)
            db.execute(
                """INSERT INTO text_record(asset_id, kind, text, author, model, payload_json)
                   VALUES (?, ?, ?, 'mission_hub', NULL, ?)""",
                (asset_id, kind, searchable, json.dumps(record, ensure_ascii=False, sort_keys=True)),
            )
            db.execute(
                "INSERT INTO text_search(asset_id, kind, text) VALUES (?, ?, ?)",
                (asset_id, kind, searchable),
            )
        review_status = review["result"].get("asset_status") if review else None
        if review_status == "usable":
            status = "reviewed_usable"
        elif review_status == "unusable":
            status = "reviewed_unusable"
        elif inspection:
            status = "previously_inspected"
        else:
            status = "downloaded"
        db.execute("UPDATE asset SET status=? WHERE id=?", (status, asset_id))
        db.execute(
            "INSERT OR IGNORE INTO selection VALUES (?, ?, 'generated_flux', ?)",
            (selection_name, asset_id, ordinal),
        )
        if status == "reviewed_usable":
            accepted_ordinal = db.execute(
                "SELECT COUNT(*) FROM selection WHERE name=?", (f"{selection_name}-accepted",)
            ).fetchone()[0]
            db.execute(
                "INSERT OR IGNORE INTO selection VALUES (?, ?, 'generated_flux_accepted', ?)",
                (f"{selection_name}-accepted", asset_id, accepted_ordinal),
            )
        elif status != "reviewed_unusable":
            pending_ordinal = db.execute(
                "SELECT COUNT(*) FROM selection WHERE name=?", (f"{selection_name}-pending",)
            ).fetchone()[0]
            db.execute(
                "INSERT OR IGNORE INTO selection VALUES (?, ?, 'generated_flux_pending', ?)",
                (f"{selection_name}-pending", asset_id, pending_ordinal),
            )
        if (ordinal + 1) % 100 == 0:
            db.commit()
            print(f"imported FLUX {ordinal + 1}/{len(distinct)}", flush=True)
    db.commit()
    return len(distinct)


def combine_selections(
    db: sqlite3.Connection,
    name: str,
    selections: list[str],
) -> int:
    if db.execute("SELECT COUNT(*) FROM selection WHERE name=?", (name,)).fetchone()[0]:
        raise ValueError(f"selection already exists: {name}")
    ordinal = 0
    chosen: set[int] = set()
    for source_name in selections:
        rows = db.execute(
            "SELECT asset_id, stratum FROM selection WHERE name=? ORDER BY ordinal",
            (source_name,),
        ).fetchall()
        if not rows:
            raise ValueError(f"selection is empty or missing: {source_name}")
        for row in rows:
            if row["asset_id"] in chosen:
                continue
            chosen.add(row["asset_id"])
            db.execute(
                "INSERT INTO selection VALUES (?, ?, ?, ?)",
                (name, row["asset_id"], row["stratum"], ordinal),
            )
            ordinal += 1
    db.commit()
    return ordinal


def filter_mechanically_valid(
    db: sqlite3.Connection,
    parent: str,
    name: str,
) -> int:
    """Copy only successfully decoded, policy-clean assets into a new selection."""
    if db.execute("SELECT COUNT(*) FROM selection WHERE name=?", (name,)).fetchone()[0]:
        raise ValueError(f"selection already exists: {name}")
    if not db.execute("SELECT 1 FROM selection WHERE name=? LIMIT 1", (parent,)).fetchone():
        raise ValueError(f"selection is empty or missing: {parent}")
    rows = db.execute(
        """SELECT s.asset_id, s.stratum
           FROM selection s JOIN mechanical_check m ON m.asset_id=s.asset_id
           WHERE s.name=? AND m.decoded=1 AND m.reasons_json='[]'
           ORDER BY s.ordinal""",
        (parent,),
    ).fetchall()
    db.executemany(
        "INSERT INTO selection VALUES (?, ?, ?, ?)",
        ((name, row["asset_id"], row["stratum"], ordinal) for ordinal, row in enumerate(rows)),
    )
    db.commit()
    return len(rows)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while block := handle.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _download_asset(row: sqlite3.Row, store: Path, retries: int) -> tuple[int, str, str, int]:
    destination = store / "blobs" / row["source"] / row["split"]
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / f'{row["source_id"]}.jpg'
    if target.exists():
        digest = _sha256_file(target)
        if row["sha256"] and row["sha256"] != digest:
            raise RuntimeError(f'existing file hash mismatch: {row["source_id"]}')
        return row["id"], str(target), digest, target.stat().st_size

    if row["source"] == "open_images_v7":
        url = f'https://open-images-dataset.s3.amazonaws.com/{row["split"]}/{row["source_id"]}.jpg'
    else:
        url = str(row["original_url"] or "")
        if not url.startswith("https://"):
            raise RuntimeError(f'{row["source_id"]}: missing safe HTTPS source URL')
    partial = target.with_suffix(".jpg.partial")
    last_error: Exception | None = None
    for attempt in range(retries):
        partial.unlink(missing_ok=True)
        digest = hashlib.sha256()
        total = 0
        try:
            with urllib.request.urlopen(url, timeout=90) as response, partial.open("wb") as output:
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 32 * 1024 * 1024:
                        raise RuntimeError("download exceeds 32 MiB safety bound")
                    digest.update(block)
                    output.write(block)
            if total == 0:
                raise RuntimeError("empty download")
            partial.replace(target)
            return row["id"], str(target), digest.hexdigest(), total
        except Exception as exc:
            partial.unlink(missing_ok=True)
            last_error = exc
            if attempt + 1 < retries:
                import time
                time.sleep(2 ** attempt)
    raise RuntimeError(f'{row["source_id"]}: {type(last_error).__name__}: {last_error}')


def download_selection(
    db: sqlite3.Connection,
    name: str,
    store: Path,
    workers: int = 1,
    retries: int = 3,
    *,
    allow_partial: bool = False,
    failure_output: Path | None = None,
    excluded_sources: tuple[str, ...] = (),
) -> None:
    if not 1 <= workers <= 32:
        raise ValueError("workers must be between 1 and 32")
    if not 1 <= retries <= 10:
        raise ValueError("retries must be between 1 and 10")
    rows = db.execute(
        """SELECT a.id, a.source, a.source_id, a.split, a.original_url, a.sha256 FROM asset a
           JOIN selection s ON s.asset_id=a.id WHERE s.name=? ORDER BY s.ordinal""",
        (name,),
    ).fetchall()
    failures: list[str] = []
    eligible_rows = []
    for row in rows:
        target = store / "blobs" / row["source"] / row["split"] / f'{row["source_id"]}.jpg'
        url = str(row["original_url"] or "")
        if row["source"] in excluded_sources and not target.exists():
            failures.append(f'{row["source_id"]}: source excluded by frozen download policy')
        elif (
            not target.exists()
            and row["source"] != "open_images_v7"
            and not url.startswith("https://")
        ):
            failures.append(f'{row["source_id"]}: missing safe HTTPS source URL')
        else:
            eligible_rows.append(row)
    completed = len(failures)
    bytes_written = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_download_asset, row, store, retries) for row in eligible_rows}
        for future in as_completed(futures):
            try:
                asset_id, target, digest, byte_size = future.result()
                db.execute(
                    "UPDATE asset SET local_path=?, sha256=?, status='downloaded' WHERE id=?",
                    (target, digest, asset_id),
                )
                bytes_written += byte_size
            except Exception as exc:
                failures.append(str(exc))
            finally:
                # Failed urllib futures retain their tracebacks, which can retain
                # response sockets. Release each completed future immediately so
                # a large bad-URL wave cannot exhaust the process file limit.
                futures.discard(future)
            completed += 1
            if completed % 100 == 0 or completed == len(rows):
                db.commit()
                print(
                    f"processed {completed}/{len(rows)} "
                    f"failures={len(failures)} bytes={bytes_written}",
                    flush=True,
                )
    db.commit()
    if failure_output is not None:
        failure_output.parent.mkdir(parents=True, exist_ok=True)
        failure_output.write_text(
            json.dumps({
                "selection": name,
                "attempted": completed,
                "downloaded": completed - len(failures),
                "failed": len(failures),
                "failures": failures,
            }, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
    if failures:
        sample = "; ".join(failures[:10])
        if allow_partial and completed > len(failures):
            print(
                f"partial download accepted: {completed - len(failures)} succeeded, "
                f"{len(failures)} failed; sample: {sample}",
                flush=True,
            )
        else:
            raise RuntimeError(f"{len(failures)} download(s) failed: {sample}")


def export_selection(db: sqlite3.Connection, name: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = db.execute(
        """SELECT s.ordinal, s.stratum, a.* FROM selection s
           JOIN asset a ON a.id=s.asset_id WHERE s.name=? ORDER BY s.ordinal""",
        (name,),
    ).fetchall()
    labels: dict[int, list[str]] = defaultdict(list)
    for record in db.execute(
        """SELECT l.asset_id, l.name FROM label l JOIN selection s ON s.asset_id=l.asset_id
           WHERE s.name=? AND l.confidence=1 ORDER BY l.asset_id,l.name""",
        (name,),
    ):
        labels[record["asset_id"]].append(record["name"])
    relations: dict[int, list[dict[str, object]]] = defaultdict(list)
    for record in db.execute(
        """SELECT r.asset_id,r.subject,r.predicate,r.object FROM relationship r
           JOIN selection s ON s.asset_id=r.asset_id WHERE s.name=? ORDER BY r.asset_id,r.id""",
        (name,),
    ):
        relations[record["asset_id"]].append({
            "subject": record["subject"], "predicate": record["predicate"],
            "object": record["object"],
        })
    counts: dict[int, list[dict[str, object]]] = defaultdict(list)
    for record in db.execute(
        """SELECT b.asset_id,b.name,COUNT(*) AS count FROM object_box b
           JOIN selection s ON s.asset_id=b.asset_id
           WHERE s.name=? AND b.group_of=0 AND b.depiction=0
           GROUP BY b.asset_id,b.name ORDER BY b.asset_id,b.name""",
        (name,),
    ):
        counts[record["asset_id"]].append({"name": record["name"], "count": record["count"]})
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            record = dict(row)
            record["labels"] = labels[row["id"]]
            record["relationships"] = relations[row["id"]]
            record["object_counts"] = counts[row["id"]]
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def inspect_selection(db: sqlite3.Connection, name: str, minimum_side: int) -> None:
    try:
        from PIL import Image, ImageOps
    except ImportError as exc:
        raise RuntimeError("inspection requires Pillow") from exc
    rows = db.execute(
        """SELECT a.id, a.local_path FROM asset a JOIN selection s ON s.asset_id=a.id
           WHERE s.name=? ORDER BY s.ordinal""", (name,)
    ).fetchall()
    for row in rows:
        reasons: list[str] = []
        image_format = image_mode = perceptual_hash = None
        width = height = None
        decoded = 0
        try:
            path = Path(row["local_path"])
            with Image.open(path) as image:
                image.load()
                decoded = 1
                image_format = image.format
                image_mode = image.mode
                width, height = image.size
                if min(width, height) < minimum_side:
                    reasons.append("small_dimension")
                if width * height < minimum_side * minimum_side:
                    reasons.append("small_area")
                gray = ImageOps.fit(image.convert("L"), (8, 8))
                pixels = list(gray.getdata())
                mean = sum(pixels) / len(pixels)
                bits = sum((value >= mean) << index for index, value in enumerate(pixels))
                perceptual_hash = f"{bits:016x}"
        except Exception as exc:
            reasons.append(f"decode_error:{type(exc).__name__}")
        db.execute(
            """INSERT INTO mechanical_check(
                   asset_id, decoded, image_format, image_mode, perceptual_hash, reasons_json
               ) VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(asset_id) DO UPDATE SET decoded=excluded.decoded,
                   image_format=excluded.image_format, image_mode=excluded.image_mode,
                   perceptual_hash=excluded.perceptual_hash, reasons_json=excluded.reasons_json,
                   checked_at=CURRENT_TIMESTAMP""",
            (row["id"], decoded, image_format, image_mode, perceptual_hash, json.dumps(reasons)),
        )
        current_status = db.execute("SELECT status FROM asset WHERE id=?", (row["id"],)).fetchone()[0]
        mechanical_status = "mechanically_valid" if decoded and not reasons else "needs_review"
        status = current_status if current_status in {"reviewed_usable", "reviewed_unusable"} else mechanical_status
        db.execute("UPDATE asset SET width=?, height=?, status=? WHERE id=?",
                   (width, height, status, row["id"]))
    db.commit()


def derive_selection(db: sqlite3.Connection, parent: str, name: str, size: int) -> None:
    requested = {
        "relationship": round(size * 0.35),
        "exact_count": round(size * 0.25),
    }
    requested["diverse_scene"] = size - sum(requested.values())
    db.execute("DELETE FROM selection WHERE name=?", (name,))
    ordinal = 0
    for stratum, wanted in requested.items():
        rows = db.execute(
            """SELECT s.asset_id FROM selection s
               JOIN mechanical_check m ON m.asset_id=s.asset_id
               WHERE s.name=? AND s.stratum=? AND m.decoded=1 AND m.reasons_json='[]'
               ORDER BY s.ordinal""", (parent, stratum)
        ).fetchall()
        if len(rows) < wanted:
            raise RuntimeError(f"only {len(rows)}/{wanted} valid images in {stratum}")
        for row in rows[:wanted]:
            db.execute("INSERT INTO selection VALUES (?, ?, ?, ?)",
                       (name, row["asset_id"], stratum, ordinal))
            ordinal += 1
    db.commit()


def contact_sheets(db: sqlite3.Connection, name: str, output_dir: Path, per_sheet: int) -> None:
    try:
        from PIL import Image, ImageDraw, ImageOps
    except ImportError as exc:
        raise RuntimeError("contact sheets require Pillow") from exc
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = db.execute(
        """SELECT s.ordinal, s.stratum, a.source_id, a.local_path FROM selection s
           JOIN asset a ON a.id=s.asset_id WHERE s.name=? ORDER BY s.ordinal""", (name,)
    ).fetchall()
    columns, cell_w, cell_h, label_h = 5, 256, 192, 38
    for page_start in range(0, len(rows), per_sheet):
        page = rows[page_start:page_start + per_sheet]
        page_rows = (len(page) + columns - 1) // columns
        sheet = Image.new("RGB", (columns * cell_w, page_rows * (cell_h + label_h)), "white")
        draw = ImageDraw.Draw(sheet)
        for index, row in enumerate(page):
            x = (index % columns) * cell_w
            y = (index // columns) * (cell_h + label_h)
            with Image.open(row["local_path"]) as image:
                tile = ImageOps.contain(image.convert("RGB"), (cell_w, cell_h))
                sheet.paste(tile, (x + (cell_w - tile.width) // 2, y + (cell_h - tile.height) // 2))
            draw.text((x + 4, y + cell_h + 2),
                      f'{row["ordinal"]:03d} {row["source_id"]}', fill="black")
            draw.text((x + 4, y + cell_h + 18), row["stratum"], fill="black")
        sheet.save(output_dir / f"{name}-{page_start // per_sheet + 1:02d}.jpg", quality=90)


def print_stats(db: sqlite3.Connection) -> None:
    for table in ("asset", "label", "object_box", "relationship", "text_record", "selection", "mechanical_check"):
        print(f"{table}: {db.execute(f'SELECT COUNT(*) FROM {table}').fetchone()[0]}")


def search(db: sqlite3.Connection, query: str, limit: int) -> None:
    rows = db.execute(
        """SELECT a.source, a.source_id, a.local_path, ts.kind, ts.text
           FROM text_search ts JOIN asset a ON a.id=ts.asset_id
           WHERE text_search MATCH ? ORDER BY rank LIMIT ?""",
        (query, limit),
    )
    for row in rows:
        print(json.dumps(dict(row), ensure_ascii=False, sort_keys=True))


def main(argv: Iterable[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)
    init = sub.add_parser("init")
    init.set_defaults(action=lambda db, args: None)
    load = sub.add_parser("import-open-images")
    load.add_argument("metadata_dir", type=Path)
    load.set_defaults(action=lambda db, args: import_open_images(db, args.metadata_dir))
    select = sub.add_parser("select")
    select.add_argument("name")
    select.add_argument("--size", type=int, default=100)
    select.add_argument("--seed", type=int, default=3501)
    select.set_defaults(action=lambda db, args: select_candidates(db, args.name, args.size, args.seed))
    production = sub.add_parser("select-production")
    production.add_argument("name")
    production.add_argument("--source", default="open_images_v7")
    production.add_argument("--exclude-selection", required=True)
    production.set_defaults(action=lambda db, args: print(json.dumps({
        "selected": select_production(db, args.name, args.source, args.exclude_selection)
    })))
    flux = sub.add_parser("import-flux-artifacts")
    flux.add_argument("mission_hub_db", type=Path)
    flux.add_argument("--selection", required=True)
    flux.add_argument("--store", type=Path, default=DEFAULT_STORE)
    flux.set_defaults(action=lambda db, args: print(json.dumps({
        "imported": import_flux_artifacts(db, args.mission_hub_db, args.store, args.selection)
    })))
    combine = sub.add_parser("combine")
    combine.add_argument("name")
    combine.add_argument("selections", nargs="+")
    combine.set_defaults(action=lambda db, args: print(json.dumps({
        "selected": combine_selections(db, args.name, args.selections)
    })))
    mechanical = sub.add_parser("filter-mechanical")
    mechanical.add_argument("parent")
    mechanical.add_argument("name")
    mechanical.set_defaults(action=lambda db, args: print(json.dumps({
        "selected": filter_mechanically_valid(db, args.parent, args.name)
    })))
    download = sub.add_parser("download")
    download.add_argument("name")
    download.add_argument("--store", type=Path, default=DEFAULT_STORE)
    download.add_argument("--workers", type=int, default=1)
    download.add_argument("--retries", type=int, default=3)
    download.add_argument("--allow-partial", action="store_true")
    download.add_argument("--failure-output", type=Path)
    download.add_argument("--exclude-source", action="append", default=[])
    download.set_defaults(action=lambda db, args: download_selection(
        db, args.name, args.store, args.workers, args.retries,
        allow_partial=args.allow_partial, failure_output=args.failure_output,
        excluded_sources=tuple(args.exclude_source),
    ))
    export = sub.add_parser("export")
    export.add_argument("name")
    export.add_argument("output", type=Path)
    export.set_defaults(action=lambda db, args: export_selection(db, args.name, args.output))
    stats = sub.add_parser("stats")
    stats.set_defaults(action=lambda db, args: print_stats(db))
    find = sub.add_parser("search")
    find.add_argument("query", help="FTS5 query, for example: 'dog AND under'")
    find.add_argument("--limit", type=int, default=20)
    find.set_defaults(action=lambda db, args: search(db, args.query, args.limit))
    inspect = sub.add_parser("inspect")
    inspect.add_argument("name")
    inspect.add_argument("--minimum-side", type=int, default=256)
    inspect.set_defaults(action=lambda db, args: inspect_selection(db, args.name, args.minimum_side))
    derive = sub.add_parser("derive")
    derive.add_argument("parent")
    derive.add_argument("name")
    derive.add_argument("--size", type=int, default=100)
    derive.set_defaults(action=lambda db, args: derive_selection(db, args.parent, args.name, args.size))
    sheets = sub.add_parser("contact-sheets")
    sheets.add_argument("name")
    sheets.add_argument("output_dir", type=Path)
    sheets.add_argument("--per-sheet", type=int, default=25)
    sheets.set_defaults(action=lambda db, args: contact_sheets(db, args.name, args.output_dir, args.per_sheet))
    args = parser.parse_args(list(argv) if argv is not None else None)
    with connect(args.db) as db:
        args.action(db, args)


if __name__ == "__main__":
    main()
