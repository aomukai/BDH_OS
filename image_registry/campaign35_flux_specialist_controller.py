"""Autonomous residual Flux cycles for Campaign 35's exact single-image boundary."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from typing import Any, Iterable

from .campaign35_word_loop_controller import atomic_json, parse_config


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


class SpecialistController:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.base = parse_config(args.base_config)
        self.root = args.root
        self.state_path = self.root / "state.json"
        self.events_path = self.root / "events.jsonl"
        self.root.mkdir(parents=True, exist_ok=True)
        if self.state_path.exists():
            self.state = load(self.state_path)
        else:
            self.state = {
                "schema_version": "ninereeds_campaign35_flux_specialist_controller_v1",
                "status": "active", "phase": "wait_review", "cycle": args.initial_cycle,
                "review_result": str(args.initial_review_result),
                "generated_sources": [f"ninereeds_flux_campaign35_v{args.initial_cycle}"],
                "cycle_roots": [str(args.initial_review_result.parent)],
                "generated_roots": [str(args.initial_generated_root)],
                "created_at": now(), "updated_at": now(),
            }
            self.save("initialized")

    def save(self, event: str, **detail: Any) -> None:
        self.state["updated_at"] = now()
        atomic_json(self.state_path, self.state)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps({"at": now(), "event": event, "phase": self.state["phase"], **detail},
                                    ensure_ascii=False, sort_keys=True) + "\n")

    def phase(self, value: str, **updates: Any) -> None:
        self.state.update(updates)
        self.state["phase"] = value
        self.save("phase_changed", next_phase=value)

    def module(self, name: str, *arguments: str) -> None:
        log_root = self.root / "logs"
        log_root.mkdir(exist_ok=True)
        with (log_root / f"{name.rsplit('.', 1)[-1]}.log").open("a", encoding="utf-8") as log:
            result = subprocess.run([sys.executable, "-m", name, *arguments], stdout=log,
                                    stderr=subprocess.STDOUT, check=False)
        if result.returncode:
            raise RuntimeError(f"module failed ({result.returncode}): {name}")

    def command(self, arguments: list[str], *, output: bool = False) -> str:
        result = subprocess.run(arguments, text=True, capture_output=output, check=False)
        if result.returncode:
            raise RuntimeError(f"command failed ({result.returncode}): {arguments}: {result.stderr if output else ''}")
        return result.stdout.strip() if output else ""

    def cycle_root(self) -> Path:
        return self.root / f"cycle-{int(self.state['cycle']):04d}"

    def wait_review(self) -> None:
        result_path = Path(self.state["review_result"])
        while not result_path.is_file():
            time.sleep(self.args.poll_seconds)
        result = load(result_path)
        if result.get("status") != "reviewed_and_reconciled":
            raise ValueError("review result is not terminal and reconciled")
        cycle = int(self.state["cycle"])
        self.phase("plan", authoritative_decisions=result["authoritative_decisions"], cycle=cycle + 1)

    def plan(self) -> None:
        root = self.cycle_root()
        inventory = root / "inventory"
        arguments = [
            "--decisions", self.state["authoritative_decisions"],
            "--curriculum", str(self.base.curriculum), "--output", str(inventory),
            "--reuse-cap", str(self.base.reuse_cap),
        ]
        for path in self.args.representation_reconciliation:
            arguments.extend(["--representation-reconciliation", str(path)])
        if not (inventory / "summary.json").is_file():
            self.module("image_registry.campaign35_flux_gap_inventory", *arguments)
        summary = load(inventory / "summary.json")
        remaining = int(summary["confirmed_single_image_generation_slots"])
        if not remaining:
            self.phase("complete", final_inventory=str(inventory / "gap_inventory.jsonl"))
            return
        draft = root / "bundle-plan"
        audited = root / "bundle-audit"
        briefs = root / "production-briefs"
        if not (draft / "summary.json").is_file():
            self.module(
                "image_registry.campaign35_scene_bundle_plan",
                "--inventory", str(inventory / "gap_inventory.jsonl"), "--output", str(draft),
                "--workers", "8", "--batch-size", "16", "--retries", "5",
                "--reuse-cap", str(self.base.reuse_cap),
            )
        if not (audited / "summary.json").is_file():
            self.module(
                "image_registry.campaign35_scene_bundle_luna_audit",
                "--bundles", str(draft / "bundle_drafts.jsonl"), "--output", str(audited),
                "--workers", "4", "--retries", "5",
            )
        if not (briefs / "summary.json").is_file():
            self.module(
                "image_registry.campaign35_scene_prompt_compose",
                "--bundles", str(audited / "audited_bundles.jsonl"), "--output", str(briefs),
                "--workers", "8", "--batch-size", "8", "--retries", "5",
            )
        brief_summary = load(briefs / "summary.json")
        if int(brief_summary["assignment_slots"]) != remaining:
            raise ValueError("production briefs do not exactly cover residual single-image slots")
        self.phase("start_generation", expected_images=int(brief_summary["planned_flux_images"]),
                   inventory=str(inventory / "gap_inventory.jsonl"),
                   briefs=str(briefs / "production_briefs.jsonl"))

    def remote_unit_state(self, unit: str) -> tuple[str, str]:
        values = []
        for prop in ("ActiveState", "Result"):
            result = subprocess.run([
                "ssh", self.args.remote, "systemctl", "--user", "show",
                "-p", prop, "--value", unit,
            ], text=True, capture_output=True, check=False)
            values.append(result.stdout.strip() if result.returncode == 0 else "unknown")
        return values[0] or "unknown", values[1] or "unknown"

    def start_generation(self) -> None:
        cycle = int(self.state["cycle"])
        remote_root = f"{self.args.remote_root}/campaign35-flux-v{cycle}"
        self.command(["ssh", self.args.remote, "mkdir", "-p", remote_root])
        self.command(["rsync", "-a", "image_registry/campaign35_flux_generate.py",
                      f"{self.args.remote}:{remote_root}/campaign35_flux_generate.py"])
        self.command(["rsync", "-a", self.state["briefs"],
                      f"{self.args.remote}:{remote_root}/production_briefs.jsonl"])
        self.command(["ssh", self.args.remote, "systemctl", "--user", "stop",
                      "ninereeds-image-review-api.service", "ninereeds-vision-api.service"])
        existing_count = int(self.command([
            "ssh", self.args.remote,
            f"cat {remote_root}/generated/generation-shard-*.jsonl 2>/dev/null | wc -l",
        ], output=True) or 0)
        for gpu in (0, 1):
            unit = f"ninereeds-c35-flux-v{cycle}-gpu{gpu}"
            active, result = self.remote_unit_state(unit)
            if existing_count == int(self.state["expected_images"]) or active in {"active", "activating"}:
                continue
            subprocess.run(["ssh", self.args.remote, "systemctl", "--user", "reset-failed", unit],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            command = [
                "ssh", self.args.remote, "systemd-run", "--user", f"--unit={unit}",
                "--property=Nice=5", "--property=IOSchedulingClass=best-effort",
                "--property=IOSchedulingPriority=6", "--collect",
                self.args.remote_python, f"{remote_root}/campaign35_flux_generate.py",
                "--briefs", f"{remote_root}/production_briefs.jsonl",
                "--output", f"{remote_root}/generated", "--model", self.args.remote_model,
                "--gpu", str(gpu), "--shard", str(gpu), "--shards", "2",
                "--seed-namespace", f"campaign35-flux-v{cycle}",
            ]
            self.command(command)
        self.phase("wait_generation", remote_root=remote_root)

    def wait_generation(self) -> None:
        cycle = int(self.state["cycle"])
        units = [f"ninereeds-c35-flux-v{cycle}-gpu{gpu}" for gpu in (0, 1)]
        while True:
            ledger_count = self.command([
                "ssh", self.args.remote,
                f"cat {self.state['remote_root']}/generated/generation-shard-*.jsonl 2>/dev/null | wc -l",
            ], output=True)
            if int(ledger_count or 0) == int(self.state["expected_images"]):
                break
            states = [self.remote_unit_state(unit) for unit in units]
            if all(active == "inactive" for active, _ in states):
                if any(result != "success" for _, result in states):
                    raise RuntimeError(f"Flux shard failed: {states}")
                break
            time.sleep(self.args.poll_seconds)
        count = int(self.command([
            "ssh", self.args.remote,
            f"cat {self.state['remote_root']}/generated/generation-shard-*.jsonl | wc -l",
        ], output=True))
        if count != int(self.state["expected_images"]):
            raise ValueError(f"generated image count differs: {count}")
        self.phase("transfer")

    def transfer(self) -> None:
        cycle = int(self.state["cycle"])
        local = self.cycle_root() / "generated"
        local.mkdir(parents=True, exist_ok=True)
        self.command(["rsync", "-a", "--partial", f"{self.args.remote}:{self.state['remote_root']}/generated/",
                      f"{local}/"])
        self.command(["ssh", self.args.remote, "systemctl", "--user", "start",
                      "ninereeds-image-review-api.service"])
        self.phase("review", local_generated=str(local))

    def review(self) -> None:
        cycle = int(self.state["cycle"])
        for port in (8792, 8793):
            while subprocess.run(["curl", "-fsS", f"http://127.0.0.1:{port}/health"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode:
                time.sleep(10)
        root = self.cycle_root() / "review"
        arguments = [
            "--base-config", str(self.args.base_config), "--cycle-id", f"campaign35-flux-v{cycle}",
            "--cycle-root", str(root), "--image-root", self.state["local_generated"],
            "--ledger", f"{self.state['local_generated']}/generation-shard-00.jsonl",
            "--ledger", f"{self.state['local_generated']}/generation-shard-01.jsonl",
            "--inventory", self.state["inventory"],
            "--prior-decisions", self.state["authoritative_decisions"],
            "--source", f"ninereeds_flux_campaign35_v{cycle}",
        ]
        self.module("image_registry.campaign35_flux_review_stage", *arguments)
        result = load(root / "result.json")
        self.state["generated_sources"].append(f"ninereeds_flux_campaign35_v{cycle}")
        self.state["cycle_roots"].append(str(root))
        self.state["generated_roots"].append(self.state["local_generated"])
        self.phase("plan", authoritative_decisions=result["authoritative_decisions"], cycle=cycle + 1)

    def complete(self) -> None:
        output = self.root / "completion"
        args = [
            "--db", str(self.base.db), "--requirements", str(self.base.requirements),
            "--decisions", self.state["authoritative_decisions"],
            "--gap-inventory", self.state["final_inventory"],
            "--reuse-cap", str(self.base.reuse_cap), "--output", str(output),
        ]
        for root in self.args.representation_reconciliation:
            for name in ("single_image_needs.jsonl", "reclassified_dispositions.jsonl", "summary.json"):
                path = root / name
                if path.is_file():
                    args.extend(["--representation-evidence", str(path)])
        for source in self.state["generated_sources"]:
            args.extend(["--generated-source", source])
        for generated_root in self.state["generated_roots"]:
            for ledger in sorted(Path(generated_root).glob("generation-shard-*.jsonl")):
                args.extend(["--flux-ledger", str(ledger)])
        for cycle_root in self.state["cycle_roots"]:
            root = Path(cycle_root)
            decisions = root / "semantic-decisions/decisions.jsonl"
            if decisions.is_file():
                args.extend(["--review-evidence", str(decisions)])
        for evidence in self.state.get("additional_review_evidence", []):
            args.extend(["--review-evidence", str(evidence)])
        self.module("image_registry.campaign35_visual_completion", *args)
        handoff = load(output / "sol-handoff.json")
        if handoff.get("status") != "task_complete" or handoff.get("unresolved_teachable_items"):
            raise RuntimeError("completion auditor did not prove task completion")
        shutil.copyfile(output / "sol-handoff.json", self.args.loop_root / "sol-handoff.json")
        self.state.update({"status": "complete", "phase": "complete", "completed_at": now(),
                           "sol_handoff": str(output / "sol-handoff.json"),
                           "consecutive_failures": 0})
        self.state.pop("last_error", None)
        self.save("task_complete")

    def run(self) -> None:
        while self.state["status"] == "active":
            action = getattr(self, self.state["phase"])
            try:
                action()
            except Exception as exc:
                failures = int(self.state.get("consecutive_failures", 0)) + 1
                self.state["consecutive_failures"] = failures
                self.state["last_error"] = {"type": type(exc).__name__, "message": str(exc), "at": now()}
                self.save("phase_error", failure=failures)
                if failures >= 5:
                    raise
                time.sleep(60)
            else:
                self.state["consecutive_failures"] = 0
                self.state.pop("last_error", None)


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-config", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--loop-root", type=Path, required=True)
    parser.add_argument("--initial-cycle", type=int, required=True)
    parser.add_argument("--initial-review-result", type=Path, required=True)
    parser.add_argument("--initial-generated-root", type=Path, required=True)
    parser.add_argument("--representation-reconciliation", type=Path, action="append", required=True)
    parser.add_argument("--remote", default="ninereeds-trainbox")
    parser.add_argument("--remote-root", default="/home/aomukai/.local/share/ninereeds/visual")
    parser.add_argument("--remote-python", default="/home/aomukai/.venvs/ninereeds-vision/bin/python")
    parser.add_argument("--remote-model", default=(
        "/home/aomukai/.cache/huggingface/models--black-forest-labs--FLUX.2-klein-4B/"
        "snapshots/e7b7dc27f91deacad38e78976d1f2b499d76a294"
    ))
    parser.add_argument("--poll-seconds", type=float, default=30)
    args = parser.parse_args(list(argv) if argv is not None else None)
    SpecialistController(args).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
