# Tier 2 Story Queue

Canonical one-file-at-a-time creation queue for `training_data/triplet_stories/tier_2/`.

Purpose:
- create a Tier 2 version of each Tier 1 domain file
- keep the work scoped to one domain file per run
- preserve the same domain order used in the Tier 1 review queue unless a human reprioritizes it

Use this file together with:
- `training_data/triplet_stories/story_tier_specs.md`
- `training_data/wiki/story_layer_rules.md`
- `training_data/phase_6_bridge/story_dialogue_progression.md`
- `training_data/wiki/story_triplet_candidates.md`
- `training_data/triplet_stories/review_queue.md`
- `training_data/triplet_stories/character_registry.md`

## Tier 2 requirements summary

Each Tier 2 file should:
1. follow the Tier 2 shape/goals in `training_data/triplet_stories/story_tier_specs.md`
2. cover the same domain as the matching Tier 1 file
3. keep stories grounded in Phase 1–5 + wiki + bridge-approved vocabulary only
4. move from very simple event framing to slightly richer contextual narrative
5. use 8–15 words per sentence unless a later canonical spec update says otherwise
6. use 12 sentences per story
7. allow `and`
8. allow `then` for temporal sequence
9. allow at most one simple `because` per story
10. keep dialogue, if any, clear and sparing; quoted dialogue with explicit speaker tags is allowed when useful but should not become the default pattern
11. avoid complex conditionals and abstract reasoning drift
12. introduce named characters where useful (for example `a boy named Timmy`) instead of leaving all human roles generic
13. when a Tier 2 story assigns a recurring name, record it in `training_data/triplet_stories/character_registry.md`
14. reuse the same named character in the matching Tier 3 and Tier 4 story thread unless a human explicitly changes the plan
15. store every story as a repeated `[user]` / `[Ninereeds]` training pair, not as table rows or markdown story headings

## Canonical creation order

1. [x] `school_and_learning.md`
2. [ ] `play_and_games.md`
3. [ ] `people_and_relationships.md`
4. [ ] `home_and_daily_life.md`
5. [ ] `weather_and_seasons.md`
6. [ ] `animals_and_nature.md`
7. [ ] `body_and_health.md`
8. [ ] `food_and_meals.md`
9. [ ] `tools_and_making.md`
10. [ ] `vehicles_and_travel.md`
