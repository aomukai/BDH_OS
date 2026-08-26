"""Export Campaign 35 semantic decisions and freeze exact M2/M3 event ledgers."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

from .cli import DEFAULT_DB, connect


def _rows(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _write(path: Path, rows) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _completed_result(db, queue: str | None, asset_id: int) -> dict | None:
    if not queue:
        return None
    row = db.execute(
        "SELECT status,result_json FROM review_queue WHERE queue_name=? AND asset_id=?",
        (queue, asset_id),
    ).fetchone()
    if row is None or row["status"] != "completed":
        return None
    return json.loads(row["result_json"])


def classify(
    db, queue: str, requirements: list[dict], *,
    watermark_queue: str | None = None,
    usability_queue: str | None = None,
    word_fit_queue: str | None = None,
    sol_word_fit_queue: str | None = None,
) -> list[dict]:
    bindings = {
        row["slot_id"]: dict(row)
        for row in db.execute(
            """SELECT * FROM campaign35_word_review_slot_binding
               WHERE queue_name=?""", (queue,),
        )
    }
    decisions = []
    for requirement in requirements:
        binding = bindings.get(requirement["slot_id"])
        base = {**requirement}
        if binding is None:
            decisions.append({**base, "disposition": "missing_candidate"})
            continue
        asset = db.execute(
            "SELECT source,source_id,local_path,sha256,width,height,status FROM asset WHERE id=?",
            (binding["asset_id"],),
        ).fetchone()
        base.update({
            "asset_id": binding["asset_id"], "candidate_tier": binding["candidate_tier"],
            "source_caption": binding["source_caption"], **dict(asset),
        })
        review = db.execute(
            "SELECT status,result_json FROM review_queue WHERE queue_name=? AND asset_id=?",
            (queue, binding["asset_id"]),
        ).fetchone()
        if review is None or review["status"] != "completed":
            decisions.append({
                **base,
                "disposition": "review_" + (review["status"] if review else "missing"),
            })
            continue
        record = json.loads(review["result_json"])
        parsed = record.get("parsed")
        errors = record.get("schema_errors") or []
        if not isinstance(parsed, dict) or errors:
            decisions.append({**base, "disposition": "review_invalid", "schema_errors": errors})
            continue
        targets = {
            str(item.get("word", "")).casefold(): item
            for item in parsed.get("targets", []) if isinstance(item, dict)
        }
        target = targets.get(requirement["word"].casefold())
        evidence = {
            "review_worker": record.get("worker_id"), "review_backend": record.get("backend"),
            "review_model": record.get("model"), "review_attempt": record.get("attempt_number"),
            "literal_caption": parsed.get("literal_caption"),
            "visible_text": parsed.get("visible_text"), "watermark": parsed.get("watermark"),
            "quality_flags": parsed.get("quality_flags"), "uncertainties": parsed.get("uncertainties"),
            "target_evidence": target.get("evidence") if target else None,
        }
        if asset["status"].startswith("deleted_") or not asset["local_path"]:
            decisions.append({
                **base, **evidence,
                "disposition": asset["status"] if asset["status"].startswith("deleted_") else "asset_missing",
            })
            continue
        if parsed.get("watermark") is True:
            luna = _completed_result(db, watermark_queue, binding["asset_id"])
            alarm = None if luna is None else luna.get("alarm")
            if alarm == "true_watermark_or_added_overlay":
                decisions.append({**base, **evidence, "disposition": "rejected_watermark"})
                continue
            if alarm not in {"in_scene_text_or_branding"}:
                decisions.append({**base, **evidence, "disposition": "needs_luna_watermark"})
                continue
            evidence["watermark_adjudication"] = alarm
            evidence["watermark_adjudication_reason"] = luna.get("reason")
        if parsed.get("admission") != "usable" or parsed.get("uncertainties"):
            luna = _completed_result(db, usability_queue, binding["asset_id"])
            usability = None if luna is None else luna.get("usability")
            if usability == "unusable":
                decisions.append({**base, **evidence, "disposition": "rejected_unusable"})
                continue
            if usability != "usable":
                decisions.append({**base, **evidence, "disposition": "needs_luna_usability"})
                continue
            evidence["usability_adjudication"] = usability
            evidence["usability_adjudication_reason"] = luna.get("reason")
        if target is None:
            decisions.append({**base, **evidence, "disposition": "review_invalid"})
        elif target.get("visible") is True:
            decisions.append({
                **base, **evidence, "disposition": "accepted",
            })
        elif target.get("visible") == "uncertain":
            luna = _completed_result(db, word_fit_queue, binding["asset_id"])
            luna_targets = {} if luna is None else {
                str(item.get("word", "")).casefold(): item
                for item in luna.get("targets", []) if isinstance(item, dict)
            }
            luna_target = luna_targets.get(requirement["word"].casefold())
            verdict = None if luna_target is None else luna_target.get("verdict")
            if verdict == "accept":
                decisions.append({
                    **base, **evidence,
                    "word_fit_adjudication": verdict,
                    "word_fit_adjudication_reason": luna_target.get("reason"),
                    "disposition": "accepted",
                })
            elif verdict == "reject":
                decisions.append({
                    **base, **evidence,
                    "word_fit_adjudication": verdict,
                    "word_fit_adjudication_reason": luna_target.get("reason"),
                    "disposition": "rejected_word_fit",
                })
            elif verdict == "uncertain":
                sol = _completed_result(db, sol_word_fit_queue, binding["asset_id"])
                sol_targets = {} if sol is None else {
                    str(item.get("word", "")).casefold(): item
                    for item in sol.get("targets", []) if isinstance(item, dict)
                }
                sol_target = sol_targets.get(requirement["word"].casefold())
                sol_verdict = None if sol_target is None else sol_target.get("verdict")
                if sol_verdict == "accept":
                    decisions.append({
                        **base, **evidence,
                        "word_fit_adjudication": verdict,
                        "word_fit_adjudication_reason": luna_target.get("reason"),
                        "sol_final_judgment": sol_verdict,
                        "sol_final_judgment_reason": sol_target.get("reason"),
                        "disposition": "accepted",
                    })
                elif sol_verdict == "reject":
                    decisions.append({
                        **base, **evidence,
                        "word_fit_adjudication": verdict,
                        "word_fit_adjudication_reason": luna_target.get("reason"),
                        "sol_final_judgment": sol_verdict,
                        "sol_final_judgment_reason": sol_target.get("reason"),
                        "disposition": "rejected_word_fit",
                    })
                else:
                    decisions.append({
                        **base, **evidence,
                        "word_fit_adjudication": verdict,
                        "word_fit_adjudication_reason": luna_target.get("reason"),
                        "disposition": "needs_sol_word_fit",
                    })
            else:
                decisions.append({
                    **base, **evidence, "disposition": "needs_luna_word_fit",
                })
        else:
            decisions.append({
                **base, **evidence, "disposition": "target_not_visible",
            })
    return decisions


def freeze(decisions: list[dict], output: Path) -> dict:
    accepted = [row for row in decisions if row["disposition"] == "accepted"]
    if len(accepted) != 25_000:
        raise ValueError(f"cannot freeze: accepted {len(accepted):,} of 25,000 slots")
    accepted.sort(key=lambda row: row["sequence_position"])
    by_concept = defaultdict(list)
    for row in accepted:
        if not str(row.get("literal_caption", "")).strip():
            raise ValueError(f"M3 caption is empty: {row['slot_id']}")
        by_concept[row["concept_id"]].append(row)
    if len(by_concept) != 2500 or any(len(rows) != 10 for rows in by_concept.values()):
        raise ValueError("cannot freeze: corpus is not exactly 2,500 concepts × 10 images")
    for concept_id, rows in by_concept.items():
        if len({row["asset_id"] for row in rows}) != 10:
            raise ValueError(f"cannot freeze: {concept_id!r} does not have 10 distinct images")
    m2 = [{
        "slot_id": row["slot_id"], "sequence_position": row["sequence_position"],
        "ordinal": row["ordinal"], "example_index": row["exposure_index"],
        "word": row["word"], "concept": row["concept"],
        "asset_id": row["asset_id"], "asset_sha256": row["sha256"],
        "image_path": row["local_path"], "completion": row["word"],
    } for row in accepted]
    m3 = [{**row, "completion": source["literal_caption"]} for row, source in zip(m2, accepted)]
    _write(output / "m2-events.jsonl", m2)
    _write(output / "m3-events.jsonl", m3)
    manifest = {
        "schema_version": "ninereeds_campaign35_visual_curriculum_v1",
        "status": "frozen", "concept_count": 2500, "images_per_concept": 10,
        "event_count": 25000, "m2_target": "one_word", "m3_target": "literal_caption",
        "same_assets_and_order": True,
    }
    (output / "frozen-manifest.json").write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--watermark-queue")
    parser.add_argument("--usability-queue")
    parser.add_argument("--word-fit-queue")
    parser.add_argument("--sol-word-fit-queue")
    parser.add_argument("--freeze", action="store_true")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    requirements = _rows(args.requirements)
    if len(requirements) != 25_000:
        raise ValueError(f"requirements ledger has {len(requirements):,} rows, expected 25,000")
    with connect(args.db) as db:
        decisions = classify(
            db, args.queue, requirements,
            watermark_queue=args.watermark_queue,
            usability_queue=args.usability_queue,
            word_fit_queue=args.word_fit_queue,
            sol_word_fit_queue=args.sol_word_fit_queue,
        )
    decisions.sort(key=lambda row: row["sequence_position"])
    buckets = defaultdict(list)
    for row in decisions:
        buckets[row["disposition"]].append(row)
    _write(args.output / "decisions.jsonl", decisions)
    for name, rows in buckets.items():
        _write(args.output / f"{name}.jsonl", rows)
    accepted_by_concept = Counter(row["concept_id"] for row in buckets["accepted"])
    summary = {
        "required_slots": len(requirements),
        "dispositions": dict(sorted(Counter(row["disposition"] for row in decisions).items())),
        "fully_accepted_concepts": sum(count == 10 for count in accepted_by_concept.values()),
        "concepts_with_any_accepted_image": len(accepted_by_concept),
        "status": "review_in_progress" if any(
            row["disposition"].startswith("review_") for row in decisions
        ) else "review_complete_not_frozen",
    }
    if args.freeze:
        summary["frozen_manifest"] = freeze(decisions, args.output)
        summary["status"] = "frozen"
    (args.output / "summary.json").write_text(
        json.dumps(summary, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
