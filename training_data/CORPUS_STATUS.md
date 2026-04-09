# Corpus Status

## What we're building

A Level 1 training corpus for the BDH (Baby Dragon Hatchling) language model.
Each entry follows this format:

```
[user]what is a X?
[assistant]5-6 simple sentences. Identity + 2-3 concrete facts + 1 contrast.
X is not Y.
```

**Target level:** Grade 4-6 reading. No jargon, no Latin taxonomy, no encyclopedic depth.
**Contrast rule:** Every entry ends with "X is not Y." Both X and Y must be defined somewhere in the corpus (no dangling contrasts).

---

## Files and their status

### Custom curriculum (hand-built, clean)
These were written from scratch to the Level 1 spec. No rewrite needed.

| File | Notes |
|---|---|
| STEM_entries.md | Temperature, properties, states of matter, forces, biology, senses, motion |
| verbs_entries.md | Actions, motion, body language, perception |
| emotions_entries.md | 31 entries |
| time_entries.md | Temporal anchors + calendar vocabulary |
| space_entries.md | Spatial prepositions, using corgi+box examples |
| colors_entries.md | Color spectrum + light/dark |
| professions_entries.md | 21 entries |
| people_roles_entries.md | Family, social roles |
| mathematical_concepts_entries.md | Number/shape/operation concepts + 1-10 word-to-symbol bridge + plus/minus/equals |
| mathematical_problems_entries.md | Grade 1 arithmetic exercises, addition and subtraction. Vocab cleaned (no ounces/miles/dollars). Still needs prose simplification pass. |
| logic_entries.md | Cause/effect, fact/opinion, goal/problem/solution — light editing only |

### Nemotron-generated, rewritten to Level 1 (clean)
| File | Notes |
|---|---|
| foods_fruits_entries.md | 21 entries including nuts cluster |
| animals_insects_arthropods_entries.md | 12 entries, article errors fixed |
| animals_mammals_entries.md | 18 entries |
| animals_birds_entries.md | 13 entries, article errors fixed |
| body_parts_entries.md | 20 entries, article errors fixed |
| vehicles_transport_entries.md | 10 entries |
| home_rooms_entries.md | 5 entries, `room` moved to top as anchor |
| logic_core_entries.md | Logical operators and foundational concepts, patched 4 entries |

### Nemotron-generated, NOT YET cleaned
These still contain encyclopedic language and need a rewrite pass.

| File | Known issues |
|---|---|
| animals_fish_sea_entries.md | |
| animals_reptiles_amphibians_entries.md | |
| abstract_operators_entries.md | |
| home_objects_entries_part1/2/3.md | Split into 3 files, may need consolidation |
| places_and_landforms_entries.md | |
| plants_and_nature_entries.md | First 14 entries encyclopedic, user's manual additions (grass, rose, daisy, mushroom etc.) are good |
| tools_and_kitchenware_entries.md | |
| topology_parts_entries.md | |
| weather_and_celestial_entries.md | |
| foods_and_drinks_entries.md | |
| foods_vegetables_entries.md | |

---

## Design principles

- **Vocabulary dependency:** No word appears in a problem or entry before it has been defined elsewhere in the corpus.
- **Bidirectional contrasts:** If entry A says "A is not B", entry B should exist and ideally say "B is not A."
- **No computation math** in concept files. Math concepts file covers number/shape/operation as language. Math problems file covers grade 1 arithmetic with known vocabulary only.
- **Cross-domain linking:** Entries reference other domains naturally (e.g. professions link to tools, animals link to plants).

## Next steps

1. Rewrite remaining 11 Nemotron files (see table above)
2. Simplify math problems prose (D'Angelo-style wordiness still lurks in some entries)
3. Dependency sort: order files so anchors come before entries that reference them
4. Final pass: check all contrast pairs are bidirectional and defined
