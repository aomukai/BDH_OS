# Triplet Stories Review Queue

Canonical one-file-at-a-time review queue for the first `training_data/triplet_stories/tier_1/` batch.

Purpose:
- prevent the story cleanup pass from becoming a 200-story all-at-once rewrite
- let Gemini CLI work one domain file at a time
- keep review, cleanup, rewrite, and verification scoped tightly enough to inspect carefully

Use this file together with:
- `training_data/triplet_stories/review_notes.md`
- `training_data/triplet_stories/story_tier_specs.md`
- `training_data/wiki/story_layer_rules.md`
- `training_data/phase_6_bridge/story_dialogue_progression.md`
- `training_data/wiki/02_wiki_implementation_todo.md`

## Review contract for each file

For the selected file only:
1. read the whole domain file
2. compare it against `review_notes.md`
3. compare it against `story_tier_specs.md`
4. check sentence-count consistency
5. check sentence simplicity and child-level register
6. check whether the stories are concrete mini-scenes rather than slogans or object-descriptions
7. check triplet visibility and support-word integration
8. check Tier 1 pronoun-introduction behavior against the Tier 1 spec
9. check that endings stay inside the scene and do not drift into morals, slogans, or mechanical add-ons
10. check dialogue staging if any interaction appears
11. rewrite only the selected file as needed
12. leave compact notes about what changed and whether more work is still needed

## Canonical review order

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

## Why this order

- `school_and_learning.md` has the strongest drift toward denser, more adult-sounding prose
- `play_and_games.md` has the clearest structural mismatch with the current Layer 1 pattern
- `people_and_relationships.md` most often drifts into moralized/generalized statements instead of concrete scenes
- `home_and_daily_life.md` and `weather_and_seasons.md` have moderate simplification needs
- the last five files look closer to the target and should be easier to verify/repair

## Completion standard

Treat a file as complete for this queue when:
- its stories fit one consistent Layer 1 structure
- its stories match the Tier 1 shape/goals in `story_tier_specs.md`
- sentences are simple enough for the intended level
- the triplet is clearly visible in each story
- endings stay grounded and scene-based
- no major adult-sounding drift remains
