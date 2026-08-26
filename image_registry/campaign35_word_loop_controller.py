"""Durable autonomous controller for Campaign 35's word-image acquisition loop.

This owns shallow orchestration.  Sol supplies one frozen configuration and receives one
terminal completion or exhaustion artifact; it does not babysit individual rounds.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import signal
import sqlite3
import subprocess
import sys
import time
from typing import Any

from .cli import DEFAULT_DB, connect
from .review_queue import (
    finalize_terminal_failures_as_unreviewable,
    queue_status,
    requeue_terminal_failures,
)


SCHEMA_VERSION = "ninereeds_campaign35_word_image_loop_v1"
RETRYABLE_ERRORS = {
    "HTTPError", "URLError", "TimeoutError", "ConnectionError", "RemoteDisconnected",
    "ValueError",  # schema-invalid model output; another worker/model may succeed
}
TERMINAL_PHASES = {"complete", "exhausted", "blocked"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def jsonl_count(path: Path, predicate=None) -> int:
    count = 0
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line:
                continue
            row = json.loads(line)
            if predicate is None or predicate(row):
                count += 1
    return count


@dataclass(frozen=True)
class LoopConfig:
    run_id: str
    root: Path
    db: Path
    store: Path
    curriculum: Path
    requirements: Path
    initial_decisions: Path
    initial_prior_queues: tuple[str, ...]
    reuse_cap: int = 4
    poll_seconds: float = 10.0
    max_item_attempts: int = 32
    download_workers: int = 16
    overfetch_factor: float = 2.0
    external_yield_floor: float = 0.15
    yield_floor_min_candidates: int = 500
    yield_floor_start_round: int = 17
    low_word_minimum_attempts: int = 8
    low_word_minimum_rounds: int = 2
    excluded_download_sources: tuple[str, ...] = ()
    allow_online_bulk_review: bool = False

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @property
    def events_path(self) -> Path:
        return self.root / "events.jsonl"


def initial_state(config: LoopConfig) -> dict[str, Any]:
    accepted = jsonl_count(
        config.initial_decisions,
        lambda row: row.get("disposition") == "accepted",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": config.run_id,
        "status": "active",
        "phase": "local_discover",
        "round": 1,
        "mode": None,
        "authoritative_decisions": str(config.initial_decisions.resolve()),
        "prior_review_queues": list(config.initial_prior_queues),
        "accepted_slots": accepted,
        "residual_slots": 25_000 - accepted,
        "no_progress_rounds": 0,
        "worker_generation": 0,
        "phase_failures": {},
        "created_at": now(),
        "updated_at": now(),
    }


@contextmanager
def exclusive_controller(root: Path):
    root.mkdir(parents=True, exist_ok=True)
    lock = (root / "controller.lock").open("a+")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        lock.close()
        raise RuntimeError("another image-loop controller already owns this run") from exc
    try:
        yield
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


class Controller:
    def __init__(self, config: LoopConfig):
        self.config = config
        self.stop_requested = False
        if config.state_path.exists():
            self.state = load_json(config.state_path)
            if self.state.get("run_id") != config.run_id:
                raise ValueError("state run_id differs from frozen configuration")
        else:
            self.state = initial_state(config)
            self.save("initialized")

    def save(self, event: str, **details: Any) -> None:
        self.state["updated_at"] = now()
        atomic_json(self.config.state_path, self.state)
        record = {"at": now(), "event": event, "phase": self.state["phase"], **details}
        with self.config.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def set_phase(self, phase: str, **updates: Any) -> None:
        previous = self.state.get("phase")
        if previous:
            self.state.setdefault("phase_failures", {})[previous] = 0
        self.state.update(updates)
        self.state["phase"] = phase
        self.save("phase_changed", next_phase=phase)

    def sync_cascades(self) -> None:
        """Materialize every currently implied escalation before testing completion."""
        from image_benchmark.luna_watermark_worker import sync_alarm_queue
        from image_benchmark.luna_usability_worker import sync_unusable_queue
        from image_benchmark.luna_word_fit_worker import sync_word_fit_queue
        from image_benchmark.sol_word_fit_worker import sync_queue as sync_sol_queue

        q = self.state["queues"]
        with connect(self.config.db) as db:
            sync_alarm_queue(db, q["semantic"], q["watermark"])
            sync_unusable_queue(db, q["semantic"], q["usability"])
            sync_word_fit_queue(db, q["semantic"], q["word_fit"])
            sync_sol_queue(db, q["word_fit"], q["sol"])

    def round_root(self) -> Path:
        return self.config.root / f"round-{self.state['round']:04d}"

    def run_command(self, name: str, arguments: list[str]) -> None:
        log_root = self.round_root() / "logs"
        log_root.mkdir(parents=True, exist_ok=True)
        log_path = log_root / f"{name}.log"
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n[{now()}] command: {json.dumps(arguments)}\n")
            result = subprocess.run(
                arguments, cwd=Path.cwd(), stdout=log, stderr=subprocess.STDOUT,
                text=True, check=False,
            )
        if result.returncode:
            raise RuntimeError(f"phase command failed ({result.returncode}): {name}; see {log_path}")

    def module(self, name: str, *arguments: str) -> None:
        self.run_command(name.replace(".", "-"), [sys.executable, "-m", name, *arguments])

    def local_discover(self) -> None:
        root = self.round_root()
        audit = root / "local-audit"
        proposal = root / "local-proposal"
        self.module(
            "image_registry.campaign35_word_images",
            "--db", str(self.config.db), "--curriculum", str(self.config.curriculum),
            "--output", str(audit), "--candidates-per-word", "100",
        )
        args = [
            "--db", str(self.config.db),
            "--decisions", self.state["authoritative_decisions"],
            "--candidate-pools", str(audit / "candidate_pools.jsonl"),
            "--output", str(proposal), "--max-asset-uses", str(self.config.reuse_cap),
        ]
        for queue in self.state["prior_review_queues"]:
            args.extend(["--prior-queue", queue])
        self.module("image_registry.campaign35_word_rerun", *args)
        summary = load_json(proposal / "summary.json")
        if summary["new_registry_review_slots"]:
            self.set_phase(
                "prepare_review", mode="local", proposal_root=str(proposal),
                candidate_slots=summary["new_registry_review_slots"],
            )
        else:
            self.set_phase("external_discover", mode="external")

    def external_discover(self) -> None:
        root = self.round_root()
        residual = Path(self.state["authoritative_decisions"]).parent / "residual_wishlist.jsonl"
        if not residual.is_file():
            raise FileNotFoundError(f"authoritative residual wishlist is missing: {residual}")
        routing = root / "yield-routing"
        self.module(
            "image_registry.campaign35_word_yield",
            "--loop-root", str(self.config.root),
            "--authoritative-decisions", self.state["authoritative_decisions"],
            "--output", str(routing),
            "--yield-floor", str(self.config.external_yield_floor),
            "--minimum-attempts", str(self.config.low_word_minimum_attempts),
            "--minimum-rounds", str(self.config.low_word_minimum_rounds),
        )
        routing_summary = load_json(routing / "summary.json")
        search_needs = routing / "external-needs.jsonl"
        specialist_needs = routing / "specialist-needs.jsonl"
        routing_updates = {
            "yield_routing": str(routing),
            "specialist_needs": str(specialist_needs),
            "specialist_slots": routing_summary["specialist_slots"],
            "low_yield_concepts": routing_summary["low_yield_concepts"],
            "external_eligible_slots": routing_summary["external_eligible_slots"],
            "recommended_next_route": (
                "representation triage, then minimal Flux edit or custom Flux generation "
                "for concrete single-image specialist residuals"
            ),
        }
        prior_reviewed = int(self.state.get("last_external_reviewed_candidates") or 0)
        prior_yield = self.state.get("last_external_target_fit_yield")
        if (
            self.state["round"] >= self.config.yield_floor_start_round
            and prior_reviewed >= self.config.yield_floor_min_candidates
            and prior_yield is not None
            and float(prior_yield) < self.config.external_yield_floor
        ):
            self.exhausted(
                "external target-fit yield previously fell below the frozen Flux-switch floor",
                external_yield_floor=self.config.external_yield_floor,
                **routing_updates,
            )
            return
        if routing_summary["external_eligible_slots"] == 0:
            self.exhausted(
                "all remaining concepts crossed the frozen per-concept external-yield floor",
                **routing_updates,
            )
            return
        oi = root / "open-images"
        localized = root / "localized"
        vg = root / "visual-genome"
        conceptual = root / "conceptual-captions"
        pixmo = root / "pixmo-cap"
        source = self.config.store / "sources"
        self.module(
            "image_registry.campaign35_word_open_images",
            "--index-db", str(source / "open_images_v7/train/annotations.sqlite3"),
            "--image-metadata", str(source / "open_images_v7/train/image_metadata.csv"),
            "--registry-db", str(self.config.db), "--needs", str(search_needs),
            "--output", str(oi),
        )
        self.module(
            "image_registry.campaign35_word_metadata",
            "--index-db", str(source / "localized_narratives/captions.sqlite3"),
            "--coco-db", str(source / "coco_2017/captions.sqlite3"),
            "--registry-db", str(self.config.db), "--wishlist", str(oi / "unresolved.jsonl"),
            "--output", str(localized),
        )
        self.module(
            "image_registry.campaign35_word_visual_genome",
            "--index-db", str(source / "visual_genome_v1_2/metadata.sqlite3"),
            "--registry-db", str(self.config.db),
            "--needs", str(localized / "unresolved.jsonl"),
            "--exclude-candidates", str(localized / "candidates.jsonl"),
            "--output", str(vg),
        )
        candidate_files = [oi / "candidates.jsonl", localized / "candidates.jsonl", vg / "candidates.jsonl"]
        conceptual_db = source / "conceptual_captions_labeled/metadata.sqlite3"
        if conceptual_db.is_file():
            args = [
                "--database", str(conceptual_db), "--registry-db", str(self.config.db),
                "--needs", str(search_needs), "--output", str(conceptual),
                "--overfetch-factor", str(self.config.overfetch_factor),
            ]
            for path in candidate_files:
                args.extend(["--existing-candidates", str(path)])
            self.module("image_registry.conceptual_captions_index", "shortlist", *args)
            candidate_files.append(conceptual / "candidates.jsonl")
        pixmo_db = source / "pixmo_cap/metadata.sqlite3"
        if pixmo_db.is_file():
            args = [
                "--database", str(pixmo_db), "--registry-db", str(self.config.db),
                "--needs", str(search_needs), "--output", str(pixmo),
                "--overfetch-factor", str(self.config.overfetch_factor),
            ]
            for path in candidate_files:
                args.extend(["--existing-candidates", str(path)])
            self.module("image_registry.pixmo_cap_index", "shortlist", *args)
            candidate_files.append(pixmo / "candidates.jsonl")
        total = sum(jsonl_count(path) for path in candidate_files)
        if not total:
            self.exhausted("all configured local and external metadata sources returned zero new candidates")
            return
        selection = f"{self.config.run_id}-r{self.state['round']:04d}-external"
        args: list[str] = ["--db", str(self.config.db)]
        for path in candidate_files:
            args.extend(["--candidates", str(path)])
        args.extend(["--selection", selection])
        self.module("image_registry.campaign35_word_candidates_registry", *args)
        self.set_phase(
            "external_download", mode="external", external_selection=selection,
            external_candidate_files=[str(path) for path in candidate_files],
            candidate_slots=total, **routing_updates,
        )

    def external_download(self) -> None:
        selection = self.state["external_selection"]
        download_args = [
            "--db", str(self.config.db), "download", selection,
            "--store", str(self.config.store), "--workers", str(self.config.download_workers),
            "--retries", "3", "--allow-partial",
            "--failure-output", str(self.round_root() / "download-failures.json"),
        ]
        for source in self.config.excluded_download_sources:
            download_args.extend(["--exclude-source", source])
        self.module("image_registry.cli", *download_args)
        self.module(
            "image_registry.cli", "--db", str(self.config.db), "inspect", selection,
            "--minimum-side", "256",
        )
        valid = selection + "-mechanically-valid"
        self.module(
            "image_registry.cli", "--db", str(self.config.db),
            "filter-mechanical", selection, valid,
        )
        self.set_phase("prepare_review", mechanically_valid_selection=valid)

    def queue_names(self) -> dict[str, str]:
        prefix = f"{self.config.run_id}-r{self.state['round']:04d}"
        return {
            "semantic": prefix + "-semantic",
            "watermark": prefix + "-watermark-luna",
            "usability": prefix + "-usability-luna",
            "word_fit": prefix + "-word-fit-luna",
            "sol": prefix + "-word-fit-sol",
        }

    def prepare_review(self) -> None:
        names = self.queue_names()
        root = self.round_root()
        if self.state["mode"] == "local":
            proposal = Path(self.state["proposal_root"])
            args = [
                "--db", str(self.config.db),
                "--decisions", self.state["authoritative_decisions"],
                "--candidate-pools", str(root / "local-audit/candidate_pools.jsonl"),
                "--output", str(proposal), "--max-asset-uses", str(self.config.reuse_cap),
                "--queue", names["semantic"], "--selection", names["semantic"],
            ]
            for queue in self.state["prior_review_queues"]:
                args.extend(["--prior-queue", queue])
            self.module("image_registry.campaign35_word_rerun", *args)
        else:
            pool = root / "candidate-pool"
            pool_args: list[str] = []
            for path in self.state["external_candidate_files"]:
                pool_args.extend(["--candidate", path])
            pool_args.extend(["--output", str(pool)])
            self.module("image_registry.campaign35_candidate_pool", "virtualize", *pool_args)
            args = [
                "--db", str(self.config.db), "--registry-proposal", "/dev/null",
            ]
            args.extend(["--metadata-proposal", str(pool / "candidates.jsonl")])
            args.extend([
                "--mechanically-ready-selection", self.state["mechanically_valid_selection"],
                "--queue", names["semantic"], "--selection", names["semantic"],
                "--output", str(root / "review-preparation"),
            ])
            self.module("image_registry.campaign35_word_review_prepare", *args)
        self.set_phase(
            "review_wait", queues=names, worker_generation=0,
            candidate_map=str(root / "candidate-pool/candidates.jsonl") if self.state["mode"] == "external" else None,
        )

    def worker_commands(self, generation: int) -> list[tuple[str, list[str]]]:
        q = self.state["queues"]
        common = [sys.executable, "-m", "image_benchmark.campaign35_word_worker",
                  "--queue", q["semantic"]]
        commands: list[tuple[str, list[str]]] = []
        if self.state.get("mode") == "local":
            for index in range(4):
                worker = f"{self.config.run_id}-local-luna-{index}-g{generation}"
                commands.append((worker, [
                    sys.executable, "-m", "image_benchmark.luna_campaign_word_worker",
                    "--queue", q["semantic"], "--worker-id", worker,
                    "--lease-seconds", "1800", "--timeout", "600",
                    "--max-attempts", str(self.config.max_item_attempts),
                ]))
        else:
            for gpu, port in (("gpu0", "8792"), ("gpu1", "8793")):
                worker = f"{self.config.run_id}-{gpu}-g{generation}"
                commands.append((worker, common + [
                    "--worker-id", worker, "--backend", f"llama.cpp-{gpu}",
                    "--endpoint", f"http://127.0.0.1:{port}/v1/chat/completions",
                    "--health-endpoint", f"http://127.0.0.1:{port}/health",
                    "--model", "gemma-4-26b-a4b-it-q4km", "--max-claims", "4",
                    "--max-attempts", str(self.config.max_item_attempts),
                    "--disable-thinking", "--require-valid-schema",
                ]))
        # Local Gemma is the default and authoritative bulk reviewer. Merely having
        # provider credentials in the service environment must never spend money or
        # mix remote review provenance into a run. Online bulk workers require an
        # explicit frozen-config opt-in.
        if (self.state.get("mode") != "local" and self.config.allow_online_bulk_review
                and os.environ.get("OPENROUTER_API_KEY")):
            for index in range(4):
                worker = f"{self.config.run_id}-openrouter-{index}-g{generation}"
                commands.append((worker, common + [
                    "--worker-id", worker, "--backend", "openrouter",
                    "--endpoint", "https://openrouter.ai/api/v1/chat/completions",
                    "--token-env", "OPENROUTER_API_KEY", "--model", "google/gemma-4-26b-a4b-it",
                    "--max-claims", "2", "--max-attempts", str(self.config.max_item_attempts),
                    "--disable-thinking", "--require-valid-schema",
                ]))
        if (self.state.get("mode") != "local" and self.config.allow_online_bulk_review
                and os.environ.get("NVIDIA_API_KEY")):
            for index in range(2):
                worker = f"{self.config.run_id}-nvidia-{index}-g{generation}"
                commands.append((worker, common + [
                    "--worker-id", worker, "--backend", "nvidia-nim",
                    "--endpoint", "https://integrate.api.nvidia.com/v1/chat/completions",
                    "--token-env", "NVIDIA_API_KEY", "--model", "google/gemma-4-31b-it",
                    "--max-claims", "2", "--max-attempts", str(self.config.max_item_attempts),
                    "--disable-thinking", "--require-valid-schema",
                ]))
        for kind, module, extra, count in (
            ("watermark", "image_benchmark.luna_watermark_worker",
             ["--source-queue", q["semantic"], "--queue", q["watermark"]], 2),
            ("usability", "image_benchmark.luna_usability_worker",
             ["--source-queue", q["semantic"], "--queue", q["usability"],
              "--watermark-queue", q["watermark"], "--skip-quarantine"], 2),
            ("word-fit", "image_benchmark.luna_word_fit_worker",
             ["--source-queue", q["semantic"], "--queue", q["word_fit"]], 2),
        ):
            for index in range(count):
                worker = f"{self.config.run_id}-{kind}-{index}-g{generation}"
                commands.append((worker, [
                    sys.executable, "-m", module, *extra, "--worker-id", worker,
                    "--lease-seconds", "300", "--timeout", "600",
                ]))
        sol_worker = f"{self.config.run_id}-sol-g{generation}"
        commands.append((sol_worker, [
            sys.executable, "-m", "image_benchmark.sol_word_fit_worker",
            "--semantic-source-queue", q["semantic"], "--luna-queue", q["word_fit"],
            "--queue", q["sol"], "--worker-id", sol_worker, "--model", "gpt-5.6-sol",
            "--lease-seconds", "300", "--timeout", "600",
        ]))
        return commands

    def spawn_workers(self, generation: int) -> list[subprocess.Popen]:
        log_root = self.round_root() / "worker-logs"
        log_root.mkdir(parents=True, exist_ok=True)
        children = []
        for worker, command in self.worker_commands(generation):
            log = (log_root / f"{worker}.log").open("a", encoding="utf-8")
            try:
                child = subprocess.Popen(
                    command, cwd=Path.cwd(), stdout=log, stderr=subprocess.STDOUT,
                    text=True,
                )
            finally:
                log.close()
            children.append(child)
        self.save("workers_spawned", generation=generation, count=len(children))
        return children

    def queue_counts(self, queue: str) -> dict[str, int]:
        with connect(self.config.db) as db:
            return queue_status(db, queue)["counts"]

    def requeue_failures(self, queue: str) -> int:
        with connect(self.config.db) as db:
            failures = db.execute(
                """SELECT q.asset_id,MAX(a.attempt_number) attempts,a.error_json
                   FROM review_queue q JOIN review_attempt a
                     ON a.queue_name=q.queue_name AND a.asset_id=q.asset_id
                   WHERE q.queue_name=? AND q.status='failed' GROUP BY q.asset_id""",
                (queue,),
            ).fetchall()
            terminal = []
            exhausted_candidates = []
            retry_types: set[str] = set()
            for row in failures:
                error_type = json.loads(row["error_json"] or "{}").get("type")
                if row["attempts"] >= self.config.max_item_attempts and error_type in RETRYABLE_ERRORS:
                    exhausted_candidates.append({
                        "asset_id": row["asset_id"], "attempts": row["attempts"],
                        "type": error_type,
                    })
                elif error_type not in RETRYABLE_ERRORS:
                    terminal.append({"asset_id": row["asset_id"], "attempts": row["attempts"], "type": error_type})
                else:
                    retry_types.add(error_type)
            if terminal:
                self.blocked("terminal review failures", failures=terminal)
                return 0
            if exhausted_candidates:
                completed = finalize_terminal_failures_as_unreviewable(
                    db, queue,
                    asset_ids=[row["asset_id"] for row in exhausted_candidates],
                )
                self.save(
                    "exhausted_candidates_closed_unreviewable",
                    queue=queue, count=completed, failures=exhausted_candidates,
                )
            requeued = (
                requeue_terminal_failures(db, queue, error_types=retry_types)
                if retry_types else 0
            )
            return requeued

    def review_wait(self) -> None:
        q = self.state["queues"]
        generation = int(self.state.get("worker_generation", 0)) + 1
        self.state["worker_generation"] = generation
        self.save("review_monitor_started", generation=generation)
        children = self.spawn_workers(generation)
        last_completed = -1
        stagnant = 0
        try:
            while not self.stop_requested and self.state["phase"] == "review_wait":
                self.sync_cascades()
                statuses = {name: self.queue_counts(queue) for name, queue in q.items()}
                semantic = statuses["semantic"]
                completed = semantic.get("completed", 0)
                if completed == last_completed:
                    stagnant += 1
                else:
                    stagnant = 0
                    last_completed = completed
                self.state["queue_status"] = statuses
                self.save("review_progress", semantic_completed=completed)

                for name, counts in statuses.items():
                    if counts.get("failed"):
                        requeued = self.requeue_failures(q[name])
                        if self.state["phase"] == "blocked":
                            return
                        if requeued:
                            self.save("failures_requeued", queue=q[name], count=requeued)
                            generation += 1
                            self.state["worker_generation"] = generation
                            children.extend(self.spawn_workers(generation))

                unfinished = {
                    name: counts.get("pending", 0) + counts.get("leased", 0)
                    for name, counts in statuses.items()
                }
                semantic_done = not unfinished["semantic"] and not statuses["semantic"].get("failed")
                cascades_done = semantic_done and all(
                    not unfinished[name] and not statuses[name].get("failed")
                    for name in ("watermark", "usability", "word_fit", "sol")
                )
                if cascades_done:
                    self.set_phase("round_finalize")
                    return
                alive = any(child.poll() is None for child in children)
                if unfinished["semantic"] and (not alive or stagnant >= 30):
                    generation += 1
                    self.state["worker_generation"] = generation
                    children.extend(self.spawn_workers(generation))
                    stagnant = 0
                time.sleep(self.config.poll_seconds)
        finally:
            if self.stop_requested:
                for child in children:
                    if child.poll() is None:
                        child.terminate()

    def round_finalize(self) -> None:
        root = self.round_root()
        q = self.state["queues"]
        decisions = root / "semantic-decisions"
        export_module = (
            "image_registry.campaign35_candidate_pool"
            if self.state.get("candidate_map") else "image_registry.campaign35_word_review_export"
        )
        export_args = [
            "--db", str(self.config.db), "--queue", q["semantic"],
            "--requirements", str(self.config.requirements), "--output", str(decisions),
            "--watermark-queue", q["watermark"], "--usability-queue", q["usability"],
            "--word-fit-queue", q["word_fit"], "--sol-word-fit-queue", q["sol"],
        ]
        if self.state.get("candidate_map"):
            export_args = ["export", *export_args, "--candidate-map", self.state["candidate_map"]]
        self.module(export_module, *export_args)
        reconciled = root / "reconciled-precap"
        capped = root / "reconciled-cap"
        before = self.state["accepted_slots"]
        self.module(
            "image_registry.campaign35_word_round_reconcile",
            "--prior", self.state["authoritative_decisions"],
            "--round", str(decisions / "decisions.jsonl"), "--output", str(reconciled),
        )
        self.module(
            "image_registry.campaign35_reuse_cap",
            "--input", str(reconciled / "decisions.jsonl"), "--output", str(capped),
            "--max-uses", str(self.config.reuse_cap),
        )
        summary = load_json(capped / "summary.json")
        if self.state["mode"] == "external":
            preview = root / "registry-finalization-preview.json"
            applied = root / "registry-finalization-applied.json"
            base = [
                "--db", str(self.config.db), "--store-root", str(self.config.store),
                "--main-queue", q["semantic"], "--watermark-queue", q["watermark"],
                "--usability-queue", q["usability"],
            ]
            overrides = root / "final-review-overrides.json"
            if overrides.is_file():
                base.extend(["--overrides", str(overrides)])
            self.module("image_registry.finalize_review", *base, "--output", str(preview))
            frontier = load_json(preview)
            self.module(
                "image_registry.finalize_review", *base,
                "--expected-usable", str(frontier["usable"]),
                "--expected-unusable", str(frontier["unusable"]), "--apply",
                "--output", str(applied),
            )
        accepted = summary["accepted_slots"]
        gained = accepted - before
        mode = self.state["mode"]
        reviewed_candidates = self.queue_counts(q["semantic"]).get("completed", 0)
        target_fit_yield = (
            gained / reviewed_candidates if mode == "external" and reviewed_candidates else None
        )
        prior = list(self.state["prior_review_queues"])
        prior.append(q["semantic"])
        # An unproductive local pass means that registry reuse is exhausted for
        # now; it does not mean the configured external sources were searched.
        # Only external no-progress rounds can establish deterministic source
        # exhaustion.
        external_no_progress = int(self.state.get("external_no_progress_rounds", 0))
        if mode == "external":
            external_no_progress = external_no_progress + 1 if gained == 0 else 0
        elif gained:
            external_no_progress = 0
        updates = {
            "round": self.state["round"] + 1,
            "mode": None,
            "authoritative_decisions": str(capped / "decisions.jsonl"),
            "prior_review_queues": prior,
            "accepted_slots": accepted,
            "residual_slots": summary["residual_slots"],
            "no_progress_rounds": external_no_progress,
            "external_no_progress_rounds": external_no_progress,
            "last_round_gain": gained,
            "last_external_reviewed_candidates": (
                reviewed_candidates if mode == "external" else self.state.get(
                    "last_external_reviewed_candidates"
                )
            ),
            "last_external_target_fit_yield": (
                target_fit_yield if mode == "external" else self.state.get(
                    "last_external_target_fit_yield"
                )
            ),
        }
        if summary["residual_slots"] == 0:
            self.complete(capped)
        elif mode == "local" and gained == 0:
            self.set_phase("external_discover", **updates)
        elif mode == "external" and external_no_progress >= 2:
            self.exhausted(
                "two consecutive fully reviewed external rounds added no accepted slots",
                **updates,
            )
        elif (
            mode == "external"
            and self.state["round"] >= self.config.yield_floor_start_round
            and reviewed_candidates >= self.config.yield_floor_min_candidates
            and target_fit_yield is not None
            and target_fit_yield < self.config.external_yield_floor
        ):
            self.exhausted(
                "external target-fit yield fell below the frozen Flux-switch floor",
                recommended_next_route=(
                    "representation triage, then minimal Flux edit or custom Flux generation "
                    "for concrete single-image residuals"
                ),
                external_yield_floor=self.config.external_yield_floor,
                **updates,
            )
        else:
            self.set_phase("local_discover", **updates)

    def complete(self, artifact_root: Path) -> None:
        self.state.update({"status": "complete", "phase": "complete", "completed_at": now()})
        handoff = {
            "schema_version": "ninereeds_visual_material_task_handoff_v1",
            "status": "task_complete", "run_id": self.config.run_id,
            "accepted_slots": 25_000, "unresolved_teachable_items": 0,
            "authoritative_artifact_root": str(artifact_root),
            "state": str(self.config.state_path), "events": str(self.config.events_path),
        }
        atomic_json(self.config.root / "sol-handoff.json", handoff)
        self.save("task_complete")

    def exhausted(self, reason: str, **updates: Any) -> None:
        self.state.update(updates)
        self.state.update({"status": "exhausted", "phase": "exhausted", "terminal_reason": reason})
        handoff = {
            "schema_version": "ninereeds_visual_material_task_handoff_v1",
            "status": "deterministic_sources_exhausted", "run_id": self.config.run_id,
            "reason": reason, "accepted_slots": self.state["accepted_slots"],
            "unresolved_teachable_items": self.state["residual_slots"],
            "authoritative_decisions": self.state["authoritative_decisions"],
            "next_authority": self.state.get(
                "recommended_next_route",
                "Sol chooses a new dataset, representation, rewrite, or Flux plan once",
            ),
            "specialist_needs": self.state.get("specialist_needs"),
            "specialist_slots": self.state.get("specialist_slots", 0),
            "state": str(self.config.state_path), "events": str(self.config.events_path),
        }
        atomic_json(self.config.root / "sol-handoff.json", handoff)
        self.save("deterministic_sources_exhausted", reason=reason)

    def blocked(self, reason: str, **details: Any) -> None:
        self.state.update({"status": "blocked", "phase": "blocked", "terminal_reason": reason})
        atomic_json(self.config.root / "blocker.json", {
            "schema_version": "ninereeds_image_loop_blocker_v1", "reason": reason,
            "details": details, "state": str(self.config.state_path), "at": now(),
        })
        self.save("blocked", reason=reason)

    def step(self) -> None:
        phase = self.state["phase"]
        if phase in TERMINAL_PHASES:
            return
        action = getattr(self, phase, None)
        if action is None:
            self.blocked("unknown controller phase", unknown_phase=phase)
            return
        try:
            action()
        except Exception as exc:
            failures = self.state.setdefault("phase_failures", {})
            failures[phase] = int(failures.get(phase, 0)) + 1
            self.state["last_error"] = {"type": type(exc).__name__, "message": str(exc), "at": now()}
            self.save("phase_error", error=self.state["last_error"])
            if failures[phase] >= 5:
                self.blocked(
                    "phase failed five consecutive controller attempts",
                    failed_phase=phase, error=self.state["last_error"],
                )
                return
            raise

    def run(self, once: bool = False) -> None:
        while self.state["phase"] not in TERMINAL_PHASES and not self.stop_requested:
            self.step()
            if once:
                return


def parse_config(path: Path) -> LoopConfig:
    raw = load_json(path)
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unknown image-loop configuration schema")
    required = (
        "run_id", "root", "db", "store", "curriculum", "requirements",
        "initial_decisions", "initial_prior_queues",
    )
    missing = [key for key in required if key not in raw]
    if missing:
        raise ValueError(f"configuration missing keys: {missing}")
    return LoopConfig(
        run_id=raw["run_id"], root=Path(raw["root"]), db=Path(raw["db"]),
        store=Path(raw["store"]), curriculum=Path(raw["curriculum"]),
        requirements=Path(raw["requirements"]), initial_decisions=Path(raw["initial_decisions"]),
        initial_prior_queues=tuple(raw["initial_prior_queues"]),
        reuse_cap=int(raw.get("reuse_cap", 4)), poll_seconds=float(raw.get("poll_seconds", 10)),
        max_item_attempts=int(raw.get("max_item_attempts", 32)),
        download_workers=int(raw.get("download_workers", 16)),
        overfetch_factor=float(raw.get("overfetch_factor", 2.0)),
        external_yield_floor=float(raw.get("external_yield_floor", 0.15)),
        yield_floor_min_candidates=int(raw.get("yield_floor_min_candidates", 500)),
        yield_floor_start_round=int(raw.get("yield_floor_start_round", 17)),
        low_word_minimum_attempts=int(raw.get("low_word_minimum_attempts", 8)),
        low_word_minimum_rounds=int(raw.get("low_word_minimum_rounds", 2)),
        excluded_download_sources=tuple(raw.get("excluded_download_sources", [])),
        allow_online_bulk_review=bool(raw.get("allow_online_bulk_review", False)),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    config = parse_config(args.config)
    with exclusive_controller(config.root):
        controller = Controller(config)

        def stop(_signum, _frame):
            controller.stop_requested = True

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        controller.run(once=args.once)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
