from __future__ import annotations

import hashlib
import json
import random
import re
from pathlib import Path
from typing import Any

from training.pipeline.cortex.foundation_corpus import _collect


SCHEMA = "ninereeds_allowlist_wave_v1"
BLOCK_SIZE = 500
NEW_PER_BLOCK = 125
REPLAY_PER_BLOCK = 325
SPECIAL_PER_BLOCK = 50
_SLUG = re.compile(r"[^a-z0-9]+")


def prepare_allowlist_wave(
    repo_root: Path,
    *,
    wave_id: str = "allowlist-0501-2000-v1",
    first_rank: int = 501,
    last_rank: int = 2000,
) -> dict[str, Any]:
    """Build deterministic, guarded foundation-style blocks from existing data."""

    rows = [
        json.loads(line)
        for line in (repo_root / "training/corpus_admin/kernel/kernel_full_words.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
        if line.strip()
    ]
    targets = rows[first_rank - 1 : last_rank]
    if len(targets) != last_rank - first_rank + 1:
        raise ValueError("requested allowlist rank interval is incomplete")
    if len(targets) % NEW_PER_BLOCK:
        raise ValueError("target count must divide into 125-concept blocks")

    replay_pool = _collect(repo_root / "training_data/kernel") + _collect(
        repo_root / "training_data/kernel_pilot20"
    )
    identity_pool = _collect(repo_root / "training_data/kernel_identity")
    language_root = repo_root / "training_data"
    german_pool = _collect(
        language_root, lambda path: path.name.casefold().endswith("_de.md")
    )
    japanese_pool = _collect(
        language_root, lambda path: path.name.casefold().endswith("_jp.md")
    )
    for label, pool, minimum in (
        ("replay", replay_pool, REPLAY_PER_BLOCK),
        ("identity", identity_pool, 25),
        ("German", german_pool, 12),
        ("Japanese", japanese_pool, 13),
    ):
        if len(pool) < minimum:
            raise ValueError(f"{label} pool has {len(pool)} examples; {minimum} required")

    output_root = repo_root / "training/pipeline/cortex/allowlist_waves" / wave_id
    output_root.mkdir(parents=True, exist_ok=True)
    blocks = []
    for block_offset in range(0, len(targets), NEW_PER_BLOCK):
        block_index = block_offset // NEW_PER_BLOCK + 1
        block_targets = targets[block_offset : block_offset + NEW_PER_BLOCK]
        new_examples = []
        heldout_cases = []
        concepts = []
        for relative_index, row in enumerate(block_targets):
            rank = first_rank + block_offset + relative_index
            train, heldout, sources = _concept_pair(repo_root, row)
            concepts.append(
                {
                    "rank": rank,
                    "concept_id": row["concept_id"],
                    "category": row["category"],
                    "train_source": sources[0],
                    "heldout_source": sources[1],
                }
            )
            new_examples.append(
                {"prompt": train[0], "completion": train[1], "stage": "new_allowlist"}
            )
            if relative_index % 5 == 0:
                heldout_cases.append(
                    _heldout_case(block_index, rank, row["concept_id"], heldout)
                )

        rng = random.Random(_seed(wave_id, block_index, "mix"))
        examples = (
            new_examples
            + _sample(replay_pool, REPLAY_PER_BLOCK, _seed(wave_id, block_index, "replay"), "replay")
            + _sample(identity_pool, 25, _seed(wave_id, block_index, "identity"), "identity")
            + _sample(german_pool, 12, _seed(wave_id, block_index, "de"), "special_de")
            + _sample(japanese_pool, 13, _seed(wave_id, block_index, "jp"), "special_ja")
        )
        rng.shuffle(examples)
        block_path = output_root / f"block-{block_index:02d}.jsonl"
        block_path.write_text(
            "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in examples),
            encoding="utf-8",
        )
        suite = _evaluation_suite(repo_root, wave_id, block_index, heldout_cases)
        suite_path = output_root / f"eval-block-{block_index:02d}.json"
        suite_path.write_text(
            json.dumps(suite, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        blocks.append(
            {
                "block_index": block_index,
                "rank_first": concepts[0]["rank"],
                "rank_last": concepts[-1]["rank"],
                "concept_count": len(concepts),
                "examples": len(examples),
                "training_path": block_path.relative_to(repo_root).as_posix(),
                "training_sha256": _sha256(block_path),
                "evaluation_path": suite_path.relative_to(repo_root).as_posix(),
                "evaluation_sha256": _sha256(suite_path),
                "concepts": concepts,
            }
        )

    manifest = {
        "schema_version": SCHEMA,
        "wave_id": wave_id,
        "allowlist_source": "training/corpus_admin/kernel/kernel_full_words.jsonl",
        "first_rank": first_rank,
        "last_rank": last_rank,
        "concept_count": len(targets),
        "block_count": len(blocks),
        "mix_per_block": {"new": 125, "replay": 325, "identity_multilingual": 50},
        "blocks": blocks,
    }
    manifest_path = output_root / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return {**manifest, "manifest_path": manifest_path.relative_to(repo_root).as_posix()}


def _concept_pair(repo_root: Path, row: dict[str, Any]):
    slug = _SLUG.sub("_", row["concept_id"].casefold()).strip("_")
    roots = (
        repo_root / "training_data/kernel_from_redesign" / row["category"] / slug,
        repo_root / "training_data/kernel_gap_fill" / row["category"] / slug,
    )
    candidates = []
    for root in roots:
        paths = sorted(root.glob("what_is*.md")) + sorted(root.glob("classification*.md"))
        for path in paths:
            turns = _collect(path.parent, lambda candidate, wanted=path: candidate == wanted)
            if turns:
                candidates.append((turns[0], path.relative_to(repo_root).as_posix()))
    unique = []
    seen = set()
    for value, source in candidates:
        key = (value[0].casefold(), value[1].casefold())
        if key not in seen:
            seen.add(key)
            unique.append((value, source))
    if len(unique) < 2:
        raise ValueError(f"concept {row['concept_id']!r} lacks two clean examples")
    return unique[0][0], unique[1][0], (unique[0][1], unique[1][1])


def _sample(pool, count: int, seed: int, stage: str):
    values = list(pool)
    random.Random(seed).shuffle(values)
    return [
        {"prompt": prompt, "completion": completion, "stage": stage}
        for prompt, completion in values[:count]
    ]


def _heldout_case(block: int, rank: int, concept: str, pair):
    completion = pair[1]
    tokens = [token for token in re.findall(r"[A-Za-z0-9'-]+", concept) if len(token) > 1]
    return {
        "case_id": f"wave-{block:02d}-rank-{rank:04d}",
        "group": "capability",
        "concept": concept,
        "language": "en",
        "prompt": pair[0],
        "expected_response": completion,
        "required_any": tokens or [concept],
        "forbidden": [],
    }


def _evaluation_suite(repo_root: Path, wave_id: str, block: int, heldout: list[dict]):
    base = json.loads(
        (repo_root / "training/pipeline/cortex/eval_suite_v1.json").read_text(encoding="utf-8")
    )
    return {
        "schema_version": "ninereeds_cortex_eval_suite_v1",
        "suite_id": f"{wave_id}-block-{block:02d}",
        "description": "Held-out rephrasings for one allowlist wave block plus protected anchors.",
        "cases": heldout + base["cases"],
    }


def _seed(wave_id: str, block: int, bucket: str) -> int:
    return int.from_bytes(
        hashlib.sha256(f"{wave_id}:{block}:{bucket}".encode()).digest()[:8], "big"
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
