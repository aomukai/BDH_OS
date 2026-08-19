import json
import sqlite3

from image_registry.conceptual_captions_index import shortlist
from image_registry.cli import connect


def _jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_shortlist_fills_wave_to_two_candidates_per_slot(tmp_path):
    index_path = tmp_path / "captions.sqlite3"
    index = sqlite3.connect(index_path)
    index.executescript("""
        CREATE TABLE image(id INTEGER PRIMARY KEY,source_id TEXT,image_url TEXT,caption TEXT,labels_json TEXT,confidence_scores_json TEXT);
        CREATE VIRTUAL TABLE image_search USING fts5(caption,labels,content='image',content_rowid='id');
    """)
    rows = [
        ("a", "https://example.test/a.jpg", "a dog runs", '["dog"]', "[0.9]"),
        ("b", "https://example.test/b.jpg", "a small dog", '["dog"]', "[0.8]"),
    ]
    index.executemany("INSERT INTO image(source_id,image_url,caption,labels_json,confidence_scores_json) VALUES (?,?,?,?,?)", rows)
    index.executemany(
        "INSERT INTO image_search(rowid,caption,labels) VALUES (?,?,?)",
        [(1, "a dog runs", "dog"), (2, "a small dog", "dog")],
    )
    index.commit()
    index.close()
    registry_path = tmp_path / "registry.sqlite3"
    with connect(registry_path):
        pass
    needs = tmp_path / "needs.jsonl"
    _jsonl(needs, [{
        "slot_id": "dog:1", "word": "dog", "concept": "dog", "ordinal": 1,
        "exposure_index": 1, "sequence_position": 1,
    }])
    output = tmp_path / "out"

    summary = shortlist(index_path, registry_path, needs, [], output, overfetch_factor=2.0)

    candidates = [json.loads(line) for line in (output / "candidates.jsonl").read_text().splitlines()]
    assert summary["wave_target"] == 2
    assert summary["wave_candidate_total"] == 2
    assert len(candidates) == 2
    assert {row["source_image_id"] for row in candidates} == {"a", "b"}
