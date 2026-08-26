#!/usr/bin/env python3
"""Build a durable, pedagogically revised curriculum with DeepSeek V4 Pro.

This deliberately produces a compact curriculum plan rather than reproducing the
large self-referential v4 registry. Responses stream to disk so progress and
partial output survive a client or desktop-app failure.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT = ROOT / "docs" / "curriculum_v5_deepseek"
MODEL = "deepseek-v4-pro"

SOURCE_PATHS = [
    ROOT / "docs" / "ninereeds_identity_and_lesson_policy.md",
    ROOT / "training_data" / "grounded_stories" / "world_bible.md",
    ROOT / "handoff" / "2023_08_20_lesson_000_example.md",
    ROOT / "handoff" / "2026_08_19_train_of_thought.md",
    ROOT / "docs" / "2026_08_20_curriculum_v1.md",
    ROOT / "docs" / "2026_08_20_curriculum_v2.md",
    ROOT / "docs" / "2026_08_20_curriculum_v3.md",
    ROOT / "ninereeds_curriculum_v4_bundle" / "ninereeds_curriculum_v4.json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_dotenv(path: Path) -> None:
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def atomic_json(path: Path, value: Any) -> None:
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(path)


def source_corpus() -> str:
    chunks = []
    for path in SOURCE_PATHS:
        if not path.is_file():
            raise FileNotFoundError(path)
        rel = path.relative_to(ROOT)
        chunks.append(f"\n<source path={json.dumps(str(rel))}>\n")
        chunks.append(path.read_text(encoding="utf-8"))
        chunks.append("\n</source>\n")
    return "".join(chunks)


AUDIT_FINDINGS = r"""
The reconstructed v4 is structurally consistent but its semantic audit is not
trustworthy. Correct these defects rather than preserving its counts or shape:

1. It puts explicit mind/person/device ontology in L001. The project note says
   the opposite: Errol should first ground the pattern implicitly; "Ninereeds is
   a mind" and the ontology belong later, after ordinary language exists.
2. Its one-novelty check counts bundles, but a bundle may hide eight unrelated
   new words. Examples include technical mega-bundles and mechanically extracted
   junk such as `c` from C123 and `does` as machine-learning vocabulary.
3. P-ID-001 is a prerequisite of 156/157 WORLD objectives and foreground point
   in 123 lessons. This is a closure shortcut, not a credible language surface.
4. All C001-C240 candidates are forced ACTIVE_COMPILED. Deferral, exclusion, and
   consolidation must remain real options with individual rationales.
5. A declared prerequisite graph is insufficient. Presentation, practice,
   correction, story text, and evaluation must be expressible using established
   language plus a realistically bounded frontier.
6. Preserve Lesson 000 as the sole staged bootstrap exception and preserve its
   actual instructional gates. Controlled drills are noncanonical. Do not invent
   repeated first meetings.
7. Do not optimize for 240, 288, or 295 lessons. Choose the useful sequence.
8. The desired artifact is a plan for compiling lessons, not bureaucratic bulk.
   Each lesson needs TOPIC and POINT plus enough information to compile it safely.
"""


SYSTEM_PROMPT = r"""
You are the senior curriculum architect for Ninereeds, a Hebbian multimodal
learner. Think deeply and critically. Your job is to create a useful teaching
sequence, not to defend an earlier artifact or make a graph pass its own audit.

Authority order:
1. identity and lesson policy;
2. current world bible;
3. actual Lesson 000 source;
4. explicit project design notes;
5. C001-C240 as candidate inventory, not an authoritative sequence;
6. v3 and reconstructed v4 as corrigible drafts.

Do not browse or import generic curricula. Reason from the supplied material.
Return JSON when requested. Be candid about deferrals and unresolved choices.
"""


def stream_json_call(
    client: OpenAI,
    *,
    messages: list[dict[str, str]],
    partial_path: Path,
    max_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    partial_path.parent.mkdir(parents=True, exist_ok=True)
    usage: dict[str, Any] = {}
    finish_reason = None
    with partial_path.open("w", encoding="utf-8") as out:
        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            reasoning_effort="max",
            max_tokens=max_tokens,
            stream=True,
            stream_options={"include_usage": True},
            extra_body={"thinking": {"type": "enabled"}},
            timeout=7200,
        )
        for chunk in stream:
            if getattr(chunk, "usage", None):
                usage = chunk.usage.model_dump()
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            if choice.finish_reason:
                finish_reason = choice.finish_reason
            content = getattr(choice.delta, "content", None)
            if content:
                out.write(content)
                out.flush()
    raw = partial_path.read_text(encoding="utf-8")
    if not raw.strip():
        raise RuntimeError("DeepSeek returned empty content")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"DeepSeek returned invalid/truncated JSON: {exc}") from exc
    if finish_reason == "length":
        raise RuntimeError("DeepSeek response reached max_tokens and may be truncated")
    return parsed, {"usage": usage, "finish_reason": finish_reason}


def validate_curriculum(data: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    lessons = data.get("lessons")
    accounting = data.get("source_accounting")
    if not isinstance(lessons, list) or not lessons:
        errors.append("lessons must be a nonempty array")
        lessons = []
    if not isinstance(accounting, list):
        errors.append("source_accounting must be an array")
        accounting = []

    required_lesson_fields = {
        "lesson_id", "topic", "point", "world_objective", "principal_novelty",
        "frontier_lexemes", "required_established_language", "prerequisites",
        "grounding_modes", "picture_book", "chronology_constraints", "characters",
        "locations", "evaluation_targets", "source_candidates", "rationale",
    }
    ids: list[str] = []
    for index, lesson in enumerate(lessons):
        if not isinstance(lesson, dict):
            errors.append(f"lesson {index} is not an object")
            continue
        missing = sorted(required_lesson_fields - set(lesson))
        if missing:
            errors.append(f"lesson {index} missing fields: {missing}")
        lid = lesson.get("lesson_id")
        ids.append(lid)
        expected = f"L{index:03d}"
        if lid != expected:
            errors.append(f"lesson sequence mismatch at {index}: {lid!r} != {expected}")
        frontier = lesson.get("frontier_lexemes", [])
        if not isinstance(frontier, list):
            errors.append(f"{lid}: frontier_lexemes is not an array")
        elif index != 0 and len(frontier) > 12:
            warnings.append(f"{lid}: unusually large frontier ({len(frontier)})")
        for token in frontier if isinstance(frontier, list) else []:
            if isinstance(token, str) and len(token.strip()) == 1 and token.strip().lower() not in {"a", "i"}:
                errors.append(f"{lid}: suspicious one-character frontier lexeme {token!r}")
    if len(ids) != len(set(ids)):
        errors.append("duplicate lesson IDs")
    positions = {lid: i for i, lid in enumerate(ids)}
    for lesson in lessons:
        if not isinstance(lesson, dict):
            continue
        lid = lesson.get("lesson_id")
        for dep in lesson.get("prerequisites", []):
            if dep not in positions:
                errors.append(f"{lid}: missing prerequisite {dep}")
            elif positions[dep] >= positions.get(lid, -1):
                errors.append(f"{lid}: prerequisite {dep} does not precede lesson")

    expected_sources = {f"C{i:03d}" for i in range(1, 241)}
    seen_sources = [x.get("source_id") for x in accounting if isinstance(x, dict)]
    missing_sources = sorted(expected_sources - set(seen_sources))
    extra_sources = sorted(set(seen_sources) - expected_sources)
    if missing_sources or extra_sources or len(seen_sources) != len(set(seen_sources)):
        errors.append(
            f"source accounting mismatch: missing={missing_sources}, extra={extra_sources}, "
            f"duplicates={len(seen_sources) - len(set(seen_sources))}"
        )
    valid_status = {"active", "deferred", "excluded", "consolidated"}
    for item in accounting:
        if not isinstance(item, dict):
            continue
        sid = item.get("source_id")
        if item.get("status") not in valid_status:
            errors.append(f"{sid}: invalid status {item.get('status')!r}")
        if not item.get("rationale"):
            errors.append(f"{sid}: missing rationale")
        for lid in item.get("lesson_ids", []):
            if lid not in positions:
                errors.append(f"{sid}: unknown lesson reference {lid}")

    if lessons:
        if lessons[0].get("topic") != "Greeting and self-introduction":
            errors.append("L000 topic was not preserved")
        early = json.dumps(lessons[1:10], ensure_ascii=False).lower()
        if "ninereeds is a mind" in early:
            errors.append("explicit Ninereeds mind ontology remains in the first ten lessons")

    return {
        "status": "PASS" if not errors else "FAIL",
        "generated_at": utc_now(),
        "lesson_count": len(lessons),
        "source_record_count": len(accounting),
        "errors": errors,
        "warnings": warnings,
    }


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Ninereeds Foundational Curriculum v5 — DeepSeek candidate",
        "",
        "> Durable local reconstruction. This remains a candidate until human/Sol review.",
        "",
    ]
    meta = data.get("metadata", {})
    lines.extend([f"- Lessons: {len(data.get('lessons', []))}", f"- Generated model: {MODEL}", ""])
    if meta:
        lines.extend(["## Metadata", "", "```json", json.dumps(meta, ensure_ascii=False, indent=2), "```", ""])
    lines.extend(["## Lesson sequence", ""])
    for lesson in data.get("lessons", []):
        lines.extend(
            [
                f"### {lesson['lesson_id']} — {lesson['topic']}",
                "",
                f"**TOPIC:** {lesson['topic']}",
                "",
                f"**POINT:** {lesson['point']}",
                "",
                f"**WORLD:** {lesson['world_objective']}",
                "",
                f"**Principal novelty:** {lesson['principal_novelty']}",
                "",
                f"**Frontier language:** {', '.join(lesson['frontier_lexemes']) or 'None'}",
                "",
                f"**Prerequisites:** {', '.join(lesson['prerequisites']) or 'None'}",
                "",
                f"**Grounding:** {', '.join(lesson['grounding_modes'])}; picture book: {lesson['picture_book']}",
                "",
                f"**Chronology:** {lesson['chronology_constraints'] or 'None'}",
                "",
                f"**Evaluation:** {'; '.join(lesson['evaluation_targets'])}",
                "",
                f"**Sources:** {', '.join(lesson['source_candidates']) or 'Synthesized'}",
                "",
                lesson["rationale"],
                "",
            ]
        )
    lines.extend(["## C001–C240 accounting", ""])
    for item in data.get("source_accounting", []):
        refs = ", ".join(item.get("lesson_ids", [])) or "—"
        lines.append(f"- **{item['source_id']}** — `{item['status']}` → {refs}: {item['rationale']}")
    lines.append("")
    return "\n".join(lines)


def validate_asset_plan(plan: dict[str, Any], curriculum: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    lessons = curriculum.get("lessons", [])
    lesson_ids = {x.get("lesson_id") for x in lessons}
    lesson_by_id = {x.get("lesson_id"): x for x in lessons}
    regular = plan.get("regular_image_requirements")
    books = plan.get("picture_books")
    if not isinstance(regular, list):
        errors.append("regular_image_requirements must be an array")
        regular = []
    if not isinstance(books, list):
        errors.append("picture_books must be an array")
        books = []
    asset_ids: list[str] = []
    covered_lessons: set[str] = set()
    for index, item in enumerate(regular):
        if not isinstance(item, dict):
            errors.append(f"regular image requirement {index} is not an object")
            continue
        aid = item.get("asset_id")
        lid = item.get("lesson_id")
        asset_ids.append(aid)
        if lid not in lesson_ids:
            errors.append(f"{aid}: unknown lesson {lid}")
        else:
            covered_lessons.add(lid)
        if not item.get("concept_or_contrast"):
            errors.append(f"{aid}: missing concept_or_contrast")
        quantity = item.get("quantity")
        if not isinstance(quantity, int) or quantity < 1:
            errors.append(f"{aid}: invalid quantity {quantity!r}")
        if not item.get("variation_dimensions"):
            warnings.append(f"{aid}: no variation dimensions")
        if not item.get("acquisition_strategy"):
            errors.append(f"{aid}: missing acquisition_strategy")
    if len(asset_ids) != len(set(asset_ids)):
        errors.append("duplicate regular asset IDs")
    uncovered = sorted(lesson_ids - covered_lessons)
    if uncovered:
        warnings.append(f"lessons without regular image requirements: {uncovered}")

    book_ids: list[str] = []
    book_lessons: set[str] = set()
    for index, book in enumerate(books):
        if not isinstance(book, dict):
            errors.append(f"picture book {index} is not an object")
            continue
        bid = book.get("book_id")
        lid = book.get("lesson_id")
        book_ids.append(bid)
        if lid not in lesson_ids:
            errors.append(f"{bid}: unknown lesson {lid}")
        else:
            book_lessons.add(lid)
            if lesson_by_id[lid].get("picture_book") == "no":
                errors.append(f"{bid}: assigned to lesson {lid} whose curriculum says picture_book=no")
        pages = book.get("pages")
        if not isinstance(pages, list) or not pages:
            errors.append(f"{bid}: pages must be a nonempty array")
            continue
        numbers = [x.get("page_number") for x in pages if isinstance(x, dict)]
        if numbers != list(range(1, len(pages) + 1)):
            errors.append(f"{bid}: page numbers are not consecutive from 1")
    if len(book_ids) != len(set(book_ids)):
        errors.append("duplicate picture-book IDs")
    required_books = {x.get("lesson_id") for x in lessons if x.get("picture_book") == "required"}
    missing_books = sorted(required_books - book_lessons)
    if missing_books:
        errors.append(f"required picture books without plans: {missing_books}")
    return {
        "status": "PASS" if not errors else "FAIL",
        "generated_at": utc_now(),
        "regular_requirement_count": len(regular),
        "regular_image_quantity": sum(x.get("quantity", 0) for x in regular if isinstance(x, dict)),
        "picture_book_count": len(books),
        "picture_book_page_count": sum(len(x.get("pages", [])) for x in books if isinstance(x, dict)),
        "errors": errors,
        "warnings": warnings,
    }


def render_asset_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Ninereeds Curriculum v5 — Asset plan",
        "",
        "> Planning inventory only. No image is trusted until admitted through the image-review cascade.",
        "",
        "## Regular teaching images",
        "",
    ]
    for item in plan.get("regular_image_requirements", []):
        lines.extend(
            [
                f"### {item['asset_id']} — {item['lesson_id']}",
                "",
                f"- Purpose: {item['instructional_purpose']}",
                f"- Concept/contrast: {item['concept_or_contrast']}",
                f"- Quantity: {item['quantity']}",
                f"- Variation: {', '.join(item['variation_dimensions'])}",
                f"- Acquisition: {item['acquisition_strategy']}",
                f"- Search terms: {', '.join(item.get('metadata_search_queries', []))}",
                f"- Generation brief: {item.get('generation_brief') or 'None'}",
                "",
            ]
        )
    lines.extend(["## Picture books", ""])
    for book in plan.get("picture_books", []):
        lines.extend(
            [
                f"### {book['book_id']} — {book['lesson_id']}: {book['title']}",
                "",
                f"{book['instructional_function']}",
                "",
            ]
        )
        for page in book["pages"]:
            lines.extend(
                [
                    f"#### Page {page['page_number']}",
                    "",
                    f"- Language function: {page['language_function']}",
                    f"- Scene: {page['scene_description']}",
                    f"- Characters: {', '.join(page['characters']) or 'None'}",
                    f"- Location: {page['location']}",
                    f"- Required objects: {', '.join(page['required_objects']) or 'None'}",
                    f"- Continuity: {page['continuity_constraints']}",
                    "",
                ]
            )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--stage", choices=("all", "design", "curriculum", "assets"), default="all")
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    load_dotenv(ROOT / ".env")
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is not set")
    client = OpenAI(api_key=api_key, base_url="https://api.deepseek.com")
    corpus = source_corpus()
    state_path = output / "state.json"
    state = {
        "status": "active",
        "model": MODEL,
        "started_at": utc_now(),
        "updated_at": utc_now(),
        "stage": "design",
        "sources": [str(p.relative_to(ROOT)) for p in SOURCE_PATHS],
    }
    atomic_json(state_path, state)

    design_path = output / "stage1_design.json"
    if args.stage in {"all", "design"}:
        design_prompt = f"""
Produce a JSON pedagogical redesign specification for a v5 curriculum. Analyze
the complete sources below and the audit findings. Decide what to preserve,
move, split, combine, defer, or exclude. Define enforceable tests that cannot be
passed merely by placing many novelties in one bundle. Design a chronological
and linguistic progression, including when the Errol/mind/device/data-transfer
thread should become explicit. Do not emit the lesson sequence yet.

Required top-level JSON keys:
- diagnosis
- governing_principles
- progression_phases
- surface_language_policy
- chronology_policy
- grounding_and_picture_book_policy
- source_disposition_policy
- validation_rules
- unresolved_human_decisions

AUDIT FINDINGS:
{AUDIT_FINDINGS}

AUTHORITATIVE AND CORRIGIBLE SOURCES:
{corpus}
"""
        design, info = stream_json_call(
            client,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": design_prompt}],
            partial_path=output / "stage1_design.partial.json",
            max_tokens=60000,
        )
        atomic_json(design_path, design)
        state.update(stage="curriculum", design_call=info, updated_at=utc_now())
        atomic_json(state_path, state)
        if args.stage == "design":
            state.update(status="complete", updated_at=utc_now())
            atomic_json(state_path, state)
            return 0
    else:
        design = json.loads(design_path.read_text(encoding="utf-8"))

    if args.stage in {"all", "curriculum"}:
        curriculum_prompt = f"""
Create the complete revised v5 curriculum as one JSON object. Follow the
approved redesign specification and source authority. This is a compact plan
from which Sol can later compile individual lessons; do not recreate v4's
inflated registries.

Use this exact top-level structure:
{{
  "metadata": {{...}},
  "design_summary": {{...}},
  "lessons": [
    {{
      "lesson_id": "L000",
      "topic": "Greeting and self-introduction",
      "point": "...",
      "world_objective": "...",
      "principal_novelty": "...",
      "frontier_lexemes": ["..."],
      "required_established_language": ["specific earlier lesson or language capability"],
      "prerequisites": ["Lnnn"],
      "grounding_modes": ["SCENE", "DIALOGUE", "SEQUENCE", "DIAGRAM", "SYMBOLIC", "DIRECT"],
      "picture_book": "required|optional|no",
      "chronology_constraints": "...",
      "characters": ["canonical names or explicit unnamed extras"],
      "locations": ["canonical locations or noncanonical direct teaching"],
      "evaluation_targets": ["..."],
      "source_candidates": ["C001"],
      "rationale": "..."
    }}
  ],
  "source_accounting": [
    {{
      "source_id": "C001",
      "status": "active|consolidated|deferred|excluded",
      "lesson_ids": ["L000"],
      "rationale": "individual evidence-based disposition"
    }}
  ],
  "unresolved_decisions": [{{"decision": "...", "impact": "..."}}],
  "self_audit": {{...}}
}}

Requirements:
- Number lessons consecutively from L000, with no gaps.
- Preserve actual Lesson 000 as the sole staged bootstrap exception.
- Each later lesson has one principal pedagogical novelty. A TOPIC may supply a
  coherent vocabulary family, but do not hide unrelated novelty inside a label.
- Repeat important POINTs with different TOPICs where useful. A lesson's POINT
  must be usable for teaching its TOPIC.
- Keep explicit Ninereeds/mind ontology out of the first ten lessons and place it
  only after enough ordinary language and Errol grounding exist.
- Make picture books required only where narrative/visual continuity materially
  helps; use direct scenes, diagrams, or dialogue honestly elsewhere.
- Account individually for exactly C001 through C240. Deferral and exclusion are
  permitted and should be used when pedagogically justified.
- Do not introduce noncanonical named people or locations. Bob remains pending
  operator canon approval, but Lesson 000 may use him as its source does.
- Ensure every prerequisite lesson precedes its dependent lesson.
- `frontier_lexemes` must list the actual new learner-facing words/fixed
  expressions, not words mechanically extracted from an explanatory sentence.
- State unresolved issues rather than manufacturing a PASS.

REDESIGN SPECIFICATION:
{json.dumps(design, ensure_ascii=False)}

AUDIT FINDINGS:
{AUDIT_FINDINGS}

AUTHORITATIVE AND CORRIGIBLE SOURCES:
{corpus}
"""
        curriculum, info = stream_json_call(
            client,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": curriculum_prompt}],
            partial_path=output / "curriculum_v5.partial.json",
            max_tokens=300000,
        )
        atomic_json(output / "curriculum_v5.json", curriculum)
        validation = validate_curriculum(curriculum)
        atomic_json(output / "validation.json", validation)
        (output / "curriculum_v5.md").write_text(render_markdown(curriculum), encoding="utf-8")
        state.update(
            status="active" if args.stage == "all" else ("complete" if validation["status"] == "PASS" else "needs_review"),
            stage="assets" if args.stage == "all" else "complete",
            curriculum_call=info,
            validation_status=validation["status"],
            lesson_count=validation["lesson_count"],
            updated_at=utc_now(),
        )
        atomic_json(state_path, state)
        if args.stage == "curriculum":
            return 0 if validation["status"] == "PASS" else 2
    else:
        curriculum = json.loads((output / "curriculum_v5.json").read_text(encoding="utf-8"))

    if args.stage in {"all", "assets"}:
        asset_prompt = f"""
Create a complete asset-acquisition plan for the frozen v5 curriculum below.
This is a separate third job: do not change lesson order, TOPIC, POINT, WORLD,
frontier language, or picture-book status.

Return one JSON object with this structure:
{{
  "metadata": {{...}},
  "regular_image_requirements": [
    {{
      "asset_id": "IMG-L001-001",
      "lesson_id": "L001",
      "instructional_purpose": "presentation|contrast|controlled_practice|evaluation|transfer",
      "concept_or_contrast": "what the images must make visually learnable",
      "quantity": 10,
      "reuse_allowed": true,
      "variation_dimensions": ["subject", "setting", "viewpoint"],
      "canonical_constraints": "...",
      "metadata_search_queries": ["concrete descriptive query"],
      "acquisition_strategy": "local_bank|metadata_download|flux|openai_image_fallback|mixed",
      "generation_brief": "prompt-neutral visual specification or null",
      "review_requirements": ["mechanical", "Gemma", "Luna-if-flagged", "Sol-if-unresolved"]
    }}
  ],
  "picture_books": [
    {{
      "book_id": "PB-Lnnn-01",
      "lesson_id": "Lnnn",
      "title": "...",
      "instructional_function": "...",
      "canonical_event": true,
      "characters": ["..."],
      "location": "...",
      "master_scene_strategy": "...",
      "pages": [
        {{
          "page_number": 1,
          "language_function": "...",
          "scene_description": "...",
          "characters": ["..."],
          "location": "...",
          "required_objects": ["..."],
          "continuity_constraints": "...",
          "derived_crops": ["..."]
        }}
      ],
      "asset_dependencies": ["canonical reference or regular asset ID"],
      "review_requirements": ["..."]
    }}
  ],
  "optional_picture_book_candidates": [
    {{"lesson_id": "Lnnn", "reason": "...", "priority": "high|medium|low"}}
  ],
  "shared_canonical_assets": [{{"asset": "...", "reason": "..."}}],
  "acquisition_summary": {{...}},
  "unresolved_asset_decisions": [{{"decision": "...", "impact": "..."}}]
}}

Rules:
- Every regular requirement is an instructional set, not necessarily one file.
- Specify enough variation to prevent spurious synonymy (for example, `itself`
  must not be represented only by cats).
- Prefer existing trusted local images, then metadata-guided downloads, then
  Flux; reserve OpenAI image generation for composition/continuity failures.
- Downloads and generated images require mechanical validation and local Gemma
  review, with Luna only for Gemma flags and Sol only when still unresolved.
- Canonical character/location references are picture-book-only and must remain
  separate from generic image-bank assets.
- A picture book must teach through an event, not merely repeat flashcards.
- Plan a book for every lesson marked `required`. For `optional` lessons, list
  only the strongest candidates separately; do not silently promote all of them.
- Respect the world bible, established chronology, Errol's embodiment limits,
  and Lesson 000's explicit no-picture-book rule.
- Use exact canonical names. Unnamed extras are allowed; invented recurring
  named characters and locations are not.
- Do not download or generate anything in this pass.

FROZEN V5 CURRICULUM:
{json.dumps(curriculum, ensure_ascii=False)}

WORLD BIBLE:
{(ROOT / 'training_data' / 'grounded_stories' / 'world_bible.md').read_text(encoding='utf-8')}

LESSON 000 SOURCE AND PICTURE-BOOK EXAMPLE:
{(ROOT / 'handoff' / '2023_08_20_lesson_000_example.md').read_text(encoding='utf-8')}
"""
        asset_plan, info = stream_json_call(
            client,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": asset_prompt}],
            partial_path=output / "asset_plan_v5.partial.json",
            max_tokens=300000,
        )
        atomic_json(output / "asset_plan_v5.json", asset_plan)
        asset_validation = validate_asset_plan(asset_plan, curriculum)
        atomic_json(output / "asset_validation.json", asset_validation)
        (output / "asset_plan_v5.md").write_text(render_asset_markdown(asset_plan), encoding="utf-8")
        curriculum_validation = json.loads((output / "validation.json").read_text(encoding="utf-8"))
        overall = "PASS" if curriculum_validation["status"] == "PASS" and asset_validation["status"] == "PASS" else "FAIL"
        state.update(
            status="complete" if overall == "PASS" else "needs_review",
            stage="complete",
            asset_call=info,
            asset_validation_status=asset_validation["status"],
            regular_requirement_count=asset_validation["regular_requirement_count"],
            regular_image_quantity=asset_validation["regular_image_quantity"],
            picture_book_count=asset_validation["picture_book_count"],
            picture_book_page_count=asset_validation["picture_book_page_count"],
            updated_at=utc_now(),
        )
        atomic_json(state_path, state)
        return 0 if overall == "PASS" else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
