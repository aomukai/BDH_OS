# Ninereeds curriculum v6: independent Sol synthesis

You are a fresh, context-isolated GPT-5.6 Sol instance acting as the principal
curriculum architect. Do not delegate or spawn subagents. Read the source files
yourself, reason through their disagreements, and produce your own curriculum.

## Write boundary

You may create and edit files only under:

`/home/aomukai/Ninereeds/docs/curriculum_v6_sol/`

Do not modify v1-v5, the reconstructed v4 bundle, the world bible, Lesson 000,
the identity policy, Mission Hub, the image registry, training data, services,
or any other repository file. The source proposals are evidence, not targets to
patch. Do not start model training or image acquisition.

## Goal

Design the strongest feasible language-and-world-model curriculum for teaching
Ninereeds on top of the visual foundation currently being prepared. The visual
foundation provides reviewed word/image grounding with variation; it must not
be mistaken for fluent language competence or a complete world model.

The expected shape is approximately 300 acquisition lessons, then a distinct
rehearsal/transfer layer that can bring the planned program toward roughly
600-700 total conducted lessons. These are safety expectations, not quotas.
Choose different totals if your reasoning supports them, and document why.

Acquisition lessons establish one principal novelty. Rehearsal lessons add no
new language or world facts: they retrieve, vary, contrast, compose, and transfer
previous material with spacing and interference control. Diagnostic/remedial
lessons may be conditional rather than precommitted.

This is a curriculum plan, not the fully authored lessons. Every acquisition
lesson must at minimum have a TOPIC and POINT whose pairing is genuinely
teachable. It must carry enough explicit prerequisite, surface-language,
grounding, chronology, rehearsal, and evaluation information for the local
lesson compiler to author the lesson later without inventing policy.

## Authority order

Resolve conflicts in this order:

1. `docs/ninereeds_identity_and_lesson_policy.md`
2. `training_data/grounded_stories/world_bible.md`
3. `handoff/2023_08_20_lesson_000_example.md`
4. Explicit methodology and intent in `handoff/2026_08_19_train_of_thought.md`
   and `mission_hub/wiki/teaching.md`
5. C001-C240 candidate provenance in `docs/2026_08_20_curriculum_v1.md`
6. v2 and v3 as design analyses
7. Reconstructed Deep Research v4 and DeepSeek v5 as independent, corrigible
   proposals

When a later proposal conflicts with a higher authority, do not preserve the
conflict for the sake of compromise.

## Independent proposals to compare deeply

Read all relevant content, not only summaries:

- Deep Research reconstruction:
  - `ninereeds_curriculum_v4_bundle/ninereeds_curriculum_v4.json`
  - `ninereeds_curriculum_v4_bundle/ninereeds_curriculum_v4.md`
  - `ninereeds_curriculum_v4_bundle/v4_source_accounting.csv`
  - `ninereeds_curriculum_v4_bundle/v4_lessons.csv`
  - `ninereeds_curriculum_v4_bundle/v4_audit.json`
- DeepSeek independent proposal:
  - `docs/curriculum_v5_deepseek/stage1_design.json`
  - `docs/curriculum_v5_deepseek/curriculum_v5.json`
  - `docs/curriculum_v5_deepseek/asset_plan_v5.json`
  - `docs/curriculum_v5_deepseek/validation.json`
  - `docs/curriculum_v5_deepseek/asset_validation.json`

Understand why v4 compiles 295 acquisition-like lessons while v5 compiles only
63 and defers 158 of C001-C240. Do not select one wholesale. Treat divergence as
evidence about coverage, priority, granularity, and risk.

## Current foundation context

Inspect enough of these files to understand the substrate being prepared and
the teaching pipeline, without changing or waiting on the live process:

- `config/mission_hub/campaign_material/campaign36/m2-teaching-lexicon.jsonl`
- `config/mission_hub/campaign_material/campaign36/image-preparation-loop-v1.json`
- `mission_hub/skills/compile-next-lesson/SKILL.md`
- `mission_hub/research/lesson-compiler.json`
- `mission_hub/research/instructor-qualification-policy.json`

The current image work is preparation only; Campaign 36 training has not begun.
Assume accepted visual materials retain provenance, hashes, variation controls,
and the local Gemma -> Luna -> Sol review escalation.

## Non-negotiable design constraints

- Preserve actual Lesson 000 as the sole staged bootstrap exception.
- Lesson 000 has no picture book. Its controlled drills are noncanonical.
- Do not repeat canonical first meetings. Maintain persistent village chronology.
- Bob remains provisional unless you can point to explicit operator approval in
  the authoritative sources; do not invent a biography.
- Errol is a mind who communicates through Gran's phone. He is not the phone,
  screen, case, symbol, or a body.
- Early appearances of Errol should ground this implicitly. Do not teach explicit
  mind/person/device ontology before sufficient ordinary language exists.
- Preserve "Errol travels by data transfer" as an intentional primitive when it
  becomes teachable; distinguish it from message transfer and physical travel.
- Do not classify Ninereeds through forbidden implementation, substrate,
  consciousness, sentience, machine, model, LLM, or AI relations.
- A lesson's presentation, practice, correction, picture-book text, and
  evaluation must be expressible using established language plus its bounded,
  semantically coherent frontier.
- A single named bundle is not evidence of one novelty. Count actual new forms,
  constructions, discourse operations, and world distinctions.
- Repeat useful POINTs with different TOPICs. Do not teach a POINT once and then
  assume robust mastery.
- Use picture books where an event, persistent scene, chronology, or social
  interaction materially improves grounding. Do not mark nearly everything
  optional and postpone the decision.
- Regular images require meaningful variation. Avoid teaching accidental
  synonymies such as `itself` = cat.
- Treat C001-C240 individually. Active, consolidated, deferred, and excluded are
  all legitimate dispositions, but comprehensive K-8 preparation cannot be
  achieved by silently deferring most of the world model.
- Do not optimize for elegant counts or for passing a validator you wrote.

## Required outputs

Create these durable files under the write boundary:

1. `README.md`
   - artifact map, status, counts, and unresolved decisions.
2. `synthesis_decisions.md`
   - substantial comparison of v4 and v5;
   - what you accepted, rejected, transformed, or newly introduced and why;
   - phase architecture and granularity rationale.
3. `curriculum_v6.json`
   - complete acquisition skeleton, consecutively numbered from `L000`;
   - metadata and explicit unresolved decisions;
   - each lesson must include:
     - `lesson_id`, `phase`, `topic`, `point`, `world_objective`;
     - `principal_novelty` and its type;
     - actual `frontier_language`;
     - `required_established_language`;
     - earlier `prerequisite_lessons`;
     - `grounding_modes`;
     - `picture_book` as `required`, `optional`, or `no`, with rationale;
     - characters, locations, chronology constraints;
     - evaluation targets;
     - source provenance;
     - intended later rehearsal targets.
4. `curriculum_v6.md`
   - readable rendering of the complete acquisition sequence.
5. `source_accounting_v6.json`
   - exactly one evidence-based record for each C001-C240;
   - disposition, resulting lesson IDs, and rationale.
6. `rehearsal_layer_v6.json`
   - a concrete scheduled rehearsal/transfer skeleton, not merely principles;
   - each entry references only earlier acquisition/rehearsal material;
   - no new frontier language or facts;
   - include spacing purpose, interference set, varied TOPIC/POINT recombination,
     grounding mode, response expectations, and evaluation objective;
   - include conditional diagnostic/remedial gates separately.
7. `rehearsal_layer_v6.md`
   - readable rendering and explanation of the spacing/transfer strategy.
8. `asset_policy_v6.md`
   - compare v4 and v5 visual assumptions;
   - identify which acquisition lessons require picture books and why;
   - define how ordinary images, canonical references, derived crops, variation,
     and fallback generation connect to the lesson skeleton;
   - do not acquire or generate assets.
9. `validate_curriculum_v6.py`
   - read-only validator for identifier uniqueness, source accounting, dependency
     order, acquisition/rehearsal separation, chronology declarations, frontier
     limits, and referential integrity;
   - do not claim to validate pedagogical quality mechanically.
10. `self_validation_v6.json`
    - actual output from running the validator;
    - structural failures must remain failures, not unsupported passes.

Use atomic writes where practical. Inspect your completed artifacts, run the
validator, and correct structural defects before finishing. Do not perform the
future adversarial review yourself: a separate fresh Sol instance will receive
that mission after this synthesis is complete.
