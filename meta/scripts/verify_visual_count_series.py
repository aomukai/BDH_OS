#!/usr/bin/env python3
"""Mechanically count red objects and compare controlled FLUX scenes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from PIL import Image

from training.pipeline.visual.color_count import (
    count_red_objects,
    scene_difference,
    union_masks,
)


def named_path(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("items must use NAME=PATH")
    return name, Path(path)


def expected_count(value: str) -> tuple[str, int]:
    name, separator, count = value.partition("=")
    if not separator or not name:
        raise argparse.ArgumentTypeError("expected counts must use NAME=INTEGER")
    try:
        parsed = int(count)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("expected count must be an integer") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("expected count must be non-negative")
    return name, parsed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--item", action="append", type=named_path, required=True)
    parser.add_argument("--expected", action="append", type=expected_count, default=[])
    parser.add_argument(
        "--requested",
        action="append",
        type=expected_count,
        default=[],
        help="commissioned count, independently of the human-labelled evaluator truth",
    )
    parser.add_argument("--object-label", default="red balls")
    parser.add_argument("--reference", help="item name used for pairwise scene comparison")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    item_paths = dict(args.item)
    if len(item_paths) != len(args.item):
        parser.error("item names must be unique")
    expected = dict(args.expected)
    requested = dict(args.requested)
    if set(expected) - set(item_paths):
        parser.error("every expected-count name must identify an item")
    if set(requested) - set(item_paths):
        parser.error("every requested-count name must identify an item")
    if args.reference is not None and args.reference not in item_paths:
        parser.error("--reference must identify an item")

    images = {}
    rows = []
    masks = {}
    for name, path in item_paths.items():
        with Image.open(path) as source:
            image = source.convert("RGB")
        images[name] = image
        observed, components, peaks, mask = count_red_objects(image)
        masks[name] = mask
        wanted = expected.get(name)
        commissioned = requested.get(name)
        failure_reasons = []
        if commissioned is not None and observed != commissioned:
            failure_reasons.append(
                {
                    "code": "exact_count_mismatch",
                    "expected": commissioned,
                    "observed": observed,
                    "evidence": "deterministic_saturated_red_shape_counter_v1",
                }
            )
        rows.append(
            {
                "name": name,
                "path": str(path),
                "asset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "width": image.width,
                "height": image.height,
                "observed_red_object_count": observed,
                "expected_red_object_count": wanted,
                "count_match": None if wanted is None else observed == wanted,
                "requested_red_object_count": commissioned,
                "commission_decision": None
                if commissioned is None
                else ("accept" if observed == commissioned else "reject"),
                "failure_reasons": failure_reasons,
                "salvage_candidate": None
                if commissioned is None or observed == commissioned
                else {
                    "teaching_goal": f"{observed} {args.object_label}",
                    "requires_semantic_visual_verification": True,
                    "basis": "mechanical count only; object identity must be independently confirmed",
                },
                "components": [component.to_dict() for component in components],
                "object_center_peaks": [peak.to_dict() for peak in peaks],
            }
        )

    if args.reference is not None:
        reference = images[args.reference]
        for row in rows:
            name = row["name"]
            exclusion = union_masks(masks[args.reference], masks[name])
            row["scene_difference_from_reference"] = scene_difference(
                reference, images[name], exclusion
            )

    checked = [row for row in rows if row["count_match"] is not None]
    report = {
        "schema_version": "ninereeds_deterministic_color_count_probe_v1",
        "reference": args.reference,
        "object_label": args.object_label,
        "items": rows,
        "metrics": {
            "checked": len(checked),
            "correct": sum(row["count_match"] is True for row in checked),
            "accuracy": None
            if not checked
            else round(sum(row["count_match"] is True for row in checked) / len(checked), 6),
        },
        "limitations": [
            "This verifier counts large connected saturated-red regions, not arbitrary objects.",
            "Red distractors, touching geometry outside the qualified range, severe occlusion, or large highlights require rejection or a different verifier.",
            "Scene-difference measurements are diagnostic until thresholds are qualified on labelled pass/fail pairs."
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
