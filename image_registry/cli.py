from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import random
import sqlite3
import urllib.request
from collections import Counter, defaultdict
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


def download_selection(db: sqlite3.Connection, name: str, store: Path) -> None:
    destination = store / "blobs" / "open_images_v7" / "validation"
    destination.mkdir(parents=True, exist_ok=True)
    rows = db.execute(
        """SELECT a.id, a.source_id, a.rotation FROM asset a
           JOIN selection s ON s.asset_id=a.id WHERE s.name=? ORDER BY s.ordinal""",
        (name,),
    ).fetchall()
    for index, row in enumerate(rows, 1):
        target = destination / f'{row["source_id"]}.jpg'
        if not target.exists():
            url = f'https://open-images-dataset.s3.amazonaws.com/validation/{row["source_id"]}.jpg'
            partial = target.with_suffix(".jpg.partial")
            try:
                with urllib.request.urlopen(url, timeout=90) as response, partial.open("wb") as output:
                    while block := response.read(1024 * 1024):
                        output.write(block)
                partial.replace(target)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        db.execute(
            "UPDATE asset SET local_path=?, sha256=?, status='downloaded' WHERE id=?",
            (str(target), digest, row["id"]),
        )
        if index % 10 == 0:
            db.commit()
            print(f"downloaded {index}/{len(rows)}")
    db.commit()


def export_selection(db: sqlite3.Connection, name: str, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = db.execute(
        """SELECT s.ordinal, s.stratum, a.* FROM selection s
           JOIN asset a ON a.id=s.asset_id WHERE s.name=? ORDER BY s.ordinal""",
        (name,),
    )
    with output.open("w", encoding="utf-8") as handle:
        for row in rows:
            record = dict(row)
            record["labels"] = [r[0] for r in db.execute(
                "SELECT name FROM label WHERE asset_id=? AND confidence=1 ORDER BY name", (row["id"],)
            )]
            record["relationships"] = [dict(r) for r in db.execute(
                "SELECT subject, predicate, object FROM relationship WHERE asset_id=?", (row["id"],)
            )]
            record["object_counts"] = [dict(r) for r in db.execute(
                """SELECT name, COUNT(*) AS count FROM object_box
                   WHERE asset_id=? AND group_of=0 AND depiction=0
                   GROUP BY name ORDER BY name""", (row["id"],)
            )]
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
        db.execute("UPDATE asset SET width=?, height=?, status=? WHERE id=?",
                   (width, height, "mechanically_valid" if decoded and not reasons else "needs_review", row["id"]))
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
    download = sub.add_parser("download")
    download.add_argument("name")
    download.add_argument("--store", type=Path, default=DEFAULT_STORE)
    download.set_defaults(action=lambda db, args: download_selection(db, args.name, args.store))
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
