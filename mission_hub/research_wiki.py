"""Structural and source-freshness checks for the Ninereeds research wiki."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
from typing import Any


PAGE_SCHEMA_VERSION = "ninereeds_research_wiki_page_v1"
METADATA_PATTERN = re.compile(r"^<!-- ninereeds-wiki: (\{.*\}) -->$")
MARKDOWN_LINK_PATTERN = re.compile(r"\[[^]]+\]\(([^)]+\.md)\)")


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain one JSON object")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def page_metadata(path: Path) -> dict[str, Any]:
    first_line = path.read_text(encoding="utf-8").splitlines()[0]
    match = METADATA_PATTERN.fullmatch(first_line)
    if match is None:
        raise ValueError("first line is not Ninereeds wiki metadata")
    value = json.loads(match.group(1))
    if not isinstance(value, dict):
        raise ValueError("wiki metadata must be a JSON object")
    return value


def lint(repo_root: Path) -> dict[str, Any]:
    root = repo_root.resolve()
    research = root / "mission_hub" / "research"
    wiki = root / "mission_hub" / "wiki"
    errors: list[str] = []

    required_contracts = [
        research / "README.md",
        research / "wiki-schema.json",
        research / "sources.json",
        research / "librarian-contract.json",
        research / "sol-planning-checklist.json",
        research / "question-dispositions.json",
        research / "campaign-design-catalogue.json",
        research / "permanent-campaign-questions.json",
        research / "luna-librarian-runbook.md",
        research / "sol-research-runbook.md",
        research / "schemas" / "campaign-goals.schema.json",
        research / "schemas" / "campaign-findings.schema.json",
        research / "schemas" / "question-review.schema.json",
        research / "schemas" / "prerequisite-work.schema.json",
        research / "templates" / "campaign_goals.md",
        research / "templates" / "campaign_findings.md",
        research / "examples" / "campaign-transition-example.json",
        research / "examples" / "prerequisite-work-examples.json",
    ]
    for path in required_contracts:
        if not path.is_file():
            errors.append(f"missing research contract: {path.relative_to(root)}")
    if errors:
        return {"ok": False, "errors": errors}

    try:
        schema = _json(research / "wiki-schema.json")
        registry = _json(research / "sources.json")
        librarian = _json(research / "librarian-contract.json")
        checklist = _json(research / "sol-planning-checklist.json")
        dispositions = _json(research / "question-dispositions.json")
        design_catalogue = _json(research / "campaign-design-catalogue.json")
        permanent_questions = _json(research / "permanent-campaign-questions.json")
        contract_schemas = [
            _json(research / "schemas" / name)
            for name in (
                "campaign-goals.schema.json",
                "campaign-findings.schema.json",
                "question-review.schema.json",
                "prerequisite-work.schema.json",
            )
        ]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return {"ok": False, "errors": [f"invalid research contract: {exc}"]}

    if schema.get("schema_version") != "ninereeds_research_wiki_schema_v1":
        errors.append("unknown research wiki schema version")
    required_pages = schema.get("required_pages")
    page_types = set(schema.get("page_types", []))
    page_statuses = set(schema.get("page_statuses", []))
    required_metadata = set(schema.get("required_metadata", []))
    if not isinstance(required_pages, list) or not all(isinstance(x, str) for x in required_pages):
        errors.append("wiki schema required_pages must be a string array")
        required_pages = []

    sources = registry.get("sources")
    if registry.get("schema_version") != "ninereeds_research_source_registry_v1":
        errors.append("unknown research source registry version")
    if not isinstance(sources, list):
        errors.append("research source registry sources must be an array")
        sources = []
    source_ids: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            errors.append("research source entry must be an object")
            continue
        source_id = source.get("id")
        path_value = source.get("path")
        expected = source.get("sha256")
        if not isinstance(source_id, str) or not source_id:
            errors.append("research source has no valid id")
            continue
        if source_id in source_ids:
            errors.append(f"duplicate research source id: {source_id}")
        source_ids.add(source_id)
        if not isinstance(path_value, str) or not isinstance(expected, str):
            errors.append(f"source {source_id} requires path and sha256")
            continue
        path = (root / path_value).resolve()
        if path != root and root not in path.parents:
            errors.append(f"source {source_id} escapes repository root")
        elif not path.is_file():
            errors.append(f"source {source_id} is missing: {path_value}")
        elif _sha256(path) != expected:
            errors.append(f"source {source_id} hash changed: {path_value}")

    if not wiki.is_dir():
        errors.append("missing mission_hub/wiki directory")
        pages: list[Path] = []
    else:
        pages = sorted(wiki.rglob("*.md"))
    for name in required_pages:
        if not (wiki / name).is_file():
            errors.append(f"missing required wiki page: {name}")

    page_ids: set[str] = set()
    metadata_by_path: dict[Path, dict[str, Any]] = {}
    for path in pages:
        relative = path.relative_to(wiki)
        try:
            metadata = page_metadata(path)
        except (IndexError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"invalid metadata in {relative}: {exc}")
            continue
        metadata_by_path[path] = metadata
        missing = required_metadata - set(metadata)
        if missing:
            errors.append(f"{relative} metadata missing: {', '.join(sorted(missing))}")
        if metadata.get("schema_version") != PAGE_SCHEMA_VERSION:
            errors.append(f"{relative} has unknown page schema version")
        page_id = metadata.get("page_id")
        if not isinstance(page_id, str) or not page_id:
            errors.append(f"{relative} has no valid page_id")
        elif page_id in page_ids:
            errors.append(f"duplicate wiki page_id: {page_id}")
        else:
            page_ids.add(page_id)
        if metadata.get("page_type") not in page_types:
            errors.append(f"{relative} has invalid page_type")
        if metadata.get("status") not in page_statuses:
            errors.append(f"{relative} has invalid status")
        references = metadata.get("source_ids")
        if not isinstance(references, list) or not all(isinstance(x, str) for x in references):
            errors.append(f"{relative} source_ids must be a string array")
        else:
            for source_id in references:
                if source_id not in source_ids:
                    errors.append(f"{relative} cites unknown source: {source_id}")

        body = path.read_text(encoding="utf-8")
        for target_value in MARKDOWN_LINK_PATTERN.findall(body):
            if "://" in target_value or target_value.startswith("#"):
                continue
            target = (path.parent / target_value.split("#", 1)[0]).resolve()
            if target != wiki and wiki not in target.parents:
                errors.append(f"{relative} link escapes wiki: {target_value}")
            elif not target.is_file():
                errors.append(f"{relative} has broken link: {target_value}")

    index = wiki / "index.md"
    if index.is_file():
        index_targets = {
            (index.parent / value.split("#", 1)[0]).resolve()
            for value in MARKDOWN_LINK_PATTERN.findall(index.read_text(encoding="utf-8"))
        }
        for path in pages:
            if path != index and path.resolve() not in index_targets:
                errors.append(f"wiki page is absent from index: {path.relative_to(wiki)}")

    if librarian.get("schema_version") != "ninereeds_librarian_contract_v1":
        errors.append("unknown librarian contract version")
    if librarian.get("role") != "luna_librarian":
        errors.append("research wiki writer must be luna_librarian")

    steps = checklist.get("steps")
    if checklist.get("schema_version") != "ninereeds_sol_campaign_planning_checklist_v2":
        errors.append("unknown Sol planning checklist version")
    allowed_step_dispositions = checklist.get("step_dispositions")
    if not isinstance(allowed_step_dispositions, list) or set(allowed_step_dispositions) != {
        "completed_with_evidence", "not_applicable", "insufficient_evidence", "blocked",
    }:
        errors.append("Sol planning checklist has invalid step dispositions")
    if not isinstance(steps, list) or not steps:
        errors.append("Sol planning checklist must contain steps")
    else:
        step_ids = [step.get("id") for step in steps if isinstance(step, dict)]
        if len(step_ids) != len(steps) or any(not isinstance(x, str) or not x for x in step_ids):
            errors.append("every Sol planning step requires an id")
        elif len(step_ids) != len(set(step_ids)):
            errors.append("Sol planning step ids must be unique")
        for step in steps:
            if isinstance(step, dict) and not step.get("evidence"):
                errors.append(f"Sol planning step has no evidence contract: {step.get('id')}")

    if dispositions.get("schema_version") != "ninereeds_research_question_dispositions_v1":
        errors.append("unknown research question disposition version")
    epistemic = dispositions.get("epistemic_answers")
    if not isinstance(epistemic, list):
        errors.append("epistemic_answers must be an array")
    else:
        epistemic_ids = [item.get("id") for item in epistemic if isinstance(item, dict)]
        required_epistemic = {
            "not_tested", "insufficient_evidence", "inconclusive_conflicting_evidence",
            "yes_supported", "no_contradicted", "question_invalid_or_underspecified", "other",
        }
        if set(epistemic_ids) != required_epistemic:
            errors.append("research question epistemic answer set is incomplete")
    for contract_schema in contract_schemas:
        if contract_schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
            errors.append(f"research contract {contract_schema.get('$id')} has unknown JSON Schema draft")

    if design_catalogue.get("schema_version") != "ninereeds_campaign_design_catalogue_v1":
        errors.append("unknown campaign design catalogue version")
    for field in ("research_purposes", "execution_designs"):
        entries = design_catalogue.get(field)
        if not isinstance(entries, list) or not entries:
            errors.append(f"campaign design catalogue {field} must be a non-empty array")
            continue
        ids = [entry.get("id") for entry in entries if isinstance(entry, dict)]
        if len(ids) != len(entries) or any(not isinstance(item, str) or not item for item in ids):
            errors.append(f"campaign design catalogue {field} entries require ids")
        elif len(ids) != len(set(ids)):
            errors.append(f"campaign design catalogue {field} ids must be unique")

    if permanent_questions.get("schema_version") != "ninereeds_permanent_campaign_questions_v1":
        errors.append("unknown permanent campaign question version")
    permanent = permanent_questions.get("questions")
    if not isinstance(permanent, list) or not permanent:
        errors.append("permanent campaign questions must be a non-empty array")
    else:
        permanent_ids = [item.get("id") for item in permanent if isinstance(item, dict)]
        if len(permanent_ids) != len(permanent) or len(permanent_ids) != len(set(permanent_ids)):
            errors.append("permanent campaign questions require unique ids")

    return {
        "ok": not errors,
        "errors": errors,
        "source_count": len(source_ids),
        "page_count": len(metadata_by_path),
        "planning_step_count": len(steps) if isinstance(steps, list) else 0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["lint"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = lint(args.root)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
