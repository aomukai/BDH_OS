"""Fresh Luna re-review of preserved Campaign 36 text-policy casualties.

Only candidates that passed the old semantic checks and failed exclusively for
text-related reasons enter this queue.  Results and acceptances are append-only.  If a
candidate still contains malformed or misleading writing, corrected Luna policy rejects
it and the next preserved candidate for that assignment may be tried.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from image_registry.campaign36_flux_streaming_luna import append_jsonl, digest, load_jsonl, review_one
from image_registry.campaign36_imagegen_fallback import (
    DEFAULT_ROOT,
    completed_assignments,
    exhausted_assignments,
    source_attempts,
)


SCHEMA_VERSION = "ninereeds_campaign36_text_policy_rereview_v1"


def imagegen_sources(root: Path) -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(root / "imagegen-v1" / "generation.jsonl", tolerate_partial_tail=True):
        attempt = row.get("attempt_id")
        if not attempt:
            attempt = (
                f"{row['production_brief_id']}-v{int(row['variant_index']):02d}"
                f"-a{int(row['generation_attempt']):02d}"
            )
        sources[str(attempt)] = row
    return sources


def all_sources(root: Path) -> dict[tuple[str, str], dict[str, Any]]:
    sources = {
        ("flux", attempt): row
        for attempt, row in source_attempts(root / "streaming-luna").items()
    }
    sources.update({
        ("codex-imagegen", attempt): row
        for attempt, row in imagegen_sources(root).items()
    })
    return sources


def review_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("provider", "")), str(row.get("attempt_id", ""))


def candidate_jobs(root: Path, audit: Path, ledger: Path) -> list[dict[str, Any]]:
    unresolved = {
        row["assignment_id"]
        for row in exhausted_assignments(root / "streaming-luna")
    } - completed_assignments(root / "imagegen-v1")
    reviewed = {
        review_key(row)
        for row in load_jsonl(ledger, tolerate_partial_tail=True)
    }
    accepted_hashes = {
        str(row["sha256"])
        for path in (
            root / "streaming-luna" / "decisions.jsonl",
            root / "imagegen-v1" / "decisions.jsonl",
            root / "imagegen-v1" / "policy-recoveries.jsonl",
        )
        for row in load_jsonl(path, tolerate_partial_tail=True)
        if row.get("verdict") == "accepted" and row.get("sha256")
    }
    sources = all_sources(root)
    by_assignment: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(audit, tolerate_partial_tail=True):
        assignment = str(row.get("assignment_id", ""))
        key = review_key(row)
        if (
            assignment not in unresolved
            or key in reviewed
            or not row.get("preserved")
            or row.get("failure_reasons") == ["visible_text"]
            or key not in sources
        ):
            continue
        path = Path(str(row.get("local_path", "")))
        expected_hash = str(row.get("sha256", ""))
        if (
            not path.is_file()
            or not expected_hash
            or digest(path) != expected_hash
            or expected_hash in accepted_hashes
        ):
            continue
        source = {
            **sources[key],
            "local_path": str(path),
            "sha256": expected_hash,
            "visible_text_policy": row.get("effective_visible_text_policy", "reject"),
            "visible_text_note": row.get("visible_text_note"),
        }
        by_assignment.setdefault(assignment, []).append({"candidate": row, "source": source})
    jobs = []
    for assignment, options in by_assignment.items():
        options.sort(key=lambda item: (
            item["candidate"].get("effective_visible_text_policy") == "required_evidence",
            -len(item["candidate"].get("failure_reasons", [])),
            item["candidate"].get("provider") == "codex-imagegen",
            item["candidate"].get("attempt_id", ""),
        ), reverse=True)
        jobs.append(options[0])
    jobs.sort(key=lambda item: item["candidate"]["assignment_id"])
    return jobs


def run_review(job: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    candidate = job["candidate"]
    source = job["source"]
    path = Path(candidate["local_path"])
    review_args = SimpleNamespace(codex=args.codex, model=args.model, timeout=args.timeout)
    fresh = review_one(source, path, review_args)
    return {
        "schema_version": SCHEMA_VERSION,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "provider": candidate["provider"],
        "attempt_id": candidate["attempt_id"],
        "assignment_id": candidate["assignment_id"],
        "concept_ids": source["concept_ids"],
        "local_path": str(path),
        "sha256": source["sha256"],
        "effective_visible_text_policy": candidate["effective_visible_text_policy"],
        "original_failure_reasons": candidate["failure_reasons"],
        "verdict": fresh["verdict"],
        "failure_reasons": fresh["failure_reasons"],
        "fresh_review": fresh,
    }


def recovery_record(review: dict[str, Any]) -> dict[str, Any]:
    fresh = review["fresh_review"]
    return {
        "schema_version": SCHEMA_VERSION,
        "recovered_at": review["reviewed_at"],
        "verdict": "accepted",
        "assignment_id": review["assignment_id"],
        "attempt_id": review["attempt_id"],
        "provider": review["provider"],
        "concept_ids": review["concept_ids"],
        "production_brief_id": fresh.get("production_brief_id"),
        "variant_index": fresh.get("variant_index"),
        "generation_attempt": fresh.get("generation_attempt"),
        "local_path": review["local_path"],
        "sha256": review["sha256"],
        "mechanical": fresh.get("mechanical"),
        "luna_result": fresh.get("luna_result"),
        "original_failure_reasons": review["original_failure_reasons"],
        "original_review_model": fresh.get("review_model"),
        "recovery_basis": "Fresh Luna review under the corrected visible-text policy.",
    }


def write_summary(root: Path, ledger: Path, remaining: int) -> None:
    rows = load_jsonl(ledger, tolerate_partial_tail=True)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "reviewed_candidates": len(rows),
        "accepted_candidates": sum(row.get("verdict") == "accepted" for row in rows),
        "rejected_candidates": sum(row.get("verdict") != "accepted" for row in rows),
        "remaining_candidate_assignments": remaining,
        "completed_exhausted_assignments": len(completed_assignments(root / "imagegen-v1")),
    }
    (root / "imagegen-v1" / "text-policy-rereview-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, sort_keys=True), flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        raise ValueError("workers must be between 1 and 16")
    audit = args.audit or args.root / "text-policy-audit-v1" / "candidates.jsonl"
    ledger = args.root / "imagegen-v1" / "text-policy-rereviews.jsonl"
    recovery = args.root / "imagegen-v1" / "policy-recoveries.jsonl"
    while True:
        jobs = candidate_jobs(args.root, audit, ledger)
        if not jobs:
            write_summary(args.root, ledger, 0)
            return 0
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(run_review, job, args) for job in jobs]
            for future in as_completed(futures):
                result = future.result()
                append_jsonl(ledger, result)
                if result["verdict"] == "accepted":
                    append_jsonl(recovery, recovery_record(result))
        write_summary(args.root, ledger, len(candidate_jobs(args.root, audit, ledger)))


if __name__ == "__main__":
    raise SystemExit(main())
