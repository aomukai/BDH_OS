"""Sequentially repair Campaign 36's candidate lexicon with Codex Luna.

The phases are deliberately serialized: hard global collisions, remaining
low-confidence proposals, then allocation of reclaimed slots.  Each completed
phase is durable and each accepted term becomes reserved before the next phase.
This tool does not inspect images, mutate the source lexicon, or start training.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any


REPO = Path("/home/aomukai/Ninereeds")
ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/lexicon-revision-v1"
)
OUTPUT = ROOT / "luna-repair-v1"
MODEL = "gpt-5.6-luna"
CODEX = Path("/home/aomukai/.local/bin/codex")
SCHEMA_VERSION = "ninereeds_campaign36_luna_lexicon_repair_v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def norm(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def base_effective(row: dict[str, Any]) -> dict[str, Any]:
    revision = row.get("candidate_revision")
    if revision:
        return {
            "teaching_term": revision.get("teaching_term", ""),
            "teaching_sense": revision.get("teaching_sense", ""),
            "part_of_speech": revision.get("part_of_speech", "other"),
            "image_grade": revision.get("same_image_grade", "C"),
            "action": revision.get("action"),
            "confidence": revision.get("confidence"),
            "authority": "semantic_first_pass",
        }
    mapping = row["mapping"]
    return {
        "teaching_term": mapping.get("teaching_term", ""),
        "teaching_sense": mapping.get("teaching_sense", ""),
        "part_of_speech": mapping.get("part_of_speech", "unspecified"),
        "image_grade": "A" if mapping.get("image_compatibility") == "unchanged" else "C",
        "action": "BASE",
        "confidence": "high",
        "authority": "virtual_lexicon",
    }


def load_decisions() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for phase in ("collisions", "low-confidence", "allocation"):
        ledger = OUTPUT / f"{phase}-decisions.jsonl"
        for record in load_jsonl(ledger):
            decision = record["decision"]
            result[decision["source_concept_id"]] = {**decision, "phase": phase}
        path = OUTPUT / f"{phase}-decisions.json"
        if not path.is_file():
            continue
        payload = json.loads(path.read_text(encoding="utf-8"))
        for decision in payload["decisions"]:
            result[decision["source_concept_id"]] = {**decision, "phase": phase}
    return result


def effective_rows(decisions: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in load_jsonl(ROOT / "candidate-lexicon.jsonl"):
        source_id = row["source"]["concept_id"]
        effective = base_effective(row)
        decision = decisions.get(source_id)
        if decision:
            if decision["action"] == "RECLAIM":
                effective = {
                    "teaching_term": "", "teaching_sense": "", "part_of_speech": "",
                    "image_grade": "C", "action": "RECLAIM",
                    "confidence": decision["confidence"], "authority": "luna",
                }
            else:
                effective = {
                    "teaching_term": decision["teaching_term"],
                    "teaching_sense": decision["teaching_sense"],
                    "part_of_speech": decision["part_of_speech"],
                    "image_grade": decision["image_grade"],
                    "action": decision["action"],
                    "confidence": decision["confidence"],
                    "authority": "luna",
                }
        result.append({**row, "effective": effective, "luna_decision": decision})
    return result


def collision_groups(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_term: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        term = norm(str(row["effective"]["teaching_term"]))
        if term:
            by_term[term].append(row)
    collisions = []
    for term, members in sorted(by_term.items()):
        if len(members) < 2:
            continue
        parts = [norm(str(row["effective"]["part_of_speech"])) for row in members]
        intentional_homograph = all(parts) and len(parts) == len(set(parts)) and "unspecified" not in parts
        if intentional_homograph:
            continue
        collisions.append({
            "normalized_term": term,
            "members": [{
                "source_concept_id": row["source"]["concept_id"],
                "source_concept": row["source"]["concept"],
                "source_sense": row["mapping"].get("source_sense"),
                "effective": row["effective"],
                "mutable": bool(row.get("candidate_revision") or row.get("luna_decision")),
            } for row in members],
        })
    return collisions


def collision_fingerprints(rows: list[dict[str, Any]]) -> set[tuple[str, tuple[str, ...]]]:
    """Return stable identities for every non-permitted collision."""
    return {
        (
            collision["normalized_term"],
            tuple(sorted(member["source_concept_id"] for member in collision["members"])),
        )
        for collision in collision_groups(rows)
    }


def schema_for(phase: str, count: int, actions: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "phase": {"type": "string", "enum": [phase]},
            "decisions": {
                "type": "array", "minItems": count, "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "source_concept_id": {"type": "string", "minLength": 1},
                        "action": {"type": "string", "enum": actions},
                        "teaching_term": {"type": "string"},
                        "teaching_sense": {"type": "string"},
                        "part_of_speech": {
                            "type": "string",
                            "enum": ["noun", "verb", "adjective", "adverb", "phrase", "other", ""],
                        },
                        "image_grade": {"type": "string", "enum": ["A", "B", "C"]},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        "rationale": {"type": "string", "minLength": 1},
                    },
                    "required": [
                        "source_concept_id", "action", "teaching_term", "teaching_sense",
                        "part_of_speech", "image_grade", "confidence", "rationale",
                    ],
                    "additionalProperties": False,
                },
            },
            "notes": {"type": "string"},
        },
        "required": ["phase", "decisions", "notes"],
        "additionalProperties": False,
    }


def run_luna(
    prompt: str,
    schema: dict[str, Any],
    phase: str,
    timeout: int,
    *,
    artifact_stem: str | None = None,
) -> dict[str, Any]:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    stem = artifact_stem or phase
    prompt_path = OUTPUT / f"{stem}-prompt.txt"
    prompt_path.write_text(prompt, encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix=f"ninereeds-luna-lexicon-{phase}-") as raw:
        temporary = Path(raw)
        schema_path = temporary / "schema.json"
        output_path = temporary / "result.json"
        schema_path.write_text(json.dumps(schema, sort_keys=True), encoding="utf-8")
        command = [
            str(CODEX), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(temporary),
            "--model", MODEL, "--output-schema", str(schema_path),
            "--output-last-message", str(output_path), "--color", "never", "-",
        ]
        completed = subprocess.run(
            command, input=prompt, text=True, capture_output=True, timeout=timeout, check=False,
        )
        transcript = {
            "at": now(), "phase": phase, "model": MODEL, "returncode": completed.returncode,
            "stdout": completed.stdout, "stderr": completed.stderr,
        }
        atomic_json(OUTPUT / f"{stem}-transcript.json", transcript)
        if completed.returncode != 0 or not output_path.is_file():
            raise RuntimeError(f"Luna {phase} failed: {completed.stderr[-1500:]}")
        return json.loads(output_path.read_text(encoding="utf-8"))


def validate_decisions(
    payload: dict[str, Any], expected_ids: set[str], *, phase: str, actions: set[str],
) -> None:
    if payload.get("phase") != phase:
        raise ValueError(f"phase mismatch: {payload.get('phase')!r}")
    rows = payload.get("decisions")
    if not isinstance(rows, list):
        raise ValueError("decisions must be a list")
    actual = [row.get("source_concept_id") for row in rows]
    if set(actual) != expected_ids or len(actual) != len(expected_ids):
        raise ValueError("Luna did not return every requested source ID exactly once")
    for row in rows:
        if row.get("action") not in actions:
            raise ValueError("invalid repair action")
        if row["action"] == "RECLAIM":
            row.update({"teaching_term": "", "teaching_sense": "", "part_of_speech": "", "image_grade": "C"})
        elif not all(norm(str(row.get(key, ""))) for key in ("teaching_term", "teaching_sense", "part_of_speech")):
            raise ValueError("accepted/replaced decisions require a complete target")


def occupied_terms(rows: list[dict[str, Any]], exclude: set[str]) -> list[str]:
    return sorted({
        norm(str(row["effective"]["teaching_term"]))
        for row in rows
        if row["source"]["concept_id"] not in exclude and norm(str(row["effective"]["teaching_term"]))
    })


def commit_phase(
    phase: str,
    expected_ids: set[str],
    prompt: str,
    actions: set[str],
    timeout: int,
    retries: int,
    post_validate: Any = None,
) -> None:
    path = OUTPUT / f"{phase}-decisions.json"
    if path.is_file():
        validate_decisions(json.loads(path.read_text()), expected_ids, phase=phase, actions=actions)
        return
    last: Exception | None = None
    current_prompt = prompt
    for attempt in range(1, retries + 1):
        try:
            payload = run_luna(current_prompt, schema_for(phase, len(expected_ids), sorted(actions)), phase, timeout)
            validate_decisions(payload, expected_ids, phase=phase, actions=actions)
            if post_validate is not None:
                post_validate(payload)
            atomic_json(path, {"schema_version": SCHEMA_VERSION, "created_at": now(), **payload})
            return
        except Exception as exc:
            last = exc
            current_prompt = prompt + f"\n\nA prior attempt failed deterministic validation: {exc}. Correct that failure."
            atomic_json(OUTPUT / f"{phase}-attempt-{attempt}-error.json", {"at": now(), "error": str(exc)})
    raise RuntimeError(f"Luna phase {phase} failed after {retries} attempts: {last}")


def commit_item(
    *,
    phase: str,
    item_key: str,
    expected_ids: set[str],
    prompt: str,
    actions: set[str],
    timeout: int,
    retries: int,
) -> None:
    ledger = OUTPUT / f"{phase}-decisions.jsonl"
    completed = {
        record["decision"]["source_concept_id"] for record in load_jsonl(ledger)
    }
    if expected_ids <= completed:
        return
    if completed & expected_ids:
        raise RuntimeError(f"partial durable decision set for {phase}/{item_key}")
    last: Exception | None = None
    base_prompt = prompt
    before_collisions = collision_fingerprints(effective_rows(load_decisions()))
    for attempt in range(1, retries + 1):
        stem = f"{phase}-{item_key}-attempt-{attempt}"
        try:
            payload = run_luna(
                base_prompt,
                schema_for(phase, len(expected_ids), sorted(actions)),
                phase,
                timeout,
                artifact_stem=stem,
            )
            validate_decisions(payload, expected_ids, phase=phase, actions=actions)
            proposed = load_decisions()
            proposed.update({row["source_concept_id"]: row for row in payload["decisions"]})
            candidate_rows = effective_rows(proposed)
            after_collisions = collision_fingerprints(candidate_rows)
            if phase == "collisions":
                if not after_collisions < before_collisions:
                    introduced = sorted(after_collisions - before_collisions)
                    raise ValueError(
                        "collision repair must remove at least one collision and introduce none; "
                        f"before={len(before_collisions)} after={len(after_collisions)} "
                        f"introduced={introduced[:3]}"
                    )
            elif after_collisions:
                raise ValueError(
                    f"proposal introduces {len(after_collisions)} global collision(s)"
                )
            if phase == "allocation" and any(
                not norm(str(row["effective"]["teaching_term"])) for row in candidate_rows
                if row["source"]["concept_id"] in expected_ids
            ):
                raise ValueError("allocation left its reclaimed slot empty")
            for decision in payload["decisions"]:
                append_jsonl(ledger, {
                    "schema_version": SCHEMA_VERSION,
                    "created_at": now(),
                    "phase": phase,
                    "item_key": item_key,
                    "decision": decision,
                    "notes": payload.get("notes", ""),
                })
            return
        except Exception as exc:
            last = exc
            atomic_json(OUTPUT / f"{stem}-error.json", {"at": now(), "error": str(exc)})
            base_prompt = prompt + f"\n\nA prior attempt failed deterministic validation: {exc}. Correct it."
    raise RuntimeError(f"Luna item {phase}/{item_key} failed after {retries} attempts: {last}")


def phase_collisions(timeout: int, retries: int) -> None:
    while True:
        rows = effective_rows(load_decisions())
        collisions = collision_groups(rows)
        if not collisions:
            return
        collision = collisions[0]
        mutable_ids = {
            member["source_concept_id"] for member in collision["members"] if member["mutable"]
        }
        if not mutable_ids:
            raise RuntimeError(f"collision {collision['normalized_term']} has no mutable member")
        protected = occupied_terms(rows, mutable_ids)
        item_key = hashlib.sha256(
            (collision["normalized_term"] + "\0" + "\0".join(sorted(mutable_ids))).encode()
        ).hexdigest()[:12]
        prompt = f"""You are Luna, the sole sequential lexicon repairer for Ninereeds' English visual foundation.

PHASE 1: resolve this ONE global collision. Preserve a good target when possible. Use REPLACE for
a distinct, common, useful contemporary term or RECLAIM when no honest distinction exists. Never
invent an obscure synonym. An intentional noun/verb homograph is allowed only with genuinely
distinct senses and parts of speech. A new surface term must not appear in PROTECTED TERMS.

Return exactly one decision for each mutable source_concept_id. KEEP copies its complete current
target. REPLACE supplies a complete locked target. RECLAIM leaves target fields empty and grade C.
The top-level `phase` field must be exactly `collisions`.

COLLISION:
{json.dumps(collision, ensure_ascii=False, indent=2)}

PROTECTED TERMS ({len(protected)}):
{json.dumps(protected, ensure_ascii=False)}
"""
        commit_item(
            phase="collisions", item_key=item_key, expected_ids=mutable_ids, prompt=prompt,
            actions={"KEEP", "REPLACE", "RECLAIM"}, timeout=timeout, retries=retries,
        )


def phase_low_confidence(timeout: int, retries: int) -> None:
    original_low = load_jsonl(ROOT / "low-confidence-proposals.jsonl")
    for item in original_low:
        decisions = load_decisions()
        source_id = item["source_concept_id"]
        if source_id in decisions or item.get("action") == "RECLAIM_FOR_MISSING_VOCABULARY":
            continue
        rows = effective_rows(decisions)
        by_id = {row["source"]["concept_id"]: row for row in rows}
        expected_ids = {source_id}
        protected = occupied_terms(rows, expected_ids)
        evidence = {
            "source_concept_id": source_id,
            "source_concept": by_id[source_id]["source"]["concept"],
            "source_sense": by_id[source_id]["mapping"].get("source_sense"),
            "current_target": by_id[source_id]["effective"],
            "first_pass_rationale": item.get("rationale"),
        }
        prompt = f"""You are Luna, the sole sequential lexicon repairer for Ninereeds' English visual foundation.

PHASE 2: independently adjudicate this ONE low-confidence proposal after collision repair.
ACCEPT only a frequent, useful, honest locked sense. REPLACE a weak, forced, obscure, or malformed
proposal with a better missing term, or RECLAIM it for phase 3. A new term must not appear in
PROTECTED TERMS. Return exactly one decision. ACCEPT copies the complete current target.
The top-level `phase` field must be exactly `low-confidence`.

ITEM:
{json.dumps(evidence, ensure_ascii=False, indent=2)}

PROTECTED TERMS ({len(protected)}):
{json.dumps(protected, ensure_ascii=False)}
"""
        commit_item(
            phase="low-confidence", item_key=hashlib.sha256(source_id.encode()).hexdigest()[:12],
            expected_ids=expected_ids, prompt=prompt,
            actions={"ACCEPT", "REPLACE", "RECLAIM"}, timeout=timeout, retries=retries,
        )


def phase_allocation(timeout: int, retries: int) -> None:
    while True:
        decisions = load_decisions()
        rows = effective_rows(decisions)
        reclaimed = [row for row in rows if not norm(str(row["effective"]["teaching_term"]))]
        if not reclaimed:
            return
        row = reclaimed[0]
        source_id = row["source"]["concept_id"]
        expected_ids = {source_id}
        protected = occupied_terms(rows, expected_ids)
        prompt = f"""You are Luna, the sole sequential lexicon repairer for Ninereeds' English visual foundation.

PHASE 3: allocate ONE missing English vocabulary target to this reclaimed lineage slot. Select a
frequent, broadly useful contemporary word absent from PROTECTED TERMS. Prefer foundational
everyday objects, actions, properties, relations, social concepts, nature, tools, places, or basic
academic vocabulary. Do not choose a personal name, nonce word, spelling variant, empty inflection,
or obscure synonym. Give one exact teachable sense and part of speech. Prefer a visually groundable
sense, while permitting a genuinely important abstract word. New images are required: grade C.
The source ID is only stable lineage, not a semantic constraint. Return exactly one REPLACE.
The top-level `phase` field must be exactly `allocation`.

SOURCE ID: {json.dumps(source_id)}

PROTECTED TERMS ({len(protected)}):
{json.dumps(protected, ensure_ascii=False)}
"""
        commit_item(
            phase="allocation", item_key=hashlib.sha256(source_id.encode()).hexdigest()[:12],
            expected_ids=expected_ids, prompt=prompt, actions={"REPLACE"},
            timeout=timeout, retries=retries,
        )


def finalize() -> dict[str, Any]:
    decisions = load_decisions()
    rows = effective_rows(decisions)
    empty = [row["source"]["concept_id"] for row in rows if not norm(str(row["effective"]["teaching_term"]))]
    collisions = collision_groups(rows)
    low_ids = {row["source_concept_id"] for row in load_jsonl(ROOT / "low-confidence-proposals.jsonl")}
    unresolved_low = sorted(source_id for source_id in low_ids if source_id not in decisions)
    if empty or collisions or unresolved_low:
        raise RuntimeError(
            f"final lexical gate failed: empty={len(empty)} collisions={len(collisions)} "
            f"unresolved_low={len(unresolved_low)}"
        )
    atomic_jsonl(OUTPUT / "repaired-lexicon.jsonl", rows)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "created_at": now(),
        "lexicon_rows": len(rows),
        "luna_decisions": len(decisions),
        "collision_decisions": len(load_jsonl(OUTPUT / "collisions-decisions.jsonl")),
        "low_confidence_decisions": len(load_jsonl(OUTPUT / "low-confidence-decisions.jsonl")),
        "allocation_decisions": len(load_jsonl(OUTPUT / "allocation-decisions.jsonl")),
        "remaining_collisions": 0,
        "remaining_reclaimed_slots": 0,
        "remaining_low_confidence": 0,
        "source_candidate_sha256": digest(ROOT / "candidate-lexicon.jsonl"),
        "repaired_lexicon_sha256": digest(OUTPUT / "repaired-lexicon.jsonl"),
        "ready_for_luna_image_compatibility_review": True,
    }
    atomic_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    if not CODEX.is_file():
        raise RuntimeError(f"Codex executable is unavailable: {CODEX}")
    phase_collisions(args.timeout, args.retries)
    phase_low_confidence(args.timeout, args.retries)
    phase_allocation(args.timeout, args.retries)
    finalize()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
