"""Compile Campaign 35's registry-first visual-material review surface.

This command is deliberately read-only.  It searches only reviewed registry
assets, shards the results into small Sol-sized batches, and reports residual
coverage.  It neither freezes a selection nor commissions image generation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import re
import sqlite3
from typing import Any, Iterable


DEFAULT_DB = Path("training_data/image_registry/registry.sqlite3")
DEFAULT_MATERIAL_ROOT = Path("config/mission_hub/campaign_material/campaign35")


def _read_only_db(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only = ON")
    return db


def _fts_query(value: str) -> str:
    tokens = re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE)
    if not tokens:
        raise ValueError(f"cannot derive a registry query from {value!r}")
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def _candidates(db: sqlite3.Connection, query: str, limit: int) -> list[dict[str, Any]]:
    rows = db.execute(
        """SELECT a.id, a.source, a.source_id, a.local_path, a.sha256,
                  a.width, a.height, ts.kind, ts.text,
                  bm25(text_search) AS score
           FROM text_search ts JOIN asset a ON a.id=ts.asset_id
           WHERE text_search MATCH ? AND a.status='reviewed_usable'
             AND a.local_path IS NOT NULL AND a.sha256 IS NOT NULL
           ORDER BY score, a.id LIMIT ?""",
        (query, max(limit * 8, 64)),
    )
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        result.append({
            "asset_id": row["id"],
            "source": row["source"],
            "source_id": row["source_id"],
            "local_path": row["local_path"],
            "sha256": row["sha256"],
            "width": row["width"],
            "height": row["height"],
            "matched_text_kind": row["kind"],
            "matched_text": row["text"],
        })
        if len(result) == limit:
            break
    return result


def _queue_state(db: sqlite3.Connection) -> dict[str, dict[str, int]]:
    exists = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_queue'"
    ).fetchone()
    if exists is None:
        return {}
    result: dict[str, dict[str, int]] = defaultdict(dict)
    for row in db.execute(
        """SELECT queue_name,status,COUNT(*) AS count FROM review_queue
           GROUP BY queue_name,status ORDER BY queue_name,status"""
    ):
        result[row["queue_name"]][row["status"]] = row["count"]
    return dict(result)


def _registry_state(db: sqlite3.Connection) -> dict[str, Any]:
    assets = {
        row["status"]: row["count"]
        for row in db.execute(
            "SELECT status,COUNT(*) AS count FROM asset GROUP BY status ORDER BY status"
        )
    }
    queues = _queue_state(db)
    # Only queues that govern corpus admission can prevent a material freeze.
    # Permanent benchmark suites deliberately retain pending cases and are not
    # part of the production review frontier.
    admission_queues = {
        name: counts for name, counts in queues.items()
        if name.startswith("visual-corpus-")
    }
    unfinished = sum(
        counts.get("pending", 0) + counts.get("leased", 0) + counts.get("failed", 0)
        for counts in admission_queues.values()
    )
    return {
        "asset_status_counts": assets,
        "review_queues": queues,
        "admission_review_queues": admission_queues,
        "unfinished_review_items": unfinished,
        "ready_to_freeze": unfinished == 0,
    }


def _visual_rows(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]


def compile_audit(
    db_path: Path,
    material_root: Path,
    output_root: Path,
    *,
    candidate_multiplier: int = 4,
    minimum_candidates: int = 8,
) -> dict[str, Any]:
    """Write a read-only, sharded candidate audit and return its summary."""
    if candidate_multiplier < 1 or minimum_candidates < 1:
        raise ValueError("candidate limits must be positive")
    manifest = json.loads((material_root / "manifest.json").read_text(encoding="utf-8"))
    output_root.mkdir(parents=True, exist_ok=True)
    batch_root = output_root / "batches"
    batch_root.mkdir(parents=True, exist_ok=True)

    total_required = total_candidates = directly_coverable = 0
    unit_counts: Counter[str] = Counter()
    batch_files: list[dict[str, Any]] = []
    with _read_only_db(db_path) as db:
        registry = _registry_state(db)
        for batch in manifest["batches"]:
            rows = _visual_rows(material_root / batch["visual_path"])
            by_ordinal: dict[int, list[dict[str, Any]]] = defaultdict(list)
            for row in rows:
                by_ordinal[row["ordinal"]].append(row)
            compiled: list[dict[str, Any]] = []
            for ordinal in sorted(by_ordinal):
                examples = by_ordinal[ordinal]
                concept = examples[0]["concept"]
                if any(row["concept"] != concept for row in examples):
                    raise ValueError(f"ordinal {ordinal} contains multiple concepts")
                required = len(examples)
                query = _fts_query(concept)
                candidates = _candidates(
                    db, query, max(minimum_candidates, required * candidate_multiplier),
                )
                status = (
                    "ready_for_sol_fit_review"
                    if len(candidates) >= required
                    else "needs_sol_query_expansion"
                )
                interpretations = []
                for row in examples:
                    match = re.search(
                        r"Visual interpretation:\s*(.*?)\s*One coherent scene", row["prompt"]
                    )
                    if match and match.group(1) not in interpretations:
                        interpretations.append(match.group(1))
                compiled.append({
                    "ordinal": ordinal,
                    "concept": concept,
                    "teaching_claims": sorted({row["canonical_caption"] for row in examples}),
                    "visual_interpretations": interpretations,
                    "required_count": required,
                    "item_ids": [row["item_id"] for row in examples],
                    "exact_query": query,
                    "status": status,
                    "candidate_count": len(candidates),
                    "candidates": candidates,
                    "sol_instruction": (
                        "Inspect pixels and choose only unambiguous teaching fits. If exact candidates "
                        "do not suffice, propose semantic-equivalent and alternate-realization queries "
                        "before declaring a residual gap. Do not commission Flux."
                    ),
                })
                total_required += required
                total_candidates += len(candidates)
                directly_coverable += min(required, len(candidates))
                unit_counts[status] += 1
            relative = Path("batches") / f"{batch['batch_id']}.jsonl"
            target = output_root / relative
            target.write_text(
                "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in compiled),
                encoding="utf-8",
            )
            batch_files.append({
                "batch_id": batch["batch_id"],
                "path": str(relative),
                "concept_units": len(compiled),
                "required_images": len(rows),
            })

    summary = {
        "schema_version": "ninereeds_campaign35_registry_audit_v1",
        "campaign_id": "campaign-35-multimodal-foundation-v1",
        "status": "preview_only_registry_still_processing" if not registry["ready_to_freeze"] else "ready_for_sol_review",
        "registry": registry,
        "policy": {
            "order": [
                "exact_registry_match", "semantic_equivalent", "alternate_realization",
                "external_acquisition", "minimal_flux_edit", "custom_flux_generation",
            ],
            "candidate_admission": "Sol fit decision followed by Luna image-to-lesson verification",
            "selection_freeze": "only after registry review is complete",
            "generation": "never dispatched by this audit",
        },
        "concept_units": sum(unit_counts.values()),
        "required_images": total_required,
        "exact_candidate_records": total_candidates,
        "exact_query_upper_bound_covered": directly_coverable,
        "exact_query_upper_bound_missing": total_required - directly_coverable,
        "unit_status_counts": dict(sorted(unit_counts.items())),
        "batches": batch_files,
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--material-root", type=Path, default=DEFAULT_MATERIAL_ROOT)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-multiplier", type=int, default=4)
    parser.add_argument("--minimum-candidates", type=int, default=8)
    args = parser.parse_args(list(argv) if argv is not None else None)
    summary = compile_audit(
        args.db, args.material_root, args.output,
        candidate_multiplier=args.candidate_multiplier,
        minimum_candidates=args.minimum_candidates,
    )
    print(json.dumps({
        "status": summary["status"],
        "concept_units": summary["concept_units"],
        "required_images": summary["required_images"],
        "exact_query_upper_bound_missing": summary["exact_query_upper_bound_missing"],
        "summary": str(args.output / "summary.json"),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
