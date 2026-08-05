#!/usr/bin/env python3
"""Train the frozen-core SigLIP2 sidecar on an accepted foundation visual pack."""

from __future__ import annotations

import argparse
import fcntl
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
from training.pipeline.visual.catalog import utc_now
from training.pipeline.visual.catalog import AssetCatalog


def load_image(root: Path, row: dict[str, Any]) -> Image.Image:
    with Image.open(root / row["object_path"]) as source:
        return source.convert("RGB")


@torch.no_grad()
def cache_features(projector, root, rows):
    return {row["asset_sha256"]: tuple(value.cpu() for value in projector.receptor_features([load_image(root, row)])) for row in rows}


def batch_features(cache, rows):
    values = [cache[row["asset_sha256"]] for row in rows]
    return tuple(torch.cat([item[index] for item in values], dim=0) for index in range(3))


@torch.no_grad()
def evaluate(projector, cache, rows, prototypes):
    correct = 0
    results = []
    for row in rows:
        visual = projector.visual_intentions_from_features(*cache[row["asset_sha256"]]).float().flatten(1)
        similarities = {
            concept: torch.nn.functional.cosine_similarity(visual, target.to(visual.device).float().flatten(1)).item()
            for concept, target in prototypes.items()
        }
        predicted = max(similarities, key=similarities.get)
        correct += predicted == row["concept_id"]
        results.append({"asset_sha256": row["asset_sha256"], "expected": row["concept_id"], "predicted": predicted})
    return {"accuracy": round(correct / len(rows), 6), "correct": correct, "total": len(rows), "items": results}


def independent_pet_rows(catalog: AssetCatalog, per_species: int) -> list[dict[str, Any]]:
    groups = {"cat": [], "dog": []}
    for record in catalog.records():
        if record["split"] != "test" or record["source"]["kind"] != "dataset":
            continue
        for claim in record["claims"]:
            if claim.get("text") in {"a cat", "a dog"}:
                concept = claim["text"].split()[1]
                if len(groups[concept]) < per_species:
                    groups[concept].append({
                        **record, "concept_id": concept, "canonical_caption": claim["text"],
                    })
                break
    if any(len(rows) != per_species for rows in groups.values()):
        raise ValueError("independent Oxford test slice is incomplete")
    return groups["cat"] + groups["dog"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pack", type=Path, required=True)
    parser.add_argument("--catalog-root", type=Path, required=True)
    parser.add_argument("--base-checkpoint", type=Path, required=True)
    parser.add_argument("--model-manifest", type=Path, default=Path("tmp/vision/model_manifest.json"))
    parser.add_argument("--output-projector", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--lr", type=float, default=0.001)
    parser.add_argument("--seed", type=int, default=240801)
    parser.add_argument("--independent-pet-eval-per-species", type=int, default=10)
    parser.add_argument("--lock-file", type=Path, default=Path("/home/aomukai/.local/state/ninereeds-control/worker/trainbox-worker.lock"))
    args = parser.parse_args()
    args.lock_file.parent.mkdir(parents=True, exist_ok=True)
    worker_lock = args.lock_file.open("a+")
    try:
        fcntl.flock(worker_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        worker_lock.close()
        raise RuntimeError("trainbox worker lock is already held") from exc
    random.seed(args.seed); torch.manual_seed(args.seed)
    pack = json.loads(args.pack.read_text(encoding="utf-8"))
    if pack.get("status") != "accepted" or not pack.get("assets"):
        raise ValueError("projector training requires a complete accepted visual pack")
    train_rows = [row for row in pack["assets"] if row["training_role"] == "train"]
    eval_rows = [row for row in pack["assets"] if row["training_role"] == "validation"]
    concepts = sorted({row["concept_id"] for row in pack["assets"]})
    if {row["concept_id"] for row in train_rows} != set(concepts) or {row["concept_id"] for row in eval_rows} != set(concepts):
        raise ValueError("every concept needs train and validation assets")
    receptor = json.loads(args.model_manifest.read_text(encoding="utf-8"))["models"]["siglip2"]
    base_hash_before = file_sha256(args.base_checkpoint)
    student, parent_kind, _ = build_student(args.base_checkpoint, frozen_dtype=torch.bfloat16, local_files_only=True)
    projector = Siglip2CortexProjector(student, receptor["snapshot_path"], receptor_dtype=torch.float16)
    partition = projector.place(receptor_device=torch.device("cuda:0"), core_device=torch.device("cuda:1"), dtype=torch.bfloat16)
    catalog = AssetCatalog(args.catalog_root)
    independent_rows = independent_pet_rows(catalog, args.independent_pet_eval_per_species)
    started = time.monotonic()
    feature_cache = cache_features(projector, args.catalog_root, train_rows + eval_rows + independent_rows)
    prototypes = {concept: projector.text_targets([next(row["canonical_caption"] for row in pack["assets"] if row["concept_id"] == concept)]).cpu() for concept in concepts}
    baseline = evaluate(projector, feature_cache, eval_rows, prototypes)
    independent_prototypes = {concept: prototypes[concept] for concept in ("cat", "dog")}
    independent_baseline = evaluate(projector, feature_cache, independent_rows, independent_prototypes)
    optimizer = torch.optim.AdamW(projector.trainable_parameters(), lr=args.lr, weight_decay=0.01)
    curve = []
    losses = []
    milestones = {1, 2, 5, 10, args.epochs}
    projector.train()
    for epoch in range(args.epochs):
        shuffled = list(train_rows); random.Random(args.seed + epoch).shuffle(shuffled)
        for offset in range(0, len(shuffled), args.batch_size):
            batch = shuffled[offset : offset + args.batch_size]
            visual = projector.visual_intentions_from_features(*batch_features(feature_cache, batch))
            target = torch.cat([prototypes[row["concept_id"]] for row in batch], dim=0)
            loss = torch.nn.functional.mse_loss(visual.float(), target.to(visual.device).float())
            optimizer.zero_grad(set_to_none=True); loss.backward()
            torch.nn.utils.clip_grad_norm_(list(projector.trainable_parameters()), 1.0)
            optimizer.step(); losses.append(float(loss.detach().cpu()))
        if epoch + 1 in milestones:
            measured = evaluate(projector, feature_cache, eval_rows, prototypes)
            curve.append({"epoch": epoch + 1, "image_exposures": len(train_rows) * (epoch + 1), **{k: measured[k] for k in ("accuracy", "correct", "total")}})
    projector.eval(); final = evaluate(projector, feature_cache, eval_rows, prototypes)
    independent_final = evaluate(projector, feature_cache, independent_rows, independent_prototypes)
    metadata = {
        "created_at": utc_now(), "experiment": "foundation_objects_v1_alignment",
        "pack_sha256": file_sha256(args.pack), "concept_count": len(concepts),
        "unique_train_images": len(train_rows), "unique_validation_images": len(eval_rows),
        "epochs": args.epochs, "image_exposures": len(train_rows) * args.epochs,
        "batch_size": args.batch_size, "lr": args.lr, "seed": args.seed,
        "parent_kind": parent_kind, "loss_first": losses[0], "loss_last": losses[-1],
        "baseline_accuracy": baseline["accuracy"], "final_accuracy": final["accuracy"],
        "independent_pet_baseline_accuracy": independent_baseline["accuracy"],
        "independent_pet_final_accuracy": independent_final["accuracy"],
        "duration_seconds": round(time.monotonic() - started, 3),
    }
    save_visual_projector(args.output_projector, projector, base_checkpoint=args.base_checkpoint, metadata=metadata)
    if file_sha256(args.base_checkpoint) != base_hash_before:
        raise RuntimeError("language-only foundation checkpoint changed")
    report = {
        "schema_version": "ninereeds_foundational_siglip2_projector_v1", "metadata": metadata,
        "base_checkpoint": str(args.base_checkpoint), "base_checkpoint_sha256": base_hash_before,
        "receptor_model_id": receptor["repo_id"], "receptor_revision": receptor["revision"],
        "partition": partition, "concepts": concepts, "baseline": baseline, "final": final,
        "independent_oxford_pet": {"baseline": independent_baseline, "final": independent_final},
        "learning_curve": curve,
    }
    args.output_report.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=args.output_report.parent, delete=False) as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2, sort_keys=True); handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(args.output_report)
    print(json.dumps({"projector": str(args.output_projector.resolve()), "report": str(args.output_report.resolve()), **metadata}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
