"""Audit and revise Campaign 36's mapped teaching lexicon.

This tool freezes an exact duplicate inventory after approved proper-name replacements,
then asks the pinned local Gemma model to propose useful, collision-aware lexical
distinctions. It does not alter corpus assignments or start image generation.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import time
from typing import Any
import urllib.request

from image_registry.campaign36_flux_streaming_luna import append_jsonl, load_jsonl


REPO = Path("/home/aomukai/Ninereeds")
LEXICON = REPO / "config/mission_hub/campaign_material/campaign36/m2-teaching-lexicon.jsonl"
NAMES = REPO / "config/mission_hub/campaign_material/campaign36/lexicon-revision-v1/name-replacements.json"
RECON = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/flux-specialist-v1/reconciliation-current/"
    "concept-coverage.jsonl"
)
OUTPUT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/lexicon-revision-v1"
)
MODEL = "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf"
ENDPOINT = "http://127.0.0.1:8792/v1/chat/completions"
DEEPSEEK_ENDPOINT = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-v4-flash-vision-exp"
SCHEMA = "ninereeds_campaign36_lexicon_revision_v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalized(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()


def cluster_id(term: str, ids: list[str]) -> str:
    payload = term + "\0" + "\0".join(sorted(ids))
    return "dup-" + hashlib.sha256(payload.encode()).hexdigest()[:12]


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def virtual_rows() -> list[dict[str, Any]]:
    name_rows = json.loads(NAMES.read_text(encoding="utf-8"))["replacements"]
    replacements = {row["source_concept_id"]: row for row in name_rows}
    coverage = {row["concept_id"]: row for row in load_jsonl(RECON)}
    rows: list[dict[str, Any]] = []
    for record in load_jsonl(LEXICON):
        source = record["source"]
        mapping = dict(record["mapping"])
        approved = replacements.get(source["concept_id"])
        if approved:
            mapping.update({
                "teaching_term": approved["new_teaching_term"],
                "teaching_sense": approved["new_teaching_sense"],
                "mapping_relation": "replace",
                "recommended_action": "replace",
                "image_compatibility": "replacement_requires_new_images",
                "teaching_utility": "foundational",
            })
        rows.append({
            "source": source,
            "mapping": mapping,
            "coverage": coverage.get(source["concept_id"], {}),
            "approved_name_replacement": approved,
        })
    return rows


def command_inventory(args: argparse.Namespace) -> int:
    rows = virtual_rows()
    by_term: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_term[normalized(str(row["mapping"]["teaching_term"]))].append(row)
    clusters: list[dict[str, Any]] = []
    for term, members in sorted(by_term.items()):
        if len(members) < 2:
            continue
        ids = [row["source"]["concept_id"] for row in members]
        clusters.append({
            "schema_version": SCHEMA,
            "cluster_id": cluster_id(term, ids),
            "teaching_term": members[0]["mapping"]["teaching_term"],
            "member_count": len(members),
            "members": [{
                "source_concept_id": row["source"]["concept_id"],
                "source_concept": row["source"]["concept"],
                "ordinal": row["source"]["ordinal"],
                "source_sense": row["mapping"].get("source_sense"),
                "teaching_sense": row["mapping"].get("teaching_sense"),
                "teaching_utility": row["mapping"].get("teaching_utility"),
                "mapping_relation": row["mapping"].get("mapping_relation"),
                "accepted_image_slots": row["coverage"].get("accepted_image_slots", 0),
                "residual_route": row["coverage"].get("residual_route"),
            } for row in members],
        })
    current_terms = sorted({normalized(str(row["mapping"]["teaching_term"])) for row in rows})
    OUTPUT.mkdir(parents=True, exist_ok=True)
    write_jsonl(OUTPUT / "duplicate-clusters.jsonl", clusters)
    write_jsonl(OUTPUT / "virtual-lexicon.jsonl", rows)
    write_json(OUTPUT / "inventory-summary.json", {
        "schema_version": SCHEMA,
        "created_at": now(),
        "lexicon_rows": len(rows),
        "unique_teaching_terms": len(current_terms),
        "duplicate_clusters": len(clusters),
        "rows_in_duplicate_clusters": sum(row["member_count"] for row in clusters),
        "approved_personal_name_replacements": len(json.loads(NAMES.read_text())["replacements"]),
        "current_terms_sha256": hashlib.sha256("\n".join(current_terms).encode()).hexdigest(),
    })
    print((OUTPUT / "inventory-summary.json").read_text(), end="")
    return 0


SYSTEM_PROMPT = """You are revising a visual English foundation curriculum for an AI learner.
Each listed source row currently maps to the same teaching term, creating unintended weighting.
Create distinct, useful English targets without inventing obscure words merely to preserve rows.

Decision order:
1. Keep the existing common term for the row whose source sense best matches it.
2. If a missing, common derivational family member (noun, verb, adjective, or adverb) naturally
   expresses another source sense, use it.
3. Otherwise consider a very close synonym whose teaching sense can plausibly use the same images.
4. If no honest distinction exists, mark RECLAIM_FOR_MISSING_VOCABULARY. Do not force a synonym.

Image grades: A = essentially the same visible evidence; B = related scenes but every image needs
individual review; C = images should not be reused. Even grade A will later be checked by Luna.
Prefer contemporary, frequent, broadly useful English. Lock polysemous words to one exact sense.
Return JSON only, using the requested schema. Do not explain outside the JSON."""


def gemma_prompt(cluster: dict[str, Any]) -> str:
    return f"""Revise this duplicate cluster:
{json.dumps(cluster, ensure_ascii=False, indent=2)}

Return:
{{
  "cluster_id": {json.dumps(cluster['cluster_id'])},
  "canonical_term": "current shared term",
  "proposals": [
    {{
      "source_concept_id": "exact supplied id",
      "action": "KEEP|DERIVATIONAL_PAIR|NEAR_SYNONYM|RECLAIM_FOR_MISSING_VOCABULARY",
      "teaching_term": "term, or empty only for RECLAIM",
      "teaching_sense": "one exact instructional sense",
      "part_of_speech": "noun|verb|adjective|adverb|phrase|other",
      "relationship": "concise relationship to the canonical term",
      "same_image_grade": "A|B|C",
      "rationale": "concise curriculum rationale",
      "confidence": "high|medium|low"
    }}
  ],
  "notes": "important cluster-level warning or none"
}}

Include every source_concept_id exactly once. Terms must be unique within this cluster."""


def request_gemma(cluster: dict[str, Any], *, retries: int = 3) -> dict[str, Any]:
    body = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": gemma_prompt(cluster)},
        ],
        "temperature": 0.65,
        # This is a bounded lexical classification task.  Gemma's hidden
        # thinking can consume the review server's entire 4K context before it
        # emits JSON, so ask it to reason directly in the structured answer.
        "chat_template_kwargs": {"enable_thinking": False},
        "response_format": {"type": "json_object"},
    }
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                ENDPOINT, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(request, timeout=900) as response:
                payload = json.loads(response.read())
            content = payload["choices"][0]["message"]["content"]
            try:
                result = json.loads(content)
            except json.JSONDecodeError as parse_error:
                append_jsonl(OUTPUT / "gemma-invalid-json.jsonl", {
                    "schema_version": SCHEMA,
                    "at": now(),
                    "cluster_id": cluster["cluster_id"],
                    "attempt": attempt,
                    "error": str(parse_error),
                    "content": content,
                })
                if content.strip():
                    body["messages"].extend([
                        {"role": "assistant", "content": content},
                        {"role": "user", "content": (
                            "That response was invalid JSON: " + str(parse_error) +
                            ". Repair it and return the complete JSON object only. Keep every "
                            "source_concept_id exactly once and do not add commentary."
                        )},
                    ])
                raise
            result["generation"] = {
                "model": MODEL,
                "created_at": now(),
                "temperature": 0.65,
                "attempt": attempt,
                "usage": payload.get("usage", {}),
            }
            return result
        except Exception as exc:
            last = exc
            time.sleep(min(10, attempt * 2))
    raise RuntimeError(f"Gemma failed after {retries} attempts: {last}")


def request_deepseek(cluster: dict[str, Any], *, retries: int = 3) -> dict[str, Any]:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    body = {
        "model": DEEPSEEK_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": gemma_prompt(cluster)},
        ],
        "temperature": 0.65,
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
        "response_format": {"type": "json_object"},
        # Large duplicate clusters can spend several thousand tokens in the
        # model's reasoning channel before emitting JSON.  Leave ample room so
        # a valid answer is not converted into an empty-content failure.
        "max_tokens": 16384,
        "stream": False,
        "user_id": "ninereeds-campaign36-lexicon-revision-v1",
    }
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            request = urllib.request.Request(
                DEEPSEEK_ENDPOINT,
                data=json.dumps(body).encode(),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=900) as response:
                payload = json.loads(response.read())
            content = payload["choices"][0]["message"]["content"]
            result = json.loads(content)
            result["generation"] = {
                "provider": "deepseek",
                "model": payload.get("model", DEEPSEEK_MODEL),
                "created_at": now(),
                "temperature": 0.65,
                "thinking": "enabled",
                "reasoning_effort": "high",
                "attempt": attempt,
                "usage": payload.get("usage", {}),
            }
            return result
        except Exception as exc:
            last = exc
            append_jsonl(OUTPUT / "deepseek-errors.jsonl", {
                "schema_version": SCHEMA,
                "at": now(),
                "cluster_id": cluster["cluster_id"],
                "attempt": attempt,
                "error": str(exc),
            })
            time.sleep(min(10, attempt * 2))
    raise RuntimeError(f"DeepSeek failed after {retries} attempts: {last}")


def validate_proposal(cluster: dict[str, Any], result: dict[str, Any]) -> None:
    if result.get("cluster_id") != cluster["cluster_id"]:
        raise ValueError("cluster_id mismatch")
    expected = {row["source_concept_id"] for row in cluster["members"]}
    proposals = result.get("proposals")
    if not isinstance(proposals, list):
        raise ValueError("proposals must be a list")
    actual = {row.get("source_concept_id") for row in proposals}
    if actual != expected or len(proposals) != len(expected):
        raise ValueError(f"proposal IDs mismatch: expected {expected}, got {actual}")
    lexical_keys = [
        (
            normalized(str(row.get("teaching_term", ""))),
            normalized(str(row.get("part_of_speech", ""))),
        )
        for row in proposals
        if row.get("action") != "RECLAIM_FOR_MISSING_VOCABULARY"
    ]
    if (
        not all(term and part_of_speech for term, part_of_speech in lexical_keys)
        or len(lexical_keys) != len(set(lexical_keys))
    ):
        raise ValueError(
            "non-reclaimed teaching term/part-of-speech pairs must be nonempty and unique within cluster"
        )
    for row in proposals:
        if row.get("action") not in {"KEEP", "DERIVATIONAL_PAIR", "NEAR_SYNONYM", "RECLAIM_FOR_MISSING_VOCABULARY"}:
            raise ValueError("invalid action")
        # A reclaimed slot has no replacement sense yet, so its existing images
        # cannot meaningfully be declared reusable for that future vocabulary.
        if row.get("action") == "RECLAIM_FOR_MISSING_VOCABULARY":
            row["same_image_grade"] = "C"
            row["teaching_term"] = ""
            row["teaching_sense"] = ""
            row["part_of_speech"] = ""
        if row.get("same_image_grade") not in {"A", "B", "C"}:
            raise ValueError("invalid image grade")


def request_validated(
    cluster: dict[str, Any],
    request_fn: Any,
    *,
    provider: str,
    retries: int = 3,
) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(1, retries + 1):
        result = request_fn(cluster)
        try:
            validate_proposal(cluster, result)
            return result
        except Exception as exc:
            last = exc
            append_jsonl(OUTPUT / f"{provider}-policy-rejections.jsonl", {
                "schema_version": SCHEMA,
                "at": now(),
                "cluster_id": cluster["cluster_id"],
                "attempt": attempt,
                "error": str(exc),
                "result": result,
            })
    raise RuntimeError(f"{provider} returned policy-invalid proposals after {retries} attempts: {last}")


def command_gemma(args: argparse.Namespace) -> int:
    clusters = load_jsonl(OUTPUT / "duplicate-clusters.jsonl")
    output = OUTPUT / "gemma-proposals.jsonl"
    count = 0
    for cluster in clusters:
        completed = {
            row["cluster_id"]
            for path in (OUTPUT / "gemma-proposals.jsonl", OUTPUT / "deepseek-proposals.jsonl")
            for row in load_jsonl(path, tolerate_partial_tail=True)
        }
        if cluster["cluster_id"] in completed:
            continue
        result = request_validated(cluster, request_gemma, provider="gemma")
        append_jsonl(output, {"schema_version": SCHEMA, **result})
        count += 1
        print(json.dumps({"completed_union": len(completed) + 1, "total": len(clusters), "cluster": cluster["teaching_term"]}), flush=True)
        if args.limit and count >= args.limit:
            break
    return 0


def command_deepseek(args: argparse.Namespace) -> int:
    clusters = list(reversed(load_jsonl(OUTPUT / "duplicate-clusters.jsonl")))
    output = OUTPUT / "deepseek-proposals.jsonl"
    count = 0
    for cluster in clusters:
        completed = {
            row["cluster_id"]
            for path in (OUTPUT / "gemma-proposals.jsonl", OUTPUT / "deepseek-proposals.jsonl")
            for row in load_jsonl(path, tolerate_partial_tail=True)
        }
        if cluster["cluster_id"] in completed:
            continue
        result = request_validated(cluster, request_deepseek, provider="deepseek")
        append_jsonl(output, {"schema_version": SCHEMA, **result})
        count += 1
        print(json.dumps({"completed_union": len(completed) + 1, "total": len(clusters), "cluster": cluster["teaching_term"]}), flush=True)
        if args.limit and count >= args.limit:
            break
    return 0


def command_validate(args: argparse.Namespace) -> int:
    """Materialize and audit the current candidate revision without accepting it."""
    clusters = load_jsonl(OUTPUT / "duplicate-clusters.jsonl")
    cluster_by_id = {row["cluster_id"]: row for row in clusters}
    gemma_rows = load_jsonl(OUTPUT / "gemma-proposals.jsonl", tolerate_partial_tail=True)
    deepseek_rows = load_jsonl(OUTPUT / "deepseek-proposals.jsonl", tolerate_partial_tail=True)
    proposals_by_cluster = {row["cluster_id"]: row for row in gemma_rows}
    overlapping_reviews = sorted(set(proposals_by_cluster) & {row["cluster_id"] for row in deepseek_rows})
    proposals_by_cluster.update({
        row["cluster_id"]: row for row in deepseek_rows if row["cluster_id"] not in proposals_by_cluster
    })

    missing_clusters = sorted(set(cluster_by_id) - set(proposals_by_cluster))
    unexpected_clusters = sorted(set(proposals_by_cluster) - set(cluster_by_id))
    proposal_by_source: dict[str, dict[str, Any]] = {}
    structural_errors: list[dict[str, Any]] = []
    low_confidence: list[dict[str, Any]] = []
    reclaimed: list[dict[str, Any]] = []

    for cid, proposal in proposals_by_cluster.items():
        cluster = cluster_by_id.get(cid)
        if cluster is None:
            continue
        try:
            validate_proposal(cluster, proposal)
        except Exception as exc:
            structural_errors.append({"cluster_id": cid, "error": str(exc)})
            continue
        keep_count = sum(row.get("action") == "KEEP" for row in proposal["proposals"])
        if keep_count < 1:
            structural_errors.append({
                "cluster_id": cid,
                "error": "expected at least one KEEP proposal",
            })
        for row in proposal["proposals"]:
            source_id = row["source_concept_id"]
            if source_id in proposal_by_source:
                structural_errors.append({
                    "cluster_id": cid,
                    "source_concept_id": source_id,
                    "error": "source concept received more than one duplicate-cluster proposal",
                })
            proposal_by_source[source_id] = row
            if row.get("confidence") != "high":
                low_confidence.append({"cluster_id": cid, **row})
            if row.get("action") == "RECLAIM_FOR_MISSING_VOCABULARY":
                reclaimed.append({"cluster_id": cid, **row, "same_image_grade": "C"})

    candidates: list[dict[str, Any]] = []
    source_ids: list[str] = []
    for original in virtual_rows():
        source_id = original["source"]["concept_id"]
        source_ids.append(source_id)
        candidate = {**original, "candidate_revision": None}
        proposal = proposal_by_source.get(source_id)
        if proposal:
            normalized_proposal = dict(proposal)
            if normalized_proposal.get("action") == "RECLAIM_FOR_MISSING_VOCABULARY":
                normalized_proposal.update({
                    "teaching_term": "",
                    "teaching_sense": "",
                    "part_of_speech": "",
                    "same_image_grade": "C",
                })
            candidate["candidate_revision"] = normalized_proposal
        candidates.append(candidate)

    duplicate_source_ids = sorted(
        source_id for source_id, count in Counter(source_ids).items() if count != 1
    )
    terms: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        proposal = row["candidate_revision"]
        if proposal:
            term = proposal.get("teaching_term", "")
        else:
            term = row["mapping"].get("teaching_term", "")
        if normalized(str(term)):
            terms[normalized(str(term))].append({
                "source_concept_id": row["source"]["concept_id"],
                "teaching_term": term,
                "revision": proposal,
            })
    collisions = []
    for term, members in sorted(terms.items()):
        if len(members) < 2:
            continue
        revised_parts = [
            normalized(str(member["revision"].get("part_of_speech", "")))
            for member in members
            if member["revision"]
        ]
        intentional_cross_pos = (
            len(revised_parts) == len(members)
            and all(revised_parts)
            and len(revised_parts) == len(set(revised_parts))
        )
        if not intentional_cross_pos:
            collisions.append({"normalized_term": term, "members": members})

    write_jsonl(OUTPUT / "candidate-lexicon.jsonl", candidates)
    write_jsonl(OUTPUT / "global-collisions.jsonl", collisions)
    write_jsonl(OUTPUT / "reclaimed-slots.jsonl", reclaimed)
    write_jsonl(OUTPUT / "low-confidence-proposals.jsonl", low_confidence)
    write_jsonl(OUTPUT / "structural-errors.jsonl", structural_errors)
    summary = {
        "schema_version": SCHEMA,
        "created_at": now(),
        "expected_clusters": len(clusters),
        "completed_clusters": len(set(proposals_by_cluster) & set(cluster_by_id)),
        "missing_clusters": len(missing_clusters),
        "unexpected_clusters": len(unexpected_clusters),
        "overlapping_independent_reviews": len(overlapping_reviews),
        "lexicon_rows": len(candidates),
        "duplicate_source_ids": duplicate_source_ids,
        "global_term_collisions": len(collisions),
        "reclaimed_slots": len(reclaimed),
        "low_confidence_proposals": len(low_confidence),
        "structural_errors": len(structural_errors),
        "ready_for_human_and_luna_review": not any([
            missing_clusters,
            unexpected_clusters,
            duplicate_source_ids,
            collisions,
            reclaimed,
            low_confidence,
            structural_errors,
        ]),
    }
    write_json(OUTPUT / "validation-summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.require_complete and not summary["ready_for_human_and_luna_review"]:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    inventory = sub.add_parser("inventory")
    inventory.set_defaults(func=command_inventory)
    gemma = sub.add_parser("gemma")
    gemma.add_argument("--limit", type=int, default=0)
    gemma.set_defaults(func=command_gemma)
    deepseek = sub.add_parser("deepseek")
    deepseek.add_argument("--limit", type=int, default=0)
    deepseek.set_defaults(func=command_deepseek)
    validate = sub.add_parser("validate")
    validate.add_argument("--require-complete", action="store_true")
    validate.set_defaults(func=command_validate)
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
