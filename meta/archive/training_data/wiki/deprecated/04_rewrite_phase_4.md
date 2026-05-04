# Rewrite Instruction: Phase 4 → User/Assistant Format

## Source files
phase_4.md — primary
phase_4_ext.md — extension, same format, include in full
phase_4_ext2.md — DO NOT include directly (see note below)

## What phase 4 teaches

Things in motion. Known concepts shown acting, changing,
and interacting in sequence. Each entry is a single narrative
block showing cause and effect across five lines,
ending with a summary sentence.

This is different from phase 1 (properties/location/process/
function across four blocks). Phase 4 has ONE block per entry
showing a complete small event.

---

## Regarding phase_4_ext2.md

Do not include ext2 content in this rewrite.

Ext2 re-teaches phase 1 concepts using phase 1 structure.
This causes concept bleed — the model re-learns old patterns
on top of established ones.

Some ext2 content is salvageable as phase 1 reinforcement.
Flag it separately: create a file called
phase_1_reinforcement_candidates.md
listing any ext2 concept that:
- is NOT already covered in phase_4.md or phase_4_ext.md
- uses only phase 1 vocabulary
- would fit the phase 1 four-block format

Do not rewrite these — just list the concept names
with a one-line note on why they might be useful.

---

## Question variety for phase 4

Phase 4 entries show events and motion. Questions should
reflect this — ask about what happened, what something did,
how something moved, what the result was.

Good question forms:

For animal behavior:
- "what does an eagle do when it hunts?"
- "how does a bee find food?"
- "what does an ant do with food?"
- "tell me what a spider does on its web"
- "how does a duck find food?"

For weather and natural events:
- "what happens during a storm?"
- "how does a flood start?"
- "what does frost do to the ground?"
- "what happens to wood in a fire?"
- "how does a wave move?"

For plants and growth:
- "how does a seed grow?"
- "what happens to a flower in the rain?"
- "how does a leaf fall?"

For geography and places:
- "what is a valley like?"
- "what lives in a desert?"
- "what happens in a jungle?"
- "describe a meadow"

For food and crops:
- "how does wheat become bread?"
- "how does a grape grow?"
- "where does a potato come from?"
- "how is garlic grown?"

---

## Format

Each entry is one block. Wrap as one [user]/[Ninereeds] pair.

The [Ninereeds] block is the original text, unchanged.

---

## Example input

This is a bee.
A bee flies near a flower from a hive.
A bee lands on a flower.
A bee gathers from the flower.
A bee returns to the hive with honey.
A bee is an insect that makes honey.

## Example output

[user]how does a bee find food?
[Ninereeds]This is a bee.
A bee flies near a flower from a hive.
A bee lands on a flower.
A bee gathers from the flower.
A bee returns to the hive with honey.
A bee is an insect that makes honey.

---

## Dependency check

Before each entry, verify:
- Is this concept already defined in phases 1-3?
- If not, flag it: [NEW CONCEPT: X]
  A new concept appearing first in phase 4 may need
  a phase 1 entry added to the reinforcement candidates file.

Known new concepts likely appearing first in phase 4:
frost, flood, storm (check against phase 1 list)
snail, goose, chicken, turkey, hamster, rat, bat
ladybug, dragonfly, grasshopper, cricket, tadpole
lizard, snake, alligator, octopus, clam, starfish,
jellyfish, coral, seaweed, shell, pearl
valley, desert, jungle, meadow, orchard, vineyard
rice, wheat, corn, bean, pea
orange, grape, strawberry, blueberry, watermelon,
pumpkin, potato, onion, garlic, lettuce, cabbage,
spinach, broccoli, cauliflower

For each flagged new concept, note:
[NEW CONCEPT: X — needs phase 1 entry before phase 4]

This creates a backfill list for a later pass.

---

## Rules

- Do not change any [Ninereeds] text. Copy it exactly.
- Do not include any content from phase_4_ext2.md.
- Vary question phrasing. No two consecutive entries
  should use the same question opening.
- Maximum question length: 12 words.
- No commentary, headers, or explanation in output.
- Output only [user]/[Ninereeds] pairs plus flagged notes.

---

## Processing instruction

Process one entry at a time.
Output the result and stop.
Wait for confirmation before continuing.
Produce phase_1_reinforcement_candidates.md
as a separate file at the end.