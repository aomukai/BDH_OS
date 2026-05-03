# TODO

This file is the single active unfinished-work queue for the repository.

Rules:
- Add new unfinished work here.
- When a task is completed, remove it from this file and move it to `history.md`.
- Do not leave completed tasks or long status summaries here.
- Legacy planning and status docs belong in `archive/`.

## Active queue

[ ] task: create phase files from training_data/phases/backfill_clean.txt
- each lemma is classified into exactly one phase (1–6) based on its conceptual type
- each lemma gets exactly one training file in the matching phase folder
- lemmas are consumed strictly in order, one at a time
- phase classification:
  - Phase 1: self-contained physical percept — directly observable, no relational context needed (sun, wood, stone, wind)
  - Phase 2: physical but contextually/relationally defined — needs surrounding relationships to make sense (beehive, farmyard, riverbed)
  - Phase 3: process, change, transformation — familiar things examined through motion, combination, or state change over time
  - Phase 4: biological cycle or natural function — single focused question, 6 lines
  - Phase 5: agency, goal-directed behavior, truth propositions — single focused question, 6 lines
  - Phase 6: meta-concepts, abstraction, language, reasoning, institutional knowledge (plan, belief, pattern, consequence)
- file format:
  - phases 1, 2, 3, 6 → 4 Q&A blocks, 27 lines, question arc: appearance → location → behavior → use/effect
  - phases 4, 5 → 1 Q&A block, 6 lines, single focused question about function or process
- register each new file in training_data/dependency_graph.json
- remove each lemma from backfill_clean.txt after its file is verified

Executor prompt:
Process words from `training_data/phases/backfill_clean.txt` one by one. For each word:

**Step 1 — Classify the word into a phase (1–6):**

- Phase 1: self-contained physical percept — directly observable, no relational context needed (sun, wood, stone, wind)
- Phase 2: physical but contextually/relationally defined — needs surrounding relationships to make sense (beehive, farmyard, riverbed)
- Phase 3: process, change, transformation — familiar things examined through motion, combination, or state change over time (bucket spilling, wind over time)
- Phase 4: biological cycle or natural function, single focused question, 6 lines (seed growing, chicken laying eggs, strawberry being picked)
- Phase 5: agency, goal-directed behavior, truth propositions, single focused question, 6 lines (hungry bird flying to worm, true/false statements)
- Phase 6: meta-concepts, abstraction, language, reasoning, institutional knowledge (plan, belief, pattern, consequence, word, sentence, exam)

Use your own judgment to classify. If genuinely ambiguous, default to the higher phase number.

**Step 2 — Generate the training file:**

Phase 1, 2, 3, 6 format — 4 Q&A blocks, blank line between each block. Each block is exactly 8 lines:
```
[user]<question>
[Ninereeds]This is <word>.
<body line 1>
<body line 2>
<body line 3>
<body line 4>
<body line 5>
<summary line>
```
The 4 questions follow this arc: appearance/description → location/origin → behavior/process → use/effect

Phase 4, 5 format — exactly 1 Q&A block, same 8-line structure, no blank lines needed:
```
[user]<single focused question about function or process>
[Ninereeds]This is <word>.
<body line 1>
<body line 2>
<body line 3>
<body line 4>
<body line 5>
<summary line>
```

Language rules — follow this style exactly:
- Use very simple, concrete, child-level language. Short sentences. Plain words only.
- Every sentence starts with the word itself as the subject (no pronouns).
- Body lines are direct observations or facts: "The sun is round." "The sun is hot." "Gradually builds up over time."
- Do NOT use academic or abstract phrasing like "exhibits", "demonstrates", "pertains to", "encompasses".
- Summary line is concrete and cumulative — it uses only words that appeared in the 5 body lines of that block.
- No negation, no speculation in body lines.

Example of correct style (word = sun, phase 1):
```
[user]what does the sun look like?
[Ninereeds]This is the sun.
The sun is round.
The sun is bright.
The sun is hot.
The sun is yellow in the sky.
The sun is a ball.
The sun is a hot bright ball in the sky.

[user]where is the sun?
[Ninereeds]This is the sun.
The sun is in the sky.
The sun is above the ground.
The sun is over the trees.
The sun moves across the sky.
The sun gives light.
The sun is a bright light in the sky.
```

**Step 3 — Save the file:**

Determine the correct phase subfolder: `training_data/phases/phase_X/`
Find the highest existing file number in that folder and increment by 1.
Save as `phase_X_NNN.md` (3-digit padding for phase 1, 2-digit for phases 2–6).

**Step 4 — Update dependency graph:**

Use Bash to append the new node to `training_data/dependency_graph.json` incrementally. Do NOT use the Read tool on this file — it is too large. Use only these Bash commands:
- To get the current node count: `jq '.nodes | length' training_data/dependency_graph.json`
- To append a node: use `jq` to append to the nodes array and write back atomically

**Step 5 — Remove the processed word:**

Delete only the first line from `backfill_clean.txt` after confirmed successful file write. Use Bash: `sed -i '1d' training_data/phases/backfill_clean.txt`

**Step 6 — Append to progress ledger:**

Append one line to `training_data/dependency_graph_progress.txt`:
`<word> → phase_X_NNN.md`
Use Bash: `echo "<word> → phase_X_NNN.md" >> training_data/dependency_graph_progress.txt`

Repeat for every word in `backfill_clean.txt` until the file is empty.

Resume behavior: At start, use Bash to get the last entry: `tail -1 training_data/dependency_graph_progress.txt`. Do NOT read the full progress file — it is large. Cross-reference with `backfill_clean.txt` using `grep` to find where to resume. Never use the Read tool on `dependency_graph.json` or `dependency_graph_progress.txt`.

[ ] task: clean up
- delete the files training_data/philosophy_backfill_list.md and training_data/phases/backfill_clean.txt