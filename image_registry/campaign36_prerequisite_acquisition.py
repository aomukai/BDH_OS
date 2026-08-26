"""Acquire and Luna-review images for Campaign 36 prerequisite contracts."""

from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import urllib.parse
import urllib.request
import shutil
from types import SimpleNamespace
from typing import Any

from PIL import Image, ImageDraw, ImageFont, ImageOps
import networkx as nx

from image_registry.campaign36_dependency_order import load_jsonl, atomic_json, atomic_jsonl
from image_registry.campaign36_headless_imagegen import generate_one


DEPENDENCY_ROOT = Path(
    "/media/aomukai/FILES/Ninereeds/image-corpus/exports/"
    "campaign36-foundation-preparation-v1/infinitive-label-v1/dependency-order-v1"
)
COMMISSION_ROOT = DEPENDENCY_ROOT / "prerequisite-commission-v1"
DEFAULT_CONTRACTS = COMMISSION_ROOT / "commission-contracts-clean.jsonl"
DEFAULT_CURRENT_ASSETS = DEPENDENCY_ROOT / "accepted-assets.jsonl"
DEFAULT_DB = Path("/home/aomukai/Ninereeds/training_data/image_registry/registry.sqlite3")
DEFAULT_OUTPUT = COMMISSION_ROOT / "acquisition-v1"
DEFAULT_CODEX = Path("/home/aomukai/.local/bin/codex")
SCHEMA_VERSION = "ninereeds_campaign36_prerequisite_acquisition_v1"


def current_assets(args: argparse.Namespace) -> list[dict[str, Any]]:
    paths = [args.current_assets, *getattr(args, "additional_current_assets", [])]
    return [row for path in paths for row in load_jsonl(path)]
STOP = {"a", "an", "and", "as", "at", "by", "for", "from", "in", "of", "on", "or", "the", "to", "with"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.casefold()) if token not in STOP}


def connect_ro(path: Path) -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=120)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def local_shortlist(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.contracts)
    current_hashes = Counter(str(row.get("sha256") or row.get("asset_sha256")) for row in current_assets(args))
    with connect_ro(args.db) as db:
        assets = {row["id"]: {
            "asset_id": row["id"], "source": row["source"], "source_id": row["source_id"],
            "local_path": row["local_path"], "sha256": row["sha256"],
            "width": row["width"], "height": row["height"], "evidence": [],
        } for row in db.execute(
            """SELECT id,source,source_id,local_path,sha256,width,height FROM asset
               WHERE status='reviewed_usable' AND local_path IS NOT NULL AND sha256 IS NOT NULL ORDER BY id"""
        ) if Path(row["local_path"]).is_file() and current_hashes[str(row["sha256"])] < 4}
        inverted: dict[str, set[int]] = {}
        preferred_caption: dict[int, tuple[int, str]] = {}
        for row in db.execute("SELECT asset_id,kind,text FROM text_record ORDER BY asset_id,id"):
            if row["asset_id"] not in assets:
                continue
            priority = 0 if row["kind"] == "reviewed_caption" else 1 if "caption" in row["kind"] else 2
            prior = preferred_caption.get(row["asset_id"])
            if prior is None or priority < prior[0]:
                preferred_caption[row["asset_id"]] = (priority, row["text"])
            for token in tokens(row["text"]):
                inverted.setdefault(token, set()).add(row["asset_id"])
        for row in db.execute("SELECT asset_id,name FROM label ORDER BY asset_id,name"):
            if row["asset_id"] not in assets:
                continue
            for token in tokens(row["name"]):
                inverted.setdefault(token, set()).add(row["asset_id"])
        for asset_id, (_, caption) in preferred_caption.items():
            assets[asset_id]["caption"] = caption
    rows = []
    counts: dict[str, int] = {}
    for contract in contracts:
        queries = list(dict.fromkeys([
            contract["component"], contract["lemma"], contract["display_label"], *contract["search_terms"],
        ]))
        scores: dict[int, tuple[int, int]] = {}
        evidence: dict[int, list[str]] = {}
        for query in queries:
            terms = tokens(query)
            matches = [inverted.get(term, set()) for term in terms]
            candidate_ids = set.intersection(*matches) if matches else set()
            for asset_id in candidate_ids:
                old = scores.get(asset_id, (0, 0))
                scores[asset_id] = (old[0] + 1, old[1] + len(terms))
                evidence.setdefault(asset_id, []).append(query)
        ranked = sorted(scores, key=lambda asset_id: (-scores[asset_id][0], -scores[asset_id][1], asset_id))
        seen_hashes: set[str] = set()
        selected = []
        for asset_id in ranked:
            asset = assets[asset_id]
            if asset["sha256"] in seen_hashes:
                continue
            seen_hashes.add(asset["sha256"])
            selected.append({
                "schema_version": SCHEMA_VERSION, "commission_id": contract["commission_id"],
                "display_label": contract["display_label"], "teaching_sense": contract["teaching_sense"],
                "visual_contract": contract["visual_contract"], "candidate_id": f"local-a{asset_id}",
                "retrieval_stage": "reviewed_local_registry", "matched_queries": evidence[asset_id],
                "retrieval_score": list(scores[asset_id]), **asset,
            })
            if len(selected) == args.candidates_per_contract:
                break
        rows.extend(selected)
        counts[contract["commission_id"]] = len(selected)
    atomic_jsonl(args.output / "local-candidates.jsonl", rows)
    summary = {
        "contracts": len(contracts), "candidate_bindings": len(rows),
        "contracts_with_candidates": sum(value > 0 for value in counts.values()),
        "contracts_with_at_least_10": sum(value >= 10 for value in counts.values()),
        "contracts_with_at_least_30": sum(value >= 30 for value in counts.values()),
        "candidate_count_min": min(counts.values(), default=0),
        "candidate_count_max": max(counts.values(), default=0),
        "created_at": now(),
    }
    atomic_json(args.output / "local-shortlist-summary.json", summary)
    return summary


def review_schema(count: int) -> dict[str, Any]:
    return {
        "type": "object", "properties": {
            "decisions": {"type": "array", "minItems": count, "maxItems": count, "items": {
                "type": "object", "properties": {
                    "panel_id": {"type": "string"}, "verdict": {"type": "string", "enum": ["accept", "reject"]},
                    "rationale": {"type": "string", "minLength": 1},
                }, "required": ["panel_id", "verdict", "rationale"], "additionalProperties": False,
            }},
            "set_notes": {"type": "string"},
        }, "required": ["decisions", "set_notes"], "additionalProperties": False,
    }


def make_sheet(rows: list[dict[str, Any]], path: Path) -> dict[str, dict[str, Any]]:
    columns, cell_w, image_h, header_h = 5, 240, 190, 26
    row_count = (len(rows) + columns - 1) // columns
    sheet = Image.new("RGB", (columns * cell_w, row_count * (image_h + header_h)), "white")
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default()
    mapping = {}
    for index, row in enumerate(rows, 1):
        panel = f"{index:02d}"
        mapping[panel] = row
        x, y = ((index - 1) % columns) * cell_w, ((index - 1) // columns) * (image_h + header_h)
        with Image.open(row["local_path"]) as image:
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((cell_w - 8, image_h - 8))
            px, py = x + (cell_w - image.width) // 2, y + header_h + (image_h - image.height) // 2
            sheet.paste(image, (px, py))
        draw.rectangle((x, y, x + cell_w - 1, y + header_h + image_h - 1), outline="black", width=1)
        draw.text((x + 8, y + 7), f"PANEL {panel}", fill="black", font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path, quality=90)
    return mapping


def run_review(contract: dict[str, Any], rows: list[dict[str, Any]], *, round_index: int, args: argparse.Namespace, stage: str = "local") -> list[dict[str, Any]]:
    result_path = args.output / f"{stage}-reviews" / f"{contract['commission_id']}-r{round_index}.json"
    if result_path.is_file():
        return json.loads(result_path.read_text(encoding="utf-8"))["reviewed_rows"]
    sheet_path = args.output / f"{stage}-contact-sheets" / f"{contract['commission_id']}-r{round_index}.jpg"
    mapping = make_sheet(rows, sheet_path)
    panel_context = [{
        "panel_id": panel, "candidate_id": row["candidate_id"], "caption_evidence": row.get("caption"),
    } for panel, row in mapping.items()]
    prompt = f"""You are Luna performing strict pixel review for an image-grounded vocabulary set.
Target display label: {contract['display_label']}
Intended meaning: {contract['teaching_sense']}
Exact visual contract: {contract['visual_contract']}

Inspect every numbered panel in the attached contact sheet. Accept only when the pixels directly and
unambiguously fit the exact intended meaning. Metadata is retrieval evidence only and cannot rescue
a visual mismatch. Reject text-only explanations, wrong homograph senses, merely associated scenes,
bad anatomy, severe blur, watermarks, collage panels, or an unclear target. Judge every panel exactly
once. Diversity is welcome but never lower the fit standard.

PANEL METADATA:\n{json.dumps(panel_context, ensure_ascii=False)}"""
    with tempfile.TemporaryDirectory(prefix="campaign36-prerequisite-review-") as raw:
        temporary = Path(raw)
        schema_path, output_path = temporary / "schema.json", temporary / "result.json"
        schema_path.write_text(json.dumps(review_schema(len(rows)), sort_keys=True), encoding="utf-8")
        completed = subprocess.run([
            str(args.codex), "exec", "--ephemeral", "--ignore-user-config", "--ignore-rules",
            "--sandbox", "read-only", "--skip-git-repo-check", "-C", str(temporary),
            "--model", args.model, "--output-schema", str(schema_path), "--image", str(sheet_path),
            "--output-last-message", str(output_path), "--color", "never", "-",
        ], input=prompt, text=True, capture_output=True, timeout=args.timeout, check=False)
        if completed.returncode != 0 or not output_path.is_file():
            raise RuntimeError(f"local review failed for {contract['commission_id']}: {completed.stderr[-2000:]}")
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    decisions = {row["panel_id"]: row for row in payload["decisions"]}
    if set(decisions) != set(mapping) or len(decisions) != len(mapping):
        raise ValueError(f"Luna omitted or duplicated panels for {contract['commission_id']} round {round_index}")
    reviewed = [{
        **row, "luna_verdict": decisions[panel]["verdict"],
        "luna_rationale": decisions[panel]["rationale"], "review_model": args.model,
    } for panel, row in mapping.items()]
    atomic_json(result_path, {"schema_version": SCHEMA_VERSION, "reviewed_rows": reviewed, "set_notes": payload["set_notes"]})
    return reviewed


def review_local(args: argparse.Namespace) -> dict[str, Any]:
    contracts = {row["commission_id"]: row for row in load_jsonl(args.contracts)}
    by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(args.output / "local-candidates.jsonl"):
        by_contract.setdefault(row["commission_id"], []).append(row)

    def review_contract(contract: dict[str, Any]) -> list[dict[str, Any]]:
        candidates = by_contract.get(contract["commission_id"], [])
        reviewed: list[dict[str, Any]] = []
        for round_index in (1, 2):
            start = (round_index - 1) * args.sheet_size
            batch = candidates[start:start + args.sheet_size]
            if not batch:
                break
            reviewed.extend(run_review(contract, batch, round_index=round_index, args=args))
            if sum(row["luna_verdict"] == "accept" for row in reviewed) >= args.accept_buffer:
                break
        return reviewed

    reviewed_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(review_contract, contract): contract_id for contract_id, contract in contracts.items()}
        for future in as_completed(futures):
            reviewed_rows.extend(future.result())
            print(f"reviewed local {futures[future]}", flush=True)
    reviewed_rows.sort(key=lambda row: (int(row["commission_id"][1:]), row["candidate_id"]))
    accepted = [row for row in reviewed_rows if row["luna_verdict"] == "accept"]
    atomic_jsonl(args.output / "local-reviewed.jsonl", reviewed_rows)
    atomic_jsonl(args.output / "local-accepted-candidates.jsonl", accepted)
    counts = Counter(row["commission_id"] for row in accepted)
    summary = {
        "contracts": len(contracts), "reviewed_bindings": len(reviewed_rows),
        "accepted_bindings": len(accepted), "contracts_with_10_accepted": sum(counts[key] >= 10 for key in contracts),
        "accepted_slots_available": sum(min(10, counts[key]) for key in contracts),
        "remaining_slots_before_global_reuse_allocation": sum(max(0, 10 - counts[key]) for key in contracts),
        "created_at": now(), "review_model": args.model,
    }
    atomic_json(args.output / "local-review-summary.json", summary)
    return summary


def allocate_local(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.contracts)
    accepted = load_jsonl(args.output / "local-accepted-candidates.jsonl")
    current = Counter(str(row.get("sha256") or row.get("asset_sha256")) for row in current_assets(args))
    by_edge: dict[tuple[str, str], dict[str, Any]] = {}
    graph = nx.DiGraph()
    source, sink = "__source__", "__sink__"
    for contract in contracts:
        graph.add_edge(source, f"c:{contract['commission_id']}", capacity=10)
    for row in accepted:
        contract_id, digest = row["commission_id"], row["sha256"]
        capacity = max(0, 4 - current[digest])
        if not capacity:
            continue
        contract_node, hash_node = f"c:{contract_id}", f"h:{digest}"
        graph.add_edge(contract_node, hash_node, capacity=1)
        graph.add_edge(hash_node, sink, capacity=capacity)
        by_edge.setdefault((contract_id, digest), row)
    flow_value, flow = nx.maximum_flow(graph, source, sink)
    selected = []
    for contract in contracts:
        contract_id = contract["commission_id"]
        rows = [by_edge[(contract_id, node[2:])] for node, value in flow.get(f"c:{contract_id}", {}).items() if value]
        rows.sort(key=lambda row: row["asset_id"])
        for exposure, row in enumerate(rows, 1):
            selected.append({**row, "exposure_index": exposure, "slot_id": f"{contract_id}-i{exposure:02d}", "selection_stage": "reviewed_local_registry"})
    selected_count = Counter(row["commission_id"] for row in selected)
    needs = []
    for order, contract in enumerate(contracts, 1):
        for exposure in range(selected_count[contract["commission_id"]] + 1, 11):
            needs.append({
                "schema_version": SCHEMA_VERSION, "commission_order": order,
                "commission_id": contract["commission_id"], "slot_id": f"{contract['commission_id']}-i{exposure:02d}",
                "exposure_index": exposure, "display_label": contract["display_label"],
                "lemma": contract["lemma"], "part_of_speech": contract["part_of_speech"],
                "teaching_sense": contract["teaching_sense"], "visual_contract": contract["visual_contract"],
                "search_terms": contract["search_terms"], "status": "needs_external_metadata_search",
            })
    atomic_jsonl(args.output / "local-selected.jsonl", selected)
    atomic_jsonl(args.output / "metadata-needs.jsonl", needs)
    result = {
        "contracts": len(contracts), "required_slots": len(contracts) * 10,
        "local_selected_slots": len(selected), "metadata_needed_slots": len(needs),
        "contracts_complete_from_local": sum(selected_count[row["commission_id"]] == 10 for row in contracts),
        "max_new_uses_of_one_hash": max(Counter(row["sha256"] for row in selected).values(), default=0),
        "max_combined_hash_reuse": max((current[digest] + count for digest, count in Counter(row["sha256"] for row in selected).items()), default=0),
        "maximum_flow": flow_value, "created_at": now(),
    }
    atomic_json(args.output / "local-allocation-summary.json", result)
    return result


def fts_query(value: str) -> str | None:
    parts = sorted(tokens(value))
    return " AND ".join(f'"{part}"' for part in parts) if parts else None


def metadata_shortlist(args: argparse.Namespace) -> dict[str, Any]:
    needs = load_jsonl(args.output / "metadata-needs.jsonl")
    contracts = {row["commission_id"]: row for row in load_jsonl(args.contracts)}
    need_counts = Counter(row["commission_id"] for row in needs)
    with connect_ro(args.db) as registry:
        existing: dict[str, set[str]] = {}
        for row in registry.execute("SELECT source,source_id FROM asset"):
            existing.setdefault(row["source"], set()).add(str(row["source_id"]))
    source_specs = [
        ("pixmo_cap", Path("/media/aomukai/FILES/Ninereeds/image-corpus/sources/pixmo_cap/metadata.sqlite3")),
        ("coco_2017", Path("/media/aomukai/FILES/Ninereeds/image-corpus/sources/coco_2017/captions.sqlite3")),
        ("visual_genome_v1_2", Path("/media/aomukai/FILES/Ninereeds/image-corpus/sources/visual_genome_v1_2/metadata.sqlite3")),
        ("conceptual_captions_labeled", Path("/media/aomukai/FILES/Ninereeds/image-corpus/sources/conceptual_captions_labeled/metadata.sqlite3")),
    ]
    dbs = {name: connect_ro(path) for name, path in source_specs}
    rows: list[dict[str, Any]] = []
    try:
        for contract_id, deficit in need_counts.items():
            contract = contracts[contract_id]
            queries = list(dict.fromkeys([contract["component"], contract["lemma"], *contract["search_terms"]]))
            candidates: dict[tuple[str, str], dict[str, Any]] = {}
            for source_rank, (source, _) in enumerate(source_specs):
                db = dbs[source]
                for query_rank, query in enumerate(queries):
                    fts = fts_query(query)
                    if not fts:
                        continue
                    try:
                        if source == "pixmo_cap":
                            found = db.execute(
                                """SELECT i.source_id,i.image_url,i.caption,bm25(image_search) score
                                   FROM image_search s JOIN image i ON i.id=s.rowid
                                   WHERE image_search MATCH ? ORDER BY score LIMIT 25""", (fts,),
                            ).fetchall()
                            converted = [{"source_id": row["source_id"], "url": row["image_url"], "caption": row["caption"], "score": row["score"]} for row in found]
                        elif source == "coco_2017":
                            found = db.execute(
                                """SELECT i.image_id,i.coco_url,i.file_name,i.split,s.caption,bm25(caption_search) score
                                   FROM caption_search s JOIN image i ON i.image_id=s.image_id
                                   WHERE caption_search MATCH ? ORDER BY score LIMIT 25""", (fts,),
                            ).fetchall()
                            converted = [{"source_id": str(row["image_id"]), "url": row["coco_url"].replace("http://", "https://", 1), "caption": row["caption"], "score": row["score"]} for row in found]
                        elif source == "visual_genome_v1_2":
                            found = db.execute(
                                """SELECT i.image_id,i.url,s.phrase,bm25(region_search) score
                                   FROM region_search s JOIN image i ON i.image_id=s.image_id
                                   WHERE region_search MATCH ? ORDER BY score LIMIT 25""", (fts,),
                            ).fetchall()
                            converted = [{"source_id": str(row["image_id"]), "url": row["url"].replace("http://", "https://", 1), "caption": row["phrase"], "score": row["score"]} for row in found]
                        else:
                            found = db.execute(
                                """SELECT i.source_id,i.image_url,i.caption,bm25(image_search) score
                                   FROM image_search s JOIN image i ON i.id=s.rowid
                                   WHERE image_search MATCH ? ORDER BY score LIMIT 25""", (fts,),
                            ).fetchall()
                            converted = [{"source_id": row["source_id"], "url": row["image_url"], "caption": row["caption"], "score": row["score"]} for row in found]
                    except sqlite3.OperationalError:
                        continue
                    for item in converted:
                        key = (source, str(item["source_id"]))
                        if key[1] in existing.get(source, set()):
                            continue
                        rank = (source_rank, query_rank, float(item["score"]))
                        prior = candidates.get(key)
                        if prior is None or rank < tuple(prior["metadata_rank"]):
                            candidates[key] = {
                                "schema_version": SCHEMA_VERSION, "commission_id": contract_id,
                                "display_label": contract["display_label"], "teaching_sense": contract["teaching_sense"],
                                "visual_contract": contract["visual_contract"], "source": source,
                                "source_id": key[1], "original_url": item["url"], "caption": item["caption"],
                                "matched_query": query, "metadata_rank": list(rank),
                                "candidate_id": f"metadata-{source}-{key[1]}", "retrieval_stage": "external_metadata_index",
                            }
            limit = min(args.metadata_candidates_per_contract, max(20, deficit * args.metadata_multiplier))
            ranked = sorted(candidates.values(), key=lambda row: (row["metadata_rank"], row["source_id"]))[:limit]
            rows.extend(ranked)
    finally:
        for db in dbs.values():
            db.close()
    atomic_jsonl(args.output / "metadata-candidates.jsonl", rows)
    counts = Counter(row["commission_id"] for row in rows)
    result = {
        "incomplete_contracts": len(need_counts), "needed_slots": len(needs),
        "metadata_candidate_bindings": len(rows),
        "contracts_with_metadata_candidates": sum(counts[key] > 0 for key in need_counts),
        "contracts_with_candidate_surplus": sum(counts[key] >= need_counts[key] * 2 for key in need_counts),
        "created_at": now(),
    }
    atomic_json(args.output / "metadata-shortlist-summary.json", result)
    return result


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def download_one(row: dict[str, Any], output: Path, timeout: int) -> dict[str, Any] | None:
    safe = urllib.parse.quote(row["source_id"], safe="._-")
    target = output / "external-downloads" / row["source"] / f"{safe}.jpg"
    if target.is_file():
        try:
            with Image.open(target) as image:
                if image.width * image.height > 50_000_000 or min(image.size) < 128:
                    raise ValueError("cached image outside pixel bounds")
                image.verify()
            return {**row, "local_path": str(target), "sha256": file_digest(target)}
        except Exception:
            target.unlink(missing_ok=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(row["original_url"], headers={"User-Agent": "Ninereeds/1.0 image curriculum"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(25 * 1024 * 1024 + 1)
        if not data or len(data) > 25 * 1024 * 1024:
            return None
        temporary = target.with_suffix(".partial")
        temporary.write_bytes(data)
        with Image.open(temporary) as image:
            if image.width * image.height > 50_000_000 or min(image.size) < 128:
                temporary.unlink(missing_ok=True)
                return None
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.save(target, format="JPEG", quality=92)
        temporary.unlink(missing_ok=True)
        return {**row, "local_path": str(target), "sha256": file_digest(target)}
    except Exception as error:
        return None


def download_metadata(args: argparse.Namespace) -> dict[str, Any]:
    bindings = load_jsonl(args.output / "metadata-candidates.jsonl")
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in bindings:
        unique.setdefault((row["source"], row["source_id"]), row)
    downloaded: dict[tuple[str, str], dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=args.download_workers) as executor:
        futures = {executor.submit(download_one, row, args.output, args.download_timeout): key for key, row in unique.items()}
        for future in as_completed(futures):
            result = future.result()
            if result is not None:
                downloaded[futures[future]] = result
    hydrated = [{**row, "local_path": downloaded[key]["local_path"], "sha256": downloaded[key]["sha256"]}
                for row in bindings if (key := (row["source"], row["source_id"])) in downloaded]
    atomic_jsonl(args.output / "metadata-downloaded.jsonl", hydrated)
    result = {
        "unique_candidates": len(unique), "unique_downloaded": len(downloaded),
        "downloaded_bindings": len(hydrated),
        "contracts_with_downloads": len({row["commission_id"] for row in hydrated}),
        "created_at": now(),
    }
    atomic_json(args.output / "metadata-download-summary.json", result)
    return result


def review_metadata(args: argparse.Namespace) -> dict[str, Any]:
    contracts = {row["commission_id"]: row for row in load_jsonl(args.contracts)}
    needs = Counter(row["commission_id"] for row in load_jsonl(args.output / "metadata-needs.jsonl"))
    by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(args.output / "metadata-downloaded.jsonl"):
        by_contract.setdefault(row["commission_id"], []).append(row)

    def review_contract(contract_id: str) -> list[dict[str, Any]]:
        contract = contracts[contract_id]
        candidates = by_contract.get(contract_id, [])
        reviewed: list[dict[str, Any]] = []
        target = needs[contract_id] + 2
        for round_index in (1, 2):
            start = (round_index - 1) * args.sheet_size
            batch = candidates[start:start + args.sheet_size]
            if not batch:
                break
            reviewed.extend(run_review(contract, batch, round_index=round_index, args=args, stage="metadata"))
            if sum(row["luna_verdict"] == "accept" for row in reviewed) >= target:
                break
        return reviewed

    reviewed_rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(review_contract, contract_id): contract_id for contract_id in needs}
        for future in as_completed(futures):
            reviewed_rows.extend(future.result())
            print(f"reviewed metadata {futures[future]}", flush=True)
    reviewed_rows.sort(key=lambda row: (int(row["commission_id"][1:]), row["candidate_id"]))
    accepted = [row for row in reviewed_rows if row["luna_verdict"] == "accept"]
    atomic_jsonl(args.output / "metadata-reviewed.jsonl", reviewed_rows)
    atomic_jsonl(args.output / "metadata-accepted-candidates.jsonl", accepted)
    counts = Counter(row["commission_id"] for row in accepted)
    result = {
        "incomplete_contracts": len(needs), "reviewed_bindings": len(reviewed_rows),
        "accepted_bindings": len(accepted),
        "contracts_with_enough_metadata_accepts": sum(counts[key] >= needs[key] for key in needs),
        "accepted_slots_available": sum(min(needs[key], counts[key]) for key in needs),
        "remaining_slots_before_reuse_allocation": sum(max(0, needs[key] - counts[key]) for key in needs),
        "created_at": now(), "review_model": args.model,
    }
    atomic_json(args.output / "metadata-review-summary.json", result)
    return result


def allocate_metadata(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.contracts)
    local = load_jsonl(args.output / "local-selected.jsonl")
    accepted = load_jsonl(args.output / "metadata-accepted-candidates.jsonl")
    current = Counter(str(row.get("sha256") or row.get("asset_sha256")) for row in current_assets(args))
    current.update(row["sha256"] for row in local)
    local_counts = Counter(row["commission_id"] for row in local)
    demand = {row["commission_id"]: 10 - local_counts[row["commission_id"]] for row in contracts}
    by_edge: dict[tuple[str, str], dict[str, Any]] = {}
    graph = nx.DiGraph()
    source, sink = "__source__", "__sink__"
    for contract_id, count in demand.items():
        graph.add_edge(source, f"c:{contract_id}", capacity=count)
    for row in accepted:
        contract_id, digest = row["commission_id"], row["sha256"]
        capacity = max(0, 4 - current[digest])
        if not capacity or demand.get(contract_id, 0) <= 0:
            continue
        graph.add_edge(f"c:{contract_id}", f"h:{digest}", capacity=1)
        graph.add_edge(f"h:{digest}", sink, capacity=capacity)
        by_edge.setdefault((contract_id, digest), row)
    flow_value, flow = nx.maximum_flow(graph, source, sink)
    selected = []
    for contract in contracts:
        contract_id = contract["commission_id"]
        rows = [by_edge[(contract_id, node[2:])] for node, value in flow.get(f"c:{contract_id}", {}).items() if value]
        rows.sort(key=lambda row: (row["source"], row["source_id"]))
        for offset, row in enumerate(rows, 1):
            exposure = local_counts[contract_id] + offset
            selected.append({**row, "exposure_index": exposure, "slot_id": f"{contract_id}-i{exposure:02d}", "selection_stage": "reviewed_external_metadata"})
    metadata_counts = Counter(row["commission_id"] for row in selected)
    generation_needs = []
    for order, contract in enumerate(contracts, 1):
        filled = local_counts[contract["commission_id"]] + metadata_counts[contract["commission_id"]]
        for exposure in range(filled + 1, 11):
            generation_needs.append({
                "schema_version": SCHEMA_VERSION, "commission_order": order,
                "commission_id": contract["commission_id"], "slot_id": f"{contract['commission_id']}-i{exposure:02d}",
                "exposure_index": exposure, "display_label": contract["display_label"], "lemma": contract["lemma"],
                "part_of_speech": contract["part_of_speech"], "teaching_sense": contract["teaching_sense"],
                "visual_contract": contract["visual_contract"], "status": "needs_flux_generation",
            })
    atomic_jsonl(args.output / "metadata-selected.jsonl", selected)
    atomic_jsonl(args.output / "generation-needs.jsonl", generation_needs)
    combined = local + selected
    final_hashes = Counter(str(row.get("sha256") or row.get("asset_sha256")) for row in current_assets(args))
    final_hashes.update(row["sha256"] for row in combined)
    result = {
        "local_selected_slots": len(local), "metadata_selected_slots": len(selected),
        "total_found_slots": len(combined), "generation_needed_slots": len(generation_needs),
        "contracts_complete_before_generation": sum(local_counts[row["commission_id"]] + metadata_counts[row["commission_id"]] == 10 for row in contracts),
        "maximum_flow": flow_value, "max_combined_hash_reuse": max(final_hashes.values(), default=0),
        "created_at": now(),
    }
    atomic_json(args.output / "metadata-allocation-summary.json", result)
    return result


def prepare_generation(args: argparse.Namespace) -> dict[str, Any]:
    needs = load_jsonl(args.output / "generation-needs.jsonl")
    contracts = {row["commission_id"]: row for row in load_jsonl(args.contracts)}
    variations = (
        "clear close view", "wider environmental view", "side view", "front view", "everyday indoor setting",
        "everyday outdoor setting", "different subject appearance", "different object appearance", "action at its clearest moment", "simple uncluttered background",
    )
    queue, prompts = [], []
    for row in needs:
        contract = contracts[row["commission_id"]]
        variation = variations[(int(row["exposure_index"]) - 1) % len(variations)]
        search_hint = contract["search_terms"][(int(row["exposure_index"]) - 1) % len(contract["search_terms"])]
        prompt = (
            "Photorealistic natural educational photograph. "
            f"Show this exact visible situation: {contract['visual_contract']} "
            f"Concrete scene hint: {search_hint}. Composition variation: {variation}. "
            "One coherent scene, one clear teaching focus, ordinary realistic materials and anatomy, "
            "the target large and visually dominant. No explanatory text, labels, logos, borders, "
            "watermarks, diagrams, symbols, or collage panels."
        )
        queue.append({
            **row, "word": row["display_label"], "concept_id": row["commission_id"],
            "ordinal": int(row["commission_order"]), "prompt": prompt,
        })
        prompts.append({"slot_id": row["slot_id"], "prompt": prompt})
    atomic_jsonl(args.output / "generation-queue.jsonl", queue)
    atomic_jsonl(args.output / "generation-prompts.jsonl", prompts)
    result = {
        "generation_slots": len(queue), "contracts": len({row["commission_id"] for row in queue}),
        "flux_prompts": len(prompts), "created_at": now(),
    }
    atomic_json(args.output / "generation-prepare-summary.json", result)
    return result


def flux_status(args: argparse.Namespace) -> dict[str, Any]:
    root = args.output / "generation-v1/flux-spool/flux_1"
    dispatch = load_jsonl(root / "dispatch.jsonl")
    counts = {}
    for gpu in (0, 1):
        completed = subprocess.run([
            "ssh", args.remote,
            f"find {args.remote_root}/gpu{gpu}/results -name '*.json' 2>/dev/null | wc -l",
        ], text=True, capture_output=True, check=False)
        counts[f"gpu{gpu}"] = int(completed.stdout.strip() or 0)
    result = {"dispatched": len(dispatch), **counts, "completed": sum(counts.values()), "remaining": len(dispatch) - sum(counts.values()), "checked_at": now()}
    atomic_json(args.output / "flux-status.json", result)
    return result


def sync_flux(args: argparse.Namespace) -> dict[str, Any]:
    root = args.output / "generation-v1/flux-spool/flux_1"
    dispatch = load_jsonl(root / "dispatch.jsonl")
    queue = {row["slot_id"]: row for row in load_jsonl(args.output / "generation-queue.jsonl")}
    for gpu in (0, 1):
        for directory in ("results", "images"):
            local = root / f"gpu{gpu}" / directory
            local.mkdir(parents=True, exist_ok=True)
            subprocess.run([
                "rsync", "-a", "--partial", f"{args.remote}:{args.remote_root}/gpu{gpu}/{directory}/", f"{local}/",
            ], text=True, capture_output=True, check=False)
    candidates, failed, pending = [], [], []
    for row in dispatch:
        result_path = root / f"gpu{row['gpu']}" / "results" / f"{row['request_id']}.json"
        if not result_path.is_file():
            pending.append(row["slot_id"])
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        produced = result.get("produced") or []
        if not produced:
            failed.append({**queue[row["slot_id"]], "failure": result.get("failures") or ["no image produced"]})
            continue
        item = produced[0]
        image = root / f"gpu{row['gpu']}" / "images" / Path(item["remote_path"]).name
        if not image.is_file():
            pending.append(row["slot_id"])
            continue
        candidates.append({
            **queue[row["slot_id"]], "candidate_id": f"flux-{row['slot_id']}",
            "local_path": str(image), "sha256": file_digest(image), "provider": "flux2-klein-4b",
            "generation_prompt": item["prompt"], "generation_stage": "flux_1",
        })
    atomic_jsonl(args.output / "flux-candidates.jsonl", candidates)
    atomic_jsonl(args.output / "flux-generation-failures.jsonl", failed)
    atomic_json(args.output / "flux-sync-summary.json", {
        "dispatched": len(dispatch), "candidates": len(candidates), "failed": len(failed),
        "pending": len(pending), "pending_slots": pending[:100], "created_at": now(),
    })
    return {"dispatched": len(dispatch), "candidates": len(candidates), "failed": len(failed), "pending": len(pending)}


def review_flux(args: argparse.Namespace) -> dict[str, Any]:
    contracts = {row["commission_id"]: row for row in load_jsonl(args.contracts)}
    by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(args.output / "flux-candidates.jsonl"):
        by_contract.setdefault(row["commission_id"], []).append(row)

    def one(contract_id: str) -> list[dict[str, Any]]:
        rows = sorted(by_contract[contract_id], key=lambda row: row["exposure_index"])
        return run_review(contracts[contract_id], rows, round_index=1, args=args, stage="flux")

    reviewed = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(one, contract_id): contract_id for contract_id in by_contract}
        for future in as_completed(futures):
            reviewed.extend(future.result())
            print(f"reviewed flux {futures[future]}", flush=True)
    reviewed.sort(key=lambda row: (int(row["commission_id"][1:]), row["exposure_index"]))
    accepted = [row for row in reviewed if row["luna_verdict"] == "accept"]
    atomic_jsonl(args.output / "flux-reviewed.jsonl", reviewed)
    atomic_jsonl(args.output / "flux-selected.jsonl", [{**row, "selection_stage": "luna_accepted_flux"} for row in accepted])
    result = {
        "reviewed": len(reviewed), "accepted": len(accepted), "rejected": len(reviewed) - len(accepted),
        "contracts_reviewed": len(by_contract), "created_at": now(), "review_model": args.model,
    }
    atomic_json(args.output / "flux-review-summary.json", result)
    return result


def allocate_flux(args: argparse.Namespace) -> dict[str, Any]:
    needs = {row["slot_id"]: row for row in load_jsonl(args.output / "generation-needs.jsonl")}
    accepted = {row["slot_id"]: row for row in load_jsonl(args.output / "flux-selected.jsonl")}
    gpt_needs = [row for slot, row in needs.items() if slot not in accepted]
    atomic_jsonl(args.output / "gpt-needs-round1.jsonl", gpt_needs)
    result = {
        "flux_needed": len(needs), "flux_accepted": len(accepted),
        "gpt_image_2_needed": len(gpt_needs), "created_at": now(),
    }
    atomic_json(args.output / "flux-allocation-summary.json", result)
    return result


def generate_gpt(args: argparse.Namespace, round_index: int) -> dict[str, Any]:
    needs_path = args.output / f"gpt-needs-round{round_index}.jsonl"
    needs = load_jsonl(needs_path)
    if args.slots:
        requested = set(args.slots)
        available = {row["slot_id"] for row in needs}
        unknown = sorted(requested - available)
        if unknown:
            raise ValueError(f"requested GPT slots are not in the round-{round_index} need ledger: {unknown}")
        needs = [row for row in needs if row["slot_id"] in requested]
    queue = {row["slot_id"]: row for row in load_jsonl(args.output / "generation-queue.jsonl")}
    corrections = {}
    if round_index > 1:
        corrections = {
            row["slot_id"]: row.get("luna_rationale", "")
            for row in load_jsonl(args.output / f"gpt-round{round_index - 1}-reviewed.jsonl")
            if row["luna_verdict"] == "reject"
        }
    result_dir = args.output / f"gpt-round{round_index}-results"
    result_dir.mkdir(parents=True, exist_ok=True)

    def one(need: dict[str, Any]) -> dict[str, Any]:
        durable = result_dir / f"{need['slot_id']}.json"
        if durable.is_file():
            return json.loads(durable.read_text(encoding="utf-8"))
        source = queue[need["slot_id"]]
        prompt = (
            "Use case: photorealistic-natural. Asset type: image-grounded vocabulary teaching example. "
            f"Primary request: {source['visual_contract']} "
            f"Intended meaning: {source['teaching_sense']} "
            "Composition: one coherent natural scene with the teaching evidence large, central, and immediately readable. "
            "Constraints: realistic anatomy and object structure; no text, labels, logos, borders, watermark, diagram, or collage."
        )
        if correction := corrections.get(need["slot_id"]):
            prompt += f" Correct the prior failure explicitly: {correction}"
        job_id = f"c36-prereq-{need['slot_id']}-gpt{round_index}"
        generated = generate_one(
            {
                "job_id": job_id, "assignment_id": job_id, "provider_attempt": round_index,
                "flux_attempt_id": "campaign36-prerequisite-flux", "concept_ids": [need["commission_id"]],
                "words": [need["display_label"]], "prompt": prompt, "status": "reserved",
            },
            root=args.output / f"gpt-image-round{round_index}", repo=args.repo,
            codex=args.codex, model=args.generation_model, timeout=args.generation_timeout,
        )
        if generated["status"] == "generated":
            image = Path(generated["image"])
            row = {
                **need, "candidate_id": f"gpt{round_index}-{need['slot_id']}",
                "local_path": str(image), "sha256": file_digest(image), "provider": "gpt-image-2",
                "generation_prompt": prompt, "generation_stage": f"gpt_image_round_{round_index}",
                "generation_status": "generated",
            }
        else:
            row = {**need, "generation_status": "failed", "generation_error": generated.get("error")}
        atomic_json(durable, row)
        return row

    rows = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(one, need): need["slot_id"] for need in needs}
        for future in as_completed(futures):
            rows.append(future.result())
            print(f"generated GPT round {round_index} {futures[future]}", flush=True)
    rows.sort(key=lambda row: (row["commission_order"], row["exposure_index"]))
    generated_rows = [row for row in rows if row["generation_status"] == "generated"]
    atomic_jsonl(args.output / f"gpt-round{round_index}-candidates.jsonl", generated_rows)
    result = {
        "round": round_index, "needed": len(needs), "generated": len(generated_rows),
        "failed": len(needs) - len(generated_rows), "created_at": now(),
    }
    atomic_json(args.output / f"gpt-round{round_index}-generation-summary.json", result)
    return result


def review_gpt(args: argparse.Namespace, round_index: int) -> dict[str, Any]:
    contracts = {row["commission_id"]: row for row in load_jsonl(args.contracts)}
    by_contract: dict[str, list[dict[str, Any]]] = {}
    for row in load_jsonl(args.output / f"gpt-round{round_index}-candidates.jsonl"):
        by_contract.setdefault(row["commission_id"], []).append(row)

    def one(contract_id: str) -> list[dict[str, Any]]:
        rows = sorted(by_contract[contract_id], key=lambda row: row["exposure_index"])
        return run_review(contracts[contract_id], rows, round_index=round_index, args=args, stage=f"gpt{round_index}")

    reviewed = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {executor.submit(one, contract_id): contract_id for contract_id in by_contract}
        for future in as_completed(futures):
            reviewed.extend(future.result())
            print(f"reviewed GPT round {round_index} {futures[future]}", flush=True)
    reviewed.sort(key=lambda row: (row["commission_order"], row["exposure_index"]))
    atomic_jsonl(args.output / f"gpt-round{round_index}-reviewed.jsonl", reviewed)
    accepted = [row for row in reviewed if row["luna_verdict"] == "accept"]
    atomic_jsonl(args.output / f"gpt-round{round_index}-selected.jsonl", [{**row, "selection_stage": f"luna_accepted_gpt_image_2_round_{round_index}"} for row in accepted])
    result = {"round": round_index, "reviewed": len(reviewed), "accepted": len(accepted), "rejected": len(reviewed) - len(accepted), "created_at": now()}
    atomic_json(args.output / f"gpt-round{round_index}-review-summary.json", result)
    return result


def allocate_gpt(args: argparse.Namespace, round_index: int) -> dict[str, Any]:
    needs = {row["slot_id"]: row for row in load_jsonl(args.output / f"gpt-needs-round{round_index}.jsonl")}
    accepted = {row["slot_id"]: row for row in load_jsonl(args.output / f"gpt-round{round_index}-selected.jsonl")}
    override_path = args.output / "human-overrides.jsonl"
    if override_path.is_file():
        accepted.update({
            row["slot_id"]: row for row in load_jsonl(override_path)
            if row["slot_id"] in needs
        })
    remaining = [row for slot, row in needs.items() if slot not in accepted]
    atomic_jsonl(args.output / f"gpt-needs-round{round_index + 1}.jsonl", remaining)
    result = {"round": round_index, "needed": len(needs), "accepted": len(accepted), "remaining": len(remaining), "created_at": now()}
    atomic_json(args.output / f"gpt-round{round_index}-allocation-summary.json", result)
    return result


def finalize(args: argparse.Namespace) -> dict[str, Any]:
    contracts = load_jsonl(args.contracts)
    ledgers = [
        args.output / "local-selected.jsonl", args.output / "metadata-selected.jsonl",
        args.output / "flux-selected.jsonl", args.output / "gpt-round1-selected.jsonl",
        args.output / "gpt-round2-selected.jsonl",
    ]
    rows = [row for path in ledgers if path.is_file() for row in load_jsonl(path)]
    by_slot: dict[str, dict[str, Any]] = {}
    for row in rows:
        slot = row["slot_id"]
        if slot in by_slot:
            raise ValueError(f"multiple accepted assets for {slot}")
        by_slot[slot] = row
    override_path = args.output / "human-overrides.jsonl"
    if override_path.is_file():
        for row in load_jsonl(override_path):
            by_slot[row["slot_id"]] = row
    expected = {
        f"{contract['commission_id']}-i{exposure:02d}"
        for contract in contracts for exposure in range(1, 11)
    }
    missing = sorted(expected - set(by_slot))
    extra = sorted(set(by_slot) - expected)
    if missing or extra:
        raise ValueError(f"prerequisite image set incomplete: missing={len(missing)} extra={len(extra)}")
    current_hashes = Counter(str(row.get("sha256") or row.get("asset_sha256")) for row in current_assets(args))
    current_hashes.update(row["sha256"] for row in by_slot.values())
    if max(current_hashes.values(), default=0) > 4:
        raise ValueError("final prerequisite assets exceed the four-use hash cap")
    contract_by_id = {row["commission_id"]: row for row in contracts}
    final_rows = []
    stable_root = args.store / "blobs/ninereeds_campaign36_prerequisites_v1"
    for order, contract in enumerate(contracts, 1):
        for exposure in range(1, 11):
            slot = f"{contract['commission_id']}-i{exposure:02d}"
            row = by_slot[slot]
            source = Path(row["local_path"])
            if not source.is_file() or file_digest(source) != row["sha256"]:
                raise ValueError(f"selected source file/hash invalid for {slot}")
            extension = source.suffix.lower() if source.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"} else ".img"
            target = stable_root / str(row.get("provider") or row.get("source") or "retrieved") / f"{row['sha256']}{extension}"
            target.parent.mkdir(parents=True, exist_ok=True)
            if not target.exists():
                temporary = target.with_suffix(target.suffix + ".partial")
                shutil.copyfile(source, temporary)
                if file_digest(temporary) != row["sha256"]:
                    raise ValueError(f"stable copy failed for {slot}")
                temporary.replace(target)
            final_rows.append({
                **row, "schema_version": SCHEMA_VERSION, "prerequisite_contract_id": f"prereq-{contract['commission_id']}",
                "commission_order": order, "display_label": contract["display_label"],
                "lemma": contract["lemma"], "part_of_speech": contract["part_of_speech"],
                "teaching_sense": contract["teaching_sense"], "visual_contract": contract["visual_contract"],
                "local_path": str(target), "sequence_position": (order - 1) * 10 + exposure,
            })
    final_contracts = [{
        **contract, "prerequisite_contract_id": f"prereq-{contract['commission_id']}",
        "commission_order": order, "image_slots": 10,
    } for order, contract in enumerate(contracts, 1)]
    final_root = args.output / "final-v1"
    atomic_jsonl(final_root / "teaching-contracts.jsonl", final_contracts)
    atomic_jsonl(final_root / "accepted-assets.jsonl", final_rows)
    provider_counts = Counter(row.get("selection_stage", row.get("provider", "unknown")) for row in final_rows)
    result = {
        "contracts": len(final_contracts), "assets": len(final_rows), "images_per_contract": 10,
        "provider_counts": dict(sorted(provider_counts.items())),
        "max_combined_hash_reuse": max(current_hashes.values(), default=0),
        "unresolved_slots": 0, "training_ready": True, "created_at": now(),
    }
    atomic_json(final_root / "summary.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("local-shortlist", "review-local", "allocate-local", "metadata-shortlist", "download-metadata", "review-metadata", "allocate-metadata", "prepare-generation", "flux-status", "sync-flux", "review-flux", "allocate-flux", "generate-gpt1", "review-gpt1", "allocate-gpt1", "generate-gpt2", "review-gpt2", "allocate-gpt2", "finalize"))
    parser.add_argument("--contracts", type=Path, default=DEFAULT_CONTRACTS)
    parser.add_argument("--current-assets", type=Path, default=DEFAULT_CURRENT_ASSETS)
    parser.add_argument("--additional-current-assets", type=Path, action="append", default=[])
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--codex", type=Path, default=DEFAULT_CODEX)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--candidates-per-contract", type=int, default=60)
    parser.add_argument("--sheet-size", type=int, default=30)
    parser.add_argument("--accept-buffer", type=int, default=12)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument("--metadata-multiplier", type=int, default=5)
    parser.add_argument("--metadata-candidates-per-contract", type=int, default=60)
    parser.add_argument("--download-workers", type=int, default=32)
    parser.add_argument("--download-timeout", type=int, default=45)
    parser.add_argument("--remote", default="ninereeds-trainbox")
    parser.add_argument("--remote-root", default="/mnt/ninereeds-runtime/visual/campaign36-prerequisites-v1")
    parser.add_argument("--repo", type=Path, default=Path("/home/aomukai/Ninereeds"))
    parser.add_argument("--generation-model", default="gpt-5.6-luna")
    parser.add_argument("--generation-timeout", type=int, default=1200)
    parser.add_argument("--slots", nargs="+")
    parser.add_argument("--store", type=Path, default=Path("/media/aomukai/FILES/Ninereeds/image-corpus"))
    args = parser.parse_args()
    if args.command == "local-shortlist":
        result = local_shortlist(args)
    elif args.command == "review-local":
        result = review_local(args)
    elif args.command == "allocate-local":
        result = allocate_local(args)
    elif args.command == "metadata-shortlist":
        result = metadata_shortlist(args)
    elif args.command == "download-metadata":
        result = download_metadata(args)
    elif args.command == "review-metadata":
        result = review_metadata(args)
    elif args.command == "allocate-metadata":
        result = allocate_metadata(args)
    elif args.command == "prepare-generation":
        result = prepare_generation(args)
    elif args.command == "flux-status":
        result = flux_status(args)
    elif args.command == "sync-flux":
        result = sync_flux(args)
    elif args.command == "review-flux":
        result = review_flux(args)
    elif args.command == "allocate-flux":
        result = allocate_flux(args)
    elif args.command == "generate-gpt1":
        result = generate_gpt(args, 1)
    elif args.command == "review-gpt1":
        result = review_gpt(args, 1)
    elif args.command == "allocate-gpt1":
        result = allocate_gpt(args, 1)
    elif args.command == "generate-gpt2":
        result = generate_gpt(args, 2)
    elif args.command == "review-gpt2":
        result = review_gpt(args, 2)
    elif args.command == "allocate-gpt2":
        result = allocate_gpt(args, 2)
    else:
        result = finalize(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
