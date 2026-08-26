"""Commission missing Campaign 36 lexical prerequisites by unique sense."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any, Iterable
from collections import Counter
import networkx as nx

from image_registry.campaign36_dependency_order import load_jsonl, atomic_json, atomic_jsonl, surface_key


DEPENDENCY_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/infinitive-label-v1/dependency-order-v1"
)
DEFAULT_MISSING = DEPENDENCY_ROOT / "missing-prerequisites.jsonl"
DEFAULT_CONTRACTS = DEPENDENCY_ROOT / "teaching-contracts.jsonl"
DEFAULT_OUTPUT = DEPENDENCY_ROOT / "prerequisite-commission-v1"
DEFAULT_CODEX = Path("/home/aomukai/.local/bin/codex")
DEFAULT_NEW_FINAL = DEFAULT_OUTPUT / "acquisition-v1/final-v1"
SCHEMA_VERSION = "ninereeds_campaign36_prerequisite_commission_v1"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def lexical_key(value: str) -> str:
    value = value.casefold().strip()
    if value.startswith("to "):
        value = value[3:]
    return re.sub(r"\s+", " ", value)


def make_groups(missing: list[dict[str, Any]], contracts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_component: dict[str, list[dict[str, Any]]] = {}
    for row in missing:
        by_component.setdefault(lexical_key(row["component"]), []).append(row)
    by_lexeme: dict[str, list[dict[str, Any]]] = {}
    for row in contracts:
        by_lexeme.setdefault(lexical_key(row["display_label"]), []).append(row)
    groups = []
    for component, claims in sorted(by_component.items()):
        groups.append({
            "component": component,
            "claims": [{
                "claim_id": row["claim_id"], "target_contract_id": row["target_contract_id"],
                "target_display_label": row["target_display_label"],
                "target_teaching_sense": contracts[int(row["target_original_ordinal"]) - 1]["teaching_sense"],
                "relation": row["relation"], "why_component_is_needed": row["rationale"],
            } for row in claims],
            "existing_same_lexeme_contracts": [{
                "contract_id": row["contract_id"], "display_label": row["display_label"],
                "part_of_speech": row["part_of_speech"], "teaching_sense": row["teaching_sense"],
            } for row in by_lexeme.get(component, [])],
        })
    return groups


def schema(count: int) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "groups": {
                "type": "array", "minItems": count, "maxItems": count,
                "items": {
                    "type": "object",
                    "properties": {
                        "component": {"type": "string"},
                        "claim_decisions": {"type": "array", "items": {
                            "type": "object", "properties": {
                                "claim_id": {"type": "string"},
                                "action": {"type": "string", "enum": ["commission", "reuse_existing", "reject"]},
                                "existing_contract_id": {"type": "string"},
                                "rationale": {"type": "string", "minLength": 1},
                            }, "required": ["claim_id", "action", "existing_contract_id", "rationale"],
                            "additionalProperties": False,
                        }},
                        "commission_contracts": {"type": "array", "items": {
                            "type": "object", "properties": {
                                "sense_key": {"type": "string", "minLength": 1},
                                "display_label": {"type": "string", "minLength": 1},
                                "lemma": {"type": "string", "minLength": 1},
                                "part_of_speech": {"type": "string", "enum": ["noun", "verb", "adjective", "adverb", "phrase", "other"]},
                                "teaching_sense": {"type": "string", "minLength": 1},
                                "visual_contract": {"type": "string", "minLength": 1},
                                "search_terms": {"type": "array", "minItems": 1, "maxItems": 8, "items": {"type": "string", "minLength": 1}},
                                "source_claim_ids": {"type": "array", "minItems": 1, "items": {"type": "string"}},
                            }, "required": ["sense_key", "display_label", "lemma", "part_of_speech", "teaching_sense", "visual_contract", "search_terms", "source_claim_ids"],
                            "additionalProperties": False,
                        }},
                        "rationale": {"type": "string", "minLength": 1},
                    },
                    "required": ["component", "claim_decisions", "commission_contracts", "rationale"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["groups"], "additionalProperties": False,
    }


def prompt(groups: list[dict[str, Any]], occupied_labels: list[str]) -> str:
    return """You are converting missing lexical dependency claims into image-set commissioning contracts.

For each component group, decide every claim:
- reuse_existing when one listed existing contract already teaches the exact required lexical sense;
- reject when the claim is circular, merely morphological without a useful prerequisite, not a
  standalone teachable visual concept, or otherwise should not cause a new ten-image set;
- commission only for a genuinely missing teachable lexical sense.

Merge commission claims that need the same part of speech and sense. Split homographs when senses
differ (for example river bank vs financial bank). Every commissioned contract must have one clear,
visually testable meaning. Verbs must use an infinitive display label beginning with 'to '. Nouns do
not take an article. Prefer a single-word close synonym if the component's ordinary label is already
occupied by a different sense. Use a short phrase only when no clean unique synonym exists. Do not
use parenthetical glosses. Proposed display labels must not duplicate the occupied labels below.
Search terms should retrieve literal visual examples, not abstract associations. The visual_contract
must say exactly what pixels qualify. Every claim_id appears exactly once in claim_decisions; every
commission action appears exactly once among commission_contracts.source_claim_ids; reuse_existing
must name a supplied existing contract; reject/reuse claims must not enter commission contracts.

OCCUPIED DISPLAY LABELS:\n""" + json.dumps(occupied_labels, ensure_ascii=False) + "\n\nGROUPS:\n" + json.dumps(groups, ensure_ascii=False)


def validate_batch_payload(batch: list[dict[str, Any]], payload: dict[str, Any], index: Any) -> None:
    expected = {row["component"]: row for row in batch}
    actual = {row["component"]: row for row in payload.get("groups", [])}
    if set(actual) != set(expected) or len(actual) != len(expected):
        raise ValueError(f"contract batch {index} did not return each group once")
    for component, result in actual.items():
        claim_ids = {row["claim_id"] for row in expected[component]["claims"]}
        decisions = result["claim_decisions"]
        if {row["claim_id"] for row in decisions} != claim_ids or len(decisions) != len(claim_ids):
            raise ValueError(f"claim partition invalid for {component}")
        commissioned = {row["claim_id"] for row in decisions if row["action"] == "commission"}
        sources = [claim for contract in result["commission_contracts"] for claim in contract["source_claim_ids"]]
        if set(sources) != commissioned or len(sources) != len(commissioned):
            raise ValueError(f"commission partition invalid for {component}")
        allowed_existing = {row["contract_id"] for row in expected[component]["existing_same_lexeme_contracts"]}
        for decision in decisions:
            if decision["action"] == "reuse_existing" and decision["existing_contract_id"] not in allowed_existing:
                raise ValueError(f"invalid existing contract for {decision['claim_id']}")
            if decision["action"] != "reuse_existing" and decision["existing_contract_id"]:
                raise ValueError(f"unexpected existing contract for {decision['claim_id']}")


def run_batch(batch: list[dict[str, Any]], *, index: int | str, output: Path, codex: Path, model: str, timeout: int, occupied: list[str]) -> list[dict[str, Any]]:
    stem = f"batch-{index:04d}" if isinstance(index, int) else f"group-{index}"
    path = output / "contract-batches" / f"{stem}.json"
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8"))["groups"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="campaign36-prerequisite-contract-") as raw:
        temporary = Path(raw)
        schema_path, result_path = temporary / "schema.json", temporary / "result.json"
        schema_path.write_text(json.dumps(schema(len(batch)), sort_keys=True), encoding="utf-8")
        completed = subprocess.run([
            str(codex), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(temporary),
            "--model", model, "--output-schema", str(schema_path),
            "--output-last-message", str(result_path), "--color", "never", "-",
        ], input=prompt(batch, occupied), text=True, capture_output=True, timeout=timeout, check=False)
        if completed.returncode != 0 or not result_path.is_file():
            raise RuntimeError(f"contract batch {index} failed: {completed.stderr[-2000:]}")
        payload = json.loads(result_path.read_text(encoding="utf-8"))
    try:
        validate_batch_payload(batch, payload, index)
    except ValueError:
        if len(batch) == 1:
            raise
        recovered = []
        returned = {row.get("component"): row for row in payload.get("groups", [])}
        for item in batch:
            prior = returned.get(item["component"])
            if prior is not None:
                try:
                    validate_batch_payload([item], {"groups": [prior]}, f"{index}-{item['component']}")
                    recovered.append(prior)
                    continue
                except ValueError:
                    pass
            safe = re.sub(r"[^a-z0-9]+", "-", item["component"]).strip("-")
            recovered.extend(run_batch(
                [item], index=f"{index}-{safe}", output=output, codex=codex,
                model=model, timeout=timeout, occupied=occupied,
            ))
        atomic_json(path, {"schema_version": SCHEMA_VERSION, "model": model, "groups": recovered, "recovered_as_single_groups": True})
        return recovered
    atomic_json(path, {"schema_version": SCHEMA_VERSION, "model": model, **payload})
    return payload["groups"]


def prepare(args: argparse.Namespace) -> dict[str, Any]:
    missing, contracts = load_jsonl(args.missing), load_jsonl(args.contracts)
    groups = make_groups(missing, contracts)
    atomic_jsonl(args.output / "component-groups.jsonl", groups)
    result = {"missing_claims": len(missing), "unique_components": len(groups), "created_at": now()}
    atomic_json(args.output / "prepare-summary.json", result)
    return result


def contracts(args: argparse.Namespace) -> dict[str, Any]:
    groups_path = args.output / "component-groups.jsonl"
    if not groups_path.is_file():
        prepare(args)
    groups = load_jsonl(groups_path)
    occupied = sorted(surface_key(row["display_label"]) for row in load_jsonl(args.contracts))
    batches = [groups[index:index + args.batch_size] for index in range(0, len(groups), args.batch_size)]
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(run_batch, batch, index=index, output=args.output, codex=args.codex, model=args.model, timeout=args.timeout, occupied=occupied): index
            for index, batch in enumerate(batches, 1)
        }
        for future in as_completed(futures):
            results.extend(future.result())
            print(f"completed contract batch {futures[future]}/{len(batches)}", flush=True)
    order = {row["component"]: index for index, row in enumerate(groups)}
    results.sort(key=lambda row: order[row["component"]])
    decisions = [decision for group in results for decision in group["claim_decisions"]]
    commissioned = []
    for group in results:
        for contract in group["commission_contracts"]:
            commissioned.append({
                "schema_version": SCHEMA_VERSION, "commission_id": f"p{len(commissioned) + 1:04d}",
                "component": group["component"], "required_images": 10, **contract,
            })
    labels = [surface_key(row["display_label"]) for row in commissioned]
    collisions = sorted({label for label in labels if labels.count(label) > 1 or label in occupied})
    atomic_jsonl(args.output / "claim-decisions.jsonl", decisions)
    atomic_jsonl(args.output / "commission-contracts.jsonl", commissioned)
    atomic_jsonl(args.output / "contract-review-groups.jsonl", results)
    result = {
        "missing_claims": len(decisions), "commission_claims": sum(row["action"] == "commission" for row in decisions),
        "reuse_existing_claims": sum(row["action"] == "reuse_existing" for row in decisions),
        "rejected_claims": sum(row["action"] == "reject" for row in decisions),
        "commission_contracts": len(commissioned), "required_images": len(commissioned) * 10,
        "display_label_collisions": collisions, "created_at": now(), "model": args.model,
    }
    atomic_json(args.output / "contract-summary.json", result)
    return result


def repair_contracts(args: argparse.Namespace) -> dict[str, Any]:
    commissioned = {row["commission_id"]: row for row in load_jsonl(args.output / "commission-contracts.jsonl")}
    decisions = load_jsonl(args.output / "claim-decisions.jsonl")
    repairs = [
        {"action": "merge", "source": "p0242", "target": "p0070", "reason": "near and close express the same short-distance visual contract"},
        {"action": "merge", "source": "p0166", "target": "p0164", "reason": "duplicate establish/start sense of to found"},
        {"action": "merge", "source": "p0178", "target": "p0176", "reason": "duplicate motion sense of to go"},
        {"action": "merge", "source": "p0351", "target": "p0344", "reason": "steady and stable share the same firm/balanced visual contract"},
        {"action": "merge", "source": "p0358", "target": "p0157", "reason": "stream and flow share the same continuous-movement visual contract"},
        {"action": "reuse_existing", "source": "p0341", "target": "source-c0391", "reason": "existing outer space contract teaches the exact required sense"},
        {"action": "rename", "source": "p0239", "display_label": "nail plate", "reason": "distinguish body-part nail from existing metal-fastener nail"},
        {"action": "rename", "source": "p0309", "display_label": "to ooze", "reason": "distinguish liquid-running sense from general to flow while retaining image compatibility"},
    ]
    for repair in repairs:
        source = repair["source"]
        if repair["action"] == "merge":
            target = commissioned[repair["target"]]
            item = commissioned.pop(source)
            target["source_claim_ids"] = sorted(set(target["source_claim_ids"] + item["source_claim_ids"]))
            target["search_terms"] = list(dict.fromkeys(target["search_terms"] + item["search_terms"]))[:8]
        elif repair["action"] == "reuse_existing":
            item = commissioned.pop(source)
            claim_ids = set(item["source_claim_ids"])
            for decision in decisions:
                if decision["claim_id"] in claim_ids:
                    decision.update({"action": "reuse_existing", "existing_contract_id": repair["target"], "rationale": repair["reason"]})
        else:
            commissioned[source]["display_label"] = repair["display_label"]
    clean = sorted(commissioned.values(), key=lambda row: int(row["commission_id"][1:]))
    existing_labels = {surface_key(row["display_label"]) for row in load_jsonl(args.contracts)}
    labels = [surface_key(row["display_label"]) for row in clean]
    collisions = sorted({label for label in labels if labels.count(label) > 1 or label in existing_labels})
    if collisions:
        raise ValueError(f"contract repair left display-label collisions: {collisions}")
    atomic_jsonl(args.output / "commission-contracts-clean.jsonl", clean)
    atomic_jsonl(args.output / "claim-decisions-clean.jsonl", decisions)
    atomic_jsonl(args.output / "contract-repairs.jsonl", repairs)
    result = {
        "commission_contracts": len(clean), "required_images": len(clean) * 10,
        "display_label_collisions": 0, "repairs": len(repairs), "created_at": now(),
    }
    atomic_json(args.output / "contract-repair-summary.json", result)
    return result


def fold(args: argparse.Namespace) -> dict[str, Any]:
    original_contracts = load_jsonl(args.contracts)
    original_assets = load_jsonl(DEPENDENCY_ROOT / "accepted-assets.jsonl")
    original_edges = load_jsonl(DEPENDENCY_ROOT / "dependency-edges.jsonl")
    missing = {row["claim_id"]: row for row in load_jsonl(DEPENDENCY_ROOT / "missing-prerequisites.jsonl")}
    decisions = load_jsonl(args.output / "claim-decisions-clean.jsonl")
    new_contracts = load_jsonl(args.new_final / "teaching-contracts.jsonl")
    new_assets = load_jsonl(args.new_final / "accepted-assets.jsonl")
    claim_to_new = {
        claim_id: row["prerequisite_contract_id"]
        for row in new_contracts for claim_id in row["source_claim_ids"]
    }
    edges = [{
        "dependency_contract_id": row["dependency_contract_id"],
        "target_contract_id": row["target_contract_id"], "provenance": "campaign36_dependency_order_v1",
    } for row in original_edges]
    rejected = 0
    for decision in decisions:
        claim_id = decision["claim_id"]
        target = missing[claim_id]["target_contract_id"]
        if decision["action"] == "commission":
            dependency = claim_to_new[claim_id]
        elif decision["action"] == "reuse_existing":
            dependency = decision["existing_contract_id"]
        else:
            rejected += 1
            continue
        edges.append({
            "dependency_contract_id": dependency, "target_contract_id": target,
            "claim_id": claim_id, "provenance": f"prerequisite_{decision['action']}",
        })
    edges = list({(row["dependency_contract_id"], row["target_contract_id"]): row for row in edges}.values())
    original_by_id = {row["contract_id"]: row for row in original_contracts}
    new_by_id = {row["prerequisite_contract_id"]: row for row in new_contracts}
    nodes = set(original_by_id) | set(new_by_id)
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_edges_from((row["dependency_contract_id"], row["target_contract_id"]) for row in edges)
    if not nx.is_directed_acyclic_graph(graph):
        raise ValueError(f"folded dependency graph has cycles: {list(nx.simple_cycles(graph))[:5]}")
    original_rank = {row["contract_id"]: float(row["ordinal"]) for row in original_contracts}
    targets_by_new: dict[str, list[float]] = {}
    for edge in edges:
        if edge["dependency_contract_id"] in new_by_id:
            targets_by_new.setdefault(edge["dependency_contract_id"], []).append(original_rank[edge["target_contract_id"]])
    rank = dict(original_rank)
    for order, row in enumerate(new_contracts, 1):
        contract_id = row["prerequisite_contract_id"]
        rank[contract_id] = min(targets_by_new.get(contract_id, [2501.0])) - 0.5 + order / 1_000_000
    order = list(nx.lexicographical_topological_sort(graph, key=lambda node: (rank[node], node)))
    new_ordinal = {contract_id: index for index, contract_id in enumerate(order, 1)}
    deps_by_target: dict[str, list[str]] = {}
    for edge in edges:
        deps_by_target.setdefault(edge["target_contract_id"], []).append(edge["dependency_contract_id"])
    combined_contracts = []
    for contract_id in order:
        if contract_id in original_by_id:
            row = original_by_id[contract_id]
            combined_contracts.append({
                **row, "source_curriculum": "campaign36_dependency_order_v1",
                "source_ordinal": row["ordinal"], "ordinal": new_ordinal[contract_id],
                "depends_on": sorted(set(deps_by_target.get(contract_id, [])), key=new_ordinal.get),
                "missing_dependencies": [],
            })
        else:
            row = new_by_id[contract_id]
            combined_contracts.append({
                **row, "contract_id": contract_id, "concept_id": contract_id,
                "word": row["lemma"], "source_curriculum": "campaign36_prerequisite_commission_v1",
                "source_ordinal": None, "ordinal": new_ordinal[contract_id],
                "depends_on": sorted(set(deps_by_target.get(contract_id, [])), key=new_ordinal.get),
                "missing_dependencies": [],
            })
    assets_by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in original_assets:
        assets_by_contract.setdefault(row["contract_id"], []).append(row)
    for row in new_assets:
        assets_by_contract.setdefault(row["prerequisite_contract_id"], []).append(row)
    combined_assets = []
    for contract_id in order:
        rows = sorted(assets_by_contract[contract_id], key=lambda row: int(row["exposure_index"]))
        if len(rows) != 10:
            raise ValueError(f"folded contract {contract_id} has {len(rows)} assets")
        ordinal = new_ordinal[contract_id]
        for exposure, row in enumerate(rows, 1):
            combined_assets.append({
                **row, "contract_id": contract_id, "source_slot_id": row["slot_id"],
                "ordinal": ordinal, "slot_id": f"c{ordinal:04d}-i{exposure:02d}",
                "exposure_index": exposure, "sequence_position": (ordinal - 1) * 10 + exposure,
                "depends_on": sorted(set(deps_by_target.get(contract_id, [])), key=new_ordinal.get),
                "missing_dependencies": [],
            })
    labels = [surface_key(row["display_label"]) for row in combined_contracts]
    if len(labels) != len(set(labels)):
        raise ValueError("folded curriculum has duplicate display labels")
    hashes = Counter(str(row.get("sha256") or row.get("asset_sha256")) for row in combined_assets)
    hashes.pop("", None)
    if max(hashes.values(), default=0) > 4:
        raise ValueError("folded curriculum exceeds image reuse cap")
    for edge in edges:
        if new_ordinal[edge["dependency_contract_id"]] >= new_ordinal[edge["target_contract_id"]]:
            raise ValueError(f"folded order violates edge: {edge}")
    root = args.output / "expanded-curriculum-v1"
    atomic_jsonl(root / "teaching-contracts.jsonl", combined_contracts)
    atomic_jsonl(root / "accepted-assets.jsonl", combined_assets)
    atomic_jsonl(root / "dependency-edges.jsonl", edges)
    result = {
        "contracts": len(combined_contracts), "assets": len(combined_assets),
        "new_contracts": len(new_contracts), "dependency_edges": len(edges),
        "dependency_violations": 0, "known_missing_prerequisites_after_fold": 0,
        "rejected_non_dependencies": rejected, "images_per_contract": 10,
        "max_image_reuse": max(hashes.values(), default=0), "created_at": now(),
        "requires_recursive_dependency_audit": True,
    }
    atomic_json(root / "summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("prepare", "contracts", "repair-contracts", "fold", "all"))
    parser.add_argument("--missing", type=Path, default=DEFAULT_MISSING)
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--codex", type=Path, default=DEFAULT_CODEX)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--batch-size", type=int, default=25)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--new-final", type=Path, default=DEFAULT_NEW_FINAL)
    args = parser.parse_args()
    if args.command in ("prepare", "all"):
        print(json.dumps(prepare(args), indent=2, sort_keys=True))
    if args.command in ("contracts", "all"):
        print(json.dumps(contracts(args), indent=2, sort_keys=True))
    if args.command in ("repair-contracts", "all"):
        print(json.dumps(repair_contracts(args), indent=2, sort_keys=True))
    if args.command in ("fold", "all"):
        print(json.dumps(fold(args), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
