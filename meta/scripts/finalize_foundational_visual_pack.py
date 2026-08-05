#!/usr/bin/env python3
"""Create an immutable training manifest from explicit Sol pixel-review decisions."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from training.pipeline.visual.catalog import AssetCatalog, utc_now


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-packet", type=Path, required=True)
    parser.add_argument("--sol-decisions", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.review_packet.read_text(encoding="utf-8"))
    decision_doc = json.loads(args.sol_decisions.read_text(encoding="utf-8"))
    decisions = {row["asset_sha256"]: row for row in decision_doc["decisions"]}
    expected = {row["asset_sha256"] for row in packet["items"]}
    if set(decisions) != expected or len(decisions) != len(decision_doc["decisions"]):
        raise ValueError("Sol must decide every candidate exactly once")
    catalog = AssetCatalog(args.catalog_root)
    records = {row["asset_sha256"]: row for row in catalog.records()}
    assets = []
    rejected = []
    for index, item in enumerate(packet["items"]):
        decision = decisions[item["asset_sha256"]]
        if decision.get("asset_status") not in {"usable", "unusable"}:
            raise ValueError("invalid Sol asset status")
        if decision.get("commission_status") not in {"fulfilled", "partially_fulfilled", "failed"}:
            raise ValueError("invalid immutable commission status")
        facts = decision.get("verified_facts")
        if not isinstance(facts, list) or not facts or not all(isinstance(fact, str) and fact.strip() for fact in facts):
            raise ValueError("Sol decisions require non-empty pixel-verified facts")
        if not isinstance(decision.get("reason"), str) or not decision["reason"].strip():
            raise ValueError("Sol decisions require a reason")
        if decision["asset_status"] == "unusable":
            rejected.append({
                "item_id": item["item_id"], "asset_sha256": item["asset_sha256"],
                "commission_status": decision["commission_status"], "asset_status": "unusable",
                "actual_facts": [fact.strip() for fact in facts], "potential_uses": [],
                "failure_reason": decision["reason"].strip(),
            })
            continue
        accepted_caption = decision.get("accepted_caption")
        if not isinstance(accepted_caption, str) or not accepted_caption.strip():
            raise ValueError("usable foundation assets require an explicit verified caption")
        record = records[item["asset_sha256"]]
        object_path = catalog.root / record["object_path"]
        if hashlib.sha256(object_path.read_bytes()).hexdigest() != item["asset_sha256"]:
            raise ValueError("catalog object hash mismatch")
        assets.append({
            "item_id": item["item_id"], "concept_id": item["concept_id"],
            "original_commission_caption": item["canonical_caption"],
            "commission_status": decision["commission_status"],
            "canonical_caption": accepted_caption.strip(), "asset_sha256": item["asset_sha256"],
            "object_path": record["object_path"], "width": record["width"], "height": record["height"],
            "media_type": record["media_type"], "source": record["source"], "lineage": record["lineage"],
            "training_role": "validation" if item["item_id"].endswith("_04") else "train",
            "disposition": {
                "commission_status": decision["commission_status"], "asset_status": "usable",
                "actual_facts": [fact.strip() for fact in facts],
                "potential_uses": [accepted_caption.strip()],
                "failure_reason": None if decision["commission_status"] == "fulfilled" else decision["reason"].strip(),
            },
            "sol_review": decision,
        })
    counts = {}
    for asset in assets:
        counts[asset["concept_id"]] = counts.get(asset["concept_id"], 0) + 1
    complete = all(counts.get(item["concept_id"], 0) == 4 for item in packet["items"] if item["item_id"].endswith("_01"))
    manifest = {
        "schema_version": "ninereeds_visual_pack_manifest_v1", "pack_id": "foundation-objects-v1",
        "created_at": utc_now(), "status": "accepted" if complete and not rejected else "incomplete",
        "authority": "sol_pixel_verified", "review_packet_sha256": hashlib.sha256(args.review_packet.read_bytes()).hexdigest(),
        "asset_count": len(assets), "rejected": rejected, "assets": assets,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2, sort_keys=True); handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output.resolve()), "status": manifest["status"], "accepted": len(assets), "rejected": len(rejected)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
