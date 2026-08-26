"""Direct-pixel preflight for Campaign 36's infinitive-label remediation queue.

The label migration's first damage estimate is caption/evidence based.  This tool
reviews only those flagged slots against the selected teaching sense using Codex
Luna and publishes the smaller, pixel-confirmed generation queue.  It is resumable
and does not mutate either manifest.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
from typing import Any, Iterable

from image_benchmark.luna_watermark_worker import structured_codex_review


SCHEMA_VERSION = "ninereeds_campaign36_infinitive_remediation_v1"
DEFAULT_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/infinitive-label-v1"
)
DEFAULT_MANIFEST = DEFAULT_ROOT / "accepted-assets.jsonl"
DEFAULT_CONTRACTS = DEFAULT_ROOT / "teaching-contracts.jsonl"
DEFAULT_REMEDIATION = DEFAULT_ROOT / "image-remediation-queue.jsonl"
DEFAULT_OUTPUT = DEFAULT_ROOT / "pixel-preflight-v1"


REVIEW_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["fit", "reject", "uncertain"]},
        "literal_caption": {"type": "string", "minLength": 1, "maxLength": 500},
        "target_evidence": {"type": "string", "minLength": 1, "maxLength": 500},
        "depicted_sense": {"type": "string", "minLength": 1, "maxLength": 500},
        "reason": {"type": "string", "minLength": 1, "maxLength": 600},
        "generation_correction": {"type": "string", "minLength": 1, "maxLength": 600},
        "visible_text": {"type": "boolean"},
        "watermark": {"type": "boolean"},
        "quality_flags": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "verdict", "literal_caption", "target_evidence", "depicted_sense", "reason",
        "generation_correction", "visible_text", "watermark", "quality_flags",
    ],
    "additionalProperties": False,
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def atomic_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def atomic_jsonl(path: Path, values: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in values),
        encoding="utf-8",
    )
    os.replace(temporary, path)


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def review_prompt(contract: dict[str, Any]) -> str:
    return f"""Inspect the attached image using only its visible pixels.

TEACHING LABEL: {contract['display_label']}
PART OF SPEECH: {contract['part_of_speech']}
ONE SELECTED MEANING: {contract['teaching_sense']}

Decide whether this exact still image is honest, direct teaching evidence for that one meaning.
Do not accept merely because another meaning of the same spelling is visible. In particular,
distinguish nouns from actions, objects from verbs, states from events, and completed past tense
from present or ongoing action. A related object, written occurrence of the word, imagined
before/after event, or generic association is insufficient. Reject visual ambiguity that could
teach the wrong sense. Also reject material anatomy/object defects, misleading text, overlays,
or watermarks. Choose uncertain only when the pixels genuinely prevent a decision.

For a rejection or uncertainty, generation_correction must describe a concrete image that would
directly teach the selected meaning. For a fit, write "none". Return exactly the required JSON.
"""


def review_one(
    *,
    slot: str,
    asset: dict[str, Any],
    contract: dict[str, Any],
    codex: str,
    model: str,
    timeout: int,
) -> dict[str, Any]:
    path = Path(str(asset["local_path"]))
    if not path.is_file():
        raise FileNotFoundError(path)
    expected = str(asset.get("sha256") or asset.get("asset_sha256") or "")
    if expected and digest(path) != expected:
        raise ValueError(f"hash mismatch for {slot}")
    result, transcript = structured_codex_review(
        path,
        executable=codex,
        model=model,
        timeout=timeout,
        prompt=review_prompt(contract),
        schema=REVIEW_SCHEMA,
        temporary_prefix="ninereeds-c36-infinitive-preflight-",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "slot_id": slot,
        "ordinal": int(contract["ordinal"]),
        "concept_id": contract["concept_id"],
        "lemma": contract["lemma"],
        "word": contract["display_label"],
        "part_of_speech": contract["part_of_speech"],
        "teaching_sense": contract["teaching_sense"],
        "source_local_path": str(path),
        "source_sha256": expected,
        **result,
        "review_backend": "codex",
        "review_model": model,
        "transcript": transcript,
    }


def preflight(args: argparse.Namespace) -> dict[str, Any]:
    manifest = {str(row["slot_id"]): row for row in load_jsonl(args.manifest)}
    contracts = {int(row["ordinal"]): row for row in load_jsonl(args.contracts)}
    flagged = load_jsonl(args.remediation)
    expected_slots = sorted(
        str(slot)
        for contract in flagged
        for slot in contract["image_mismatch_slots"]
    )
    if len(expected_slots) != len(set(expected_slots)):
        raise ValueError("remediation queue repeats a slot")
    missing = [slot for slot in expected_slots if slot not in manifest]
    if missing:
        raise ValueError(f"remediation slots missing from manifest: {missing[:5]}")

    decisions_path = args.output / "decisions.jsonl"
    prior = {row["slot_id"]: row for row in load_jsonl(decisions_path)}
    unexpected = sorted(set(prior) - set(expected_slots))
    if unexpected:
        raise ValueError(f"preflight ledger contains unexpected slots: {unexpected[:5]}")
    pending = [slot for slot in expected_slots if slot not in prior]
    lock = threading.Lock()

    def durable_append(row: dict[str, Any]) -> None:
        with lock:
            args.output.mkdir(parents=True, exist_ok=True)
            with decisions_path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {}
        for slot in pending:
            asset = manifest[slot]
            ordinal = int(slot[1:5])
            futures[
                pool.submit(
                    review_one,
                    slot=slot,
                    asset=asset,
                    contract=contracts[ordinal],
                    codex=args.codex,
                    model=args.model,
                    timeout=args.timeout,
                )
            ] = slot
        for index, future in enumerate(as_completed(futures), 1):
            slot = futures[future]
            try:
                row = future.result()
            except Exception as exc:
                row = {
                    "schema_version": SCHEMA_VERSION,
                    "reviewed_at": datetime.now(timezone.utc).isoformat(),
                    "slot_id": slot,
                    "ordinal": int(slot[1:5]),
                    "concept_id": contracts[int(slot[1:5])]["concept_id"],
                    "lemma": contracts[int(slot[1:5])]["lemma"],
                    "word": contracts[int(slot[1:5])]["display_label"],
                    "part_of_speech": contracts[int(slot[1:5])]["part_of_speech"],
                    "teaching_sense": contracts[int(slot[1:5])]["teaching_sense"],
                    "verdict": "uncertain",
                    "literal_caption": "review failed",
                    "target_evidence": "none",
                    "depicted_sense": "unresolved",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "generation_correction": "Generate fresh direct evidence for the selected sense.",
                    "visible_text": False,
                    "watermark": False,
                    "quality_flags": ["review_failure"],
                    "review_backend": "error",
                    "review_model": args.model,
                }
            durable_append(row)
            prior[slot] = row
            print(f"reviewed {index}/{len(pending)} {slot} {row['verdict']}", flush=True)

    decisions = [prior[slot] for slot in expected_slots]
    generation = [row for row in decisions if row["verdict"] != "fit"]
    atomic_jsonl(args.output / "generation-queue.jsonl", generation)
    counts: dict[str, int] = {}
    for row in decisions:
        counts[row["verdict"]] = counts.get(row["verdict"], 0) + 1
    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "caption_flagged_slots": len(expected_slots),
        "pixel_reviewed_slots": len(decisions),
        "verdict_counts": dict(sorted(counts.items())),
        "generation_queue_slots": len(generation),
        "generation_queue_contracts": len({row["ordinal"] for row in generation}),
        "complete": len(decisions) == len(expected_slots),
    }
    atomic_json(args.output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("preflight",))
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACTS)
    parser.add_argument("--remediation", type=Path, default=DEFAULT_REMEDIATION)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--workers", type=int, default=12)
    parser.add_argument("--timeout", type=int, default=600)
    args = parser.parse_args()
    if not 1 <= args.workers <= 32:
        raise ValueError("workers must be between 1 and 32")
    result = preflight(args)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
