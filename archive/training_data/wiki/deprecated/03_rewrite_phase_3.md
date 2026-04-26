# Rewrite Instruction: phase_3_5_taxonomy → User/Assistant Format

## Source material
Use the cleanest available version: phase_3_5_taxonomy_v4.md
Supplement with useful content from v3 and v5 where noted below.

## What this file teaches
Categorical reasoning:
- X is a Y / X is not a Y
- class membership and exclusion
- habitat and behavior as category markers
- group summaries

---

## Output structure

Split into THREE output files, trained in this order:

### File 1: taxonomy_core.md
Concepts to include:
- animal (anchor)
- fish, shark, salmon
- whale, dolphin (not fish)
- bird, eagle, hawk, owl, duck
- insect, bee, ant
- spider (not insect)
- frog (ground + water)
- dog, cat
- vehicle, car, boat
- person, boy, girl
- sun, moon, rain, river, wind, fire
  (as non-animals — establish the boundary)
- habitat summaries: water / air / ground

### File 2: taxonomy_groups.md
Concepts to include:
- pet, farm animal, wild animal
- sea creature
- reptile, mammal, nocturnal animal
- tree, flower
- weather types

### File 3: taxonomy_concepts.md
Concepts to include:
- body parts, face, hand, foot
- home, room, kitchen, bedroom
- furniture, bed
- food, fruit, vegetable, drink, tool
- number, color, size, shape
- feeling, place, material
- comparatives:
  fast/slow, big/small, hot/cold,
  wet/dry, hard/soft, full/empty,
  day/night

Process files in order. Do not mix content between files.

---

## Question variety for taxonomy

Taxonomy entries need different question types than phase_3_ext.
Use these forms:

For "X is a Y" (membership):
- "what is a shark?"
- "tell me about eagles"
- "what kind of animal is a bee?"
- "what is a dolphin?"

For "X is not a Y" (exclusion):
- "is a whale a fish?"
- "is a spider an insect?"
- "are dolphins fish?"
- "what is a frog — is it a bird?"

For habitat / behavior:
- "where do fish live?"
- "how does an ant move?"
- "where does an eagle fly?"
- "what does a duck do?"

For group summaries:
- "what animals live in water?"
- "what animals fly in air?"
- "what walks on the ground?"
- "name some birds"
- "what is a vehicle?"

For comparatives (File 3):
- "what is the difference between hot and cold?"
- "what does fast mean?"
- "how are big and small different?"
- "what does full mean?"

For non-animal boundaries:
- "is the sun an animal?"
- "what is rain — is it alive?"
- "is a river a living thing?"

---

## Block format

Most taxonomy entries are single blocks of 6 lines,
not four-block groups like phase_3_ext.

Wrap each block as one [user]/[Ninereeds] pair.

Where a concept has two consecutive blocks
(like frog in v4), treat them as two separate pairs
with different questions.

---

## Example input (from v4)

This is a whale.
A whale is an animal.
A whale swims in water.
A whale lives in water.
A whale is not a fish.
A whale is an animal that lives in water.

This is a duck.
A duck is a bird.
A duck is an animal.
A duck flies in air.
A duck swims on water.
A duck is a bird that flies in air and swims on water.

## Example output

[user]is a whale a fish?
[Ninereeds]This is a whale.
A whale is an animal.
A whale swims in water.
A whale lives in water.
A whale is not a fish.
A whale is an animal that lives in water.

[user]what kind of animal is a duck?
[Ninereeds]This is a duck.
A duck is a bird.
A duck is an animal.
A duck flies in air.
A duck swims on water.
A duck is a bird that flies in air and swims on water.

---

## Content rules

- Do not change any [Ninereeds] text. Copy it exactly.
- Where v4 has removed heavy negation that v3 had,
  keep v4 as base.
- Where v5 has useful content not in v4
  (reptile, mammal, nocturnal, comparatives),
  take those blocks and add them to the appropriate file.
- All inserted blocks from v5 must use only vocabulary
  already defined earlier in that file or in prior phases.
- Flag any v5 block that introduces new vocabulary:
  [VOCABULARY CHECK: word] so a human can review it.

---

## Quality check before each block

1. Is the question natural and varied?
2. Does the question match the content of the block?
3. Is this the right file for this concept?
4. Does any word in the block lack a prior definition?

---

## Processing instruction

Process one file at a time.
Within each file, process one block at a time.
Output the result and stop.
Wait for confirmation before continuing.
Flag merged v5 content clearly: [FROM v5]