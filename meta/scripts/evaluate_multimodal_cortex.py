#!/usr/bin/env python3
"""Probe cross-modal access in one Cortex checkpoint without changing it."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch.nn import functional as F

from cortex.siglip2 import BoundedVisualResampler, Siglip2ProjectorConfig
from cortex.student import build_student, load_visual_state


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def load_features(path: Path) -> dict[str, tuple[torch.Tensor, torch.Tensor, torch.Tensor]]:
    result = {}
    with np.load(path, allow_pickle=False) as values:
        for index, digest in enumerate(str(item) for item in values["asset_sha256"].tolist()):
            result[digest] = (
                torch.from_numpy(values[f"patch_{index:04d}"]),
                torch.from_numpy(values[f"mask_{index:04d}"]),
                torch.from_numpy(values[f"shape_{index:04d}"]),
            )
    return result


def tokens(value: str) -> set[str]:
    return {token.strip(".,!?;:'\"()[]{}").casefold() for token in value.split() if token.strip(".,!?;:'\"()[]{}")}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--experience", type=Path, required=True)
    parser.add_argument("--branch-id", required=True)
    parser.add_argument("--campaign-id", required=True)
    parser.add_argument("--checkpoint-sha256", required=True)
    parser.add_argument("--features-sha256", required=True)
    parser.add_argument("--experience-sha256", required=True)
    parser.add_argument("--ingress-device", default="cuda:0")
    parser.add_argument("--core-device", default="cuda:1")
    parser.add_argument("--max-new-tokens", type=int, default=24)
    parser.add_argument("--scan-mode", choices=("crossmodal", "visual_structure"), default="crossmodal")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if sha256(args.checkpoint) != args.checkpoint_sha256 or sha256(args.features) != args.features_sha256 or sha256(args.experience) != args.experience_sha256:
        raise ValueError("cross-modal evaluation input bytes changed after authorization")

    experience = json.loads(args.experience.read_text(encoding="utf-8"))
    events = experience.get("manifest", {}).get("events", experience.get("events", []))
    captions = {(item["ordinal"], item["example_index"]): item["text"] for item in events if item.get("type") == "hear_or_read_text"}
    selected = []
    seen = set()
    for item in events:
        if item.get("type") != "observe_image":
            continue
        if args.scan_mode == "crossmodal" and item.get("concept") in seen:
            continue
        key = (item["ordinal"], item["example_index"])
        if key in captions:
            selected.append({"concept": item["concept"], "asset_sha256": item["asset_sha256"], "caption": captions[key]})
            if args.scan_mode == "crossmodal":
                seen.add(item["concept"])
    if len(selected) < 2:
        raise ValueError("cross-modal probe requires at least two distinct concepts")

    visual_state = load_visual_state(args.checkpoint)
    report = {
        "schema_version": "ninereeds_crossmodal_evaluation_v1",
        "campaign_id": args.campaign_id,
        "branch_id": args.branch_id,
        "checkpoint_sha256": args.checkpoint_sha256,
        "features_sha256": args.features_sha256,
        "experience_sha256": args.experience_sha256,
        "observer_effect": "none_read_only",
        "loss_role": "telemetry_only",
        "probe_count": len(selected),
        "visual_adapter_present": visual_state is not None,
        "scan_mode": args.scan_mode,
    }
    if visual_state is None:
        report.update({"status": "visual_path_absent", "image_to_text": [], "retrieval": {"top1_correct": 0, "total": len(selected), "accuracy": 0.0}})
    else:
        features = load_features(args.features)
        student, _, _ = build_student(args.checkpoint, frozen_dtype=torch.bfloat16, local_files_only=True)
        student.place(ingress_device=torch.device(args.ingress_device), core_device=torch.device(args.core_device), trainable_dtype=torch.bfloat16)
        config = Siglip2ProjectorConfig(**visual_state["config"])
        resampler = BoundedVisualResampler(config)
        resampler.load_state_dict(visual_state["resampler_state"], strict=True)
        resampler.to(device=torch.device(args.ingress_device), dtype=torch.bfloat16).eval()
        student.eval()
        visual_vectors = []
        outputs = []
        with torch.no_grad():
            for item in selected:
                patch, mask, shape = features[item["asset_sha256"]]
                parameter = next(resampler.parameters())
                observed, observed_mask = resampler(patch.unsqueeze(0).to(parameter.device, parameter.dtype), mask.unsqueeze(0).to(parameter.device), shape.unsqueeze(0).to(parameter.device))
                hidden = student.core.encode_embeds(observed)
                intentions = student.intention(hidden, observed_mask.to(hidden.device))
                if args.scan_mode == "crossmodal":
                    generated = student.expression.generate(intentions, max_new_tokens=args.max_new_tokens, do_sample=False)
                    response = student.expression.tokenizer.batch_decode(generated, skip_special_tokens=True)[0]
                    expected = tokens(item["caption"])
                    overlap = len(expected & tokens(response)) / max(len(expected), 1)
                    outputs.append({**item, "response": response, "caption_token_recall": round(overlap, 6)})
                visual_vectors.append(intentions.mean(dim=1).to(torch.float32).cpu())
            text_vectors = None
            if args.scan_mode == "crossmodal":
                # A merged Cortex can be substantially wider than either
                # specialist.  Encoding every caption in one batch made the
                # read-only probe scale VRAM with the size of the evaluation
                # shard (21 GiB for 168 captions on Campaign 35 M4).  Keep the
                # exact order and bytes while bounding observer memory.
                text_batches = []
                captions_in_order = [item["caption"] for item in selected]
                for start in range(0, len(captions_in_order), 8):
                    text_batches.append(
                        student.intentions(captions_in_order[start:start + 8])
                        .mean(dim=1).to(torch.float32).cpu()
                    )
                text_vectors = torch.cat(text_batches, dim=0)
        visual_matrix = F.normalize(torch.cat(visual_vectors, dim=0), dim=1)
        if args.scan_mode == "visual_structure":
            similarity = visual_matrix @ visual_matrix.T
            within, between = [], []
            for left in range(len(selected)):
                for right in range(left + 1, len(selected)):
                    target = within if selected[left]["concept"] == selected[right]["concept"] else between
                    target.append(float(similarity[left, right]))
            within_mean = sum(within) / len(within) if within else 0.0
            between_mean = sum(between) / len(between) if between else 0.0
            report.update({
                "status": "visual_structure_scanned",
                "image_to_text": [],
                "retrieval": {"top1_correct": 0, "total": 0, "accuracy": 0.0},
                "visual_structure": {
                    "image_count": len(selected),
                    "concept_count": len({item["concept"] for item in selected}),
                    "within_concept_cosine": round(within_mean, 6),
                    "between_concept_cosine": round(between_mean, 6),
                    "concept_separation": round(within_mean - between_mean, 6),
                },
            })
            args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
            return 0
        assert text_vectors is not None
        text_matrix = F.normalize(text_vectors, dim=1)
        similarity = visual_matrix @ text_matrix.T
        predictions = similarity.argmax(dim=1)
        correct = sum(int(predictions[index]) == index for index in range(len(selected)))
        report.update({
            "status": "evaluated",
            "image_to_text": outputs,
            "image_to_text_mean_caption_token_recall": round(sum(item["caption_token_recall"] for item in outputs) / len(outputs), 6),
            "retrieval": {
                "method": "visual_intention_to_text_intention_cosine",
                "top1_correct": correct,
                "total": len(selected),
                "accuracy": round(correct / len(selected), 6),
                "matched_mean_cosine": round(float(similarity.diag().mean()), 6),
                "all_pairs_mean_cosine": round(float(similarity.mean()), 6),
            },
        })
    args.output.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
