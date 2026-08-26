#!/usr/bin/env python3
"""Build a resumable one-concept-at-a-time teaching lexicon with a local LLM."""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import subprocess
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from m2_teaching_lexicon_ledger import append as ledger_append
from m2_teaching_lexicon_ledger import claim as ledger_claim
from m2_teaching_lexicon_ledger import read_rows as ledger_read_rows


SCHEMA_VERSION = "ninereeds_m2_teaching_lexicon_mapping_v1"
RELATIONS = [
    "unchanged",
    "exact_synonym",
    "sense_clarification",
    "narrower_common_term",
    "broader_common_term",
    "related_teaching_substitute",
    "defer_original",
]
DECISION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "source_sense",
        "teaching_term",
        "teaching_sense",
        "mapping_relation",
        "recommended_action",
        "frequency_band",
        "teaching_utility",
        "image_compatibility",
        "rationale",
        "alternate_candidates",
        "ambiguities",
    ],
    "properties": {
        "source_sense": {"type": "string", "minLength": 1},
        "teaching_term": {"type": "string", "minLength": 1},
        "teaching_sense": {"type": "string", "minLength": 1},
        "mapping_relation": {"type": "string", "enum": RELATIONS},
        "recommended_action": {
            "type": "string",
            "enum": ["keep", "replace", "defer"],
        },
        "frequency_band": {
            "type": "string",
            "enum": ["very_common", "common", "less_common", "rare", "specialized"],
        },
        "teaching_utility": {
            "type": "string",
            "enum": ["foundational", "high", "useful", "specialized", "low"],
        },
        "image_compatibility": {
            "type": "string",
            "enum": ["unchanged", "review", "reselect", "not_visual"],
        },
        "rationale": {"type": "string", "minLength": 1},
        "alternate_candidates": {
            "type": "array",
            "maxItems": 3,
            "items": {"type": "string", "minLength": 1},
        },
        "ambiguities": {
            "type": "array",
            "maxItems": 5,
            "items": {"type": "string", "minLength": 1},
        },
    },
}

SYSTEM_PROMPT = """You are an expert applied linguist and language-curriculum designer.

For exactly one source concept from Ninereeds Campaign 35 M2, choose the English
term that should represent that concept in a future language-teaching curriculum.
Reason carefully about actual English frequency, communicative usefulness,
teachability, grammatical productivity, concreteness, and the supplied intended
sense. The curriculum will begin simply but is not restricted to K-2 vocabulary.

Preserve semantic lineage. Do not replace a source concept with an unrelated but
more fashionable word. Keeping the original is often correct. A replacement may
be a single word or a short fixed expression when that is clearly more natural for
teaching the intended sense. Distinguish exact synonyms, sense clarifications,
narrower or broader common terms, and merely related substitutes honestly.

Judge whether the original M2 images can still teach the chosen term. If the
semantic shift could invalidate them, require review or reselection. If the source
is ambiguous or the evidence conflicts, record that instead of inventing certainty.

This is an independent first-pass decision. Do not attempt to optimize the whole
2,500-item inventory, and do not avoid a good term merely because another concept
might independently map to it. Cross-item collisions will be audited later.

Use mapping_relation `unchanged` whenever teaching_term is the same term as the
source concept and recommended_action is `keep`. Use `defer_original` when the
same term is deferred. Reserve `exact_synonym` for a genuinely different term.

Think as long as useful, then return only the requested structured decision."""


class LocalLedger:
    def __init__(self, output: Path, worker_id: str) -> None:
        self.output = output
        self.worker_id = worker_id

    def completed(self) -> set[int]:
        return {row["source"]["ordinal"] for row in ledger_read_rows(self.output)}

    def claim(self, ordinal: int) -> bool:
        return ledger_claim(self.output, ordinal, self.worker_id)

    def append(self, row: dict[str, Any]) -> str:
        return ledger_append(self.output, row)


class RemoteLedger:
    def __init__(self, host: str, helper: str, output: str, worker_id: str) -> None:
        self.host = host
        self.helper = helper
        self.output = output
        self.worker_id = worker_id

    def _run(self, command: str, *arguments: str, input_text: str | None = None) -> Any:
        completed = subprocess.run(
            [
                "ssh", "--", self.host, "python3", self.helper,
                "--output", self.output, command, *arguments,
            ],
            input=input_text,
            text=True,
            capture_output=True,
            check=True,
        )
        return json.loads(completed.stdout)

    def completed(self) -> set[int]:
        return set(self._run("completed"))

    def claim(self, ordinal: int) -> bool:
        result = self._run(
            "claim", "--ordinal", str(ordinal), "--worker-id", self.worker_id,
        )
        return bool(result["claimed"])

    def append(self, row: dict[str, Any]) -> str:
        result = self._run("append", input_text=json.dumps(row, ensure_ascii=False))
        return str(result["status"])


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON at {path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"expected object at {path}:{line_number}")
            rows.append(row)
    return rows


def validate_curriculum(rows: list[dict[str, Any]]) -> None:
    ordinals = [row.get("ordinal") for row in rows]
    if ordinals != list(range(1, len(rows) + 1)):
        raise ValueError("curriculum ordinals must be contiguous and ordered from 1")
    concept_ids = [row.get("concept_id") for row in rows]
    if len(set(concept_ids)) != len(concept_ids):
        raise ValueError("curriculum concept_id values must be unique")


def completed_rows(path: Path) -> dict[int, dict[str, Any]]:
    if not path.exists():
        return {}
    completed: dict[int, dict[str, Any]] = {}
    for row in load_jsonl(path):
        if row.get("schema_version") != SCHEMA_VERSION:
            raise ValueError(f"unexpected schema version in {path}")
        ordinal = row.get("source", {}).get("ordinal")
        if not isinstance(ordinal, int) or ordinal in completed:
            raise ValueError(f"invalid or duplicate completed ordinal {ordinal!r}")
        completed[ordinal] = row
    return completed


def source_evidence(row: dict[str, Any], source_root: Path, lessons: list[dict[str, Any]]) -> str:
    source_path = source_root / str(row.get("source_path", ""))
    source_text = ""
    if source_path.is_file():
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
    evidence = {
        "curriculum_record": row,
        "original_source_text": source_text[:12_000],
        "campaign35_text_examples": lessons,
    }
    return json.dumps(evidence, ensure_ascii=False, indent=2)


def extract_content(response: dict[str, Any]) -> dict[str, Any]:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("response has no choices")
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, dict):
        decision = content
    elif isinstance(content, str):
        text = content.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        decision = json.loads(text)
    else:
        raise ValueError("response message has no JSON content")
    if not isinstance(decision, dict):
        raise ValueError("decision is not an object")
    missing = set(DECISION_SCHEMA["required"]) - set(decision)
    extra = set(decision) - set(DECISION_SCHEMA["properties"])
    if missing or extra:
        raise ValueError(f"decision keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}")
    if decision["mapping_relation"] not in RELATIONS:
        raise ValueError("decision has invalid mapping_relation")
    return decision


def request_decision(
    endpoint: str,
    model: str,
    evidence: str,
    timeout: float,
    token: str,
    json_mode: str,
    thinking: bool,
    reasoning_effort: str,
    max_tokens: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    schema_text = json.dumps(DECISION_SCHEMA, ensure_ascii=False, indent=2)
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Evaluate this one source concept and produce its mapping decision as JSON. "
                    "The JSON object must conform exactly to this schema:\n\n"
                    + schema_text
                    + "\n\nSOURCE EVIDENCE:\n"
                    + evidence
                ),
            },
        ],
        "temperature": 0.35,
        "top_p": 0.9,
        "response_format": ({
            "type": "json_schema",
            "json_schema": {
                "name": "m2_teaching_lexicon_decision",
                "strict": True,
                "schema": DECISION_SCHEMA,
            },
        } if json_mode == "json_schema" else {"type": "json_object"}),
    }
    if thinking:
        payload["thinking"] = {"type": "enabled"}
    if reasoning_effort:
        payload["reasoning_effort"] = reasoning_effort
    if max_tokens > 0:
        payload["max_tokens"] = max_tokens
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=None if timeout <= 0 else timeout) as response:
        raw = json.load(response)
    return extract_content(raw), raw.get("usage", {})


def append_durable(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--curriculum", type=Path, required=True)
    parser.add_argument("--text-lessons", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--endpoint", default="http://127.0.0.1:8080/v1/chat/completions")
    parser.add_argument("--model", default="qwen3.6-35b-a3b-q4-k-m-turboquant")
    parser.add_argument("--token-env", default="")
    parser.add_argument("--json-mode", choices=["json_schema", "json_object"], default="json_schema")
    parser.add_argument("--thinking", action="store_true")
    parser.add_argument("--reasoning-effort", choices=["", "high", "max"], default="")
    parser.add_argument("--max-tokens", type=int, default=0)
    parser.add_argument("--timeout-seconds", type=float, default=0)
    parser.add_argument("--max-attempts", type=int, default=0, help="0 retries forever")
    parser.add_argument("--start-ordinal", type=int, default=1)
    parser.add_argument("--stop-ordinal", type=int)
    parser.add_argument("--order", choices=["ascending", "descending"], default="ascending")
    parser.add_argument("--worker-id", default="qwen-ascending")
    parser.add_argument("--ssh-ledger-host", default="")
    parser.add_argument("--ssh-ledger-helper", default="")
    parser.add_argument("--ssh-ledger-output", default="")
    args = parser.parse_args()

    if args.ssh_ledger_host:
        if not args.ssh_ledger_helper or not args.ssh_ledger_output:
            parser.error("remote ledger requires --ssh-ledger-helper and --ssh-ledger-output")
        ledger: LocalLedger | RemoteLedger = RemoteLedger(
            args.ssh_ledger_host,
            args.ssh_ledger_helper,
            args.ssh_ledger_output,
            args.worker_id,
        )
    else:
        if args.output is None:
            parser.error("local ledger requires --output")
        ledger = LocalLedger(args.output, args.worker_id)
    token = os.environ.get(args.token_env, "") if args.token_env else ""
    if args.token_env and not token:
        parser.error(f"environment variable {args.token_env} is not set")

    curriculum = load_jsonl(args.curriculum)
    validate_curriculum(curriculum)
    lessons_by_ordinal: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for lesson in load_jsonl(args.text_lessons):
        ordinal = lesson.get("ordinal")
        if isinstance(ordinal, int):
            lessons_by_ordinal[ordinal].append(lesson)
    stop = args.stop_ordinal or len(curriculum)
    ordered_curriculum = curriculum if args.order == "ascending" else list(reversed(curriculum))

    while True:
        completed = ledger.completed()
        source = next((
            row for row in ordered_curriculum
            if args.start_ordinal <= row["ordinal"] <= stop
            and row["ordinal"] not in completed
            and ledger.claim(row["ordinal"])
        ), None)
        if source is None:
            break
        ordinal = source["ordinal"]
        evidence = source_evidence(source, args.source_root, lessons_by_ordinal[ordinal])
        attempt = 0
        while True:
            attempt += 1
            try:
                decision, usage = request_decision(
                    args.endpoint,
                    args.model,
                    evidence,
                    args.timeout_seconds,
                    token,
                    args.json_mode,
                    args.thinking,
                    args.reasoning_effort,
                    args.max_tokens,
                )
                source_term = source["concept"].strip().casefold()
                teaching_term = decision["teaching_term"].strip().casefold()
                same_term = teaching_term == source_term
                # Campaign concepts sometimes carry a numeric sense-disambiguator
                # (for example, "value 2") that is not part of the English lexeme.
                source_lexeme = re.sub(r"\s+\d+$", "", source_term)
                if same_term and decision["recommended_action"] == "keep":
                    decision["mapping_relation"] = "unchanged"
                elif same_term and decision["recommended_action"] == "defer":
                    decision["mapping_relation"] = "defer_original"
                elif teaching_term == source_lexeme and source_lexeme != source_term:
                    decision["mapping_relation"] = "sense_clarification"
                elif not same_term and decision["mapping_relation"] == "unchanged":
                    decision["mapping_relation"] = "exact_synonym"
                result = {
                    "schema_version": SCHEMA_VERSION,
                    "source": {
                        "campaign": "campaign35",
                        "branch": "M2",
                        "ordinal": ordinal,
                        "concept_id": source["concept_id"],
                        "concept": source["concept"],
                        "depends_on": source.get("depends_on", []),
                        "source_path": source.get("source_path", ""),
                        "source_sha256": source.get("source_sha256", ""),
                    },
                    "mapping": decision,
                    "generation": {
                        "model": args.model,
                        "attempt": attempt,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "usage": usage,
                    },
                }
                append_status = ledger.append(result)
                print(
                    f"{ordinal:04d}/{len(curriculum)} {source['concept']!r} -> "
                    f"{decision['teaching_term']!r} ({decision['recommended_action']}; {append_status})",
                    flush=True,
                )
                break
            except (
                OSError,
                ValueError,
                subprocess.CalledProcessError,
                urllib.error.URLError,
                urllib.error.HTTPError,
            ) as exc:
                print(f"ordinal {ordinal} attempt {attempt} failed: {exc}", flush=True)
                if args.max_attempts and attempt >= args.max_attempts:
                    raise
                delay = min(60.0, 2.0 ** min(attempt, 6)) + random.random()
                time.sleep(delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
