from __future__ import annotations

import json

from image_registry.campaign35_word_review import initialize_queue
from image_registry.campaign35_word_review_export import classify
from image_registry.cli import connect


def _requirement() -> dict:
    return {
        "slot_id": "c0001-i01", "word": "dog", "concept": "dog",
        "ordinal": 1, "exposure_index": 1, "sequence_position": 1,
    }


def _db(tmp_path, *, watermark=False, admission="usable", visible=True, status="reviewed_usable"):
    path = tmp_path / "registry.sqlite3"
    db = connect(path)
    db.execute(
        "INSERT INTO asset(source,source_id,split,local_path,sha256,status) VALUES ('test','a','validation','/images/a.jpg','abc',?)",
        (status,),
    )
    binding = {**_requirement(), "asset_id": 1, "source_caption": "A dog.", "candidate_tier": "primary"}
    initialize_queue(db, "semantic", [binding])
    parsed = {
        "admission": admission, "visible_text": False, "watermark": watermark,
        "quality_flags": [], "literal_caption": "A dog.",
        "targets": [{"word": "dog", "visible": visible, "evidence": "A dog is visible."}],
        "uncertainties": [],
    }
    db.execute(
        "UPDATE review_queue SET status='completed',result_json=? WHERE queue_name='semantic' AND asset_id=1",
        (json.dumps({"parsed": parsed, "schema_errors": []}),),
    )
    db.commit()
    return db


def _luna(db, queue: str, result: dict):
    db.execute(
        "INSERT INTO selection(name,asset_id,stratum,ordinal) VALUES (?,1,'test',0)",
        (queue,),
    )
    db.execute(
        "INSERT INTO review_queue(queue_name,asset_id,ordinal,status,completed_at,result_json) VALUES (?,1,0,'completed','now',?)",
        (queue, json.dumps(result)),
    )
    db.commit()


def test_false_watermark_alarm_returns_to_target_fit(tmp_path):
    with _db(tmp_path, watermark=True) as db:
        _luna(db, "watermarks", {"alarm": "in_scene_text_or_branding", "reason": "No overlay."})
        row = classify(db, "semantic", [_requirement()], watermark_queue="watermarks")[0]
        assert row["disposition"] == "accepted"
        assert row["watermark_adjudication"] == "in_scene_text_or_branding"


def test_usability_rescue_does_not_override_target_fit(tmp_path):
    with _db(tmp_path, admission="unusable", visible=False) as db:
        _luna(db, "usability", {"usability": "usable", "reason": "Recognizable image."})
        row = classify(db, "semantic", [_requirement()], usability_queue="usability")[0]
        assert row["disposition"] == "target_not_visible"


def test_deleted_asset_cannot_be_resurrected(tmp_path):
    with _db(tmp_path, watermark=True, status="deleted_watermark") as db:
        db.execute("UPDATE asset SET local_path=NULL WHERE id=1")
        db.commit()
        _luna(db, "watermarks", {"alarm": "in_scene_text_or_branding", "reason": "No overlay."})
        row = classify(db, "semantic", [_requirement()], watermark_queue="watermarks")[0]
        assert row["disposition"] == "deleted_watermark"


def test_luna_uncertain_word_fit_escalates_only_to_sol(tmp_path):
    with _db(tmp_path, visible="uncertain") as db:
        _luna(db, "word-fit", {"targets": [{
            "word": "dog", "verdict": "uncertain", "reason": "Relevant pixels are obscured."
        }]})
        row = classify(db, "semantic", [_requirement()], word_fit_queue="word-fit")[0]
        assert row["disposition"] == "needs_sol_word_fit"


def test_sol_is_final_judge_for_luna_uncertain_word_fit(tmp_path):
    with _db(tmp_path, visible="uncertain") as db:
        _luna(db, "word-fit", {"targets": [{
            "word": "dog", "verdict": "uncertain", "reason": "Relevant pixels are obscured."
        }]})
        _luna(db, "sol-word-fit", {"targets": [{
            "word": "dog", "verdict": "accept", "reason": "The visible animal is clearly a dog."
        }]})
        row = classify(
            db, "semantic", [_requirement()], word_fit_queue="word-fit",
            sol_word_fit_queue="sol-word-fit",
        )[0]
        assert row["disposition"] == "accepted"
        assert row["sol_final_judgment"] == "accept"
