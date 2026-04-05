from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from inference import BDHInference

ROOT = Path(__file__).resolve().parent
RUNS_DIR = ROOT / "runs"
SESSIONS_DIR = ROOT / "sessions"


@dataclass
class SessionSnapshot:
    request: str
    created_at: str
    session_id: str
    active_lora: str


@dataclass
class LoraSelection:
    lora: str
    type: str
    reason: str


def utc_timestamp() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")


def classify_request(request: str) -> dict[str, Any]:
    """Placeholder classification logic for milestone 1.

    This intentionally stays simple and deterministic.
    """
    lowered = request.lower()
    complexity = "simple"
    if len(request.split()) > 20:
        complexity = "medium"
    if any(word in lowered for word in ["analyze", "compare", "explain", "design"]):
        complexity = "complex"

    return {
        "task_type": "general_text",
        "complexity": complexity,
        "specialization_required": False,
    }


def select_lora(classification: dict[str, Any]) -> LoraSelection:
    # Milestone 1: simulate selection only.
    return LoraSelection(
        lora="none",
        type="core-only",
        reason="Milestone 1 placeholder selection; no real LoRA routing yet.",
    )


def snapshot_session(request: str, selection: LoraSelection) -> SessionSnapshot:
    ts = utc_timestamp()
    return SessionSnapshot(
        request=request,
        created_at=ts,
        session_id=f"session_{ts}",
        active_lora=selection.lora,
    )


def ensure_directories() -> None:
    for path in [
        RUNS_DIR,
        SESSIONS_DIR,
        ROOT / "workflow",
        ROOT / "loras" / "skills",
        ROOT / "loras" / "dreams",
        ROOT / "dream_queue",
        ROOT / "knowledge",
    ]:
        path.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_markdown(path: Path, title: str, body: str) -> None:
    path.write_text(f"# {title}\n\n{body.strip()}\n", encoding="utf-8")


def save_run_artifacts(
    run_dir: Path,
    request: str,
    classification: dict[str, Any],
    session: SessionSnapshot,
    selection: LoraSelection,
    specialist_output: str,
    final_output: str,
    logs: list[str],
) -> None:
    write_json(
        run_dir / "request.json",
        {
            "request": request,
            "classification": classification,
        },
    )
    write_json(run_dir / "session_snapshot.json", asdict(session))
    write_json(run_dir / "selected_lora.json", asdict(selection))
    write_markdown(run_dir / "specialist_output.md", "Specialist Output", specialist_output)
    write_markdown(run_dir / "final_output.md", "Final Output", final_output)
    write_json(
        run_dir / "metadata.json",
        {
            "created_at": utc_timestamp(),
            "pipeline": "milestone_1_vertical_slice",
            "core_checkpoint": "core/bdh_100m_final.pt",
            "core_reloaded": True,
        },
    )
    (run_dir / "logs.txt").write_text("\n".join(logs) + "\n", encoding="utf-8")


def run_specialist_phase(model: BDHInference, request: str, selection: LoraSelection) -> str:
    prompt = (
        "You are the specialist phase of BDH Cognitive OS. "
        "Process the request and produce a raw working artifact.\n\n"
        f"Request: {request}\n"
        f"Active LoRA: {selection.lora} ({selection.type})"
    )
    return model.generate_text(prompt)


def run_clean_core_phase(model: BDHInference, request: str, specialist_output: str) -> str:
    prompt = (
        "You are the clean core phase of BDH Cognitive OS. "
        "Read the specialist artifact and produce the outward-facing final answer.\n\n"
        f"Original request: {request}\n\n"
        f"Specialist artifact:\n{specialist_output}"
    )
    return model.generate_text(prompt)


def main() -> None:
    parser = argparse.ArgumentParser(description="BDH Cognitive OS harness (Milestone 1)")
    parser.add_argument(
        "request",
        nargs="?",
        help="Request text. If omitted, the harness prompts interactively.",
    )
    parser.add_argument(
        "--checkpoint",
        default="core/bdh_100m_final.pt",
        help="Path to the BDH checkpoint.",
    )
    parser.add_argument(
        "--max-new-tokens",
        type=int,
        default=96,
        help="Maximum new tokens to generate per phase.",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.8,
        help="Sampling temperature.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=40,
        help="Top-k sampling cutoff.",
    )
    args = parser.parse_args()

    request = args.request or input("Request: ").strip()
    if not request:
        raise SystemExit("Request cannot be empty.")

    ensure_directories()
    run_id = utc_timestamp()
    run_dir = RUNS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=False)

    logs: list[str] = []
    logs.append(f"[{utc_timestamp()}] Starting run {run_id}")

    classification = classify_request(request)
    logs.append(f"[{utc_timestamp()}] Classified request: {classification}")

    selection = select_lora(classification)
    logs.append(f"[{utc_timestamp()}] Selected LoRA: {asdict(selection)}")

    session = snapshot_session(request, selection)
    logs.append(f"[{utc_timestamp()}] Snapshot session: {asdict(session)}")

    model = BDHInference(
        checkpoint_path=ROOT / args.checkpoint,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
    )
    logs.append(f"[{utc_timestamp()}] Loaded core model from {args.checkpoint}")

    specialist_output = run_specialist_phase(model, request, selection)
    logs.append(f"[{utc_timestamp()}] Completed specialist phase")

    # Milestone 1 clean reload: instantiate a fresh wrapper to ensure core-only pass.
    model = BDHInference(
        checkpoint_path=ROOT / args.checkpoint,
        max_new_tokens=args.max_new_tokens,
        temperature=args.temperature,
        top_k=args.top_k,
    )
    logs.append(f"[{utc_timestamp()}] Reloaded clean core model")

    final_output = run_clean_core_phase(model, request, specialist_output)
    logs.append(f"[{utc_timestamp()}] Completed clean core phase")

    save_run_artifacts(
        run_dir=run_dir,
        request=request,
        classification=classification,
        session=session,
        selection=selection,
        specialist_output=specialist_output,
        final_output=final_output,
        logs=logs,
    )
    logs.append(f"[{utc_timestamp()}] Saved run artifacts to {run_dir}")

    print("\n=== Final Output ===\n")
    print(final_output)
    print(f"\nArtifacts saved to: {run_dir}")


if __name__ == "__main__":
    main()
