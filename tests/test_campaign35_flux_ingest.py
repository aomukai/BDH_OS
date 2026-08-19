import json
from pathlib import Path

import pytest

from image_registry.campaign35_flux_ingest import main, sha256
from image_registry.cli import connect


def _jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_ingest_generated_pixels_and_exact_slot_proposals(tmp_path: Path) -> None:
    db_path = tmp_path / "registry.sqlite3"
    store = tmp_path / "store"
    images = tmp_path / "generated"
    output = tmp_path / "ingest"
    images.mkdir()

    generated = images / "scene-0001-v00.png"
    generated.write_bytes(b"test-pixels")
    digest = sha256(generated)
    ledger = tmp_path / "ledger.jsonl"
    _jsonl(ledger, [{
        "production_brief_id": "scene-0001", "variant_index": 0,
        "concept_ids": ["dog"], "prompt": "A clearly visible dog.",
        "sha256": digest, "width": 512, "height": 384,
        "model": "flux-test",
    }])
    inventory = tmp_path / "inventory.jsonl"
    _jsonl(inventory, [{
        "concept_id": "dog", "word": "dog", "ordinal": 7,
        "route": "single_image", "missing_slots": 1,
        "missing_slot_ids": ["c0007-dog-i03"],
    }])

    assert main([
        "--db", str(db_path), "--store", str(store),
        "--ledger", str(ledger), "--image-root", str(images),
        "--inventory", str(inventory), "--source", "flux-cycle-test",
        "--selection", "flux-test",
        "--output", str(output),
    ]) == 0

    with connect(db_path) as db:
        asset = db.execute("SELECT * FROM asset").fetchone()
        assert asset["source"] == "flux-cycle-test"
        assert Path(asset["local_path"]).is_file()
        assert db.execute(
            "SELECT COUNT(*) FROM selection WHERE name='flux-test'"
        ).fetchone()[0] == 1
    proposals = [json.loads(line) for line in (output / "slot_proposals.jsonl").read_text().splitlines()]
    assert proposals == [{
        "candidate_tier": "generated_flux_coherent_scene",
        "caption": "A clearly visible dog.", "concept": "dog",
        "concept_id": "dog", "exposure_index": 3, "ordinal": 7,
        "sequence_position": 63, "slot_id": "c0007-dog-i03",
        "source": "flux-cycle-test",
        "source_image_id": "scene-0001-v00", "word": "dog",
    }]


def test_ingest_rejects_pixel_identical_variants(tmp_path: Path) -> None:
    images = tmp_path / "generated"
    images.mkdir()
    for variant in range(2):
        (images / f"scene-0001-v{variant:02d}.png").write_bytes(b"same-pixels")
    digest = sha256(images / "scene-0001-v00.png")
    ledger = tmp_path / "ledger.jsonl"
    _jsonl(ledger, [{
        "production_brief_id": "scene-0001", "variant_index": variant,
        "concept_ids": ["dog"], "prompt": "A dog.", "sha256": digest,
        "width": 512, "height": 384, "model": "flux-test",
    } for variant in range(2)])
    inventory = tmp_path / "inventory.jsonl"
    _jsonl(inventory, [{
        "concept_id": "dog", "word": "dog", "ordinal": 7,
        "route": "single_image", "missing_slots": 2,
        "missing_slot_ids": ["c0007-dog-i03", "c0007-dog-i04"],
    }])
    with pytest.raises(ValueError, match="pixel-identical"):
        main([
            "--db", str(tmp_path / "registry.sqlite3"),
            "--store", str(tmp_path / "store"), "--ledger", str(ledger),
            "--image-root", str(images), "--inventory", str(inventory),
            "--selection", "flux-test", "--output", str(tmp_path / "output"),
        ])
