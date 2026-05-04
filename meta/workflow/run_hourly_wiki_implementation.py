#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = REPO_ROOT / "training_data" / "wiki"
TODO_PATH = REPO_ROOT / "todo.md"
HISTORY_PATH = REPO_ROOT / "history.md"
LOG_PATH = REPO_ROOT / "archive" / "workflow" / "hourly_worker_log.md"
STATE_PATH = REPO_ROOT / "workflow" / "hourly_wiki_executor_state.json"
MAX_TURNS = "18"
TEMP_GEMINI_FALLBACK_HOURS = 4
HERMES_ENV_PATH = Path.home() / ".hermes" / ".env"

PRIMARY_EXECUTOR = {
    "name": "Gemini 2.5 Pro",
    "command": "gemini",
    "model": "gemini-2.5-pro",
    "kind": "gemini",
}
FALLBACK_EXECUTOR = {
    "name": "Gemini 3 Flash",
    "command": "gemini",
    "model": "gemini-3-flash-preview",
    "kind": "gemini",
}

CHECKBOX_RE = re.compile(r"^(?P<prefix>\s*(?:\d+\.|[-*])\s+)\[(?P<mark>[ xX])\]\s+(?P<item>.+?)\s*$")
GENERIC_RATE_LIMIT_PATTERNS = [
    "rate limit",
    "429",
    "too many requests",
    "usage limit",
    "overloaded",
    "try again later",
    "exceeded your current quota",
]
TEMPORARY_RATE_LIMIT_PATTERNS = [
    "cooldown",
    "please wait",
    "retry later",
    "retry-later",
    "session cap",
    "session limit",
    "session usage limit",
    "conversation cap",
    "conversation limit",
    "out of extra usage",
]
WEEKLY_RATE_LIMIT_PATTERNS = [
    "weekly limit",
    "weekly usage cap",
    "weekly usage limit",
    "weekly cap",
    "7-day limit",
    "7 day limit",
    "reset-next-week",
    "reset next week",
    "resets next week",
]


def utc_now_dt() -> datetime:
    return datetime.now(timezone.utc)


def utc_now() -> str:
    return utc_now_dt().strftime("%Y-%m-%d %H:%M:%S UTC")


def parse_iso_utc(raw: Optional[str]) -> Optional[datetime]:
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def find_todo_file() -> Path:
    if TODO_PATH.exists():
        return TODO_PATH
    raise FileNotFoundError(f"Could not find root todo file: {TODO_PATH}")


def extract_todo_step_number(raw_line: str) -> Optional[str]:
    match = re.match(r"^\s*(\d+)\.\s+\[[ xX]\]\s+", raw_line)
    if match:
        return match.group(1)
    return None


def find_next_unchecked(todo_path: Path) -> Optional[dict[str, str]]:
    lines = todo_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        match = CHECKBOX_RE.match(line)
        if match and match.group("mark") == " ":
            return {
                "line_number": str(index + 1),
                "raw_line": line,
                "item": match.group("item").strip(),
                "step_number": extract_todo_step_number(line) or "",
            }
    return None


def format_summary_with_step(summary: str, step_number: Optional[str]) -> str:
    if step_number:
        return f"Step {step_number}: {summary}"
    return summary


def append_log(
    status: str,
    todo_path: Path,
    item: Optional[str],
    summary: str,
    step_number: Optional[str] = None,
    changed_files: Optional[list[str]] = None,
    extra: Optional[str] = None,
) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LOG_PATH.exists():
        LOG_PATH.write_text("# Training-Data Hourly Worker Log\n\n", encoding="utf-8")

    lines = [
        f"## {utc_now()} — {status}",
        f"- todo file: `{todo_path.relative_to(REPO_ROOT)}`",
        f"- step: {step_number}" if step_number else "- step: none",
        f"- item: `{item}`" if item else "- item: none",
        f"- summary: {summary}",
    ]
    if changed_files is not None:
        if changed_files:
            lines.append("- changed files:")
            lines.extend(f"  - `{path}`" for path in changed_files)
        else:
            lines.append("- changed files: none")
    if extra:
        lines.append("- details:")
        for line in extra.strip().splitlines():
            lines.append(f"  {line}")
    lines.append("")

    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines))


def load_hermes_env() -> dict[str, str]:
    env = os.environ.copy()
    if not HERMES_ENV_PATH.exists():
        return env

    for raw_line in HERMES_ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env.setdefault(key.strip(), value.strip().strip('"').strip("'"))
    return env


def run(command: list[str], cwd: Path, env: Optional[dict[str, str]] = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
        env=env,
    )


def classify_rate_limit(text: str) -> Optional[str]:
    lowered = text.lower()
    if any(pattern in lowered for pattern in WEEKLY_RATE_LIMIT_PATTERNS):
        return "weekly"
    if any(pattern in lowered for pattern in TEMPORARY_RATE_LIMIT_PATTERNS):
        return "temporary"
    if any(pattern in lowered for pattern in GENERIC_RATE_LIMIT_PATTERNS):
        return "unknown"
    return None


def parse_executor_json(stdout: str) -> dict[str, Any]:
    return json.loads(stdout)


def maybe_parse_executor_payload(stdout: str) -> Optional[dict[str, Any]]:
    try:
        payload = parse_executor_json(stdout)
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def parse_reported_files(text: str) -> list[str]:
    files: list[str] = []
    in_files_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if "FILES:" in line:
            in_files_block = True
            continue
        if not in_files_block:
            continue
        if not line.startswith("-"):
            break
        path = line[1:].strip()
        if not path or path.lower() == "none":
            continue
        files.append(path)
    return files


def extract_report_field(text: str, label: str) -> Optional[str]:
    anchored_matches = re.findall(rf"(?:^|\n)\s*{re.escape(label)}:\s*(.+)$", text, re.MULTILINE)
    if anchored_matches:
        return anchored_matches[-1].strip()
    loose_matches = re.findall(rf"{re.escape(label)}:\s*(.+)", text)
    if loose_matches:
        return loose_matches[-1].strip()
    return None


def read_logged_statuses(log_path: Path) -> list[str]:
    if not log_path.exists():
        return []
    statuses: list[str] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## ") and " — " in line:
            statuses.append(line.rsplit(" — ", 1)[1].strip())
    return statuses


def count_consecutive_rate_limit_skips(log_path: Path) -> int:
    count = 0
    for status in reversed(read_logged_statuses(log_path)):
        if status in {"rate-limited-skip", "weekly-cap-likely-skip"}:
            count += 1
            continue
        break
    return count


def count_rate_limit_skips_in_recent_entries(log_path: Path, window: int = 10) -> int:
    recent_statuses = read_logged_statuses(log_path)[-window:]
    return sum(status in {"rate-limited-skip", "weekly-cap-likely-skip"} for status in recent_statuses)


def refine_rate_limit_type(
    executor_name: str,
    rate_limit_type: str,
    consecutive_prior_rate_limits: int,
    rate_limits_in_recent_entries: int,
) -> str:
    _ = executor_name, consecutive_prior_rate_limits, rate_limits_in_recent_entries
    if rate_limit_type != "unknown":
        return rate_limit_type
    return "temporary"


def get_repo_state() -> set[str]:
    result = run(["git", "status", "--short", "--untracked-files=all"], REPO_ROOT)
    files: set[str] = set()
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        files.add(line[3:].strip() if len(line) >= 4 else line.strip())
    return files


def build_prompt(todo_path: Path, item: str, step_number: Optional[str]) -> str:
    selected_step = step_number or "unknown"
    return f"""
You are implementing one backlog item from the root todo inside the BDH Cognitive OS repository.

Repository root: {REPO_ROOT}
Selected todo step: {selected_step}
Selected todo item: {item}
Todo file: {todo_path}
History file: {HISTORY_PATH}

Mandatory instructions:
- Read and follow AGENTS.md, README.md, todo.md, history.md, and docs/wiki.md before editing.
- Implement ONLY the selected todo item above.
- Include the todo step number in your final report.
- Update the appropriate files required by the selected item. Relevant edits may live under training_data/wiki/, training_data/triplet_stories/, training_data/phases/, docs/, or workflow/.
- Keep `todo.md` as the single source of unfinished work. When the selected task is complete, remove that task from `todo.md` and move it into `history.md` under an appropriate completed section.
- If the selected task creates obvious follow-up work, add new unchecked tasks to `todo.md` immediately in the correct stage.
- Do not modify bdh.py or anything under core/.
- Do not commit, push, or create branches.
- Keep edits minimal, explicit, and reproducible.
- If supporting context is needed, you may read archived legacy docs under `archive/`, wiki_category_backlog.md, story_tier_specs.md, wiki_expansion_index.md, wiki_entry_expansion_index.md, and dependency_graph.json.
- After finishing, print a concise final report in exactly this format:

STATUS: success
STEP: {selected_step}
SUMMARY: <one short paragraph>
FILES:
- path/to/file1
- path/to/file2

If implementation is blocked for a non-rate-limit reason, print:

STATUS: blocked
STEP: {selected_step}
SUMMARY: <reason>
FILES:
- none
""".strip()


def build_executor_command(executor: dict[str, Any], prompt: str) -> list[str]:
    if executor["kind"] == "claude":
        return [
            executor["command"],
            "-p",
            prompt,
            "--model",
            executor["model"],
            "--output-format",
            "json",
            "--max-turns",
            MAX_TURNS,
            "--allowedTools",
            "Read,Edit,Write,Bash",
        ]
    return [
        executor["command"],
        "-p",
        prompt,
        "--model",
        executor["model"],
        "--output-format",
        "json",
        "--approval-mode",
        "yolo",
    ]


def execute_with_executor(executor: dict[str, Any], prompt: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    command = build_executor_command(executor, prompt)
    return run(command, REPO_ROOT, env=env)


def parse_executor_output(stdout: str) -> str:
    payload = maybe_parse_executor_payload(stdout)
    if payload is None:
        return stdout.strip()
    return (payload.get("response") or payload.get("result") or "").strip()


def executor_payload_subtype(stdout: str) -> str:
    payload = maybe_parse_executor_payload(stdout)
    if payload is None:
        return ""
    return str(payload.get("subtype") or "").strip().lower()


def executor_payload_is_success(stdout: str) -> bool:
    subtype = executor_payload_subtype(stdout)
    if subtype:
        return subtype == "success"
    return True


def load_executor_state() -> dict[str, Any]:
    default_state = {
        "mode": "gemini_primary",
        "temporary_flash_until": None,
        "weekly_flash_since": None,
        "last_limit_reason": None,
    }
    if not STATE_PATH.exists():
        return default_state
    try:
        payload = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return default_state
    if not isinstance(payload, dict):
        return default_state
    mode = str(payload.get("mode") or default_state["mode"])
    if mode == "gemini_primary":
        mode = "gemini_primary"
    return {
        "mode": mode,
        "temporary_flash_until": payload.get("temporary_flash_until"),
        "weekly_flash_since": payload.get("weekly_flash_since"),
        "last_limit_reason": payload.get("last_limit_reason"),
    }


def save_executor_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def clear_expired_temporary_fallback(state: dict[str, Any], now: datetime) -> bool:
    until = parse_iso_utc(state.get("temporary_flash_until"))
    if state.get("mode") != "temporary_flash" or not until:
        return False
    if now < until:
        return False
    state["mode"] = "gemini_primary"
    state["temporary_flash_until"] = None
    state["last_limit_reason"] = None
    return True


def activate_temporary_flash_fallback(state: dict[str, Any], now: datetime, reason: str) -> str:
    until = now + timedelta(hours=TEMP_GEMINI_FALLBACK_HOURS)
    state["mode"] = "temporary_flash"
    state["temporary_flash_until"] = until.isoformat()
    state["last_limit_reason"] = reason
    return until.isoformat()


def activate_weekly_flash_mode(state: dict[str, Any], now: datetime, reason: str) -> None:
    state["mode"] = "weekly_flash"
    state["weekly_flash_since"] = now.isoformat()
    state["temporary_flash_until"] = None
    state["last_limit_reason"] = reason


def maybe_persist_fallback_for_explicit_primary_limit_signal(
    state: dict[str, Any],
    signal_text: str,
    now: datetime,
) -> Optional[str]:
    signal_type = classify_rate_limit(signal_text)
    if signal_type == "weekly":
        activate_weekly_flash_mode(state, now, signal_text[-1000:])
        save_executor_state(state)
        return "Gemini 2.5 Pro hit a weekly limit; switching to Gemini 3 Flash full-time."
    if signal_type in {"temporary", "unknown"}:
        until = activate_temporary_flash_fallback(state, now, signal_text[-1000:])
        save_executor_state(state)
        return f"Gemini 2.5 Pro hit a temporary limit; switching to Gemini 3 Flash until {until}."
    return None


def persist_temporary_flash_fallback_for_primary_executor_issue(
    state: dict[str, Any],
    now: datetime,
    reason: str,
) -> str:
    until = activate_temporary_flash_fallback(state, now, reason[-1000:])
    save_executor_state(state)
    return f"Gemini 2.5 Pro issue detected; keeping Gemini 3 Flash active until {until}."


def select_executor_from_state(state: dict[str, Any], now: datetime) -> tuple[dict[str, Any], Optional[str]]:
    if clear_expired_temporary_fallback(state, now):
        save_executor_state(state)
    if state.get("mode") == "weekly_flash":
        return FALLBACK_EXECUTOR, "weekly"
    until = parse_iso_utc(state.get("temporary_flash_until"))
    if state.get("mode") == "temporary_flash" and until and now < until:
        return FALLBACK_EXECUTOR, "temporary"
    return PRIMARY_EXECUTOR, None


def describe_active_mode(state_reason: Optional[str], state: dict[str, Any]) -> Optional[str]:
    if state_reason == "weekly":
        since = state.get("weekly_flash_since") or "unknown"
        return f"Executor mode: Gemini 3 Flash full-time after Gemini 2.5 Pro weekly limit ({since})."
    if state_reason == "temporary":
        until = state.get("temporary_flash_until") or "unknown"
        return f"Executor mode: temporary Gemini 3 Flash fallback active until {until} after Gemini 2.5 Pro limit."
    return None


def run_selected_executor(
    executor: dict[str, Any],
    prompt: str,
    env: dict[str, str],
    state: dict[str, Any],
    step_number: Optional[str],
    todo_path: Path,
    item: str,
) -> tuple[subprocess.CompletedProcess[str], dict[str, Any], list[str]]:
    notes: list[str] = []
    result = execute_with_executor(executor, prompt, env)
    combined_output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    rate_limit_type = classify_rate_limit(combined_output)
    payload_success = executor_payload_is_success(result.stdout or "")

    if executor["name"] != PRIMARY_EXECUTOR["name"] or not rate_limit_type:
        return result, executor, notes

    if result.returncode == 0 and payload_success:
        return result, executor, notes

    prior_rate_limit_streak = count_consecutive_rate_limit_skips(LOG_PATH)
    recent_rate_limit_count = count_rate_limit_skips_in_recent_entries(LOG_PATH, window=10)
    refined_rate_limit_type = refine_rate_limit_type(
        executor["name"],
        rate_limit_type,
        prior_rate_limit_streak,
        recent_rate_limit_count,
    )
    now = utc_now_dt()

    if refined_rate_limit_type == "weekly":
        activate_weekly_flash_mode(state, now, combined_output[-1000:])
        save_executor_state(state)
        notes.append("Gemini 2.5 Pro hit a weekly limit; switching to Gemini 3 Flash full-time.")
    else:
        until = activate_temporary_flash_fallback(state, now, combined_output[-1000:])
        save_executor_state(state)
        notes.append(f"Gemini 2.5 Pro hit a temporary limit; switching to Gemini 3 Flash until {until}.")

    fallback_result = execute_with_executor(FALLBACK_EXECUTOR, prompt, env)
    return fallback_result, FALLBACK_EXECUTOR, notes


def main() -> int:
    try:
        todo_path = find_todo_file()
    except FileNotFoundError as exc:
        append_log("missing-todo", TODO_PATH, None, str(exc))
        print(str(exc))
        return 1

    next_item = find_next_unchecked(todo_path)
    if not next_item:
        summary = "No unchecked root-todo items were found."
        append_log("no-op", todo_path, None, summary)
        print(summary)
        return 0

    item = next_item["item"]
    step_number = next_item.get("step_number") or None
    prompt = build_prompt(todo_path, item, step_number)
    before_state = get_repo_state()
    env = load_hermes_env()

    executor_state = load_executor_state()
    selected_executor, active_mode_reason = select_executor_from_state(executor_state, utc_now_dt())
    mode_note = describe_active_mode(active_mode_reason, executor_state)

    result, final_executor, switch_notes = run_selected_executor(
        selected_executor,
        prompt,
        env,
        executor_state,
        step_number,
        todo_path,
        item,
    )
    combined_output = ((result.stdout or "") + "\n" + (result.stderr or "")).strip()
    rate_limit_type = classify_rate_limit(combined_output)

    executor_text_preview = parse_executor_output(result.stdout) if result.stdout else ""
    malformed_success = (
        result.returncode == 0
        and (
            not executor_text_preview
            or extract_report_field(executor_text_preview, "STATUS") is None
            or extract_report_field(executor_text_preview, "SUMMARY") is None
            or "FILES:" not in executor_text_preview
        )
    )
    if malformed_success:
        retry_prompt = prompt + "\n\nIMPORTANT RETRY: Your previous response did not follow the required exact STATUS/SUMMARY/FILES format. Retry the SAME selected task now and end with the exact required report format. Do not just say that the run is complete."
        if final_executor["name"] == PRIMARY_EXECUTOR["name"]:
            fallback_note = maybe_persist_fallback_for_explicit_primary_limit_signal(executor_state, combined_output, utc_now_dt())
            if not fallback_note:
                fallback_note = persist_temporary_flash_fallback_for_primary_executor_issue(
                    executor_state,
                    utc_now_dt(),
                    combined_output or "malformed-success-output",
                )
            retry_result = execute_with_executor(FALLBACK_EXECUTOR, retry_prompt, env)
            retry_executor = FALLBACK_EXECUTOR
            retry_switch_notes = [
                "Gemini 2.5 Pro returned malformed success output; switching immediately to Gemini 3 Flash."
                + (f" {fallback_note}" if fallback_note else "")
            ]
        else:
            retry_result, retry_executor, retry_switch_notes = run_selected_executor(
                final_executor,
                retry_prompt,
                env,
                executor_state,
                step_number,
                todo_path,
                item,
            )
        retry_combined_output = ((retry_result.stdout or "") + "\n" + (retry_result.stderr or "")).strip()
        if retry_result.returncode == 0:
            result = retry_result
            final_executor = retry_executor
            combined_output = retry_combined_output
            rate_limit_type = classify_rate_limit(combined_output)
            switch_notes = [*switch_notes, *retry_switch_notes, "Retried once after malformed executor output."]
        else:
            combined_output = retry_combined_output
            rate_limit_type = classify_rate_limit(combined_output)

    if result.returncode != 0:
        if rate_limit_type:
            limit_label_map = {
                "weekly": "weekly rate limit",
                "temporary": "temporary rate limit",
                "unknown": "rate limit",
            }
            limit_label = limit_label_map[rate_limit_type]
            summary = f"{final_executor['name']} hit a {limit_label}. Skipping this run and retrying later."
            details = [*(switch_notes or [])]
            if mode_note:
                details.append(mode_note)
            details.append(combined_output[-4000:])
            append_log(
                "rate-limited-skip",
                todo_path,
                item,
                summary,
                step_number=step_number,
                extra="\n".join(part for part in details if part),
            )
            print(format_summary_with_step(summary, step_number))
            return 0

        summary = f"{final_executor['name']} failed with exit code {result.returncode}."
        details = [*(switch_notes or [])]
        if mode_note:
            details.append(mode_note)
        details.append(combined_output[-4000:])
        append_log(
            "error",
            todo_path,
            item,
            summary,
            step_number=step_number,
            extra="\n".join(part for part in details if part),
        )
        print(format_summary_with_step(summary, step_number))
        print(combined_output)
        return result.returncode

    executor_text = parse_executor_output(result.stdout)
    after_state = get_repo_state()
    reported_files = parse_reported_files(executor_text)
    changed_files = reported_files or sorted(after_state - before_state)
    status = extract_report_field(executor_text, "STATUS") or ""
    summary = extract_report_field(executor_text, "SUMMARY") or ""

    if not status or not summary:
        summary = f"{final_executor['name']} returned malformed success output without STATUS/SUMMARY."
        details = [*(switch_notes or [])]
        if mode_note:
            details.append(mode_note)
        details.append(f"Final executor: {final_executor['name']}")
        details.append(executor_text[-4000:])
        append_log(
            "malformed-output",
            todo_path,
            item,
            summary,
            step_number=step_number,
            changed_files=changed_files,
            extra="\n".join(part for part in details if part),
        )
        print(format_summary_with_step(summary, step_number))
        return 1

    if status.lower() == "success" and not changed_files:
        if final_executor["name"] == PRIMARY_EXECUTOR["name"]:
            fallback_note = maybe_persist_fallback_for_explicit_primary_limit_signal(executor_state, combined_output, utc_now_dt())
            if not fallback_note:
                fallback_note = persist_temporary_flash_fallback_for_primary_executor_issue(
                    executor_state,
                    utc_now_dt(),
                    executor_text or combined_output or "empty-success-no-op",
                )
            gemini_prompt = prompt + "\n\nIMPORTANT RETRY: Gemini 2.5 Pro reported success but changed no files. Repeat the SAME selected task now with the exact required STATUS/SUMMARY/FILES format and actually complete the task."
            gemini_result = execute_with_executor(FALLBACK_EXECUTOR, gemini_prompt, env)
            gemini_output = ((gemini_result.stdout or "") + "\n" + (gemini_result.stderr or "")).strip()
            if gemini_result.returncode == 0:
                result = gemini_result
                final_executor = FALLBACK_EXECUTOR
                combined_output = gemini_output
                rate_limit_type = classify_rate_limit(combined_output)
                switch_notes = [
                    *switch_notes,
                    "Gemini 2.5 Pro reported success but changed no files; switching immediately to Gemini 3 Flash."
                    + (f" {fallback_note}" if fallback_note else ""),
                ]
                executor_text = parse_executor_output(result.stdout)
                after_state = get_repo_state()
                reported_files = parse_reported_files(executor_text)
                changed_files = reported_files or sorted(after_state - before_state)
                status = extract_report_field(executor_text, "STATUS") or ""
                summary = extract_report_field(executor_text, "SUMMARY") or ""
            else:
                empty_summary = f"Gemini 2.5 Pro reported success but changed no files, and the Gemini 3 Flash fallback failed."
                details = [*(switch_notes or [])]
                if mode_note:
                    details.append(mode_note)
                details.append(f"Final executor: {final_executor['name']}")
                details.append(executor_text[-4000:])
                details.append(gemini_output[-4000:])
                append_log(
                    "empty-success",
                    todo_path,
                    item,
                    empty_summary,
                    step_number=step_number,
                    changed_files=[],
                    extra="\n".join(part for part in details if part),
                )
                print(format_summary_with_step(empty_summary, step_number))
                return 1

        if status.lower() == "success" and not changed_files:
            empty_summary = f"{final_executor['name']} reported success but changed no files. Treating this run as incomplete."
            details = [*(switch_notes or [])]
            if mode_note:
                details.append(mode_note)
            details.append(f"Final executor: {final_executor['name']}")
            details.append(executor_text[-4000:])
            append_log(
                "empty-success",
                todo_path,
                item,
                empty_summary,
                step_number=step_number,
                changed_files=[],
                extra="\n".join(part for part in details if part),
            )
            print(format_summary_with_step(empty_summary, step_number))
            return 1

    summary_prefixes = []
    if switch_notes:
        summary_prefixes.extend(switch_notes)
    elif mode_note:
        summary_prefixes.append(mode_note)
    if final_executor["name"] == FALLBACK_EXECUTOR["name"] and not summary_prefixes:
        summary_prefixes.append("Run executed with Gemini 3 Flash fallback policy.")
    final_summary = " ".join(summary_prefixes + [summary]).strip()

    details = [*(switch_notes or [])]
    if mode_note:
        details.append(mode_note)
    details.append(f"Final executor: {final_executor['name']}")
    details.append(executor_text[-4000:])
    append_log(
        status,
        todo_path,
        item,
        final_summary,
        step_number=step_number,
        changed_files=changed_files,
        extra="\n".join(part for part in details if part),
    )
    print(format_summary_with_step(final_summary, step_number))
    return 0


if __name__ == "__main__":
    sys.exit(main())
