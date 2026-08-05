#!/usr/bin/env python3
"""Join candidate, Gemma, and DeepSeek evidence into Sol review packets and contact sheets."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

from training.pipeline.visual.catalog import AssetCatalog, utc_now


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def sheets(rows: list[dict[str, Any]], catalog: AssetCatalog, output_dir: Path, per_sheet: int = 12) -> list[str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for offset in range(0, len(rows), per_sheet):
        canvas = Image.new("RGB", (1024, 3 * 240), "white")
        draw = ImageDraw.Draw(canvas)
        for local_index, row in enumerate(rows[offset : offset + per_sheet]):
            column, line = local_index % 4, local_index // 4
            x, y = column * 256, line * 240
            with Image.open(catalog.root / row["object_path"]) as source:
                image = source.convert("RGB")
            image.thumbnail((248, 195))
            canvas.paste(image, (x + 4, y + 4))
            draw.text((x + 4, y + 202), f"{row['item_id']} | {row['triage']['bucket']}", fill="black")
            draw.text((x + 4, y + 218), row["asset_sha256"][:12], fill="black")
        path = output_dir / f"sol_review_{offset // per_sheet + 1:02d}.jpg"
        canvas.save(path, quality=92)
        paths.append(str(path.resolve()))
    return paths


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--gemma", type=Path, required=True)
    parser.add_argument("--triage", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sheet-dir", type=Path, required=True)
    args = parser.parse_args()
    candidates = json.loads(args.candidates.read_text(encoding="utf-8"))
    gemma = json.loads(args.gemma.read_text(encoding="utf-8"))
    triage = json.loads(args.triage.read_text(encoding="utf-8"))
    observations = {row["asset_sha256"]: row for row in gemma["items"]}
    policies = {row["asset_sha256"]: row for row in triage["decisions"]}
    catalog = AssetCatalog(args.catalog_root)
    assets = {row["asset_sha256"]: row for row in catalog.records()}
    rows = []
    for candidate in candidates["items"].values():
        digest = candidate["asset_sha256"]
        observed = observations[digest]
        policy = policies[digest]
        record = assets[digest]
        rows.append({
            "item_id": candidate["item_id"], "concept_id": candidate["concept_id"],
            "canonical_caption": candidate["canonical_caption"],
            "asset_sha256": digest, "display_filename": record["display_filename"],
            "object_path": record["object_path"], "source_kind": candidate["source_kind"],
            "gemma": {
                "parse_ok": observed["parse_ok"], "blind": observed.get("blind"),
                "rubric": observed.get("rubric"), "hard_gate_reasons": observed.get("hard_gate_reasons", []),
                "effective_decision": observed.get("effective_decision"),
            },
            "triage": policy,
            "required_sol_output": {
                "commission_status": "fulfilled | partially_fulfilled | failed",
                "asset_status": "usable | unusable",
                "accepted_caption": "exact verified foundation teaching caption, or null",
                "verified_facts": "array of literal facts checked against pixels",
                "reason": "concise pixel-grounded reason",
            },
        })
    packet = {
        "schema_version": "ninereeds_foundational_sol_review_v1", "created_at": utc_now(),
        "authority": {"gemma_observes": True, "deepseek_proposes": True, "sol_admits": True},
        "source_candidates": str(args.candidates.resolve()), "source_gemma": str(args.gemma.resolve()),
        "source_triage": str(args.triage.resolve()), "items": rows,
    }
    packet["contact_sheets"] = sheets(rows, catalog, args.sheet_dir)
    atomic_json(args.output, packet)
    print(json.dumps({"output": str(args.output.resolve()), "items": len(rows), "contact_sheets": len(packet["contact_sheets"])}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
