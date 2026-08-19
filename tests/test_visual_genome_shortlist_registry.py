import json
from pathlib import Path

from image_registry.cli import connect
from image_registry.visual_genome_shortlist_registry import admit


def test_admits_visual_genome_candidate_and_caption(tmp_path: Path) -> None:
    candidate = {
        "source_image_id": "1", "split": "all",
        "source_metadata": {
            "original_url": "https://example/1.jpg", "landing_url": "https://visualgenome.org/",
            "license_url": None, "width": 640, "height": 480,
        },
        "retrieval_evidence": {"matched_region_id": 2, "matched_phrase": "A dog under a table."},
    }
    shortlist = tmp_path / "shortlist.jsonl"
    shortlist.write_text(json.dumps(candidate) + "\n", encoding="utf-8")
    with connect(tmp_path / "registry.sqlite3") as db:
        assert admit(db, shortlist, "vg")["created"] is True
        assert tuple(db.execute("SELECT source,status FROM asset").fetchone()) == (
            "visual_genome_v1_2", "metadata_only",
        )
        assert db.execute("SELECT text FROM text_record").fetchone()[0] == "A dog under a table."
        assert admit(db, shortlist, "vg")["created"] is False
