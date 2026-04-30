# Level 1 Finish and Level 2 Start Plan

For the canonical overall training sequence, see `docs/training_pipeline.md`.
This file focuses specifically on the Level 1 trunk pass and the gate into Level 2.

Working plan for finishing the Level 1 wiki cleanup pass and choosing safe
Level 2 expansions.

Use this file together with:
- `docs/training_pipeline.md` — canonical sequence for training, audits, story layers, and Mommy Says Machine evaluation
- `history.md` — wiki history, current corpus state, and tiering
- `training_data/wiki/wiki_category_backlog.md` — strategic backlog and dependency map
- `todo.md` — active working queue
- `training_data/wiki/00_ideas.md` — deferred connective-tissue batch
- `training_data/phases/missing_curriculum_terms.md` — anchor-gap log

---

## Level 1 cleanup order — COMPLETED (2026-04-18)

All trunk files have been audited. See `01_CORPUS_STATUS.md` for detailed results.

1. [x] `logic_entries.md` — 60 entries, ownership splits with storytelling intentional
2. [x] `STEM_entries.md` — 51 entries, well-scoped bridge file
3. [x] `time_entries.md` — 35 entries, clean temporal ownership
4. [x] `space_entries.md` — 36 entries, `height` duplicate removed
5. [x] `verbs_entries.md` — 77 entries, intentional splits documented
6. [x] `mathematical_concepts_entries.md` — 29 entries, concept-only scope confirmed
7. [x] `body_parts_entries.md` — 28 entries, no drift detected

Note: the former `mathematical_problems_entries.md` file was later reclassified out of the wiki and moved into `training_data/reasoning/` as standalone reasoning-corpus seed material (2026-04-28).

---

## File-by-file review targets

### 1. `logic_entries.md`

Look out for:
- file bloat
- concepts that belong more naturally in social or pragmatic files
- overlap with `time_entries.md` around `begin`, `middle`, `end`
- overly abstract or textbook wording

Current risk areas:
- `self`, `other`, `own`, `belong`, `memory`, `habit`
- core logic mixed with broad human/social abstraction

### 2. `STEM_entries.md`

Look out for:
- overlap with `verbs_entries.md`
- overlap with sensory/body-state files
- overlap with weather/light/state-change ownership elsewhere
- drift from compact bridge file into catch-all knowledge file

Current risk areas:
- `breathe`, `eat`, `drink`, `sleep`, `awake`
- `see`, `hear`, `smell`, `taste`, `touch`
- broad state-change and life-process language

### 3. `time_entries.md`

Look out for:
- clean temporal ownership
- overlap with `logic_entries.md`
- overlap with `storytelling_and_narrative_structure_entries.md`
- keeping sequence language simple and concrete

Current risk areas:
- relation to `begin`, `middle`, `end`
- relation to narrative sequence words

### 4. `space_entries.md`

Look out for:
- spatial-relation clarity
- overlap with `mathematical_concepts_entries.md`
- whether measurement-adjacent terms truly belong here

Current risk areas:
- `height`, `width`, `depth`
- `center`, `edge`, `corner`

### 5. `verbs_entries.md`

Look out for:
- whether the file is acting like a clean core action layer
- overlap with specialist domain files
- duplicate ownership of verbs that already have better homes elsewhere

Rule:
- keep high-frequency, general-purpose verbs
- avoid letting the file compete with domain-specific anchor files

### 6. `mathematical_concepts_entries.md`

Look out for:
- keeping it concept-language only
- no drift into problem-solving explanation
- no unnecessary spatial vocabulary if that belongs to `space_entries.md`

Current strength:
- compact and coherent

### 7. `body_parts_entries.md`

Look out for:
- ordering from broader to narrower
- contrast cleanliness
- whether any entries are drifting from anatomy into body-state or health ownership

Current strength:
- stable inventory structure and mostly clean contrasts

---

## Cross-file overlap hotspots — RESOLVED (2026-04-18)

All overlap hotspots have been audited and documented. See `dependency_ledger.md` for full details.

- `logic_entries.md` vs `time_entries.md`
  - `begin`, `middle`, `end` — logic owns abstract sequence, storytelling owns narrative sense, time does not own
  - RESOLVED: Intentional split documented

- `STEM_entries.md` vs `verbs_entries.md`
  - `eat`, `drink`, `sleep`, `breathe` — STEM owns biological process, verbs owns action
  - RESOLVED: Intentional split documented

- `STEM_entries.md` vs sensory/body files
  - `see`, `hear`, `smell`, `taste`, `touch` — STEM owns sense organs, sensory_experiences owns descriptive qualities
  - RESOLVED: Intentional split documented

- `space_entries.md` vs `mathematical_concepts_entries.md`
  - `height` — RESOLVED: Removed from space, measurement_and_comparison is canonical owner
  - `width`, `depth`, `center`, `edge`, `corner` — Unique to space_entries, no conflict

- former `mathematical_problems_entries.md` wiki file
  - RECLASSIFIED: moved to `training_data/reasoning/` as standalone reasoning-corpus seed material on 2026-04-28 because it did not fit the wiki path cleanly

---

## After the trunk pass

Review bridge files before adding new connective tissue:

- `exceptions_and_qualifications_entries.md`
- `storytelling_and_narrative_structure_entries.md`
- `degrees_of_truth_entries.md`
- `intentions_and_plans_in_action_entries.md`
- `perspective_taking_and_theory_of_mind_entries.md`

Then implement the deferred connective-tissue batch from `00_ideas.md`, including:

- additions to `STEM_entries.md`
- additions to `logic_entries.md`
- additions to `exceptions_and_qualifications_entries.md`
- additions to `storytelling_and_narrative_structure_entries.md`
- additions to `time_entries.md`
- new file `appearance_and_hidden_state_entries.md`

Do not mix this batch into the first quality pass.

---

## Alternating Expansion Cadence (Canonical Rule)

Wiki and story layers expand together in an alternating pattern.
Each wiki level is followed by a corresponding story layer before the next wiki level begins.

### The cadence

```
Wiki Level 1 → Story Layer 1 → Wiki Level 2 → Story Layer 2 → Wiki Level 3 → Story Layer 3 → ...
```

### Why alternate

1. **Grounding before variation**: Stories use only vocabulary grounded in the preceding wiki (and curriculum). A story layer must not introduce vocabulary the dragon has not already learned through definitions.

2. **Reinforcement through context**: After the dragon learns concepts through wiki definitions, stories show those concepts used together in realistic scenarios. This reinforces meaning and teaches co-occurrence patterns.

3. **Controlled complexity growth**: Each wiki level adds new concepts or richer branching. Each story layer adds new sentence structures and cognitive load (see `story_layer_rules.md`). Interleaving them prevents the dragon from learning concepts without usage or usage without concepts.

4. **Quality gates**: The transition from one wiki level to its story layer is a natural checkpoint for human review. If wiki quality is poor, fix it before writing stories. If stories reveal vocabulary gaps, fix the wiki before expanding.

### Story layers track wiki levels

| Wiki Level | Followed by | Story scope |
|------------|-------------|-------------|
| Level 1 | Story Layer 1 | Vocabulary from Phase 1–5 + Wiki Level 1. For the current rewrite-stage spec, use `training_data/triplet_stories/story_tier_specs.md`: 8 sentences, one small concrete event, one main subject, first safe pronoun use only after clear introduction. |
| Level 2 | Story Layer 2 | Adds Wiki Level 2 vocabulary. For the current rewrite-stage spec, use `training_data/triplet_stories/story_tier_specs.md`: 12 sentences, scene-setting, longer event chains, optional named characters, clear noun → name → pronoun handling, and at most one mild obstacle or change. |
| Level 3 | Story Layer 3 | Adds Wiki Level 3 vocabulary. Allows "but," one causal chain, one comparison. |
| Level 4 | Story Layer 4 | Adds Wiki Level 4 vocabulary. Allows multiple cause-effect links and explicit reasoning. |

### Connective tissue batch placement

The connective tissue batch from `00_ideas.md` should be implemented between Wiki Level 1 and Story Layer 1. These bridge concepts (become, turn into, appear, disappear, fail, etc.) are needed for stories to describe state changes and outcomes naturally.

Sequence with connective tissue:

```
Wiki Level 1 → Level 1 Audit → Connective Tissue Batch → Story Layer 1 → Wiki Level 2 → Story Layer 2 → ...
```

### Do not skip story layers

Do not jump directly from Wiki Level 1 to Wiki Level 2 without Story Layer 1.
Do not jump directly from Wiki Level 2 to Wiki Level 3 without Story Layer 2.

The story layer is not optional decoration. It is part of how the dragon learns to use concepts, not just recognize them.

### Do not front-load stories

Do not write Story Layer 2 content before Wiki Level 2 exists.
Do not use Level 2 vocabulary in Story Layer 1.

Each story layer draws from the vocabulary pool available at that point in the progression. Jumping ahead creates ungrounded vocabulary in stories.

### Human review at each transition

The transition between a wiki level and its story layer is a human review checkpoint.
The transition between a story layer and the next wiki level is also a human review checkpoint.

Questions to answer before each transition:
- Is the current wiki level stable and well-grounded?
- Does the story layer correctly use only grounded vocabulary?
- Are there concept gaps that should be fixed before expansion?
- Is the dragon's output quality good enough to justify the next level?

---

## Level 2 start criteria

Start Level 2 only after:

- trunk ownership is stable
- major Level 1 files sound consistent in voice
- overlap and contrast issues are under control
- new early-anchor gaps are logged in `missing_curriculum_terms.md` instead of being solved ad hoc
- **Story Layer 1 is complete** (per the alternating cadence rule above)

---

## Good Level 2 candidates

These are the files most likely to benefit from richer branching, subcases, and pragmatic variation:

- `emotions_entries.md`
- `communication_acts_and_language_entries.md`
- `friends_and_peer_interactions_entries.md`
- `conflict_resolution_and_relationship_repair_entries.md`
- `school_life_and_learning_entries.md`
- `play_games_and_sports_entries.md`
- `community_places_and_services_entries.md`
- `technology_and_digital_media_entries.md`
- `health_and_wellness_entries.md`
- `storytelling_and_narrative_structure_entries.md`
- `perspective_taking_and_theory_of_mind_entries.md`
- `evidence_and_justification_entries.md`

These files can grow through richer distinctions, more common scripts, more substructure, or more example families.

---

## Files that should probably stay compact

These are support files. They are not strong Level 2 snowflake candidates unless real corpus pressure appears:

- `time_entries.md`
- `space_entries.md`
- `mathematical_concepts_entries.md`
- `containers_and_capacity_entries.md`
- `levels_of_intensity_and_gradation_entries.md`
- `exceptions_and_qualifications_entries.md`
- `degrees_of_truth_entries.md`

Bigger is not automatically better for these files.

---

## Overall sequence

1. [x] Finish the Level 1 trunk pass. — COMPLETED 2026-04-18
2. [ ] Finish the Level 1 bridge and connective-tissue pass.
3. [x] Run one corpus-wide overlap, contrast, and dependency cleanup. — COMPLETED 2026-04-18
4. [x] Update planning docs in one batch. — COMPLETED 2026-04-18
5. [ ] Start Level 2 only on files that genuinely benefit from richer branching.
