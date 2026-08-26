# Lesson contract

## Required planning evidence

Bind exact paths and SHA-256 values for the learner-state artifact, known closure, curriculum
plan, teaching methodology, world bible, identity policy, lesson pattern, and Instructor
qualification record. A mutable path without its observed hash is not evidence.

Record one Topic and exactly one principal Point. The Point may be a word, relation, response
form, grammar operation, or communicative act. Every other scored word, form, relation, and
operation must appear in the prerequisite list with evidence from this learner's lineage.

## Lesson variants

### `dialogue_only`

Require presentation examples; separate affirmative, negative, W-question, and OR-question
practice pools; a mixed-practice pool containing only established forms; explicit answer
contracts, assistance rules, budgets, and completion rules; and no picture-book pages or story
comprehension block.

### `picture_book`

Require everything in `dialogue_only`, plus one instructional kernel using the already-taught
Point; a page-ordered prerequisite-safe story; frozen master scenes and deterministic crops or
highlights; scene truth for every page; comprehension questions and controlled transfer; and
character, location, and object continuity evidence.

Do not use a story to smuggle in several untaught relations. Teach them separately first, then
let the story recombine them.

## Phase and answer rules

Run phases in this order: presentation, affirmative, negative, W-question, OR-question, mixed
practice, optional transfer or picture book. A later form must not appear inside early feedback.

Each exercise names its target, stimulus, asset references, acceptable answers, semantic
invariants, and whether target-language production is required. Preserve meaning and production
as separate judgments. A semantically correct answer in another language may demonstrate the
concept while failing target-language production.

Use the smallest intervention supported by evidence. `USE_MARKERS` is a deliberate bounded
intervention: use a constituent-only role marker before a full role map; use `+...+` only for
the current grammar frontier. Pair every marked sentence with its identical unmarked form,
require unmarked learner output, and retest immediately without markers. A marked response is
teaching evidence, never independent-performance evidence. Reduce support after recovery and
retest. Keep remediation bounded; `defer_and_revisit` is a valid outcome.

## Adaptive bounds

Declare presentation replay, maximum teacher turns, mixed-practice cap, acquisition fraction,
marker syntax and fading gates, and permitted controller actions. `USE_MARKERS`, `TRAIN_MORE`,
`TRAIN_LONGER`, and `REPLAY_LESSON` remain distinct. Marker counters and support levels survive
process restarts and context compaction. Predicted dosage is planning evidence; actual dosage is
an outcome.

## Immutability

Freeze exact order, texts, answer contracts, asset identities, hashes, randomization seed or
enumerated pool, intervention menu, budgets, completion rules, and research metadata. Per-model
adaptive traces remain separate from the shared immutable lesson.
