"""Discover and apply obvious lexical dependencies to Campaign 36.

The source layer is immutable.  This module asks Luna to distinguish genuine
compound/phrase/derivational components from accidental string splits, records
components absent from the curriculum, and emits a stable topological order in
a new versioned layer while keeping every contract's ten images attached.
"""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import itertools
import csv
import io
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable


LABEL_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/infinitive-label-v1"
)
DEFAULT_CONTRACTS = LABEL_ROOT / "teaching-contracts.jsonl"
DEFAULT_MANIFEST = LABEL_ROOT / "remediation-generation-v1/reconciliation-v1/accepted-assets.jsonl"
DEFAULT_OUTPUT = LABEL_ROOT / "dependency-order-v1"
DEFAULT_CODEX = Path("/home/aomukai/.local/bin/codex")
DEFAULT_REPORT_DIR = Path("/home/aomukai/Documents/Codex/2026-08-24/he/outputs")
SCHEMA_VERSION = "ninereeds_campaign36_dependency_order_v1"
RELATIONS = ("compound_component", "phrase_content_word", "derivational_base")
STOPWORDS = {
    "a", "an", "and", "at", "by", "for", "from", "in", "of", "on", "or",
    "the", "to", "with",
}
PREFIXES = ("anti", "counter", "dis", "inter", "mis", "non", "over", "pre", "re", "sub", "super", "un", "under")
SUFFIXES = ("ability", "ibility", "ation", "ition", "ment", "ness", "less", "ful", "able", "ible", "ship", "hood", "ward", "wise", "ing", "ed", "er", "or", "ly", "al", "ic", "y")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def atomic_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    temporary.replace(path)


def normalized(value: str) -> str:
    value = value.casefold().strip()
    if value.startswith("to "):
        value = value[3:]
    value = re.sub(r"\s*\([^)]*\)\s*", " ", value)
    value = re.sub(r"[^a-z0-9'-]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def surface_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold().strip())


def exposure_index(row: dict[str, Any]) -> int:
    if row.get("exposure_index") is not None:
        return int(row["exposure_index"])
    match = re.fullmatch(r"c\d{4}-i(\d{2})", str(row.get("slot_id", "")))
    if not match:
        raise ValueError(f"asset lacks a usable exposure index: {row.get('slot_id')}")
    return int(match.group(1))


def dictionary_words(paths: list[Path]) -> set[str]:
    result: set[str] = set()
    for path in paths:
        if not path.is_file():
            continue
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            word = line.casefold().removesuffix("'s")
            if re.fullmatch(r"[a-z]+", word):
                result.add(word)
    return result


def stem_options(word: str, known: set[str], words: set[str]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for prefix in PREFIXES:
        if word.startswith(prefix) and len(word) - len(prefix) >= 3:
            stem = word[len(prefix):]
            if stem in known or stem in words:
                options.append({"analysis": "prefix", "component": stem})
    for suffix in SUFFIXES:
        if not word.endswith(suffix) or len(word) - len(suffix) < 3:
            continue
        raw = word[:-len(suffix)]
        variants = {raw, raw + "e"}
        if raw.endswith("i"):
            variants.add(raw[:-1] + "y")
        if len(raw) >= 2 and raw[-1] == raw[-2]:
            variants.add(raw[:-1])
        for stem in sorted(variants):
            if stem in known or stem in words:
                options.append({"analysis": "suffix", "component": stem})
    return options


def candidate_rows(contracts: list[dict[str, Any]], words: set[str]) -> list[dict[str, Any]]:
    known = {normalized(row["display_label"]) for row in contracts}
    candidates: list[dict[str, Any]] = []
    for row in contracts:
        label = normalized(row["display_label"])
        tokens = [part for part in re.findall(r"[a-z]+", label) if part not in STOPWORDS]
        analyses: list[Any] = []
        if len(tokens) > 1:
            analyses.append({"analysis": "phrase_tokens", "components": tokens})
        if len(tokens) == 1:
            word = tokens[0]
            for index in range(2, len(word) - 1):
                left, right = word[:index], word[index:]
                if (left in known or left in words) and (right in known or right in words):
                    analyses.append({"analysis": "closed_split", "components": [left, right]})
            analyses.extend(stem_options(word, known, words))
        if not analyses:
            continue
        # Deduplicate noisy dictionary-derived analyses without losing their order.
        seen: set[str] = set()
        unique = []
        for analysis in analyses:
            key = json.dumps(analysis, sort_keys=True)
            if key not in seen:
                seen.add(key)
                unique.append(analysis)
        candidates.append({
            "concept_id": row["concept_id"],
            "original_ordinal": int(row["ordinal"]),
            "display_label": row["display_label"],
            "lemma": row["lemma"],
            "part_of_speech": row["part_of_speech"],
            "teaching_sense": row["teaching_sense"],
            "candidate_analyses": unique,
        })
    return candidates


def review_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array", "minItems": count, "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "concept_id": {"type": "string"},
                        "is_lexically_composite": {"type": "boolean"},
                        "dependencies": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "component": {"type": "string", "minLength": 1},
                                    "relation": {"type": "string", "enum": list(RELATIONS)},
                                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                                    "rationale": {"type": "string", "minLength": 1},
                                },
                                "required": ["component", "relation", "confidence", "rationale"],
                                "additionalProperties": False,
                            },
                        },
                        "rationale": {"type": "string", "minLength": 1},
                    },
                    "required": ["concept_id", "is_lexically_composite", "dependencies", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["decisions"],
        "additionalProperties": False,
    }


def review_prompt(batch: list[dict[str, Any]]) -> str:
    return """You are auditing lexical teaching order for an image-grounded English curriculum.

For every supplied target, decide whether its INTENDED SENSE is transparently built from simpler
English lexical components that should obviously be taught first. Accept only:
- genuine closed compounds (dog + house -> doghouse),
- content words in open or hyphenated compounds/phrases,
- a transparent derivational base (read -> readable; readable -> unreadable).

Reject accidental substrings and etymology that is not synchronically obvious: office is not
off + ice, strawberry is not straw + berry in its ordinary fruit meaning unless a component
actually helps a learner interpret the compound, and understand is not under + stand. Do not add
hypernyms, world knowledge, conceptual associations, grammatical function words, articles, or
general definitions. Normalize components to a standalone lowercase dictionary form; use the
base verb without 'to'. If a real component is absent from the curriculum it must still be named.
Prefer the immediate transparent component, but include a deeper lexical base too when it is also
plainly useful. An item may have zero dependencies. Return every concept_id exactly once.

Candidate analyses are deliberately over-inclusive mechanical hints, not claims. The intended
sense is authoritative.

ITEMS:\n""" + json.dumps(batch, ensure_ascii=False)


def component_forms(component: str) -> set[str]:
    word = normalized(component)
    forms = {word}
    if " " in word:
        return forms
    irregular = {"wooden": "wood", "sports": "sport", "clothes": "clothing"}
    if word in irregular:
        forms.add(irregular[word])
    if word.endswith("ies") and len(word) > 4:
        forms.add(word[:-3] + "y")
    if word.endswith("es") and len(word) > 4:
        forms.add(word[:-2])
    if word.endswith("s") and len(word) > 3:
        forms.add(word[:-1])
    for suffix in ("ing", "ed", "er", "or"):
        if not word.endswith(suffix) or len(word) - len(suffix) < 3:
            continue
        raw = word[:-len(suffix)]
        forms.update({raw, raw + "e"})
        if len(raw) >= 2 and raw[-1] == raw[-2]:
            forms.add(raw[:-1])
    return {form for form in forms if form}


def resolution_claims(
    contracts: list[dict[str, Any]], bound_decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    aliases: dict[str, list[dict[str, Any]]] = {}
    for row in contracts:
        for form in component_forms(row["display_label"]) | component_forms(row["lemma"]):
            aliases.setdefault(form, []).append(row)
    claims = []
    for decision in bound_decisions:
        for index, dependency in enumerate(decision["dependencies"], 1):
            candidates: dict[int, dict[str, Any]] = {}
            for form in component_forms(dependency["component"]):
                for row in aliases.get(form, []):
                    ordinal = int(row["ordinal"])
                    if f"source-c{ordinal:04d}" != decision["contract_id"]:
                        candidates[ordinal] = row
            claims.append({
                "claim_id": f"{decision['contract_id']}-d{index:02d}",
                "target_contract_id": decision["contract_id"],
                "target_concept_id": decision["concept_id"],
                "target_display_label": decision["target_display_label"],
                "target_original_ordinal": decision["target_original_ordinal"],
                "target_teaching_sense": next(
                    row["teaching_sense"] for row in contracts
                    if int(row["ordinal"]) == int(decision["target_original_ordinal"])
                ),
                **dependency,
                "candidate_contracts": [{
                    "contract_id": f"source-c{ordinal:04d}",
                    "display_label": row["display_label"],
                    "part_of_speech": row["part_of_speech"],
                    "teaching_sense": row["teaching_sense"],
                } for ordinal, row in sorted(candidates.items())],
            })
    return claims


def resolution_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array", "minItems": count, "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "claim_id": {"type": "string"},
                        "resolution": {"type": "string", "enum": ["present", "absent", "reject_dependency"]},
                        "matched_contract_id": {"type": "string"},
                        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                        "rationale": {"type": "string", "minLength": 1},
                    },
                    "required": ["claim_id", "resolution", "matched_contract_id", "confidence", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["decisions"], "additionalProperties": False,
    }


def resolution_prompt(batch: list[dict[str, Any]]) -> str:
    return """You are the final sense-aware resolver for lexical teaching dependencies.

For each claim, choose exactly one:
- present: the dependency is genuine and exactly one candidate contract teaches the required
  lexical component in the right part of speech and sense;
- absent: the dependency is genuine, but no candidate contract teaches that component sense;
- reject_dependency: the proposed component is accidental, etymological rather than obvious,
  semantically unhelpful for the intended target, or otherwise should not constrain teaching order.

Surface spelling is insufficient. For painter, the verb sense 'to paint' is the derivational base,
not the paint material. For fingernail, a metal-fastener noun 'nail' and a fastening verb 'to nail'
do not teach the body-part component, so that component is absent. For driftwood, choose the motion
sense of drift, not a snow-drift noun. Use present only with a candidate contract_id supplied in the
claim. For absent or reject_dependency, matched_contract_id must be an empty string. Judge the
intended senses, not images or etymological trivia. Return every claim_id exactly once.

CLAIMS:\n""" + json.dumps(batch, ensure_ascii=False)


def run_resolution_batch(batch: list[dict[str, Any]], *, index: int, output: Path, codex: Path, model: str, timeout: int) -> list[dict[str, Any]]:
    final_path = output / "resolution-batches" / f"batch-{index:04d}.json"
    if final_path.is_file():
        return json.loads(final_path.read_text(encoding="utf-8"))["decisions"]
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="campaign36-dependency-resolution-") as raw:
        temporary = Path(raw)
        schema_path, result_path = temporary / "schema.json", temporary / "result.json"
        schema_path.write_text(json.dumps(resolution_schema(len(batch)), sort_keys=True), encoding="utf-8")
        completed = subprocess.run([
            str(codex), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(temporary),
            "--model", model, "--output-schema", str(schema_path),
            "--output-last-message", str(result_path), "--color", "never", "-",
        ], input=resolution_prompt(batch), text=True, capture_output=True, timeout=timeout, check=False)
        if completed.returncode != 0 or not result_path.is_file():
            raise RuntimeError(f"Luna resolution batch {index} failed: {completed.stderr[-2000:]}")
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    claims = {row["claim_id"]: row for row in batch}
    actual = [row.get("claim_id") for row in payload.get("decisions", [])]
    if len(actual) != len(claims) or set(actual) != set(claims):
        raise ValueError(f"resolution batch {index} did not return every claim exactly once")
    for decision in payload["decisions"]:
        allowed = {row["contract_id"] for row in claims[decision["claim_id"]]["candidate_contracts"]}
        if decision["resolution"] == "present" and decision["matched_contract_id"] not in allowed:
            raise ValueError(f"invalid matched contract for {decision['claim_id']}")
        if decision["resolution"] != "present" and decision["matched_contract_id"]:
            raise ValueError(f"non-present claim has a match for {decision['claim_id']}")
    atomic_json(final_path, {"schema_version": SCHEMA_VERSION, "model": model, **payload})
    return payload["decisions"]


def run_luna_batch(batch: list[dict[str, Any]], *, index: int, output: Path, codex: Path, model: str, timeout: int) -> list[dict[str, Any]]:
    final_path = output / "batches" / f"batch-{index:04d}.json"
    if final_path.is_file():
        payload = json.loads(final_path.read_text(encoding="utf-8"))
        return payload["decisions"]
    final_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="campaign36-dependency-luna-") as raw:
        temporary = Path(raw)
        schema_path = temporary / "schema.json"
        result_path = temporary / "result.json"
        schema_path.write_text(json.dumps(review_schema(len(batch)), sort_keys=True), encoding="utf-8")
        completed = subprocess.run([
            str(codex), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(temporary),
            "--model", model, "--output-schema", str(schema_path),
            "--output-last-message", str(result_path), "--color", "never", "-",
        ], input=review_prompt(batch), text=True, capture_output=True, timeout=timeout, check=False)
        if completed.returncode != 0 or not result_path.is_file():
            raise RuntimeError(f"Luna batch {index} failed: {completed.stderr[-2000:]}")
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    expected = [row["concept_id"] for row in batch]
    actual = [row.get("concept_id") for row in payload.get("decisions", [])]
    if len(actual) != len(expected) or set(actual) != set(expected):
        raise ValueError(f"Luna batch {index} did not return every concept exactly once")
    for decision in payload["decisions"]:
        decision["dependencies"] = [{**dep, "component": normalized(dep["component"])} for dep in decision["dependencies"]]
        # The dependency list is the substantive structured judgment.  Treat the
        # summary boolean as derived so a harmless Luna inconsistency cannot
        # invalidate an otherwise complete batch.
        decision["is_lexically_composite"] = bool(decision["dependencies"])
    atomic_json(final_path, {"schema_version": SCHEMA_VERSION, "model": model, **payload})
    return payload["decisions"]


def stable_topological_order(contracts: list[dict[str, Any]], edges: list[dict[str, Any]]) -> list[str]:
    key_for = lambda row: str(row.get("contract_id") or row["concept_id"])
    original = {key_for(row): int(row["ordinal"]) for row in contracts}
    outgoing: dict[str, set[str]] = {key: set() for key in original}
    indegree = {key: 0 for key in original}
    for edge in edges:
        before = str(edge.get("dependency_contract_id") or edge["dependency_concept_id"])
        after = str(edge.get("target_contract_id") or edge["target_concept_id"])
        if after not in outgoing[before]:
            outgoing[before].add(after)
            indegree[after] += 1
    ready = sorted((key for key, degree in indegree.items() if degree == 0), key=original.get)
    result: list[str] = []
    while ready:
        current = ready.pop(0)
        result.append(current)
        for target in sorted(outgoing[current], key=original.get):
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
                ready.sort(key=original.get)
    if len(result) != len(contracts):
        cyclic = sorted((key for key, degree in indegree.items() if degree), key=original.get)
        raise ValueError(f"dependency graph contains a cycle: {cyclic[:20]}")
    return result


def bind_decisions_to_contracts(
    candidates: list[dict[str, Any]], decisions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Bind legacy concept-keyed Luna rows to unique source-contract ordinals.

    Five inherited concept IDs are duplicated. Candidate component overlap
    disambiguates the meaningful cases; tied zero-dependency decisions are
    interchangeable and fall back to source order.
    """
    candidates_by_id: dict[str, list[dict[str, Any]]] = {}
    decisions_by_id: dict[str, list[dict[str, Any]]] = {}
    for row in candidates:
        candidates_by_id.setdefault(row["concept_id"], []).append(row)
    for row in decisions:
        decisions_by_id.setdefault(row["concept_id"], []).append(row)
    bound: list[dict[str, Any]] = []
    for concept_id, candidate_group in candidates_by_id.items():
        decision_group = decisions_by_id.get(concept_id, [])
        if len(candidate_group) != len(decision_group):
            raise ValueError(
                f"candidate/decision count differs for {concept_id}: "
                f"{len(candidate_group)} != {len(decision_group)}"
            )
        candidate_group.sort(key=lambda row: int(row["original_ordinal"]))

        def hints(candidate: dict[str, Any]) -> set[str]:
            result: set[str] = set()
            for analysis in candidate["candidate_analyses"]:
                if analysis.get("component"):
                    result.add(normalized(analysis["component"]))
                result.update(normalized(value) for value in analysis.get("components", []))
            return result

        best = None
        for permutation in itertools.permutations(decision_group):
            score = sum(
                len(hints(candidate) & {normalized(dep["component"]) for dep in decision["dependencies"]})
                for candidate, decision in zip(candidate_group, permutation)
            )
            if best is None or score > best[0]:
                best = (score, permutation)
        assert best is not None
        for candidate, decision in zip(candidate_group, best[1]):
            ordinal = int(candidate["original_ordinal"])
            bound.append({
                **decision,
                "contract_id": f"source-c{ordinal:04d}",
                "target_original_ordinal": ordinal,
                "target_display_label": candidate["display_label"],
            })
    bound.sort(key=lambda row: row["target_original_ordinal"])
    return bound


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.contracts)
    candidates = candidate_rows(contracts, dictionary_words(args.dictionary))
    atomic_jsonl(args.output / "candidates.jsonl", candidates)
    summary = {"contracts": len(contracts), "candidate_targets": len(candidates), "created_at": now()}
    atomic_json(args.output / "prepare-summary.json", summary)
    return summary


def review(args: argparse.Namespace) -> dict[str, Any]:
    candidates_path = args.output / "candidates.jsonl"
    if not candidates_path.is_file():
        prepare(args)
    candidates = load_jsonl(candidates_path)
    batches = [candidates[index:index + args.batch_size] for index in range(0, len(candidates), args.batch_size)]
    decisions: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_luna_batch, batch, index=index, output=args.output, codex=args.codex, model=args.model, timeout=args.timeout): index
            for index, batch in enumerate(batches, 1)
        }
        for future in as_completed(futures):
            decisions.extend(future.result())
            print(f"completed Luna batch {futures[future]}/{len(batches)}", flush=True)
    ordinal = {row["concept_id"]: row["original_ordinal"] for row in candidates}
    decisions.sort(key=lambda row: ordinal[row["concept_id"]])
    atomic_jsonl(args.output / "luna-decisions.jsonl", decisions)
    summary = {
        "candidate_targets": len(candidates), "reviewed_targets": len(decisions),
        "composite_targets": sum(row["is_lexically_composite"] for row in decisions),
        "dependencies_named": sum(len(row["dependencies"]) for row in decisions),
        "model": args.model, "created_at": now(),
    }
    atomic_json(args.output / "review-summary.json", summary)
    return summary


def resolve(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.contracts)
    candidates = load_jsonl(args.output / "candidates.jsonl")
    bound = bind_decisions_to_contracts(
        candidates, load_jsonl(args.output / "luna-decisions.jsonl")
    )
    atomic_jsonl(args.output / "luna-decisions-bound.jsonl", bound)
    claims = resolution_claims(contracts, bound)
    atomic_jsonl(args.output / "dependency-claims.jsonl", claims)
    batches = [claims[index:index + args.batch_size] for index in range(0, len(claims), args.batch_size)]
    decisions: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(
                run_resolution_batch, batch, index=index, output=args.output,
                codex=args.codex, model=args.model, timeout=args.timeout,
            ): index
            for index, batch in enumerate(batches, 1)
        }
        for future in as_completed(futures):
            decisions.extend(future.result())
            print(f"completed Luna resolution batch {futures[future]}/{len(batches)}", flush=True)
    claim_order = {row["claim_id"]: index for index, row in enumerate(claims)}
    decisions.sort(key=lambda row: claim_order[row["claim_id"]])
    atomic_jsonl(args.output / "resolved-dependencies.jsonl", decisions)
    counts: dict[str, int] = {}
    for row in decisions:
        counts[row["resolution"]] = counts.get(row["resolution"], 0) + 1
    summary = {
        "claims": len(claims), "decisions": len(decisions), "resolution_counts": counts,
        "non_high_confidence": sum(row["confidence"] != "high" for row in decisions),
        "model": args.model, "created_at": now(),
    }
    atomic_json(args.output / "resolution-summary.json", summary)
    return summary


def adjudicate(args: argparse.Namespace) -> dict[str, Any]:
    claims = {row["claim_id"]: row for row in load_jsonl(args.output / "dependency-claims.jsonl")}
    prior = load_jsonl(args.output / "resolved-dependencies.jsonl")
    uncertain = [row for row in prior if row["confidence"] != "high"]
    adjudication_items = [{
        **claims[row["claim_id"]],
        "prior_resolution": row["resolution"],
        "prior_matched_contract_id": row["matched_contract_id"],
        "prior_rationale": row["rationale"],
        "adjudication_instruction": (
            "Independently resolve the prior medium-confidence judgment. Prefer reject_dependency "
            "over a speculative edge; use absent when the lexical dependency is real but its exact "
            "sense is not taught; use present only for an exact sense match."
        ),
    } for row in uncertain]
    batches = [adjudication_items[index:index + args.batch_size] for index in range(0, len(adjudication_items), args.batch_size)]
    adjudicated: list[dict[str, Any]] = []
    existing_rounds = sorted(args.output.glob("adjudication-v[0-9]*"))
    adjudication_root = args.output / f"adjudication-v{len(existing_rounds) + 1}"
    with ThreadPoolExecutor(max_workers=min(args.workers, max(1, len(batches)))) as executor:
        futures = {
            executor.submit(
                run_resolution_batch, batch, index=index, output=adjudication_root,
                codex=args.codex, model=args.model, timeout=args.timeout,
            ): index
            for index, batch in enumerate(batches, 1)
        }
        for future in as_completed(futures):
            adjudicated.extend(future.result())
            print(f"completed Luna adjudication batch {futures[future]}/{len(batches)}", flush=True)
    replacements = {row["claim_id"]: row for row in adjudicated}
    merged = [replacements.get(row["claim_id"], row) for row in prior]
    atomic_jsonl(args.output / "resolved-dependencies.jsonl", merged)
    summary = {
        "adjudicated": len(adjudicated),
        "remaining_non_high_confidence": sum(row["confidence"] != "high" for row in merged),
        "changed_resolution": sum(
            replacements[row["claim_id"]]["resolution"] != row["resolution"]
            for row in uncertain
        ),
        "created_at": now(), "model": args.model,
    }
    atomic_json(args.output / "adjudication-summary.json", summary)
    return summary


def build(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.contracts)
    manifest = load_jsonl(args.manifest)
    claims = {row["claim_id"]: row for row in load_jsonl(args.output / "dependency-claims.jsonl")}
    decisions = load_jsonl(args.output / "resolved-dependencies.jsonl")
    if len(contracts) != 2500 or len(manifest) != 25000:
        raise ValueError("expected exactly 2,500 contracts and 25,000 assets")
    contract_by_key = {int(row["ordinal"]): row for row in contracts}
    edges: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    uncertain: list[dict[str, Any]] = []
    for resolution in decisions:
        claim = claims[resolution["claim_id"]]
        resolved = {**claim, **resolution, "resolver_rationale": resolution["rationale"]}
        if resolution["confidence"] != "high":
            uncertain.append(resolved)
        if resolution["resolution"] == "reject_dependency":
            rejected.append(resolved)
            continue
        target_ordinal = int(claim["target_original_ordinal"])
        target = contract_by_key[target_ordinal]
        base = {
            "claim_id": claim["claim_id"], "target_contract_id": claim["target_contract_id"],
            "target_concept_id": target["concept_id"], "target_display_label": target["display_label"],
            "target_original_ordinal": target_ordinal, "component": claim["component"],
            "relation": claim["relation"], "confidence": resolution["confidence"],
            "rationale": resolution["rationale"],
        }
        if resolution["resolution"] == "present":
            match_contract_id = resolution["matched_contract_id"]
            match_ordinal = int(match_contract_id.removeprefix("source-c"))
            match = contract_by_key[match_ordinal]
            edges.append({
                **base, "dependency_contract_id": match_contract_id,
                "dependency_concept_id": match["concept_id"],
                "dependency_display_label": match["display_label"],
                "dependency_original_ordinal": match_ordinal,
            })
        else:
            missing.append({**base, "candidate_contracts_reviewed": claim["candidate_contracts"]})
    edge_key = lambda row: (row["dependency_contract_id"], row["target_contract_id"])
    edges = list({edge_key(row): row for row in edges}.values())
    edges.sort(key=lambda row: (row["target_original_ordinal"], row["dependency_original_ordinal"]))
    missing.sort(key=lambda row: (row["target_original_ordinal"], row["component"]))
    graph_contracts = [
        {**row, "contract_id": f"source-c{int(row['ordinal']):04d}"} for row in contracts
    ]
    order = stable_topological_order(graph_contracts, edges)
    new_ordinal = {contract_id: index for index, contract_id in enumerate(order, 1)}
    deps_by_target: dict[str, list[str]] = {}
    missing_by_target: dict[str, list[str]] = {}
    for edge in edges:
        deps_by_target.setdefault(edge["target_contract_id"], []).append(edge["dependency_contract_id"])
    for row in missing:
        missing_by_target.setdefault(row["target_contract_id"], []).append(row["component"])
    ordered_contracts = []
    for contract_id in order:
        source_ordinal = int(contract_id.removeprefix("source-c"))
        row = contract_by_key[source_ordinal]
        ordered_contracts.append({
            **row, "schema_version": SCHEMA_VERSION, "contract_id": contract_id,
            "source_ordinal": source_ordinal, "ordinal": new_ordinal[contract_id],
            "depends_on": sorted(set(deps_by_target.get(contract_id, [])), key=new_ordinal.get),
            "missing_dependencies": sorted(set(missing_by_target.get(contract_id, []))),
        })
    assets_by_ordinal: dict[int, list[dict[str, Any]]] = {}
    for asset in manifest:
        assets_by_ordinal.setdefault(int(asset["ordinal"]), []).append(asset)
    ordered_assets = []
    for contract_id in order:
        source_ordinal = int(contract_id.removeprefix("source-c"))
        assets = sorted(assets_by_ordinal[source_ordinal], key=exposure_index)
        if len(assets) != 10:
            raise ValueError(f"{contract_id} has {len(assets)} images, expected 10")
        ordinal = new_ordinal[contract_id]
        for exposure, asset in enumerate(assets, 1):
            ordered_assets.append({
                **asset, "schema_version": SCHEMA_VERSION, "contract_id": contract_id,
                "source_ordinal": source_ordinal, "source_slot_id": asset["slot_id"],
                "ordinal": ordinal, "slot_id": f"c{ordinal:04d}-i{exposure:02d}",
                "sequence_position": (ordinal - 1) * 10 + exposure,
                "depends_on": sorted(set(deps_by_target.get(contract_id, [])), key=new_ordinal.get),
                "missing_dependencies": sorted(set(missing_by_target.get(contract_id, []))),
            })
    if len({row["slot_id"] for row in ordered_assets}) != 25000:
        raise ValueError("reordered manifest does not have 25,000 unique slots")
    for edge in edges:
        if new_ordinal[edge["dependency_contract_id"]] >= new_ordinal[edge["target_contract_id"]]:
            raise ValueError(f"unsatisfied dependency edge: {edge}")
    atomic_jsonl(args.output / "dependency-edges.jsonl", edges)
    atomic_jsonl(args.output / "missing-prerequisites.jsonl", missing)
    atomic_jsonl(args.output / "rejected-dependency-claims.jsonl", rejected)
    atomic_jsonl(args.output / "uncertain-resolution-review.jsonl", uncertain)
    atomic_jsonl(args.output / "teaching-contracts.jsonl", ordered_contracts)
    atomic_jsonl(args.output / "accepted-assets.jsonl", ordered_assets)
    moved = sum(new_ordinal[f"source-c{int(row['ordinal']):04d}"] != int(row["ordinal"]) for row in contracts)
    violations_before = sum(row["dependency_original_ordinal"] >= row["target_original_ordinal"] for row in edges)
    summary = {
        "schema_version": SCHEMA_VERSION, "created_at": now(), "contracts": len(ordered_contracts),
        "assets": len(ordered_assets), "dependency_edges": len(edges),
        "targets_with_dependencies": len(deps_by_target), "missing_prerequisites": len(missing),
        "targets_with_missing_prerequisites": len(missing_by_target),
        "rejected_dependency_claims": len(rejected),
        "non_high_confidence_resolutions": len(uncertain),
        "dependency_violations_before": violations_before, "dependency_violations_after": 0,
        "contracts_moved": moved, "images_per_contract_min": 10, "images_per_contract_max": 10,
        "training_ready_with_respect_to_present_dependencies": True,
    }
    atomic_json(args.output / "summary.json", summary)
    return summary


def validate(args: argparse.Namespace) -> dict[str, Any]:
    source_assets = load_jsonl(args.manifest)
    contracts = load_jsonl(args.output / "teaching-contracts.jsonl")
    assets = load_jsonl(args.output / "accepted-assets.jsonl")
    edges = load_jsonl(args.output / "dependency-edges.jsonl")
    missing = load_jsonl(args.output / "missing-prerequisites.jsonl")
    resolutions = load_jsonl(args.output / "resolved-dependencies.jsonl")
    if len(contracts) != 2500 or len(assets) != 25000:
        raise ValueError("wrong contract or asset count")
    if [row["ordinal"] for row in contracts] != list(range(1, 2501)):
        raise ValueError("contract ordinals are not contiguous")
    if len({row["contract_id"] for row in contracts}) != 2500:
        raise ValueError("contract IDs are not unique")
    if len({surface_key(row["display_label"]) for row in contracts}) != 2500:
        raise ValueError("display labels are not unique")
    contract_order = {row["contract_id"]: int(row["ordinal"]) for row in contracts}
    counts = Counter(row["contract_id"] for row in assets)
    if set(counts.values()) != {10} or len(counts) != 2500:
        raise ValueError("not every contract has exactly ten images")
    if [int(row["sequence_position"]) for row in assets] != list(range(1, 25001)):
        raise ValueError("asset sequence positions are not contiguous")
    if len({row["slot_id"] for row in assets}) != 25000:
        raise ValueError("slot IDs are not unique")
    source = {row["slot_id"]: row for row in source_assets}
    for row in assets:
        original = source[row["source_slot_id"]]
        if row["local_path"] != original["local_path"]:
            raise ValueError(f"asset path changed for {row['source_slot_id']}")
        if (row.get("sha256") or row.get("asset_sha256")) != (original.get("sha256") or original.get("asset_sha256")):
            raise ValueError(f"asset hash changed for {row['source_slot_id']}")
        expected_slot = f"c{int(row['ordinal']):04d}-i{exposure_index(row):02d}"
        if row["slot_id"] != expected_slot:
            raise ValueError(f"slot/ordinal mismatch: {row['slot_id']}")
    for edge in edges:
        if contract_order[edge["dependency_contract_id"]] >= contract_order[edge["target_contract_id"]]:
            raise ValueError(f"dependency order violation: {edge['claim_id']}")
    hashes = Counter(str(row.get("sha256") or row.get("asset_sha256")) for row in assets)
    hashes.pop("", None)
    if max(hashes.values(), default=0) > 4:
        raise ValueError("image reuse cap exceeded")
    if any(row["confidence"] != "high" for row in resolutions):
        raise ValueError("non-high-confidence resolution remains")
    result = {
        "schema_version": SCHEMA_VERSION, "validated_at": now(), "valid": True,
        "contracts": len(contracts), "assets": len(assets), "images_per_contract": 10,
        "unique_display_labels": len({surface_key(row["display_label"]) for row in contracts}),
        "dependency_edges": len(edges), "dependency_order_violations": 0,
        "missing_prerequisites_reported": len(missing),
        "max_exact_image_reuse": max(hashes.values(), default=0),
        "source_asset_bindings_preserved": True, "non_high_confidence_resolutions": 0,
    }
    atomic_json(args.output / "validation.json", result)
    return result


def csv_text(fieldnames: list[str], rows: list[dict[str, Any]]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue()


def report(args: argparse.Namespace) -> dict[str, Any]:
    summary = json.loads((args.output / "summary.json").read_text(encoding="utf-8"))
    validation = json.loads((args.output / "validation.json").read_text(encoding="utf-8"))
    contracts = {row["contract_id"]: row for row in load_jsonl(args.output / "teaching-contracts.jsonl")}
    missing = load_jsonl(args.output / "missing-prerequisites.jsonl")
    edges = load_jsonl(args.output / "dependency-edges.jsonl")
    rejected = load_jsonl(args.output / "rejected-dependency-claims.jsonl")
    relation_names = {
        "compound_component": "Closed-compound components",
        "phrase_content_word": "Open/hyphenated phrase components",
        "derivational_base": "Transparent derivational bases",
    }
    missing_rows = []
    for row in missing:
        target = contracts[row["target_contract_id"]]
        missing_rows.append({
            "target_new_ordinal": target["ordinal"], "target_source_ordinal": target["source_ordinal"],
            "target_contract_id": row["target_contract_id"], "target_display_label": row["target_display_label"],
            "target_teaching_sense": target["teaching_sense"], "missing_component": row["component"],
            "relation": row["relation"], "reason": row["rationale"],
            "candidate_contracts_reviewed": "; ".join(
                f"{item['contract_id']} {item['display_label']} [{item['part_of_speech']}]: {item['teaching_sense']}"
                for item in row.get("candidate_contracts_reviewed", [])
            ),
        })
    edge_rows = []
    for row in edges:
        target, dependency = contracts[row["target_contract_id"]], contracts[row["dependency_contract_id"]]
        edge_rows.append({
            "dependency_new_ordinal": dependency["ordinal"], "dependency_display_label": dependency["display_label"],
            "target_new_ordinal": target["ordinal"], "target_display_label": target["display_label"],
            "relation": row["relation"], "reason": row["rationale"],
            "dependency_contract_id": row["dependency_contract_id"], "target_contract_id": row["target_contract_id"],
        })
    args.report_dir.mkdir(parents=True, exist_ok=True)
    missing_path = args.report_dir / "campaign36-missing-prerequisites.csv"
    edges_path = args.report_dir / "campaign36-dependency-edges.csv"
    missing_path.write_text(csv_text([
        "target_new_ordinal", "target_source_ordinal", "target_contract_id", "target_display_label",
        "target_teaching_sense", "missing_component", "relation", "reason", "candidate_contracts_reviewed",
    ], missing_rows), encoding="utf-8")
    edges_path.write_text(csv_text([
        "dependency_new_ordinal", "dependency_display_label", "target_new_ordinal", "target_display_label",
        "relation", "reason", "dependency_contract_id", "target_contract_id",
    ], edge_rows), encoding="utf-8")
    missing_counts = Counter(row["relation"] for row in missing)
    edge_counts = Counter(row["relation"] for row in edges)
    missing_targets = {row["target_contract_id"] for row in missing}
    compound_missing = missing_counts["compound_component"] + missing_counts["phrase_content_word"]
    compound_missing_targets = len({
        row["target_contract_id"] for row in missing
        if row["relation"] in {"compound_component", "phrase_content_word"}
    })
    derivational_missing_targets = len({
        row["target_contract_id"] for row in missing if row["relation"] == "derivational_base"
    })
    report_path = args.report_dir / "campaign36-dependency-order-report.md"
    report_path.write_text(f"""# Campaign 36 dependency-order report

**Date:** 2026-08-24
**Status:** Versioned dependency order built and deterministically validated.

## Outcome

- Contracts: **{validation['contracts']:,}**
- Images: **{validation['assets']:,}** — exactly **10 per contract**
- High-confidence present dependency edges: **{summary['dependency_edges']:,}**
- Present-edge violations before reorder: **{summary['dependency_violations_before']:,}**
- Present-edge violations after reorder: **0**
- Genuine missing prerequisite claims: **{summary['missing_prerequisites']:,}** across **{len(missing_targets):,}** targets
- Rejected mechanical/Luna dependency claims: **{len(rejected):,}**
- Unresolved or non-high-confidence decisions: **0**
- Exact display labels: **{validation['unique_display_labels']:,} unique**
- Maximum exact-image reuse: **{validation['max_exact_image_reuse']}**
- Original source-image bindings preserved: **yes**

The reordered manifest uses unique source-contract IDs (`source-c####`) because five inherited
`concept_id` values are reused by different contracts. Every image remains attached to its original
teaching contract; new ordinals, slot IDs, and sequence positions are internally consistent.

## Missing prerequisites

| Kind | Present edges ordered | Missing prerequisite claims |
|---|---:|---:|
| {relation_names['compound_component']} | {edge_counts['compound_component']} | {missing_counts['compound_component']} |
| {relation_names['phrase_content_word']} | {edge_counts['phrase_content_word']} | {missing_counts['phrase_content_word']} |
| {relation_names['derivational_base']} | {edge_counts['derivational_base']} | {missing_counts['derivational_base']} |
| **Total** | **{len(edges)}** | **{len(missing)}** |

There are **{compound_missing}** missing compound/phrase component claims across
**{compound_missing_targets}** targets and **{missing_counts['derivational_base']}** missing
transparent derivational-base claims across **{derivational_missing_targets}** targets. These cannot
be satisfied by reordering because the required lexical sense is absent. They are explicitly carried
as `missing_dependencies` on the affected contracts and image rows.

Sense matching was enforced. For example, `painter` correctly depends on the verb `to paint`, while
the metal-fastener `nail` and fastening verb `to nail` do **not** satisfy the body-part component in
`fingernail` or `toenail`. Those body-part senses are reported as missing.

The complete case-by-case ledger is in `campaign36-missing-prerequisites.csv`. The complete accepted
edge list and final ordinals are in `campaign36-dependency-edges.csv`.

## Authoritative versioned layer

`{args.output}`

Key files:

- `teaching-contracts.jsonl` — reordered contracts with `depends_on` and `missing_dependencies`
- `accepted-assets.jsonl` — the same 25,000 source images, reordered with their contracts
- `dependency-edges.jsonl` — accepted sense-matched edges
- `missing-prerequisites.jsonl` — genuine prerequisites absent in the required sense
- `rejected-dependency-claims.jsonl` — false or unhelpful decompositions
- `validation.json` — deterministic integrity checks
""", encoding="utf-8")
    return {"report": str(report_path), "missing_csv": str(missing_path), "edges_csv": str(edges_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "review", "resolve", "adjudicate", "build", "validate", "report", "all"))
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACTS)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--dictionary", type=Path, nargs="+", default=[Path("/usr/share/dict/american-english"), Path("/usr/share/dict/british-english")])
    parser.add_argument("--codex", type=Path, default=DEFAULT_CODEX)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    args = parser.parse_args()
    if args.command in ("prepare", "all"):
        print(json.dumps(prepare(args), indent=2, sort_keys=True))
    if args.command in ("review", "all"):
        print(json.dumps(review(args), indent=2, sort_keys=True))
    if args.command in ("resolve", "all"):
        print(json.dumps(resolve(args), indent=2, sort_keys=True))
    if args.command in ("adjudicate", "all"):
        print(json.dumps(adjudicate(args), indent=2, sort_keys=True))
    if args.command in ("build", "all"):
        print(json.dumps(build(args), indent=2, sort_keys=True))
    if args.command in ("validate", "all"):
        print(json.dumps(validate(args), indent=2, sort_keys=True))
    if args.command in ("report", "all"):
        print(json.dumps(report(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
