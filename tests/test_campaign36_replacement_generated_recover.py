import json

from image_registry.campaign36_replacement_generated_recover import recover
from image_registry.cli import connect


def test_recover_republishes_registry_admission_idempotently(tmp_path):
    db_path = tmp_path / "registry.sqlite3"
    root = tmp_path / "generation"
    image = tmp_path / "dog.png"
    image.write_bytes(b"accepted pixels")
    claim = {
        "word": "dog",
        "concept_id": "dog",
        "teaching_sense": "a domestic canine",
        "ordinal": 7,
        "prompt_cycle": 0,
    }
    review = {
        "verdict": "accepted",
        "review_backend": "codex",
        "review_model": "gpt-5.6-luna",
        "luna_result": {"literal_caption": "A dog standing on grass.", "watermark": False},
    }
    with connect(db_path) as db:
        db.execute(
            """INSERT INTO asset(source,source_id,split,original_url,author,title,
                                  declared_bytes,local_path,sha256,width,height,status)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                "ninereeds_campaign36_replacement_generated",
                "dog-1",
                "generated",
                "campaign36-flux:dog-1",
                "Ninereeds / Flux",
                "dog",
                image.stat().st_size,
                str(image),
                "abc123",
                512,
                384,
                "reviewed_usable",
            ),
        )
        asset_id = db.execute("SELECT id FROM asset").fetchone()[0]
        db.execute(
            """INSERT INTO text_record(asset_id,kind,text,author,model,payload_json)
               VALUES (?,'generation_prompt',?,'campaign36_replacement_flux','flux2',?)""",
            (asset_id, "A clear photograph of a dog.", json.dumps({"claim": claim, "review": review})),
        )
        db.commit()

    first = recover(db_path, root)
    assert first["recovered_accepted_records"] == 1
    assert first["recovered_evidence_records"] == 1
    accepted = json.loads((root / "accepted-generated.jsonl").read_text(encoding="utf-8"))
    assert accepted["word"] == "dog"
    assert accepted["generation_provider"] == "flux"

    second = recover(db_path, root)
    assert second["recovered_accepted_records"] == 0
    assert second["recovered_evidence_records"] == 0
    assert len((root / "accepted-generated.jsonl").read_text(encoding="utf-8").splitlines()) == 1
