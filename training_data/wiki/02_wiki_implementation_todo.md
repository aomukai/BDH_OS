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

13. [x] Run a corpus-wide contrast and dependency cleanup pass
    Notes:
    - Audited 1,366 contrast statements across all wiki entry files.
    - All contrasts point to grounded concepts (wiki or curriculum anchors).
    - Identified 31 duplicate question anchors: 5 documented intentional splits, 16 contextually acceptable, 10 flagged for future review.
    - High-priority deduplication: `height` (remove from space_entries.md), `lever` (clarify ownership).
    - Full results documented in ranked_gap_list.md under "Corpus-Wide Cleanup Pass Results (2026-04-18)".

14. [x] Resolve the concrete cleanup issues identified by Step 13's corpus-wide contrast and dependency pass
    Notes:
    - `height` duplicate removed from `space_entries.md`; canonical owner is `measurement_and_comparison_entries.md`.
    - `lever` ownership clarified as intentional split: `machines_and_simple_mechanisms_entries.md` (primary, simple machine science) and `tools_and_kitchenware_entries.md` (secondary, practical tool context).
    - School-domain duplicates (`grade`, `teacher`, `paper`) reviewed and documented as contextually acceptable.
    - All 16 contextually acceptable duplicates documented in `dependency_ledger.md` under "Documented Duplicate Anchors (Step 14 Cleanup)".
    - Low-priority overlaps (`a lot`, `collar`, `responsibility`, `category`, `material`) documented in ledger.
    - Resolution summary added to `ranked_gap_list.md` under "Step 14 Resolution Summary (2026-04-18)".

15. [x] Reconcile documentation after the gap-filling batch
    Notes:
    - Updated `01_CORPUS_STATUS.md` with gap-filling batch completion summary (Steps 1-14).
    - Added "Completed: Gap-Filling and Trunk Audit Batch" section documenting dependency infrastructure, trunk audit results, and cleanup summary.
    - Updated `level1_finish_and_level2_start_plan.md` to mark trunk audit as complete, cross-file overlap hotspots as resolved, and overall sequence steps 1, 3, 4 as done.
    - `start.md` does not exist; documentation workflow uses `02_wiki_implementation_todo.md` and `01_CORPUS_STATUS.md` as the two canonical files.

### D. After Wiki Level 1 is stable

16. [x] Backfill the phase 1-5 curriculum with foundational high-frequency terms that the wiki repeatedly relies on but the curriculum does not yet teach explicitly
    Notes:
    - Completed comprehensive analysis identifying 7 high-priority terms across 3 tiers.
    - Tier 1 (Critical, 4 terms): `thing`/`object`, `word`, `sentence`, `thought`/`idea` — each used in 15-50+ wiki files.
    - Tier 2 (Important, 3 terms): `true`, `real`, `money` — each used in 5-10+ wiki files.
    - Tier 3 (Defer, 3 terms): `truth`, `reality`, `cent` — depend on earlier terms.
    - Recommended resolution: Create Phase 5B bridging batch (~8-12 curriculum files) following standard curriculum format.
    - Sequencing: thing → word → sentence → thought → true → real → money.
    - Full analysis, implementation notes, and status tracking added to `missing_curriculum_terms.md`.

17. [x] Build a candidate triplet list for Story Layer 1 after Wiki Level 1
    Notes:
    - Created `story_triplet_candidates.md` with 200 semantically coherent triplets across 10 domains.
    - Domains: Animals/Nature (20), Home/Daily Life (20), Food/Meals (20), School/Learning (20), Play/Games (20), Weather/Seasons (20), People/Relationships (20), Body/Health (20), Vehicles/Travel (20), Tools/Making (20).
    - Each triplet follows anchor + support1 + support2 format with scenario hints.
    - All vocabulary verified grounded in Phase 1-5 curriculum or Wiki Level 1.
    - Includes design principles, usage notes, and example story expansion.
    - Ready for story drafting in ChatGPT, Gemini, local models, or other tools.

18. [x] Write a Story Layer rules document after the triplet list is ready
    Notes:
    - Created `story_layer_rules.md` with comprehensive rules for Story Layers 1-4.
    - Sentence-length targets: Layer 1 (5-10 words), Layer 2 (8-15), Layer 3 (10-18), Layer 4 (12-20).
    - Five-dimension cognitive-load framework: sentence length, concept count, causation, temporality, contrast.
    - Truthfulness rules cover: certainty, "I don't know," lookup/ask-for-help, and uncertainty-not-worth-pursuing cases.
    - Quality checklist and failure modes section for quality passes.
    - Example prompts for external model story generation included.
    - Document usable as prompt/rubric for drafting and quality assurance.

19. [x] Document and follow the alternating expansion cadence: Wiki Level 1 → Stories 1 → Wiki Level 2 → Stories 2 → later wiki/story pairs
   Notes:
   - Added comprehensive "Alternating Expansion Cadence (Canonical Rule)" section to `level1_finish_and_level2_start_plan.md`.
   - Documents the strict alternating pattern: Wiki Level N → Story Layer N → Wiki Level N+1 → Story Layer N+1.
   - Explains why alternation matters: grounding before variation, reinforcement through context, controlled complexity growth, quality gates.
   - Includes story-layer-to-wiki-level mapping table with vocabulary scope and sentence constraints per level.
   - Documents connective tissue batch placement between Wiki Level 1 and Story Layer 1.
   - Adds explicit rules: do not skip story layers, do not front-load stories with ungrounded vocabulary.
   - Specifies human review checkpoints at each transition.
   - Updated Level 2 start criteria to include "Story Layer 1 is complete" as a prerequisite.
   - Added cross-reference in `docs/training_pipeline.md` Stage 7 to point to the detailed cadence rules.

### E. Level 2 queue setup

20. [x] Pause the hourly wiki implementation cron while Level 2 planning replaces the old queue
   Notes:
   - Paused cron job `hourly-wiki-implementation` (`795c8123f2ae`) to stop burning tokens on an exhausted queue.

21. [x] Run a file-level Level 2 expansion assessment before creating the real Level 2 batch
   Notes:
   - Created `training_data/wiki/wiki_level2_expansion_assessment.md`.
   - Assessed current Level 1 files into 3 buckets: 12 expand-now candidates, 16 conditional/later candidates, and 84 keep-at-Level-1 files.
   - Used `level1_finish_and_level2_start_plan.md` explicit candidates/compact-file guidance plus role-group rules from `01_CORPUS_STATUS.md`.

22. [x] Filter the dedicated Wiki Level 2 queue so it only includes files that actually justify expansion
   Notes:
   - Rewrote `training_data/wiki/wiki_level2_queue.md` as a filtered queue for dedicated Level 2 expansion articles only.
   - Queue now contains 12 approved expand-now file containers across 4 passes: creation, quality, gaps, dependencies.
   - Each queued file must be treated as a container whose entries are evaluated individually for escalation.
   - Queue rule is still one file container at a time, preserving the same file order across all passes unless a human reprioritizes it.

23. [x] Create scaffold files for the approved Level 2 article batch
   Notes:
   - Created `training_data/wiki/level2_articles/` with 12 scaffold files and `level2_articles_manifest.md`.
   - Scaffold creation is planning structure only, not completed content-writing.

24. [x] Build an entry-level expansion index so file-level queue runs do not hide per-entry decisions
   Notes:
   - Created `training_data/wiki/wiki_entry_expansion_index.md` and `training_data/wiki/wiki_entry_expansion_index.csv`.
   - Index treats each Level 1 entry as its own entity and records whether it currently remains Level 1 or is detected in a written Level 2 article.
   - File-level docs now explicitly point to the entry-level index as the canonical entity view.

25. [x] Review the Story Layer 1 / connective-tissue gate before actual Level 2 writing begins
   Notes:
   - User explicitly approved the per-file Claude-driven expansion workflow and allowed Level 2 article writing to begin one file container at a time.

26. [ ] Continue the Level 2 queue from `wiki_level2_queue.md`, one file container at a time
   Notes:
   - Earlier file-level creation results have been rechecked under the new entry-level workflow.
   - Existing Level 2 drafts remain repairable artifacts, but the queue now runs on per-entry accounting.
   - Creation pass is complete for all approved files.
   - Quality pass completed for `emotions_entries.md` (2026-04-19): 20/20 split verified; article structure and content earn tokens.
   - Quality pass completed for `friends_and_peer_interactions_entries.md` (2026-04-19): existing 5/4 entry split verified; article retained without edits because invitation/refusal, joining-play, conflict, playdate, and friendship-maintenance sections already earn their tokens.
   - Quality pass completed for `conflict_resolution_and_relationship_repair_entries.md` (2026-04-19): 4/3 entry split verified (advanced: conflict resolution, compromise, forgive, apologize; stayed L1: let's try again, that's okay, how can we fix this); article retained without edits because the apology, forgiveness, compromise, repair-failure, and rebuilding sections earn their tokens. Next quality-pass file: `school_life_and_learning_entries.md`.
   - Quality pass completed for `school_life_and_learning_entries.md` (2026-04-19): 8/21 entry split verified (advanced: school, classroom, teacher, student, lesson, homework, recess, test; stayed L1: subject, grade, school bus, book, paper, pencil, pen, crayon, backpack, lunchbox, playground, principal, magazine); article retained without edits because the existing 12-section school-domain scenario set still earns its tokens. Next quality-pass file: `play_games_and_sports_entries.md`.
   - Quality pass completed for `play_games_and_sports_entries.md` (2026-04-19): existing 6/4 entry split verified (advanced: play, game, team, win, lose, cheat; stayed L1: sport, score, tag, hide and seek); article retained without edits because the play-types, rules/fairness, cheating, team-coordination, win/lose, and sportsmanship sections still earn their tokens. Next quality-pass file: `community_places_and_services_entries.md`.
   - Quality pass completed for `community_places_and_services_entries.md` (2026-04-19): 5/11 entry split verified (advanced: library, hospital, grocery store, fire station, restaurant; stayed L1: community place, service, police, police station, post office, museum, bakery, bus stop, bank, pharmacy, clinic); article retained without edits because the existing library/hospital/grocery-store/fire-station/restaurant sections still earn their tokens. Next quality-pass file: `technology_and_digital_media_entries.md`.
   - Quality pass completed for `technology_and_digital_media_entries.md` (2026-04-19): existing 5/9 entry split verified (advanced: phone, tablet, computer, video, app; stayed L1: technology, screen, message, swipe, tap, TV, keyboard, photo, username); article retained without edits because the device-use rules, screen-time boundaries, permission scripts, and app/video safety scenarios still earn their tokens. Next quality-pass file: `health_and_wellness_entries.md`.
   - Quality pass completed for `health_and_wellness_entries.md` (2026-04-19): existing 12/5 entry split verified (advanced: fever, cough, sore throat, headache, stomachache, cut, bruise, medicine, germ, sneeze, runny nose, checkup; stayed L1: health, wellness, bandage, rash, allergy); article retained without edits because the symptom, injury-care, medicine-safety, hygiene, and checkup sections still earn their tokens. Next quality-pass file: `storytelling_and_narrative_structure_entries.md`.
   - Quality pass completed for `storytelling_and_narrative_structure_entries.md` (2026-04-19): 5/11 entry split verified (advanced: story, plot, narrator, suddenly, meanwhile; stayed L1: beginning, middle, end, first, next, then, before, after, finally, at the end, once upon a time); article retained without edits because the story-types, plot-structure, narrator-perspective, and pacing-tools sections still earn their tokens. Next quality-pass file: `perspective_taking_and_theory_of_mind_entries.md`.
   - Quality pass completed for `perspective_taking_and_theory_of_mind_entries.md` (2026-04-19): 6/2 entry split verified (advanced: perspective, believe, misunderstand, I thought, he didn't know that, put yourself in someone else's place; stayed L1: they felt, she wanted); article retained without edits because the perspective, belief, misunderstanding, past-thought-reporting, missing-information, and empathy-practice sections still earn their tokens. Next quality-pass file: `evidence_and_justification_entries.md`.
   - Quality pass completed for `evidence_and_justification_entries.md` (2026-04-19): 4/5 entry split verified (advanced: `justification`, `reason why`, `example`, `that proves`; stayed L1: `because I saw it`, `I know this because`, `for instance`, `I can show you`, `back it up`); article retained without edits because the source-of-justification branching, reason-vs-example distinction, good-vs-weak example treatment, and prove-vs-support sections still earn their tokens. Next gap-pass file: `emotions_entries.md`.
   - Gap pass completed for `emotions_entries.md` (2026-04-19): 20/20 split retained (advanced: `emotion`, `happiness`, `sadness`, `anger`, `frustration`, `fear`, `nervousness`, `worry`, `panic`, `loneliness`, `belonging`, `pride`, `shame`, `embarrassment`, `guilt`, `jealousy`, `disappointment`, `excitement`, `boredom`, `calmness`; stayed L1: `surprise`, `confusion`, `love`, `bravery`, `hunger`, `thirst`, `pain`, `comfort`, `fullness`, `hate`, `kindness`, `cruelty`, `tiredness`, `trust`, `hope`, `curiosity`, `gratitude`, `relief`, `wonder`, `disgust`); no article-body changes were needed because the existing 9-section article already covers the highest-value mixed-feeling, regulation, distinction, and scenario gaps. Next gap-pass file: `communication_acts_and_language_entries.md`.
   - Gap pass completed for `communication_acts_and_language_entries.md` (2026-04-20): 6/5 split retained (advanced: `ask`, `answer`, `promise`, `"what does that mean"`, `"can you say it again"`, `"I meant"`; stayed L1: `communication`, `whisper`, `shout`, `explain`, `complaint`); no article-body changes were needed because the existing asking, answering, promise, and conversation-repair sections already cover the highest-value gaps. Next gap-pass file: `friends_and_peer_interactions_entries.md`.
   - Gap pass completed for `friends_and_peer_interactions_entries.md` (2026-04-20): existing 5/4 split retained (advanced: `friendship`, `invite`, `argue`, `make up`, `playdate`; stayed L1: `classmate`, `teammate`, `play together`, `be my friend`); no article-body changes were needed because the invitation/refusal, joining-play, conflict, playdate, and friendship-maintenance sections already cover the highest-value peer-social gaps. Next gap-pass file: `conflict_resolution_and_relationship_repair_entries.md`.
   - Gap pass completed for `conflict_resolution_and_relationship_repair_entries.md` (2026-04-20): existing 4/3 split retained (advanced: `conflict resolution`, `compromise`, `forgive`, `apologize`; stayed L1: `let's try again`, `that's okay`, `how can we fix this`); no article-body changes were needed because the apology, forgiveness, compromise, repair-failure, and rebuilding sections already cover the highest-value gaps. Next gap-pass file: `school_life_and_learning_entries.md`.
   - Gap pass completed for `school_life_and_learning_entries.md` (2026-04-20): existing 8/13 split retained (advanced: `school`, `classroom`, `teacher`, `student`, `lesson`, `homework`, `recess`, `test`; stayed L1: `subject`, `grade`, `school bus`, `book`, `paper`, `pencil`, `pen`, `crayon`, `backpack`, `lunchbox`, `playground`, `principal`, `magazine`); no article-body changes were needed because the existing school-routine, classroom-flow, interaction, homework, test, transition, event, and hard-day sections already cover the highest-value gaps. Next gap-pass file: `play_games_and_sports_entries.md`.
- Gap pass completed for `play_games_and_sports_entries.md` (2026-04-20): existing 6/4 split retained (advanced: `play`, `game`, `team`, `win`, `lose`, `cheat`; stayed L1: `sport`, `score`, `tag`, `hide and seek`); no article-body changes were needed because the current play-types, rules/fairness, cheating, team-coordination, win/lose, and sportsmanship sections already cover the highest-value gaps. Next gap-pass file: `community_places_and_services_entries.md`.
- Gap pass completed for `community_places_and_services_entries.md` (2026-04-20): existing 5/11 split retained (advanced: `library`, `hospital`, `grocery store`, `fire station`, `restaurant`; stayed L1: `community place`, `service`, `police`, `police station`, `post office`, `museum`, `bakery`, `bus stop`, `bank`, `pharmacy`, `clinic`); no article-body changes were needed because the existing visit scripts, helper roles, safety guidance, and place comparisons already cover the highest-value gaps. Next gap-pass file: `technology_and_digital_media_entries.md`.
- Gap pass completed for `technology_and_digital_media_entries.md` (2026-04-20): existing 5/9 split retained (advanced: `phone`, `tablet`, `computer`, `video`, `app`; stayed L1: `technology`, `screen`, `message`, `swipe`, `tap`, `TV`, `keyboard`, `photo`, `username`); no article-body changes were needed because the existing device-use rules, screen-time boundaries, permission scripts, and app/video safety scenarios already cover the highest-value gaps. Next gap-pass file: `health_and_wellness_entries.md`.

- Gap pass completed for `health_and_wellness_entries.md` (2026-04-20): existing 12/5 split retained (advanced: `fever`, `cough`, `sore throat`, `headache`, `stomachache`, `cut`, `bruise`, `medicine`, `germ`, `sneeze`, `runny nose`, `checkup`; stayed L1: `health`, `wellness`, `bandage`, `rash`, `allergy`); no article-body changes were needed because the symptom, injury-care, medicine-safety, hygiene, and checkup sections already cover the highest-value gaps. Next gap-pass file: `storytelling_and_narrative_structure_entries.md`.
- Gap pass completed for `storytelling_and_narrative_structure_entries.md` (2026-04-20): existing 5/11 split retained (advanced: `story`, `plot`, `narrator`, `suddenly`, `meanwhile`; stayed L1: `beginning`, `middle`, `end`, `first`, `next`, `then`, `before`, `after`, `finally`, `at the end`, `once upon a time`); no article-body changes were needed because the story-types, plot-structure, narrator-perspective, and pacing-tools sections already cover the highest-value gaps. Next gap-pass file: `perspective_taking_and_theory_of_mind_entries.md`.
- Gap pass completed for `perspective_taking_and_theory_of_mind_entries.md` (2026-04-20): existing 6/2 split retained (advanced: `perspective`, `believe`, `misunderstand`, `I thought`, `he didn't know that`, `put yourself in someone else's place`; stayed L1: `they felt`, `she wanted`); no article-body changes were needed because the perspective, belief, misunderstanding, past-thought-reporting, missing-information, empathy-practice, and common-scenario sections already cover the highest-value gaps.
- Gap pass completed for `evidence_and_justification_entries.md` (2026-04-20): existing 4/5 split retained (advanced: `justification`, `reason why`, `example`, `that proves`; stayed L1: `because I saw it`, `I know this because`, `for instance`, `I can show you`, `back it up`); no article-body changes were needed because the source-of-justification branching, reason-vs-example distinction, good-vs-weak example treatment, and prove-vs-support sections already cover the highest-value gaps. Pass 3 (Gap Pass) is now complete for all 12 approved files. Next queued file: `emotions_entries.md` (Pass 4 — Dependencies).
- Dependency pass completed for `emotions_entries.md` (2026-04-20): existing 20/20 split retained (advanced: `emotion`, `happiness`, `sadness`, `anger`, `frustration`, `fear`, `nervousness`, `worry`, `panic`, `loneliness`, `belonging`, `pride`, `shame`, `embarrassment`, `guilt`, `jealousy`, `disappointment`, `excitement`, `boredom`, `calmness`; stayed L1: `surprise`, `confusion`, `love`, `bravery`, `hunger`, `thirst`, `pain`, `comfort`, `fullness`, `hate`, `kindness`, `cruelty`, `tiredness`, `trust`, `hope`, `curiosity`, `gratitude`, `relief`, `wonder`, `disgust`). Metadata-only completion: dependencies were confirmed against `body_states_and_internal_cues_entries.md`, `body_parts_entries.md`, `people_roles_entries.md`, `school_life_and_learning_entries.md`, and `play_games_and_sports_entries.md`, so no article-body changes were needed. Level 3 remains the provisional ceiling, but the file now holds for human review before any Level 3 branching. Next dependency-pass file: `communication_acts_and_language_entries.md`.
- Dependency pass completed for `communication_acts_and_language_entries.md` (2026-04-20): existing 6/5 split retained (advanced: `ask`, `answer`, `promise`, `"what does that mean"`, `"can you say it again"`, `"I meant"`; stayed L1: `communication`, `whisper`, `shout`, `explain`, `complaint`). Metadata-only completion: dependencies were rechecked against `greetings_and_social_salutations_entries.md`, `agreement_and_disagreement_entries.md`, `manners_politeness_and_social_etiquette_entries.md`, `praise_criticism_and_feedback_entries.md`, `people_roles_entries.md`, `conflict_resolution_and_relationship_repair_entries.md`, and `evidence_and_justification_entries.md`, so no article-body changes were needed. Level 2 remains the ceiling and the next dependency-pass file is `friends_and_peer_interactions_entries.md`.
- Dependency pass completed for `friends_and_peer_interactions_entries.md` (2026-04-20): existing 5/4 split retained (advanced: `friendship`, `invite`, `argue`, `make up`, `playdate`; stayed L1: `classmate`, `teammate`, `play together`, `be my friend`). Metadata-only completion: dependencies were verified against `emotions_entries.md`, `conflict_resolution_and_relationship_repair_entries.md`, `play_games_and_sports_entries.md`, `people_roles_entries.md`, `ownership_and_sharing_entries.md`, `manners_politeness_and_social_etiquette_entries.md`, `school_life_and_learning_entries.md`, and `inclusion_bullying_and_kindness_entries.md`, so no article-body changes were needed. Level 2 remains the ceiling and the next dependency-pass file is `conflict_resolution_and_relationship_repair_entries.md`.
- Dependency pass completed for `play_games_and_sports_entries.md` (2026-04-21): existing 6/4 split retained (advanced: `play`, `game`, `team`, `win`, `lose`, `cheat`; stayed L1: `sport`, `score`, `tag`, `hide and seek`). Metadata-only completion: dependencies were verified against `emotions_entries.md` (happiness, anger, frustration, pride, embarrassment, calmness, trust), `logic_entries.md` (fairness), `inclusion_bullying_and_kindness_entries.md` (respect), `agreement_and_disagreement_entries.md` (disagreement), `conflict_resolution_and_relationship_repair_entries.md` (conflict resolution, compromise, forgive, apologize), `verbs_entries.md` (listen), `STEM_entries.md` (breathe), `learning_memory_and_metacognition_entries.md` (practice), `imagination_and_pretend_play_entries.md` (imagination, pretend), and `school_life_and_learning_entries.md` (recess), so no article-body changes were needed. Level 2 remains the ceiling and the next dependency-pass file is `community_places_and_services_entries.md`.
   - Dependency pass completed for `technology_and_digital_media_entries.md` (2026-04-21): existing 5/9 split retained (advanced: `phone`, `tablet`, `computer`, `video`, `app`; stayed L1: `technology`, `screen`, `message`, `swipe`, `tap`, `TV`, `keyboard`, `photo`, `username`). Metadata-only completion: dependencies were verified against `online_safety_and_privacy_entries.md` (password, personal information, screen time, ask a grown-up), `growth_and_life_stages_human_entries.md` (child, grown-up, adult), `people_roles_entries.md` (family), `emotions_entries.md` (fear, worry, trust, tiredness), `logic_entries.md` (true, false, truth, lie, problem, rule), `safety_rules_and_emergency_awareness_entries.md` (safety, careful), `manners_politeness_and_social_etiquette_entries.md` (please, may I, politeness), `inclusion_bullying_and_kindness_entries.md` (respect), `boundaries_and_consent_entries.md` (consent), `money_trade_and_shopping_entries.md` (money), `time_entries.md` (time), `body_parts_entries.md` (eye), `sleep_and_rest_entries.md` (rest, bedtime concepts), `meals_and_mealtime_talk_entries.md` (meal), `accidents_and_mistakes_entries.md` (accident), and `simple_physics_energy_and_power_entries.md` (power, energy), so no article-body changes were needed. Level 2 remains the ceiling and the next dependency-pass file is `health_and_wellness_entries.md`.
   - Dependency pass completed for `health_and_wellness_entries.md` (2026-04-21): existing 12/5 split retained (advanced: `fever`, `cough`, `sore throat`, `headache`, `stomachache`, `cut`, `bruise`, `medicine`, `germ`, `sneeze`, `runny nose`, `checkup`; stayed L1: `health`, `wellness`, `bandage`, `rash`, `allergy`). Metadata-only completion: dependencies were verified against `body_parts_entries.md` (head, face, hand, finger, nose, mouth, ear, eye, belly, chest, knee, forehead), `body_states_and_internal_cues_entries.md` (dizzy, sore, shiver, tummy hurts), `growth_and_life_stages_human_entries.md` (child, adult, grown-up), `daily_routines_and_self_care_entries.md` (wash hands, routine), `sleep_and_rest_entries.md` (rest, sleepy), `community_places_and_services_entries.md` (hospital, clinic, pharmacy), `professions_entries.md` (doctor, nurse), `foods_and_drinks_entries.md` (water, food, soup), `emotions_entries.md` (fear, worry, pain, comfort, tiredness, relief, calmness, nervousness), `school_life_and_learning_entries.md` (school, homework, test), and `measurement_and_comparison_entries.md` (temperature), so no article-body changes were needed. Level 2 remains the ceiling and the next dependency-pass file is `storytelling_and_narrative_structure_entries.md`.

27. [x] Add missing law/safety role anchors: `police` and `police officer`
   Notes:
   - Added `police` to `community_places_and_services_entries.md` as the broader community-safety/institution anchor.
   - Added `police officer` to `professions_entries.md` as the person-role/job anchor.
   - Kept `police station` in `community_places_and_services_entries.md` as the place anchor.

   - Completed entry-level creation-pass repair for `friends_and_peer_interactions_entries.md`: 5 entries advanced to Level 2 (`friendship`, `invite`, `argue`, `make up`, `playdate`) and 4 stayed Level 1 (`classmate`, `teammate`, `play together`, `be my friend`).
   - Completed entry-level creation-pass repair for `conflict_resolution_and_relationship_repair_entries.md`: 4 entries advanced to Level 2 (`conflict resolution`, `compromise`, `forgive`, `apologize`) and 3 stayed Level 1 (`let's try again`, `that's okay`, `how can we fix this`).
   - Completed entry-level creation-pass repair for `school_life_and_learning_entries.md`: 8 entries advanced to Level 2 (`school`, `classroom`, `teacher`, `student`, `lesson`, `homework`, `recess`, `test`) and 13 stayed Level 1 (`subject`, `grade`, `school bus`, `book`, `paper`, `pencil`, `pen`, `crayon`, `backpack`, `lunchbox`, `playground`, `principal`, `magazine`).
   - Completed entry-level creation-pass repair for `play_games_and_sports_entries.md`: 6 entries advanced to Level 2 (`play`, `game`, `team`, `win`, `lose`, `cheat`) and 4 stayed Level 1 (`sport`, `score`, `tag`, `hide and seek`).
   - Completed entry-level creation-pass repair for `community_places_and_services_entries.md`: 5 entries advanced to Level 2 (`library`, `hospital`, `grocery store`, `fire station`, `restaurant`) and 11 stayed Level 1 (`community place`, `service`, `police`, `police station`, `post office`, `museum`, `bakery`, `bus stop`, `bank`, `pharmacy`, `clinic`).
   - Completed entry-level creation-pass repair for `technology_and_digital_media_entries.md`: 5 entries advanced to Level 2 (`phone`, `tablet`, `computer`, `video`, `app`) and 9 stayed Level 1 (`technology`, `screen`, `message`, `swipe`, `tap`, `TV`, `keyboard`, `photo`, `username`).
   - Completed entry-level creation-pass repair for `health_and_wellness_entries.md`: 12 entries advanced to Level 2 (`fever`, `cough`, `sore throat`, `headache`, `stomachache`, `cut`, `bruise`, `medicine`, `germ`, `sneeze`, `runny nose`, `checkup`) and 5 stayed Level 1 (`health`, `wellness`, `bandage`, `rash`, `allergy`).
   - Completed entry-level creation-pass repair for `storytelling_and_narrative_structure_entries.md`: 5 entries advanced to Level 2 (`story`, `plot`, `narrator`, `suddenly`, `meanwhile`) and 11 stayed Level 1 (`beginning`, `middle`, `end`, `first`, `next`, `then`, `before`, `after`, `finally`, `at the end`, `once upon a time`).
   - Completed entry-level creation-pass review for `perspective_taking_and_theory_of_mind_entries.md`: 6 entries advanced to Level 2 (`perspective`, `believe`, `misunderstand`, `I thought`, `he didn't know that`, `put yourself in someone else's place`) and 2 stayed Level 1 (`they felt`, `she wanted`).
   - Completed entry-level creation-pass for `evidence_and_justification_entries.md`: 4 entries advanced to Level 2 (`justification`, `reason why`, `example`, `that proves`) and 5 stayed Level 1 (`because I saw it`, `I know this because`, `for instance`, `I can show you`, `back it up`).

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
