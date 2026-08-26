"""Generate, review, and append an immutable Campaign 36 asset replacement."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from types import SimpleNamespace

from image_registry.campaign36_flux_streaming_luna import append_jsonl, review_one
from image_registry.campaign36_headless_imagegen import DEFAULT_CODEX, DEFAULT_REPO, generate_one
from image_registry.campaign36_imagegen_fallback import DEFAULT_ROOT, normalize_image, sha256


SCHEMA_VERSION = "ninereeds_campaign36_asset_replacement_v1"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--replacement-id", required=True)
    parser.add_argument("--replaces-assignment", required=True)
    parser.add_argument("--slots-json", required=True)
    parser.add_argument("--concepts-json", required=True)
    parser.add_argument("--words-json", required=True)
    parser.add_argument("--evidence-json", required=True)
    parser.add_argument("--prompt-file", type=Path, required=True)
    parser.add_argument("--codex", type=Path, default=DEFAULT_CODEX)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--generation-timeout", type=int, default=900)
    parser.add_argument("--review-timeout", type=int, default=600)
    args = parser.parse_args()

    slots = json.loads(args.slots_json)
    concepts = json.loads(args.concepts_json)
    words = json.loads(args.words_json)
    evidence = json.loads(args.evidence_json)
    if not slots or len(concepts) != len(words) or set(concepts) != set(evidence):
        raise SystemExit("replacement slots/concepts/words/evidence are inconsistent")
    prompt = args.prompt_file.read_text(encoding="utf-8")
    job = {
        "job_id": args.replacement_id,
        "assignment_id": args.replacement_id,
        "provider_attempt": 1,
        "flux_attempt_id": "asset-replacement",
        "concept_ids": concepts,
        "words": words,
        "prompt": prompt,
        "brainstorm_after_attempt": None,
        "brainstorm_idea": None,
        "representation_override": None,
        "status": "reserved",
    }
    generated = generate_one(
        job, root=args.root, repo=args.repo, codex=args.codex,
        model=args.model, timeout=args.generation_timeout,
    )
    if generated["status"] != "generated":
        print(json.dumps(generated, ensure_ascii=False, indent=2))
        return 1

    target = args.root / "imagegen-v1/images" / f"{args.replacement_id}.png"
    normalize_image(Path(generated["image"]), target)
    review_row = {
        "schema_version": SCHEMA_VERSION,
        "assignment_id": args.replacement_id,
        "production_brief_id": args.replacement_id,
        "variant_index": 0,
        "generation_attempt": 1,
        "concept_ids": concepts,
        "words": words,
        "evidence_by_concept": evidence,
        "grounding_mode": "direct",
        "visible_text_policy": "reject",
        "prompt": prompt,
        "local_path": str(target),
        "sha256": sha256(target),
        "width": 512,
        "height": 384,
        "provider": "codex-built-in-imagegen",
    }
    verdict = review_one(
        review_row, target,
        SimpleNamespace(codex=args.codex, model=args.model, timeout=args.review_timeout),
    )
    record = {
        **review_row,
        "schema_version": SCHEMA_VERSION,
        "replaces_assignment": args.replaces_assignment,
        "replaces_slots": slots,
        "verdict": verdict["verdict"],
        "review": verdict,
    }
    append_jsonl(args.root / "imagegen-v1/asset-replacements.jsonl", record)
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0 if verdict["verdict"] == "accepted" else 2


if __name__ == "__main__":
    raise SystemExit(main())
