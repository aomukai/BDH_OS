We are continuing the Level 1 wiki training data build.

Project structure:

* `training_data/wiki/` contains category-based concept files
* Each file defines one clean conceptual domain
* Files are later merged into a single Level 1 training corpus

Core design rules:

* One canonical home per concept whenever possible
* Avoid anchor duplication across categories
* Use simple child-facing Level 1 language
* Prefer concrete facts and clear contrasts
* Keep category ownership strict

Recent salvage batch completed:

* `storytelling_and_narrative_structure_entries.md`
* `imagination_and_pretend_play_entries.md`
* `chores_and_home_responsibilities_entries.md`
* `safety_signs_and_symbols_entries.md`
* `community_places_and_services_entries.md`
* `cooking_and_food_preparation_entries.md`
* `construction_and_material_transformations_entries.md`

Recent partial-category expansion completed:

* `emotions_entries.md` gained `frustration`, `confusion`, `nervousness`, `jealousy`, `embarrassment`, and `relief`

Important boundary decisions from this batch:

* `Storytelling and Narrative Structure` owns sequencing language, not plot-role vocabulary
* `Imagination and Pretend Play` owns pretend-play language, not general art/storytelling
* `Community Places and Services` owns public-use places and service functions, not `school` or `park`
* `Cooking and Food Preparation` owns process language, not kitchen tools or food definitions
* `Construction and Material Transformations` owns maker/change verbs, while `STEM_entries.md` still owns general science-state verbs such as `melt`, `freeze`, `boil`, `break`, and `fix`
* Complex-emotion additions should extend `emotions_entries.md`, not create a duplicate emotion file

Current workflow:

1. Check backlog and corpus status first
2. Check existing canonical homes for overlap
3. Salvage only the usable concepts
4. Rewrite into canonical wiki files
5. Run a quick contrast / dependency pass
6. Batch doc updates after a small group of changes

Current task:
Next clean authoring target: `Wants, Needs, and Preferences`

Goal:

* Bridge body signals and action language
* Support self-expression such as "I want", "I need", "I like"
* Keep clear separation from emotions, pure logic, and politeness categories
