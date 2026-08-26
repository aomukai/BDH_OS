# Ninereeds curriculum v6 — independent Sol synthesis

Status: **complete_pending_independent_adversarial_review**. Structural self-validation: **PASS**. Independent adversarial pedagogical review has not been performed and is intentionally out of scope for this synthesis.

## Counts

- Acquisition lessons: **396** (`L000`–`L395`)
- Scheduled rehearsal/transfer lessons: **270** (`R001`–`R270`)
- Planned conducted total: **666**
- Conditional diagnostic/remedial gates: **6**, not counted unless triggered
- Required picture books: **34**; optional: **0**; no-book: **362**
- C001–C240 accounting records: **240** (206 active; 34 consolidated; 0 deferred; 0 excluded)

The 396 acquisition count is intentional. Actual novelty counting, restored foundational language, comprehensive world coverage, and separation of acquisition from transfer make a 300-lesson cap pedagogically dishonest. The combined total is 666, within the requested 600–700 planning range.

## Artifact map

| File | Role |
|---|---|
| `README.md` | Status, counts, artifact map, and unresolved decisions |
| `synthesis_decisions.md` | V4/v5 comparison, accepted/rejected/transformed decisions, architecture, and granularity rationale |
| `curriculum_v6.json` | Normative 396-lesson acquisition skeleton with dependencies, surface closure, grounding, chronology, evaluation, provenance, and rehearsal links |
| `curriculum_v6.md` | Readable complete acquisition sequence |
| `source_accounting_v6.json` | Exactly one evidence-based disposition record for each C001–C240 |
| `rehearsal_layer_v6.json` | Normative 270-entry no-novelty schedule plus separate conditional gates |
| `rehearsal_layer_v6.md` | Readable schedule and spacing/transfer explanation |
| `asset_policy_v6.md` | V4/v5 visual comparison, required-book inventory, variation, references, crops, and fallback policy |
| `validate_curriculum_v6.py` | Read-only structural validator; it does not score pedagogy |
| `self_validation_v6.json` | Actual captured validator result |
| `build_v6.py` | Deterministic atomic artifact authoring helper retained for auditability; not a lesson compiler or training entry point |

## Binding unresolved decisions

- **U01_LEARNER_STATE**: The actual demonstrated language, error profile, and instructor qualification at the time each lesson is compiled. The sequence is a dependency skeleton, not permission to skip the actual-state check or force the nominal next ID.
- **U02_BOB_APPROVAL**: Whether an operator approves Bob beyond the Lesson 000 source appearance. No approval was found; no biography, asset request, relationship, or later appearance is authorized.
- **U03_L000_ACQUAINTANCE_EDGES**: Any acquaintance/first-meeting relation not unambiguously depicted in actual Lesson 000. Do not infer extra canonical first meetings from controlled drills.
- **U04_ACCEPTED_ASSET_INSTANCES**: Which prepared images, references, master scenes, crops, or fallback candidates pass review for each compiled lesson. This synthesis acquires and generates nothing; lexicon acceptance never proves language competence.
- **U05_EXTENDED_CAST**: First learner-facing appearances for world-bible extended cast not explicitly used in this skeleton. A lesson compiler may not insert them ad hoc or stage a first meeting without a new approved acquisition plan.
- **U06_ABSOLUTE_DATES**: Exact calendar dates and local weather for canonical season segments. They must fit the declared relative sequence and world-bible seasonal facts; weather is not inferred from season as a certainty.

## Boundaries

No source proposal, world file, policy, mission file, training data, service, or image registry was modified. No model training, image acquisition, download, generation, or live Campaign 36 action was started. The visual foundation is treated as reviewed referential grounding, not as fluent language or a complete world model.
