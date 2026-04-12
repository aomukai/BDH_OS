# Wiki Implementation TODO

Working implementation queue for the Level 1 wiki.

This file is the practical companion to:
- `training_data/wiki/wiki_category_backlog.md` — strategic category backlog
- `training_data/wiki/CORPUS_STATUS.md` — current corpus state
- `training_data/phase 1 to 5/rewritten/missing_curriculum_terms.md` — curriculum-side anchor gaps

Use this file for the next concrete writing and review steps.

---

## Current priorities

The current goal is not "write everything fast."
The current goal is:

1. finish partial foundational categories
2. add missing high-utility daily-life categories in dependency order
3. periodically check whether new wiki vocabulary needs earlier anchoring in `phase 1–5`

Recent completed salvage / implementation batch:

- `Storytelling and Narrative Structure`
- `Imagination and Pretend Play`
- `Chores and Home Responsibilities`
- `Safety Signs and Symbols`
- `Community Places and Services`
- `Cooking and Food Preparation`
- `Construction and Material Transformations`
- `Emotions Beyond Basic States` partially expanded by extending `emotions_entries.md`

---

## Next 10 categories to implement

These are the next best targets after the cleanup sprint.
They are ordered for dependency flow, not just by interest.

1. [x] `School Life and Learning`
   Notes: expanded with everyday school life terms: `teacher`, `student`, `recess`, `subject`, `grade`, `backpack`, `school bus`.

2. [x] `Clothing and Apparel`
   Notes: expanded with `clothing`, `jacket`, `shirt`, `mitten`, `skirt`, `dress`, `sock`, `shoe`, and `zipper`.

3. [x] `Money, Trade, and Shopping`
   Notes: expanded with `penny`, `nickel`, `dime`, `quarter`, `change`, `allowance`, `customer`, and `shopkeeper`.

4. [x] `Movement and Physical Action`
   Notes: implemented as a bridge category with `movement`, `exercise`, `balance`, `stretch`, `kick`, `bounce`, `spin`, and `dance`, avoiding duplication of the main verbs file.

5. [x] `Directions and Navigation`
   Notes: implemented around route-following language: `left`, `right`, `up`, `down`, `forward`, `backward`, `turn`, `go straight`, `map`, `route`, `address`.

6. [x] `Meals and Mealtime Talk`
   Notes: implemented around `meal`, `breakfast`, `lunch`, `dinner`, `snack`, `hungry`, `full`, `pass something`, and `all done`.

7. [x] `Sensory Experiences`
   Notes: implemented as descriptive sensory language and named sensory events: `sound`, `loud`, `quiet`, `noisy`, `silent`, `bright`, `dim`, `sticky`, `sweet`, `sour`, `bang`, `squeak`, `roar`, `chirp`, `melody`.

8. [x] `Daily Routines and Self-Care`
   Notes: implemented around `routine`, `wake up`, `get ready`, `get dressed`, `wash your hands`, `eat breakfast`, `go to school`, `pack a backpack`, `line up`, `go to bed`, and `pajamas`.

9. [x] `States of Being and Condition`
   Notes: implemented as the adjective/state layer with `condition`, `open`, `closed`, `on`, `off`, `clean`, `dirty`, `broken`, `fixed`, and `asleep`.

10. [x] `Body States and Internal Cues`
   Notes: implemented for hunger, thirst, pain, tiredness, comfort, and self-report.

---

## After the next 10

These are the next wave once the above is stable:

11. `Wants, Needs, and Preferences`
12. `Greetings and Social Salutations`
13. `Waiting and Patience`
14. `Containers and Capacity`
15. `Manners, Politeness, and Social Etiquette`
16. `Communication Acts and Language`
17. `Agreement and Disagreement`
18. `Ownership and Sharing`
19. `Friends and Peer Interactions`
20. `Personal Identity and Self-Description`

Recommended next clean authoring order after the salvage batch:

1. `Wants, Needs, and Preferences`
2. `Greetings and Social Salutations`
3. `Waiting and Patience`
4. `Containers and Capacity`
5. `Communication Acts and Language`

---

## Recurring review loop

Run these checks every few category additions, not just at the very end.

### 1. Anchor drift review

Question:
Does a newly written wiki entry rely on words that feel too ungrounded in `phase 1–5`?

Action:
- add the word to `missing_curriculum_terms.md` if it feels important and reusable
- note whether the word needs a phase anchor, a later phase concept file, or is safe to remain wiki-only

Examples already noticed:
- `thought`
- `real`
- `reality`
- `true`
- `truth`
- `money`

### 2. Duplicate ownership review

Question:
Did a new category accidentally create a second full anchor for a concept that already has a better home?

Action:
- keep one canonical `what is X?` home whenever possible
- move or cut duplicates before they spread into later expansion levels

### 3. Dangling contrast review

Question:
Did a new entry introduce `X is not Y` where `Y` has no entry yet?

Action:
- either implement `Y`
- or change the contrast to an already grounded concept

### 4. Register review

Question:
Does the file still sound like preschool/1st-grade educational material?

Warning signs:
- textbook compression
- hidden mechanism explanations
- adult therapeutic language
- taxonomy voice
- too many facts per sentence

### 5. Ordering review

Question:
Does the file go from broader anchors to narrower concepts?

Action:
- parent concept first
- specific examples later
- relation-heavy entries after the objects they depend on

---

## Small implementation rules

- Finish `PARTIAL` categories before starting too many new siblings.
- Prefer categories that unlock many later categories.
- Keep category identity clean; do not let files become catch-all buckets.
- If a concept belongs equally to two domains, choose one canonical home early.
- Add checklist comments at the top of files when obvious later additions are known.

---

## Good stopping points

A category batch is in a good temporary state when:

- the file has a clear anchor or anchors
- the prose matches current Level 1 voice
- there are no obvious duplicate concept homes
- the file order mostly goes from general to specific
- any important new anchor gaps are logged
