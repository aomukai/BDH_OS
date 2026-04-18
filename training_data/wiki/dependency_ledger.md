# Wiki Corpus Dependency Ledger

Generated from `wiki_category_backlog.md` by auditing and normalizing all `Depends on:` items.

Purpose: Track where each dependency concept lives, whether it is grounded in the corpus, and flag gaps.

---

## Ledger Key

- **WIKI**: Dependency has a canonical wiki entry file
- **CURRICULUM**: Concept is grounded in phase 1-5 curriculum only (not wiki)
- **SPLIT**: Concept is split across multiple files; primary owner listed
- **MISSING**: No grounded anchor exists
- **ALIAS**: Listed term is an alias; see canonical entry

---

## Dependency Inventory

### Core Structural Domains

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| time | WIKI | time_entries.md | Anchors temporal vocabulary |
| time (morning/afternoon/evening/night) | WIKI | time_entries.md | Time-of-day subset |
| time (past/present/future) | WIKI | time_entries.md | Tense markers |
| time (day/week/month/year/season) | WIKI | time_entries.md | Calendar units |
| time (soon/later/not yet) | WIKI | time_entries.md | Relative time markers |
| space | WIKI | space_entries.md | Spatial relations |
| space (near/far/between) | WIKI | space_entries.md | Proximity subset |
| space (on/in/under/over/near/far/between) | WIKI | space_entries.md | Positional words |
| topology / spatial parts | WIKI | topology_parts_entries.md | Part-whole spatial |
| logic | WIKI | logic_entries.md | Reasoning vocabulary |
| logic (rule, goal) | WIKI | logic_entries.md | Normative concepts |
| logic (same/different) | WIKI | logic_entries.md | Identity/contrast |
| logic (cause/effect) | WIKI | logic_entries.md | Causal reasoning |
| logic (possible/impossible) | WIKI | logic_entries.md | Modality |
| logic (problem/solution) | WIKI | logic_entries.md | Problem-solving |
| logic (truth, fact/opinion) | WIKI | logic_entries.md | Epistemics |
| logic (all/some/none) | WIKI | logic_entries.md | Quantifiers |
| logic (part/whole, more/less) | WIKI | logic_entries.md | Mereology and comparison |
| logic (begin/middle/end) | SPLIT | logic_entries.md, storytelling_and_narrative_structure_entries.md | Overlap flagged |
| logic (order) | WIKI | logic_entries.md | Sequence concepts |
| logic (choice, decide) | WIKI | logic_entries.md | Decision vocabulary |
| logic (change) | WIKI | logic_entries.md | State-change concepts |
| logic (necessary) | WIKI | logic_entries.md | Modal necessity |

### Body and Health

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| body | WIKI | body_parts_entries.md | Body-part inventory |
| body (hand, tooth, hair, face) | WIKI | body_parts_entries.md | Specific parts |
| body (leg, arm, foot, hand) | WIKI | body_parts_entries.md | Limbs |
| body parts | WIKI | body_parts_entries.md | General anchor |
| body parts (head, belly, mouth, nose, skin, bone) | WIKI | body_parts_entries.md | Core parts |
| mouth | WIKI | body_parts_entries.md | Specific part |
| ear | WIKI | body_parts_entries.md | Specific part |
| nose | WIKI | body_parts_entries.md | Specific part |
| face | WIKI | body_parts_entries.md | Specific part |
| body states (hunger, thirst, tiredness) | WIKI | body_states_and_internal_cues_entries.md | Internal cues |
| feeling | WIKI | emotions_entries.md | Emotion anchor |
| feeling (happy/sad) | WIKI | emotions_entries.md | Core emotions |
| feeling (happy/sad/angry) | WIKI | emotions_entries.md | Core emotions |
| feeling (tired/happy/sad) | WIKI | emotions_entries.md | State + emotion |
| feeling (scared) | WIKI | emotions_entries.md | Fear |
| feeling (excited/frustrated/bored) | WIKI | emotions_entries.md | Complex emotions |
| feeling (happy/excited) | WIKI | emotions_entries.md | Positive states |
| feeling (proud/embarrassed/encouraged) | WIKI | emotions_entries.md | Self-conscious emotions |
| feeling (sorry/sad/embarrassed) | WIKI | emotions_entries.md | Regret cluster |
| feeling (excited/sad/guilty) | WIKI | emotions_entries.md | Mixed cluster |

### Objects and Physical World

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| home | WIKI | home_rooms_entries.md | Home as place |
| home objects | WIKI | home_objects_entries_part1.md | Household items |
| bed | WIKI | home_objects_entries_part1.md | Furniture |
| door | CURRICULUM | phase curriculum | Basic object |
| window | CURRICULUM | phase curriculum | Basic object |
| lamp | WIKI | home_objects_entries_part2.md | Lighting |
| table | CURRICULUM | phase curriculum | Furniture |
| chair | CURRICULUM | phase curriculum | Furniture |
| broom | WIKI | tools_and_kitchenware_entries.md | Cleaning tool |
| bucket | WIKI | containers_and_capacity_entries.md | Container |
| cup/plate/bowl | WIKI | tools_and_kitchenware_entries.md | Tableware |
| spoon | WIKI | tools_and_kitchenware_entries.md | Utensil |
| pot | WIKI | tools_and_kitchenware_entries.md | Cookware |
| book | WIKI | school_life_and_learning_entries.md | Reading material |
| paper | WIKI | school_life_and_learning_entries.md | Writing material |
| crayon | WIKI | school_life_and_learning_entries.md | Art supply |
| pencil | WIKI | school_life_and_learning_entries.md | Writing tool |
| pen | WIKI | school_life_and_learning_entries.md | Writing tool |
| scissors | WIKI | classroom_objects_and_school_tools_entries.md | Cutting tool |
| stick | CURRICULUM | phase curriculum | Basic object |
| block | CURRICULUM | phase curriculum | Building material |
| ball | CURRICULUM | phase curriculum | Toy/sport |
| doll | CURRICULUM | phase curriculum | Toy |
| rope | CURRICULUM | phase curriculum | Binding/play |
| sandbox | CURRICULUM | phase curriculum | Play structure |
| seesaw | CURRICULUM | phase curriculum | Play structure |
| button | WIKI | clothing_and_apparel_entries.md | Fastener |
| light | WIKI | simple_physics_energy_and_power_entries.md | Light source/phenomenon |
| candle | WIKI | holidays_and_celebrations_entries.md | Light/celebration |
| objects | ALIAS | various | Refers to general object files |

### Tools and Construction

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| tools | WIKI | tools_and_kitchenware_entries.md | General tools |
| tools and kitchenware | WIKI | tools_and_kitchenware_entries.md | Combined domain |
| hammer | WIKI | tools_and_kitchenware_entries.md | Hand tool |
| screw | WIKI | tools_and_kitchenware_entries.md | Fastener |
| wheel | WIKI | machines_and_simple_mechanisms_entries.md | Simple machine |
| lever | WIKI | machines_and_simple_mechanisms_entries.md | Simple machine |
| hook | CURRICULUM | phase curriculum | Basic hardware |
| brick | CURRICULUM | phase curriculum | Building material |
| ice | WIKI | weather_and_celestial_entries.md | Frozen water |
| water | WIKI | foods_and_drinks_entries.md | Liquid |
| wood | WIKI | material_composition_entries.md | Material |
| stone | WIKI | material_composition_entries.md | Material |
| fire | CURRICULUM | phase curriculum | Combustion |

### Food and Drink

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| food and drink | WIKI | foods_and_drinks_entries.md | General food |
| foods and drinks | WIKI | foods_and_drinks_entries.md | Alias |
| food (water, soup) | WIKI | foods_and_drinks_entries.md | Liquids |
| food (cake, cookie) | WIKI | foods_and_drinks_entries.md | Sweets |
| apple | WIKI | foods_fruits_entries.md | Fruit |
| banana | WIKI | foods_fruits_entries.md | Fruit |
| bread | WIKI | foods_and_drinks_entries.md | Staple |
| milk | WIKI | foods_and_drinks_entries.md | Dairy |
| egg | WIKI | foods_and_drinks_entries.md | Protein |
| sugar | WIKI | foods_and_drinks_entries.md | Sweetener |
| honey | CURRICULUM | phase curriculum | Sweet/bee product |

### Animals

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| animals | WIKI | animals_mammals_entries.md | General anchor |
| animals (mammals, birds, fish/sea) | WIKI | animals_mammals_entries.md, animals_birds_entries.md, animals_fish_entries.md | Split across files |
| animals (mammals, birds, insects, fish/sea, reptiles) | WIKI | Multiple animal files | Full animal corpus |
| dog | WIKI | animals_mammals_entries.md | Mammal |
| cat | WIKI | animals_mammals_entries.md | Mammal |
| fish | WIKI | animals_fish_entries.md | Aquatic |
| bird | WIKI | animals_birds_entries.md | Avian |
| butterfly | WIKI | animals_insects_arthropods_entries.md | Insect |
| frog | WIKI | animals_reptiles_amphibians_entries.md | Amphibian |

### Plants and Nature

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| plants and nature | WIKI | plants_and_nature_entries.md | Botany |
| tree | WIKI | plants_and_nature_entries.md | Large plant |
| leaf | WIKI | plants_and_nature_entries.md | Plant part |

### Places and Geography

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| places | WIKI | places_and_landforms_entries.md | Geographic features |
| places and landforms | WIKI | places_and_landforms_entries.md | Full domain |
| road | WIKI | places_and_landforms_entries.md | Infrastructure |
| bridge | WIKI | places_and_landforms_entries.md | Infrastructure |
| river | WIKI | places_and_landforms_entries.md | Water feature |
| sea | WIKI | places_and_landforms_entries.md | Water body |
| field | WIKI | places_and_landforms_entries.md | Land type |
| hill | WIKI | places_and_landforms_entries.md | Landform |
| farm | WIKI | places_and_landforms_entries.md | Agricultural |

### Weather and Celestial

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| weather and seasons | WIKI | weather_and_celestial_entries.md | Weather domain |
| sun | WIKI | weather_and_celestial_entries.md | Star |
| moon | WIKI | weather_and_celestial_entries.md | Satellite |
| star | WIKI | weather_and_celestial_entries.md | Celestial |
| rain | WIKI | weather_and_celestial_entries.md | Precipitation |
| snow | WIKI | weather_and_celestial_entries.md | Precipitation |
| wind | WIKI | weather_and_celestial_entries.md | Air movement |
| night | WIKI | time_entries.md | Time of day |

### People and Relationships

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| family | WIKI | people_roles_entries.md | Family unit |
| family relationships | WIKI | people_roles_entries.md | Kinship |
| family roles | WIKI | people_roles_entries.md | Family members |
| friend | WIKI | people_roles_entries.md | Relationship |
| person | WIKI | people_roles_entries.md | Human being |
| people and family roles | WIKI | people_roles_entries.md | Combined domain |

### Numbers and Math

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| number (0-10) | WIKI | mathematical_concepts_entries.md | Core numbers |
| counting | WIKI | mathematical_concepts_entries.md | Number skill |
| addition/subtraction | WIKI | mathematical_concepts_entries.md | Operations |
| size | WIKI | measurement_and_comparison_entries.md | Dimension |
| size (more/less) | WIKI | measurement_and_comparison_entries.md | Comparison |
| shape | WIKI | mathematical_concepts_entries.md | Geometry |

### STEM and Science

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| STEM concepts | WIKI | STEM_entries.md | Bridge file |
| STEM concepts (forces, motion, temperature) | WIKI | STEM_entries.md | Physics subset |
| STEM concepts (states of matter) | WIKI | STEM_entries.md | Chemistry |
| STEM concepts (senses) | WIKI | STEM_entries.md | Biology |
| STEM concepts (states of matter, properties) | WIKI | STEM_entries.md | Material science |

### Clothing

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| clothing | WIKI | clothing_and_apparel_entries.md | Garments |
| clothing (shirt, pants, shoe, sock) | WIKI | clothing_and_apparel_entries.md | Basic items |
| clothing (shirt, coat, boot) | WIKI | clothing_and_apparel_entries.md | Seasonal wear |
| shirt | WIKI | clothing_and_apparel_entries.md | Upper garment |

### Vehicles and Transport

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| vehicles and transport | WIKI | vehicles_transport_entries.md | Transportation |
| car | WIKI | vehicles_transport_entries.md | Vehicle |
| bus | WIKI | vehicles_transport_entries.md | Public transport |

### Verbs and Actions

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| verbs | WIKI | verbs_entries.md | Action words |
| verbs (give, take, hold, make) | WIKI | verbs_entries.md | Core actions |
| verbs (give, take, hold, move) | WIKI | verbs_entries.md | Core actions |
| verbs (give/take/hold/drop) | WIKI | verbs_entries.md | Manipulation |
| verbs (drop/break/fall) | WIKI | verbs_entries.md | Accident verbs |
| verbs (make, hold) | WIKI | verbs_entries.md | Creation/grasp |

### Color and Appearance

| Dependency | Status | Canonical Home | Notes |
|------------|--------|----------------|-------|
| colour | WIKI | colors_entries.md | Color vocabulary |
| color | ALIAS | colors_entries.md | US spelling |
| shape | WIKI | mathematical_concepts_entries.md | Geometry |

---

## Backlog Category Dependencies (Resolved)

The following categories from `wiki_category_backlog.md` previously marked dependencies as `(backlog)`. All have been resolved against current wiki files:

| Old Backlog Reference | Resolution | Current File |
|-----------------------|------------|--------------|
| daily routines (backlog) | COVERED | daily_routines_and_self_care_entries.md |
| school life and learning (backlog) | COVERED | school_life_and_learning_entries.md |
| manners, politeness (backlog) | COVERED | manners_politeness_and_social_etiquette_entries.md |
| safety, rules (backlog) | COVERED | safety_rules_and_emergency_awareness_entries.md |
| play, games, sports (backlog) | COVERED | play_games_and_sports_entries.md |
| communication acts (backlog) | COVERED | communication_acts_and_language_entries.md |
| friends and peer interactions (backlog) | COVERED | friends_and_peer_interactions_entries.md |
| art and creative expression (backlog) | COVERED | art_and_creative_expression_entries.md |
| imagination and pretend play (backlog) | COVERED | imagination_and_pretend_play_entries.md |
| ownership and sharing (backlog) | COVERED | ownership_and_sharing_entries.md |
| wants, needs, preferences (backlog) | COVERED | wants_needs_and_preferences_entries.md |
| hobbies and interests (backlog) | COVERED | hobbies_and_interests_entries.md |
| greetings and social salutations (backlog) | COVERED | greetings_and_social_salutations_entries.md |
| personal identity (backlog) | COVERED | personal_identity_and_self_description_entries.md |
| clothing and apparel (backlog) | COVERED | clothing_and_apparel_entries.md |
| states of being (backlog) | COVERED | states_of_being_and_condition_entries.md |
| animal care and pet keeping (backlog) | COVERED | animal_care_and_pet_keeping_entries.md |
| safety signs and symbols (backlog) | COVERED | safety_signs_and_symbols_entries.md |
| classroom objects (backlog) | COVERED | classroom_objects_and_school_tools_entries.md |
| directions and navigation (backlog) | COVERED | directions_and_navigation_entries.md |
| location and direction in action (backlog) | COVERED | location_and_direction_in_action_entries.md |
| agreement and disagreement (backlog) | COVERED | agreement_and_disagreement_entries.md |
| uncertainty and guessing (backlog) | COVERED | uncertainty_and_guessing_entries.md |
| lost and found (backlog) | COVERED | lost_and_found_misplacing_objects_entries.md |
| waiting and patience (backlog) | COVERED | waiting_and_patience_entries.md |
| containers and capacity (backlog) | COVERED | containers_and_capacity_entries.md |
| body states and internal cues (backlog) | COVERED | body_states_and_internal_cues_entries.md |
| holidays and celebrations (backlog) | COVERED | holidays_and_celebrations_entries.md |
| storytelling and narrative structure (backlog) | COVERED | storytelling_and_narrative_structure_entries.md |
| chores and home responsibilities (backlog) | COVERED | chores_and_home_responsibilities_entries.md |
| sleep and rest (backlog) | COVERED | sleep_and_rest_entries.md |
| conflict resolution (backlog) | COVERED | conflict_resolution_and_relationship_repair_entries.md |
| boundaries and consent (backlog) | COVERED | boundaries_and_consent_entries.md |
| seasonal activities (backlog) | COVERED | seasonal_activities_entries.md |
| data, charts, graphs (backlog) | COVERED | data_charts_and_graphs_entries.md |
| material composition (backlog) | COVERED | material_composition_entries.md |
| simple physics (backlog) | COVERED | simple_physics_energy_and_power_entries.md |
| animal habitats (backlog) | COVERED | animal_habitats_and_homes_entries.md |
| levels of intensity (backlog) | COVERED | levels_of_intensity_and_gradation_entries.md |
| food groups and nutrition (backlog) | COVERED | food_groups_and_nutrition_entries.md |
| musical instruments (backlog) | COVERED | musical_instruments_entries.md |
| shadow and light (backlog) | COVERED | shadow_and_light_phenomena_entries.md |
| garden and planting (backlog) | COVERED | garden_and_planting_basics_entries.md |
| group roles (backlog) | COVERED | group_roles_and_participation_entries.md |
| evidence and justification (backlog) | COVERED | evidence_and_justification_entries.md |
| categories and grouping (backlog) | COVERED | categories_and_grouping_entries.md |
| exceptions and qualifications (backlog) | COVERED | exceptions_and_qualifications_entries.md |
| intentions and plans (backlog) | COVERED | intentions_and_plans_in_action_entries.md |
| accidents and mistakes (backlog) | COVERED | accidents_and_mistakes_entries.md |
| smells and tastes (backlog) | COVERED | smells_and_tastes_entries.md |
| collections and collecting (backlog) | COVERED | collections_and_collecting_entries.md |
| sibling relationships (backlog) | COVERED | sibling_relationships_and_dynamics_entries.md |
| degrees of truth (backlog) | COVERED | degrees_of_truth_entries.md |
| health and wellness (backlog) | COVERED | health_and_wellness_entries.md |
| emotions beyond basic states (backlog) | COVERED | emotions_entries.md |
| measurement and comparison (backlog) | COVERED | measurement_and_comparison_entries.md |
| natural life cycles (backlog) | COVERED | natural_life_cycles_and_processes_entries.md |
| construction and material transformations (backlog) | COVERED | construction_and_material_transformations_entries.md |
| cooking and food preparation (backlog) | COVERED | cooking_and_food_preparation_entries.md |
| community places and services (backlog) | COVERED | community_places_and_services_entries.md |
| environmental care (backlog) | COVERED | environmental_care_and_stewardship_entries.md |
| fractions and sharing quantities (backlog) | COVERED | fractions_and_sharing_quantities_entries.md |
| perspective-taking and theory of mind (backlog) | COVERED | perspective_taking_and_theory_of_mind_entries.md |
| humor and figurative language (backlog) | COVERED | humor_and_figurative_language_entries.md |
| inclusion, bullying, kindness (backlog) | COVERED | inclusion_bullying_and_kindness_entries.md |
| online safety and privacy (backlog) | COVERED | online_safety_and_privacy_entries.md |
| civic responsibility (backlog) | COVERED | civic_responsibility_and_community_rules_entries.md |
| learning, memory, metacognition (backlog) | COVERED | learning_memory_and_metacognition_entries.md |
| future planning and goals (backlog) | COVERED | future_planning_and_goals_entries.md |
| story roles and plot elements (backlog) | COVERED | story_roles_and_plot_elements_entries.md |
| social-emotional learning (backlog) | COVERED | social_emotional_learning_competencies_entries.md |
| secrets, surprises, promises (backlog) | COVERED | secrets_surprises_and_keeping_promises_entries.md |
| praise, criticism, feedback (backlog) | COVERED | praise_criticism_and_feedback_entries.md |
| opinions, persuasion, debate (backlog) | COVERED | opinions_persuasion_and_simple_debate_entries.md |
| numbers beyond 10 (backlog) | COVERED | numbers_beyond_10_and_large_number_talk_entries.md |
| machines and simple mechanisms (backlog) | COVERED | machines_and_simple_mechanisms_entries.md |
| growth and life stages (backlog) | COVERED | growth_and_life_stages_human_entries.md |
| sensory experiences (backlog) | COVERED | sensory_experiences_entries.md |

---

## Curriculum-Only Dependencies

These concepts appear in `Depends on:` lines but have no wiki anchor. They are grounded in phase 1-5 curriculum files only:

| Concept | Phase Anchor | Wiki Coverage Needed? |
|---------|--------------|----------------------|
| door | phase 1 | Low priority (basic object) |
| window | phase 1 | Low priority (basic object) |
| table | phase 1 | Low priority (basic furniture) |
| chair | phase 1 | Low priority (basic furniture) |
| stick | phase 1 | Low priority (basic object) |
| block | phase 1 | Low priority (toy/construction) |
| ball | phase 1 | Low priority (toy) |
| doll | phase 1 | Low priority (toy) |
| rope | phase 1 | Low priority (tool/play) |
| sandbox | phase 1 | Low priority (play structure) |
| seesaw | phase 1 | Low priority (play structure) |
| hook | phase 1 | Low priority (hardware) |
| brick | phase 1 | Low priority (building material) |
| fire | phase 1 | Medium priority (safety-relevant) |
| honey | phase 1 | Low priority (food item) |

---

## Identified Ownership Overlaps

These concepts appear in multiple files or have unclear primary ownership:

| Concept | Files Involved | Recommended Owner |
|---------|---------------|-------------------|
| begin/middle/end | logic_entries.md, storytelling_and_narrative_structure_entries.md | storytelling (narrative), logic (abstract sequence) |
| eat/drink/sleep/breathe | STEM_entries.md, verbs_entries.md | verbs (action), STEM (biological process) |
| see/hear/smell/taste/touch | STEM_entries.md, sensory_experiences_entries.md | sensory_experiences (descriptive), STEM (sense organs) |
| height | space_entries.md, measurement_and_comparison_entries.md | measurement_and_comparison_entries.md (DUPLICATE ANCHOR — remove from space) |
| width/depth | space_entries.md only | space_entries.md (no conflict — measurement has comparatives wider/narrower only) |
| center/edge/corner | space_entries.md only | space_entries.md (no conflict — math_concepts has shapes only) |
| full/empty | containers_and_capacity_entries.md, states_of_being_and_condition_entries.md | containers (container states), states (general adjectives) |
| wet/dry | STEM_entries.md, states_of_being_and_condition_entries.md | states (condition adjectives) |
| heavy/light | STEM_entries.md, measurement_and_comparison_entries.md | measurement (weight comparison) |
| awake/asleep | STEM_entries.md, states_of_being_and_condition_entries.md, sleep_and_rest_entries.md | sleep_and_rest (sleep context) |

---

## Summary Statistics

- **Total unique dependency concepts**: ~150
- **WIKI-grounded**: ~120
- **CURRICULUM-only**: ~15
- **MISSING**: 0 (all backlog references resolved)
- **Overlap hotspots**: 9

---

---

## Comprehension-Critical Missing or Weak Prerequisites

This section identifies concepts that many files depend on but are either missing anchors, have weak definitions, or need clarification. Priority is based on how many files depend on the concept and how central it is to understanding the corpus.

### Priority 1: High-impact conceptual gaps (many dependencies)

These concepts underpin much of the corpus and need strong anchors:

| Concept | Current Status | Impact | Recommendation |
|---------|----------------|--------|----------------|
| `person` | WIKI (people_roles_entries.md) | Very high — nearly all social files | Confirm anchor is clear and early in file |
| `thing` / `object` | No wiki anchor | Very high — implicit prerequisite | Consider adding to abstract_operators_entries.md as foundational anchor |
| `animal` | WIKI (animals_mammals_entries.md) | Very high — all animal files depend on it | Confirm anchor is stable |
| `place` | WIKI (places_and_landforms_entries.md) | High — geography and space files | Confirm anchor is clear |
| `idea` / `thought` | Weak — `thought` only in missing_curriculum_terms.md | Medium-high — logic, learning, communication | Add entry to logic_entries.md or consider curriculum placement |
| `word` | No wiki anchor | Medium-high — communication and language files | Add to communication_acts_and_language_entries.md |
| `sentence` | No wiki anchor | Medium — storytelling and communication files | Add to communication_acts_and_language_entries.md |

### Priority 2: Curriculum-only concepts that need verification

These are grounded in phase 1-5 curriculum only, not wiki. Verify they are solid enough for files that depend on them:

| Concept | Curriculum Anchor | Dependent Wiki Files | Risk Level |
|---------|-------------------|----------------------|------------|
| `fire` | phase 1 | safety, cooking, weather, STEM | Medium — safety-relevant |
| `door` | phase 1 | home rooms, daily routines | Low |
| `table` | phase 1 | meals, home objects, daily routines | Low |
| `ball` | phase 1 | play/games, sports | Low |
| `rope` | phase 1 | play/games, tools | Low |

Fire is the only curriculum-only concept with safety relevance — other basic objects are low-risk since the curriculum covers them well.

### Priority 3: Weak anchors within existing wiki files

These concepts have wiki entries but the entries may be too abstract or come too late in their files:

| Concept | Current File | Issue | Recommendation |
|---------|--------------|-------|----------------|
| `category` | abstract_operators_entries.md | Very abstract; may not teach classification well | Entry exists but `categories_and_grouping_entries.md` now provides clearer anchor |
| `past / present / future` | time_entries.md | Good coverage but also echoed in logic_entries.md | Overlap flagged; recommend time file owns temporal meanings |
| `begin / middle / end` | SPLIT: logic + storytelling | Overlap flagged in ledger | Recommend storytelling owns narrative sense; logic owns abstract sequence sense |
| `eat / drink / sleep` | SPLIT: STEM + verbs | STEM owns as biological process; verbs owns as action | Clarify in trunk audit that both usages are intentional |

### Priority 4: Structural language that may need strengthening

These concepts support comprehension across the corpus but are not missing — they just need to be checked during the trunk audit:

| Concept | File | Check During Trunk Audit |
|---------|------|--------------------------|
| `more / less` | logic_entries.md | Confirm these are grounded with concrete examples |
| `part / whole` | logic_entries.md | Strong coverage — confirm stays clear |
| `same / different` | logic_entries.md | Strong coverage — confirm stays clear |
| `why / because` | communication_acts_and_language_entries.md, evidence_and_justification_entries.md | Check that causal connectives are explicitly taught |
| `if / then` | logic_entries.md | Covered — confirm entry is child-accessible |

### Not comprehension-critical (low priority)

These curriculum-only items were flagged in the ledger but do not cause comprehension gaps:

- Basic objects: `stick`, `block`, `doll`, `sandbox`, `seesaw`, `hook`, `brick`
- These are well-covered in curriculum and are not heavily depended on by wiki files
- No wiki anchor is needed unless new files specifically require them

---

## Summary: Recommended Actions

1. **Add wiki anchors for:**
   - `thing` / `object` — foundational for "what is X?" structure
   - `word` and `sentence` — supports communication and story files
   - `idea` or `thought` — supports reasoning and reflection files

2. **Verify curriculum anchors for:**
   - `fire` — the only safety-relevant curriculum-only concept

3. **Resolve during trunk audit:**
   - begin/middle/end ownership (logic vs storytelling)
   - eat/drink/sleep ownership (STEM vs verbs)
   - past/present/future ownership (time vs logic)

4. **No action needed for:**
   - Basic curriculum objects (door, table, ball, etc.) — adequately grounded
   - ~15 curriculum-only items flagged in ledger — all low priority

---

## Documented Duplicate Anchors (Step 14 Cleanup)

The following duplicate anchors were reviewed during the Step 14 corpus cleanup pass and documented here for reference.

### Resolved High-Priority Duplicates

| Concept | Action Taken | Result |
|---------|--------------|--------|
| `height` | Removed from space_entries.md | measurement_and_comparison_entries.md is canonical owner |
| `lever` | Documented as intentional split | machines_and_simple_mechanisms_entries.md is primary (simple machine definition); tools_and_kitchenware_entries.md is secondary (practical tool context) |

### Contextually Acceptable School-Domain Duplicates

These duplicates appear in multiple files but serve different teaching contexts. No action needed — both entries are useful.

| Concept | Files | Rationale |
|---------|-------|-----------|
| `grade` | personal_identity_and_self_description_entries.md, school_life_and_learning_entries.md | Personal identity teaches grade as part of self-introduction; school_life teaches grade as part of school structure |
| `teacher` | school_life_and_learning_entries.md, professions_entries.md | School_life teaches teacher in classroom context; professions teaches teacher as a job/career |
| `paper` | material_composition_entries.md, school_life_and_learning_entries.md | Material_composition owns material-science definition; school_life introduces it in school context |

### Other Contextually Acceptable Duplicates (From Step 13 Audit)

| Concept | Files Involved | Rationale |
|---------|----------------|-----------|
| `light` | simple_physics_energy_and_power_entries.md, colors_entries.md, weather_and_celestial_entries.md | Different domains: physics, color, natural lighting |
| `ice` | STEM_entries.md, weather_and_celestial_entries.md | STEM owns state-of-matter; weather owns precipitation |
| `rainbow` | colors_entries.md, weather_and_celestial_entries.md | Colors owns color spectrum; weather owns natural phenomenon |
| `quarter` | fractions_and_sharing_quantities_entries.md, money_and_basic_economics_entries.md | Fractions owns numerical meaning; money owns coin meaning |
| `right` | directions_and_navigation_entries.md, logic_entries.md | Directions owns spatial direction; logic owns correctness |
| `full` | STEM_entries.md, meals_and_table_manners_entries.md | STEM owns container state; meals owns satiation sense |
| `ask`/`answer`/`whisper` | communication_acts_and_language_entries.md, verbs_entries.md | Communication owns speech acts; verbs owns action forms |
| `slide`/`roll` | machines_and_simple_mechanisms_entries.md, verbs_entries.md | Machines owns physics motion; verbs owns action forms |
| `boil`/`pour`/`mix` | STEM_entries.md, cooking_and_food_preparation_entries.md | STEM owns state-change science; cooking owns practical kitchen usage |
| `half` | fractions_and_sharing_quantities_entries.md, mathematical_concepts_entries.md | Fractions owns sharing context; math owns numerical definition |
| `paint` | art_and_creative_expression_entries.md, verbs_entries.md | Art owns material/activity; verbs owns action form |

### Remaining Low-Priority Overlaps (No Action Needed)

| Concept | Files | Notes |
|---------|-------|-------|
| `a lot` | levels_of_intensity_and_gradation_entries.md, numbers_beyond_10_and_large_number_talk_entries.md | Minor semantic overlap, functional as-is |
| `collar` | animal_care_and_pet_keeping_entries.md, clothing_and_apparel_entries.md | Pet collar vs shirt collar — naturally different |
| `responsibility` | chores_and_home_responsibilities_entries.md, civic_responsibility_and_community_rules_entries.md | Home chores vs civic duty — naturally different |
| `category` | abstract_operators_entries.md, categories_and_grouping_entries.md | Abstract concept vs practical grouping — both useful |
| `material` | abstract_operators_entries.md, material_composition_entries.md | Abstract vs concrete materials — acceptable |

---

## Next Steps

1. Review identified ownership overlaps during trunk audit (items 4-11 in todo list)
2. Confirm curriculum-only items are sufficiently grounded for comprehension
3. Use this ledger when adding new wiki content to avoid creating duplicate anchors
