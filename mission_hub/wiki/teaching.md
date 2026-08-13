<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-teaching","page_type":"teaching_methodology","status":"active","updated":"2026-08-13","source_ids":["src-teaching-brainstorm-20260813","src-current-teaching-methodology-v1","src-current-intervention-catalogue-v1"]} -->
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

## Lesson grammar

### Presentation

Use short examples grounded in known vocabulary. Examples expose a relation or schema,
then a withheld case elicits prediction. Presentation is not a list of answer strings
to copy.

### Controlled practice

Systematically vary the linguistic operation. The provisional beginner template of
four positive, four negative, four W-question, and four forced-choice examples is a
starting dosage, not a universal constant. Negatives should express useful boundaries
or reversals rather than random falsehoods.

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
