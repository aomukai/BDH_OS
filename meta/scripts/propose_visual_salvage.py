#!/usr/bin/env python3
"""Ask DeepSeek for non-authoritative alternative uses of failed visual commissions."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from training.pipeline.control.material_generator import DeepSeekMaterialGenerator
from training.pipeline.visual.catalog import utc_now
from training.pipeline.visual.salvage import parse_salvage_response, salvage_prompt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--provider-order",
        nargs="+",
        default=["openrouter", "nvidia", "deepseek"],
        help="v4 providers precede the legacy official-chat fallback",
    )
    parser.add_argument("--timeout-seconds", type=int, default=45)
    parser.add_argument("--transient-attempts", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=10.0)
    args = parser.parse_args()

    report = json.loads(args.input.read_text(encoding="utf-8"))
    series = [
        {
            "asset_sha256": row["asset_sha256"],
            "name": row["name"],
            "mechanically_observed_count": row["observed_red_object_count"],
        }
        for row in report["items"]
    ]
    items = []
    for row in report["items"]:
        if row.get("commission_decision") != "reject":
            continue
        items.append(
            {
                "asset_sha256": row["asset_sha256"],
                "original_teaching_goal": (
                    f"exactly {row['requested_red_object_count']} {report['object_label']}"
                ),
                "commission_decision": "reject",
                "failure_reasons": row["failure_reasons"],
                "mechanical_observations": {
                    "red_object_count": row["observed_red_object_count"],
                    "count_verifier_qualified_accuracy": report["metrics"]["accuracy"],
                    "object_center_peaks": row["object_center_peaks"],
                    "scene_difference_from_reference": row.get("scene_difference_from_reference"),
                },
                "visual_observations": {
                    "semantic_object_identity": "pending independent visual verification"
                },
                "candidate_pair_assets": [
                    candidate
                    for candidate in series
                    if candidate["asset_sha256"] != row["asset_sha256"]
                ],
            }
        )
    if not items:
        raise ValueError("input report contains no rejected commissions")

    generator = DeepSeekMaterialGenerator(
        repo_root=Path.cwd(), timeout_seconds=args.timeout_seconds,
        transient_attempts=args.transient_attempts,
        retry_backoff_seconds=args.retry_backoff_seconds,
    )
    response = generator.generate(
        {
            "prompt": salvage_prompt(items),
            "provider_order": args.provider_order,
            "max_tokens": 8192,
        }
    )
    proposals = parse_salvage_response(response["text"])
    expected = {item["asset_sha256"] for item in items}
    returned = {item["asset_sha256"] for item in proposals}
    if len(returned) != len(proposals) or returned != expected:
        raise ValueError("DeepSeek must return exactly one proposal for every rejected asset")

    output = {
        "schema_version": "ninereeds_visual_salvage_proposals_v1",
        "created_at": utc_now(),
        "source_report": str(args.input.resolve()),
        "assistant_provider": response["provider"],
        "assistant_model": response["model"],
        "assistant_attempt": response["attempt"],
        "authority": "proposal_only_pending_sol_pixel_review",
        "proposals": proposals,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "assistant_model": response["model"],
                "proposals": len(proposals),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
