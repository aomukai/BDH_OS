# Phase 5 Blueprint (State -> Action -> Goal -> Outcome)

This blueprint defines the drafting slots for Phase 5 stories before writing any story text.

It is designed to enforce:
- motivation contrast
- destination contrast
- purpose contrast
- strict 6-sentence schema compatibility

---

## 1) Canonical Slot Schema

Use this slot sequence for every story:

1. `This is a {state} {subject}.`
2. `The {subject} {move_1} in/on {environment}.`
3. `The {subject} {move_1} to {target}.`
4. `The {subject} {arrival_verb} in/on {target}.` or `The {subject} reaches the {target}.`
5. Outcome form is fixed by verb class:
   - consume class: `The {subject} eats the {object}.` / `The {subject} drinks the water.`
   - rest class: `The {subject} sleeps in/on the {place}.` / `The {subject} rests in/on the {place}.`
6. `The {subject} {move_1} to {target} to {purpose_verb}.`

Sentence 6 must only reuse elements already introduced in 1-5.
For v1, keep prepositions to `in`, `on`, `to`.

---

## 2) Vocabulary Guardrails (Phase 5 v1)

### States (triggers)
- `hungry`
- `sleepy`
- `thirsty`
- `tired`

### Subjects (v1 set)
- `bird`
- `bunny`
- `frog`
- `fish`
- `duck`

### Movement verbs
- `flies`, `hops`, `jumps`, `swims`

### Arrival verbs
- `lands`, `stops`, `reaches`

### Outcome/purpose verbs
- `eat`, `sleep`, `drink`, `rest`

### Environments/targets/objects
- `air`, `grass`, `water`, `pond`, `nest`, `hole`, `leaf`, `carrot`, `worm`, `branch`, `bush`, `plants`

---

## 3) Subject x Trigger Blueprint Matrix

Each row is one planned story blueprint (not story text).

| ID | Subject | State | S2 Movement + Environment | S3 Target | S4 Arrival | S5 Outcome | S6 Purpose |
|---|---|---|---|---|---|---|---|
| B1 | bird | hungry | flies in the air | worm | reaches the worm | eats the worm | to eat |
| B2 | bird | sleepy | flies in the air | nest | lands in the nest | sleeps in the nest | to sleep |
| B3 | bird | thirsty | flies in the air | pond | reaches the pond | drinks the water | to drink |
| BU1 | bunny | hungry | hops in the grass | carrot | reaches the carrot | eats the carrot | to eat |
| BU2 | bunny | sleepy | hops in the grass | hole | reaches the hole | rests in the hole | to rest |
| BU3 | bunny | thirsty | hops in the grass | pond | reaches the pond | drinks the water | to drink |
| F1 | frog | hungry | jumps in the grass | worm | reaches the worm | eats the worm | to eat |
| F2 | frog | sleepy | jumps on the grass | leaf | lands on the leaf | rests on the leaf | to rest |
| F3 | frog | thirsty | jumps on the grass | pond | reaches the pond | drinks the water | to drink |
| FI1 | fish | hungry | swims in the water | worm | reaches the worm | eats the worm | to eat |
| FI2 | fish | sleepy | swims in the water | hole | reaches the hole | rests in the hole | to rest |
| FI3 | fish | tired | swims in the water | plants | reaches the plants | rests in the plants | to rest |
| D1 | duck | hungry | swims in the pond | bread | reaches the bread | eats the bread | to eat |
| D2 | duck | sleepy | swims in the pond | nest | reaches the nest | sleeps in the nest | to sleep |
| D3 | duck | thirsty | swims in the pond | water | reaches the water | drinks the water | to drink |

Notes:
- `bird` and `bunny` are intentionally contrast-heavy anchors.
- `fish thirsty` is removed in v1 because it is low-contrast (`fish` is already in water).
- `bug` and `food` are standardized to `worm` for tighter lexical consistency.
- Keep movement fixed per subject in v1:
  - `bird -> flies`
  - `bunny -> hops`
  - `frog -> jumps`
  - `fish -> swims`
  - `duck -> swims`

---

## 4) Contrast Rules (Cross-Story, Same Subject)

For each subject:
1. Keep subject constant across at least 3 stories.
2. Change state each time.
3. Change target each time.
4. Change outcome/purpose each time.
5. Do not allow one default destination for all states.

Minimum contrast set:
- `hungry -> food target -> eat`
- `sleepy -> shelter/rest target -> sleep/rest`
- `thirsty -> water target -> drink`

---

## 5) Compatibility Rules

Before drafting stories, validate each row:
1. Movement is physically plausible for subject.
2. Movement medium matches movement verb:
   - `flies -> air`
   - `swims -> water/pond`
   - `hops/jumps -> grass/ground`
3. Target is reachable via movement in S2/S3.
4. Arrival verb fits target type.
5. Outcome is possible at target.
6. Sentence 5 follows fixed outcome form:
   - consume class (`eat/drink`) -> object form
   - rest class (`sleep/rest`) -> location form
7. S6 can be formed without introducing a new noun/verb.

Hard fail examples:
- `bird swims to nest` (movement mismatch)
- `bunny lands in carrot` (arrival mismatch)
- S6 mentioning `tree` when `tree` never appeared in S1-S5

---

## 6) Drafting Order (Practical)

1. Draft anchor contrast subject first (`bird`): hungry/sleepy/thirsty.
2. Draft second anchor (`bunny`) with the same trigger triad.
3. Draft remaining subjects with contrast-preserving state sets (allow `tired` where needed for stronger contrast).
4. Run per-subject contrast check.
5. Run per-story schema check.
6. Freeze v1 blueprint before writing story text.

---

## 7) Optional Phase 5 v2 Expansion (Later)

Only after v1 is stable:
- add broader `tired` coverage across non-fish subjects
- add subjects: `cat`, `dog`, `mouse`
- add verbs: `walks`, `runs`, `crawls`
- add targets: `branch`, `bush`, `hole` (if not already used)

Keep the same contrast logic and schema constraints.
