We are continuing the Level 1 wiki training data build.

Read these first for current context:

* `AGENTS.md` — repo-wide rules and constraints
* `README.md` — project overview and runtime status
* `docs/bdh_cognitive_os_design.md` — architecture reference
* `training_data/wiki/CORPUS_STATUS.md` — current wiki corpus state
* `training_data/wiki/wiki_category_backlog.md` — strategic category backlog
* `training_data/wiki/wiki_implementation_todo.md` — practical next-step queue
* `training_data/phase 1 to 5/rewritten/missing_curriculum_terms.md` — wiki-to-curriculum anchor gaps

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

Recent implementation batches completed:

* `wants_needs_and_preferences_entries.md`
* `greetings_and_social_salutations_entries.md`
* `waiting_and_patience_entries.md`
* `containers_and_capacity_entries.md`
* `communication_acts_and_language_entries.md`
* `agreement_and_disagreement_entries.md`
* `ownership_and_sharing_entries.md`
* `friends_and_peer_interactions_entries.md`
* `personal_identity_and_self_description_entries.md`
* `manners_politeness_and_social_etiquette_entries.md`
* `play_games_and_sports_entries.md`
* `art_and_creative_expression_entries.md`
* `hobbies_and_interests_entries.md`
* `safety_rules_and_emergency_awareness_entries.md`
* `classroom_objects_and_school_tools_entries.md`
* `location_and_direction_in_action_entries.md`
* `animal_care_and_pet_keeping_entries.md`
* `lost_and_found_misplacing_objects_entries.md`
* `uncertainty_and_guessing_entries.md`
* `sleep_and_rest_entries.md`
* `holidays_and_celebrations_entries.md`
* `conflict_resolution_and_relationship_repair_entries.md`
* `boundaries_and_consent_entries.md`
* `seasonal_activities_entries.md`

Important boundary decisions from this batch:

* `Storytelling and Narrative Structure` owns sequencing language, not plot-role vocabulary
* `Imagination and Pretend Play` owns pretend-play language, not general art/storytelling
* `Community Places and Services` owns public-use places and service functions, not `school` or `park`
* `Cooking and Food Preparation` owns process language, not kitchen tools or food definitions
* `Construction and Material Transformations` owns maker/change verbs, while `STEM_entries.md` still owns general science-state verbs such as `melt`, `freeze`, `boil`, `break`, and `fix`
* Complex-emotion additions should extend `emotions_entries.md`, not create a duplicate emotion file
* `Wants, Needs, and Preferences` owns self-expression like `I want`, `I need`, `I like`, not body-state signals or pure logic
* `Greetings and Social Salutations` owns hello/goodbye language, not manners formulas like `please` and `thank you`
* `Waiting and Patience` owns queueing and delay language, while the base verb `wait` can still live in broader verb coverage
* `Communication Acts and Language` owns conversation mechanics, while `Agreement and Disagreement` owns alignment and refusal responses
* `Ownership and Sharing`, `Friends and Peer Interactions`, and `Conflict Resolution and Relationship Repair` are separate social layers and should not collapse into one catch-all file
* `Boundaries and Consent` owns refusal, limits, and personal-space language and should stay distinct from politeness or conflict-repair language

Current workflow:

1. Check backlog and corpus status first
2. Check existing canonical homes for overlap
3. Salvage only the usable concepts
4. Rewrite into canonical wiki files
5. Run a quick contrast / dependency pass
6. Batch doc updates after a small group of changes

Current corpus snapshot:

* `88` backlog categories total
* `36` `COVERED`
* `18` `PARTIAL`
* `34` `MISSING`

Current task:
Next clean authoring targets:

* `Data, Charts, and Graphs`
* `Material Composition`
* `Animal Habitats and Homes`
* `Food Groups and Nutrition`
* `Levels of Intensity and Gradation`

Goal:

* Keep expanding missing middle-layer daily-life categories without blurring concept ownership
* Continue using `wiki_category_backlog.md`, `wiki_implementation_todo.md`, and `CORPUS_STATUS.md` as the live source of truth
* Do another contrast / dependency cleanup pass after the next batch rather than trying to perfect every file immediately
