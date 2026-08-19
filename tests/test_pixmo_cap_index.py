import json
import sqlite3

from image_registry.cli import connect
from image_registry.pixmo_cap_index import shortlist


def _jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_pixmo_fills_positions_left_by_an_earlier_faucet(tmp_path):
    index_path = tmp_path / "pixmo.sqlite3"
    index = sqlite3.connect(index_path)
    index.executescript("""
        CREATE TABLE image(id INTEGER PRIMARY KEY,source_id TEXT,image_url TEXT,caption TEXT,transcripts_json TEXT);
        CREATE VIRTUAL TABLE image_search USING fts5(caption);
    """)
    index.executemany(
        "INSERT INTO image(source_id,image_url,caption,transcripts_json) VALUES (?,?,?,?)",
        [
            ("a", "https://example.test/a.jpg", "a dog running", "[]"),
            ("b", "https://example.test/b.jpg", "a sleeping dog", "[]"),
        ],
    )
    index.executemany(
        "INSERT INTO image_search(rowid,caption) VALUES (?,?)",
        [(1, "a dog running"), (2, "a sleeping dog")],
    )
    index.commit()
    index.close()
    registry_path = tmp_path / "registry.sqlite3"
    with connect(registry_path):
        pass
    needs = tmp_path / "needs.jsonl"
    existing = tmp_path / "existing.jsonl"
    _jsonl(needs, [{
        "slot_id": "dog:1", "word": "dog", "concept": "dog", "ordinal": 1,
        "exposure_index": 1, "sequence_position": 1,
    }])
    _jsonl(existing, [{
        "slot_id": "dog:1", "source": "earlier", "source_image_id": "old",
        "source_metadata": {"original_url": "https://example.test/old.jpg"},
    }])

    summary = shortlist(
        index_path, registry_path, needs, [existing], tmp_path / "out", overfetch_factor=2.0
    )

    rows = [json.loads(line) for line in (tmp_path / "out/candidates.jsonl").read_text().splitlines()]
    assert summary["wave_target"] == 2
    assert summary["wave_candidate_total"] == 2
    assert len(rows) == 1
    assert rows[0]["candidate_rank_for_slot"] == 2
    assert rows[0]["source"] == "pixmo_cap"
