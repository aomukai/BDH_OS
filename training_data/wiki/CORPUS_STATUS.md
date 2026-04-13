# Corpus Status

## What we're building

A Level 1 training corpus for the BDH (Baby Dragon Hatchling) language model.
Each entry follows this format:

```
[user]what is a X?
[assistant]5-6 simple sentences. Identity + 2-3 concrete facts + 1 contrast.
X is not Y.
```

**Target level:** simple child-facing language, roughly preschool to 1st grade in tone, with room to grow later. No jargon, no Latin taxonomy, no encyclopedic depth.
**Contrast rule:** Every entry ends with "X is not Y." Both X and Y must be defined somewhere in the corpus (no dangling contrasts).

---

## Files and their status

### Clean and aligned to current Level 1 target
These files are in good shape for the current manual-cleanup pass.

| File | Notes |
|---|---|
| abstract_operators_entries.md | Reduced to actual abstract/meta anchors: `category`, `feeling`, `material`, `size` |
| animals_birds_entries.md | Lowered register; simpler distinctions, less bird-book language |
| animals_fish_entries.md | Renamed from `animals_fish_sea_entries.md`; focused on water animals only |
| animals_insects_arthropods_entries.md | Reordered with `insect` and `arthropod` first; contrasts cleaned |
| animals_reptiles_amphibians_entries.md | Added `reptile`, `amphibian`, `toad`; simplified throughout |
| agreement_and_disagreement_entries.md | New response-and-alignment category; anchors `agreement`, `disagreement`, `yes`, `no`, `I agree`, `I disagree`, `me too`, `not me` |
| art_and_creative_expression_entries.md | New making-and-expression category; anchors `art`, `creativity`, `draw`, `paint`, `craft`, `decorate`, `erase`, `clay`, `collage` |
| animal_care_and_pet_keeping_entries.md | New pet-responsibility category; anchors `pet care`, `pet keeping`, `pet food`, `water bowl`, `leash`, `collar`, `litter box`, `grooming`, `vet` |
| boundaries_and_consent_entries.md | New personal-limits category; anchors `boundary`, `personal space`, `stop`, `not okay`, `my body`, `I don't want to`, `consent`, `you may not` |
| chores_and_home_responsibilities_entries.md | New home-task category; anchors `chore`, `responsibility`, `clean up`, `put something away`, `make the bed`, `set the table`, `sweep the floor`, `water plants`, `feed a pet`, `take out the trash`, `tidy up` |
| clothing_and_apparel_entries.md | Expanded category; now anchors `clothing`, `coat`, `jacket`, `shirt`, `hat`, `glove`, `mitten`, `pants`, `skirt`, `dress`, `sock`, `shoe`, `button`, `zipper` |
| communication_acts_and_language_entries.md | New conversation-mechanics category; anchors `communication`, `ask`, `answer`, `whisper`, `shout`, `explain`, `promise`, `what does that mean`, `can you say it again`, `I meant` |
| community_places_and_services_entries.md | New town-services category; anchors `community place`, `service`, `library`, `hospital`, `grocery store`, `fire station`, `police station`, `post office`, `museum`, `restaurant`, `bakery`, `bus stop` |
| conflict_resolution_and_relationship_repair_entries.md | New social-repair category; anchors `conflict resolution`, `compromise`, `forgive`, `apologize`, `let's try again`, `that's okay`, `how can we fix this` |
| construction_and_material_transformations_entries.md | New maker-change category; anchors `construction`, `repair`, `glue something`, `fold something`, `tear something`, `flatten something`, `mold something`, `shred something`, `crush something` |
| containers_and_capacity_entries.md | New container-usage category; anchors `container`, `bag`, `jar`, `bottle`, `basket`, `pocket`, `drawer`, `fit`, `spill`, `overflow`, `put it in` |
| cooking_and_food_preparation_entries.md | New cooking-process category; anchors `cooking`, `food preparation`, `recipe`, `ingredient`, `chop food`, `peel food`, `stir food`, `whisk`, `bake`, `simmer`, `season food`, `knead dough` |
| classroom_objects_and_school_tools_entries.md | New classroom-item category; anchors `school tool`, `ruler`, `eraser`, `glue`, `scissors`, `marker`, `whiteboard`, `glue stick`, `sharpener` |
| daily_routines_and_self_care_entries.md | New routine category; anchors `routine`, `wake up`, `get ready`, `get dressed`, `wash your hands`, `eat breakfast`, `go to school`, `pack a backpack`, `line up`, `go to bed`, `pajamas` |
| directions_and_navigation_entries.md | New route-and-direction category; anchors `left`, `right`, `up`, `down`, `forward`, `backward`, `turn`, `go straight`, `map`, `route`, `address` |
| foods_and_drinks_entries.md | Rewritten into simpler Level 1 voice; anchors reordered |
| friends_and_peer_interactions_entries.md | New peer-social category; anchors `friendship`, `classmate`, `teammate`, `play together`, `invite`, `argue`, `make up`, `playdate`, `be my friend` |
| growth_and_life_stages_human_entries.md | New human-development category; anchors `life stage`, `baby`, `toddler`, `child`, `teenager`, `adult`, `grown-up`, `grow up`, `when I was little` |
| greetings_and_social_salutations_entries.md | New conversation-opening category; anchors `greeting`, `hello`, `hi`, `good morning`, `good night`, `goodbye`, `see you later`, `nice to meet you`, `welcome` |
| health_and_wellness_entries.md | New wellness category; anchors `health`, `wellness`, `fever`, `cough`, `sore throat`, `headache`, `stomachache`, `cut`, `bruise`, `bandage`, `medicine`, `germ` |
| hobbies_and_interests_entries.md | New free-time preference category; anchors `hobby`, `interest`, `favorite thing to do`, `free time`, `collect`, `reading for fun`, `music as a hobby`, `building as a hobby` |
| holidays_and_celebrations_entries.md | New special-day category; anchors `holiday`, `celebration`, `party`, `gift`, `candle`, `special day`, `tradition`, `present` |
| home_objects_entries_part1.md | Clean enough for current pass; migrated `book` to school category |
| home_objects_entries_part2.md | Cleaned and reordered with `furniture` as anchor; clothing removed |
| home_objects_entries_part3.md | Cleaned; `paper` migrated to school category |
| imagination_and_pretend_play_entries.md | New pretend-play category; anchors `imagination`, `pretend`, `pretend play`, `make-believe`, `dress up`, `role play`, `imaginary friend`, `symbolic play`, `game of pretend` |
| logic_entries.md | Merged former `logic_core_entries.md` into this file; now the single canonical logic file |
| machines_and_simple_mechanisms_entries.md | New mechanism category; anchors `machine`, `simple machine`, `ramp`, `wheel`, `axle`, `gear`, `pulley`, `roll`, `slide` |
| meals_and_mealtime_talk_entries.md | New routine-and-talk category; anchors `meal`, `breakfast`, `lunch`, `dinner`, `snack`, `hungry`, `full`, `pass something`, `all done` |
| money_trade_and_shopping_entries.md | Expanded category; now anchors `money`, `coin`, `dollar`, `penny`, `nickel`, `dime`, `quarter`, `change`, `allowance`, `store`, `customer`, `shopkeeper`, `buy`, `sell`, `pay`, `cost`, `price`, `save`, `spend` |
| natural_life_cycles_and_processes_entries.md | New natural-process category; anchors `life cycle`, `plant growth`, `hatching`, `metamorphosis`, `pollination`, `hibernation`, `decomposition`, `water cycle`, `day and night pattern`, `season change` |
| numbers_beyond_10_and_large_number_talk_entries.md | New extended-number category; anchors `eleven`, `twelve`, `thirteen`, `twenty`, `one hundred`, `one thousand`, `a lot`, `about twenty`, `more than fifty` |
| opinions_persuasion_and_simple_debate_entries.md | New opinion-register category; anchors `opinion`, `I think`, `in my opinion`, `agree`, `disagree`, `persuasion`, `convince`, `reason in an argument`, `evidence`, `debate` |
| ownership_and_sharing_entries.md | New social-ownership category; anchors `ownership`, `mine`, `yours`, `borrow`, `return`, `sharing`, `can I use that`, `that's mine` |
| personal_identity_and_self_description_entries.md | New self-introduction category; anchors `identity`, `name`, `age`, `birthday`, `grade`, `I am`, `I live in`, `about me facts` |
| play_games_and_sports_entries.md | New group-play category; anchors `play`, `game`, `sport`, `team`, `score`, `win`, `lose`, `cheat`, `tag`, `hide and seek` |
| safety_rules_and_emergency_awareness_entries.md | New safety-and-help category; anchors `safety`, `danger`, `careful`, `emergency`, `trusted adult`, `call for help`, `look both ways`, `helmet`, `seatbelt`, `not safe` |
| seasonal_activities_entries.md | New season-behavior category; anchors `seasonal activities`, `what do people do in spring`, `what do people do in summer`, `what do people do in autumn`, `what do people do in winter`, `puddle jumping`, `picnic`, `harvest` |
| sleep_and_rest_entries.md | New bedtime-and-rest category; anchors `rest`, `sleepy`, `nap`, `blanket`, `pillow`, `dream`, `nightmare`, `time for bed`, `lullaby`, `night light` |
| lost_and_found_misplacing_objects_entries.md | New missing-object category; anchors `lost`, `found`, `where is it`, `I can't find it`, `have you seen my`, `search`, `lost and found`, `left it somewhere` |
| location_and_direction_in_action_entries.md | New action-direction phrase category; anchors `come here`, `go there`, `bring it to me`, `put it on the table`, `take it outside`, `move it over`, `set it down`, `point to it` |
| movement_and_physical_action_entries.md | New bridge category; anchors `movement`, `exercise`, `balance`, `stretch`, `kick`, `bounce`, `spin`, `dance` without duplicating the main verbs file |
| places_and_landforms_entries.md | Reordered for concept ownership; now canonical home for `forest`, `garden`, `meadow`, `orchard`, `hill` |
| plants_and_nature_entries.md | Early entries simplified; duplicate place concepts removed |
| school_life_and_learning_entries.md | New category; currently anchors `school`, `classroom`, `lesson`, `homework`, `book`, `paper`, `pencil`, `pen`, `crayon` |
| safety_signs_and_symbols_entries.md | New signs category; anchors `sign`, `symbol`, `stop sign`, `exit sign`, `danger sign`, `caution sign`, `no entry sign`, `pedestrian crossing sign`, `poison symbol`, `first aid symbol`, `slippery floor sign` |
| sensory_experiences_entries.md | New descriptive-sensory category; anchors `sound`, `loud`, `quiet`, `noisy`, `silent`, `bright`, `dim`, `sticky`, `sweet`, `sour`, `bang`, `squeak`, `roar`, `chirp`, `melody` |
| space_entries.md | Rewritten around spatial relations and simple spatial ideas; shape/geometry teaching stays in `mathematical_concepts_entries.md` |
| STEM_entries.md | Rewritten into simpler bridge language across matter, motion, change, life, and senses |
| states_of_being_and_condition_entries.md | New adjective-state category; anchors `condition`, `open`, `closed`, `on`, `off`, `clean`, `dirty`, `broken`, `fixed`, `asleep` |
| storytelling_and_narrative_structure_entries.md | New narrative-sequencing category; anchors `story`, `beginning`, `middle`, `end`, `first`, `next`, `then`, `before`, `after`, `finally`, `at the end` |
| time_entries.md | Rewritten into simpler child-facing time language; reduced abstract and philosophical phrasing |
| tools_and_kitchenware_entries.md | Cleaned and clarified; now includes `kitchenware` anchor |
| topology_parts_entries.md | Reworked into true part-whole entries (`neck of a bottle`, `rim of a cup`, etc.) |
| verbs_entries.md | 76 entries; duplicate `drive`/`sail` removed; major simplification pass completed |
| vehicles_transport_entries.md | Polished into the current Level 1 voice; now also anchors `transport` |
| waiting_and_patience_entries.md | New self-control category; anchors `waiting`, `patience`, `turn`, `not yet`, `a little longer`, `hurry up`, `almost ready`, `wait your turn`, `stand in line` |
| weather_and_celestial_entries.md | Rewritten into simple child-facing voice; `weather` and `wave` added |
| uncertainty_and_guessing_entries.md | New hedge-and-possibility category; anchors `uncertainty`, `maybe`, `probably`, `I guess`, `not sure`, `could be`, `might`, `I wonder` |
| wants_needs_and_preferences_entries.md | New self-expression category; anchors `want`, `need`, `preference`, `I want`, `I need`, `I like`, `I dislike`, `favorite`, `prefer` |

### Clean earlier / low concern
These looked solid before the current cleanup sprint and were not major problem files.

| File | Known issues |
|---|---|
| animals_mammals_entries.md | Strong overall; now includes `human`, `monkey`, `ape`, `chimp` |
| body_parts_entries.md | 20 entries, no current cleanup concerns |
| colors_entries.md | Color spectrum + light/dark |
| emotions_entries.md | Expanded emotion category; now also includes `frustration`, `confusion`, `nervousness`, `jealousy`, `embarrassment`, and `relief` |
| foods_fruits_entries.md | 21 entries including nuts cluster |
| home_rooms_entries.md | 5 entries, `room` moved to top as anchor |
| mathematical_concepts_entries.md | Number/shape/operation concepts + 1-10 word-to-symbol bridge + plus/minus/equals |
| measurement_and_comparison_entries.md | New measurement category; anchors `measurement`, `comparison`, `bigger`, `smaller`, `taller`, `shorter`, `heavier`, `lighter`, `length`, `height`, `weight`, `capacity`, `distance`, `estimate` |
| people_roles_entries.md | Family and social roles |
| professions_entries.md | 21 entries |

### Still worth a future pass
These are not blockers, but they may still want style cleanup, dependency review, or expansion later.

| File | Notes |
|---|---|
| foods_vegetables_entries.md | Not touched in the current cleanup sprint |
| mathematical_problems_entries.md | Still likely wants prose simplification pass |
| STEM_entries.md | May still overlap with weather/light/ice concepts and could use later ownership review |
| logic_entries.md | May still overlap with time concepts (`past`, `present`, `future`) |
| space_entries.md | May still overlap with mathematical shape vocabulary |

---

## Design principles

- **Vocabulary dependency:** No word appears in a problem or entry before it has been defined elsewhere in the corpus.
- **Bidirectional contrasts:** If entry A says "A is not B", entry B should exist and ideally say "B is not A."
- **No computation math** in concept files. Math concepts file covers number/shape/operation as language. Math problems file covers grade 1 arithmetic with known vocabulary only.
- **Cross-domain linking:** Entries reference other domains naturally (e.g. professions link to tools, animals link to plants).
- **Clear concept ownership:** prefer one canonical `what is X?` home per concept whenever possible.
- **General before specific:** broader anchors should usually appear before narrower concepts inside a file.

## Known dangling contrasts

These words appear as contrast targets (`X is not Y`) but do not yet have their
own entry. Each one is a candidate for later expansion.

| Word | Appears in | Priority |
|---|---|---|
| tiger | animals_mammals | medium |
| magazine | school_life_and_learning | low |
| plastic | school_life_and_learning | low |
| fog | weather_and_celestial | medium |
| breeze | weather_and_celestial | low |
| lightning | weather_and_celestial | high |
| darkness | weather_and_celestial | medium |
| puddle | weather_and_celestial | low |
| climate | weather_and_celestial | low |
| raven | animals_birds | low |
| plantain | foods_fruits | low |
| numeral | mathematical_concepts | low |

## Next steps

1. Continue manual cleanup before large category expansion
2. Review untouched or partially touched files like `foods_vegetables_entries.md`
3. Run later dependency/contrast pass across the whole wiki
4. Expand missing categories only after existing files have clear identity and ownership
5. Use `wiki_implementation_todo.md` as the practical write queue and recurring anchor-review checklist
