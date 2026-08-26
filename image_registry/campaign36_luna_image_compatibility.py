"""Audit images for Campaign 36 concepts changed by Luna's lexicon repair.

Grade-C changes are deterministically incompatible because they explicitly require
new images. Grade A/B changes are inspected, one concept at a time, by Codex Luna
with the accepted images attached. Results are append-only and this tool starts no
image generation or model training.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
from typing import Any


ROOT = Path("/media/aomukai/FILES/Ninereeds/image-corpus/exports/campaign36-foundation-preparation-v1")
LEXICON = ROOT / "lexicon-revision-v1/luna-repair-v1/repaired-lexicon.jsonl"
LEXICON_SUMMARY = ROOT / "lexicon-revision-v1/luna-repair-v1/summary.json"
BASE = ROOT / "loop/corrections/2026-08-22-knew-to-know/decisions.jsonl"
GENERATED = ROOT / "flux-specialist-v1/reconciliation-current/accepted-generated-slots.jsonl"
OUTPUT = ROOT / "lexicon-revision-v1/luna-image-compatibility-v1"
CODEX = Path("/home/aomukai/.local/bin/codex")
MODEL = "gpt-5.6-luna"
SCHEMA_VERSION = "ninereeds_campaign36_luna_image_compatibility_v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def append_jsonl(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def sha256(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def accepted_slots() -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(BASE):
        if row.get("disposition") == "accepted":
            result[row["slot_id"]] = row
    for row in load_jsonl(GENERATED):
        result[row["slot_id"]] = {**row, "disposition": "accepted"}
    return result


def changed_rows() -> list[dict[str, Any]]:
    return [row for row in load_jsonl(LEXICON) if row.get("luna_decision")]


def schema(slot_ids: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "concept_id": {"type": "string"},
            "decisions": {
                "type": "array", "minItems": len(slot_ids), "maxItems": len(slot_ids),
                "items": {
                    "type": "object",
                    "properties": {
                        "slot_id": {"type": "string", "enum": slot_ids},
                        "compatible": {"type": "boolean"},
                        "literal_caption": {"type": "string"},
                        "target_evidence": {"type": "string"},
                        "reason": {"type": "string", "minLength": 1},
                        "uncertainties": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["slot_id", "compatible", "literal_caption", "target_evidence", "reason", "uncertainties"],
                    "additionalProperties": False,
                },
            },
            "pack_note": {"type": "string"},
        },
        "required": ["concept_id", "decisions", "pack_note"],
        "additionalProperties": False,
    }


def review_concept(row: dict[str, Any], assets: list[dict[str, Any]], timeout: int, retries: int) -> dict[str, Any]:
    source = row["source"]
    effective = row["effective"]
    source_id = source["concept_id"]
    slot_ids = [asset["slot_id"] for asset in assets]
    image_map = [
        {
            "image_number": index,
            "slot_id": asset["slot_id"],
            "prior_word": asset.get("word"),
            "prior_caption": asset.get("literal_caption"),
            "prior_evidence": asset.get("target_evidence"),
            "path": asset["local_path"],
        }
        for index, asset in enumerate(assets, 1)
    ]
    prompt = f"""You are Luna performing a strict image-compatibility audit for one English teaching concept.

Inspect every attached image. Decide whether the visible image itself is honest, useful evidence for
the exact NEW target below. Prior captions are hints only and cannot override pixels. Reject images
that depict only the old meaning, depend on invisible context, contradict the target, are malformed,
or would teach a misleading association. Visible text is allowed when it is correct and useful.
Do not change the teaching target and do not be lenient merely to preserve an asset.

CONCEPT ID: {source_id}
OLD TERM: {row['mapping'].get('teaching_term')}
OLD SENSE: {row['mapping'].get('teaching_sense')}
NEW TERM: {effective['teaching_term']}
NEW PART OF SPEECH: {effective['part_of_speech']}
NEW SENSE: {effective['teaching_sense']}
PRIOR COMPATIBILITY GRADE: {effective['image_grade']}

ATTACHED IMAGE MAP:
{json.dumps(image_map, ensure_ascii=False, indent=2)}

Return exactly one decision per slot_id. literal_caption must describe visible content without
claiming the target word. target_evidence must state the visible evidence for the new sense, or be
empty when incompatible. concept_id must exactly match the supplied concept ID.
"""
    key = hashlib.sha256(source_id.encode()).hexdigest()[:12]
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        stem = f"{key}-attempt-{attempt}"
        with tempfile.TemporaryDirectory(prefix="ninereeds-luna-image-compat-") as raw:
            temporary = Path(raw)
            schema_path = temporary / "schema.json"
            output_path = temporary / "result.json"
            schema_path.write_text(json.dumps(schema(slot_ids)), encoding="utf-8")
            command = [
                str(CODEX), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
                "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(temporary),
                "--model", MODEL, "--output-schema", str(schema_path),
                "--output-last-message", str(output_path), "--color", "never",
            ]
            for asset in assets:
                command.extend(["--image", asset["local_path"]])
            command.append("-")
            try:
                completed = subprocess.run(command, input=prompt, text=True, capture_output=True, timeout=timeout, check=False)
                atomic_json(OUTPUT / f"{stem}-transcript.json", {
                    "at": now(), "model": MODEL, "concept_id": source_id,
                    "returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr,
                })
                if completed.returncode != 0 or not output_path.is_file():
                    raise RuntimeError(completed.stderr[-1500:])
                payload = json.loads(output_path.read_text(encoding="utf-8"))
                if payload.get("concept_id") != source_id:
                    raise ValueError("concept_id mismatch")
                decisions = payload.get("decisions", [])
                actual = [decision.get("slot_id") for decision in decisions]
                if len(actual) != len(slot_ids) or set(actual) != set(slot_ids):
                    raise ValueError("Luna did not return every slot exactly once")
                return payload
            except Exception as exc:
                last = exc
                atomic_json(OUTPUT / f"{stem}-error.json", {"at": now(), "error": str(exc)})
                prompt += f"\n\nA prior attempt failed deterministic validation: {exc}. Correct it."
    raise RuntimeError(f"compatibility review failed for {source_id}: {last}")


def run(timeout: int, retries: int) -> dict[str, Any]:
    gate = json.loads(LEXICON_SUMMARY.read_text(encoding="utf-8"))
    if not gate.get("ready_for_luna_image_compatibility_review"):
        raise RuntimeError("lexical gate is not ready")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    ledger = OUTPUT / "decisions.jsonl"
    completed = {row["slot_id"] for row in load_jsonl(ledger)}
    slots = accepted_slots()
    changed = changed_rows()

    for row in changed:
        source_id = row["source"]["concept_id"]
        assets = sorted(
            [asset for asset in slots.values() if asset.get("concept_id") == source_id],
            key=lambda asset: asset["slot_id"],
        )
        pending = [asset for asset in assets if asset["slot_id"] not in completed]
        if not pending:
            continue
        if row["effective"]["image_grade"] == "C":
            for asset in pending:
                append_jsonl(ledger, {
                    "schema_version": SCHEMA_VERSION, "created_at": now(), "concept_id": source_id,
                    "slot_id": asset["slot_id"], "compatible": False,
                    "literal_caption": asset.get("literal_caption", ""), "target_evidence": "",
                    "reason": "Grade-C lexicon replacement requires new images for a different teaching target.",
                    "uncertainties": [], "review_backend": "deterministic_grade_c",
                    "review_model": None, "asset_sha256": asset.get("sha256") or asset.get("asset_sha256"),
                    "local_path": asset.get("local_path"),
                })
                completed.add(asset["slot_id"])
            continue
        payload = review_concept(row, pending, timeout, retries)
        by_slot = {asset["slot_id"]: asset for asset in pending}
        for decision in payload["decisions"]:
            asset = by_slot[decision["slot_id"]]
            append_jsonl(ledger, {
                "schema_version": SCHEMA_VERSION, "created_at": now(), "concept_id": source_id,
                **decision, "pack_note": payload.get("pack_note", ""),
                "review_backend": "codex_headless_multimodal", "review_model": MODEL,
                "asset_sha256": asset.get("sha256") or asset.get("asset_sha256"),
                "local_path": asset.get("local_path"),
            })
            completed.add(decision["slot_id"])

    decisions = load_jsonl(ledger)
    changed_ids = {row["source"]["concept_id"] for row in changed}
    expected = {slot_id for slot_id, asset in slots.items() if asset.get("concept_id") in changed_ids}
    actual = {row["slot_id"] for row in decisions}
    if actual != expected or len(actual) != len(decisions):
        raise RuntimeError(f"compatibility ledger mismatch: expected={len(expected)} actual={len(actual)} rows={len(decisions)}")
    retained = sum(bool(row["compatible"]) for row in decisions)
    per_concept_retained: dict[str, int] = {concept_id: 0 for concept_id in changed_ids}
    for decision in decisions:
        per_concept_retained[decision["concept_id"]] += int(bool(decision["compatible"]))
    residual = sum(10 - min(10, count) for count in per_concept_retained.values())
    summary = {
        "schema_version": SCHEMA_VERSION, "created_at": now(), "changed_concepts": len(changed_ids),
        "audited_accepted_assets": len(decisions), "retained_assets": retained,
        "rejected_assets": len(decisions) - retained, "residual_slots_for_changed_concepts": residual,
        "lexicon_sha256": sha256(LEXICON), "decisions_sha256": sha256(ledger),
        "ready_for_image_reconciliation": True,
    }
    atomic_json(OUTPUT / "summary.json", summary)
    print(json.dumps(summary, indent=2), flush=True)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--retries", type=int, default=3)
    args = parser.parse_args()
    run(args.timeout, args.retries)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
