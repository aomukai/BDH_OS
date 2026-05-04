#!/bin/bash
# run_regen.sh PHASE BATCH_SIZE

cd /home/aomukai/Ninereeds

PHASE=$1
BATCH=$2
WORD_FILE="training_data/phases/phase_${PHASE}_words.txt"

if [ -z "$PHASE" ] || [ -z "$BATCH" ]; then
  echo "Usage: run_regen.sh PHASE BATCH_SIZE"
  exit 1
fi

if [ "$PHASE" = "4" ] || [ "$PHASE" = "5" ]; then
  FORMAT="single"
else
  FORMAT="four"
fi

echo "[$(date)] Starting phase $PHASE regen. Format: $FORMAT. Batch: $BATCH. Words: $(wc -l < $WORD_FILE)"

while [ -s "$WORD_FILE" ]; do
  REMAINING=$(wc -l < "$WORD_FILE")
  echo "[$(date)] Phase $PHASE | Remaining: $REMAINING | Starting batch of up to $BATCH"

  if [ "$FORMAT" = "four" ]; then
    opencode run --model openrouter/deepseek/deepseek-v4-flash --dangerously-skip-permissions "$(cat <<PROMPT
IMPORTANT: Do NOT read dependency_graph.json, dependency_graph_progress.txt, or any ledger file. The word list file is your only input. Start immediately without checking any prior state.

Process up to $BATCH words from \`training_data/phases/phase_${PHASE}_words.txt\`, then stop.

For each word, do these 6 steps in order:

STEP 1 — Get the word:
  head -1 training_data/phases/phase_${PHASE}_words.txt

STEP 2 — Generate the training file content.
Format: 4 Q&A blocks, blank line between blocks. Each block is exactly 8 lines:

  [user]<question>
  [Ninereeds]This is a <word>.
  <body line 1>
  <body line 2>
  <body line 3>
  <body line 4>
  <body line 5>
  <summary line>

  Article rule: "a"/"an" for countable nouns, "the" for unique things (the sun), bare word for abstract processes (This is strip.).
  Question arc — block 1: appearance; block 2: location; block 3: behavior; block 4: use or effect.
  Language rules:
  - Simple, concrete, child-level language. Short sentences. Plain words.
  - Every sentence starts with the word (or article+word) as subject. No pronouns.
  - BANNED WORDS: its, your, their, our, my, they, it, he, she, we, you
  - BANNED PHRASES: exhibits, demonstrates, pertains, encompasses, facilitates, enables, characterized, inherent, fundamental, represents, signifies, denotes, plays a role
  - Summary line: natural sentence using only words that appeared in the 5 body lines of that same block.
  - No negation, no speculation.

  Example (word = sun):
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

STEP 3 — Find the next file number and save:
  Run: ls training_data/phases/phase_${PHASE}/ | sort -t_ -k3 -n | tail -1
  Extract only the number (e.g. from "phase_${PHASE}_173.md" extract 173), add 1, use that as NNN.
  Save file as: training_data/phases/phase_${PHASE}/phase_${PHASE}_NNN.md

STEP 4 — Update dependency graph (use ONLY bash/jq, NEVER the Read tool):
  jq --arg f "training_data/phases/phase_${PHASE}/phase_${PHASE}_NNN.md" '.nodes[\$f] = {"path": \$f, "kind": "phase"}' training_data/dependency_graph.json > /tmp/dg_tmp.json && mv /tmp/dg_tmp.json training_data/dependency_graph.json

STEP 5 — Remove the processed word:
  sed -i '1d' training_data/phases/phase_${PHASE}_words.txt

STEP 6 — Append to ledger:
  echo "<word> -> phase_${PHASE}_NNN.md" >> training_data/dependency_graph_progress.txt

After $BATCH words (or when the word file is empty), stop and print:
RECEIPT
Files written: [count]
Last file: [filename]
Remaining: [wc -l training_data/phases/phase_${PHASE}_words.txt]
PROMPT
)"

  else
    opencode run --model openrouter/deepseek/deepseek-v4-flash --dangerously-skip-permissions "$(cat <<PROMPT
IMPORTANT: Do NOT read dependency_graph.json, dependency_graph_progress.txt, or any ledger file. The word list file is your only input. Start immediately without checking any prior state.

Process up to $BATCH words from \`training_data/phases/phase_${PHASE}_words.txt\`, then stop.

For each word, do these 6 steps in order:

STEP 1 — Get the word:
  head -1 training_data/phases/phase_${PHASE}_words.txt

STEP 2 — Generate the training file content.
Format: exactly 1 Q&A block, exactly 8 lines, no blank lines:

  [user]<single focused question>
  [Ninereeds]This is a <word>.
  <body line 1>
  <body line 2>
  <body line 3>
  <body line 4>
  <body line 5>
  <summary line>

  Article rule: "a"/"an" for countable nouns, bare word for abstract states/actions.
$(if [ "$PHASE" = "4" ]; then
  echo "  Question focus: ask about a biological cycle or natural physical function (e.g. 'what does a seed do when it grows?', 'what happens when an egg hatches?')"
else
  echo "  Question focus: ask about agency, goal-directed behavior, or a mental state (e.g. 'what does a hungry bird do?', 'what does it mean to want something?')"
fi)
  Language rules:
  - Simple, concrete, child-level language. Short sentences. Plain words.
  - Every sentence starts with the word (or article+word) as subject. No pronouns.
  - BANNED WORDS: its, your, their, our, my, they, it, he, she, we, you
  - BANNED PHRASES: exhibits, demonstrates, pertains, encompasses, facilitates, enables, characterized, inherent, fundamental, represents, signifies, denotes, plays a role
  - Summary line: natural sentence using only words that appeared in the 5 body lines.
  - No negation, no speculation.

  Example (phase 5, word = hungry bird):
  [user]what does a hungry bird do?
  [Ninereeds]This is a hungry bird.
  The bird flies in the air.
  The bird flies to the worm.
  The bird reaches the worm.
  The bird eats the worm.
  The bird flies to the worm to eat.

STEP 3 — Find the next file number and save:
  Run: ls training_data/phases/phase_${PHASE}/ | sort -t_ -k3 -n | tail -1
  Extract only the number (e.g. from "phase_${PHASE}_46.md" extract 46), add 1, use that as NNN.
  Save file as: training_data/phases/phase_${PHASE}/phase_${PHASE}_NNN.md

STEP 4 — Update dependency graph (use ONLY bash/jq, NEVER the Read tool):
  jq --arg f "training_data/phases/phase_${PHASE}/phase_${PHASE}_NNN.md" '.nodes[\$f] = {"path": \$f, "kind": "phase"}' training_data/dependency_graph.json > /tmp/dg_tmp.json && mv /tmp/dg_tmp.json training_data/dependency_graph.json

STEP 5 — Remove the processed word:
  sed -i '1d' training_data/phases/phase_${PHASE}_words.txt

STEP 6 — Append to ledger:
  echo "<word> -> phase_${PHASE}_NNN.md" >> training_data/dependency_graph_progress.txt

After $BATCH words (or when the word file is empty), stop and print:
RECEIPT
Files written: [count]
Last file: [filename]
Remaining: [wc -l training_data/phases/phase_${PHASE}_words.txt]
PROMPT
)"
  fi

  echo "[$(date)] Batch done. Sleeping 3s..."
  sleep 3
done

echo "[$(date)] Phase $PHASE complete."
