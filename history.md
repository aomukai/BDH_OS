# HISTORY

This file records finished work.

Rules:
- Every completed task moves here from `todo.md`.
- `todo.md` stays focused on unfinished work only.
- Legacy planning/status files were moved to `archive/` and summarized below.

## Finished at a glance

- **Phase 1–5 curriculum foundation:** existing rewritten corpus present; foundational missing-term backfill analysis completed.
- **Phase 6 bridge:** manifest drafted, all 6 files written, all 6 files quality-passed.
- **Wiki Level 1:** stable base corpus and cleanup pass completed.
- **Wiki Level 2:** 12 approved Level 2 articles written; post-Level-2 quality pass completed for all 12.
- **Story Tier 1:** All 10 Tier 1 files (`school_and_learning.md`, `play_and_games.md`, `people_and_relationships.md`, `home_and_daily_life.md`, `weather_and_seasons.md`, `animals_and_nature.md`, `body_and_health.md`, `food_and_meals.md`, `tools_and_making.md`, and `vehicles_and_travel.md`) have been audited/repaired and converted into repeated `[user]` / `[assistant]` training-pair format.
- **Story Tier 2:** `school_and_learning.md` created and quality-passed; `play_and_games.md`, `people_and_relationships.md`, `home_and_daily_life.md`, `weather_and_seasons.md`, `animals_and_nature.md`, `body_and_health.md`, `food_and_meals.md`, `tools_and_making.md`, and `vehicles_and_travel.md` created.
- **Story Tier 3:** `school_and_learning.md` created as the first vertical-slice file.
- **Story Tier 4:** `school_and_learning.md` created as the first vertical-slice file.
- **Directory structure cleanup:** active corpus files now live under `training_data/phases/` and `training_data/wiki/wiki_1`–`wiki_4`; legacy queue/status docs and old deprecated phase files were moved under `archive/`.
- **Planning status:** the Wiki Level 3 planning gate was opened for planning only.

## Imported completed tasks from legacy files

### training_data/phases/phase_6/review_queue.md
- 1. [x] `phase_6_01.md`
- 2. [x] `phase_6_02.md`
- 3. [x] `phase_6_03.md`
- 4. [x] `phase_6_04.md`
- 5. [x] `phase_6_05.md`
- 6. [x] `phase_6_06.md`

### todo.md
- 1. [x] Audit and repair `training_data/triplet_stories/tier_1/body_and_health.md` against the Tier 1 spec — REPAIRED (2026-04-25): All 20 stories audited. Converted from markdown table + `##` headings to `[user]`/`[assistant]` pair format. Fixed header typos (story #143: see+see→see+look, story #158: soap+bubbles→soap+clean). Removed first-person (I/my/me), second-person (you/your), names (Mommy), and imperative/exclamatory style. Ensured 8-sentence structure and third-person narration for all entries.
- 2. [x] Audit and repair `training_data/triplet_stories/tier_1/people_and_relationships.md` against the Tier 1 spec
- 2. [x] `school_and_learning.md`
- 3. [x] `play_and_games.md`
- 4. [x] Audit and repair `training_data/triplet_stories/tier_1/home_and_daily_life.md` against the Tier 1 spec — REPAIRED (2026-04-25): All 20 stories audited. Removed quoted dialogue, names, and first-person perspective. Ensured 8-sentence structure and indirect narration for all entries.
- 5. [x] Convert `training_data/triplet_stories/tier_1/home_and_daily_life.md` into repeated `[user]` / `[assistant]` training pairs
- 6. [x] Audit and repair `training_data/triplet_stories/tier_1/weather_and_seasons.md` against the Tier 1 spec — REPAIRED (2026-04-25): All 20 stories audited. Removed first-person perspective (I/my/me/we/our), converted from markdown table + `##` headings to `[user]`/`[assistant]` pair format, ensured 8-sentence structure and third-person narration for all entries.
- 7. [x] Convert `training_data/triplet_stories/tier_1/weather_and_seasons.md` into repeated `[user]` / `[assistant]` training pairs
- 8. [x] Audit and repair `training_data/triplet_stories/tier_1/animals_and_nature.md` against the Tier 1 spec — REPAIRED (2026-04-25): All 20 stories audited. Converted from markdown table + `##` headings to `[user]`/`[assistant]` pair format. Fixed story #5 header typo (flower+flower→flower+honey). Ensured 8-sentence structure for all entries. No names, no quoted dialogue, no first-person. Endings stay inside scene.
- 9. [x] Audit and repair `training_data/triplet_stories/tier_1/food_and_meals.md` against the Tier 1 spec — REPAIRED (2026-04-25): All 20 stories audited. Converted from markdown table + `##` headings to `[user]`/`[assistant]` pair format. Fixed story #52 header typo (grape+vine+left→grape+vine+bunch). Expanded all stories from 6-7 sentences to 8 sentences. Ensured clear noun referent before any pronoun use. No names, no quoted dialogue, no first-person. Endings stay inside scene.
- 10. [x] Audit and repair `training_data/triplet_stories/tier_1/tools_and_making.md` against the Tier 1 spec — REPAIRED (2026-04-26): All 20 stories audited. Converted from markdown table + `##` headings to `[user]`/`[assistant]` pair format. Removed first-person perspective (I/my/me/we) from all stories. Removed asterisk-wrapped onomatopoeia (*Clang!*, *Scrape!*, etc.). Expanded all stories from 6-7 sentences to 8 sentences. Ensured clear noun referent before any pronoun use. No names, no quoted dialogue. Endings stay inside scene.
- 11. [x] Audit and repair `training_data/triplet_stories/tier_1/vehicles_and_travel.md` against the Tier 1 spec — REPAIRED (2026-04-26): All 20 stories audited. Converted from markdown table + `##` headings to `[user]`/`[assistant]` pair format. Removed first-person perspective (I/my/me/we/us/our) from all stories. Removed names (Dad, Mom). Removed exclamatory/command style (Look!, Watch me!). Ensured 8-sentence structure and third-person narration for all entries. No names, no quoted dialogue. Endings stay inside scene.
- 12. [x] Convert `training_data/triplet_stories/tier_1/vehicles_and_travel.md` into repeated `[user]` / `[assistant]` training pairs — completed as part of audit/repair task above.
- 13. [x] Convert `training_data/triplet_stories/tier_1/school_and_learning.md` into repeated `[user]` / `[assistant]` training pairs — COMPLETED (2026-04-26): Converted from markdown table + `##` headings format to repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. All 20 stories retained with 8 sentences each. Story content unchanged; only format converted.
- 14. [x] Convert `training_data/triplet_stories/tier_1/people_and_relationships.md` into repeated `[user]` / `[assistant]` training pairs — COMPLETED (2026-04-26): Converted from markdown table + `##` headings format to repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. All 20 stories retained with 8 sentences each. Story content unchanged; only format converted. Added header with file title.
- 15. [x] Convert `training_data/triplet_stories/tier_1/animals_and_nature.md` into repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format — COMPLETED (2026-04-26): Verified that the file is in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format with 20 stories of 8 sentences each. Format conversion was completed during the audit/repair phase.
- 16. [x] Create `training_data/triplet_stories/tier_2/play_and_games.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters from a new registry, and uses Domain 5 triplets. Verified vocabulary against Phase 1-5 and Wiki Level 1.
| 17. [x] Create `training_data/triplet_stories/tier_2/people_and_relationships.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters (reusing students from previous files and adding new family/neighbor/doctor roles), and uses Domain 7 triplets. Verified vocabulary against Phase 1-5 and Wiki Level 1.
| 18. [x] Create `training_data/triplet_stories/tier_2/home_and_daily_life.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters from the registry (including family members Mrs. Lee and Mr. Brown, and baby Billy), and uses Domain 2 triplets. Verified vocabulary against Phase 1-5 and Wiki Level 1.
- 19. [x] Create `training_data/triplet_stories/tier_2/weather_and_seasons.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters (20 new children: Tess, Eli, Ivy, Cole, Nina, Jade, Max, Ben, Rosa, Owen, Mila, Pete, Gia, Kai, Zara, Amy, Wes, Eve, Hugo, Nate), and uses weather/seasons triplets. Added characters to character_registry.md.
- 20. [x] Create `training_data/triplet_stories/tier_2/animals_and_nature.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters (20 new children: Fern, Gus, Iris, Drew, Clara, Jude, Nell, Seth, June, Kai, Phoebe, Miles, Hope, Ross, Ada, Theo, Vera, Wyatt, Bea, Leo), and uses animals/nature triplets matching the Tier 1 anchors. Added characters to character_registry.md.
- 21. [x] Create `training_data/triplet_stories/tier_2/body_and_health.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters (20 new children: Rose, Jace, Pearl, Dean, Daisy, Hank, Kay, Arlo, Wren, Scott, Joy, Cole, Nell, Miles, Faye, Hugh, Ivy, Reid, Opal, Kent), and uses body/health triplets matching the Tier 1 anchors (hand, foot, eye, ear, nose, mouth, tooth, belly, knee, finger, sleep, hungry, thirsty, sick, hurt, medicine, bandage, washing, brushing teeth, exercise). Added characters to character_registry.md.
- 22. [x] Create `training_data/triplet_stories/tier_2/food_and_meals.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters (20 new children: Beth, Gabe, Clara, Eli, Fern, Grant, Hope, Hugh, Iris, Joel, Kate, Lane, Meg, Ned, Olive, Paul, Quinn, Reed, Sara, Todd), and uses food/meals triplets matching the Tier 1 anchors (apple, banana, bread, egg, carrot, cookie, milk, soup, cheese, berry, orange, grapes, potato, corn, honey, rice, watermelon, strawberry, pumpkin, cupcake). Added characters to character_registry.md.
- 23. [x] Create `training_data/triplet_stories/tier_2/tools_and_making.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters (20 new children: Cody, Tara, Will, Dawn, Mark, Ruth, Kent, Jade, Eric, Nina, Greg, Lily, Jude, May, Finn, Boyd, Gwen, Dean, Anne, Phil), and uses tools/making triplets matching the Tier 1 anchors (hammer, shovel, rope, bucket, broom, scissors, glue, brush, brick, block, screw, key, hook, nail, lever, wheel, saw, tape, pot, spoon). Added characters to character_registry.md.
- 24. [x] Create `training_data/triplet_stories/tier_2/vehicles_and_travel.md` in repeated `[user]` / `[assistant]` format — COMPLETED (2026-04-26): Created 20 Tier 2 stories in the repeated `[user]tell me a story about <anchor>.` / `[assistant]` pair format. Each story has 12 sentences, named characters (20 new children: Tate, Vera, Nash, Willa, Joel, Skye, Drew, Faye, Gus, Pearl, Troy, Mae, Jett, June, Cade, Lark, Eli, Iris, Kent, Hope), and uses vehicles/travel triplets matching the Tier 1 anchors (car, bus, bike, train, plane, boat, truck, sled, wagon, ship, wheel, road, bridge, helmet, seatbelt, walking, running, trip, map, stop sign). Added characters to character_registry.md.

### training_data/triplet_stories/tier_1/post_level2_review_queue.md
- 1. [x] `people_and_relationships.md` — REPAIRED (2026-04-25): All 20 stories audited. Removed quoted dialogue, names, and first-person perspective. Ensured 8-sentence structure and indirect narration for all entries.
- 2. [x] `school_and_learning.md` — PASS (2026-04-24): All 20 stories verified. 8 sentences each, no names, no quoted dialogue, pronouns only after clear referents, endings inside scene. No fixes needed.

### training_data/triplet_stories/tier_2/post_level2_review_queue.md
- 1. [x] `school_and_learning.md`

### training_data/triplet_stories/tier_2/review_queue.md
- 1. [x] `school_and_learning.md`

### training_data/triplet_stories/tier_3/review_queue.md
- 1. [x] `school_and_learning.md`

### training_data/triplet_stories/tier_4/review_queue.md
- 1. [x] `school_and_learning.md`

### todo.md
- 1. [x] Audit and normalize backlog dependencies, then build a corpus-wide dependency ledger from `wiki_category_backlog.md`
- 2. [x] Identify comprehension-critical missing or weak prerequisites
- 3. [x] Produce a ranked gap list for the wiki corpus
- 4. [x] Audit `logic_entries.md` for dependency ownership and overlap
- 5. [x] Audit `STEM_entries.md` for dependency ownership and overlap
- 6. [x] Audit `time_entries.md` for sequence-language ownership
- 7. [x] Audit `space_entries.md` for shape/measurement overlap
- 8. [x] Audit `verbs_entries.md` for duplicate specialist ownership
- 9. [x] Audit `mathematical_concepts_entries.md` for concept-only scope
- 10. [x] Audit `mathematical_problems_entries.md` for Level 1 register and grounded prerequisites
- 11. [x] Audit `body_parts_entries.md` for anatomy vs body-state / health drift
- 12. [x] Review `foods_vegetables_entries.md` as the first non-trunk cleanup file
- 13. [x] Run a corpus-wide contrast and dependency cleanup pass
- 14. [x] Resolve the concrete cleanup issues identified by Step 13's corpus-wide contrast and dependency pass
- 15. [x] Reconcile documentation after the gap-filling batch
- 16. [x] Backfill the phase 1-5 curriculum with foundational high-frequency terms that the wiki repeatedly relies on but the curriculum does not yet teach explicitly
- 17. [x] Build a candidate triplet list for Story Layer 1 after Wiki Level 1
- 18. [x] Write a Story Layer rules document after the triplet list is ready
- 19. [x] Document and follow the alternating expansion cadence: Wiki Level 1 → Stories 1 → Wiki Level 2 → Stories 2 → later wiki/story pairs
- 20. [x] Complete the Phase 6 bridge manifest and first file-order plan for Gemini CLI weekend work
- 21. [x] Draft the first Phase 6 bridge curriculum batch in repo-native format and audit it for vocabulary leakage
- 22. [x] Update story-generation infrastructure so dialogue enters in the staged progression instead of collapsing too early into quoted speech
- 23. [x] Pause the hourly wiki implementation cron while Level 2 planning replaces the old queue
- 24. [x] Run a file-level Level 2 expansion assessment before creating the real Level 2 batch
- 25. [x] Filter the dedicated Wiki Level 2 queue so it only includes files that actually justify expansion
- 26. [x] Create scaffold files for the approved Level 2 article batch
- 27. [x] Build an entry-level expansion index so file-level queue runs do not hide per-entry decisions
- 28. [x] Review the Story Layer 1 / connective-tissue gate before actual Level 2 writing begins
- 29. [x] Continue the Level 2 queue from `wiki_level2_queue.md`, one file container at a time
- 30. [x] Add missing law/safety role anchors: `police` and `police officer`
- 31. [x] Review, clean up, and selectively rewrite the first `training_data/triplet_stories/` Tier 1 batch after the current higher-priority queue is finished, **one file at a time**
- 32. [x] Expand `training_data/triplet_stories/story_tier_specs.md` so it also defines Tier 3 and Tier 4 shape/goals before any Tier 3 or Tier 4 batch work starts
- 33. [x] Create the Tier 2 story batch from the cleaned Tier 1 files, **one file at a time**
- 34. [x] Set up the canonical Tier 3 queue/review files inside the existing `training_data/triplet_stories/tier_3/` folder before Tier 3 drafting starts
- 35. [x] Create the Tier 3 story batch from the completed Tier 2 files, **one file at a time**
- 36. [x] Set up the canonical Tier 4 queue/review files inside the existing `training_data/triplet_stories/tier_4/` folder before Tier 4 drafting starts
- 37. [x] Create the Tier 4 story batch from the completed Tier 3 files, **one file at a time**
- 38. [x] Create a canonical uncovered-word routing file for concepts still not covered across Phase 1–6 / bridge / wiki / story layers
- 39. [x] Build the uncovered-word routing file in small audited batches instead of one giant pass
- 40. [x] Run the post-Wiki-Level-2 quality pass on the Phase 6 bridge files, one file at a time
- 41. [x] Run the post-Wiki-Level-2 quality pass on Story Tier 1, one file at a time
- 42. [x] Run the post-Wiki-Level-2 quality pass on the dedicated Wiki Level 2 batch, one file at a time
- 43. [x] Run the post-Wiki-Level-2 quality pass on Story Tier 2, one file at a time
- 44. [x] Only after Tasks 40–43 are complete, open the Wiki Level 3 planning/review gate

### training_data/wiki/wiki_level2_post_review_queue.md
- 1. [x] `emotions_entries.md`
- 2. [x] `communication_acts_and_language_entries.md`
- 3. [x] `friends_and_peer_interactions_entries.md`
- 4. [x] `conflict_resolution_and_relationship_repair_entries.md`
- 5. [x] `school_life_and_learning_entries.md`
- 6. [x] `play_games_and_sports_entries.md`
- 7. [x] `community_places_and_services_entries.md`
- 8. [x] `technology_and_digital_media_entries.md`
- 9. [x] `health_and_wellness_entries.md`
- 10. [x] `storytelling_and_narrative_structure_entries.md`
- 11. [x] `perspective_taking_and_theory_of_mind_entries.md`
- 12. [x] `evidence_and_justification_entries.md`

### training_data/wiki/wiki_level2_queue.md
- 1. [x] `emotions_entries.md`
- 2. [x] `communication_acts_and_language_entries.md`
- 3. [x] `friends_and_peer_interactions_entries.md`
- 6. [x] `play_games_and_sports_entries.md`
- 8. [x] `technology_and_digital_media_entries.md`
- 9. [x] `health_and_wellness_entries.md`
- 10. [x] `storytelling_and_narrative_structure_entries.md`
- 11. [x] `perspective_taking_and_theory_of_mind_entries.md`
- 12. [x] `evidence_and_justification_entries.md`
- 4. [x] `conflict_resolution_and_relationship_repair_entries.md`
- 5. [x] `school_life_and_learning_entries.md`
- 7. [x] `community_places_and_services_entries.md`

### Wiki Level 2 dependency-pass closures
- [x] `evidence_and_justification_entries.md` — dependency pass completed 2026-04-25: 4/5 split retained; metadata-only completion; dependencies verified against logic, emotions, uncertainty_and_guessing, communication_acts_and_language, play_games_and_sports, school_life_and_learning, plants_and_nature, weather_and_celestial, natural_life_cycles_and_processes, foods_and_drinks, safety_signs_and_symbols, people_roles, sensory_experiences, and abstract_operators anchors; no article-body changes needed.
- [x] `conflict_resolution_and_relationship_repair_entries.md` — dependency pass completed 2026-04-25: 4/3 split retained; metadata-only completion; dependencies verified against emotions, friends/peer, agreement/disagreement, accidents/mistakes, safety_rules, play_games, manners, people_roles, and growth_life_stages anchors; no article-body changes needed.
- [x] `community_places_and_services_entries.md` — dependency pass completed 2026-04-25: 5/11 split retained; metadata-only completion; dependencies verified against professions, safety_rules_and_emergency_awareness, health_and_wellness, vehicles_transport, money_trade_and_shopping, places_and_landforms, home_rooms, foods_and_drinks, civic_responsibility, school_life_and_learning, and time anchors; no article-body changes needed.

## Archived legacy task/status docs

- `archive/start.md`
- `archive/history.md`
- `archive/todo.md`
- `archive/training_data/wiki/wiki_level2_queue.md`
- `archive/training_data/wiki/wiki_level2_post_review_queue.md`
- `archive/training_data/wiki/wiki_level3_planning_gate.md`
- `archive/training_data/wiki/wiki_2_manifest.md`
- `archive/todo.md`
- `archive/training_data/triplet_stories/tier_1/post_level2_review_queue.md`
- `archive/training_data/triplet_stories/tier_2/review_queue.md`
- `archive/training_data/triplet_stories/tier_2/post_level2_review_queue.md`
- `archive/training_data/triplet_stories/tier_3/review_queue.md`
- `archive/training_data/triplet_stories/tier_4/review_queue.md`
- `archive/training_data/phases/phase_6/review_queue.md`
