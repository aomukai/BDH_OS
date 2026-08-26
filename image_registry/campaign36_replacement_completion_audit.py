"""Prove that the Campaign 36 replacement corpus is complete and internally sound.

The audit joins the frozen retained corpus with the reconciler's replacement selection,
then checks every one of the 25,000 required slots, the four-use global image cap,
review/generation terminal state, local-file presence, and (optionally) pixel-file hashes.
It only publishes the combined final manifest when every invariant passes.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sqlite3
from typing import Any, Iterable


def rows(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def atomic_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    hasher = hashlib.sha256()
    with temporary.open("w", encoding="utf-8") as handle:
        for value in values:
            line = json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n"
            handle.write(line)
            hasher.update(line.encode())
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return hasher.hexdigest()


def audit(args: argparse.Namespace) -> dict[str, Any]:
    requirements = rows(args.requirements)
    retained = rows(args.retained)
    replacements = rows(args.replacements)
    reconciliation = json.loads(args.reconciliation_summary.read_text(encoding="utf-8"))
    combined = retained + replacements
    errors: list[str] = []

    required_by_slot = {row["slot_id"]: row for row in requirements}
    if len(required_by_slot) != len(requirements):
        errors.append("requirements contain duplicate slot IDs")
    actual_by_slot: dict[str, dict[str, Any]] = {}
    for row in combined:
        slot = row.get("slot_id") or row.get("target_slot_id")
        if not slot:
            errors.append(f"asset lacks slot ID: {row.get('source_id') or row.get('sha256')}")
            continue
        if slot in actual_by_slot:
            errors.append(f"slot is filled more than once: {slot}")
        actual_by_slot[slot] = row

    missing = sorted(set(required_by_slot) - set(actual_by_slot))
    extra = sorted(set(actual_by_slot) - set(required_by_slot))
    if missing:
        errors.append(f"missing required slots: {len(missing)}")
    if extra:
        errors.append(f"unexpected slots: {len(extra)}")

    mismatched_slots: list[str] = []
    for slot in sorted(set(required_by_slot) & set(actual_by_slot)):
        required = required_by_slot[slot]
        actual = actual_by_slot[slot]
        if actual.get("word") != required.get("word") or actual.get("concept_id") != required.get("concept_id"):
            mismatched_slots.append(slot)
    if mismatched_slots:
        errors.append(f"slot word/concept mismatches: {len(mismatched_slots)}")

    # Surface forms are not unique teaching contracts: the frozen vocabulary can
    # deliberately contain homonyms such as ``nail``/``nail_2``.  Counting only
    # the displayed word collapses two ten-image concepts into a false twenty-
    # image violation.  Slot identity is already concept-aware, so the quota
    # invariant must use the same immutable (word, concept_id) partition.
    teaching_counts = Counter(
        (row.get("word"), row.get("concept_id")) for row in combined
    )
    bad_teaching_counts = {
        f"{word} [{concept_id}]": count
        for (word, concept_id), count in teaching_counts.items()
        if count != args.images_per_word
    }
    expected_teachings = {
        (row["word"], row["concept_id"]) for row in requirements
    }
    if set(teaching_counts) != expected_teachings:
        errors.append("combined manifest teaching-contract set differs from requirements")
    if bad_teaching_counts:
        errors.append(
            f"teaching contracts without exactly {args.images_per_word} images: "
            f"{len(bad_teaching_counts)}"
        )

    sha_counts: Counter[str] = Counter()
    missing_sha = 0
    missing_files: list[str] = []
    hash_mismatches: list[str] = []
    invalid_rows: list[str] = []
    for row in combined:
        sha = row.get("sha256") or row.get("asset_sha256")
        if not sha:
            missing_sha += 1
        else:
            sha_counts[str(sha)] += 1
        local = Path(str(row.get("local_path") or ""))
        if not local.is_file():
            missing_files.append(str(local))
        elif args.verify_content_hashes and sha and digest(local) != sha:
            hash_mismatches.append(str(local))
        # Raw Gemma watermark/status fields are alarms, not final verdicts.  A
        # frozen row may legitimately retain ``watermark: true`` after Luna
        # ruled it an in-scene logo, or ``mechanically_valid`` after the later
        # semantic gate accepted it.  The authoritative terminal fact is the
        # accepted disposition written by the corresponding reconciler.
        if not str(row.get("disposition") or "").startswith("accepted"):
            invalid_rows.append(str(row.get("slot_id") or row.get("source_id")))
    if missing_sha:
        errors.append(f"assets lacking SHA-256: {missing_sha}")
    overused = {sha: count for sha, count in sha_counts.items() if count > args.reuse_cap}
    if overused:
        errors.append(f"image hashes over the global reuse cap: {len(overused)}")
    if missing_files:
        errors.append(f"missing local image files: {len(missing_files)}")
    if hash_mismatches:
        errors.append(f"content hash mismatches: {len(hash_mismatches)}")
    if invalid_rows:
        errors.append(f"selected rows lacking an authoritative accepted disposition: {len(invalid_rows)}")

    if int(reconciliation.get("semantic_unfinished_claims", -1)) != 0:
        errors.append("semantic review is unfinished")
    if int(reconciliation.get("cascade_unfinished_claims", -1)) != 0:
        errors.append("Luna/Sol adjudication is unfinished")
    if int(reconciliation.get("residual_images", -1)) != 0:
        errors.append("reconciliation still has image deficits")
    if int(reconciliation.get("selected_slots", -1)) != len(replacements):
        errors.append("reconciliation selected-slot count disagrees with replacement manifest")

    with sqlite3.connect(args.db) as db:
        generation_counts = dict(
            db.execute("SELECT status,COUNT(*) FROM campaign36_word_generation GROUP BY status")
        )
        generation_totals = db.execute(
            """SELECT COUNT(*),COALESCE(SUM(target_count),0),
                      COALESCE(SUM(accepted_count),0),COALESCE(SUM(remaining_count),0)
               FROM campaign36_word_generation"""
        ).fetchone()
        leased_attempts = db.execute(
            "SELECT COUNT(*) FROM campaign36_word_generation_attempt WHERE status='leased'"
        ).fetchone()[0]
        has_review_queue = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_queue'"
        ).fetchone() is not None
        has_bindings = db.execute(
            """SELECT 1 FROM sqlite_master
               WHERE type='table' AND name='campaign35_word_review_slot_binding'"""
        ).fetchone() is not None
        exact_sense_review: dict[str, dict[str, int]] = {}
        exact_sense_bindings: dict[str, dict[str, int]] = {}
        if has_review_queue:
            for pool in ("metadata", "local"):
                queue = f"campaign36-visual-vocab-replacements-{pool}-v1-semantic"
                total, completed, exact = db.execute(
                    """SELECT COUNT(*),
                              COALESCE(SUM(status='completed'),0),
                              COALESCE(SUM(
                                status='completed' AND
                                json_extract(result_json,'$.prompt_version')
                                  ='campaign35-word-review-v2-exact-sense'
                              ),0)
                       FROM review_queue WHERE queue_name=?""",
                    (queue,),
                ).fetchone()
                exact_sense_review[queue] = {
                    "total": total, "completed": completed, "exact_sense_v2": exact,
                }
                if has_bindings:
                    binding_total, missing_sense = db.execute(
                        """SELECT COUNT(*),COALESCE(SUM(
                                   trim(COALESCE(teaching_sense,''))=''
                               ),0)
                           FROM campaign35_word_review_slot_binding
                           WHERE queue_name=?""",
                        (queue,),
                    ).fetchone()
                    exact_sense_bindings[queue] = {
                        "total": binding_total, "missing_sense": missing_sense,
                    }
        else:
            exact_sense_review = {}
    if set(generation_counts) != {"complete"} or generation_counts.get("complete") != generation_totals[0]:
        errors.append(f"generation queue is not wholly complete: {generation_counts}")
    if generation_totals[3] != 0 or generation_totals[2] != generation_totals[1]:
        errors.append("generation queue retains an image deficit")
    if leased_attempts:
        errors.append(f"generation attempts still leased: {leased_attempts}")
    if not exact_sense_review:
        errors.append("semantic review provenance evidence is missing")
    for queue, counts in exact_sense_review.items():
        if not counts["total"] or counts["completed"] != counts["total"] or counts["exact_sense_v2"] != counts["total"]:
            errors.append(f"semantic queue lacks complete exact-sense-v2 provenance: {queue} {counts}")
    if not exact_sense_bindings:
        errors.append("immutable teaching-sense binding evidence is missing")
    for queue, counts in exact_sense_bindings.items():
        if not counts["total"] or counts["missing_sense"]:
            errors.append(f"semantic queue has missing teaching-sense bindings: {queue} {counts}")

    report: dict[str, Any] = {
        "schema_version": "ninereeds_campaign36_replacement_completion_audit_v1",
        "complete": not errors,
        "errors": errors,
        "requirements": len(requirements),
        "combined_assets": len(combined),
        "retained_assets": len(retained),
        "replacement_assets": len(replacements),
        # ``words`` remains the marker's backwards-compatible contract count.
        # Also expose the literal surface-form count so the distinction is clear.
        "words": len(teaching_counts),
        "teaching_contracts": len(teaching_counts),
        "unique_surface_words": len({word for word, _ in teaching_counts}),
        "missing_slots": missing,
        "unexpected_slots": extra,
        "mismatched_slots": mismatched_slots,
        "bad_word_counts": bad_teaching_counts,
        "bad_teaching_contract_counts": bad_teaching_counts,
        "max_image_reuse": max(sha_counts.values(), default=0),
        "overused_hashes": overused,
        "missing_files": missing_files,
        "hash_mismatches": hash_mismatches,
        "invalid_selected_rows": invalid_rows,
        "generation_status_counts": generation_counts,
        "exact_sense_review": exact_sense_review,
        "exact_sense_bindings": exact_sense_bindings,
        "generation_totals": {
            "words": generation_totals[0],
            "target": generation_totals[1],
            "accepted": generation_totals[2],
            "remaining": generation_totals[3],
            "leased_attempts": leased_attempts,
        },
    }
    if not errors:
        ordered = [actual_by_slot[row["slot_id"]] for row in requirements]
        report["final_manifest"] = str(args.final_manifest)
        report["final_manifest_sha256"] = atomic_jsonl(args.final_manifest, ordered)
    atomic_json(args.output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--requirements", type=Path, required=True)
    parser.add_argument("--retained", type=Path, required=True)
    parser.add_argument("--replacements", type=Path, required=True)
    parser.add_argument("--reconciliation-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--final-manifest", type=Path, required=True)
    parser.add_argument("--images-per-word", type=int, default=10)
    parser.add_argument("--reuse-cap", type=int, default=4)
    parser.add_argument("--verify-content-hashes", action="store_true")
    args = parser.parse_args()
    result = audit(args)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
