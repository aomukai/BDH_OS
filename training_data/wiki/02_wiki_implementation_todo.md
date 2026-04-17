# Wiki Implementation TODO

Active working queue for the wiki corpus.

This file is the **single active todo list** for wiki work.
Do not use it as a history log.
Completed batches and corpus-state notes belong in `training_data/wiki/01_CORPUS_STATUS.md`.

Use this file together with:
- `docs/training_pipeline.md` — canonical sequence for training, audits, story layers, and Mommy Says Machine evaluation
- `training_data/wiki/01_CORPUS_STATUS.md` — history, status, and cleanup notes
- `training_data/wiki/wiki_category_backlog.md` — strategic backlog and dependency map
- `training_data/wiki/level1_finish_and_level2_start_plan.md` — trunk cleanup order and overlap hotspots
- `training_data/wiki/ranked_gap_list.md` — prioritized comprehension gaps by dependency count and centrality
- `training_data/phase 1 to 5/rewritten/missing_curriculum_terms.md` — wiki-to-curriculum anchor gaps

---

## What this file is for now

The current job is **gap filling for comprehension**.
The goal is not to add random new material.
The goal is to identify what the dragon must already understand in order to learn the existing wiki cleanly.

That means prioritizing:
1. dependency coverage
2. trunk-file ownership cleanup
3. anchor-gap logging
4. overlap reduction
5. only then broader Level 2 expansion

---

## Operating rules

- Keep this file focused on active unchecked work.
- When a task is completed, check it off here and move the result summary into `01_CORPUS_STATUS.md`.
- If a task reveals more work, add the follow-up here as a new unchecked item instead of burying it in prose elsewhere.
- Prefer dependency and comprehension fixes over decorative expansion.
- Prefer one canonical concept home whenever possible.

---

## Current active queue

### A. Build the dependency picture first

1. [x] Audit and normalize backlog dependencies, then build a corpus-wide dependency ledger from `wiki_category_backlog.md`
   Notes:
   - Created `dependency_ledger.md` with ~150 unique dependency concepts mapped to canonical homes.
   - All ~75 old `(backlog)` markers resolved against current COVERED wiki files.
   - Identified ~15 curriculum-only dependencies (basic objects like door, table, ball).
   - Documented 9 ownership overlap hotspots for trunk audit (begin/middle/end, eat/drink/sleep, etc.).
   - Zero missing dependencies — all backlog references now have grounded anchors.

2. [x] Identify comprehension-critical missing or weak prerequisites
   Notes:
   - Added "Comprehension-Critical Missing or Weak Prerequisites" section to `dependency_ledger.md`.
   - Priority 1 gaps: `thing`/`object`, `word`, `sentence`, and `idea`/`thought` need wiki anchors.
   - Priority 2: `fire` is the only curriculum-only concept with safety relevance needing verification.
   - Priority 3: Weak anchors flagged for begin/middle/end, eat/drink/sleep ownership splits.
   - Priority 4: Structural language (more/less, part/whole, if/then) confirmed present but needs trunk audit check.
   - Low priority: Basic curriculum objects (door, table, ball, etc.) are adequately grounded.
   - Recommended actions summarized: add 3-4 wiki anchors, verify fire, resolve overlaps in trunk audit.

3. [x] Produce a ranked gap list for the wiki corpus
   Notes:
   - Created `ranked_gap_list.md` with 36 gaps organized into 4 tiers by dependency count and centrality.
   - Tier 1 (Critical, 4 items): `thing`/`object`, `word`, `sentence`, `idea`/`thought` — need wiki anchors immediately.
   - Tier 2 (Important, 8 items): Ownership splits (begin/middle/end, eat/drink/sleep, sense verbs, etc.) — resolve during trunk audit.
   - Tier 3 (Useful, 10 items): Existing anchors to verify are clear and early in files — after trunk audit.
   - Tier 4 (Low priority, 14 items): Curriculum-only basics (door, table, ball, etc.) — no action needed.
   - Included recommended action sequence and cross-reference to trunk audit items.

### B. Finish the Level 1 trunk pass

4. [x] Audit `logic_entries.md` for dependency ownership and overlap
   Notes:
   - Audited 60 entries for ownership conflicts with time, storytelling, ownership/sharing, learning/memory, and personal identity files.
   - `begin`/`middle`/`end`: Intentional split with storytelling_and_narrative_structure_entries.md. Logic owns abstract sequence sense; storytelling owns narrative sense. No time_entries overlap found. No action needed.
   - `own`/`belong`: Minor overlap with ownership_and_sharing_entries.md. Logic version is abstract/philosophical; ownership_and_sharing teaches practical social usage. Both defensible; ownership_and_sharing is the stronger teaching home but logic version provides foundational anchor. Flagged as low-priority overlap.
   - `memory`: Distinct from learning_memory_and_metacognition's `remember`/`forget`. Logic covers noun form as abstract concept. Acceptable split.
   - `self`/`other`: Distinct from personal_identity_and_self_description's practical self-introduction. Logic covers philosophical identity vs alterity. Acceptable split.
   - `habit`: Unique to logic_entries. No overlap found.
   - No duplicate anchors found for core logic vocabulary (exist, real, same, different, part, whole, cause, effect, etc.).
   - File size (60 entries) is justified as core generative infrastructure.
   - Result: No structural changes required. Two low-priority overlaps noted (own/belong, memory) for future consideration if social files need strengthening.

5. [x] Audit `STEM_entries.md` for dependency ownership and overlap
   Notes:
   - Audited 51 entries for ownership conflicts with verbs, sensory, body-state, weather, and state-change files.
   - **Physical properties (hot/cold/warm, heavy/light, hard/soft, wet/dry, rough/smooth)**: STEM owns grounded physical-science definitions. No duplicates in `states_of_being_and_condition_entries.md`. `measurement_and_comparison_entries.md` covers measurement context for heavy/light; STEM owns tactile/physical sense. Acceptable split.
   - **States of matter (solid/liquid/gas, steam/ice)**: STEM owns definitively. `weather_and_celestial_entries.md` has `ice` in weather context; STEM covers material-science sense. Both usages defensible (different focus).
   - **Forces and motion (push/pull, float/sink, fall/rise, move, fast/slow)**: STEM owns physics definitions. `verbs_entries.md` has `push`, `pull`, `fall` as action verbs. Intentional split: STEM owns force/physics sense; verbs owns action sense.
   - **State changes (melt/freeze, boil, burn, pour, mix, bend, break/fix)**: STEM owns material transformations. `verbs_entries.md` has `break` as action. `construction_and_material_transformations_entries.md` covers building, not elemental changes. STEM is correct home.
   - **Container states (full/empty)**: STEM defines physical sense. `containers_and_capacity_entries.md` owns container-specific context. Acceptable split.
   - **Life processes (alive, breathe, eat, drink, sleep, awake, die, live, born, grow)**: Major overlap area. `verbs_entries.md` has `eat`, `drink`, `sleep`. `sleep_and_rest_entries.md` covers bedtime context. `natural_life_cycles_and_processes_entries.md` has `birth`. Split is intentional: STEM owns biological-process definitions; verbs owns action forms; sleep/rest owns bedtime context; life-cycles owns developmental stages. Documented in `dependency_ledger.md`.
   - **Sense verbs (see/hear/smell/taste/touch)**: STEM has compact sense-organ definitions. `sensory_experiences_entries.md` covers experiential adjectives (loud, quiet, bright, sweet). Clean split: STEM owns "what does it mean to X?"; sensory_experiences owns descriptive qualities.
   - **Result**: STEM_entries.md is a well-scoped bridge file at 51 entries. All overlaps are intentional and documented. No structural changes required.

6. [x] Audit `time_entries.md` for sequence-language ownership
   Notes:
   - Audited 35 entries for overlap with `logic_entries.md` and `storytelling_and_narrative_structure_entries.md`.
   - **begin/middle/end**: Correctly absent from time_entries.md. Logic owns abstract sequence sense; storytelling owns narrative structure sense. No time overlap — clean.
   - **before/after**: Defined in both time_entries.md (temporal meaning) and storytelling_entries (narrative usage). Intentional split: time owns the general temporal definition; storytelling shows in-story usage. Both entries are complementary and teach distinct aspects.
   - **then**: Defined in both time_entries.md ("another time, not now") and storytelling_entries ("links one event to the next"). Intentional split: time owns temporal reference; storytelling owns narrative connective. Acceptable.
   - **Unique to time_entries.md**: Calendar units (day/week/month/year/season), time-of-day (morning/afternoon/evening/night), tense markers (past/present/future/now), and frequency adverbs (always/never/soon/immediately/frequently/rarely). No overlaps found in logic or storytelling files.
   - **Result**: time_entries.md is well-scoped with 35 entries covering temporal vocabulary. All overlaps with storytelling are intentional (before/after/then teach different aspects). No structural changes required.

7. [x] Audit `space_entries.md` for shape/measurement overlap
   Notes:
   - Audited 37 entries for overlap with `mathematical_concepts_entries.md` and `measurement_and_comparison_entries.md`.
   - **height**: DUPLICATE ANCHOR. Defined in both `space_entries.md` (line 90) and `measurement_and_comparison_entries.md` (line 30). Both give essentially the same definition ("how tall something is from bottom to top"). Recommended canonical owner: `measurement_and_comparison_entries.md`, which groups all measurement dimensions (length, height, weight, capacity, distance, speed, temperature). Flagged for removal from space_entries.md in future cleanup pass.
   - **width/depth**: Unique to `space_entries.md`. `measurement_and_comparison_entries.md` has comparatives (wider/narrower) but not base nouns. Acceptable split: space owns spatial dimensions, measurement owns comparative forms.
   - **center/edge/corner**: Unique to `space_entries.md`. Not in mathematical_concepts_entries.md (which owns shapes only). Clean ownership.
   - **Shapes (circle, square, triangle, rectangle)**: Owned by `mathematical_concepts_entries.md`. Not present in `space_entries.md`. Clean split.
   - **Spatial prepositions (on, in, under, over, etc.)**: 28 entries unique to `space_entries.md`. No overlap with other files.
   - **Result**: One duplicate anchor (`height`) identified for future removal. No other structural changes required. Space_entries.md is well-scoped as a spatial prepositions and relations file.

8. [x] Audit `verbs_entries.md` for duplicate specialist ownership
   Notes:
   - Audited 77 entries for duplicate anchors with STEM, learning_memory, ownership_and_sharing, and other specialist files.
   - **DUPLICATE ANCHORS (exact question format, same concept):**
     - `eat`: verbs_entries.md:235 AND STEM_entries.md:120 — STEM owns biological-process; verbs owns everyday action. Recommend keeping both (intentional split).
     - `drink`: verbs_entries.md:238 AND STEM_entries.md:123 — Same rationale as eat. Intentional split.
     - `sleep`: verbs_entries.md:241 AND STEM_entries.md:126 — Same rationale. sleep_and_rest_entries.md adds bedtime context. Intentional three-way split.
     - `see`: verbs_entries.md:271 AND STEM_entries.md:141 — STEM owns sense-organ definition; verbs owns action. Intentional split.
     - `hear`: verbs_entries.md:274 AND STEM_entries.md:144 — Same rationale as see. Intentional split.
   - **INTENTIONAL SPLITS (different question format or clearly distinct focus):**
     - `push`/`pull`: STEM ("what is a push/pull") owns noun/force sense; verbs ("what does it mean to push/pull") owns action sense. Clean split.
     - `learn`/`remember`/`forget`: learning_memory_and_metacognition uses "what does X mean" format; verbs uses "what does it mean to X" format. Same concept, different framing. learning_memory is specialist metacognition file; verbs is general action file. Recommend documenting as intentional redundancy for reinforcement.
     - `share`: verbs (general action) vs ownership_and_sharing ("sharing" noun concept). Different anchors — no conflict.
     - `fall`/`grow`/`break`/`fix`: STEM owns physics/material-change sense. verbs mentions these in contrasts but does not have standalone entries for all. No duplicate anchors.
   - **SENSE VERBS (smell/taste/touch):** Only in STEM_entries.md, not in verbs_entries.md. No conflict.
   - **Result**: Five duplicate anchors identified (eat, drink, sleep, see, hear). All five represent intentional splits: STEM teaches biological/perceptual function, verbs teaches everyday action. No structural changes required. Overlaps are documented in dependency_ledger.md.
   - **Recommendation**: During future cleanup, consider adding a brief cross-reference comment at the top of STEM_entries.md noting intentional overlap with verbs_entries.md for life-process verbs.

9. [x] Audit `mathematical_concepts_entries.md` for concept-only scope
   Notes:
   - Audited 29 entries covering numbers (0-10), operations vocabulary, comparison, fractions, and shapes.
   - **Concept-only scope confirmed**: All entries are definitional "what is X?" questions. No problem-solving procedures or worked examples appear in this file.
   - **Clean split with `mathematical_problems_entries.md`**: Concepts file teaches vocabulary/definitions (what addition means); problems file teaches application (how to add). Intentional and clean.
   - **No overlap with `measurement_and_comparison_entries.md`**: measurement owns comparative forms (bigger/smaller, heavier/lighter); math_concepts owns absolute comparison language (more than/less than, equal). Acceptable split.
   - **No overlap with `space_entries.md`**: space owns spatial dimensions (width, depth, height) and prepositions; math_concepts owns shape vocabulary only. Clean ownership.
   - **"round" entry**: Could theoretically fit in space_entries, but is tightly coupled to circle definition. Current placement is defensible.
   - **Result**: File is well-scoped. No structural changes required. No duplicate anchors found.

10. [x] Audit `mathematical_problems_entries.md` for Level 1 register and grounded prerequisites
    Notes:
    - **Grounded prerequisites: PASSED**. All vocabulary (foods, animals, objects, places, actions, time words) is grounded in existing wiki or curriculum files. Minor note: file uses "television" while wiki anchor is "TV" — same concept, acceptable.
    - **Prose simplicity: PASSED**. Short sentences, concrete language, step-by-step breakdowns, consistent terminology with `mathematical_concepts_entries.md`.
    - **Level 1 register: PARTIAL PASS — needs stratification**. Number range escalates beyond Level 1 scope:
      - Lines 1-22 (numbers 0-15): Level 1 appropriate ✓
      - Lines 23-52 (numbers 10-100): Level 1/2 bridge — acceptable stretch
      - Lines 53-73, 93-137 (numbers 100-2000+): Level 2/3 content — exceeds `mathematical_concepts_entries.md` scope (0-10 only)
    - **Specific outliers**: Problems using 548, 648, 1640, 2078, 965, 873, 679 are 3-4 digit numbers that create a comprehension gap against the concepts file.
    - **Recommendation**: Either add section header comments marking difficulty tiers, or split large-number problems (>100) into a new `mathematical_problems_level2_entries.md` file. No ownership conflicts found. No structural changes made in this audit — flagged for future rewriting decision.

11. [x] Audit `body_parts_entries.md` for anatomy vs body-state / health drift
    Notes:
    - Audited 28 entries for content scope and ownership boundaries.
    - **No drift detected**: All entries are anatomical definitions (what is X?), not body-state or wellness concepts.
    - **body_states_and_internal_cues_entries.md**: No overlap. `belly` mentions "hungry belly may rumble" but this is context for teaching anatomy, not a body-state definition. Body-states file correctly covers internal cues (hunger, dizziness, soreness).
    - **health_and_wellness_entries.md**: No overlap. `forehead` mentions fever checking but this is common usage context, not a health condition. Health file correctly covers conditions (fever, cough, headache) and care items (bandage, medicine).
    - **Broad-to-narrow ordering**: Preserved. File starts with `body part` (general), then major regions (head, face, arm, leg), then extremities (hand, foot), then details (ear, earlobe, eye, eyelid). Later entries (forehead, cheek, fingertip, knuckle) are part-level details that correctly follow their parent structures earlier in file.
    - **Result**: File is well-scoped. No structural changes required. No entries need trimming or relocation.

### C. Gap filling after the trunk pass

12. [x] Review `foods_vegetables_entries.md` as the first non-trunk cleanup file
    Notes:
    - Audited 16 entries for Level 1 register, duplicate anchors, contrast grounding, and ordering.
    - **Level 1 register: PASSED**. All entries use simple, concrete, child-facing language. Short sentences throughout.
    - **Duplicate anchors: NONE**. Clean ownership boundaries with food-related files:
      - `foods_vegetables_entries.md` owns vegetable definitions (vegetable, bean, broccoli, cabbage, carrot, cauliflower, garlic, lettuce, onion, pea, potato, spinach, tomato, parsnip, kale, sweet potato).
      - `foods_and_drinks_entries.md` owns general food/drink terms plus staples (food, drink, bread, cheese, egg, honey, milk, rice, soup, water, etc.).
      - `foods_fruits_entries.md` owns fruits and nuts (fruit, berry, apple, banana, plantain, nut, etc.).
      - `food_groups_and_nutrition_entries.md` owns nutrition concepts (food group, nutrition, vitamin, balanced meal, etc.).
      - `cooking_and_food_preparation_entries.md` owns cooking verbs and techniques. No overlap.
    - **Contrast grounding: ALL GROUNDED**. All 16 contrasts point to grounded anchors:
      - Within-file contrasts: bean↔pea, broccoli↔cauliflower, cabbage↔lettuce, carrot↔parsnip, garlic↔onion, potato↔sweet potato, spinach↔kale (symmetric pairs).
      - Cross-file contrast: `vegetable` → `fruit` grounded in foods_fruits_entries.md.
      - Clever contrast: tomato → potato (rhyme contrast, both grounded).
    - **Broad-to-narrow ordering: CORRECT**. File starts with general `vegetable` anchor, then individual vegetables in mostly alphabetical order. Later additions (parsnip, kale, sweet potato) correctly reference contrast pairs that appear earlier.
    - **Result**: File is well-scoped and clean. No structural changes required. Good symmetric contrast coverage within the vegetable domain.

13. [ ] Run a corpus-wide contrast and dependency cleanup pass
    Notes:
    - Verify that new or revised contrasts still point to grounded concepts.
    - Confirm that dependency fixes did not introduce duplicate anchor homes.

14. [ ] Reconcile documentation after the gap-filling batch
    Notes:
    - Update `01_CORPUS_STATUS.md` with completed work.
    - Keep `start.md` and planning docs aligned with the current two-file workflow.

### D. After Wiki Level 1 is stable

15. [ ] Backfill the phase 1-5 curriculum with foundational high-frequency terms that the wiki repeatedly relies on but the curriculum does not yet teach explicitly
    Notes:
    - Focus on always-used scaffold terms, not every missing word.
    - Current strongest candidates: `word`, `sentence`, `thought`/`idea`, `true`, `real`, with `money` as a practical follow-up candidate.
    - Prefer additions that improve comprehension across many wiki files, not narrow domain vocabulary.
    - Use `missing_curriculum_terms.md` as the tracking file for candidate selection and resolution.

16. [ ] Build a candidate triplet list for Story Layer 1 after Wiki Level 1
    Notes:
    - Generate strong anchor triplets for story creation from Phase 1-5 + Wiki Level 1 coverage.
    - Prioritize triplets that are semantically coherent, grounded, and reusable for short simple stories.
    - Treat this as the planning input for the first story-generation batch, not as story writing itself.
    - Deliverable: a reusable triplet-candidate list that can be taken into ChatGPT, Gemini, or a local model for story drafting.

17. [ ] Write a Story Layer rules document after the triplet list is ready
    Notes:
    - Define sentence-length targets by story level and the iterative cognitive-load framework.
    - Explicitly avoid "twist" framing; use gradual added load instead.
    - Include truthfulness-first behavior, including "I don't know," lookup/ask-for-help decisions, and cases where uncertainty is not important enough to pursue.
    - This document should be usable as the prompt/rubric when drafting stories in outside models and later when doing quality passes.

18. [ ] Document and follow the alternating expansion cadence: Wiki Level 1 → Stories 1 → Wiki Level 2 → Stories 2 → later wiki/story pairs
    Notes:
    - Treat each wiki level as followed by a corresponding story layer.
    - Keep story expansion tied to the wiki level that grounds it.
    - Use this cadence as the canonical progression unless later human review changes it.

---

## Deferred until the comprehension pass is stable

- Level 2 branching and richer snowflake expansion
- `00_ideas.md` connective-tissue batch
- New category creation unless the dependency audit proves it is necessary

---

## Good stopping condition for the current phase

This phase is in good shape when:
- the dependency ledger exists
- the trunk files have been audited
- the highest-value prerequisite gaps are either filled or explicitly logged
- `missing_curriculum_terms.md` contains the curriculum-side anchor gaps that should not be solved ad hoc in the wiki
- `01_CORPUS_STATUS.md` reflects the completed cleanup work
