"""Build Campaign 35's word-level 25,000-image curriculum proposal.

The material unit is a word exposure, not an M1 sentence.  Every one of the
2,500 ordered M1 concepts receives exactly ten distinct image slots.  Registry
text is retrieval evidence only; proposals remain pending pixel verification.
The verified caption is preserved now because M3 and M5 reuse the exact M2
images and order with that caption enabled.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Any


DEFAULT_DB = Path("training_data/image_registry/registry.sqlite3")
DEFAULT_CURRICULUM = Path(
    "config/mission_hub/campaign_material/campaign35/curriculum.jsonl"
)
EXPOSURES_PER_WORD = 10
SCHEMA_VERSION = "ninereeds_campaign35_word_image_curriculum_proposal_v1"


def _jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _surface_word(concept: str) -> str:
    """Remove curriculum disambiguators without changing the taught word."""
    value = re.sub(r"\s+\d+$", "", concept).strip()
    if not value:
        raise ValueError(f"concept has no teachable surface word: {concept!r}")
    return value


def _fts_query(word: str) -> str:
    tokens = re.findall(r"[^\W_]+", word.casefold(), flags=re.UNICODE)
    if not tokens:
        raise ValueError(f"cannot derive registry query from {word!r}")
    return " AND ".join(f'"{token.replace(chr(34), chr(34) * 2)}"' for token in tokens)


def _read_curriculum(path: Path) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    if len(rows) != 2500:
        raise ValueError(f"Campaign 35 requires exactly 2,500 words, found {len(rows)}")
    if [row.get("ordinal") for row in rows] != list(range(1, 2501)):
        raise ValueError("Campaign 35 word ordinals are not exactly 1..2500")
    return rows


def _connect_read_only(path: Path) -> sqlite3.Connection:
    if not path.is_file():
        raise FileNotFoundError(path)
    db = sqlite3.connect(f"file:{path.resolve()}?mode=ro", uri=True, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def _tokens(value: str) -> set[str]:
    return set(re.findall(r"[^\W_]+", value.casefold(), flags=re.UNICODE))


def _load_registry_index(
    db: sqlite3.Connection,
) -> tuple[dict[int, dict[str, Any]], dict[str, set[int]]]:
    """Load the small reviewed registry once instead of issuing 2,500 FTS scans."""
    assets = {
        row["id"]: {
            "asset_id": row["id"], "source": row["source"],
            "source_id": row["source_id"], "path": row["local_path"],
            "sha256": row["sha256"], "width": row["width"], "height": row["height"],
            "caption": None, "evidence": [],
        }
        for row in db.execute(
            """SELECT id,source,source_id,local_path,sha256,width,height FROM asset
               WHERE status='reviewed_usable' AND local_path IS NOT NULL
                 AND sha256 IS NOT NULL ORDER BY id"""
        )
    }
    for row in db.execute(
        "SELECT id,asset_id,kind,text FROM text_record ORDER BY asset_id,id"
    ):
        asset = assets.get(row["asset_id"])
        if asset is None:
            continue
        asset["evidence"].append((row["kind"], row["text"]))
        if row["kind"] == "reviewed_caption":
            asset["caption"] = row["text"]
    for row in db.execute("SELECT asset_id,name FROM label ORDER BY asset_id,name"):
        asset = assets.get(row["asset_id"])
        if asset is not None:
            asset["evidence"].append(("label", row["name"]))
    inverted: dict[str, set[int]] = {}
    for asset_id, asset in assets.items():
        if not asset["caption"]:
            continue
        for kind, text in asset.pop("evidence"):
            for token in _tokens(text):
                inverted.setdefault(token, set()).add(asset_id)
    return assets, inverted


def _candidates(
    assets: dict[int, dict[str, Any]], inverted: dict[str, set[int]],
    word: str, *, limit: int,
) -> list[dict[str, Any]]:
    terms = sorted(_tokens(word))
    if not terms:
        raise ValueError(f"cannot derive registry query from {word!r}")
    matches = [inverted.get(term, set()) for term in terms]
    asset_ids = set.intersection(*matches) if matches else set()
    result: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()
    for asset_id in sorted(asset_ids):
        asset = assets[asset_id]
        if asset["sha256"] in seen_hashes:
            continue
        seen_hashes.add(asset["sha256"])
        result.append({
            **asset,
            "matched_text_kind": "registry_word_index",
            "matched_text": word,
        })
        if len(result) == limit:
            break
    return result


def build_proposal(
    db_path: Path,
    curriculum_path: Path,
    output_root: Path,
    *,
    candidates_per_word: int = 30,
) -> dict[str, Any]:
    if candidates_per_word < EXPOSURES_PER_WORD:
        raise ValueError("candidate pool must allow at least ten images per word")
    curriculum = _read_curriculum(curriculum_path)
    output_root.mkdir(parents=True, exist_ok=True)
    requirements: list[dict[str, Any]] = []
    pools: list[dict[str, Any]] = []
    proposals: list[dict[str, Any]] = []
    wishlist: list[dict[str, Any]] = []

    with _connect_read_only(db_path) as db:
        assets, inverted = _load_registry_index(db)
        for concept in curriculum:
            ordinal = concept["ordinal"]
            word = str(concept.get("teaching_term") or _surface_word(concept["concept"])).strip()
            teaching_sense = str(concept.get("teaching_sense") or concept["concept"]).strip()
            candidates = _candidates(
                assets, inverted, word, limit=candidates_per_word,
            )
            pools.append({
                "ordinal": ordinal,
                "concept": concept["concept"],
                "concept_id": concept["concept_id"],
                "teaching_sense": teaching_sense,
                "word": word,
                "required_images": EXPOSURES_PER_WORD,
                "candidate_count": len(candidates),
                "candidates": candidates,
            })
            for exposure in range(1, EXPOSURES_PER_WORD + 1):
                slot_id = f"c{ordinal:04d}-i{exposure:02d}"
                requirement = {
                    "slot_id": slot_id,
                    "sequence_position": (ordinal - 1) * EXPOSURES_PER_WORD + exposure,
                    "ordinal": ordinal,
                    "concept": concept["concept"],
                    "concept_id": concept["concept_id"],
                    "teaching_sense": teaching_sense,
                    "word": word,
                    "exposure_index": exposure,
                }
                requirements.append(requirement)
                if exposure <= len(candidates):
                    proposals.append({
                        **requirement,
                        **candidates[exposure - 1],
                        "m2_completion": word,
                        "m3_completion": candidates[exposure - 1]["caption"],
                        "verification_status": "pending_luna_word_image_verification",
                    })
                else:
                    wishlist.append({
                        **requirement,
                        "status": "registry_candidate_gap",
                        "next_action": "search_external_metadata_then_flux_as_last_resort",
                    })

    _jsonl(output_root / "requirements.jsonl", requirements)
    _jsonl(output_root / "candidate_pools.jsonl", pools)
    _jsonl(output_root / "selection_proposal.jsonl", proposals)
    _jsonl(output_root / "wishlist.jsonl", wishlist)
    summary = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": "campaign-35-multimodal-foundation-v1",
        "status": "proposal_only_pending_pixel_verification",
        "concept_count": len(curriculum),
        "exposures_per_word": EXPOSURES_PER_WORD,
        "required_images": len(requirements),
        "proposed_images": len(proposals),
        "registry_gap_images": len(wishlist),
        "fully_proposed_words": sum(
            len(row["candidates"]) >= EXPOSURES_PER_WORD for row in pools
        ),
        "words_with_registry_gap": sum(
            len(row["candidates"]) < EXPOSURES_PER_WORD for row in pools
        ),
        "curriculum_sha256": _sha256(curriculum_path),
        "contract": {
            "m2": "same ordered images with the one-word target only",
            "m3": "same ordered images with their verified full captions",
            "m5": "exact replay of M3 from the M4 merge checkpoint",
            "pixel_verification_required": True,
            "metadata_is_retrieval_evidence_not_pixel_proof": True,
        },
    }
    (output_root / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--curriculum", type=Path, default=DEFAULT_CURRICULUM)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidates-per-word", type=int, default=30)
    args = parser.parse_args()
    summary = build_proposal(
        args.db, args.curriculum, args.output,
        candidates_per_word=args.candidates_per_word,
    )
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
