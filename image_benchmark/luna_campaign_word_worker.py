"""Use Codex Luna as the primary target-fit reviewer for trusted local assets."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time
from typing import Any

from image_benchmark.campaign35_word_worker import (
    collect_unique_target_words,
    parse_response,
)
from image_benchmark.luna_watermark_worker import structured_codex_review
from image_registry.campaign35_word_review import load_bindings_for_asset
from image_registry.cli import DEFAULT_DB, connect
from image_registry.review_queue import (
    claim_batch, complete_claim, fail_claim, queue_status, register_worker, renew_claim,
)


MODEL = "gpt-5.6-luna"
SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "admission": {"type": "string", "enum": ["usable", "unusable", "uncertain"]},
        "visible_text": {"type": "boolean"},
        "watermark": {"type": "boolean"},
        "quality_flags": {"type": "array", "items": {"type": "string"}},
        "literal_caption": {"type": "string", "minLength": 1, "maxLength": 500},
        "reason": {"type": "string", "minLength": 1, "maxLength": 500},
        "targets": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "word": {"type": "string", "minLength": 1},
                    "visible": {
                        "type": "string", "enum": ["present", "absent", "uncertain"],
                    },
                    "evidence": {"type": "string", "minLength": 1, "maxLength": 500},
                },
                "required": ["word", "visible", "evidence"],
                "additionalProperties": False,
            },
        },
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "admission", "visible_text", "watermark", "quality_flags",
        "literal_caption", "reason", "targets", "uncertainties",
    ],
    "additionalProperties": False,
}


def coalesce_sense_targets(
    targets: list[dict[str, Any]], expected_words: list[str],
) -> list[dict[str, Any]]:
    """Collapse Luna's per-sense rows into the requested surface-term row.

    One mapped teaching concept can intentionally contain several legitimate senses.
    A single exposure is a fit when at least one declared sense is directly visible;
    concept-level variation is audited across all ten exposures later.
    """
    canonical = {word.casefold(): word for word in expected_words}
    # Luna will occasionally return the surface lemma (``sole``) even when the
    # immutable contract deliberately disambiguates it (``sole (of foot)``).
    # Accept that abbreviation only when it identifies exactly one expected
    # contract.  If two senses such as ``bank (river)`` and ``bank (financial)``
    # are present together, ``bank`` remains ambiguous and is correctly left as
    # an extra/missing target for retry rather than guessed.
    aliases: dict[str, list[str]] = {}
    for key in canonical:
        for marker in (" (", " —"):
            if marker in key:
                alias = key.split(marker, 1)[0].strip()
                if alias:
                    aliases.setdefault(alias, []).append(key)
                break
    grouped: dict[str, list[dict[str, Any]]] = {key: [] for key in canonical}
    extras: list[dict[str, Any]] = []
    for target in targets:
        value = str(target.get("word", "")).strip().casefold()
        key = value if value in canonical else None
        if key is None:
            for candidate in canonical:
                if value.startswith(candidate + " (") or value.startswith(candidate + " —"):
                    key = candidate
                    break
        if key is None and len(aliases.get(value, [])) == 1:
            key = aliases[value][0]
        if key is None:
            extras.append(target)
        else:
            grouped[key].append(target)
    merged: list[dict[str, Any]] = []
    rank = {False: 0, "uncertain": 1, True: 2}
    for key, word in canonical.items():
        items = grouped[key]
        if not items:
            continue
        visible = max((item["visible"] for item in items), key=rank.__getitem__)
        evidence = "; ".join(dict.fromkeys(
            str(item.get("evidence", "")).strip() for item in items
            if str(item.get("evidence", "")).strip()
        ))
        merged.append({"word": word, "visible": visible, "evidence": evidence})
    return merged + extras


def prompt_for(bindings: list[dict[str, Any]]) -> str:
    words = collect_unique_target_words(bindings)
    descriptions: dict[str, list[str]] = {word.casefold(): [] for word in words}
    for row in bindings:
        word = str(row["word"]).strip()
        sense = str(row.get("teaching_sense") or row.get("concept") or word).strip()
        if sense not in descriptions[word.casefold()]:
            descriptions[word.casefold()].append(sense)
    target_block = "\n".join(
        f"- {word}: {'; '.join(descriptions[word.casefold()])}" for word in words
    )
    return f"""Inspect this already corpus-approved local image as a candidate for a language lesson.

Target teaching terms and intended senses:
{target_block}

Use only visible pixels. For each term, return `present` only when the image directly and
unambiguously supports the intended sense, `absent` when it does not, and `uncertain` only
when the relevant pixels genuinely cannot be judged. A merely related scene, homonym, hidden
state, imagined event, filename, metadata, or caption is not evidence. Give one target result
for each term above.

The asset was previously audited, but independently report any visible watermark, serious
quality problem, or uncertainty you notice so it can be escalated. Write one literal caption
describing only visible content and one short top-level reason summarizing the decision. Return
only the required JSON."""


def run(args: argparse.Namespace) -> None:
    with connect(args.db) as db:
        register_worker(db, args.queue, args.worker_id, "codex", args.model, 1)
    processed = 0
    while args.max_items is None or processed < args.max_items:
        with connect(args.db) as db:
            claims = claim_batch(
                db, args.queue, args.worker_id, requested=1,
                lease_seconds=args.lease_seconds,
            )
            status = queue_status(db, args.queue)
        if not claims:
            unfinished = sum(status["counts"].get(key, 0) for key in ("pending", "leased"))
            if not unfinished:
                return
            time.sleep(args.poll_seconds)
            continue
        claim = claims[0]
        started = time.perf_counter()
        try:
            image = Path(claim["local_path"])
            if hashlib.sha256(image.read_bytes()).hexdigest() != claim["sha256"]:
                raise ValueError(f"image hash mismatch for {claim['source_id']}")
            with connect(args.db) as db:
                renew_claim(db, claim["claim_token"], args.worker_id, args.lease_seconds)
                bindings = load_bindings_for_asset(db, claim["queue_name"], claim["asset_id"])
            expected = collect_unique_target_words(bindings)
            parsed, transcript = structured_codex_review(
                image, executable=args.codex, model=args.model, timeout=args.timeout,
                prompt=prompt_for(bindings), schema=SCHEMA,
                temporary_prefix="ninereeds-luna-local-word-",
            )
            review_reason = parsed.pop("reason")
            for target in parsed["targets"]:
                target["visible"] = {
                    "present": True, "absent": False, "uncertain": "uncertain",
                }[target["visible"]]
            parsed["targets"] = coalesce_sense_targets(parsed["targets"], expected)
            _, errors = parse_response(json.dumps(parsed), expected)
            if errors:
                raise ValueError("schema-invalid Luna result: " + "; ".join(errors))
            record = {
                "queue": args.queue, "ordinal": claim["ordinal"],
                "source_id": claim["source_id"], "asset_id": claim["asset_id"],
                "worker_id": args.worker_id, "backend": "codex", "model": args.model,
                "prompt_version": "campaign36-local-word-fit-luna-v1",
                "attempt_number": claim["attempt_number"],
                "inference_seconds": time.perf_counter() - started,
                "raw": json.dumps(parsed, ensure_ascii=False), "parsed": parsed,
                "schema_errors": [], "semantic_contract_errors": [],
                "usage": None, "targets": expected, "transcript": transcript,
                "review_reason": review_reason,
            }
            with connect(args.db) as db:
                complete_claim(db, claim["claim_token"], args.worker_id, record)
            print(f"{claim['ordinal']} {claim['source_id']} reviewed", flush=True)
        except Exception as exc:
            retry = claim["attempt_number"] < args.max_attempts
            with connect(args.db) as db:
                fail_claim(
                    db, claim["claim_token"], args.worker_id,
                    {"type": type(exc).__name__, "message": str(exc), "retry": retry},
                    retry=retry,
                )
            print(f"{claim['ordinal']} failed: {type(exc).__name__}: {exc}", flush=True)
        processed += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--queue", required=True)
    parser.add_argument("--worker-id", required=True)
    parser.add_argument("--codex", default="/home/aomukai/.local/bin/codex")
    parser.add_argument("--model", default=MODEL)
    parser.add_argument("--lease-seconds", type=int, default=1800)
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--max-attempts", type=int, default=6)
    parser.add_argument("--max-items", type=int)
    parser.add_argument("--poll-seconds", type=float, default=5)
    run(parser.parse_args())


if __name__ == "__main__":
    main()
