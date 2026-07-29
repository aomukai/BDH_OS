from __future__ import annotations

import hashlib
import random
import re
from pathlib import Path
from typing import Callable

from training.pipeline.control.ledger import utc_now


FOUNDATION_BLOCK_SIZE = 500
FOUNDATION_CHUNK_SIZE = 50
REPLAY_EXAMPLES = 325
NEW_EXAMPLES = 125
SPECIAL_EXAMPLES = 50

_TURN = re.compile(
    r"\[user\]\s*(.*?)\s*\n\[Ninereeds\]\s*(.*?)(?=\n\s*\[user\]|\Z)",
    re.IGNORECASE | re.DOTALL,
)


def build_foundation_replay_script(
    repo_root: Path,
    *,
    campaign_id: str,
    block_index: int,
    parent_checkpoint: str,
    orchestrator_plan_id: str,
) -> dict:
    """Assemble one bounded foundation block from existing curated material.

    The compact in-memory script stays below the control transport's 256 KiB
    envelope while preserving the operator-directed 65/25/10 replay mix.
    """

    replay = _choose(
        _collect(repo_root / "training_data/kernel")
        + _collect(repo_root / "training_data/kernel_pilot20"),
        REPLAY_EXAMPLES,
        _seed(campaign_id, block_index, "replay"),
    )
    new = _choose(
        _collect(repo_root / "training_data/kernel_from_redesign"),
        NEW_EXAMPLES,
        _seed(campaign_id, block_index, "new"),
    )
    identity = _choose(
        _collect(repo_root / "training_data/kernel_identity"),
        SPECIAL_EXAMPLES // 2,
        _seed(campaign_id, block_index, "identity"),
    )
    multilingual_root = repo_root / "training_data/pre_c16"
    german = _choose(
        _collect(multilingual_root, lambda path: path.name.endswith("_DE.md")),
        12,
        _seed(campaign_id, block_index, "german"),
    )
    japanese = _choose(
        _collect(multilingual_root, lambda path: path.name.endswith("_JP.md")),
        13,
        _seed(campaign_id, block_index, "japanese"),
    )
    selected = (
        [(*value, "replay") for value in replay]
        + [(*value, "new") for value in new]
        + [(*value, "special") for value in identity]
        + [(*value, "special_de") for value in german]
        + [(*value, "special_ja") for value in japanese]
    )
    random.Random(_seed(campaign_id, block_index, "order")).shuffle(selected)

    items = []
    for index, (prompt, completion, bucket) in enumerate(selected, 1):
        items.append(
            {
                "item_id": f"foundation_{index:04d}",
                "stage": bucket,
                "user_prompt": prompt,
                "teacher_correction": None,
                "ask_after_correction": False,
                "expected_original": {
                    "acceptable": [completion],
                    "forbidden": [],
                },
                "expected_after_correction": {
                    "acceptable": [completion],
                    "forbidden": [],
                },
                "target_failure_modes": ["cross_prompt_generation_collapse"],
                "training_answer_max_bytes": 256,
            }
        )

    session_id = f"{campaign_id}-foundation-replay-{block_index:04d}"
    prompt_hash = hashlib.sha256(
        "\n".join(item["user_prompt"] for item in items).encode("utf-8")
    ).hexdigest()
    structural_hash = hashlib.sha256(
        "\n".join(item["stage"] for item in items).encode("utf-8")
    ).hexdigest()
    return {
        "schema_version": "msm_script_v1",
        "script_id": f"script-{session_id}",
        "session_id": session_id,
        "orchestrator_plan_id": orchestrator_plan_id,
        "script_author": "operator-directed-deterministic-corpus",
        "created_at": utc_now(),
        "concept": "broad_foundational_replay",
        "card_id": f"card-foundation-replay-{block_index:04d}",
        "checkpoint": parent_checkpoint,
        "session_mode": "protected_anchor_session",
        "intended_stage": "foundational_bootstrap",
        "intended_failure_targets": [
            "cross_prompt_generation_collapse",
            "expression_repetition_collapse",
            "catastrophic_interference",
        ],
        "executor_context": {
            "executor_id": "deterministic-corpus-assembler",
            "selection_method": "fixed",
            "meta_scratchpad_injected": False,
            "meta_scratchpad_path": None,
        },
        "script_fingerprint": {
            "algorithm": "msm_script_fingerprint_v1",
            "structural_hash": structural_hash,
            "prompt_hash": prompt_hash,
            "question_type_sequence": [],
            "contrast_pairs": [],
        },
        "trainer_contract": {
            "send_user_prompt": True,
            "record_original_answer": True,
            "send_teacher_correction": True,
            "record_after_correction_answer": True,
            "do_not_grade": True,
            "do_not_modify_items": True,
        },
        "items": items,
    }


def foundation_replay_chunks(script: dict) -> list[dict]:
    """Split a finalized foundation script into resumable transport chunks."""

    items = script.get("items")
    if not isinstance(items, list) or len(items) != FOUNDATION_BLOCK_SIZE:
        raise ValueError(
            f"foundation script must contain {FOUNDATION_BLOCK_SIZE} items"
        )
    examples = [
        {
            "prompt": str(item["user_prompt"]),
            "completion": str(item["expected_original"]["acceptable"][0]),
            "stage": str(item["stage"]),
        }
        for item in items
    ]
    curriculum_sha256 = hashlib.sha256(_canonical(examples)).hexdigest()
    chunks = []
    for offset in range(0, len(examples), FOUNDATION_CHUNK_SIZE):
        values = examples[offset : offset + FOUNDATION_CHUNK_SIZE]
        chunks.append(
            {
                "chunk_index": len(chunks) + 1,
                "chunk_count": (
                    FOUNDATION_BLOCK_SIZE + FOUNDATION_CHUNK_SIZE - 1
                )
                // FOUNDATION_CHUNK_SIZE,
                "examples": values,
                "chunk_sha256": hashlib.sha256(_canonical(values)).hexdigest(),
                "curriculum_sha256": curriculum_sha256,
            }
        )
    return chunks


def _collect(
    root: Path,
    predicate: Callable[[Path], bool] = lambda _path: True,
) -> list[tuple[str, str]]:
    values: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for path in sorted(root.rglob("*.md")):
        if not predicate(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for prompt, completion in _TURN.findall(text):
            prompt = " ".join(prompt.split())
            completion = " ".join(completion.split())
            key = (prompt.casefold(), completion.casefold())
            if (
                prompt
                and completion
                and len(prompt.encode("utf-8")) <= 512
                and len(completion.encode("utf-8")) <= 256
                and key not in seen
            ):
                seen.add(key)
                values.append((prompt, completion))
    return values


def _choose(
    values: list[tuple[str, str]],
    count: int,
    seed: int,
) -> list[tuple[str, str]]:
    shuffled = list(values)
    random.Random(seed).shuffle(shuffled)
    if len(shuffled) < count:
        raise ValueError(
            f"foundation corpus has only {len(shuffled)} eligible examples; "
            f"{count} are required"
        )
    return shuffled[:count]


def _seed(campaign_id: str, block_index: int, bucket: str) -> int:
    digest = hashlib.sha256(
        f"{campaign_id}:{block_index}:{bucket}".encode("utf-8")
    ).digest()
    return int.from_bytes(digest[:8], "big")


def _canonical(value: object) -> bytes:
    import json

    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
