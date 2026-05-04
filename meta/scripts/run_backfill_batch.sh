#!/bin/bash
# Runs opencode in fresh 20-word batches to keep context small.
cd /home/aomukai/Ninereeds

BATCH_SIZE=20

while [ -s training_data/phases/backfill_clean.txt ]; do
    COUNT=$(wc -l < training_data/phases/backfill_clean.txt)
    echo "[$(date)] Batch start. Words remaining: $COUNT"

    opencode run --model openrouter/google/gemini-2.5-flash --dangerously-skip-permissions "$(cat <<'PROMPT'
Process the next 20 words from `training_data/phases/backfill_clean.txt`, then stop. Do not process more than 20 words in this session.

**Step 1 — Classify into a phase (1–6):**
- Phase 1: self-contained physical percept — directly observable, no relational context needed (sun, wood, stone, wind)
- Phase 2: physical but contextually/relationally defined — needs surrounding relationships (beehive, farmyard, riverbed)
- Phase 3: process, change, transformation — familiar things through motion, combination, or state change (spilling, eroding)
- Phase 4: biological cycle or natural function, single focused question (seed growing, chicken laying eggs)
- Phase 5: agency, goal-directed behavior, truth propositions, single focused question (hungry bird flying to worm)
- Phase 6: meta-concepts, abstraction, language, reasoning, institutional knowledge (plan, belief, pattern, consequence)

If ambiguous, default to higher phase number.

**Step 2 — Generate the training file:**

Phase 1, 2, 3, 6: 4 Q&A blocks, blank line between blocks. Each block = exactly 8 lines.
Phase 4, 5: 1 Q&A block, same 8-line structure, no blank line needed.

Block structure:
[user]<question>
[Ninereeds]This is <word>.
<body line 1>
<body line 2>
<body line 3>
<body line 4>
<body line 5>
<summary line>

Article rule on [Ninereeds] line:
- Specific singular things: "This is the sun."
- Countable/abstract concepts: "This is a pattern." / "This is an atom."

Question arc for phases 1/2/3/6:
- Block 1: what does it look like / what is it
- Block 2: where is it / where does it appear
- Block 3: what does it do / how does it behave
- Block 4: what is it for / what does it give or cause

Language rules — strict:
- Simple, concrete, child-level language only. Short sentences. Plain words.
- Every sentence must start with the word (or article+word) as subject.
- BANNED WORDS: its, your, their, our, my, they, it, he, she, we, you — never use any of these anywhere in the file.
- Body lines are direct observations: "A pattern is a repeated shape." "A molecule is in water."
- BANNED PHRASES: exhibits, demonstrates, pertains, encompasses, facilitates, enables, characterized, inherent, fundamental, represents, signifies, denotes, plays a role
- Summary line must be a natural readable sentence — NOT a word list. Wrong: "A pattern is a shape or line or color." Right: "A pattern is a repeated shape or color found on objects."
- Summary line uses only words that appeared in the 5 body lines of that same block.
- No negation, no speculation.

Canonical reference — match this style exactly:
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

Step 3 — Save the file:
ls training_data/phases/phase_X/ | sort -t_ -k3 -n | tail -1 → increment by 1. Save as phase_X_NNN.md (3-digit padding for phase 1, 2-digit for phases 2–6).

Step 4 — Update dependency graph:
NEVER use Read tool on dependency_graph.json.
jq --arg f "training_data/phases/phase_X/phase_X_NNN.md" '.nodes[$f] = {"path": $f, "kind": "phase"}' training_data/dependency_graph.json > /tmp/dg_tmp.json && mv /tmp/dg_tmp.json training_data/dependency_graph.json

Step 5 — Remove processed word:
sed -i '1d' training_data/phases/backfill_clean.txt

Step 6 — Append to ledger:
echo "<word> -> phase_X_NNN.md" >> training_data/dependency_graph_progress.txt

After every 20 words (or when the file is empty), stop and output receipt:
RECEIPT
-------
Files processed this run: [count]
Progress ledger last entry: [tail -1 training_data/dependency_graph_progress.txt]
Output file record count: [jq '.nodes | length' training_data/dependency_graph.json]
Files remaining: [wc -l training_data/phases/backfill_clean.txt]
Status: DONE | IN_PROGRESS | BLOCKED
PROMPT
)"

    echo "[$(date)] Batch done. Sleeping 3s..."
    sleep 3
done

echo "[$(date)] backfill_clean.txt is empty. All words processed."
