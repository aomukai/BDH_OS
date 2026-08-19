"""Durably ingest and fully review one completed Campaign 35 Flux cycle."""

from __future__ import annotations

import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import sys
from typing import Any, Iterable

from .campaign35_word_loop_controller import Controller, atomic_json, now, parse_config
from .cli import connect


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def run_module(name: str, *arguments: str) -> None:
    result = subprocess.run([sys.executable, "-m", name, *arguments], check=False)
    if result.returncode:
        raise RuntimeError(f"module failed ({result.returncode}): {name}")


def selection_count(db_path: Path, name: str) -> int:
    with connect(db_path) as db:
        return db.execute("SELECT COUNT(*) FROM selection WHERE name=?", (name,)).fetchone()[0]


def queue_count(db_path: Path, name: str) -> int:
    with connect(db_path) as db:
        return db.execute("SELECT COUNT(*) FROM review_queue WHERE queue_name=?", (name,)).fetchone()[0]


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--cycle-id", required=True)
    parser.add_argument("--cycle-root", type=Path, required=True)
    parser.add_argument("--image-root", type=Path, required=True)
    parser.add_argument("--ledger", type=Path, action="append", required=True)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--prior-decisions", type=Path, required=True)
    parser.add_argument("--source", required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)

    base = parse_config(args.base_config)
    args.cycle_root.mkdir(parents=True, exist_ok=True)
    selection = f"{args.cycle_id}-generated"
    mechanical = f"{selection}-mechanically-valid"
    queues = {
        "semantic": f"{args.cycle_id}-semantic",
        "watermark": f"{args.cycle_id}-watermark-luna",
        "usability": f"{args.cycle_id}-usability-luna",
        "word_fit": f"{args.cycle_id}-word-fit-luna",
        "sol": f"{args.cycle_id}-word-fit-sol",
    }
    ingest = args.cycle_root / "ingest"
    if not (ingest / "summary.json").is_file():
        command = [
            "--db", str(base.db), "--store", str(base.store),
            "--image-root", str(args.image_root), "--inventory", str(args.inventory),
            "--source", args.source, "--selection", selection, "--output", str(ingest),
        ]
        for ledger in args.ledger:
            command.extend(["--ledger", str(ledger)])
        run_module("image_registry.campaign35_flux_ingest", *command)
    expected = load(ingest / "summary.json")["assets"]
    if selection_count(base.db, selection) != expected:
        raise ValueError("ingested selection count differs from frozen generation ledger")

    run_module("image_registry.cli", "--db", str(base.db), "inspect", selection, "--minimum-side", "256")
    if not selection_count(base.db, mechanical):
        run_module("image_registry.cli", "--db", str(base.db), "filter-mechanical", selection, mechanical)
    if selection_count(base.db, mechanical) != expected:
        raise ValueError("a generated image failed mechanical inspection")

    preparation = args.cycle_root / "review-preparation"
    if not queue_count(base.db, queues["semantic"]):
        run_module(
            "image_registry.campaign35_word_review_prepare",
            "--db", str(base.db), "--registry-proposal", "/dev/null",
            "--metadata-proposal", str(ingest / "slot_proposals.jsonl"),
            "--mechanically-ready-selection", mechanical,
            "--queue", queues["semantic"], "--selection", queues["semantic"],
            "--output", str(preparation),
        )
    prepared = load(preparation / "summary.json")["items"]
    if prepared != expected or queue_count(base.db, queues["semantic"]) != expected:
        raise ValueError("semantic review queue does not exactly cover generated assets")

    controller_root = args.cycle_root / "review-controller"
    config = replace(base, run_id=args.cycle_id, root=controller_root,
                     initial_decisions=args.prior_decisions)
    state_path = controller_root / "state.json"
    if not state_path.exists():
        state = {
            "schema_version": "ninereeds_campaign35_word_image_loop_v1",
            "run_id": args.cycle_id, "status": "active", "phase": "review_wait",
            "round": 1, "mode": "external",
            "authoritative_decisions": str(args.prior_decisions),
            "prior_review_queues": list(base.initial_prior_queues),
            "accepted_slots": 0, "residual_slots": 25_000,
            "no_progress_rounds": 0, "worker_generation": 0,
            "phase_failures": {}, "queues": queues,
            "candidate_map": None, "created_at": now(), "updated_at": now(),
        }
        atomic_json(state_path, state)
    controller = Controller(config)
    if controller.state["phase"] == "review_wait":
        controller.review_wait()
    if controller.state["phase"] != "round_finalize":
        raise RuntimeError(f"review did not reach finalization: {controller.state['phase']}")

    decisions = args.cycle_root / "semantic-decisions"
    if not (decisions / "summary.json").is_file():
        run_module(
            "image_registry.campaign35_word_review_export",
            "--db", str(base.db), "--queue", queues["semantic"],
            "--requirements", str(base.requirements), "--output", str(decisions),
            "--watermark-queue", queues["watermark"],
            "--usability-queue", queues["usability"],
            "--word-fit-queue", queues["word_fit"],
            "--sol-word-fit-queue", queues["sol"],
        )
    reconciled = args.cycle_root / "reconciled-precap"
    capped = args.cycle_root / "reconciled-cap"
    if not (reconciled / "summary.json").is_file():
        run_module(
            "image_registry.campaign35_word_round_reconcile",
            "--prior", str(args.prior_decisions), "--round", str(decisions / "decisions.jsonl"),
            "--output", str(reconciled),
        )
    if not (capped / "summary.json").is_file():
        run_module(
            "image_registry.campaign35_reuse_cap", "--input", str(reconciled / "decisions.jsonl"),
            "--output", str(capped), "--max-uses", str(base.reuse_cap),
        )

    preview = args.cycle_root / "registry-finalization-preview.json"
    applied = args.cycle_root / "registry-finalization-applied.json"
    final_args = [
        "--db", str(base.db), "--store-root", str(base.store),
        "--main-queue", queues["semantic"], "--watermark-queue", queues["watermark"],
        "--usability-queue", queues["usability"],
    ]
    if not applied.is_file():
        run_module("image_registry.finalize_review", *final_args, "--output", str(preview))
        frontier = load(preview)
        run_module(
            "image_registry.finalize_review", *final_args,
            "--expected-usable", str(frontier["usable"]),
            "--expected-unusable", str(frontier["unusable"]), "--apply",
            "--output", str(applied),
        )
    result = {
        "schema_version": "ninereeds_campaign35_flux_review_stage_v1",
        "status": "reviewed_and_reconciled", "cycle_id": args.cycle_id,
        "generated_assets": expected, "queues": queues,
        "authoritative_decisions": str(capped / "decisions.jsonl"),
        "reconciliation_summary": load(capped / "summary.json"),
        "registry_finalization": load(applied),
    }
    (args.cycle_root / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
