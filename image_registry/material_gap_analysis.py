#!/usr/bin/env python3
"""Build a deterministic registry-first material proposal and residual wishlist.

This is the reusable ``we need X / have Y / must find or create Z`` pass.  It
never writes to the registry or dispatches an acquisition/generation provider.
All proposed assignments remain pending pixel verification.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import sqlite3
from typing import Iterable


REPO = Path(__file__).resolve().parents[1]
OUT = Path()
MATERIAL = Path()
MISSION = Path()
AUDIT = Path()
DB = Path()
TOOL = REPO / "mission_hub/research/visual-material-tool.json"
REQUEST_SCHEMA = REPO / "mission_hub/research/schemas/visual-material-request.schema.json"

SCHEMA = "ninereeds_material_gap_analysis_v1"
VERIFY = "pending_luna_pixel_verification"
CAMPAIGN_ID = ""
EXPECTED_ITEMS: int | None = None
EXPECTED_CONCEPTS: int | None = None
ACTIVE_MISMATCH_ITEM_IDS: set[str] = set()
WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
CLAIM_RE = re.compile(r"Visual interpretation:\s*(.*?)\s*One coherent scene", re.I)
PROMPT_ITEM_RE = re.compile(r"Variation\s+(\d+)\s+for curriculum item\s+(\d+)", re.I)

STOP = {
    "a", "an", "and", "are", "as", "at", "be", "because", "between", "by", "can",
    "does", "for", "from", "has", "have", "here", "in", "into", "is", "it", "its",
    "of", "on", "one", "or", "that", "the", "their", "there", "these", "this", "those",
    "through", "to", "two", "used", "using", "when", "where", "with", "without",
    "appears", "brings", "helps", "happens", "shows", "means", "makes", "allows",
    "describe", "describes", "something", "thing", "things", "example", "examples",
}

ACTIVE_FALSE_POSITIVE_ITEM_IDS: set[str] = set()
ACTIVE_AUDITED_ALTERNATE_ITEM_IDS: set[str] = set()
REVIEW_POLICY_PATH: Path | None = None

# Small auditable equivalence map. Alternate-realization terms additionally come directly
# from each authoritative visual interpretation; no model-generated ontology is used.
SYNONYM_GROUPS = [
    ("car", "automobile", "vehicle"), ("bike", "bicycle", "cycle"),
    ("sofa", "couch"), ("child", "kid", "boy", "girl"), ("baby", "infant"),
    ("person", "human", "people", "man", "woman"), ("airplane", "aeroplane", "aircraft", "plane"),
    ("boat", "ship", "vessel"), ("road", "street", "highway"), ("home", "house"),
    ("cup", "mug"), ("garbage", "trash", "rubbish", "waste"), ("cellphone", "phone", "telephone"),
    ("television", "tv", "monitor", "screen"), ("photo", "photograph", "picture", "image"),
    ("forest", "woods", "woodland"), ("ocean", "sea"), ("stream", "creek"),
    ("rock", "stone"), ("mountain", "peak"), ("flower", "blossom"),
    ("raincoat", "waterproof"), ("sneakers", "trainers", "shoes"), ("pants", "trousers"),
    ("store", "shop"), ("doctor", "physician"), ("teacher", "educator"),
    ("student", "pupil"), ("police", "officer"), ("firefighter", "fireman"),
    ("happy", "joyful", "smiling"), ("sad", "unhappy", "crying"),
    ("angry", "mad"), ("quick", "fast", "rapid"), ("large", "big", "huge"),
    ("small", "little", "tiny"), ("near", "close"), ("far", "distant"),
    ("begin", "start"), ("finish", "end", "complete"), ("purchase", "buy"),
    ("repair", "fix"), ("speak", "talk"), ("listen", "hear"), ("look", "see", "watch"),
    ("run", "jog"), ("jump", "leap"), ("throw", "toss"), ("hold", "carry"),
    ("cut", "slice"), ("build", "construct"), ("choose", "select", "pick"),
    ("container", "box", "bin"), ("refrigerator", "fridge"), ("cabinet", "cupboard"),
    ("stove", "oven", "cooker"), ("yard", "garden"), ("sidewalk", "pavement"),
    ("flashlight", "torch"), ("cookie", "biscuit"), ("candy", "sweet"),
    ("soccer", "football"), ("truck", "lorry"), ("elevator", "lift"),
]
SYNONYMS: dict[str, set[str]] = collections.defaultdict(set)
for group in SYNONYM_GROUPS:
    normalized = set(group)
    for word in group:
        SYNONYMS[word].update(normalized - {word})

ABSTRACT_WORDS = {
    "ability", "absence", "acceptance", "access", "accountability", "accuracy", "advantage",
    "agreement", "allowance", "ambiguity", "attention", "awareness", "balance", "basis",
    "belief", "certainty", "choice", "clarity", "comparison", "competence", "confidence",
    "consistency", "context", "control", "correctness", "decision", "difference", "difficulty",
    "effect", "effort", "equality", "evidence", "experience", "expressing", "fairness",
    "finding", "freedom", "goal", "growth", "idea", "identity", "importance", "independence",
    "information", "intelligence", "intention", "judgment", "knowledge", "meaning", "memory",
    "method", "necessity", "normal", "opinion", "order", "outcome", "pattern", "perfect",
    "possibility", "purpose", "quality", "rate", "reason", "relationship", "relevance",
    "responsibility", "result", "risk", "role", "safety", "sense", "similarity", "skill",
    "solution", "success", "support", "system", "thought", "trust", "truth", "understanding",
    "value", "worth",
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_hash(paths: list[Path]) -> str:
    h = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        h.update(str(path).encode())
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def dump_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")


def lemma(token: str) -> str:
    token = token.casefold()
    if len(token) > 4 and token.endswith("ies"):
        return token[:-3] + "y"
    if len(token) > 5 and token.endswith("ing"):
        root = token[:-3]
        return root[:-1] if len(root) > 2 and root[-1] == root[-2] else root
    if len(token) > 4 and token.endswith("ed"):
        root = token[:-2]
        return root[:-1] if len(root) > 2 and root[-1] == root[-2] else root
    if len(token) > 4 and token.endswith("es"):
        return token[:-2]
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def tokens(text: str) -> set[str]:
    return {lemma(x) for x in WORD_RE.findall(text.casefold()) if len(x) > 1}


def words(text: str) -> list[str]:
    return [lemma(x) for x in WORD_RE.findall(text.casefold()) if len(x) > 1]


def norm(text: str) -> str:
    return " ".join(words(text))


def raw_norm(text: str) -> str:
    return " ".join(x.casefold() for x in WORD_RE.findall(text))


def extract_claim(prompt: str) -> str:
    match = CLAIM_RE.search(prompt)
    if not match:
        raise ValueError(f"missing visual interpretation: {prompt}")
    return match.group(1).strip()


def connect_ro() -> sqlite3.Connection:
    db = sqlite3.connect(f"file:{DB}?mode=ro", uri=True, timeout=60)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA query_only=ON")
    return db


def load_inputs():
    visual_paths = sorted(MATERIAL.glob("visual-batches/*.jsonl"))
    items = []
    for path in visual_paths:
        items.extend(json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line)
    items.sort(key=lambda x: (x["ordinal"], x["example_index"]))
    for item in items:
        item["teaching_claim"] = extract_claim(item["prompt"])
    concepts = [json.loads(line) for line in (MATERIAL / "curriculum.jsonl").read_text(encoding="utf-8").splitlines() if line]
    audit_rows = {}
    for path in sorted((AUDIT / "batches").glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            audit_rows[row["ordinal"]] = row
    return items, concepts, audit_rows, visual_paths


def load_registry(db: sqlite3.Connection):
    assets = {}
    for row in db.execute(
        "SELECT id,source,source_id,split,local_path,sha256,width,height,title,status "
        "FROM asset WHERE status='reviewed_usable' AND local_path IS NOT NULL AND sha256 IS NOT NULL ORDER BY id"
    ):
        assets[row["id"]] = dict(row)
    evidence: dict[int, list[dict]] = collections.defaultdict(list)
    for row in db.execute(
        "SELECT t.asset_id,t.kind,t.text FROM text_record t JOIN asset a ON a.id=t.asset_id "
        "WHERE a.status='reviewed_usable' AND a.local_path IS NOT NULL AND a.sha256 IS NOT NULL ORDER BY t.asset_id,t.id"
    ):
        evidence[row["asset_id"]].append({"kind": row["kind"], "text": row["text"]})
    for asset_id, asset in assets.items():
        if asset["title"]:
            evidence[asset_id].append({"kind": "asset_title", "text": asset["title"]})
    label_map: dict[int, list[str]] = collections.defaultdict(list)
    for row in db.execute(
        "SELECT l.asset_id,l.name FROM label l JOIN asset a ON a.id=l.asset_id "
        "WHERE a.status='reviewed_usable' AND a.local_path IS NOT NULL AND a.sha256 IS NOT NULL "
        "GROUP BY l.asset_id,l.name ORDER BY l.asset_id,l.name"
    ):
        label_map[row["asset_id"]].append(row["name"])
        evidence[row["asset_id"]].append({"kind": "label", "text": row["name"]})
    relationship_map: dict[int, list[str]] = collections.defaultdict(list)
    for row in db.execute(
        "SELECT r.asset_id,r.subject,r.predicate,r.object FROM relationship r JOIN asset a ON a.id=r.asset_id "
        "WHERE a.status='reviewed_usable' AND a.local_path IS NOT NULL AND a.sha256 IS NOT NULL ORDER BY r.asset_id,r.id"
    ):
        text = f'{row["subject"]} {row["predicate"]} {row["object"]}'
        relationship_map[row["asset_id"]].append(text)
        evidence[row["asset_id"]].append({"kind": "relationship", "text": text})
    return assets, evidence, label_map, relationship_map


def make_index(assets: dict, evidence: dict):
    asset_tokens = {}
    inverted: dict[str, set[int]] = collections.defaultdict(set)
    evidence_tokens: dict[int, list[set[str]]] = {}
    for asset_id in assets:
        rows = evidence.get(asset_id, [])
        row_tokens = [tokens(row["text"]) for row in rows]
        merged = set().union(*row_tokens) if row_tokens else set()
        asset_tokens[asset_id] = merged
        evidence_tokens[asset_id] = row_tokens
        for token in merged:
            inverted[token].add(asset_id)
    return asset_tokens, evidence_tokens, inverted


def concept_terms(concept: str) -> tuple[set[str], set[str]]:
    base = tokens(concept)
    semantic = set()
    for token in base:
        semantic.update(SYNONYMS.get(token, ()))
    return base, semantic


def claim_terms(claim: str, concept: str) -> list[str]:
    base = tokens(concept)
    return sorted({t for t in words(claim) if t not in STOP and t not in base and len(t) > 2})


def is_generic_claim(claim: str, concept: str) -> bool:
    n = norm(claim)
    c = norm(concept)
    return n in {f"{c} is here", f"{c} here", c}


def is_definition_claim(claim: str, concept: str) -> bool:
    n = norm(claim)
    c = norm(concept)
    return n.startswith(f"{c} is an ") or n.startswith(f"{c} is a ") or n.startswith(f"{c} are ")


def ambiguous_reason(concept: str, claims: list[str], item_ids: list[str]) -> str | None:
    if any(item_id in ACTIVE_MISMATCH_ITEM_IDS for item_id in item_ids):
        return "At least one authoritative visual interpretation is mismatched with, negates, or fails to visibly demonstrate its named concept."
    cterms = tokens(concept)
    abstract = bool(cterms & ABSTRACT_WORDS)
    inward = any(re.search(r"\b(thought|inner|belief|meaning|understanding|intention|worth|truth)\b", x, re.I) for x in claims)
    comparative = any(re.search(r"\b(best|perfect|correct|important|fair|normal|similar|different)\b", x, re.I) for x in claims)
    if abstract and inward:
        return "The lesson targets an internal or relational abstraction whose defining state is not directly visible in one unlabeled still image."
    if abstract or comparative:
        return "The concept is evaluative, relational, or abstract; a still image may show an example but cannot by itself establish the intended generalization."
    return None


def exact_prompt_item(text: str, item: dict) -> bool:
    match = PROMPT_ITEM_RE.search(text)
    if not match:
        return False
    item_id = f"c{int(match.group(2)):04d}-e{int(match.group(1))}"
    claim_match = CLAIM_RE.search(text)
    return item_id == item["item_id"] and claim_match is not None and claim_match.group(1).strip() == item["teaching_claim"]


def best_evidence(asset_id: int, item: dict, evidence: dict, evidence_tokens: dict, semantic: set[str]):
    concept_norm = raw_norm(item["concept"])
    cterms = set(claim_terms(item["teaching_claim"], item["concept"]))
    weights = {"reviewed_caption": 8, "generation_prompt": 7, "relationship": 6, "label": 5,
               "prior_final_review": 4, "prior_inspection": 4, "asset_title": 3, "source_terms": 1}
    best = None
    for row, rtokens in zip(evidence.get(asset_id, []), evidence_tokens.get(asset_id, [])):
        rn = raw_norm(row["text"])
        exact = bool(concept_norm and f" {concept_norm} " in f" {rn} ")
        # A semantic substitution must cover the complete concept phrase.  A
        # match for "person" is not sufficient evidence for "brave person".
        semantic_base_text = re.sub(r"\s+\d+$", "", item["concept"].casefold())
        semantic_base = {t for t in tokens(semantic_base_text) if t not in STOP}
        sem = sorted({
            candidate for token in semantic_base
            for candidate in SYNONYMS.get(token, ()) if candidate in rtokens
        })
        semantic_complete = bool(sem) and all(
            token in rtokens or bool(SYNONYMS.get(token, set()) & rtokens)
            for token in semantic_base
        )
        if not semantic_complete:
            sem = []
        overlap = sorted(cterms & rtokens)
        prompt_exact = row["kind"] == "generation_prompt" and exact_prompt_item(row["text"], item)
        score = weights.get(row["kind"], 0) + (100 if prompt_exact else 0) + (20 if exact else 0) + 9 * len(sem) + 4 * len(overlap)
        candidate = (score, prompt_exact, exact, sem, overlap, row["kind"], row["text"])
        if best is None or candidate > best:
            best = candidate
    return best


def candidate_pool(item: dict, inverted: dict, audit_assets: set[int]) -> set[int]:
    base, semantic = concept_terms(item["concept"])
    cterms = claim_terms(item["teaching_claim"], item["concept"])
    pool = set(audit_assets)
    # Search the complete postings, but only score assets satisfying a coherent
    # query. Unioning every interpretation word makes common words dominate and
    # is neither semantically useful nor computationally bounded.
    if base:
        pool.update(set.intersection(*(inverted.get(token, set()) for token in base)))
    for token in semantic:
        pool.update(inverted.get(token, ()))
    rare = sorted((token for token in cterms if len(inverted.get(token, ())) <= 5000),
                  key=lambda token: (len(inverted.get(token, ())), token))
    if len(rare) >= 2:
        pool.update(inverted.get(rare[0], set()) & inverted.get(rare[1], set()))
    elif rare and len(inverted.get(rare[0], ())) <= 500:
        pool.update(inverted.get(rare[0], ()))
    return pool


def eligible(item: dict, match) -> tuple[bool, str | None, int]:
    if match is None:
        return False, None, 0
    score, prompt_exact, exact, sem, overlap, kind, _ = match
    matched_text = match[-1]
    if item["item_id"] in ACTIVE_MISMATCH_ITEM_IDS or item["item_id"] in ACTIVE_FALSE_POSITIVE_ITEM_IDS:
        return False, None, score
    generic = is_generic_claim(item["teaching_claim"], item["concept"])
    definition = is_definition_claim(item["teaching_claim"], item["concept"])
    if prompt_exact:
        return True, "exact", score
    admissible_kinds = {"reviewed_caption", "generation_prompt", "relationship", "label"}
    text_risk = bool(re.search(
        r"\b(text|words?|labeled|labelled|infographic|chart|graph|poster|logo|signs?|printed|reads|titled|graffiti|collage)\b",
        matched_text, re.I,
    ))
    if kind not in admissible_kinds or text_risk:
        return False, None, score
    if exact and (generic or overlap or definition) and (kind != "label" or generic or definition):
        return True, "exact", score
    needed_semantic_overlap = min(2, len(claim_terms(item["teaching_claim"], item["concept"])))
    if sem and (generic or definition or len(overlap) >= needed_semantic_overlap):
        return True, "semantic_equivalent", score
    total_claim_terms = len(claim_terms(item["teaching_claim"], item["concept"]))
    if (
        item["item_id"] in ACTIVE_AUDITED_ALTERNATE_ITEM_IDS
        and len(overlap) >= 3
        and len(overlap) / max(1, total_claim_terms) >= 0.6
        and kind in {"reviewed_caption", "relationship"}
    ):
        return True, "alternate_realization", score
    return False, None, score


def rationale_for(tier: str, match, item: dict) -> str:
    _, prompt_exact, exact, semantic, overlap, kind, _ = match
    if prompt_exact:
        return "Registry generation-prompt evidence exactly names this curriculum item, concept, variation, and teaching interpretation; the pixels still require Luna review."
    if tier == "exact":
        detail = f" and overlaps claim terms {overlap}" if overlap else ""
        return f"{kind} evidence explicitly names the concept{detail}; it is a plausible item-level teaching candidate, not pixel proof."
    if tier == "semantic_equivalent":
        return f"{kind} evidence uses documented equivalent term(s) {semantic} and overlaps claim terms {overlap}; Luna must resolve visual sense and fit."
    return f"{kind} evidence realizes the claim through concrete terms {overlap} without literally naming the concept; this is deliberately provisional."


def priority(ordinal: int, ambiguous: bool) -> str:
    if ambiguous:
        return "low"
    if ordinal <= 500:
        return "high"
    if ordinal <= 1500:
        return "medium"
    return "normal"


def _campaign_id(path: Path) -> str:
    value = json.loads(path.read_text(encoding="utf-8"))
    campaign = value.get("campaign", value)
    result = campaign.get("id") or value.get("campaign_id") or value.get("id")
    if not result:
        raise ValueError(f"campaign id is absent from {path}")
    return str(result)


def _configure(argv: Iterable[str] | None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("training_data/image_registry/registry.sqlite3"))
    parser.add_argument("--material-root", type=Path, required=True)
    parser.add_argument("--mission", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--campaign-id")
    parser.add_argument("--expected-items", type=int)
    parser.add_argument("--expected-concepts", type=int)
    parser.add_argument(
        "--review-policy", type=Path,
        help="Optional JSON lists: mismatch_item_ids, false_positive_item_ids, audited_alternate_item_ids.",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)
    resolved_output = args.output.resolve()
    protected_downloads = Path("/media/aomukai/FILES/Downloads").resolve()
    if resolved_output == protected_downloads or protected_downloads in resolved_output.parents:
        parser.error(f"refusing protected output tree: {protected_downloads}")

    global DB, MATERIAL, MISSION, AUDIT, OUT, CAMPAIGN_ID
    global EXPECTED_ITEMS, EXPECTED_CONCEPTS, ACTIVE_MISMATCH_ITEM_IDS
    global ACTIVE_FALSE_POSITIVE_ITEM_IDS, ACTIVE_AUDITED_ALTERNATE_ITEM_IDS, REVIEW_POLICY_PATH
    DB = args.db.resolve()
    MATERIAL = args.material_root.resolve()
    MISSION = args.mission.resolve()
    AUDIT = args.audit.resolve()
    OUT = resolved_output
    CAMPAIGN_ID = args.campaign_id or _campaign_id(MISSION)
    EXPECTED_ITEMS = args.expected_items
    EXPECTED_CONCEPTS = args.expected_concepts
    policy: dict[str, list[str]] = {}
    if args.review_policy:
        policy.update(json.loads(args.review_policy.read_text(encoding="utf-8")))
    ACTIVE_MISMATCH_ITEM_IDS = set(policy.get("mismatch_item_ids", []))
    ACTIVE_FALSE_POSITIVE_ITEM_IDS = set(policy.get("false_positive_item_ids", []))
    ACTIVE_AUDITED_ALTERNATE_ITEM_IDS = set(policy.get("audited_alternate_item_ids", []))
    REVIEW_POLICY_PATH = args.review_policy.resolve() if args.review_policy else None
    OUT.mkdir(parents=True, exist_ok=True)


def main(argv: Iterable[str] | None = None) -> int:
    _configure(argv)
    items, concepts, audit_rows, visual_paths = load_inputs()
    if EXPECTED_ITEMS is not None and len(items) != EXPECTED_ITEMS:
        raise ValueError(f"expected {EXPECTED_ITEMS} items, found {len(items)}")
    if EXPECTED_CONCEPTS is not None and len(concepts) != EXPECTED_CONCEPTS:
        raise ValueError(f"expected {EXPECTED_CONCEPTS} concepts, found {len(concepts)}")
    with connect_ro() as db:
        assets, evidence, labels, relationships = load_registry(db)
        registry_status_counts = dict(db.execute("SELECT status,COUNT(*) FROM asset GROUP BY status ORDER BY status").fetchall())
        source_status_counts = [dict(row) for row in db.execute("SELECT source,status,COUNT(*) count FROM asset GROUP BY source,status ORDER BY source,status")]
        has_review_queue = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='review_queue'"
        ).fetchone()
        queue_counts = [] if has_review_queue is None else [
            dict(row) for row in db.execute(
                "SELECT queue_name,status,COUNT(*) count FROM review_queue "
                "GROUP BY queue_name,status ORDER BY queue_name,status"
            )
        ]
    asset_tokens, evidence_tokens, inverted = make_index(assets, evidence)
    audit_asset_ids = {o: {x["asset_id"] for x in row["candidates"]} for o, row in audit_rows.items()}

    # First reserve exact item-specific Flux prompt assets, then rank remaining items.
    assignments = []
    used: set[int] = set()
    unresolved = []
    item_candidates = {}
    ordered = sorted(items, key=lambda x: (0 if any(exact_prompt_item(r["text"], x) for aid in audit_asset_ids.get(x["ordinal"], set()) for r in evidence.get(aid, []) if r["kind"] == "generation_prompt") else 1, x["ordinal"], x["example_index"]))
    for item in ordered:
        pool = candidate_pool(item, inverted, audit_asset_ids.get(item["ordinal"], set()))
        ranked = []
        rejected = []
        for asset_id in pool:
            match = best_evidence(asset_id, item, evidence, evidence_tokens, concept_terms(item["concept"])[1])
            ok, tier, score = eligible(item, match)
            entry = (score, -asset_id, asset_id, tier, match)
            if ok:
                ranked.append(entry)
            elif match:
                rejected.append(entry)
        ranked.sort(reverse=True)
        rejected.sort(reverse=True)
        item_candidates[item["item_id"]] = {"eligible": len(ranked), "searched": len(pool), "best_rejected": rejected[0] if rejected else None}
        chosen = next((row for row in ranked if row[2] not in used), None)
        if chosen is None:
            unresolved.append(item)
            continue
        _, _, asset_id, tier, match = chosen
        used.add(asset_id)
        asset = assets[asset_id]
        _, _, _, semantic, overlap, kind, matched_text = match
        assignments.append({
            "schema_version": SCHEMA,
            "campaign_id": CAMPAIGN_ID,
            "item_id": item["item_id"], "ordinal": item["ordinal"], "example_index": item["example_index"],
            "concept_id": item["concept_id"], "concept": item["concept"],
            "asset_id": asset_id, "path": asset["local_path"], "sha256": asset["sha256"],
            "source": asset["source"], "source_id": asset["source_id"],
            "width": asset["width"], "height": asset["height"],
            "matched_registry_text_kind": kind, "matched_registry_text": matched_text,
            "matched_semantic_terms": semantic, "matched_claim_terms": overlap,
            "intended_teaching_claim": item["teaching_claim"], "query_tier": tier,
            "rationale": rationale_for(tier, match, item), "verification_status": VERIFY,
        })
    assignments.sort(key=lambda x: (x["ordinal"], x["example_index"]))

    assigned_by_item = {x["item_id"]: x for x in assignments}
    by_concept_items: dict[int, list[dict]] = collections.defaultdict(list)
    for item in items:
        by_concept_items[item["ordinal"]].append(item)
    ambiguous = []
    for ordinal, group in sorted(by_concept_items.items()):
        reason = ambiguous_reason(group[0]["concept"], [x["teaching_claim"] for x in group], [x["item_id"] for x in group])
        if reason:
            ambiguous.append({"ordinal": ordinal, "concept_id": group[0]["concept_id"], "concept": group[0]["concept"],
                              "item_ids": [x["item_id"] for x in group], "reason": reason})
    ambiguous_ordinals = {x["ordinal"] for x in ambiguous}

    wishlist = []
    for ordinal, group in sorted(by_concept_items.items()):
        missing = [x for x in group if x["item_id"] not in assigned_by_item]
        if not missing:
            continue
        searched = sum(item_candidates[x["item_id"]]["searched"] for x in missing)
        eligible_total = sum(item_candidates[x["item_id"]]["eligible"] for x in missing)
        if ordinal in ambiguous_ordinals:
            gap_class = "curriculum_image_lesson_ambiguity"
            why = "The available evidence can illustrate examples, but the curriculum claim is abstract or relational and is not honestly established by a single unlabeled still image."
        elif searched and any(item_candidates[x["item_id"]]["best_rejected"] for x in missing):
            gap_class = "search_or_query_gap"
            why = "Registry search returned lexical or contextual near-matches, but none met the conservative item-specific evidence rule with an unused asset."
        else:
            gap_class = "genuine_material_gap"
            why = "No reviewed local registry evidence was found that names the concept/equivalent or concretely realizes enough of the teaching claim."
        alternatives = []
        for item in missing:
            terms = claim_terms(item["teaching_claim"], item["concept"])
            if terms:
                alternatives.append("scene containing " + ", ".join(terms[:5]))
        alternatives = list(dict.fromkeys(alternatives))[:6]
        wishlist.append({
            "schema_version": SCHEMA, "request_id": f"material-{CAMPAIGN_ID}-c{ordinal:04d}-residual",
            "concept_id": group[0]["concept_id"], "concept": group[0]["concept"], "ordinal": ordinal,
            "item_ids": [x["item_id"] for x in missing],
            "teaching_needs": [{"item_id": x["item_id"], "teaching_claim": x["teaching_claim"]} for x in missing],
            "exact_teaching_need": "Distinct, unambiguous, text-free still image evidence for each listed item-specific interpretation.",
            "acceptable_alternatives": alternatives or [f"a concrete, culturally neutral scene that visibly distinguishes {group[0]['concept']}"],
            "gap_class": gap_class, "why_current_candidates_are_insufficient": why,
            "registry_search_evidence": {"candidate_assets_examined_across_missing_items": searched, "eligible_but_unavailable_or_used": eligible_total},
            "acquisition_priority": priority(ordinal, ordinal in ambiguous_ordinals),
            "pre_acquisition_review": "Revise the image lesson before acquisition." if ordinal in ambiguous_ordinals else "Manual Luna-assisted review of the strongest registry near-matches before acquisition.",
            "preferred_next_action": "external_acquisition",
            "fallback_order": ["external_acquisition", "minimal_flux_edit", "custom_flux_generation"],
            "authorization_status": "proposal_only_not_dispatched",
        })

    # Expansion rows cover every audit-declared expansion and every concept with a non-exact outcome/residual.
    tiers_by_ordinal: dict[int, collections.Counter] = collections.defaultdict(collections.Counter)
    for row in assignments:
        tiers_by_ordinal[row["ordinal"]][row["query_tier"]] += 1
    expansion_ordinals = {o for o, row in audit_rows.items() if row["status"] == "needs_sol_query_expansion"}
    expansion_ordinals.update(row["ordinal"] for row in assignments if row["query_tier"] != "exact")
    expansion_ordinals.update(row["ordinal"] for row in wishlist)
    query_expansions = []
    for ordinal in sorted(expansion_ordinals):
        group = by_concept_items[ordinal]
        concept = group[0]["concept"]
        base, semantic = concept_terms(concept)
        alternate = []
        for item in group:
            phrase = " ".join(claim_terms(item["teaching_claim"], concept)[:6])
            if phrase and phrase not in alternate:
                alternate.append(phrase)
        exact_assets = set.intersection(*(inverted.get(t, set()) for t in base)) if base else set()
        semantic_assets = set().union(*(inverted.get(t, set()) for t in semantic)) if semantic else set()
        alternate_assets = set()
        for phrase in alternate:
            pts = set(phrase.split())
            if pts:
                sets = [inverted.get(t, set()) for t in pts]
                alternate_assets.update(set.intersection(*sets) if sets else set())
        query_expansions.append({
            "schema_version": SCHEMA, "ordinal": ordinal, "concept_id": group[0]["concept_id"], "concept": concept,
            "exact_query": " AND ".join(f'\"{t}\"' for t in sorted(base)),
            "semantic_equivalents": sorted(semantic),
            "semantic_equivalent_queries": [f'\"{t}\"' for t in sorted(semantic)],
            "alternate_concrete_realizations": alternate,
            "alternate_realization_queries": [" AND ".join(f'\"{t}\"' for t in p.split()) for p in alternate],
            "rationale": "Semantic terms use the fixed auditable equivalence map; alternate realizations are extracted from the campaign's own item-specific visual interpretations.",
            "registry_result_asset_counts": {"exact": len(exact_assets), "semantic_equivalent": len(semantic_assets), "alternate_realization": len(alternate_assets)},
            "proposal_outcomes": dict(sorted(tiers_by_ordinal[ordinal].items())),
            "residual_item_count": sum(1 for x in group if x["item_id"] not in assigned_by_item),
        })

    source_counts = collections.Counter(x["source"] for x in assignments)
    tier_counts = collections.Counter(x["query_tier"] for x in assignments)
    use_counts = collections.Counter(x["asset_id"] for x in assignments)
    overused = [{"asset_id": aid, "assignment_count": n} for aid, n in sorted(use_counts.items()) if n > 1]
    concept_coverage = []
    for ordinal, group in sorted(by_concept_items.items()):
        n = sum(1 for x in group if x["item_id"] in assigned_by_item)
        concept_coverage.append({"ordinal": ordinal, "concept_id": group[0]["concept_id"], "concept": group[0]["concept"],
                                 "required_items": len(group), "assigned_items": n, "residual_items": len(group)-n,
                                 "coverage_status": "full" if n == len(group) else "none" if n == 0 else "partial"})
    concept_status = collections.Counter(x["coverage_status"] for x in concept_coverage)
    gap_counts = collections.Counter(x["gap_class"] for x in wishlist)
    residual_item_counts = collections.Counter()
    for row in wishlist:
        residual_item_counts[row["gap_class"]] += len(row["item_ids"])

    dump_jsonl(OUT / "selection_proposal.jsonl", assignments)
    dump_jsonl(OUT / "wishlist.jsonl", wishlist)
    dump_jsonl(OUT / "query_expansions.jsonl", query_expansions)

    input_paths = [MISSION, MATERIAL / "manifest.json", MATERIAL / "curriculum.jsonl", TOOL, REQUEST_SCHEMA, AUDIT / "summary.json"] + visual_paths + sorted((AUDIT / "batches").glob("*.jsonl"))
    if REVIEW_POLICY_PATH is not None:
        input_paths.append(REVIEW_POLICY_PATH)
    summary = {
        "schema_version": SCHEMA, "campaign_id": CAMPAIGN_ID,
        "status": "provisional_registry_assignment_complete_pending_luna",
        "scope": {"concepts": len(concepts), "items": len(items), "reviewed_usable_registry_assets": registry_status_counts.get("reviewed_usable", 0),
                  "reviewed_usable_local_hashable_assets_searched": len(assets)},
        "evidence_policy": "Caption, prompt, label, relationship, title, and source-term evidence rank candidates; none proves pixel-level teaching fit.",
        "coverage": {
            "items": {"required": len(items), "provisionally_assigned": len(assignments), "residual": len(items)-len(assignments),
                      "coverage_fraction": round(len(assignments)/len(items), 6)},
            "concepts": {"required": len(concepts), **dict(sorted(concept_status.items()))},
            "sources": dict(sorted(source_counts.items())), "query_tiers": dict(sorted(tier_counts.items())),
            "residual_gap_groups": dict(sorted(gap_counts.items())), "residual_items_by_gap_class": dict(sorted(residual_item_counts.items())),
            "unique_assets": len(use_counts), "overused_asset_count": len(overused), "overused_assignment_count": sum(x["assignment_count"]-1 for x in overused),
        },
        "registry": {"asset_status_counts": registry_status_counts, "source_status_counts": source_status_counts, "review_queue_counts": queue_counts},
        "audit_baseline": json.loads((AUDIT / "summary.json").read_text(encoding="utf-8")),
        "coverage_by_concept": concept_coverage, "overused_assets": overused,
        "ambiguous_or_visually_abstract_concepts": ambiguous,
        "query_expansion_concept_count": len(query_expansions),
        "verification_status": VERIFY,
        "review_policy": {
            "path": str(REVIEW_POLICY_PATH) if REVIEW_POLICY_PATH else None,
            "mismatch_item_count": len(ACTIVE_MISMATCH_ITEM_IDS),
            "false_positive_item_count": len(ACTIVE_FALSE_POSITIVE_ITEM_IDS),
            "audited_alternate_item_count": len(ACTIVE_AUDITED_ALTERNATE_ITEM_IDS),
        },
        "next_gate": "Luna pixel verification of every provisional assignment, prioritized as described in sol_report.md.",
        "input_set_sha256": canonical_hash(input_paths),
    }
    dump_json(OUT / "summary.json", summary)

    # Validate manifest batch hashes, item partition, registry status/path/hash, and output rows.
    manifest = json.loads((MATERIAL / "manifest.json").read_text(encoding="utf-8"))
    batch_hash_errors = []
    for batch in manifest["batches"]:
        path = MATERIAL / batch["visual_path"]
        actual = sha256_file(path)
        if actual != batch["visual_sha256"]:
            batch_hash_errors.append({"path": str(path), "expected": batch["visual_sha256"], "actual": actual})
    asset_errors = []
    for row in assignments:
        asset = assets.get(row["asset_id"])
        path = Path(row["path"])
        if asset is None or asset["status"] != "reviewed_usable":
            asset_errors.append({"item_id": row["item_id"], "error": "asset_not_reviewed_usable"})
        elif not path.is_file():
            asset_errors.append({"item_id": row["item_id"], "error": "local_file_missing", "path": str(path)})
        else:
            actual = sha256_file(path)
            if actual != row["sha256"] or actual != asset["sha256"]:
                asset_errors.append({"item_id": row["item_id"], "error": "sha256_mismatch", "actual": actual})
    all_item_ids = {x["item_id"] for x in items}
    selected_ids = [x["item_id"] for x in assignments]
    wish_ids = [iid for row in wishlist for iid in row["item_ids"]]
    partition_ok = set(selected_ids).isdisjoint(wish_ids) and set(selected_ids) | set(wish_ids) == all_item_ids and len(selected_ids)+len(wish_ids) == len(items)
    output_hashes = {name: sha256_file(OUT / name) for name in ["summary.json", "selection_proposal.jsonl", "wishlist.jsonl", "query_expansions.jsonl"]}
    validation = {
        "schema_version": SCHEMA, "status": "passed" if not batch_hash_errors and not asset_errors and partition_ok and not overused else "failed",
        "checks": {
            "authoritative_dimensions": {
                "passed": (EXPECTED_ITEMS is None or len(items) == EXPECTED_ITEMS)
                and (EXPECTED_CONCEPTS is None or len(concepts) == EXPECTED_CONCEPTS),
                "items": len(items), "concepts": len(concepts),
                "expected_items": EXPECTED_ITEMS, "expected_concepts": EXPECTED_CONCEPTS,
            },
            "manifest_visual_batch_hashes": {"passed": not batch_hash_errors, "checked": len(manifest["batches"]), "errors": batch_hash_errors},
            "selection_rows_parse_and_unique_items": {"passed": len(selected_ids)==len(set(selected_ids)), "rows": len(selected_ids)},
            "item_partition_selection_or_wishlist": {"passed": partition_ok, "selection_items": len(selected_ids), "wishlist_items": len(wish_ids)},
            "selected_assets_reviewed_local_and_sha256_match": {"passed": not asset_errors, "checked": len(assignments), "errors": asset_errors},
            "assignment_verification_status": {"passed": all(x["verification_status"]==VERIFY for x in assignments), "required_value": VERIFY},
            "asset_uniqueness": {"passed": not overused, "unique_assets": len(use_counts), "overused_assets": overused},
            "no_provider_invocation": {"passed": True, "detail": "Builder performs local read-only SQLite/filesystem analysis only."},
            "registry_database_read_only": {"passed": True, "detail": "SQLite opened with mode=ro and PRAGMA query_only=ON."},
        },
        "method": {
            "determinism": "Stable ordinal/item/asset ordering; fixed equivalence map; no randomness, timestamps, network, or provider calls.",
            "registry_search_scope": "All status=reviewed_usable assets with non-null local_path and sha256; text_record kinds plus title, labels, and relationships.",
            "caption_limit": "Registry text is candidate evidence only; every assignment remains pending Luna pixel verification.",
            "pixel_sample": {"performed": False, "reason": "Bulk files were hash-validated, but no pixel-fit judgments were made; Luna remains the designated verifier."},
        },
        "helper_scripts": [{"path": str(Path(__file__).resolve()), "sha256": sha256_file(Path(__file__).resolve()),
                            "purpose": "Rebuild proposal/report outputs deterministically from explicit read-only inputs.",
                            "command": "python3 -m image_registry.material_gap_analysis --help"}],
        "deliverable_hashes_excluding_self": output_hashes,
    }
    dump_json(OUT / "validation_report.json", validation)

    coverage_percent = 100 * len(assignments) / len(items) if items else 0.0
    report = f"""# {CAMPAIGN_ID} registry-first visual-material report

## Outcome

This bounded pass provisionally assigns **{len(assignments):,} of {len(items):,} items ({coverage_percent:.1f}%)** across **{concept_status.get('full',0):,} fully covered, {concept_status.get('partial',0):,} partially covered, and {concept_status.get('none',0):,} uncovered concepts**. Every assignment remains `{VERIFY}`. Caption and metadata evidence are candidate evidence, never proof of pixel-level fit.

The residual is **{len(items)-len(assignments):,} items** in **{len(wishlist):,} concept-level wishlist groups**. These are separated as {residual_item_counts.get('genuine_material_gap',0):,} genuine-material-gap items, {residual_item_counts.get('search_or_query_gap',0):,} search/query-gap items, and {residual_item_counts.get('curriculum_image_lesson_ambiguity',0):,} items whose image lesson is itself ambiguous or visually abstract.

## What the existing curriculum asks for

The authoritative curriculum contains {len(concepts):,} dependency-ordered concepts and {len(items):,} distinct visual item IDs. Each item asks for one coherent natural, text-free, unlabeled, watermark-free, non-collage still image tied to a specific visual interpretation. Variants are not interchangeable: they may split definition/appearance, context, behavior or mechanism, and purpose/use. The proposal therefore matches at item level rather than treating the concept label alone as sufficient.

## Registry search and evidence policy

The complete local reviewed-usable pool with a recorded path and SHA-256 was searched: **{len(assets):,} assets**. Evidence included reviewed captions, generation prompts, prior review text, source terms, asset titles, labels, and relationships. Query order was exact concept, fixed documented semantic equivalents, then concrete terms extracted from the campaign's own visual interpretation. Exact campaign-linked Flux prompts were treated as strong provenance-linked candidate evidence, while still requiring Luna to inspect pixels.

Assignments by source: {json.dumps(dict(sorted(source_counts.items())), sort_keys=True)}. Assignments by query tier: {json.dumps(dict(sorted(tier_counts.items())), sort_keys=True)}. Assets are unique across assignments: **{len(use_counts):,} unique assets; {len(overused)} overused assets**.

## Residual interpretation

`search_or_query_gap` means registry evidence exists but is too weak, polysemous, or not item-specific enough for an honest assignment. `genuine_material_gap` means no adequate reviewed local evidence emerged after the bounded expansion. `curriculum_image_lesson_ambiguity` means the lesson asks a still image to establish an internal, evaluative, causal, temporal, or relational claim that a single unlabeled frame may not teach reliably. The full ambiguous-concept list is in `summary.json`; it contains **{len(ambiguous):,} concepts**.

Wishlist entries are proposals only. They preserve the mandated fallback order: external acquisition, then minimal Flux edit of a suitable reviewed image, then custom Flux generation. No acquisition, edit, generation, selection-table write, training action, ledger change, or Mission Hub mutation occurred.

## What Luna should verify next

1. Verify the **{tier_counts.get('alternate_realization',0):,} alternate-realization assignments** first, because they rely on concrete scene equivalence rather than the concept word.
2. Verify the **{tier_counts.get('semantic_equivalent',0):,} semantic-equivalent assignments**, checking sense, cultural neutrality, salience, and whether the target relation is actually visible.
3. Verify exact-tier Open Images matches for item-specific properties/actions, then exact campaign-linked Flux-prompt matches for prompt adherence, artifacts, embedded text, collage/watermark, and ambiguity.
4. Reject any candidate whose pixels do not make the intended teaching claim unambiguous; rejected item IDs return to their existing wishlist group before any acquisition proposal advances.

## Validation and reproducibility

`validation_report.json` records batch-hash checks, every selected file's status/path/SHA-256 verification, exact item partition, uniqueness, helper-script identity, and deliverable hashes. Run `python3 -m image_registry.material_gap_analysis --help` for the reusable rebuild command. The registry is opened read-only.
"""
    (OUT / "sol_report.md").write_text(report, encoding="utf-8")

    # Add report hash after report exists, while leaving validation self-hash deliberately absent.
    validation = json.loads((OUT / "validation_report.json").read_text(encoding="utf-8"))
    validation["deliverable_hashes_excluding_self"]["sol_report.md"] = sha256_file(OUT / "sol_report.md")
    dump_json(OUT / "validation_report.json", validation)
    print(json.dumps({"status": validation["status"], "assigned": len(assignments), "residual": len(items)-len(assignments),
                      "concept_status": dict(concept_status), "sources": dict(source_counts), "tiers": dict(tier_counts),
                      "wishlist_groups": len(wishlist), "query_expansions": len(query_expansions), "overused": len(overused)}, sort_keys=True))
    return 0 if validation["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
