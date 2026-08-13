"""Compile the exact bounded reading packet for a Sol campaign-planning job."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


PROCEDURE = Path("mission_hub/research/sol-planning-procedure.json")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_briefing(
    repo_root: Path,
    *,
    prior_goals: Path | None = None,
    prior_findings: Path | None = None,
    live_state: Path | None = None,
    max_bytes: int = 100_000,
) -> dict[str, Any]:
    root = repo_root.resolve()
    procedure_path = root / PROCEDURE
    procedure_bytes = procedure_path.read_bytes()
    procedure = json.loads(procedure_bytes)
    documents: list[dict[str, Any]] = []
    total_bytes = 0

    def add(path: Path, purpose: str, group: str) -> None:
        nonlocal total_bytes
        resolved = path if path.is_absolute() else root / path
        resolved = resolved.resolve()
        if resolved != root and root not in resolved.parents:
            raise ValueError(f"briefing input escapes repository: {path}")
        data = resolved.read_bytes()
        total_bytes += len(data)
        if total_bytes > max_bytes:
            raise ValueError(f"briefing exceeds byte budget: {total_bytes}/{max_bytes}")
        documents.append({
            "group": group,
            "path": resolved.relative_to(root).as_posix(),
            "purpose": purpose,
            "sha256": _sha256(data),
            "bytes": len(data),
            "content": data.decode("utf-8"),
        })

    for group in procedure["ordered_read_set"]:
        for value in group.get("required_paths", []):
            add(Path(value), group["purpose"], group["id"])
        if group["id"] == "prior_campaign":
            if prior_goals:
                add(prior_goals, group["purpose"], group["id"])
            if prior_findings:
                add(prior_findings, group["purpose"], group["id"])
    if live_state:
        add(live_state, "Supply authoritative current Mission Hub state and resource constraints.", "live_state")

    missing_runtime_inputs = []
    if bool(prior_goals) != bool(prior_findings):
        missing_runtime_inputs.append("prior campaign goals and findings must be supplied together")
    if live_state is None:
        missing_runtime_inputs.append("authoritative Mission Hub live-state snapshot")
    return {
        "schema_version": "ninereeds_sol_briefing_v1",
        "procedure": {
            "path": PROCEDURE.as_posix(),
            "sha256": _sha256(procedure_bytes),
            "instruction": procedure["instruction"],
            "required_forms": procedure["required_forms"],
            "output_contract": procedure["output_contract"],
        },
        "status": "ready" if not missing_runtime_inputs else "incomplete_runtime_inputs",
        "missing_runtime_inputs": missing_runtime_inputs,
        "total_content_bytes": total_bytes,
        "documents": documents,
    }


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--prior-goals", type=Path)
    parser.add_argument("--prior-findings", type=Path)
    parser.add_argument("--live-state", type=Path)
    parser.add_argument("--max-bytes", type=int, default=100_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(list(argv) if argv is not None else None)
    result = build_briefing(
        args.root,
        prior_goals=args.prior_goals,
        prior_findings=args.prior_findings,
        live_state=args.live_state,
        max_bytes=args.max_bytes,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "documents": len(result["documents"]),
        "content_bytes": result["total_content_bytes"],
        "output": str(args.output),
    }, sort_keys=True))
    return 0 if result["status"] == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
