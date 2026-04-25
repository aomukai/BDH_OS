# TODO

This file is the **single source of truth for all new work** in this repository.

Rules:
- Add new work here, not in nested queue files.
- When a task is finished, **remove it from this file** and move it to `history.md`.
- Do not leave completed tasks checked here.
- If a task creates follow-up work, add the follow-up tasks here immediately in the right stage.
- Legacy planning/status docs were moved to `archive/`.

## Where we are now

- **Phase 1–5 curriculum:** foundational corpus exists; later backfill work remains after newer wiki/story concepts are consolidated.
- **Phase 6 bridge:** drafted and post-Level-2 quality-passed; treated as stable.
- **Wiki Level 1:** stable base corpus; no active Level 1 expansion queue.
- **Wiki Level 2:** 12 Level 2 article files exist and passed quality review; 3 dependency-pass closures were completed after the root-todo migration, and 1 dependency-pass task still remains.
- **Story Tier 1:** `school_and_learning.md` and `play_and_games.md` have been audited/repaired; the rest of the Tier 1 corpus still needs audit work. Stored-file conversion into repeated `[user]` / `[assistant]` pairs is only partially done.
- **Story Tier 2:** `school_and_learning.md` exists and passed quality review; the other 9 domain files still need creation.
- **Story Tier 3:** `school_and_learning.md` exists as a vertical slice, but corpus-wide Tier 3 creation/review has not started.
- **Story Tier 4:** `school_and_learning.md` exists as a vertical slice, but corpus-wide Tier 4 creation/review has not started.

## Active queue

### 1. Close out remaining Wiki Level 2 dependency-pass work
- [ ] Finish the dependency pass for `training_data/wiki/wiki_1/evidence_and_justification_entries.md`

### 2. Check Story Tier 1
- [ ] Audit and repair `training_data/triplet_stories/tier_1/people_and_relationships.md` against the Tier 1 spec
- [ ] Audit and repair `training_data/triplet_stories/tier_1/home_and_daily_life.md` against the Tier 1 spec
- [ ] Audit and repair `training_data/triplet_stories/tier_1/weather_and_seasons.md` against the Tier 1 spec
- [ ] Audit and repair `training_data/triplet_stories/tier_1/animals_and_nature.md` against the Tier 1 spec
- [ ] Audit and repair `training_data/triplet_stories/tier_1/body_and_health.md` against the Tier 1 spec
- [ ] Audit and repair `training_data/triplet_stories/tier_1/food_and_meals.md` against the Tier 1 spec
- [ ] Audit and repair `training_data/triplet_stories/tier_1/tools_and_making.md` against the Tier 1 spec
- [ ] Audit and repair `training_data/triplet_stories/tier_1/vehicles_and_travel.md` against the Tier 1 spec

### 3. Edit Story Tier 1 into repeated `[user]` / `[assistant]` training-pair format
- [ ] Convert `training_data/triplet_stories/tier_1/school_and_learning.md` into repeated `[user]` / `[assistant]` training pairs
- [ ] Convert `training_data/triplet_stories/tier_1/people_and_relationships.md` into repeated `[user]` / `[assistant]` training pairs
- [ ] Convert `training_data/triplet_stories/tier_1/home_and_daily_life.md` into repeated `[user]` / `[assistant]` training pairs
- [ ] Convert `training_data/triplet_stories/tier_1/weather_and_seasons.md` into repeated `[user]` / `[assistant]` training pairs
- [ ] Convert `training_data/triplet_stories/tier_1/animals_and_nature.md` into repeated `[user]` / `[assistant]` training pairs
- [ ] Convert `training_data/triplet_stories/tier_1/body_and_health.md` into repeated `[user]` / `[assistant]` training pairs
- [ ] Convert `training_data/triplet_stories/tier_1/food_and_meals.md` into repeated `[user]` / `[assistant]` training pairs
- [ ] Convert `training_data/triplet_stories/tier_1/tools_and_making.md` into repeated `[user]` / `[assistant]` training pairs
- [ ] Convert `training_data/triplet_stories/tier_1/vehicles_and_travel.md` into repeated `[user]` / `[assistant]` training pairs

### 4. Create Story Tier 2
- [ ] Create `training_data/triplet_stories/tier_2/play_and_games.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_2/people_and_relationships.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_2/home_and_daily_life.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_2/weather_and_seasons.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_2/animals_and_nature.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_2/body_and_health.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_2/food_and_meals.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_2/tools_and_making.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_2/vehicles_and_travel.md` in repeated `[user]` / `[assistant]` format

### 5. Check Story Tier 2
- [ ] Quality-check `training_data/triplet_stories/tier_2/play_and_games.md`
- [ ] Quality-check `training_data/triplet_stories/tier_2/people_and_relationships.md`
- [ ] Quality-check `training_data/triplet_stories/tier_2/home_and_daily_life.md`
- [ ] Quality-check `training_data/triplet_stories/tier_2/weather_and_seasons.md`
- [ ] Quality-check `training_data/triplet_stories/tier_2/animals_and_nature.md`
- [ ] Quality-check `training_data/triplet_stories/tier_2/body_and_health.md`
- [ ] Quality-check `training_data/triplet_stories/tier_2/food_and_meals.md`
- [ ] Quality-check `training_data/triplet_stories/tier_2/tools_and_making.md`
- [ ] Quality-check `training_data/triplet_stories/tier_2/vehicles_and_travel.md`

### 6. Create Wiki Level 3
- [ ] Reconfirm the Level 3 candidate set after Tier 2 completion and write the minimal Level 3 plan directly in `todo.md` notes or adjacent docs if needed
- [ ] Create the first eligible Wiki Level 3 article (currently expected to be `emotions_entries.md` unless the reassessment changes)

### 7. Check Wiki Level 3
- [ ] Quality-check the created Wiki Level 3 article(s)

### 8. Create Story Tier 3
- [ ] Create `training_data/triplet_stories/tier_3/play_and_games.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_3/people_and_relationships.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_3/home_and_daily_life.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_3/weather_and_seasons.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_3/animals_and_nature.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_3/body_and_health.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_3/food_and_meals.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_3/tools_and_making.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_3/vehicles_and_travel.md` in repeated `[user]` / `[assistant]` format

### 9. Check Story Tier 3
- [ ] Quality-check `training_data/triplet_stories/tier_3/school_and_learning.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/play_and_games.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/people_and_relationships.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/home_and_daily_life.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/weather_and_seasons.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/animals_and_nature.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/body_and_health.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/food_and_meals.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/tools_and_making.md`
- [ ] Quality-check `training_data/triplet_stories/tier_3/vehicles_and_travel.md`

### 10. Create Wiki Level 4
- [ ] Reconfirm the Level 4 candidate set after Wiki Level 3 and Story Tier 3 work and write the minimal Level 4 plan directly in `todo.md` notes or adjacent docs if needed
- [ ] Create the first eligible Wiki Level 4 article(s)

### 11. Check Wiki Level 4
- [ ] Quality-check the created Wiki Level 4 article(s)

### 12. Create Story Tier 4
- [ ] Create `training_data/triplet_stories/tier_4/play_and_games.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_4/people_and_relationships.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_4/home_and_daily_life.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_4/weather_and_seasons.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_4/animals_and_nature.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_4/body_and_health.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_4/food_and_meals.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_4/tools_and_making.md` in repeated `[user]` / `[assistant]` format
- [ ] Create `training_data/triplet_stories/tier_4/vehicles_and_travel.md` in repeated `[user]` / `[assistant]` format

### 13. Check Story Tier 4
- [ ] Quality-check `training_data/triplet_stories/tier_4/school_and_learning.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/play_and_games.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/people_and_relationships.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/home_and_daily_life.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/weather_and_seasons.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/animals_and_nature.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/body_and_health.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/food_and_meals.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/tools_and_making.md`
- [ ] Quality-check `training_data/triplet_stories/tier_4/vehicles_and_travel.md`

### 14. Concepts ledger and curriculum backfill
- [ ] Build `training_data/wiki/wiki_and_story_introduced_concepts.md`
- [ ] Turn the introduced-concepts list into a bounded Phase 1–5 backfill plan
- [ ] Apply the first bounded Phase 1–5 curriculum backfill batch from that plan
- [ ] Update `training_data/phases/dependency_graph.json` after all planned backfill batches are complete

Note: once the backfill plan exists, add any additional curriculum-batch tasks here before starting them.
