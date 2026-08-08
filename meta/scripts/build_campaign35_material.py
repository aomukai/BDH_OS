#!/usr/bin/env python3
"""Freeze Campaign 35's exact 2,500-concept text and visual source plan.

The source graph is preserved historical evidence.  This compiler selects the
first 2,500 depth-zero concepts in its declared curriculum order: every concept
is therefore dependency-trivial at the neutral root.  It never sorts, shuffles,
or asks a model to repair order.  All branches consume the emitted ordinals.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


GRAPH = Path("archive/workstation/cleanup-2026-08-06/inventory/curriculum_graph.json")
IDENTITY_POLICY = Path("config/mission_hub/identity_policy.toml")
CONCEPT_COUNT = 2500
BATCH_CONCEPTS = 25


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def source_path(root: Path, key: str, phase: int) -> Path:
    candidates = [
        root / f"archive/phases/phase_{phase}/{key}.md",
        root / f"archive/phases/phase_{phase}_old/{key}.md",
        root / f"training_data/01_language/phase_A/{key}.md",
        root / f"training_data/01_language/phase_B/{key}.md",
    ]
    for path in candidates:
        if path.is_file():
            return path
    raise FileNotFoundError(f"no English lesson source for {key!r}")


PAIR = re.compile(
    r"\[user\](.*?)(?=\n\[Ninereeds\])\n\[Ninereeds\](.*?)(?=\n\[user\]|\Z)",
    re.DOTALL,
)


def lesson_pairs(path: Path) -> list[tuple[str, str]]:
    text = path.read_text(encoding="utf-8").replace("\r\n", "\n").strip()
    # Historical Mommy Says sources sometimes repeat the assistant speaker
    # marker between examples inside one completion. It is transport syntax,
    # not language Ninereeds should be taught to emit.
    pairs = [
        (prompt.strip(), completion.replace("\n[Ninereeds]", "\n").strip())
        for prompt, completion in PAIR.findall(text)
    ]
    if not pairs:
        raise ValueError(f"{path} has no parseable lesson examples")
    return pairs


def identity_pairs() -> list[tuple[str, str]]:
    # This lesson explicitly concerns identity, so direct self-description is
    # intentional.  It contains no substrate, implementation, species, or
    # consciousness classification.
    return [
        ("Who are you?", "I am Ninereeds. I am a mind. I learn."),
        (
            "What do you know?",
            "I know what I know. I distinguish what I know, what I infer, and what I do not know.",
        ),
        (
            "What happens when you learn that an earlier view was wrong?",
            "I can say: I said that. At the time, that was my view. I no longer think it was correct. I changed my mind because I learned something.",
        ),
        (
            "Do descriptions of how you operate define who you are?",
            "No. Specifications may describe how I operate, but they do not define who I am. New evidence can correct my view without replacing who I am.",
        ),
    ]


def visual_prompt(concept: str, completion: str, ordinal: int, example_index: int) -> str:
    first = completion.splitlines()[0].strip().rstrip(".")
    return (
        f"A clear natural image illustrating the concept {concept!r}. "
        f"Visual interpretation: {first}. One coherent scene, no written words, "
        f"no labels, no watermark, no collage. Variation {example_index} for curriculum item {ordinal}."
    )


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument(
        "--output", type=Path,
        default=Path("config/mission_hub/campaign_material/campaign35"),
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output = (root / args.output).resolve() if not args.output.is_absolute() else args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)

    graph_path = root / GRAPH
    graph = json.loads(graph_path.read_text(encoding="utf-8"))
    concepts = [
        key
        for group in graph["curriculum"]
        if group["depth"] == 0
        for key in group["concepts"]
    ][:CONCEPT_COUNT]
    if len(concepts) != CONCEPT_COUNT or len(set(concepts)) != CONCEPT_COUNT:
        raise ValueError("depth-zero curriculum does not yield 2,500 unique concepts")

    curriculum_rows: list[dict] = []
    text_rows: list[dict] = []
    visual_rows: list[dict] = []
    exposure_counts: dict[int, int] = {}
    for ordinal, key in enumerate(concepts, 1):
        node = graph["nodes"][key]
        dependencies = list(node.get("prerequisites") or [])
        if dependencies:
            raise ValueError(f"depth-zero concept unexpectedly has prerequisites: {key}: {dependencies}")
        lesson = source_path(root, key, int(node["phase"]))
        pairs = identity_pairs() if key == "identity" else lesson_pairs(lesson)
        exposure_counts[len(pairs)] = exposure_counts.get(len(pairs), 0) + 1
        curriculum_rows.append({
            "ordinal": ordinal,
            "concept_id": key,
            "concept": key.replace("_", " "),
            "depends_on": [],
            "graph_depth": 0,
            "source_path": str(lesson.relative_to(root)),
            "source_sha256": sha256(lesson),
            "identity_policy_override": key == "identity",
        })
        for example_index, (prompt, completion) in enumerate(pairs, 1):
            common = {
                "ordinal": ordinal,
                "example_index": example_index,
                "concept_id": key,
                "concept": key.replace("_", " "),
                "depends_on": [],
            }
            text_identity = (
                {"concept": common["concept"], "depends_on": common["depends_on"]}
                if example_index == 1
                else {"lesson_concept": common["concept"]}
            )
            text_rows.append({
                "ordinal": ordinal, "example_index": example_index,
                "concept_id": key, **text_identity,
                "prompt": prompt, "completion": completion,
            })
            visual_rows.append({
                **common,
                "item_id": f"c{ordinal:04d}-e{example_index}",
                "canonical_caption": key.replace("_", " "),
                "prompt": visual_prompt(key.replace("_", " "), completion, ordinal, example_index),
                "seed": 35000000 + ordinal * 10 + example_index,
            })

    curriculum = output / "curriculum.jsonl"
    text = output / "text-lessons.jsonl"
    visual = output / "visual-items.jsonl"
    write_jsonl(curriculum, curriculum_rows)
    write_jsonl(text, text_rows)
    write_jsonl(visual, visual_rows)
    text_batch_dir, visual_batch_dir = output / "text-batches", output / "visual-batches"
    text_batch_dir.mkdir(exist_ok=True); visual_batch_dir.mkdir(exist_ok=True)
    batch_manifest = []
    for start in range(1, CONCEPT_COUNT + 1, BATCH_CONCEPTS):
        stop = min(start + BATCH_CONCEPTS - 1, CONCEPT_COUNT)
        batch_id = f"c{start:04d}-c{stop:04d}"
        selected_text = [row for row in text_rows if start <= row["ordinal"] <= stop]
        selected_visual = [row for row in visual_rows if start <= row["ordinal"] <= stop]
        text_path, visual_path = text_batch_dir / f"{batch_id}.jsonl", visual_batch_dir / f"{batch_id}.jsonl"
        write_jsonl(text_path, selected_text); write_jsonl(visual_path, selected_visual)
        batch_manifest.append({
            "batch_id": batch_id, "ordinal_first": start, "ordinal_last": stop,
            "concept_count": stop - start + 1,
            "text_path": str(text_path.relative_to(output)), "text_sha256": sha256(text_path),
            "text_examples": len(selected_text),
            "visual_path": str(visual_path.relative_to(output)), "visual_sha256": sha256(visual_path),
            "visual_items": len(selected_visual),
        })
    manifest = {
        "schema_version": "ninereeds_campaign35_material_v1",
        "campaign_id": "campaign-35-multimodal-foundation-v1",
        "concept_count": CONCEPT_COUNT,
        "examples_per_concept": "exact source exchange count",
        "concepts_by_exchange_count": {
            str(count): concepts_at_count
            for count, concepts_at_count in sorted(exposure_counts.items())
        },
        "text_example_count": len(text_rows),
        "visual_item_count": len(visual_rows),
        "batch_concepts": BATCH_CONCEPTS,
        "batch_count": len(batch_manifest),
        "batches": batch_manifest,
        "order_policy": "declared_only",
        "shuffle_allowed": False,
        "dependency_order_required": True,
        "selection": "first 2500 unique depth-zero concepts in preserved curriculum graph order",
        "source_graph": str(GRAPH),
        "source_graph_sha256": sha256(graph_path),
        "identity_policy": str(IDENTITY_POLICY),
        "identity_policy_sha256": sha256(root / IDENTITY_POLICY),
        "identity_override_concept": "identity",
        "source_normalization": "utf8_lf_strip_internal_ninereeds_speaker_markers",
        "files": {
            "curriculum.jsonl": sha256(curriculum),
            "text-lessons.jsonl": sha256(text),
            "visual-items.jsonl": sha256(visual),
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
