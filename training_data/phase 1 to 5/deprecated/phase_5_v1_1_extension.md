# Phase 5 v1.1 Extension Blueprint (Basic Concept Layer)

This is a controlled extension to Phase 5 v1.

Goal:
- keep `state -> action -> goal -> outcome` intact
- add one extra contrast dimension at a time
- avoid widening vocabulary too quickly

This file defines blueprint slots only (no story text).

---

## 1) Scope and Order

Apply in this order:
1. `fast/slow` (movement intensity)
2. `big/small` (environment/target scale)
3. Directional prepositions (`behind`, `under`, `between`) only in v2

---

## 2) Hard Constraints (Inherited + New)

- Keep the Phase 5 six-sentence schema unchanged.
- Keep subject-specific movement locked:
  - `bird -> flies`
  - `bunny -> hops`
  - `frog -> jumps`
  - `fish -> swims`
  - `duck -> swims`
- Keep movement-medium matching mandatory:
  - `flies -> air`
  - `swims -> water/pond`
  - `hops/jumps -> grass/ground`
- In v1.1, allow only one added contrast per story:
  - either speed (`fast/slow`)
  - or size (`big/small`)
  - not both in the same story
- Do not add new targets in sentence 6.

---

## 3) Speed Contrast Blueprint (fast/slow)

Use speed as a modifier of sentence 2 and/or sentence 3 movement, while keeping destination and purpose mapping stable.

| Subject | State | Movement | Medium | Target Family | Purpose |
|---|---|---|---|---|---|
| bird | hungry | flies fast / flies slow | air | food target (`worm`) | eat |
| bunny | thirsty | hops fast / hops slow | grass | water target (`pond`) | drink |
| frog | sleepy | jumps fast / jumps slow | grass | rest target (`leaf`) | rest |
| fish | hungry | swims fast / swims slow | water | food target (`worm`) | eat |
| duck | sleepy | swims fast / swims slow | pond | shelter target (`nest`) | sleep |

Usage rule:
- For each selected base row, create a paired contrast:
  - same subject/state/target/purpose
  - only speed term changes (`fast` vs `slow`)

---

## 4) Size Contrast Blueprint (big/small)

Use size as a descriptor for environment or target nouns already used in v1.

| Subject | State | Environment Size Slot | Target Size Slot | Purpose |
|---|---|---|---|---|
| bird | sleepy | `big tree` (optional context) | `small nest` | sleep |
| bunny | hungry | `big grass field` (or `small grass patch`) | `small carrot` | eat |
| frog | thirsty | `small pond` or `big pond` | `small water edge` (optional) | drink |
| fish | tired | `big water area` / `small water area` | `small plants` | rest |
| duck | hungry | `big pond` / `small pond` | `small bread piece` | eat |

Usage rule:
- Keep movement and purpose unchanged.
- Add only one size pair per story family (`big` vs `small`).
- Prefer size on nouns already present in the base row.

---

## 5) Recommended v1.1 Batch Size

- Add 10 stories total first:
  - 5 speed-contrast stories (one per subject)
  - 5 size-contrast stories (one per subject)

This keeps v1.1 small and diagnosable before scaling.

---

## 6) QA Checklist for v1.1

Per story:
- Exactly one new contrast dimension introduced.
- Movement-medium rule still valid.
- State still controls target and purpose.
- Sentence 6 recap uses only introduced concepts.

Per contrast pair:
- Only the intended contrast token changes (`fast/slow` or `big/small`).
- Destination and purpose remain constant within the pair.
- No preposition expansion beyond v1 set (`in`, `on`, `to`).

---

## 7) Deferred to v2

Do not include yet:
- `behind`, `under`, `between`
- multi-contrast stories (speed + size together)
- new subject classes beyond v1 set

Bring these in only after v1.1 quality checks pass.

---

## 8) Pre-Generation Lock (v1.1)

These rules are mandatory before generating the 10-story v1.1 batch.

### Article consistency
- Sentence 1 form:
  - `This is a {state} {subject}.`
  - or `This is an {state} {subject}.` when needed by vowel sound
- Sentences 2-6 subject form:
  - always `The {subject} ...`
- Target/object referencing inside a story:
  - first mention may use `a/an` when natural
  - after introduction, use `the` for the same target thread

### Sentence 6 recap compression
- In v1.1, sentence 6 must omit speed/size modifiers.
- Recap keeps only action-goal-purpose:
  - `The {subject} {move} to the {target} to {purpose}.`
- This tests compression:
  - temporary descriptors (for example `fast`, `slow`, `big`, `small`) are not treated as permanent goal properties.
