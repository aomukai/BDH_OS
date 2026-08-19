"""Catalog Hugging Face image datasets and rank metadata sources for a wishlist.

This tool downloads dataset-card metadata only.  It never treats a dataset card,
caption, or label as pixel evidence and never downloads image payloads.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import time
from typing import Any, Iterable
import urllib.error
import urllib.parse
import urllib.request


SCHEMA_VERSION = "ninereeds_huggingface_image_dataset_catalog_v1"
RANKING_VERSION = "ninereeds_huggingface_residual_source_ranking_v1"
DEFAULT_ENDPOINT = "https://huggingface.co/api/datasets"
USER_AGENT = "Ninereeds-image-metadata-catalog/1.0"

TEXT_HINTS = {
    "caption", "captions", "text", "description", "descriptions", "sentence",
    "sentences", "label", "labels", "class", "classes", "category", "categories",
    "attribute", "attributes", "relation", "relations", "relationship",
    "relationships", "action", "actions", "verb", "verbs", "noun", "nouns",
    "object", "objects", "phrase", "phrases", "answer", "answers", "question",
}
PIXEL_LOCATOR_HINTS = {
    "url", "urls", "image-url", "image-urls", "image-path", "image-paths", "path",
    "paths", "file", "filename", "file-name", "photo-url", "download-url",
}
POSITIVE_TASKS = {
    "image-to-text": 8,
    "object-detection": 7,
    "image-classification": 5,
    "visual-question-answering": 4,
    "text-to-image": 2,
}
LOW_VALUE_TERMS = {
    "ocr", "document", "documents", "pdf", "handwriting", "formula", "latex",
    "medical", "radiology", "xray", "x-ray", "histopathology", "retinal", "ct-scan",
    "satellite", "remote-sensing", "aerial", "lidar", "point-cloud",
    "robot", "robotics", "trajectory", "gui", "screenshot", "website", "chart",
    "diagram", "synthetic", "generated", "benchmark", "eval", "evaluation",
}
GENERAL_WORLD_TERMS = {
    "caption", "visual-genome", "coco", "flickr", "open-images", "scene", "object",
    "attribute", "action", "relationship", "human-object", "everyday", "in-the-wild",
}


def now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
        handle.flush()
    return count


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def link_next(header: str | None) -> str | None:
    if not header:
        return None
    for part in header.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="next"', part)
        if match:
            return match.group(1)
    return None


def request_json(url: str, *, attempts: int = 5, timeout: float = 60) -> tuple[Any, str | None]:
    error: Exception | None = None
    for attempt in range(attempts):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response), link_next(response.headers.get("Link"))
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            error = exc
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in {429, 500, 502, 503, 504}:
                raise
            if attempt + 1 < attempts:
                time.sleep(min(2 ** attempt, 20))
    assert error is not None
    raise error


def walk_features(value: Any, prefix: str = "") -> Iterable[tuple[str, str, Any]]:
    if isinstance(value, list):
        for entry in value:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("name", "")).strip()
            path = ".".join(part for part in (prefix, name) if part)
            dtype = entry.get("dtype") or entry.get("_type") or entry.get("feature", {}).get("dtype")
            if dtype:
                yield path, str(dtype).casefold(), entry
            nested = entry.get("feature") or entry.get("features")
            if nested:
                yield from walk_features(nested, path)
    elif isinstance(value, dict):
        for name, entry in value.items():
            path = ".".join(part for part in (prefix, str(name)) if part)
            if isinstance(entry, dict):
                dtype = entry.get("dtype") or entry.get("_type")
                if dtype:
                    yield path, str(dtype).casefold(), entry
                nested = entry.get("feature") or entry.get("features")
                if nested:
                    yield from walk_features(nested, path)


def parse_declared_count(value: Any) -> int:
    if value in {None, ""}:
        return 0
    if isinstance(value, (int, float)):
        return int(value)
    match = re.search(r"\d[\d,._ ]*", str(value))
    if not match:
        return 0
    return int(re.sub(r"[^0-9]", "", match.group(0)) or 0)


def normalize_dataset(raw: dict[str, Any]) -> dict[str, Any]:
    card = raw.get("cardData") or {}
    infos = card.get("dataset_info") or []
    if isinstance(infos, dict):
        infos = [infos]
    feature_rows: list[tuple[str, str, Any]] = []
    examples = 0
    for info in infos:
        feature_rows.extend(walk_features(info.get("features") or []))
        for split in info.get("splits") or []:
            examples += parse_declared_count(split.get("num_examples"))
    image_fields = sorted({path for path, dtype, _ in feature_rows if dtype == "image"})
    metadata_fields = set()
    pixel_locator_fields = set()
    class_names = set()
    for path, dtype, entry in feature_rows:
        leaf = path.rsplit(".", 1)[-1].casefold().replace("_", "-")
        words = set(re.split(r"[^a-z0-9]+", leaf))
        if dtype == "string" and (leaf in PIXEL_LOCATOR_HINTS or "url" in words or "path" in words):
            pixel_locator_fields.add(path)
        if dtype in {"string", "classlabel", "translation"} and (words & TEXT_HINTS or dtype == "classlabel"):
            metadata_fields.add(path)
        if dtype == "classlabel":
            class_names.update(str(name) for name in (entry.get("names") or []) if name)
    licenses = card.get("license") or []
    if isinstance(licenses, str):
        licenses = [licenses]
    tasks = card.get("task_categories") or []
    if isinstance(tasks, str):
        tasks = [tasks]
    sizes = card.get("size_categories") or []
    if isinstance(sizes, str):
        sizes = [sizes]
    tags = card.get("tags") or []
    if isinstance(tags, str):
        tags = [tags]
    languages = card.get("language") or []
    if isinstance(languages, str):
        languages = [languages]
    return {
        "schema_version": SCHEMA_VERSION,
        "dataset_id": raw.get("id"),
        "author": raw.get("author"),
        "sha": raw.get("sha"),
        "last_modified": raw.get("lastModified"),
        "downloads": int(raw.get("downloads") or 0),
        "likes": int(raw.get("likes") or 0),
        "trending_score": float(raw.get("trendingScore") or 0),
        "gated": raw.get("gated", False),
        "private": bool(raw.get("private", False)),
        "disabled": bool(raw.get("disabled", False)),
        "pretty_name": card.get("pretty_name"),
        "licenses": sorted(set(map(str, licenses))),
        "task_categories": sorted(set(map(str, tasks))),
        "size_categories": sorted(set(map(str, sizes))),
        "tags": sorted(set(map(str, tags))),
        "languages": sorted(set(map(str, languages))),
        "annotations_creators": card.get("annotations_creators") or [],
        "source_datasets": card.get("source_datasets") or [],
        "num_examples_declared": examples or None,
        "image_fields": image_fields,
        "pixel_locator_fields": sorted(pixel_locator_fields),
        "metadata_fields": sorted(metadata_fields),
        "class_names": sorted(class_names),
        "metadata_searchable_structure": bool(
            (image_fields or pixel_locator_fields) and (metadata_fields or class_names)
        ),
        "cataloged_at": now(),
    }


def initial_url(endpoint: str, page_size: int) -> str:
    parameters = [
        ("filter", "modality:image,library:datasets"),
        ("limit", str(page_size)),
        ("sort", "downloads"), ("direction", "-1"),
        ("expand", "downloads"), ("expand", "likes"), ("expand", "trendingScore"),
        ("expand", "gated"), ("expand", "private"), ("expand", "disabled"),
        ("expand", "author"), ("expand", "sha"), ("expand", "lastModified"),
        ("expand", "cardData"),
    ]
    return endpoint + "?" + urllib.parse.urlencode(parameters)


def crawl(output: Path, *, endpoint: str = DEFAULT_ENDPOINT, page_size: int = 100, max_pages: int | None = None) -> dict[str, Any]:
    output.mkdir(parents=True, exist_ok=True)
    catalog = output / "catalog.jsonl"
    state_path = output / "crawl-state.json"
    if state_path.is_file():
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("schema_version") != SCHEMA_VERSION:
            raise ValueError("catalog crawl state has an unknown schema")
    else:
        state = {
            "schema_version": SCHEMA_VERSION, "status": "active", "pages": 0,
            "datasets": 0, "next_url": initial_url(endpoint, page_size), "created_at": now(),
        }
        atomic_json(state_path, state)
    if state.get("status") == "complete":
        return state
    while state.get("next_url") and (max_pages is None or state["pages"] < max_pages):
        rows, next_url = request_json(state["next_url"])
        normalized = [normalize_dataset(row) for row in rows]
        appended = append_jsonl(catalog, normalized)
        state.update({
            "pages": state["pages"] + 1, "datasets": state["datasets"] + appended,
            "next_url": next_url, "updated_at": now(),
        })
        if not next_url:
            state.update({"status": "complete", "completed_at": now()})
        atomic_json(state_path, state)
    return state


def tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z][a-z0-9-]+", value.casefold()) if len(token) > 1}


def score_dataset(row: dict[str, Any], needs: Counter[str]) -> tuple[float, list[str], list[str]]:
    score = 0.0
    reasons: list[str] = []
    if row.get("private") or row.get("disabled"):
        return -1000.0, ["private_or_disabled"], []
    if row.get("gated") not in {False, None}:
        score -= 8
        reasons.append("gated")
    if row.get("licenses"):
        score += 4
        reasons.append("declared_license")
    else:
        score -= 5
        reasons.append("missing_license")
    if row.get("image_fields"):
        score += 8
        reasons.append("declared_image_field")
    elif row.get("pixel_locator_fields"):
        score += 6
        reasons.append("declared_pixel_locator")
    if row.get("metadata_fields"):
        score += min(10, 4 + len(row["metadata_fields"]))
        reasons.append("searchable_text_or_label_fields")
    if row.get("class_names"):
        score += 5
        reasons.append("declared_class_names")
    task_scores = [POSITIVE_TASKS.get(task, 0) for task in row.get("task_categories") or []]
    score += max(task_scores, default=0)
    examples = int(row.get("num_examples_declared") or 0)
    if examples >= 10_000:
        score += min(6, math.log10(examples) - 2)
    downloads = int(row.get("downloads") or 0)
    likes = int(row.get("likes") or 0)
    score += min(8, math.log10(downloads + 1) * 1.5)
    score += min(4, math.log10(likes + 1))
    haystack = " ".join([
        str(row.get("dataset_id") or ""), str(row.get("pretty_name") or ""),
        " ".join(row.get("tags") or []), " ".join(row.get("metadata_fields") or []),
        " ".join(row.get("class_names") or []),
    ])
    haystack_tokens = tokens(haystack)
    low = sorted(haystack_tokens & LOW_VALUE_TERMS)
    if low:
        score -= min(20, 4 * len(low))
        reasons.append("domain_penalty:" + ",".join(low[:5]))
    general = sorted(haystack_tokens & GENERAL_WORLD_TERMS)
    if general:
        score += min(10, 2 * len(general))
        reasons.append("general_world_signals:" + ",".join(general[:5]))
    concept_hits = sorted(word for word in needs if word.casefold() in haystack_tokens)
    if concept_hits:
        weighted = sum(needs[word] for word in concept_hits)
        score += min(20, len(concept_hits) * 0.5 + math.log2(weighted + 1))
        reasons.append("declared_vocabulary_overlap")
    searchable = bool(row.get("metadata_searchable_structure")) or bool(
        row.get("metadata_fields") and "image-to-text" in (row.get("task_categories") or [])
    )
    if not searchable:
        score -= 20
        reasons.append("no_declared_searchable_image_metadata_pair")
    return round(score, 4), reasons, concept_hits


def rank(catalog: Path, needs_path: Path, output: Path, *, limit: int = 500) -> dict[str, Any]:
    needs_rows = load_jsonl(needs_path)
    needs = Counter(str(row.get("word") or row.get("concept") or "").casefold() for row in needs_rows)
    needs.pop("", None)
    ranked = []
    for row in load_jsonl(catalog):
        score, reasons, concept_hits = score_dataset(row, needs)
        ranked.append({**row, "source_score": score, "score_reasons": reasons, "declared_concept_hits": concept_hits})
    ranked.sort(key=lambda row: (-row["source_score"], -row.get("downloads", 0), row["dataset_id"]))
    candidates = ranked[:limit]
    output.mkdir(parents=True, exist_ok=True)
    (output / "candidates.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    summary = {
        "schema_version": RANKING_VERSION,
        "catalog_datasets": len(ranked), "ranked_candidates": len(candidates),
        "residual_slots": len(needs_rows), "residual_words": len(needs),
        "searchable_structures": sum(bool(row.get("metadata_searchable_structure")) for row in ranked),
        "status": "metadata_source_candidates_require_schema_license_and_pixel_access_validation",
        "created_at": now(),
    }
    atomic_json(output / "summary.json", summary)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    crawl_parser = sub.add_parser("crawl")
    crawl_parser.add_argument("--output", type=Path, required=True)
    crawl_parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    crawl_parser.add_argument("--page-size", type=int, default=100)
    crawl_parser.add_argument("--max-pages", type=int)
    rank_parser = sub.add_parser("rank")
    rank_parser.add_argument("--catalog", type=Path, required=True)
    rank_parser.add_argument("--needs", type=Path, required=True)
    rank_parser.add_argument("--output", type=Path, required=True)
    rank_parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    if args.command == "crawl":
        result = crawl(args.output, endpoint=args.endpoint, page_size=args.page_size, max_pages=args.max_pages)
    else:
        result = rank(args.catalog, args.needs, args.output, limit=args.limit)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
