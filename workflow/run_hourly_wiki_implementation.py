#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
WIKI_DIR = REPO_ROOT / "training_data" / "wiki"
TODO_PATH = WIKI_DIR / "02_wiki_implementation_todo.md"
LOG_PATH = WIKI_DIR / "wiki_implementation_run_log.md"
MAX_TURNS = "18"

CHECKBOX_RE = re.compile(r"^(?P<prefix>\s*(?:\d+\.|[-*])\s+)\[(?P<mark>[ xX])\]\s+(?P<item>.+?)\s*$")
RATE_LIMIT_PATTERNS = [
    "rate limit",
    "429",
    "too many requests",
    "usage limit",
    "overloaded",
    "try again later",
    "exceeded your current quota",
]
SESSION_RATE_LIMIT_PATTERNS = [
    "session limit",
    "session usage limit",
    "conversation limit",
]
WEEKLY_RATE_LIMIT_PATTERNS = [
    "weekly limit",
    "weekly usage limit",
    "7-day limit",
    "7 day limit",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def find_todo_file() -> Path:
    if TODO_PATH.exists():
        return TODO_PATH
    raise FileNotFoundError(f"Could not find wiki implementation todo file: {TODO_PATH}")


def extract_todo_step_number(raw_line: str) -> Optional[str]:
    match = re.match(r"^\s*(\d+)\.\s+\[[ xX]\]\s+", raw_line)
    if match:
        return match.group(1)
    return None


def find_next_unchecked(todo_path: Path) -> Optional[dict]:
    lines = todo_path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
        match = CHECKBOX_RE.match(line)
        if match and match.group("mark") == " ":
            return {
                "line_number": index + 1,
                "raw_line": line,
                "item": match.group("item").strip(),
                "step_number": extract_todo_step_number(line),
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
        LOG_PATH.write_text("# Wiki Implementation Cron Log\n\n", encoding="utf-8")

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


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        text=True,
        capture_output=True,
    )


def classify_rate_limit(text: str) -> Optional[str]:
    lowered = text.lower()
    if any(pattern in lowered for pattern in WEEKLY_RATE_LIMIT_PATTERNS):
        return "weekly"
    if any(pattern in lowered for pattern in SESSION_RATE_LIMIT_PATTERNS):
        return "session"
    if any(pattern in lowered for pattern in RATE_LIMIT_PATTERNS):
        return "unknown"
    return None


def parse_claude_json(stdout: str) -> dict:
    return json.loads(stdout)


def parse_reported_files(text: str) -> list[str]:
    files: list[str] = []
    in_files_block = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line == "FILES:":
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
    rate_limit_type: str,
    consecutive_prior_rate_limits: int,
    rate_limits_in_recent_entries: int,
) -> str:
    if rate_limit_type != "unknown":
        return rate_limit_type
    if consecutive_prior_rate_limits >= 5 or rate_limits_in_recent_entries >= 5:
        return "weekly"
    return rate_limit_type


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
You are implementing one wiki backlog item inside the BDH Cognitive OS repository.

Repository root: {REPO_ROOT}
Selected todo step: {selected_step}
Selected todo item: {item}
Todo file: {todo_path}

Mandatory instructions:
- Read and follow AGENTS.md, README.md, and docs/wiki.md before editing.
- Implement ONLY the selected todo item above.
- Include the todo step number in your final report.
- Update the appropriate wiki file or files under training_data/wiki/.
- Update the todo file by marking the selected item as checked and add a short Notes line describing what you implemented.
- Do not modify bdh.py or anything under core/.
- Do not commit, push, or create branches.
- Keep edits minimal, explicit, and reproducible.
- If supporting context is needed, you may read wiki_category_backlog.md and level1_finish_and_level2_start_plan.md.
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


def main() -> int:
    try:
        todo_path = find_todo_file()
    except FileNotFoundError as exc:
        append_log("missing-todo", TODO_PATH, None, str(exc))
        print(str(exc))
        return 1

    next_item = find_next_unchecked(todo_path)
    if not next_item:
        summary = "No unchecked wiki implementation items were found."
        append_log("no-op", todo_path, None, summary)
        print(summary)
        return 0

    item = next_item["item"]
    step_number = next_item.get("step_number")
    prompt = build_prompt(todo_path, item, step_number)
    before_state = get_repo_state()
    command = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        "bypassPermissions",
        "--allowedTools",
        "Read,Edit,Write,Bash",
        "--max-turns",
        MAX_TURNS,
    ]
    result = run(command, REPO_ROOT)
    combined_output = (result.stdout or "") + "\n" + (result.stderr or "")
    rate_limit_type = classify_rate_limit(combined_output)

    if result.returncode != 0:
        if rate_limit_type:
            prior_rate_limit_streak = count_consecutive_rate_limit_skips(LOG_PATH)
            recent_rate_limit_count = count_rate_limit_skips_in_recent_entries(LOG_PATH, window=10)
            refined_rate_limit_type = refine_rate_limit_type(
                rate_limit_type,
                prior_rate_limit_streak,
                recent_rate_limit_count,
            )
            limit_label_map = {
                "weekly": "weekly rate limit",
                "session": "session rate limit",
                "unknown": "rate limit",
            }
            limit_label = limit_label_map[refined_rate_limit_type]
            if rate_limit_type == "unknown" and refined_rate_limit_type == "weekly":
                summary = (
                    "Claude Code hit a rate limit again. Based on the recent cron history "
                    "(this run plus either a 6-run streak or 5 of the last 10 logged entries also being rate-limited), "
                    "this is likely the weekly cap. Skipping this run and retrying next hour."
                )
                status = "weekly-cap-likely-skip"
            else:
                summary = f"Claude Code hit a {limit_label}. Skipping this run and retrying next hour."
                status = "rate-limited-skip"
            display_summary = format_summary_with_step(summary, step_number)
            append_log(status, todo_path, item, summary, step_number=step_number, extra=combined_output[-4000:])
            print(display_summary)
            return 0
        summary = f"Claude Code failed with exit code {result.returncode}."
        append_log("error", todo_path, item, summary, step_number=step_number, extra=combined_output[-4000:])
        print(format_summary_with_step(summary, step_number))
        print(combined_output)
        return result.returncode

    try:
        payload = parse_claude_json(result.stdout)
        claude_text = payload.get("result", "").strip()
    except json.JSONDecodeError:
        claude_text = result.stdout.strip()

    after_state = get_repo_state()
    reported_files = parse_reported_files(claude_text)
    changed_files = reported_files or sorted(after_state - before_state)
    status_match = re.search(r"^STATUS:\s*(.+)$", claude_text, re.MULTILINE)
    summary_match = re.search(r"^SUMMARY:\s*(.+)$", claude_text, re.MULTILINE)
    status = status_match.group(1).strip() if status_match else "completed"
    summary = summary_match.group(1).strip() if summary_match else "Claude Code completed the run."

    append_log(status, todo_path, item, summary, step_number=step_number, changed_files=changed_files, extra=claude_text[-4000:])
    print(format_summary_with_step(summary, step_number))
    return 0


if __name__ == "__main__":
    sys.exit(main())
