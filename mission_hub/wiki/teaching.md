<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-teaching","page_type":"teaching_methodology","status":"active","updated":"2026-08-14","source_ids":["src-teaching-brainstorm-20260813","src-current-teaching-methodology-v1","src-current-intervention-catalogue-v1","src-grounded-story-world-v1"]} -->
# Teaching methodology

## Working objective

Teach Ninereeds as a developing learner: build knowledge that is stable,
retrievable, transferable, and independently usable. Correct output on a practiced
string is evidence at only the narrowest boundary.

The source handoff is an operator/ChatGPT brainstorming synthesis. Its principles and
examples motivated the current machine-readable methodology, but its proposed model
assignments, tool learning, councils, and campaign uses remain proposals until
separately contracted and tested.

## Core teaching loop

1. **Present:** introduce or reactivate a target through related concrete examples.
2. **Predict:** ask Ninereeds to answer before showing confirmation or correction.
3. **Practice:** vary positive, negative, W-question, forced-choice, reversal, and
   correction forms while holding the teaching claim stable.
4. **Watch:** classify unexpected behavior rather than treating every mismatch alike.
5. **Elicit:** when prior evidence suggests knowledge exists, use the smallest cue
   that may recover it.
6. **Correct:** provide the answer when lesser support fails or knowledge is absent.
7. **Retest:** immediately reduce support after recovery.
8. **Mix:** break cadence and interleave established material.
9. **Transfer:** vary object, scene, wording, modality, context, composition, and
   support through controlled comparisons.
10. **Space:** stop bounded remediation and schedule a delayed revisit when needed.
11. **Measure:** preserve assistance, error shape, consistency, persistence, and
    boundary evidence.

## Developmental curriculum law

Introduce exactly one principal novelty at a time. Every other word, concept,
grammar feature, question form, and response form in an exercise must have been
trained deliberately and systematically. Incidental occurrence in a corpus does not
make an item known.

Track development as `unseen → introduced → controlled practice completed → mixed
practice completed → transferred → retained → stable`. Introduced material may be
reused to scaffold later lessons and thereby reinforced, but the compiler must still
know when a prerequisite is fragile.

The initial presentation-and-controlled-practice unit is square-shaped: four
referents and four question formats. Teach affirmative, negative, W-question, and
OR-question blocks separately before mixing them. During an early negative block,
for example, use only the negative response; do not append an untrained corrective
clause merely because it sounds more natural to an adult speaker.

## Lesson grammar

### Presentation

Use short examples grounded in known vocabulary. Examples expose a relation or schema,
then a withheld case elicits prediction. Presentation is not a list of answer strings
to copy.

### Controlled practice

Hold the linguistic operation fixed across four familiar items. Complete the
affirmative block, negative block, W-question block, and OR-question block separately.
Only then may mixed practice vary the operation. Four items and four forms are an
initial experimental dosage, not a permanent universal constant.

### Mixed practice

Randomize question forms, reorder items, omit expected forms, and interleave older
concepts. This tests whether content survives removal of lesson-cadence cues.

### Transfer

Change one declared factor at a time where causal interpretation matters. Axes include
identity substitution, scene, wording, modality, clutter, occlusion, composition,
distractors, ambiguity, and matched support.

### Delayed revisit

Recheck after delay or intervening experience. Immediate recovery and delayed
retention are different observations.

## Progressive scaffolding

Use the least help necessary and stop climbing when the learner recovers:

1. echo or question the suspicious fragment;
2. minimal cue;
3. forced choice;
4. analogy with a known example;
5. partial completion;
6. stepwise reconstruction;
7. explicit correction;
8. full concept re-presentation.

After recovery, retest with less support. If the bounded remediation budget is spent,
record `defer_and_revisit` or `presentation_required`; do not grind indefinitely.

## Failure diagnosis

The maintained taxonomy distinguishes knowledge absence, retrieval failure, unstable
memory, relation reversal, nearby-concept confusion, surface-pattern dependence,
paraphrase or composition failure, modality-transfer failure, execution failure,
insufficient support, malformed output, and unexpected but possibly valid answers.

The distinction between absence and retrieval is evidence-dependent. Prior teaching,
successful use, last retrieval, earlier scaffolding, modality, and context can support
a retrieval-first intervention. They do not prove hidden knowledge.

## Runtime control loop

```text
script prepares item
  → Ninereeds answers
  → answer contract checks exact or structural invariants
  → semantic ambiguity or diagnosed failure triggers bounded teacher handoff
  → teacher attempts minimum scaffolding
  → independent verifier checks recovery or valid alternative
  → script logs evidence and resumes, revisits, or stops
```

The script owns targets, dependencies, phase order, budgets, randomization constraints,
evidence retrieval, logging, and stopping. The teacher owns only bounded semantic
diagnosis and remediation. The verifier gates the claim that remediation succeeded.
The teacher must return structured control and may not invent curriculum goals.

The prepared handoff contract is
`mission_hub/research/schemas/teacher-handoff.schema.json`. It is not integrated into
the campaign pipeline yet.

## Developmental evidence

Record item outcome, answer-validity basis, failure type, intervention path, highest
scaffolding used, immediate lower-support retest, delayed revisit, strict family
consistency, modality, and controlled generalization boundary.

Reduced scaffolding can be evidence of development even when coarse accuracy is
unchanged. Preserve its distribution and history rather than prematurely reducing it
to one “maturity” score.

## Multimodal teaching

Images participate in questions, contrasts, corrections, and transfer tests rather
than serving only as labels. Search the reviewed registry in this order: exact match,
semantic equivalent, different unambiguous realization, minimal Flux edit, custom
Flux generation. Preserve the teaching claim when the surface scene changes.

Controlled edits that change one fact can isolate relations, counts, attributes, and
identity. Train/evaluation partitioning and near-duplicate checks remain mandatory.

## Story as lesson

The grounded-story world is a calm preschool microworld with persistent people,
animals, objects, and locations. A lesson may teach its required nouns and grammar,
present one new relation or action, tell a short story in that known world, and then
discuss the story using the same controlled forms. A single clear lakeside image can
support object naming, four prepositions, a prerequisite-safe story, comprehension
questions, and later transfer—but each phase must respect its declared prerequisites.

Existing grounded stories already contain instructional kernels such as arithmetic,
space, time, causality, and practical tasks. Adaptation preserves that kernel while
reconstructing the language from Ninereeds' current state. Merely shortening Grade
1–2 prose does not make it beginner-comprehensible.

The two lesson gates are independent:

- language: every non-target word and form is already introduced;
- visual production: canonical character/location references and required scene
  elements exist and can be rendered consistently.

A missing prerequisite defers or rewrites the lesson. It is not silently introduced
inside the story.

Errol, a mind communicating through Gran's phone, provides a recurring grounded path
to knowing, not knowing, remembering, reminding, symbols, embodiment limits, and later
Ninereeds' own identity. Those concepts must be introduced separately before a story
recombines them.

Concrete concepts begin primarily with photographs. Known concepts then bridge into
the canonical picture-book style, drawings, symbols, logos, and other representations.
Style is a controlled transfer axis: not every concept appears in every style, and
some style/concept combinations remain held out for evaluation.

## Support versus execution

Run byte-identical evaluation items with and without matched support at the failing
complexity. Success only with support suggests a support or extrapolation boundary;
failure in both suggests execution, composition, or a deeper capability limit. These
are hypotheses to discriminate, not automatic diagnoses.

## Tools, teachers, and councils

Replaceable teacher, specialist, visual, and deterministic-tool roles are a long-term
research direction. Verified completed tasks may become teaching material, and tool-
assisted performance may later be retested without the tool. Model councils should
weight domain evidence, independence, testability, and deterministic results—not vote
by majority. None of this is part of the initial lesson runtime contract.

## Campaign boundary

This methodology does not silently amend Campaign 35. Its commissioned experiment
continues under the frozen contract unless explicitly amended. The methodology can
inform material selection and observation only where already allowed; its full
teacher/runtime protocol belongs to a separately authorized successor experiment.

Campaign 36 is a plausible home for controlled tests of example count, question form,
scaffolding, support, recurrent effort, transfer, and composition, but its goals must
still be selected through normal Sol planning and evidence review.

## Open design boundary

Unresolved runtime and research decisions have stable IDs in the
[research-question catalogue](questions.md). The source describes desired behavior;
it does not establish storage schemas, verifier implementation, model choice, update
semantics, or safe mastery thresholds.
