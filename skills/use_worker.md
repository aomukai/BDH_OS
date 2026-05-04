# Skill: Use Worker

## What this is

A routing guide. When I need to delegate work, I read this first to decide which worker to send it to and how to write the executor prompt.

---

## When to use a worker at all

**Handle myself (no worker):**
- Reading 1–5 files for analysis
- Writing a single document (manifest, plan, skill file, etc.)
- Quick verification checks (jq, grep, wc -l, head)
- Decisions, routing, judgment calls
- Reviewing a worker's receipt

**Send to a worker:**
- Reading and/or writing more than ~5 corpus files
- Updating dependency_graph.json
- Backfill, regen, or audit passes across many files
- Any task with an `Executor prompt:` block in todo.md
- Tasks that are pure I/O with no judgment required

The threshold is: if it would consume significant Claude Code tokens just doing file reads, it goes to a worker.

---

## Worker selection

| Priority | Worker | Best for | Cost |
|---|---|---|---|
| 1 (primary) | gpt-5.4-mini (codex) | All tasks — I/O and reasoning | Flat-rate $20 OpenAI subscription — effectively free |
| 2 (fallback) | DeepSeek v4 flash (opencode) | Same tasks, when GPT is rate-limited | OpenRouter pay-per-token — costs real money |
| 3 | Gemini CLI | Last resort if both above are unavailable | — |

**Default rule:** Always try codex first. Only fall back to DeepSeek when the OpenAI rate limit is active. Check `skills/worker_codex.md` for the current reset time.

**Current state (as of 2026-05-04):** OpenAI rate-limited until May 5, 2026 at 9:11 PM JST. Use DeepSeek until then.

---

## How to write an executor prompt

A good executor prompt contains exactly:
1. **Role line:** "You are an executor. Perform exactly the following operations and nothing else."
2. **Task:** What to do, stated precisely. No ambiguity.
3. **Context:** Exactly what schema/format to use, what files to read, what keys to look for.
4. **Steps:** Numbered steps in order. No conditional branching unless necessary.
5. **Verification:** What to run to confirm the work is done. What the expected output is.
6. **Receipt:** What to report back (file list, counts, status).

Keep executor prompts specific and bounded. If the task is too large for one prompt, break it into sequential runs with a progress file.

---

## Verifying a receipt

A receipt is only valid if it includes:
- Named files processed this run
- Last line of the progress ledger (read directly from the file, not from memory)
- Node/record count from the actual output file (e.g., `jq '.nodes | length'`)
- Files remaining count

If any of these are missing or unverifiable, the task is **not done**. Run the verification commands myself before accepting completion.

---

## See also
- `skills/worker_deepseek.md` — DeepSeek v4 flash invocation and limits
- `skills/worker_codex.md` — GPT-4.1 mini via codex, rate limit notes
- `AGENTS.md` — operating contract sent to any worker model
