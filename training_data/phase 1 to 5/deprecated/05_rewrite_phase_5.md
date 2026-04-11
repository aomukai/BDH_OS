# Rewrite Instruction: Phase 5 → User/Assistant Format

## Source files
phase_5_v1.md — primary
phase_5_v1_1.md — extension, include in full
phase_5_1_anchor_repair.md — DO NOT include

## What phase 5 teaches

Goal-directed behavior driven by internal state.
Each entry follows a fixed narrative grammar:

state (hungry/sleepy/thirsty/tired)
→ movement (how the animal moves)
→ approach (moving toward a goal)
→ arrival (reaching the goal)
→ action (fulfilling the need)
→ summary (X moves to Y to Z)

This teaches:
- internal state as cause
- movement as response
- goal as destination
- action as resolution
- infinitive purpose clause: "to eat", "to sleep", "to drink"

---

## Regarding phase_5_1_anchor_repair.md

Do not include this file.
The anchor repair approach — repeating monologue statements
about dogs and bunnies — did not repair damaged anchors
because it does not train the question-answer pathway.
That repair is handled better by the rewritten phase 1
and taxonomy core files establishing clean [user]/[assistant]
pairs from the start.

---

## Question variety for phase 5

Questions must reflect the state that drives the behavior.
The state word belongs in the question.

For hungry animals:
- "what does a hungry bird do?"
- "where does a hungry bunny go?"
- "how does a hungry fish find food?"
- "what happens when a frog is hungry?"
- "where does a hungry duck swim?"

For sleepy animals:
- "where does a sleepy bird go?"
- "what does a sleepy bunny do?"
- "how does a tired fish rest?"
- "where does a sleepy duck go to sleep?"

For thirsty animals:
- "what does a thirsty frog do?"
- "where does a thirsty bird fly?"
- "how does a thirsty bunny find water?"

Vary between:
- "what does X do when it is Y?"
- "where does a Y X go?"
- "how does X find Z?"
- "what happens when X is Y?"
- "tell me what a Y X does"

---

## Format

Each entry is one block of six lines.
Wrap as one [user]/[assistant] pair.
The [assistant] block is the original text, unchanged.

---

## Example input

This is a hungry bird.
The bird flies in the air.
The bird flies to the worm.
The bird reaches the worm.
The bird eats the worm.
The bird flies to the worm to eat.

This is a sleepy bunny.
The bunny hops in the grass.
The bunny hops to the hole.
The bunny reaches the hole.
The bunny rests in the hole.
The bunny hops to the hole to rest.

## Example output

[user]what does a hungry bird do?
[assistant]This is a hungry bird.
The bird flies in the air.
The bird flies to the worm.
The bird reaches the worm.
The bird eats the worm.
The bird flies to the worm to eat.

[user]where does a sleepy bunny go?
[assistant]This is a sleepy bunny.
The bunny hops in the grass.
The bunny hops to the hole.
The bunny reaches the hole.
The bunny rests in the hole.
The bunny hops to the hole to rest.

---

## Handling v1_1 modifiers

Phase_5_v1_1 adds fast/slow/big/small as modifiers.
These are already defined in the corpus.
Treat them the same way — one block, one question.
The modifier can appear in the question if natural:

- "what does a hungry bird do when it flies fast?"
- "where does a slow sleepy bunny go?"

But only if it sounds natural. Do not force it.
A plain state question is always acceptable.

---

## Rules

- Do not change any [assistant] text. Copy it exactly.
- Do not include phase_5_1_anchor_repair.md content.
- Vary question phrasing. Do not repeat the same
  question form for consecutive entries.
- The state word (hungry/sleepy/thirsty/tired) should
  appear in most questions.
- Maximum question length: 12 words.
- No commentary, headers, or explanation in output.
- Output only [user]/[assistant] pairs.

---

## Processing instruction

Process one entry at a time.
Output the result and stop.
Wait for confirmation before continuing.
Process phase_5_v1.md first, then phase_5_v1_1.md.