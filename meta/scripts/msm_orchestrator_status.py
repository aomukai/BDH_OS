#!/usr/bin/env python3
"""Print deterministic startup status for the stateless MSM orchestrator."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
MSM = ROOT / "training/pipeline/msm"
STATE = MSM / "state"
TRAINBOX_CONTROL_ROOT = Path("/home/aomukai/.local/state/ninereeds-control")
SENTINELS = {
    "HUMAN_ATTENTION",
    "BLOCKED",
    "TRAINING_MACHINE_DOWN",
    "API_CREDITS_EXHAUSTED",
    "PROMOTION_REVIEW_REQUIRED",
}
ORCHESTRATOR_STATUS_JSON = STATE / "orchestrator_status.json"
ORCHESTRATOR_STATUS_MD = STATE / "orchestrator_status.md"


def rel(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"_error": "invalid_json", "path": rel(path)}
    return data if isinstance(data, dict) else {"_error": "not_object", "path": rel(path)}


def latest(paths: list[Path]) -> Path | None:
    existing = [p for p in paths if p.exists()]
    if not existing:
        return None
    return max(existing, key=lambda p: p.stat().st_mtime)


def find_latest(pattern: str) -> Path | None:
    return latest(list(MSM.glob(pattern)))


def find_sentinels() -> list[str]:
    if not MSM.exists():
        return []
    found: list[str] = []
    for path in MSM.rglob("*"):
        if path.is_file() and path.name in SENTINELS:
            found.append(rel(path))
    return sorted(found)


def latest_cortex_run(
    control_root: Path = TRAINBOX_CONTROL_ROOT,
) -> dict[str, Any] | None:
    reports = control_root / "reports"
    if not reports.is_dir():
        return None
    for path in sorted(
        reports.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ):
        report = load_json(path)
        if not report or report.get("status") != "succeeded":
            continue
        result = report.get("result")
        if not isinstance(result, dict) or result.get("kind") != "cortex_block":
            continue
        metadata = result.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {}
        optimizer = metadata.get("optimizer")
        if not isinstance(optimizer, dict):
            optimizer = {}
        ownership = metadata.get("ownership")
        if not isinstance(ownership, dict):
            ownership = {}
        return {
            "status": result.get("status"),
            "plan_id": report.get("plan_id"),
            "completed_at": report.get("completed_at"),
            "checkpoint": result.get("checkpoint_after"),
            "architecture": metadata.get("architecture"),
            "trainable_parameters": ownership.get("trainable_parameters"),
            "optimizer_policy": optimizer.get("policy_version"),
            "initial_loss": metadata.get("initial_loss"),
            "final_loss": metadata.get("final_loss"),
        }
    return None


def session_requires_orchestrator(report: dict[str, Any] | None) -> bool:
    if not report:
        return False
    scores = report.get("scores")
    if isinstance(scores, dict) and scores.get("requires_orchestrator") is True:
        return True
    recommendation = report.get("executor_recommendation")
    if isinstance(recommendation, dict) and recommendation.get("requires_orchestrator_decision") is True:
        return True
    return False


def archived_session_ids(archive: dict[str, Any] | None) -> set[str]:
    if not archive:
        return set()
    entries = archive.get("entries")
    if not isinstance(entries, list):
        return set()
    return {entry["session_id"] for entry in entries if isinstance(entry, dict) and isinstance(entry.get("session_id"), str)}


def status_markdown(summary: dict[str, Any]) -> str:
    def fmt(value: Any) -> str:
        return "none" if value is None or value == "" else str(value)

    sentinels = summary.get("sentinels") or []
    sentinel_text = "\n".join(f"- {path}" for path in sentinels) if sentinels else "- none"
    return (
        "# MSM Orchestrator Status\n\n"
        f"- Regime: {fmt(summary.get('regime'))}\n"
        f"- Current phase: {fmt(summary.get('current_phase_id'))}\n"
        f"- Phase gate: {fmt(summary.get('phase_gate_status'))}\n"
        f"- Wake reason: {fmt(summary.get('wake_reason'))}\n"
        f"- Next safe action: {fmt(summary.get('next_safe_action'))}\n"
        f"- Codex brake: {fmt(summary.get('codex_brake_action'))}\n"
        f"- Latest phase block report: {fmt(summary.get('latest_block_report'))}\n"
        f"- Latest phase block status: {fmt(summary.get('latest_block_status'))}\n"
        f"- Latest phase block gate: {fmt(summary.get('latest_block_gate_status'))}\n"
        f"- Latest session report: {fmt(summary.get('latest_session_report'))}\n"
        f"- Latest session requires orchestrator: {fmt(summary.get('latest_session_requires_orchestrator'))}\n"
        f"- Latest session archived: {fmt(summary.get('latest_session_archived'))}\n"
        f"- Latest update eval: {fmt(summary.get('latest_update_eval'))}\n"
        "\n## Sentinels\n\n"
        f"{sentinel_text}\n"
    )


def write_status_files(summary: dict[str, Any]) -> None:
    STATE.mkdir(parents=True, exist_ok=True)
    ORCHESTRATOR_STATUS_JSON.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    ORCHESTRATOR_STATUS_MD.write_text(status_markdown(summary), encoding="utf-8")


def infer_next_action(
    *,
    registry: dict[str, Any] | None,
    config: dict[str, Any] | None,
    brake: dict[str, Any] | None,
    sentinels: list[str],
    latest_block_report: dict[str, Any] | None,
    latest_session_report: dict[str, Any] | None,
    latest_session_archived: bool,
    latest_update_eval: dict[str, Any] | None,
) -> tuple[str, str]:
    if sentinels:
        return "stop", "sentinel_present"
    if brake and brake.get("action") in {"pause_until_reset", "blocked_unknown_reset"}:
        return "stop", f"codex_brake:{brake.get('action')}"
    if registry is None:
        return "create_or_repair_phase_registry", "phase_registry_missing"
    if config is None:
        return "create_orchestrator_config", "orchestrator_config_missing"
    if session_requires_orchestrator(latest_session_report) and not latest_session_archived:
        return "review_session_report", "session_report_requires_orchestrator"
    if latest_update_eval is not None:
        decision = latest_update_eval.get("decision")
        if not isinstance(decision, dict) or decision.get("status") in {None, "manual_review"}:
            return "review_update", "update_review"
    if latest_block_report is None:
        return "run_phase_block", "no_block_yet"
    status = latest_block_report.get("status")
    gate_status = latest_block_report.get("gate_status")
    recommendation = latest_block_report.get("local_recommendation")
    if status == "planned":
        return "run_phase_block", "block_planned_not_run"
    if status == "failed" or gate_status == "blocked":
        return "escalate_or_repair_block", "block_failed"
    if recommendation == "phase_gate_review" or gate_status in {"met", "manual_review"}:
        return "review_phase_gate", "gate_review"
    if recommendation == "run_next_block_same_phase" and gate_status == "not_met":
        return "run_phase_block", "phase_gate_not_met"
    if recommendation == "escalate_orchestrator" or gate_status == "not_evaluated":
        return "decide_next_phase_action", "block_needs_decision"
    return "decide_next_phase_action", "block_finished"


def build_summary() -> dict[str, Any]:
    registry_path = STATE / "phase_registry.json"
    config_path = STATE / "orchestrator_config.json"
    brake_path = STATE / "codex_brake.json"
    registry = load_json(registry_path)
    config = load_json(config_path)
    brake = load_json(brake_path)
    session_archive = load_json(STATE / "session_archive.json")
    current_phase = registry.get("current_phase_id") if registry else None

    latest_block_path = None
    if isinstance(current_phase, str) and current_phase:
        latest_block_path = find_latest(f"phase_blocks/{current_phase}/*/block_report.json")
    if latest_block_path is None:
        latest_block_path = find_latest("phase_blocks/*/*/block_report.json")
    latest_block_report = load_json(latest_block_path) if latest_block_path else None

    latest_session = find_latest("sessions/*/report_card.json")
    latest_session_report = load_json(latest_session) if latest_session else None
    latest_update = find_latest("updates/*/update_candidate_eval.json")
    latest_update_eval = load_json(latest_update) if latest_update else None
    sentinels = find_sentinels()
    latest_session_id = latest_session_report.get("session_id") if latest_session_report else None
    latest_session_archived = (
        isinstance(latest_session_id, str)
        and latest_session_id in archived_session_ids(session_archive)
    )
    next_action, wake_reason = infer_next_action(
        registry=registry,
        config=config,
        brake=brake,
        sentinels=sentinels,
        latest_block_report=latest_block_report,
        latest_session_report=latest_session_report,
        latest_session_archived=latest_session_archived,
        latest_update_eval=latest_update_eval,
    )
    cortex = latest_cortex_run()

    return {
        "schema_version": "msm_orchestrator_status_v1",
        "regime": registry.get("regime") if registry else None,
        "current_phase_id": current_phase,
        "phase_gate_status": (
            registry.get("phases", {}).get(current_phase, {}).get("gate_status")
            if registry and isinstance(current_phase, str)
            else None
        ),
        "orchestrator_config_present": config is not None,
        "codex_brake_action": brake.get("action") if brake else None,
        "sentinels": sentinels,
        "latest_block_report": rel(latest_block_path) if latest_block_path else None,
        "latest_block_status": latest_block_report.get("status") if latest_block_report else None,
        "latest_block_gate_status": latest_block_report.get("gate_status") if latest_block_report else None,
        "latest_session_report": rel(latest_session) if latest_session else None,
        "latest_session_requires_orchestrator": session_requires_orchestrator(latest_session_report),
        "latest_session_archived": latest_session_archived,
        "latest_update_eval": rel(latest_update) if latest_update else None,
        "wake_reason": wake_reason,
        "next_safe_action": next_action,
        "cortex": cortex,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-files", action="store_true", help="Write orchestrator_status.json and orchestrator_status.md.")
    parser.add_argument("--quiet", action="store_true", help="Do not print JSON to stdout.")
    args = parser.parse_args()

    summary = build_summary()
    if args.write_files:
        write_status_files(summary)
    if not args.quiet:
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
