#!/usr/bin/env python3
"""Train a frozen-core SigLIP2 projector on a bounded Oxford cat/dog probe."""

from __future__ import annotations

import argparse
import json
import random
import tempfile
import time
from pathlib import Path
from typing import Any

import torch
from PIL import Image

from cortex.siglip2 import Siglip2CortexProjector, file_sha256, save_visual_projector
from cortex.student import build_student
from training.pipeline.visual.catalog import AssetCatalog, utc_now


def species(record: dict[str, Any]) -> str:
    for claim in record["claims"]:
        if claim["text"] in {"a cat", "a dog"}:
            return claim["text"].split()[1]
    raise ValueError(f"missing species claim: {record['asset_sha256']}")


def select(
    catalog: AssetCatalog,
    split: str,
    per_species: int,
    *,
    selection_seed: int | None = None,
) -> list[dict[str, Any]]:
    groups = {"cat": [], "dog": []}
    for record in catalog.records():
        if record["split"] != split:
            continue
        label = species(record)
        groups[label].append(record)
    if selection_seed is not None:
        for offset, label in enumerate(("cat", "dog")):
            random.Random(selection_seed + offset).shuffle(groups[label])
    groups = {label: records[:per_species] for label, records in groups.items()}
    if any(len(group) != per_species for group in groups.values()):
        raise ValueError(f"not enough {split} cat/dog assets")
    return [record for label in ("cat", "dog") for record in groups[label]]


def load_image(root: Path, record: dict[str, Any]) -> Image.Image:
    with Image.open(root / record["object_path"]) as source:
        return source.convert("RGB")


@torch.no_grad()
def cache_features(
    projector: Siglip2CortexProjector,
    root: Path,
    records: list[dict[str, Any]],
) -> dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
    cache = {}
    for record in records:
        features = projector.receptor_features([load_image(root, record)])
        cache[record["asset_sha256"]] = tuple(value.cpu() for value in features)
    return cache


def batch_features(
    cache: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    records: list[dict[str, Any]],
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
    values = [cache[record["asset_sha256"]] for record in records]
    return tuple(torch.cat([item[index] for item in values], dim=0) for index in range(3))  # type: ignore[return-value]


@torch.no_grad()
def accuracy(
    projector: Siglip2CortexProjector,
    cache: dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]],
    records: list[dict[str, Any]],
    prototypes: dict[str, torch.Tensor],
) -> dict[str, Any]:
    correct = 0
    rows = []
    for record in records:
        features = cache[record["asset_sha256"]]
        visual = projector.visual_intentions_from_features(*features).float().flatten(1)
        similarities = {
            label: torch.nn.functional.cosine_similarity(
                visual, target.to(visual.device).float().flatten(1)
            ).item()
            for label, target in prototypes.items()
        }
        predicted = max(similarities, key=similarities.get)
        expected = species(record)
        correct += predicted == expected
        rows.append(
            {
                "asset_sha256": record["asset_sha256"],
                "expected": expected,
                "predicted": predicted,
                "similarities": {key: round(value, 6) for key, value in similarities.items()},
            }
        )
    return {"accuracy": round(correct / len(records), 6), "correct": correct, "total": len(records), "items": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--base-checkpoint", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, default=Path("tmp/vision/model_manifest.json"))
    parser.add_argument("--output-projector", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--train-per-species", type=int, default=5)
    parser.add_argument("--eval-per-species", type=int, default=10)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument(
        "--train-subset-seed",
        type=int,
        help="shuffle the train split reproducibly while keeping evaluation fixed",
    )
    args = parser.parse_args()
    if min(args.train_per_species, args.eval_per_species, args.epochs, args.batch_size) <= 0:
        parser.error("sample, epoch, and batch counts must be positive")
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    base_hash_before = file_sha256(args.base_checkpoint)
    manifest = json.loads(args.model_manifest.read_text(encoding="utf-8"))
    receptor = manifest["models"]["siglip2"]
    student, parent_kind, _ = build_student(
        args.base_checkpoint,
        frozen_dtype=torch.bfloat16,
        local_files_only=True,
    )
    projector = Siglip2CortexProjector(
        student,
        receptor["snapshot_path"],
        receptor_dtype=torch.float16,
    )
    partition = projector.place(
        receptor_device=torch.device("cuda:0"),
        core_device=torch.device("cuda:1"),
        dtype=torch.bfloat16,
    )
    catalog = AssetCatalog(args.catalog_root)
    train_records = select(
        catalog,
        "train",
        args.train_per_species,
        selection_seed=args.train_subset_seed,
    )
    eval_records = select(catalog, "test", args.eval_per_species)
    started = time.monotonic()
    feature_cache = cache_features(
        projector, args.catalog_root, train_records + eval_records
    )
    prototypes = {
        label: projector.text_targets([f"a {label}"]).cpu()
        for label in ("cat", "dog")
    }
    baseline = accuracy(projector, feature_cache, eval_records, prototypes)
    optimizer = torch.optim.AdamW(
        projector.trainable_parameters(), lr=args.lr, weight_decay=0.01
    )
    losses = []
    learning_curve = []
    milestones = {1, 2, 5, 10, args.epochs}
    projector.train()
    for epoch in range(args.epochs):
        shuffled = list(train_records)
        random.Random(args.seed + epoch).shuffle(shuffled)
        for offset in range(0, len(shuffled), args.batch_size):
            batch = shuffled[offset : offset + args.batch_size]
            patches, mask, shapes = batch_features(feature_cache, batch)
            visual = projector.visual_intentions_from_features(patches, mask, shapes)
            target = torch.cat([prototypes[species(record)] for record in batch], dim=0)
            loss = torch.nn.functional.mse_loss(
                visual.float(), target.to(visual.device).float()
            )
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(list(projector.trainable_parameters()), 1.0)
            optimizer.step()
            losses.append(float(loss.detach().cpu()))
        completed_epoch = epoch + 1
        if completed_epoch in milestones:
            measured = accuracy(projector, feature_cache, eval_records, prototypes)
            learning_curve.append(
                {
                    "epochs": completed_epoch,
                    "image_exposures": len(train_records) * completed_epoch,
                    "accuracy": measured["accuracy"],
                    "correct": measured["correct"],
                    "total": measured["total"],
                }
            )
    projector.eval()
    final = accuracy(projector, feature_cache, eval_records, prototypes)
    duration = time.monotonic() - started
    metadata = {
        "created_at": utc_now(),
        "experiment": "oxford_cat_dog_known_concept_probe",
        "unique_train_images": len(train_records),
        "train_per_species": args.train_per_species,
        "eval_per_species": args.eval_per_species,
        "epochs": args.epochs,
        "image_exposures": len(train_records) * args.epochs,
        "batch_size": args.batch_size,
        "lr": args.lr,
        "seed": args.seed,
        "train_subset_seed": args.train_subset_seed,
        "parent_kind": parent_kind,
        "loss_first": losses[0],
        "loss_last": losses[-1],
        "baseline_accuracy": baseline["accuracy"],
        "final_accuracy": final["accuracy"],
        "duration_seconds": round(duration, 3),
    }
    save_visual_projector(
        args.output_projector,
        projector,
        base_checkpoint=args.base_checkpoint,
        metadata=metadata,
    )
    base_hash_after = file_sha256(args.base_checkpoint)
    if base_hash_after != base_hash_before:
        raise RuntimeError("language-only baseline checkpoint changed during projector probe")
    report = {
        "schema_version": "ninereeds_siglip2_projector_probe_v1",
        "metadata": metadata,
        "base_checkpoint": str(args.base_checkpoint),
        "base_checkpoint_sha256": base_hash_after,
        "receptor_model_id": receptor["repo_id"],
        "receptor_revision": receptor["revision"],
        "partition": partition,
        "train_assets": [record["asset_sha256"] for record in train_records],
        "baseline": baseline,
        "final": final,
        "learning_curve": learning_curve,
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output_report.parent, delete=False) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output_report)
    print(json.dumps({"projector": str(args.output_projector), "report": str(args.output_report), **metadata}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
