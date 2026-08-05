#!/usr/bin/env python3
"""Use DeepSeek to triage a Gemma visual-observation report into three buckets."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from training.pipeline.control.material_generator import DeepSeekMaterialGenerator
from training.pipeline.visual.catalog import utc_now
from training.pipeline.visual.triage import decision_prompt, effective_triage, parse_triage_response


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--provider-order", nargs="+", default=["deepseek", "openrouter", "nvidia"])
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--transient-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=10.0)
    parser.add_argument("--batch-size", type=int, default=12)
    args = parser.parse_args()
    report = json.loads(args.input.read_text(encoding="utf-8"))
    items = report["items"]
    if args.batch_size <= 0:
        parser.error("--batch-size must be positive")
    generator = DeepSeekMaterialGenerator(
        repo_root=Path.cwd(), timeout_seconds=args.timeout_seconds,
        transient_attempts=args.transient_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )
    known = {item["asset_sha256"] for item in items}
    if args.output.exists():
        output = json.loads(args.output.read_text(encoding="utf-8"))
        if output.get("source_report") != str(args.input.resolve()):
            raise ValueError("existing triage output belongs to a different report")
        decisions = output["decisions"]
        providers = output.get("provider_attempts", [])
    else:
        decisions = []
        providers = []
    completed = {row["asset_sha256"] for row in decisions}
    pending = [item for item in items if item["asset_sha256"] not in completed]
    for offset in range(0, len(pending), args.batch_size):
        batch = pending[offset : offset + args.batch_size]
        response = generator.generate(
            {"prompt": decision_prompt(batch), "provider_order": args.provider_order, "max_tokens": 4096}
        )
        proposed_rows = parse_triage_response(response["text"])
        proposed = {row["asset_sha256"]: row for row in proposed_rows}
        if len(proposed) != len(proposed_rows):
            raise ValueError("DeepSeek returned a duplicate asset_sha256")
        batch_known = {item["asset_sha256"] for item in batch}
        if set(proposed) - batch_known:
            raise ValueError("DeepSeek returned an unknown asset_sha256")
        for item in batch:
            asset = item["asset_sha256"]
            decisions.append({"asset_sha256": asset, **effective_triage(item, proposed.get(asset))})
        providers.append({"provider": response["provider"], "model": response["model"], "attempt": response["attempt"], "items": len(batch)})
        partial_counts = {bucket: sum(row["bucket"] == bucket for row in decisions) for bucket in ("accept", "check_again", "reject")}
        partial = {
            "schema_version": "ninereeds_visual_triage_v1", "created_at": utc_now(),
            "source_report": str(args.input.resolve()), "policy_provider": response["provider"],
            "policy_model": response["model"], "policy_attempt": response["attempt"],
            "provider_attempts": providers, "status": "running", "counts": partial_counts,
            "decisions": decisions,
        }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
            json.dump(partial, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            temporary = Path(handle.name)
        temporary.replace(args.output)
    counts = {bucket: sum(row["bucket"] == bucket for row in decisions) for bucket in ("accept", "check_again", "reject")}
    last = providers[-1] if providers else {"provider": None, "model": None, "attempt": None}
    output = {
        "schema_version": "ninereeds_visual_triage_v1",
        "created_at": utc_now(),
        "source_report": str(args.input.resolve()),
        "policy_provider": last["provider"],
        "policy_model": last["model"],
        "policy_attempt": last["attempt"],
        "provider_attempts": providers,
        "status": "complete" if len(decisions) == len(items) else "running",
        "counts": counts,
        "decisions": decisions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output.resolve()), "counts": counts}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
