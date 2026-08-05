#!/usr/bin/env python3
"""Import Oxford-IIIT Pet parquet images into the visual asset catalog."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyarrow.parquet as parquet

from training.pipeline.visual.catalog import AssetCatalog


DATASET_NAME = "Oxford-IIIT Pet"
DATASET_REVISION = "timm/oxford-iiit-pet@10b6888"
DATASET_LICENSE = "CC-BY-SA-4.0"


def breed_name(image_id: str) -> str:
    stem, separator, number = image_id.rpartition("_")
    value = stem if separator and number.isdigit() else image_id
    return value.replace("_", " ").strip().lower()


def import_parquet(
    catalog: AssetCatalog,
    path: Path,
    *,
    split: str,
    qualification_per_species: int,
    limit: int | None,
) -> dict[str, int]:
    table = parquet.read_table(path, columns=["image", "image_id", "label_cat_dog"])
    counts = {"cat": 0, "dog": 0}
    imported = 0
    for row in table.to_pylist():
        if limit is not None and imported >= limit:
            break
        species = "cat" if row["label_cat_dog"] == 0 else "dog"
        breed = breed_name(row["image_id"])
        selected_split = (
            "qualification"
            if split == "train" and counts[species] < qualification_per_species
            else split
        )
        counts[species] += 1
        catalog.import_bytes(
            row["image"]["bytes"],
            {
                "display_filename": row["image"]["path"],
                "family_id": f"oxford-pet:{row['image_id']}",
                "split": selected_split,
                "description": {
                    "text": (
                        f"A photograph labelled as a {breed} {species} in the "
                        "Oxford-IIIT Pet dataset. Detailed visual description pending review."
                    ),
                    "status": "source_label_only",
                    "author": DATASET_NAME,
                    "model_id": None,
                    "model_revision": None,
                },
                "search_terms": [species, breed, f"{breed} {species}", "pet", "photograph"],
                "facts": [
                    {
                        "text": f"the source dataset labels this image as a {species}",
                        "status": "source_label",
                        "confidence": 1.0,
                        "evidence": f"label_cat_dog={row['label_cat_dog']}",
                    },
                    {
                        "text": f"the source dataset labels the breed as {breed}",
                        "status": "source_label",
                        "confidence": 1.0,
                        "evidence": f"image_id={row['image_id']}",
                    },
                ],
                "claims": [
                    {"text": f"a {species}", "status": "candidate", "verified_by": [DATASET_NAME]},
                    {"text": f"a {breed} {species}", "status": "candidate", "verified_by": [DATASET_NAME]},
                ],
                "source": {
                    "kind": "dataset",
                    "dataset": DATASET_REVISION,
                    "item_id": row["image_id"],
                    "license": DATASET_LICENSE,
                    "attribution": DATASET_NAME,
                },
                "lineage": {
                    "parent_sha256": None,
                    "model_id": None,
                    "model_revision": None,
                    "prompt": None,
                    "seed": None,
                    "intended_delta": None,
                },
            },
            export_jsonl=False,
        )
        imported += 1
    return {"imported": imported, "cats": counts["cat"], "dogs": counts["dog"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--qualification-per-species", type=int, default=100)
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    if args.qualification_per_species < 0 or (args.limit is not None and args.limit <= 0):
        parser.error("counts must be non-negative and limit must be positive")
    catalog = AssetCatalog(args.catalog_root)
    results = {}
    for split in ("train", "test"):
        paths = sorted((args.source / "data").glob(f"{split}-*.parquet"))
        if not paths:
            parser.error(f"missing {split} parquet under {args.source / 'data'}")
        results[split] = import_parquet(
            catalog,
            paths[0],
            split=split,
            qualification_per_species=args.qualification_per_species,
            limit=args.limit,
        )
    catalog.export_jsonl()
    print(json.dumps({"catalog": str(args.catalog_root.resolve()), "splits": results}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
