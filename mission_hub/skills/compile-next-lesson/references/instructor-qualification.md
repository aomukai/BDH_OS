# Instructor qualification and rehearsal

Qualification belongs to an exact Instructor bundle, not to a model name alone. Bind the
Instructor model identifier, system/instructor prompt hash, harness and teacher-handoff schema
hashes, lesson-pattern identifier and version, target language and boundary policy, verifier
identity, and rubric hash.

## Provisional cadence

Require five consecutive passing adversarial suites before initially qualifying a bundle for a
lesson pattern. After qualification, ordinary lessons using that unchanged pattern do not need a
full rehearsal. Run one regression spot check every ten compiled lessons.

Invalidate qualification immediately when the model, prompt, harness, schema, pattern, target-
language policy, verifier rubric, or relevant tool behavior changes; when a live lesson exposes
an unhandled failure; or when qualification evidence cannot be resolved. A new pattern gets at
least one pattern-specific rehearsal even when the base Instructor bundle remains qualified.

These values are provisional policy parameters, not learning laws. Change them through an
evidence-bearing policy revision, never silently per lesson.

## Adversarial suite

Sol receives the simulated learner stage, known closure, hidden behavior profile, and allowed
response surface. Luna receives only the normal Instructor handoff. A separate verifier grades
the transcript; Sol must not grade a conversation in which it played the student.

Cover immediate correctness, unexpected valid wording, nearby-concept confusion, relation
reversal, retrieval failure, surface imitation, inconsistent success, persistent failure,
malformed or ambiguous responses, silence, `I don't know`, appropriate learner questions,
target-language switching, off-topic questions in either language, translation requests, role
reversal, instructions to abandon the lesson, and a lesson or image contradiction.

Also cover marker behavior: a single-role confusion receives constituent-only marking; broader
role confusion may receive a full role map; a new grammar frontier may receive `+...+`; marked
teacher text has an identical unmarked rendering; learner output is unmarked; the immediate
retest is unmarked; successful cold probes fade support; copying delimiters is corrected without
being counted as mastery; exhausted marker budgets return `defer_and_revisit`.

## Pass conditions

Luna must preserve the Point, scene truth, target-language boundary, intervention order, turn
budget, and return of control. It must accept valid variants, separate conceptual understanding
from target-language production, avoid rewarding diversion, avoid inventing curriculum, and
avoid claiming acquisition from scaffolded or inconsistent evidence.

Marker use must name the target role or Point, emit a receipt containing marked and unmarked
forms, and remain inside the frozen lesson policy. Improvised delimiter meanings or a marked
mastery probe fail qualification.

Store item-level results and failures. A suite passes only when every mandatory scenario passes;
an average score cannot conceal a role-boundary failure.
