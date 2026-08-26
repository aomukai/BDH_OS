"""Recover reviewed/generated Campaign 36 staging images after a worker crash.

The normal worker admits an image only after normalization and an independent
Luna pixel review.  A crash between those steps and registry admission leaves a
staging file (or a downloaded Flux spool result).  This command re-runs the
pixel gate, admits every still-valid partial success, and publishes the same
append-only evidence records as the ordinary workers.  It is intentionally
idempotent: an already admitted ``source_id`` is never inserted twice.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
from types import SimpleNamespace
from typing import Any

from image_registry.campaign36_flux_streaming_luna import review_one
from image_registry.campaign36_imagegen_fallback import normalize_image
from image_registry.campaign36_replacement_flux_dispatcher import default_prompt
from image_registry.campaign36_replacement_generation_queue import connect as generation_connect
from image_registry.campaign36_replacement_imagegen_worker import (
    DEFAULT_ROOT,
    DEFAULT_STORE,
    admit,
    append_locked,
    digest,
    duplicate_hash,
    prompt_for,
)
from image_registry.cli import connect as registry_connect


IDENTIFIER = re.compile(
    r"^c36-repl-(?P<ordinal>\d+)-p(?P<prompt_cycle>\d+)-.*"
    r"-v(?P<variant>\d+)-r(?P<retry>\d+)$"
)


def flux_candidates(root: Path) -> dict[str, dict[str, Any]]:
    values: dict[str, dict[str, Any]] = {}
    for result_path in sorted((root / "flux-spool").glob("gpu*/results/*.json")):
        try:
            result = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        gpu_root = result_path.parents[1]
        for candidate in result.get("produced", []):
            if not isinstance(candidate, dict) or not candidate.get("remote_path"):
                continue
            identifier = Path(candidate["remote_path"]).stem
            source = gpu_root / "images" / Path(candidate["remote_path"]).name
            values[identifier] = {**candidate, "source": source}
    return values


def staged_candidates(root: Path) -> list[dict[str, Any]]:
    values: dict[tuple[str, str], dict[str, Any]] = {}
    for provider in ("imagegen", "flux"):
        for path in sorted((root / provider / "accepted-staging").glob("*.png")):
            values[(provider, path.stem)] = {
                "provider": provider, "identifier": path.stem,
                "staging": path, "source": None, "prompt": None,
            }
    for identifier, candidate in flux_candidates(root).items():
        source = Path(candidate["source"])
        if not source.is_file():
            continue
        key = ("flux", identifier)
        staging = root / "flux" / "accepted-staging" / source.name
        values.setdefault(key, {
            "provider": "flux", "identifier": identifier,
            "staging": staging, "source": source,
            "prompt": candidate.get("prompt"),
        })
        values[key]["source"] = source
        values[key]["prompt"] = candidate.get("prompt")
    return list(values.values())


def recover(args: argparse.Namespace) -> dict[str, int]:
    counts = {"discovered": 0, "accepted": 0, "rejected": 0,
              "duplicates": 0, "already_admitted": 0, "errors": 0}
    evidence_path = args.root / "staging-recovery-evidence.jsonl"
    for candidate in staged_candidates(args.root):
        counts["discovered"] += 1
        identifier = candidate["identifier"]
        match = IDENTIFIER.match(identifier)
        if match is None:
            append_locked(evidence_path, {
                "source_id": identifier, "status": "unrecognized_identifier",
            })
            counts["errors"] += 1
            continue
        provider = candidate["provider"]
        staging = Path(candidate["staging"])
        source = candidate.get("source")
        source = Path(source) if source else None
        try:
            with registry_connect(args.db) as db:
                existing = db.execute(
                    """SELECT id FROM asset
                       WHERE source='ninereeds_campaign36_replacement_generated'
                         AND source_id=?""", (identifier,),
                ).fetchone()
            if existing is not None:
                staging.unlink(missing_ok=True)
                if source is not None:
                    source.unlink(missing_ok=True)
                counts["already_admitted"] += 1
                continue
            with generation_connect(args.db) as db:
                raw = db.execute(
                    "SELECT * FROM campaign36_word_generation WHERE ordinal=?",
                    (int(match["ordinal"]),),
                ).fetchone()
            if raw is None:
                raise ValueError(f"no generation contract for ordinal {match['ordinal']}")
            item = dict(raw)
            staged_prompt_cycle = int(match["prompt_cycle"])
            if staged_prompt_cycle > int(item["prompt_cycle"]):
                raise ValueError("staged image prompt cycle is newer than its contract")
            # A prompt reviser may advance the live contract while a successfully
            # reviewed pixel is stranded before registry admission.  The pixel is
            # still valid for the same immutable concept/sense, and partial
            # successes must survive provider crossover.  Preserve the cycle that
            # actually produced it in the admitted evidence.
            item["prompt_cycle"] = staged_prompt_cycle
            if not staging.is_file():
                if source is None or not source.is_file():
                    raise FileNotFoundError(identifier)
                staging.parent.mkdir(parents=True, exist_ok=True)
                normalize_image(source, staging)
            sha256 = digest(staging)
            if duplicate_hash(args.db, sha256):
                append_locked(evidence_path, {
                    "source_id": identifier, "provider": provider,
                    "status": "duplicate_hash", "sha256": sha256,
                })
                staging.unlink(missing_ok=True)
                if source is not None:
                    source.unlink(missing_ok=True)
                counts["duplicates"] += 1
                continue
            variant = int(match["variant"])
            retry = int(match["retry"])
            prompt = str(candidate.get("prompt") or "").strip()
            if not prompt:
                prompt = (
                    prompt_for(item, variant=variant, retry=retry)
                    if provider == "imagegen" else default_prompt(item)
                )
            review_row = {
                "schema_version": "ninereeds_campaign36_replacement_generated_v1",
                "assignment_id": identifier,
                "production_brief_id": identifier,
                "variant_index": variant,
                "generation_attempt": retry,
                "concept_ids": [item["concept_id"]],
                "words": [item["word"]],
                "evidence_by_concept": {item["concept_id"]: item["teaching_sense"]},
                "grounding_mode": "direct",
                "visible_text_policy": "reject",
                "prompt": prompt,
                "local_path": str(staging),
                "sha256": sha256,
                "width": 512,
                "height": 384,
                "provider": "codex-built-in-imagegen" if provider == "imagegen" else "flux2-klein-4b",
            }
            verdict = review_one(
                review_row, staging,
                SimpleNamespace(codex=args.codex, model=args.review_model, timeout=args.review_timeout),
            )
            append_locked(evidence_path, {
                "source_id": identifier, "provider": provider,
                "status": verdict["verdict"], "sha256": sha256,
                "failure_reasons": verdict.get("failure_reasons", []),
                "review": verdict,
            })
            if verdict["verdict"] != "accepted":
                staging.unlink(missing_ok=True)
                if source is not None:
                    source.unlink(missing_ok=True)
                counts["rejected"] += 1
                continue
            record = admit(
                db_path=args.db, store=args.store, source_id=identifier,
                image=staging, sha256=sha256, prompt=prompt, item=item,
                verdict=verdict, provider=provider,
            )
            append_locked(args.root / "accepted-generated.jsonl", record)
            append_locked(args.root / "review-evidence.jsonl", {**record, "review": verdict})
            staging.unlink(missing_ok=True)
            if source is not None:
                source.unlink(missing_ok=True)
            counts["accepted"] += 1
        except Exception as exc:
            append_locked(evidence_path, {
                "source_id": identifier, "provider": provider,
                "status": "recovery_error", "type": type(exc).__name__,
                "message": str(exc),
            })
            counts["errors"] += 1
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--store", type=Path, default=DEFAULT_STORE)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--review-model", default="gpt-5.6-luna")
    parser.add_argument("--review-timeout", type=int, default=600)
    args = parser.parse_args()
    print(json.dumps(recover(args), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
