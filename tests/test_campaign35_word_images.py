from __future__ import annotations

import json
from pathlib import Path
import sqlite3

import pytest

from image_registry.campaign35_word_images import build_proposal


def _write_curriculum(path: Path) -> None:
    rows = [
        {
            "ordinal": ordinal,
            "concept": "dog 2" if ordinal == 2 else f"word{ordinal}",
            "concept_id": f"word_{ordinal}",
            "depends_on": [],
        }
        for ordinal in range(1, 2501)
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _write_registry(path: Path) -> None:
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE asset(
          id INTEGER PRIMARY KEY, source TEXT, source_id TEXT, local_path TEXT,
          sha256 TEXT, width INTEGER, height INTEGER, status TEXT
        );
        CREATE TABLE text_record(
          id INTEGER PRIMARY KEY, asset_id INTEGER, kind TEXT, text TEXT
        );
        CREATE TABLE label(asset_id INTEGER, name TEXT);
        CREATE VIRTUAL TABLE text_search USING fts5(asset_id UNINDEXED,kind,text);
        """
    )
    for index in range(1, 13):
        digest = f"{index:064x}"
        db.execute(
            "INSERT INTO asset VALUES (?,?,?,?,?,?,?,?)",
            (index, "fixture", str(index), f"/images/{index}.jpg", digest, 640, 480, "reviewed_usable"),
        )
        caption = f"A dog in scene {index}."
        db.execute("INSERT INTO text_record(asset_id,kind,text) VALUES (?,'reviewed_caption',?)", (index, caption))
        db.execute("INSERT INTO text_search(asset_id,kind,text) VALUES (?,'reviewed_caption',?)", (index, caption))
    db.commit()
    db.close()


def test_word_image_proposal_has_ten_ordered_slots_per_word(tmp_path: Path) -> None:
    curriculum, registry, output = tmp_path / "curriculum.jsonl", tmp_path / "registry.sqlite3", tmp_path / "out"
    _write_curriculum(curriculum)
    _write_registry(registry)
    summary = build_proposal(registry, curriculum, output, candidates_per_word=10)
    requirements = [json.loads(line) for line in (output / "requirements.jsonl").read_text().splitlines()]
    proposals = [json.loads(line) for line in (output / "selection_proposal.jsonl").read_text().splitlines()]
    assert summary["required_images"] == 25_000
    assert len(requirements) == 25_000
    assert requirements[0]["slot_id"] == "c0001-i01"
    assert requirements[-1]["sequence_position"] == 25_000
    # The numeric suffix disambiguates curriculum entries; it is not taught.
    assert requirements[10]["word"] == "dog"
    assert all(row["m2_completion"] == "dog" for row in proposals if row["ordinal"] == 2)
    assert all(row["m3_completion"].startswith("A dog") for row in proposals)


def test_word_image_proposal_rejects_non_2500_curriculum(tmp_path: Path) -> None:
    curriculum, registry = tmp_path / "curriculum.jsonl", tmp_path / "registry.sqlite3"
    curriculum.write_text(json.dumps({"ordinal": 1, "concept": "dog", "concept_id": "dog"}) + "\n")
    _write_registry(registry)
    with pytest.raises(ValueError, match="2,500"):
        build_proposal(registry, curriculum, tmp_path / "out")
