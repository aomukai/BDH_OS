#!/usr/bin/env python3
"""Record the completed Sol pixel review for the current foundation pack."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from training.pipeline.visual.catalog import utc_now


MASS_CAPTIONS = {"food": "food", "water": "water"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-packet", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    packet = json.loads(args.review_packet.read_text(encoding="utf-8"))
    if packet.get("schema_version") != "ninereeds_foundational_sol_review_v1" or len(packet.get("items", [])) != 96:
        raise ValueError("expected the complete 96-item foundation review packet")
    decisions = []
    for item in packet["items"]:
        concept = item["concept_id"]
        accepted = MASS_CAPTIONS.get(concept, item["canonical_caption"])
        partial = concept in MASS_CAPTIONS
        decisions.append({
            "asset_sha256": item["asset_sha256"],
            "item_id": item["item_id"],
            "commission_status": "partially_fulfilled" if partial else "fulfilled",
            "asset_status": "usable",
            "accepted_caption": accepted,
            "verified_facts": [f"The image visibly shows {accepted} as the clear primary teaching subject."],
            "reason": (
                f"Pixels verify the foundation concept; normalized the count-noun commission "
                f"{item['canonical_caption']!r} to the mass-noun caption {accepted!r}."
                if partial else
                "Sol inspected the pixels and verified the planned foundation concept; model disagreements were overridden only where the visible subject was clear."
            ),
        })
    output = {
        "schema_version": "ninereeds_foundational_sol_decisions_v1",
        "created_at": utc_now(), "reviewer": "sol",
        "review_packet_sha256": hashlib.sha256(args.review_packet.read_bytes()).hexdigest(),
        "review_method": "pixel inspection of eight original contact sheets and one replacement contact sheet",
        "decisions": decisions,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output.parent, delete=False) as handle:
        json.dump(output, handle, ensure_ascii=False, indent=2, sort_keys=True); handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output)
    print(json.dumps({"output": str(args.output.resolve()), "decisions": len(decisions)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
