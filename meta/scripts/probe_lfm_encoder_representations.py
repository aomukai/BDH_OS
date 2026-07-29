#!/usr/bin/env python3
"""Compare LFM2.5 Encoder layers on multilingual and semantic pairs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch
import torch.nn.functional as F
from transformers import AutoModelForMaskedLM, AutoTokenizer

MODEL_ID = "LiquidAI/LFM2.5-Encoder-230M"
MODEL_REVISION = "0b649ad0c684378b03d4d8304f7577a662ab89bc"

CASES = [
    {"id": "dog_en", "text": "A dog is an animal."},
    {"id": "dog_en_paraphrase", "text": "Dogs are animals."},
    {"id": "dog_de", "text": "Ein Hund ist ein Tier."},
    {"id": "dog_ja", "text": "犬は動物です。"},
    {"id": "dog_zh", "text": "狗是一种动物。"},
    {"id": "dog_negation", "text": "A dog is not an animal."},
    {"id": "bank_money", "text": "She deposited money at the bank."},
    {"id": "bank_river", "text": "She sat on the bank of the river."},
    {"id": "identity", "text": "My name is Ninereeds."},
    {"id": "quoted_claim", "text": "Andi said that the moon is made of cheese."},
]

PAIRS = [
    ("dog_en", "dog_en_paraphrase", "paraphrase"),
    ("dog_en", "dog_de", "translation_de"),
    ("dog_en", "dog_ja", "translation_ja"),
    ("dog_en", "dog_zh", "translation_zh"),
    ("dog_en", "dog_negation", "negation"),
    ("bank_money", "bank_river", "word_sense"),
]


def masked_mean(states: torch.Tensor, mask: torch.Tensor) -> torch.Tensor:
    weights = mask.unsqueeze(-1).to(states.dtype)
    return (states * weights).sum(dim=1) / weights.sum(dim=1).clamp_min(1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--revision", default=MODEL_REVISION)
    parser.add_argument("--layers", default="0,4,8,11,14")
    parser.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    layers = [int(value) for value in args.layers.split(",")]
    if any(layer < 0 or layer > 14 for layer in layers):
        parser.error("LFM2.5 Encoder layers must be between 0 and 14")

    device = torch.device(args.device)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_id,
        revision=args.revision,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    masked_lm = AutoModelForMaskedLM.from_pretrained(
        args.model_id,
        revision=args.revision,
        trust_remote_code=True,
        local_files_only=args.local_files_only,
    )
    model = masked_lm.lfm2.to(device).eval()
    encoded = tokenizer(
        [case["text"] for case in CASES],
        padding=True,
        truncation=True,
        max_length=128,
        return_tensors="pt",
    ).to(device)
    with torch.no_grad():
        outputs = model(**encoded, output_hidden_states=True, return_dict=True)

    indices = {case["id"]: index for index, case in enumerate(CASES)}
    results = []
    for layer in layers:
        pooled = masked_mean(outputs.hidden_states[layer], encoded["attention_mask"])
        for left, right, kind in PAIRS:
            similarity = F.cosine_similarity(
                pooled[indices[left]].unsqueeze(0),
                pooled[indices[right]].unsqueeze(0),
            ).item()
            results.append(
                {
                    "layer": layer,
                    "left": left,
                    "right": right,
                    "pair_type": kind,
                    "cosine_similarity": similarity,
                }
            )

    report = {
        "schema_version": "lfm2_5_encoder_representation_probe_v1",
        "model_id": args.model_id,
        "revision": args.revision,
        "device": str(device),
        "layers": layers,
        "cases": CASES,
        "results": results,
        "note": "Cosine similarity is diagnostic evidence, not proof of shared concepts.",
    }
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
