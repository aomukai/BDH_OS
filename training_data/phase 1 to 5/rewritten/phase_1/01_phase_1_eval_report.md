# BDH Phase 1 Curriculum Eval Report v2

## Summary

| Check | Result |
|---|---|
| Content match (source vs rewritten) | 99/99 PASS |
| Vocabulary integrity (cumulative bank) | 99/99 PASS |

---

## Check 1: Content Match

Each rewritten file in `rewritten/` was compared block-by-block against its corresponding source file in `phase 1 to 5/`. The `[user]question` and `[assistant]` markup was stripped from rewritten files before comparison.

**Result: 99/99 PASS** — All rewritten files exactly match their source content.

---

## Check 2: Vocabulary Integrity

Strategy: cumulative vocabulary bank across all 99 files in order (01→99). For each block, the last line is the summary/concept sentence; all preceding lines are the body. A summary word is only flagged as a violation if it does not appear in:
- the current block's body lines, OR
- the cumulative bank of all words introduced in prior blocks/files

When a summary introduced a new concept word, an introductory sentence was added to that block's body to establish the word before the summary uses it. Words introduced this way enter the bank for all subsequent files.

**Result: 99/99 PASS** — 0 block violations. All concept words in summary sentences are grounded in body text or the cumulative bank.

### Fix statistics

- 261 introductory sentences added across 198 blocks in all 99 source files
- Same changes mirrored to all 99 rewritten files
- 8 grammatically malformed generated sentences patched via string replacement
- 2 final violations (phase_1_32.md `peeling`, phase_1_88.md `body's`) fixed by direct edit

---

## Notes

- Block structure: each source file contains 4 blocks of variable line count. Summary is always the last line of each block.
- Rewritten format: each block is preceded by a `[user]question` line; the first line of the assistant response is prefixed with `[assistant]`.
- Vocabulary checking uses regex `[a-z']+` (lowercased) with a large stop-word list filtered out. Possessive forms (e.g. `body's`) are treated as distinct tokens.
