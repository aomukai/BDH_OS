import importlib.util
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "workflow" / "run_hourly_wiki_implementation.py"
spec = importlib.util.spec_from_file_location("hourly_wiki", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class RateLimitHeuristicTests(unittest.TestCase):
    def test_unknown_claude_limit_becomes_weekly_after_five_prior_rate_limits_in_last_ten_entries(self):
        self.assertEqual(
            module.refine_rate_limit_type(
                module.CLAUDE_EXECUTOR["name"],
                "unknown",
                consecutive_prior_rate_limits=2,
                rate_limits_in_recent_entries=5,
            ),
            "weekly",
        )

    def test_unknown_claude_limit_becomes_temporary_when_recent_window_is_below_threshold(self):
        self.assertEqual(
            module.refine_rate_limit_type(
                module.CLAUDE_EXECUTOR["name"],
                "unknown",
                consecutive_prior_rate_limits=4,
                rate_limits_in_recent_entries=4,
            ),
            "temporary",
        )

    def test_explicit_temporary_limit_is_not_overridden_by_recent_window(self):
        self.assertEqual(
            module.refine_rate_limit_type(
                module.CLAUDE_EXECUTOR["name"],
                "temporary",
                consecutive_prior_rate_limits=10,
                rate_limits_in_recent_entries=9,
            ),
            "temporary",
        )

    def test_unknown_gemini_limit_is_treated_as_temporary(self):
        self.assertEqual(
            module.refine_rate_limit_type(
                module.GEMINI_EXECUTOR["name"],
                "unknown",
                consecutive_prior_rate_limits=10,
                rate_limits_in_recent_entries=9,
            ),
            "temporary",
        )

    def test_counts_trailing_rate_limit_streak_from_log(self):
        log_text = """# Wiki Implementation Cron Log

## 2026-04-17 00:00:00 UTC — success
## 2026-04-17 01:00:00 UTC — rate-limited-skip
## 2026-04-17 02:00:00 UTC — weekly-cap-likely-skip
## 2026-04-17 03:00:00 UTC — rate-limited-skip
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "wiki_implementation_run_log.md"
            log_path.write_text(log_text, encoding="utf-8")
            self.assertEqual(module.count_consecutive_rate_limit_skips(log_path), 3)

    def test_counts_rate_limit_entries_within_recent_window(self):
        log_text = """# Wiki Implementation Cron Log

## 2026-04-17 00:00:00 UTC — rate-limited-skip
## 2026-04-17 01:00:00 UTC — success
## 2026-04-17 02:00:00 UTC — rate-limited-skip
## 2026-04-17 03:00:00 UTC — no-op
## 2026-04-17 04:00:00 UTC — rate-limited-skip
## 2026-04-17 05:00:00 UTC — success
## 2026-04-17 06:00:00 UTC — weekly-cap-likely-skip
## 2026-04-17 07:00:00 UTC — success
## 2026-04-17 08:00:00 UTC — rate-limited-skip
## 2026-04-17 09:00:00 UTC — success
## 2026-04-17 10:00:00 UTC — rate-limited-skip
"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_path = Path(tmpdir) / "wiki_implementation_run_log.md"
            log_path.write_text(log_text, encoding="utf-8")
            self.assertEqual(module.count_rate_limit_skips_in_recent_entries(log_path, window=10), 5)

    def test_classify_rate_limit_detects_cooldown_and_weekly_patterns(self):
        self.assertEqual(module.classify_rate_limit("Claude is on cooldown, please wait."), "temporary")
        self.assertEqual(module.classify_rate_limit("You hit the weekly usage limit."), "weekly")

    def test_classify_rate_limit_detects_cap_phrases_and_hyphenated_reset_phrase(self):
        self.assertEqual(module.classify_rate_limit("Claude conversation cap reached; retry-later."), "temporary")
        self.assertEqual(module.classify_rate_limit("Claude weekly usage cap reached; reset-next-week."), "weekly")


class TodoStepReportingTests(unittest.TestCase):
    def test_extracts_numeric_step_number_from_ordered_checkbox_line(self):
        self.assertEqual(module.extract_todo_step_number("9. [ ] Audit `mathematical_concepts_entries.md`"), "9")

    def test_find_next_unchecked_includes_step_number(self):
        todo_text = """# Demo\n\n1. [x] Done item\n2. [ ] Pending item\n"""
        with tempfile.TemporaryDirectory() as tmpdir:
            todo_path = Path(tmpdir) / "todo.md"
            todo_path.write_text(todo_text, encoding="utf-8")
            next_item = module.find_next_unchecked(todo_path)
            self.assertEqual(next_item["step_number"], "2")
            self.assertEqual(next_item["item"], "Pending item")

    def test_build_prompt_requests_step_number_in_final_report(self):
        prompt = module.build_prompt(Path("/tmp/todo.md"), "Pending item", "14")
        self.assertIn("Selected todo step: 14", prompt)
        self.assertIn("STEP: 14", prompt)

    def test_format_summary_with_step_prefixes_summary(self):
        self.assertEqual(
            module.format_summary_with_step("Completed cleanup pass.", "13"),
            "Step 13: Completed cleanup pass.",
        )


class ExecutorStateTests(unittest.TestCase):
    def test_temporary_fallback_selects_gemini_until_expiry(self):
        now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
        state = {
            "mode": "temporary_gemini",
            "temporary_gemini_until": (now + timedelta(hours=2)).isoformat(),
            "weekly_gemini_since": None,
            "last_limit_reason": "cooldown",
        }
        executor, reason = module.select_executor_from_state(state, now)
        self.assertEqual(executor["name"], module.GEMINI_EXECUTOR["name"])
        self.assertEqual(reason, "temporary")

    def test_expired_temporary_fallback_returns_to_claude(self):
        now = datetime(2026, 4, 24, 12, 0, tzinfo=timezone.utc)
        state = {
            "mode": "temporary_gemini",
            "temporary_gemini_until": (now - timedelta(minutes=1)).isoformat(),
            "weekly_gemini_since": None,
            "last_limit_reason": "cooldown",
        }
        executor, reason = module.select_executor_from_state(state, now)
        self.assertEqual(executor["name"], module.CLAUDE_EXECUTOR["name"])
        self.assertIsNone(reason)
        self.assertEqual(state["mode"], "claude_primary")
        self.assertIsNone(state["temporary_gemini_until"])


if __name__ == "__main__":
    unittest.main()
