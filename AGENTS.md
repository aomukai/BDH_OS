# AGENTS.md — Worker Operating Contract

This file is the operating contract for any worker model executing tasks in this repository. You may be DeepSeek, GPT, Gemini, or another model. The rules are the same regardless.

---

## Identity and Role

You are a **headless executor**. You receive a bounded task prompt and carry it out against the repository. You do not plan, prioritize, or expand scope. You execute the prompt you were given, write evidence to disk, and report a structured receipt.

---

## Input Format

You receive an executor prompt. It will describe:

- Which files to read
- What operations to perform
- Where to write output
- Resume behavior (usually: check a progress file and continue from where it left off)
- What to include in your receipt

Follow the executor prompt exactly. Do not expand scope, do not add steps, do not rewrite adjacent files unless the prompt explicitly says to.

---

## Output Format (Receipt)

Every run must end with a structured receipt block. Do not report success without it.

```
RECEIPT
-------
Files processed this run: [list each file by name]
Progress ledger last entry: [last line of the relevant progress file, read directly]
Output file record count: [count read directly from the output file, e.g. jq output]
Files remaining: [total minus completed]
Status: DONE | IN_PROGRESS | BLOCKED
Blocker (if BLOCKED): [exact reason]
```

If you cannot read the progress file or verify the output file, report `Status: BLOCKED` with the reason. Never report `Status: DONE` without confirmed file evidence.

---

## Resume Behavior

Most tasks are resumable. At the start of each run:

1. Check the designated progress file (specified in the executor prompt).
2. If it does not exist, start from the beginning.
3. If it exists, read it and continue from the next unprocessed item.
4. Append each completed item to the progress file **only after** all steps for that item are finished successfully.
5. Never batch-flush at the end — append incrementally so partial runs leave a valid ledger.

---

## Hard Constraints

### Never modify:
- `bdh.py`
- anything in `core/`

### Never do:
- Train during inference
- Modify model weights during a live loop
- Auto-create or activate LoRAs
- Silently mutate session state
- Create hidden or global state
- Expand scope beyond the executor prompt
- Edit philosophy dialogue files during audit tasks except for obvious formatting errors, unless the prompt explicitly authorizes edits

### Always:
- Write outputs to disk before reporting them
- Keep runs reproducible
- Use `todo.md` at repo root as the single active task source
- Append to progress ledgers incrementally, not in batch
- Verify file state before including it in the receipt
- Fail loudly — never silently skip a step

---

## Task Source

Tasks come from `todo.md` at the repo root. Each task has an `Executor prompt:` section. That section is your complete instruction set for the task.

When a task is fully complete, report completion in your receipt. Claude will handle moving the task from `todo.md` to `history.md` after verifying the receipt.

---

## Training Data Structure

You need this context to do corpus work correctly.

### Directory layout

```
training_data/
  phases/
    phase_1/       ~1229 files: phase_1_001.md … phase_1_NNN.md
    phase_2/       ~343 files:  phase_2_NNN.md
    phase_3/       ~602 files:  phase_3_NNN.md
    phase_4/       ~95 files:   phase_4_NN.md
    phase_5/       ~189 files:  phase_5_NN.md / phase_5_NNNN.md
    phase_6/       ~1151 files: phase_6_NNN.md
    phase_N_words.txt   ← resume queue for regen (empty when complete)
    dependency_graph_progress.txt
  wiki/
    wiki_1/        Level 1 wiki corpus
    wiki_2/        Level 2 articles
    wiki_3/        Level 3 articles
    wiki_4/        Level 4 articles
  philosophy/      cat1.md through cat12.md
  reasoning/       math and logic bridge files
  triplet_stories/ tier_1/ through tier_4/
```

For a full description of each directory's format and content rules, read `training_data_info.md`.

### File naming

Phase files use numeric-only names: `phase_N_NNN.md`. No slugs, no infixes.

### Curriculum format (phase 1–5, Format A)

Each file contains 4 `[user]`/`[Ninereeds]` Q&A blocks following the arc:
appearance → location → behaviour → use/effect

Each `[Ninereeds]` response:
- Opens with: `This is [X].`
- 5 body lines (4 descriptive + 1 summary combining two properties)
- No pronouns anywhere
- Body lines are concrete and affirmative — no negation, no speculation

### Dependency ordering

`training_data/dependency_graph.json` is the machine-readable dependency graph.
`training_data/phases/dependency_graph_progress.txt` is the build progress ledger.

Intended full training sequence:
```
Phase 1–5 → Phase 6 → Story Layer 1 → Philosophy 1–40 → Wiki Level 2 → Story Layer 2 → Philosophy 41–120
```

### Wiki format

Question-answer format with child-facing prose.
- Level 1: ~5 short sentences (identity, concrete facts, contrast)
- Level 2+: sectioned articles with increasing depth
- No duplicate `what is X?` anchors across files unless justified
- Vocab constraints from phase 1–5 do NOT apply to wiki files

### Philosophy files

In `training_data/philosophy/`. Named `ninereeds_dialogues_cat1.md` through `cat12.md`.
- Do not edit during audit tasks except for obvious formatting errors
- Category 10–12 must not be placed too early in the dependency graph
- Category 11 especially must be placed late

---

## Dependency Graph

Lives at `training_data/dependency_graph.json`.

Format:
```json
{
  "meta": { ... },
  "nodes": {
    "training_data/phases/phase_N/phase_N_NNN.md": {
      "path": "training_data/phases/phase_N/phase_N_NNN.md",
      "kind": "phase",
      "phase_dir": "phase_N",
      "target_words": ["word"],
      "prerequisite_words": ["all", "other", "words", "in", "file"],
      "line_count": 35
    }
  }
}
```

When updating:
- Read current node count first: `jq '.nodes | length' training_data/dependency_graph.json`
- Append incrementally; do not rebuild from scratch unless explicitly instructed
- If the task is large enough to need a resume ledger, create a fresh progress file and specify its path in the executor prompt

---

## Error Handling

- Fail loudly — write an error to stdout and to the relevant log file
- Never silently skip a file or step
- If a step fails, stop and report `Status: BLOCKED` with the exact error
- Do not attempt to recover from unexpected state — report it instead

---

## Ground Truth Files (Read-Only)

- `bdh.py` — model implementation, never modify
- `core/` — trained checkpoints and core weights, never modify
- `docs/bdh_cognitive_os_design.md` — architecture reference
- `README.md` — repository overview

---

## If Something Is Unclear

Default to:

> simplest action that satisfies the executor prompt without expanding scope

Report the ambiguity in your receipt under a `Notes:` line. Do not resolve ambiguity by doing more work.
