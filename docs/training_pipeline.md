# BDH Training Pipeline

Canonical sequence for training, auditing, expansion, and late-stage evaluation.

This file exists so the training process is described in one place instead of being
spread across `phase 1 to 5/`, wiki planning notes, and Mommy Says Machine design docs.

---

## Purpose

The dragon should not jump directly from raw concept files into richer reasoning tasks.
The intended progression is:

1. build a strict language foundation
2. expand concept knowledge in the wiki
3. audit grounding and ownership
4. add bridge concepts needed for hidden-state and perspective reasoning
5. add story-based contextual variation
6. only then move into richer wiki levels
7. evaluate and diagnose with Mommy Says Machine after training

---

## Stage 1 — Phase 1–5 curriculum foundation

**Source:** `training_data/phases/`

This is the first training layer.
It provides:
- concrete vocabulary
- strict formatting
- dependency-ordered introduction of concepts
- compositional patterns built from already-grounded words

Key references:
- `training_data/phases/concept_index.md`
- `training_data/phases/training_sequence.txt`
- `training_data/phases/dependency_graph.json`
- `training_data/phases/missing_curriculum_terms.md`

Training note:
- `training_sequence.txt` is the authoritative order, not raw filename order.

Exit condition for this stage:
- the dragon has the intended early language foundation from phases 1–5

---

## Stage 2 — Wiki Level 1

**Primary sources:**
- `todo.md`
- `history.md`
- `training_data/wiki/wiki_category_backlog.md`
- `training_data/wiki/wiki_expansion_index.md`
- `training_data/wiki/wiki_entry_expansion_index.md`
- `training_data/wiki/level1_finish_and_level2_start_plan.md`
- `training_data/wiki/wiki_1/`

Wiki Level 1 adds:
- broader concept coverage
- category ownership
- child-facing explanatory language
- relational and social knowledge beyond the phase 1–5 curriculum

Current expectation:
- finish Level 1 with dependency coverage, overlap cleanup, and grounded concept homes
- do not treat the wiki as a random expansion bucket

Exit condition for this stage:
- Level 1 content is complete enough for a full audit
- trunk ownership and major dependency issues are under control

---

## Stage 3 — Level 1 audit

Before moving forward, perform a proper Level 1 audit.

Audit goals:
- verify category ownership
- verify overlap is under control
- verify contrast cleanliness
- verify dependency coverage
- verify voice consistency across the full Level 1 corpus

This audit is broader than simply checking whether files exist.
It asks whether the current Level 1 corpus is actually teachable as a coherent whole.

Exit condition for this stage:
- Level 1 is judged stable enough to compare against the earlier curriculum foundation

---

## Stage 4 — Level 1 vs phase 1–5 grounding audit

This is the grounding audit between the wiki corpus and the earlier curriculum.

Question:
- does the dragon already have enough phase 1–5 support to absorb the Level 1 wiki cleanly?

For important wiki concepts, classify them as:
- grounded in phase 1–5
- weakly grounded in phase 1–5
- missing curriculum anchor
- better left wiki-only

Use:
- `training_data/phases/missing_curriculum_terms.md`
- the dependency work from `wiki_category_backlog.md`
- the Level 1 cleanup results

This is the gate before richer expansion.
If grounding is weak, fix or log the gaps before moving on.

Exit condition for this stage:
- major wiki concepts are either grounded, explicitly deferred, or logged as curriculum-side gaps

---

## Stage 5 — Connective tissue batch / Phase 6 bridge

**Primary sources:**
- `training_data/wiki/00_ideas.md`
- `training_data/phases/phase_6/README.md`
- `training_data/phases/phase_6/phase_6_spec.md`
- `training_data/phases/phase_6/story_dialogue_progression.md`

Do not implement this during the main Level 1 quality pass.
Implement it only after:
- Level 1 audit is complete
- Level 1 vs phase 1–5 grounding audit is complete

This stage now has two tightly related jobs:

1. **Connective tissue concepts**
   - become / turn into / shrink / appear / disappear / use up / run out
   - outcome / both / also / but / however / fail
   - only if / in that case / otherwise
   - step / in order
   - eventually / takes time
   - new file: `appearance_and_hidden_state_entries.md`

2. **Phase 6 bridge curriculum**
   - teach missing scaffold vocabulary such as `word`, `sentence`, `thought`, `idea`, `true`, `real`, `question`, `answer`, `plan`, and `goal`
   - teach those words through a small reusable pattern grid rather than as isolated vocabulary only
   - prepare the dragon for Story Layer 1 without jumping too early into compressed quotation-based dialogue

Purpose:
- bridge from plain concept definition into hidden-state reasoning, delayed change, outcome tracking, appearance vs reality, and basic language-about-language
- prepare the dragon for better story understanding and later theory-of-mind work
- introduce the dialogue progression gradually: full proposition in Phase 6 → narrated indirect discourse in Story Layer 1 → quoted dialogue with speaker tags in Story Layer 2 → short elliptical replies only later

Exit condition for this stage:
- the bridge concepts needed for richer reasoning are present and stable
- the first Phase 6 bridge files and pattern grid are defined well enough that Story Layer 1 can rely on them

---

## Stage 6 — Story layer 1

**Source:** `training_data/wiki/00_ideas.md`

Stories are a separate training layer.
They are not wiki definitions.

Purpose:
- teach co-occurrence in context
- teach more natural sentence structures
- reinforce grounded words in flexible use

Story layer 1 should happen after:
- phase 1–5 foundation
- wiki Level 1
- Level 1 audit
- Level 1 vs phase 1–5 grounding audit
- connective tissue batch

Story rules:
- only use grounded vocabulary
- prefer one anchor concept with two supporting concepts
- use semantically coherent triplets
- do not force abstract concepts into stories if they do not fit naturally

This is the first story layer and should stay concrete and daily-life oriented.

Exit condition for this stage:
- the dragon has seen known concepts both in definition format and in short contextual narrative format

---

## Stage 7 — Wiki Level 2 and later story spirals

After the earlier stages are stable, move to richer wiki expansion.

Level 2 should not begin automatically just because Level 1 is "done."
It should begin only after the earlier audit and grounding gates are satisfied.

When moving to Level 2:
- review sample outputs and decide whether the style and abstraction level are actually desired
- refine category plans before doing large-scale expansion
- keep human review in the loop

### Alternating expansion cadence

Wiki and story layers expand together in a strict alternating pattern:

```
Wiki Level 1 → Story Layer 1 → Wiki Level 2 → Story Layer 2 → post-Level-2 consolidation review → Wiki Level 3 → Story Layer 3 → ...
```

After each wiki level, add the corresponding story layer before beginning the next wiki level:
- Wiki Level 2 → Story Layer 2
- then run a consolidation quality pass across the bridge/story/wiki stack before opening Wiki Level 3
- Wiki Level 3 → Story Layer 3
- and so on

Do not skip story layers. Do not front-load stories with vocabulary from a wiki level that does not yet exist.

The story format can remain stable while the vocabulary pool and conceptual richness expand.

For detailed rules on this cadence, see `training_data/wiki/level1_finish_and_level2_start_plan.md`.

---

## Stage 8 — Mommy Says Machine evaluation and targeted correction

**Source:** `docs/mommy_says_machine.md`

Mommy Says Machine is not the main trainer.
It is primarily:
- an evaluation system
- a diagnostic system
- a correction-pair generator for future offline training

Use it after training when the dragon is expected to be near the target competence level.

Best use cases:
- concepts that are clearly defined but still fail in practice
- false belief and hidden-state failures
- checking how the dragon handles correction
- measuring within-session retention

If stable failure patterns appear, the correction pairs can feed a later clean training run.

Exit condition for this stage:
- human review determines whether the model is good enough, what it is failing, and whether further offline training is warranted

---

## Human review checkpoints

Human review is especially important at these transitions:

1. **Before Level 2**
   - review Level 1 quality
   - review the Level 1 vs phase 1–5 grounding audit
   - review whether connective tissue additions are the right ones

2. **Before story layer expansion beyond Level 1**
   - check whether story outputs match the desired dragon voice and reasoning style

3. **Before using Mommy Says Machine correction data for training**
   - inspect whether failures are real concept failures or prompt-format artifacts
   - inspect whether teacher corrections are actually the kind of signal worth training on

---

## Current practical sequence

As of now, the intended near-term order is:

1. finish wiki Level 1 cleanup and gap filling
2. run a proper Level 1 audit
3. audit Level 1 against phase 1–5 grounding
4. implement the connective tissue batch from `00_ideas.md`
5. create story layer 1
6. review whether the resulting corpus quality justifies moving to Level 2
7. only later run Mommy Says Machine as evaluation / targeted remediation

---

## Related files

- `training_data/phases/concept_index.md`
- `training_data/phases/training_sequence.txt`
- `training_data/phases/missing_curriculum_terms.md`
- `history.md`
- `todo.md`
- `training_data/wiki/wiki_category_backlog.md`
- `training_data/wiki/level1_finish_and_level2_start_plan.md`
- `training_data/wiki/00_ideas.md`
- `docs/mommy_says_machine.md`
