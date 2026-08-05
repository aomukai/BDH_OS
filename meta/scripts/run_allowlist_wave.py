#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from training.pipeline.control.ledger import ControlLedger, LedgerError, utc_now
from training.pipeline.control.transport import SshControlTransport
from training.pipeline.cortex.artifacts import CortexCampaignPublisher


DEFAULT_CONTROL = Path("/home/aomukai/.local/state/ninereeds-orchestrator-control")
DEFAULT_PARENT = "core/cortex/baselines/foundation-language-only-20260731.pt"
WAVE_TIMER = "ninereeds-allowlist-wave.timer"
LRS = ("0.000003", "0.000001")
TERMINAL = {"completed", "blocked", "dead_letter"}
OBJECTIVE = (
    "Teach Ninereeds 1,500 additional allowlisted concepts (frequency ranks "
    "501–2000) in twelve guarded foundation-style blocks. Each block mixes 125 "
    "new concepts with 325 foundation replays and 50 identity/multilingual anchors, "
    "then requires deterministic held-out and protected-anchor admission before "
    "the candidate may become the next parent."
)


def _atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def _new_state(wave_id: str, parent: str) -> dict[str, Any]:
    return {
        "schema_version": "ninereeds_allowlist_wave_state_v1",
        "wave_id": wave_id,
        "status": "running",
        "phase": "ready",
        "block_index": 1,
        "attempt_index": 1,
        "parent_checkpoint": parent,
        "current_plan_id": None,
        "accepted_blocks": [],
        "rejected_attempts": [],
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "handoff": None,
    }


def _campaign_state(state: dict[str, Any], block_count: int) -> dict[str, Any]:
    status = str(state["status"])
    if status == "running":
        stop_reason = (
            f"Block {min(int(state['block_index']), block_count)} of {block_count}: "
            f"{str(state['phase']).replace('_', ' ')}."
        )
    elif status == "completed":
        stop_reason = "All allowlist blocks passed their deterministic admission gates."
    else:
        handoff = state.get("handoff") if isinstance(state.get("handoff"), dict) else {}
        stop_reason = str(handoff.get("reason") or "The guarded wave requires intervention.")
    return {
        "schema_version": "ninereeds_autonomous_campaign_v1",
        "campaign_id": state["wave_id"],
        "objective": OBJECTIVE,
        "created_at": state["started_at"],
        "updated_at": state["updated_at"],
        "status": status,
        "stop_reason": stop_reason,
        "current_plan_id": state.get("current_plan_id"),
        "boundary_index": min(int(state["block_index"]), block_count),
    }


def _reconcile_current_plan(
    ledger: ControlLedger,
    transport: SshControlTransport,
    plan_id: str,
) -> None:
    """Import a remote result or idempotently restore a missed dispatch.

    The local plan and wave state are authoritative.  A transport outage is not a
    campaign failure: the persistent timer will retry the same immutable plan on
    its next wake.
    """
    try:
        transport.sync(plan_id)
        return
    except (LedgerError, OSError, subprocess.SubprocessError):
        pass
    try:
        transport.dispatch(plan_id)
    except (LedgerError, OSError, subprocess.SubprocessError):
        pass


def _stop_persistent_wake_cycle() -> bool:
    """Disable future wakes after the wave reaches a durable terminal state."""
    completed = subprocess.run(
        ["/usr/bin/systemctl", "--user", "disable", "--now", WAVE_TIMER],
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    return completed.returncode == 0


def tick(
    repo: Path,
    control: Path,
    wave_id: str,
    parent: str,
    *,
    transport: SshControlTransport | None = None,
) -> dict[str, Any]:
    manifest_path = repo / "training/pipeline/cortex/allowlist_waves" / wave_id / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    state_path = control / "derived" / f"{wave_id}-state.json"
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else _new_state(wave_id, parent)
    ledger = ControlLedger(control)
    transport = transport or SshControlTransport(ledger)
    publisher = CortexCampaignPublisher(repo)
    publisher.ensure_campaign(_campaign_state(state, manifest["block_count"]))
    if state["status"] != "running":
        publisher.finalize(_campaign_state(state, manifest["block_count"]))
        return state

    block_index = int(state["block_index"])
    if block_index > manifest["block_count"]:
        state.update(
            status="completed",
            phase="handoff_ready",
            handoff={
                "text_checkpoint": state["parent_checkpoint"],
                "next_intervention": "Re-evaluate and retrain the SigLIP2 projector against this text checkpoint before resuming visual curriculum work.",
            },
            updated_at=utc_now(),
        )
        _atomic_json(state_path, state)
        publisher.finalize(_campaign_state(state, manifest["block_count"]))
        return state

    block = manifest["blocks"][block_index - 1]
    attempt = int(state["attempt_index"])
    if state["phase"] == "ready":
        session = f"{wave_id}-b{block_index:02d}-a{attempt}"
        plan_id = f"plan-train-{session}"
        ledger.create_plan(
            kind="cortex_block",
            mode="live",
            payload={
                "jsonl_path": block["training_path"],
                "output_checkpoint": f"core/cortex/{session}.pt",
                "runner_args": [
                    "--parent", state["parent_checkpoint"],
                    "--epochs", "1", "--batch-size", "1", "--lr", LRS[attempt - 1],
                    "--ingress-device", "cuda:0", "--core-device", "cuda:1",
                    "--train-scope", "full", "--rms-clip", "1.0",
                    "--stochastic-rounding", "--local-files-only",
                    "--probe-max-new-tokens", "24",
                ],
            },
            created_by="allowlist-wave-controller",
            plan_id=plan_id,
            authorization={
                "allow_weight_updates": True,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
            max_attempts=3,
        )
        state.update(phase="training", current_plan_id=plan_id, updated_at=utc_now())
        _atomic_json(state_path, state)
        return state

    current_plan_id = state["current_plan_id"]
    _reconcile_current_plan(ledger, transport, current_plan_id)
    receipt = ledger.receipt(current_plan_id)
    if receipt is None or receipt["status"] not in TERMINAL:
        return state
    if receipt["status"] != "completed":
        state.update(status="blocked", phase="training_failed", updated_at=utc_now(), handoff={"reason": receipt.get("last_error")})
        _atomic_json(state_path, state)
        return state

    if state["phase"] == "training":
        train_report = ledger.report(state["current_plan_id"])
        candidate = train_report["result"]["checkpoint_after"]
        session = Path(candidate).stem
        eval_id = f"plan-wave-eval-{session}"
        ledger.create_plan(
            kind="cortex_evaluation",
            mode="live",
            payload={
                "campaign_id": wave_id,
                "candidate_checkpoint": candidate,
                "parent_checkpoint": state["parent_checkpoint"],
                "target_concept": None,
                "suite_path": block["evaluation_path"],
                "output_path": f"core/cortex/evaluations/wave-{session}.json",
                "development_stage": "language_stabilization",
            },
            created_by="allowlist-wave-controller",
            parent_plan_id=state["current_plan_id"],
            plan_id=eval_id,
            authorization={
                "allow_weight_updates": False,
                "allow_checkpoint_promotion": False,
                "allow_auto_advance": False,
            },
            max_attempts=2,
        )
        state.update(phase="evaluating", current_plan_id=eval_id, updated_at=utc_now())
        _atomic_json(state_path, state)
        return state

    report = ledger.report(state["current_plan_id"])
    evaluation = report["result"]["evaluation"]
    certificate = report["result"]["certificate"]
    candidate = certificate["candidate_checkpoint"]
    summary = {
        "block_index": block_index,
        "attempt_index": attempt,
        "learning_rate": LRS[attempt - 1],
        "candidate_checkpoint": candidate,
        "certificate_status": certificate["status"],
        "target_gain": certificate["target_gain"],
        "overall_score": certificate["overall_score"],
        "parent_overall_score": certificate["parent_overall_score"],
        "protected_score": certificate["protected_score"],
        "parent_protected_score": certificate["parent_protected_score"],
        "failure_modes": certificate["failure_modes"],
        "evaluated_at": utc_now(),
    }
    publisher.publish_evaluation(
        campaign_state=_campaign_state(state, manifest["block_count"]),
        source_plan_id=state["current_plan_id"],
        evaluation=evaluation,
    )
    if certificate["status"] == "admitted":
        state["accepted_blocks"].append(summary)
        state.update(
            block_index=block_index + 1,
            attempt_index=1,
            parent_checkpoint=candidate,
            phase="ready",
            current_plan_id=None,
            updated_at=utc_now(),
        )
    else:
        state["rejected_attempts"].append(summary)
        if attempt < len(LRS):
            state.update(attempt_index=attempt + 1, phase="ready", current_plan_id=None, updated_at=utc_now())
        else:
            state.update(
                status="blocked",
                phase="evaluation_gate_failed",
                updated_at=utc_now(),
                handoff={
                    "reason": "Both conservative learning-rate attempts failed the deterministic admission gate.",
                    "rollback_checkpoint": state["parent_checkpoint"],
                    "last_certificate": summary,
                },
            )
    _atomic_json(state_path, state)
    publisher.finalize(_campaign_state(state, manifest["block_count"]))
    return state


def main() -> int:
    parser = argparse.ArgumentParser(description="Advance the guarded allowlist wave by one durable transition.")
    parser.add_argument("--repo", type=Path, default=REPO_ROOT)
    parser.add_argument("--control-root", type=Path, default=DEFAULT_CONTROL)
    parser.add_argument("--wave-id", default="allowlist-0501-2000-v1")
    parser.add_argument("--parent", default=DEFAULT_PARENT)
    args = parser.parse_args()
    result = tick(args.repo.resolve(), args.control_root, args.wave_id, args.parent)
    print(json.dumps({key: result.get(key) for key in ("wave_id", "status", "phase", "block_index", "attempt_index", "current_plan_id", "parent_checkpoint")}, sort_keys=True))
    if result["status"] in {"completed", "blocked"} and not _stop_persistent_wake_cycle():
        print(
            f"failed to disable terminal wake timer {WAVE_TIMER}",
            file=sys.stderr,
        )
        return 3
    return 0 if result["status"] != "blocked" else 2


if __name__ == "__main__":
    raise SystemExit(main())
