#!/bin/bash
# Classifies words from /tmp/chunk_* into phases 1-6 using opencode.
# Outputs one "word|N" line per word to /tmp/classified.txt.

> /tmp/classified.txt

for chunk in /tmp/chunk_aa /tmp/chunk_ab /tmp/chunk_ac /tmp/chunk_ad /tmp/chunk_ae /tmp/chunk_af /tmp/chunk_ag; do
    echo "[$(date)] Processing $chunk ($(wc -l < $chunk) words)..."
    WORDS=$(cat "$chunk")
    opencode run --model openrouter/google/gemini-2.5-flash --dangerously-skip-permissions "$(cat <<PROMPT
You are given a list of words. Classify each word into exactly one phase (1–6) using these definitions:

Phase 1: self-contained physical percept — directly observable, no relational context needed (sun, wood, stone, wind, spider, apple, chair)
Phase 2: physical but contextually or relationally defined — needs surrounding relationships to make sense (beehive, farmyard, riverbed, aisle, airport)
Phase 3: process, change, or transformation — familiar things through motion, combination, or state change (spilling, eroding, melting, stripping)
Phase 4: biological cycle or natural function (seed growing, hatching, germinating, photosynthesis)
Phase 5: agency, goal-directed behavior, mental states, truth propositions (wanting, believing, trying, hunger, intention)
Phase 6: meta-concepts, abstraction, language, reasoning, institutional knowledge (plan, rule, pattern, meaning, category, consequence)

If ambiguous, default to the higher phase number.

Output ONLY lines in this exact format, one per word, nothing else:
word|N

Words to classify:
$WORDS
PROMPT
)" >> /tmp/classified.txt
    echo "[$(date)] Chunk done. Total classified so far: $(wc -l < /tmp/classified.txt)"
    sleep 2
done

echo "[$(date)] All chunks done. Total: $(wc -l < /tmp/classified.txt) lines"
