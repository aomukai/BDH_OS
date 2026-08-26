import json
import sqlite3

from image_registry.campaign36_replacement_generation_queue import (
    append_unresolved_handoff,
    claim,
    connect,
    finish,
    renew,
    revise_prompt,
    sync,
)


def test_live_word_claim_can_be_renewed(tmp_path):
    db_path = tmp_path / "registry.sqlite3"
    replacement = tmp_path / "replacement.jsonl"
    selected = tmp_path / "selected.jsonl"
    replacement.write_text(json.dumps({
        "new_word": "dog", "new_concept_id": "dog",
        "new_teaching_sense": "a domestic canine", "ordinal": 1,
    }) + "\n")
    selected.write_text("")
    with connect(db_path) as db:
        sync(db, replacement_map=replacement, selected_assets=selected, reviews_complete=True)
        item = claim(db, provider="imagegen", worker_id="imagegen-0", lease_seconds=60)
        old_expiry = item["claim_expires_at"]
        new_expiry = renew(
            db, claim_token=item["claim_token"], worker_id="imagegen-0",
            lease_seconds=600,
        )
        assert new_expiry > old_expiry
        attempt_expiry = db.execute(
            "SELECT lease_expires_at FROM campaign36_word_generation_attempt WHERE claim_token=?",
            (item["claim_token"],),
        ).fetchone()[0]
        assert attempt_expiry == new_expiry


def test_open_review_reconciliation_may_regress_provisional_complete_word(tmp_path):
    db_path = tmp_path / "registry.sqlite3"
    replacement = tmp_path / "replacement.jsonl"
    selected = tmp_path / "selected.jsonl"
    replacement.write_text(json.dumps({
        "new_word": "dog", "new_concept_id": "dog",
        "new_teaching_sense": "a domestic canine", "ordinal": 1,
    }) + "\n")
    selected.write_text("".join(json.dumps({"word": "dog"}) + "\n" for _ in range(10)))
    with connect(db_path) as db:
        state = sync(
            db, replacement_map=replacement, selected_assets=selected,
            reviews_complete=False,
        )
        assert state["counts"] == {"complete": 1}
        selected.write_text("".join(json.dumps({"word": "dog"}) + "\n" for _ in range(9)))
        state = sync(
            db, replacement_map=replacement, selected_assets=selected,
            reviews_complete=False,
        )
        assert state["counts"] == {"review_pending": 1}
        assert state["accepted_images"] == 9
        assert state["remaining_images"] == 1
        state = sync(
            db, replacement_map=replacement, selected_assets=selected,
            reviews_complete=True,
        )
        assert state["counts"] == {"unclaimed": 1}


def test_cross_provider_then_revised_prompt_cycle(tmp_path):
    db_path = tmp_path / "registry.sqlite3"
    replacement = tmp_path / "replacement.jsonl"
    selected = tmp_path / "selected.jsonl"
    replacement.write_text(
        json.dumps(
            {
                "new_word": "dog",
                "new_concept_id": "dog",
                "new_teaching_sense": "a domestic canine",
                "ordinal": 1,
            }
        )
        + "\n"
    )
    selected.write_text("".join(json.dumps({"word": "dog"}) + "\n" for _ in range(8)))
    with connect(db_path) as db:
        state = sync(
            db,
            replacement_map=replacement,
            selected_assets=selected,
            reviews_complete=True,
        )
        assert state["remaining_images"] == 2
        first = claim(db, provider="flux", worker_id="flux-0", lease_seconds=600)
        state = finish(
            db,
            claim_token=first["claim_token"],
            worker_id="flux-0",
            produced_count=2,
            accepted_added=1,
            evidence={"reason": "one rejected"},
        )
        assert state["status"] == "needs_other_provider"
        assert claim(db, provider="flux", worker_id="flux-1", lease_seconds=600) is None
        second = claim(db, provider="imagegen", worker_id="imagegen-0", lease_seconds=600)
        state = finish(
            db,
            claim_token=second["claim_token"],
            worker_id="imagegen-0",
            produced_count=1,
            accepted_added=0,
            evidence={"reason": "rejected"},
        )
        assert state["status"] == "needs_prompt_revision"
        state = revise_prompt(db, word="dog", prompt="A clear photograph of one dog.")
        assert state["prompt_cycle"] == 1
        third = claim(db, provider="imagegen", worker_id="imagegen-1", lease_seconds=600)
        state = finish(
            db,
            claim_token=third["claim_token"],
            worker_id="imagegen-1",
            produced_count=1,
            accepted_added=1,
            evidence={"reason": "accepted"},
        )
        assert state["status"] == "complete"


def test_restarted_worker_expires_own_claim_and_crosses_provider(tmp_path):
    db_path = tmp_path / "registry.sqlite3"
    replacement = tmp_path / "replacement.jsonl"
    selected = tmp_path / "selected.jsonl"
    replacement.write_text(
        "\n".join(
            json.dumps(
                {
                    "new_word": word,
                    "new_concept_id": word,
                    "new_teaching_sense": word,
                    "ordinal": index,
                }
            )
            for index, word in enumerate(("dog", "cat"), 1)
        )
        + "\n"
    )
    selected.write_text("")
    with connect(db_path) as db:
        sync(
            db,
            replacement_map=replacement,
            selected_assets=selected,
            reviews_complete=True,
        )
        first = claim(db, provider="flux", worker_id="flux-0", lease_seconds=600)
        assert first["word"] == "dog"
        restarted = claim(db, provider="flux", worker_id="flux-0", lease_seconds=600)
        assert restarted["word"] == "cat"
        crossover = claim(db, provider="imagegen", worker_id="imagegen-0", lease_seconds=600)
        assert crossover["word"] == "dog"
        expired = db.execute(
            """SELECT status,evidence_json FROM campaign36_word_generation_attempt
               WHERE word='dog' AND provider='flux'"""
        ).fetchone()
        assert expired["status"] == "expired"
        assert "worker_restarted_before_finish" in expired["evidence_json"]


def test_both_providers_on_revised_prompt_route_to_handoff(tmp_path):
    db_path = tmp_path / "registry.sqlite3"
    replacement = tmp_path / "replacement.jsonl"
    selected = tmp_path / "selected.jsonl"
    handoff = tmp_path / "ideas.md"
    replacement.write_text(
        json.dumps(
            {
                "new_word": "difficult",
                "new_concept_id": "difficult",
                "new_teaching_sense": "hard to depict",
                "ordinal": 1,
            }
        )
        + "\n"
    )
    selected.write_text("")
    with connect(db_path) as db:
        sync(db, replacement_map=replacement, selected_assets=selected, reviews_complete=True)
        for provider, worker in (("flux", "f0"), ("imagegen", "i0")):
            item = claim(db, provider=provider, worker_id=worker, lease_seconds=600)
            finish(
                db,
                claim_token=item["claim_token"],
                worker_id=worker,
                produced_count=10,
                accepted_added=0,
                evidence={"reason": "all rejected"},
            )
        revise_prompt(db, word="difficult", prompt="A clearer representation.")
        for provider, worker in (("imagegen", "i1"), ("flux", "f1")):
            item = claim(db, provider=provider, worker_id=worker, lease_seconds=600)
            state = finish(
                db,
                claim_token=item["claim_token"],
                worker_id=worker,
                produced_count=10,
                accepted_added=0,
                evidence={"reason": "revised prompt still failed"},
            )
        assert state["status"] == "unresolved"
        report = append_unresolved_handoff(db, path=handoff)
        assert report["unresolved_words"] == 1
        assert "## difficult" in handoff.read_text()
