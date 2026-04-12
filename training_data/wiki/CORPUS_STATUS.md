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
| chores_and_home_responsibilities_entries.md | New home-task category; anchors `chore`, `responsibility`, `clean up`, `put something away`, `make the bed`, `set the table`, `sweep the floor`, `water plants`, `feed a pet`, `take out the trash`, `tidy up` |
| clothing_and_apparel_entries.md | Expanded category; now anchors `clothing`, `coat`, `jacket`, `shirt`, `hat`, `glove`, `mitten`, `pants`, `skirt`, `dress`, `sock`, `shoe`, `button`, `zipper` |
| community_places_and_services_entries.md | New town-services category; anchors `community place`, `service`, `library`, `hospital`, `grocery store`, `fire station`, `police station`, `post office`, `museum`, `restaurant`, `bakery`, `bus stop` |
| construction_and_material_transformations_entries.md | New maker-change category; anchors `construction`, `repair`, `glue something`, `fold something`, `tear something`, `flatten something`, `mold something`, `shred something`, `crush something` |
| cooking_and_food_preparation_entries.md | New cooking-process category; anchors `cooking`, `food preparation`, `recipe`, `ingredient`, `chop food`, `peel food`, `stir food`, `whisk`, `bake`, `simmer`, `season food`, `knead dough` |
| daily_routines_and_self_care_entries.md | New routine category; anchors `routine`, `wake up`, `get ready`, `get dressed`, `wash your hands`, `eat breakfast`, `go to school`, `pack a backpack`, `line up`, `go to bed`, `pajamas` |
| directions_and_navigation_entries.md | New route-and-direction category; anchors `left`, `right`, `up`, `down`, `forward`, `backward`, `turn`, `go straight`, `map`, `route`, `address` |
| foods_and_drinks_entries.md | Rewritten into simpler Level 1 voice; anchors reordered |
| home_objects_entries_part1.md | Clean enough for current pass; migrated `book` to school category |
| home_objects_entries_part2.md | Cleaned and reordered with `furniture` as anchor; clothing removed |
| home_objects_entries_part3.md | Cleaned; `paper` migrated to school category |
| imagination_and_pretend_play_entries.md | New pretend-play category; anchors `imagination`, `pretend`, `pretend play`, `make-believe`, `dress up`, `role play`, `imaginary friend`, `symbolic play`, `game of pretend` |
| logic_entries.md | Merged former `logic_core_entries.md` into this file; now the single canonical logic file |
| meals_and_mealtime_talk_entries.md | New routine-and-talk category; anchors `meal`, `breakfast`, `lunch`, `dinner`, `snack`, `hungry`, `full`, `pass something`, `all done` |
| money_trade_and_shopping_entries.md | Expanded category; now anchors `money`, `coin`, `dollar`, `penny`, `nickel`, `dime`, `quarter`, `change`, `allowance`, `store`, `customer`, `shopkeeper`, `buy`, `sell`, `pay`, `cost`, `price`, `save`, `spend` |
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
| weather_and_celestial_entries.md | Rewritten into simple child-facing voice; `weather` and `wave` added |

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
