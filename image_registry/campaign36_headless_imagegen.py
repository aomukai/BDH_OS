"""Run Campaign 36 built-in ImageGen fallback in isolated headless Codex tasks.

Generation is parallel, but imports are serialized through the existing append-only
ImageGen/Luna bridge.  Each child is ephemeral and may invoke built-in ``$imagegen``
exactly once; API and CLI image-generation fallbacks are explicitly forbidden.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
import fcntl
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from typing import Any
import urllib.request

from PIL import Image

from image_registry.campaign36_flux_streaming_luna import (
    append_jsonl,
    effective_visible_text_policy,
    load_jsonl,
)
from image_registry.campaign36_imagegen_fallback import (
    DEFAULT_ROOT,
    MAX_PROVIDER_ATTEMPTS,
    completed_assignments,
    active_override,
    brainstorms,
    exhausted_assignments,
    prompt_for,
    provider_attempts,
    brainstorm_state,
    representation_overrides,
    source_attempts,
    superseded_assignments,
)


SCHEMA_VERSION = "ninereeds_campaign36_headless_imagegen_v1"
DEFAULT_CODEX = Path("/home/aomukai/.local/bin/codex")
DEFAULT_REPO = Path("/home/aomukai/Ninereeds")
DEFAULT_HANDOFF_REPORT = DEFAULT_REPO / "handoff/2026_08_22_image_representation_ideas_needed.md"
DEFAULT_GENERATED_CACHE = Path("/home/aomukai/.codex/generated_images")
DEFAULT_LEXICON = DEFAULT_REPO / "config/mission_hub/campaign_material/campaign36/m2-teaching-lexicon.jsonl"
LEASE_MINUTES = 90
TEXT_DEPENDENT_EVIDENCE = re.compile(
    r"\b(?:written|text|word|phrase|sentence|label|caption|spelling|apostrophe|equation|formula)\b",
    re.IGNORECASE,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def timestamp() -> str:
    return utc_now().isoformat()


def job_id(assignment: str, provider_attempt: int) -> str:
    return f"{assignment}-ig{provider_attempt:02d}"


def append_event(path: Path, row: dict[str, Any]) -> None:
    append_jsonl(path, {"schema_version": SCHEMA_VERSION, "at": timestamp(), **row})


def latest_job_events(path: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path, tolerate_partial_tail=True):
        latest[row["job_id"]] = row
    return latest


def active_assignments(path: Path) -> set[str]:
    cutoff = utc_now() - timedelta(minutes=LEASE_MINUTES)
    active: set[str] = set()
    for row in latest_job_events(path).values():
        if row["status"] not in {"reserved", "generating", "generated"}:
            continue
        try:
            recorded = datetime.fromisoformat(row["at"])
        except (KeyError, ValueError):
            continue
        if recorded >= cutoff:
            active.add(row["assignment_id"])
    return active


def representation_conflict(source: dict[str, Any]) -> str | None:
    """Text-dependent contracts are reviewable because Luna adjudicates their writing."""
    return None


def latest_decisions(output: Path) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(output / "decisions.jsonl", tolerate_partial_tail=True):
        assignment = row["assignment_id"]
        if assignment not in latest or int(row["generation_attempt"]) > int(latest[assignment]["generation_attempt"]):
            latest[assignment] = row
    return latest


def load_teaching_senses(path: Path = DEFAULT_LEXICON) -> dict[str, dict[str, Any]]:
    senses: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path, tolerate_partial_tail=True):
        concept_id = row.get("source", {}).get("concept_id")
        mapping = row.get("mapping", {})
        if concept_id:
            senses[concept_id] = {
                "teaching_term": mapping.get("teaching_term"),
                "teaching_sense": mapping.get("teaching_sense"),
                "source_sense": mapping.get("source_sense"),
                "ambiguities": mapping.get("ambiguities") or [],
            }
    return senses


def write_handoff_report(root: Path, report_path: Path) -> None:
    """Publish a compact, replaceable dashboard of representation decisions."""
    output = root / "imagegen-v1"
    attempts = provider_attempts(output)
    decisions = latest_decisions(output)
    done = completed_assignments(output)
    superseded = superseded_assignments(output)
    sources = source_attempts(root / "streaming-luna")
    exhausted = {row["assignment_id"]: row for row in exhausted_assignments(root / "streaming-luna")}
    brainstorm_by_assignment: dict[str, list[dict[str, Any]]] = {}
    brainstorm_by_cycle = brainstorms(output)
    overrides_by_assignment = representation_overrides(output)
    teaching_senses = load_teaching_senses()
    for row in load_jsonl(output / "brainstorms.jsonl", tolerate_partial_tail=True):
        brainstorm_by_assignment.setdefault(row["assignment_id"], []).append(row)

    manual: list[dict[str, Any]] = []
    automatic: list[dict[str, Any]] = []
    for assignment, recorded in sorted(attempts.items()):
        if assignment in done or assignment in superseded or assignment not in decisions:
            continue
        active_brainstorm, required_after = brainstorm_state(
            output, assignment, recorded, brainstorm_by_cycle
        )
        override = active_override(
            output, assignment, recorded, overrides_by_assignment
        )
        decision = decisions[assignment]
        source_decision = exhausted.get(assignment)
        source = sources.get(source_decision["attempt_id"]) if source_decision else None
        row = {
            "assignment": assignment,
            "attempts": recorded,
            "words": decision.get("concept_ids") or (source or {}).get("concept_ids", []),
            "evidence": (source or {}).get("evidence_by_concept", {}),
            "failures": decision.get("failure_reasons", []),
            "instruction": decision.get("recommission_instruction"),
            "brainstorms": brainstorm_by_assignment.get(assignment, []),
            "senses": {
                concept_id: teaching_senses.get(concept_id, {})
                for concept_id in (decision.get("concept_ids") or (source or {}).get("concept_ids", []))
            },
        }
        if required_after == -1 and override is None:
            manual.append(row)
        else:
            stage = "human override in progress" if override else (
                "Gemma brainstorm pending" if required_after is not None else (
                    "Gemma prompts in progress" if active_brainstorm else "initial ImageGen attempts"
                )
            )
            row["stage"] = stage
            automatic.append(row)

    # This is deliberately a human idea queue, not an operational dashboard.
    # Consolidate repeated failed assignments for the same word and expose only
    # the two things the user needs to brainstorm: the word and its fixed sense.
    needed: dict[str, str] = {}
    for row in manual:
        for concept_id in row["words"]:
            sense = row["senses"].get(concept_id, {})
            word = sense.get("teaching_term") or concept_id
            description = sense.get("teaching_sense") or sense.get("source_sense")
            if not description:
                description = row["evidence"].get(concept_id, "Meaning not recorded.")
            needed.setdefault(word, description)

    lines = ["# Words needing image ideas", ""]
    if needed:
        for word, description in sorted(needed.items()):
            lines.append(f"- **{word}** — {description}")
    else:
        lines.append("Nothing currently needs ideas.")
    lines.append("")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    temporary = report_path.with_suffix(report_path.suffix + ".tmp")
    temporary.write_text("\n".join(lines), encoding="utf-8")
    temporary.replace(report_path)


def gemma_prompt(source: dict[str, Any], decisions: list[dict[str, Any]]) -> str:
    return """You are brainstorming recovery prompts for a visual language curriculum.
The exact teaching target is fixed. Propose up to five substantially different,
generation-ready visual representations that preserve it exactly and address all rejection
evidence. Request five, but return only sound ideas; one to four is acceptable. Do not add
labels or visible writing unless the fixed contract explicitly requires them. If the contract
is contradictory or no honest image can directly teach it, return zero ideas and explain the
conflict. Return JSON only:
{"ideas":[{"title":"short name","prompt":"complete image-generation prompt"}],"conflict":"none or exact conflict"}

FIXED CONTRACT:
""" + json.dumps({
        "concept_ids": source["concept_ids"],
        "words": source.get("words", source["concept_ids"]),
        "evidence_by_concept": source.get("evidence_by_concept", {}),
    }, ensure_ascii=False, indent=2) + "\n\nREJECTED IMAGEGEN ATTEMPTS:\n" + json.dumps([
        {
            "provider_attempt": int(row["generation_attempt"]) - 3,
            "failure_reasons": row.get("failure_reasons", []),
            "recommission_instruction": row.get("recommission_instruction"),
        }
        for row in decisions
    ], ensure_ascii=False, indent=2)


def request_gemma(
    endpoint: str, model: str, source: dict[str, Any], decisions: list[dict[str, Any]], retries: int = 3,
) -> dict[str, Any]:
    prompt = gemma_prompt(source, decisions)
    body = json.dumps({
        "model": model,
        "temperature": 1.15,
        "top_p": 0.95,
        "top_k": 60,
        "max_tokens": 4096,
        "response_format": {"type": "json_object"},
        "chat_template_kwargs": {"enable_thinking": False},
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    last_error: Exception | None = None
    for retry in range(retries):
        try:
            request = urllib.request.Request(
                endpoint, data=body,
                headers={"Authorization": "Bearer local", "Content-Type": "application/json"},
            )
            with urllib.request.urlopen(request, timeout=300) as response:
                document = json.load(response)
            raw = document["choices"][0]["message"]["content"].strip()
            if raw.startswith("```"):
                raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
            result = json.loads(raw)
            ideas = result.get("ideas")
            if not isinstance(ideas, list) or len(ideas) > 5:
                raise ValueError("Gemma returned an invalid idea list")
            clean = []
            for idea in ideas:
                title = str(idea.get("title") or "").strip()
                prompt_text = str(idea.get("prompt") or "").strip()
                if title and prompt_text:
                    clean.append({"title": title, "prompt": prompt_text})
            return {"prompt": prompt, "ideas": clean, "conflict": str(result.get("conflict") or "none")}
        except Exception as exc:
            last_error = exc
            if retry + 1 < retries:
                time.sleep(2 ** retry)
    raise RuntimeError(f"Gemma brainstorm failed after {retries} attempts: {last_error}")


def ensure_brainstorm(args: argparse.Namespace) -> bool:
    """Create at most one required post-cap brainstorm; return whether one was attempted."""
    output = args.root / "imagegen-v1"
    existing = brainstorms(output)
    done = completed_assignments(output)
    superseded = superseded_assignments(output)
    attempts = provider_attempts(output)
    sources = source_attempts(args.root / "streaming-luna")
    exhausted = exhausted_assignments(args.root / "streaming-luna")
    quarantine = {
        row["assignment_id"]
        for row in load_jsonl(output / "representation-quarantine.jsonl", tolerate_partial_tail=True)
    }
    all_decisions = load_jsonl(output / "decisions.jsonl", tolerate_partial_tail=True)
    for decision in exhausted:
        assignment = decision["assignment_id"]
        recorded = attempts.get(assignment, 0)
        active_brainstorm, required_after = brainstorm_state(
            output, assignment, recorded, existing
        )
        if required_after == -1:
            if assignment not in quarantine:
                source = sources[decision["attempt_id"]]
                append_event(output / "representation-quarantine.jsonl", {
                    "assignment_id": assignment,
                    "flux_attempt_id": decision["attempt_id"],
                    "concept_ids": source["concept_ids"],
                    "words": source.get("words", source["concept_ids"]),
                    "reason": "All Gemma recovery prompts exhausted after three ImageGen attempts each.",
                    "status": "joint_manual_ideation_required",
                })
            continue
        if (
            assignment in done or assignment in superseded or assignment in quarantine or required_after is None
            or (assignment, required_after) in existing
        ):
            continue
        source = sources[decision["attempt_id"]]
        relevant = [row for row in all_decisions if row["assignment_id"] == assignment]
        result = request_gemma(args.gemma_endpoint, args.gemma_model, source, relevant)
        record = {
            "schema_version": SCHEMA_VERSION,
            "at": timestamp(),
            "assignment_id": assignment,
            "after_attempt": required_after,
            "model": args.gemma_model,
            "sampling": {"temperature": 1.15, "top_p": 0.95, "top_k": 60},
            **result,
        }
        append_jsonl(output / "brainstorms.jsonl", record)
        if not result["ideas"]:
            append_event(output / "representation-quarantine.jsonl", {
                "assignment_id": assignment,
                "flux_attempt_id": decision["attempt_id"],
                "concept_ids": source["concept_ids"],
                "words": source.get("words", source["concept_ids"]),
                "reason": f"Gemma produced zero viable recovery prompts: {result['conflict']}",
                "status": "joint_manual_ideation_required",
            })
        print(json.dumps({
            "assignment_id": assignment, "status": "brainstormed",
            "ideas": len(result["ideas"]), "conflict": result["conflict"],
        }), flush=True)
        return True
    return False


def reserve_jobs(root: Path, limit: int) -> list[dict[str, Any]]:
    output = root / "imagegen-v1"
    output.mkdir(parents=True, exist_ok=True)
    events = output / "headless-jobs.jsonl"
    quarantine_path = output / "representation-quarantine.jsonl"
    lock_path = output / "headless-jobs.lock"
    lock_path.touch(exist_ok=True)
    with lock_path.open("r+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        exhausted = exhausted_assignments(root / "streaming-luna")
        done = completed_assignments(output)
        superseded = superseded_assignments(output)
        attempts = provider_attempts(output)
        brainstorm_by_cycle = brainstorms(output)
        imagegen_latest = latest_decisions(output)
        active = active_assignments(events)
        source_by_attempt = source_attempts(root / "streaming-luna")
        overrides = representation_overrides(output)
        quarantined = {
            row["assignment_id"]
            for row in load_jsonl(quarantine_path, tolerate_partial_tail=True)
        }
        jobs: list[dict[str, Any]] = []
        for decision in exhausted:
            assignment = decision["assignment_id"]
            if (
                assignment in done or assignment in superseded or assignment in active
                or (assignment in quarantined and assignment not in overrides)
            ):
                continue
            recorded_attempts = attempts.get(assignment, 0)
            brainstorm, required_after = brainstorm_state(
                output, assignment, recorded_attempts, brainstorm_by_cycle
            )
            override = active_override(
                output, assignment, recorded_attempts, overrides
            )
            if required_after == -1 and override is None:
                continue
            if required_after not in {None, -1} and not (brainstorm and brainstorm.get("ideas")):
                continue
            provider_attempt = recorded_attempts + 1
            source = source_by_attempt[decision["attempt_id"]]
            if override:
                source = {
                    **source,
                    "evidence_by_concept": override["evidence_by_concept"],
                    "words": override.get("words") or source.get("words"),
                    "grounding_mode": override.get(
                        "grounding_mode", source.get("grounding_mode", "direct")
                    ),
                    "visible_text_policy": override.get("visible_text_policy", "reject"),
                    "visible_text_note": override.get("visible_text_note"),
                }
            conflict = representation_conflict(source)
            if conflict:
                append_event(
                    quarantine_path,
                    {
                        "assignment_id": assignment,
                        "flux_attempt_id": decision["attempt_id"],
                        "concept_ids": source["concept_ids"],
                        "words": source.get("words", source["concept_ids"]),
                        "reason": conflict,
                        "status": "representation_triage_required",
                    },
                )
                quarantined.add(assignment)
                continue
            identifier = job_id(assignment, provider_attempt)
            effective_decision = (
                {**decision, "recommission_instruction": override["representation_prompt"]}
                if override else decision
            )
            generation_prompt = prompt_for(source, effective_decision)
            idea = None
            if brainstorm:
                ideas = brainstorm["ideas"]
                brainstorm_after = int(brainstorm["after_attempt"])
                offset = max(0, recorded_attempts - brainstorm_after)
                idea = ideas[min(len(ideas) - 1, offset // MAX_PROVIDER_ATTEMPTS)]
                generation_prompt += (
                    "\nGemma recovery representation selected for this prompt cycle:\n"
                    f"- {idea['title']}: {idea['prompt']}\n"
                    "Use this as the concrete visual strategy without changing the exact teaching targets."
                )
                prior = imagegen_latest.get(assignment)
                if prior and prior.get("recommission_instruction") not in {None, "none"}:
                    generation_prompt += f"\nLatest Luna correction: {prior['recommission_instruction']}"
            if override:
                generation_prompt += (
                    "\nUser-approved representation after manual triage:\n"
                    f"{override['representation_prompt']}\n"
                    "This representation supersedes the earlier contradictory road-marking wording."
                )
            row = {
                "job_id": identifier,
                "assignment_id": assignment,
                "provider_attempt": provider_attempt,
                "flux_attempt_id": decision["attempt_id"],
                "concept_ids": source["concept_ids"],
                "words": source.get("words", source["concept_ids"]),
                "prompt": generation_prompt,
                "brainstorm_after_attempt": int(brainstorm["after_attempt"]) if brainstorm else None,
                "brainstorm_idea": idea,
                "representation_override": override,
                "status": "reserved",
            }
            append_event(events, row)
            jobs.append(row)
            if len(jobs) >= limit:
                break
        return jobs


def child_prompt(job: dict[str, Any], output_path: Path) -> str:
    return f"""Use the $imagegen skill and built-in ImageGen tool exactly once.

Generate this single project-bound image using the specification between BEGIN and END.
Do not use an API, OPENAI_API_KEY, SDK, script, or CLI image generator. If built-in
ImageGen is unavailable, fail without substituting another generator.

BEGIN IMAGE SPECIFICATION
{job['prompt']}
END IMAGE SPECIFICATION

This is a scientific-educational image. Keep all important content comfortably inside
safe crop margins because it will be normalized to 4:3. After generation, copy the
chosen generated bitmap from Codex's generated-images directory to this exact path:
{output_path}

Do not review, revise, import, or describe the image. Do not call ImageGen a second
time. Finish with exactly one short line: SAVED <absolute path>, or FAILED <reason>.
"""


def validate_generated(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"headless Codex did not create {path}")
    with Image.open(path) as image:
        image.load()
        if min(image.size) < 256:
            raise ValueError(f"generated image is too small: {image.size}")


def file_digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            value.update(chunk)
    return value.hexdigest()


def cleanup_own_generated_cache_copy(
    image_path: Path,
    *,
    not_before_ns: int,
    cache_root: Path = DEFAULT_GENERATED_CACHE,
) -> list[str]:
    """Remove only cache files created for this job and copied to ``image_path``.

    The generated-image cache also contains user and other-task assets.  Content
    identity plus the subprocess start time avoids touching those pre-existing
    files, while preventing thousands of redundant originals from filling `/`.
    """
    if not image_path.is_file() or not cache_root.is_dir():
        return []
    expected_size = image_path.stat().st_size
    expected_digest = file_digest(image_path)
    removed: list[str] = []
    for candidate in cache_root.rglob("*"):
        try:
            metadata = candidate.stat()
        except FileNotFoundError:
            continue
        if (
            not candidate.is_file()
            or metadata.st_mtime_ns < not_before_ns
            or metadata.st_size != expected_size
        ):
            continue
        if file_digest(candidate) != expected_digest:
            continue
        candidate.unlink()
        removed.append(str(candidate))
        parent = candidate.parent
        while parent != cache_root:
            try:
                parent.rmdir()
            except OSError:
                break
            parent = parent.parent
    return removed


def generate_one(
    job: dict[str, Any], *, root: Path, repo: Path, codex: Path, model: str, timeout: int,
) -> dict[str, Any]:
    output = root / "imagegen-v1"
    staging = output / "headless-staging"
    logs = output / "headless-logs"
    prompts = output / "prompts"
    staging.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)
    prompts.mkdir(parents=True, exist_ok=True)
    identifier = job["job_id"]
    image_path = staging / f"{identifier}.png"
    prompt_path = prompts / f"{identifier}-headless.txt"
    final_path = logs / f"{identifier}-last.txt"
    stdout_path = logs / f"{identifier}.log"
    prompt = child_prompt(job, image_path)
    prompt_path.write_text(prompt, encoding="utf-8")
    append_event(output / "headless-jobs.jsonl", {**job, "status": "generating"})
    command = [
        str(codex), "exec", "--ephemeral", "--enable", "image_generation",
        "--model", model, "--sandbox", "workspace-write", "--cd", str(repo),
        "--add-dir", str(staging), "--output-last-message", str(final_path), "-",
    ]
    started_ns = time.time_ns()
    try:
        with prompt_path.open("r", encoding="utf-8") as stdin, stdout_path.open(
            "w", encoding="utf-8"
        ) as transcript:
            completed = subprocess.run(
                command, stdin=stdin, stdout=transcript, stderr=subprocess.STDOUT,
                text=True, timeout=timeout, check=False,
            )
        validate_generated(image_path)
        if completed.returncode != 0:
            raise RuntimeError(f"codex exited {completed.returncode} after producing an image")
    except Exception as exc:
        diagnostic = "\n".join(
            path.read_text(encoding="utf-8", errors="replace")[-8000:]
            for path in (final_path, stdout_path)
            if path.is_file()
        )
        result = {
            **job,
            "status": "generation_failed",
            "error": f"{type(exc).__name__}: {exc}",
            "prompt_file": str(prompt_path),
            "transcript": str(stdout_path),
        }
        append_event(output / "headless-jobs.jsonl", result)
        safety_markers = (
            "blocked by the safety system",
            "rejected by the safety system",
            '"code": "moderation_blocked"',
        )
        if any(marker in diagnostic.lower() for marker in safety_markers):
            append_event(output / "representation-quarantine.jsonl", {
                "assignment_id": job["assignment_id"],
                "flux_attempt_id": job["flux_attempt_id"],
                "concept_ids": job["concept_ids"],
                "words": job.get("words", job["concept_ids"]),
                "reason": "Built-in ImageGen blocked the request under provider safety policy.",
                "status": "provider_safety_blocked",
            })
        return result
    removed_cache = cleanup_own_generated_cache_copy(
        image_path, not_before_ns=started_ns,
    )
    result = {
        **job,
        "status": "generated",
        "image": str(image_path),
        "prompt_file": str(prompt_path),
        "transcript": str(stdout_path),
        "cache_artifacts_removed": removed_cache,
    }
    append_event(output / "headless-jobs.jsonl", result)
    return result


def import_review(job: dict[str, Any], *, root: Path, repo: Path, timeout: int) -> dict[str, Any]:
    output = root / "imagegen-v1"
    command = [
        "/home/aomukai/.venvs/ninereeds-cortex/bin/python", "-m",
        "image_registry.campaign36_imagegen_fallback", "--root", str(root),
        "import-review", "--assignment", job["assignment_id"],
        "--image", job["image"], "--prompt-file", job["prompt_file"],
        "--provider-attempt", str(job["provider_attempt"]), "--timeout", str(timeout),
    ]
    completed = subprocess.run(
        command, cwd=repo, text=True, capture_output=True, timeout=timeout + 60,
        check=False,
    )
    status = "reviewed" if completed.returncode in {0, 2} else "import_failed"
    result = {
        **job,
        "status": status,
        "import_returncode": completed.returncode,
        "import_stdout": completed.stdout[-4000:],
        "import_stderr": completed.stderr[-4000:],
    }
    append_event(output / "headless-jobs.jsonl", result)
    return result


def run_batch(args: argparse.Namespace) -> int:
    ensure_brainstorm(args)
    jobs = reserve_jobs(args.root, min(args.limit, args.workers))
    if not jobs:
        write_handoff_report(args.root, args.handoff_report)
        print(json.dumps({"status": "idle", "reason": "no eligible assignments"}))
        return 0
    generated: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                generate_one, job, root=args.root, repo=args.repo, codex=args.codex,
                model=args.model, timeout=args.generation_timeout,
            ): job
            for job in jobs
        }
        for future in as_completed(futures):
            result = future.result()
            print(json.dumps({k: result.get(k) for k in ("job_id", "status", "error")}), flush=True)
            if result["status"] == "generated":
                generated.append(result)
    reviewed = [
        import_review(job, root=args.root, repo=args.repo, timeout=args.review_timeout)
        for job in generated
    ]
    summary = {
        "status": "batch_complete",
        "reserved": len(jobs),
        "generated": len(generated),
        "reviewed": sum(row["status"] == "reviewed" for row in reviewed),
        "import_failed": sum(row["status"] == "import_failed" for row in reviewed),
    }
    write_handoff_report(args.root, args.handoff_report)
    print(json.dumps(summary, sort_keys=True), flush=True)
    return 0 if summary["generated"] == len(jobs) and not summary["import_failed"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--repo", type=Path, default=DEFAULT_REPO)
    parser.add_argument("--codex", type=Path, default=DEFAULT_CODEX)
    parser.add_argument("--model", default="gpt-5.6-luna")
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--limit", type=int, default=2)
    parser.add_argument("--generation-timeout", type=int, default=900)
    parser.add_argument("--review-timeout", type=int, default=600)
    parser.add_argument("--gemma-endpoint", default="http://127.0.0.1:8792/v1/chat/completions")
    parser.add_argument("--gemma-model", default="gemma-4-26b-a4b-it-q4km")
    parser.add_argument("--handoff-report", type=Path, default=DEFAULT_HANDOFF_REPORT)
    parser.add_argument("--report-only", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=30)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or not 1 <= args.limit <= 32:
        raise SystemExit("workers must be 1..8 and limit must be 1..32")
    if args.report_only:
        write_handoff_report(args.root, args.handoff_report)
        print(args.handoff_report)
        return 0
    while True:
        result = run_batch(args)
        if not args.loop:
            return result
        if result != 0:
            print(
                json.dumps(
                    {
                        "status": "batch_degraded_continuing",
                        "reason": "recoverable per-job failure was persisted for retry",
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        time.sleep(args.poll_seconds)


if __name__ == "__main__":
    raise SystemExit(main())
