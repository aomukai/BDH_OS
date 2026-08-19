"""Profile and bundle Campaign 35 still-image gaps into multi-claim Flux scenes."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import time
from typing import Any, Iterable
import urllib.request


ANCHORS = {
    "home_interior", "kitchen_food", "garden_plants", "outdoor_nature", "animals",
    "people_social", "body_health", "clothing", "school_learning", "office_work",
    "tools_making", "transport_street", "buildings_places", "sports_play",
    "water_weather", "science_math", "objects_still_life", "technology",
    "art_music", "commerce_money",
}
ROLES = {
    "subject", "object", "attribute", "action", "relation", "quantity", "state",
    "environment", "symbol_or_label",
}
FALLBACK_ANCHORS = ["objects_still_life", "home_interior", "school_learning"]


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def batches(rows: list[dict[str, Any]], size: int) -> list[list[dict[str, Any]]]:
    return [rows[index:index + size] for index in range(0, len(rows), size)]


def prompt(rows: list[dict[str, Any]]) -> str:
    compact = [{
        "concept_id": row["concept_id"], "word": row["word"],
        "missing_slots": row["missing_slots"],
        "accepted_examples": row.get("accepted_examples", []),
        "rejected_generated_examples": row.get("rejected_generated_examples", []),
        "specialist_hint": row.get("specialist_hint", ""),
        "curriculum_excerpt": row.get("curriculum_excerpt", "")[:500],
    } for row in rows]
    return f"""Profile concrete visual teaching claims for later scene bundling. This is Campaign
35 M2 for Ninereeds: each exposure contains one target English word plus one image, with no
explanatory caption and no assumed pretrained world knowledge. Each word needs ten distinct
positive examples. An image must directly teach the target word through visible pixels;
association, cultural shorthand, and visible text spelling the target are insufficient. Existing
accepted examples show the intended visual sense. For each concept choose exactly three useful
scene anchors from {sorted(ANCHORS)}, one visual_role from {sorted(ROLES)}, a concise visible
criterion, and a concrete Flux prompt fragment. Set solo_only true only when combining the claim
with unrelated teaching targets would make it ambiguous. Do not drop or add IDs.
Rejected generated examples are evidence from earlier Flux cycles. Explicitly avoid their failed
scene, framing, scale, or evidence strategy. Propose a materially different visible treatment;
do not merely paraphrase the rejected prompt.
When a specialist_hint is present it captures a reviewer-discovered distinction and is mandatory.

Return JSON only:
{{"profiles":[{{"concept_id":"...","scene_anchors":["...","...","..."],
"visual_role":"...","visible_criterion":"...","prompt_fragment":"...",
"solo_only":false}}]}}

ITEMS:
{json.dumps(compact, ensure_ascii=False)}"""


def request_profiles(endpoint: str, token: str, model: str, rows: list[dict[str, Any]], retries: int) -> list[dict[str, Any]]:
    expected = {row["concept_id"] for row in rows}
    body = json.dumps({
        "model": model, "temperature": 0, "max_tokens": 5000,
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
        "messages": [{"role": "user", "content": prompt(rows)}],
    }).encode()
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            request = urllib.request.Request(endpoint, data=body, headers={
                "Authorization": f"Bearer {token}", "Content-Type": "application/json",
            })
            with urllib.request.urlopen(request, timeout=180) as response:
                document = json.load(response)
            profiles = json.loads(document["choices"][0]["message"]["content"])["profiles"]
            if {row.get("concept_id") for row in profiles} != expected:
                raise ValueError("profile IDs differ from requested batch")
            for row in profiles:
                anchors = row.get("scene_anchors")
                valid_anchors = []
                if isinstance(anchors, list):
                    valid_anchors = list(dict.fromkeys(anchor for anchor in anchors if anchor in ANCHORS))
                for fallback in FALLBACK_ANCHORS:
                    if len(valid_anchors) == 3:
                        break
                    if fallback not in valid_anchors:
                        valid_anchors.append(fallback)
                row["scene_anchors"] = valid_anchors[:3]
                if row.get("visual_role") not in ROLES:
                    row["visual_role"] = "attribute"
                if not str(row.get("visible_criterion") or "").strip() or not str(row.get("prompt_fragment") or "").strip():
                    raise ValueError(f"missing visual detail for {row.get('concept_id')}")
                row["solo_only"] = bool(row.get("solo_only"))
                row["model"] = model
            return profiles
        except Exception as exc:
            last_error = exc
            if attempt + 1 < retries:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"profile batch failed: {last_error}")


def compatible(anchor: str, chosen: list[dict[str, Any]], candidate: dict[str, Any]) -> bool:
    if candidate["solo_only"] or any(row["solo_only"] for row in chosen):
        return False
    if anchor not in candidate["scene_anchors"]:
        return False
    if candidate["word"] in {row["word"] for row in chosen}:
        return False
    # Crowding several abstract labels or several spatial relations into one frame is rarely clear.
    roles = Counter(row["visual_role"] for row in chosen)
    if candidate["visual_role"] in {"relation", "symbol_or_label"} and roles[candidate["visual_role"]]:
        return False
    return True


def make_bundles(rows: list[dict[str, Any]], profiles: dict[str, dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    active = {row["concept_id"]: int(row["missing_slots"]) for row in rows}
    details = {row["concept_id"]: {**row, **profiles[row["concept_id"]]} for row in rows}
    grouped: dict[tuple[str, tuple[str, ...]], int] = defaultdict(int)
    while active:
        first_id = max(active, key=lambda item: (active[item], -details[item]["ordinal"]))
        first = details[first_id]
        best: tuple[int, int, str, list[dict[str, Any]]] | None = None
        for anchor in first["scene_anchors"]:
            pool = [details[item] for item in active if item != first_id and compatible(anchor, [first], details[item])]
            pool.sort(key=lambda row: (
                row["visual_role"] == first["visual_role"], -active[row["concept_id"]], row["ordinal"],
            ))
            chosen = [first]
            for candidate in pool:
                if len(chosen) >= cap:
                    break
                if compatible(anchor, chosen, candidate):
                    chosen.append(candidate)
            score = (len(chosen), sum(active[row["concept_id"]] for row in chosen), anchor, chosen)
            if best is None or score[:2] > best[:2]:
                best = score
        assert best is not None
        anchor, chosen = best[2], best[3]
        ids = tuple(sorted((row["concept_id"] for row in chosen), key=lambda item: details[item]["ordinal"]))
        variants = min(active[item] for item in ids)
        grouped[(anchor, ids)] += variants
        for item in ids:
            active[item] -= variants
            if not active[item]:
                del active[item]
    bundles = []
    for index, ((anchor, ids), variants) in enumerate(grouped.items(), 1):
        bundles.append({
            "bundle_id": f"scene-{index:04d}", "scene_anchor": anchor,
            "concept_ids": list(ids), "words": [details[item]["word"] for item in ids],
            "variant_count": variants, "assignment_count": variants * len(ids),
            "claims": [{
                "concept_id": item, "word": details[item]["word"],
                "visual_role": details[item]["visual_role"],
                "visible_criterion": details[item]["visible_criterion"],
                "prompt_fragment": details[item]["prompt_fragment"],
            } for item in ids],
            "status": "draft_requires_deepseek_prompt_composition_and_validation",
        })
    return bundles


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--endpoint", default="https://api.deepseek.com/chat/completions")
    parser.add_argument("--token-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--retries", type=int, default=3)
    parser.add_argument("--reuse-cap", type=int, default=4)
    args = parser.parse_args(list(argv) if argv is not None else None)
    token = os.environ.get(args.token_env)
    if not token:
        raise ValueError(f"missing token: {args.token_env}")
    all_rows = load_jsonl(args.inventory)
    rows = [row for row in all_rows if row["route"] in {"single_image", "single_image_empirically_demonstrated"}]
    args.output.mkdir(parents=True, exist_ok=True)
    partial = args.output / "profiles.partial.jsonl"
    prior = load_jsonl(partial) if partial.exists() else []
    profiles = {row["concept_id"]: row for row in prior}
    wanted = {row["concept_id"] for row in rows}
    if not set(profiles) <= wanted:
        raise ValueError("profile partial contains concepts outside current inventory")
    remaining = [row for row in rows if row["concept_id"] not in profiles]
    work = batches(remaining, args.batch_size)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(request_profiles, args.endpoint, token, args.model, batch, args.retries): batch for batch in work}
        for completed, future in enumerate(as_completed(futures), 1):
            result = future.result()
            with partial.open("a", encoding="utf-8") as handle:
                for row in result:
                    profiles[row["concept_id"]] = row
                    handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            print(f"profiled {completed}/{len(work)} batches concepts={len(profiles)}/{len(rows)}", flush=True)
    if set(profiles) != wanted:
        raise RuntimeError("profile partition incomplete")
    ordered_profiles = [profiles[row["concept_id"]] for row in rows]
    write_jsonl(args.output / "scene_profiles.jsonl", ordered_profiles)
    bundles = make_bundles(rows, profiles, args.reuse_cap)
    write_jsonl(args.output / "bundle_drafts.jsonl", bundles)
    slots = sum(row["missing_slots"] for row in rows)
    images = sum(row["variant_count"] for row in bundles)
    summary = {
        "schema_version": "ninereeds_campaign35_scene_bundle_plan_v1",
        "concepts": len(rows), "assignment_slots": slots, "draft_blueprints": len(bundles),
        "planned_images": images, "average_claims_per_image": slots / images,
        "reuse_cap": args.reuse_cap,
        "status": "draft_requires_deepseek_prompt_composition_and_bundle_validation",
    }
    (args.output / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
