<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-teaching","page_type":"teaching_methodology","status":"active","updated":"2026-08-29","source_ids":["src-current-teaching-methodology-v1","src-current-intervention-catalogue-v1","src-grounded-story-world-v1","src-bdh-cq-paper","src-current-evaluation-methodology-v1","src-campaign35-post-reconstruction-planning-20260819"]} -->
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
concepts. This later *kreuz und quer* phase uses only already introduced material and
tests whether content survives removal of lesson-cadence cues. It is neither additional
curriculum breadth nor simple repetition.

### Transfer

Change one declared factor at a time where causal interpretation matters. Axes include
identity substitution, scene, wording, modality, clutter, occlusion, composition,
distractors, ambiguity, and matched support.

When transfer is a campaign objective, use the controlled ladders and strict
consistency rules in the [evaluation methodology](evaluation.md). Include tested
levels inside and beyond the practiced range, freeze fresh items after checkpoint
selection, and replicate around any observed transition rather than reducing the
curve to one average.

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
immutable lesson contract + learner trace + verified scene state
  → Luna conducts the next teaching turn
  → Ninereeds answers or asks
  → Luna interprets the response and selects explanation, crop, highlight, or scaffold
  → deterministic checks validate scene facts and structural invariants where possible
  → independent verifier gates acquisition or recovery claims
  → harness logs the trace and enforces phase, budget, revisit, and stop boundaries
```

For the candidate developmental school, Luna—not a deterministic dialogue script—
conducts the lesson. The immutable contract still owns the Point, dependencies,
allowed novelty, truth conditions, phase constraints, budgets, randomization,
evidence requirements, and stopping rules. Luna owns conversational realization,
semantic interpretation, demonstration, visual focus, and adaptive scaffolding within
those boundaries. The verifier gates claims that acquisition or remediation
succeeded. Luna returns structured evidence and may not invent curriculum goals.

The prepared handoff contract is
`mission_hub/research/schemas/teacher-handoff.schema.json`. It is not integrated into
the campaign pipeline yet and must be revised if the full Luna-conducted lesson
candidate is selected.

## Adaptive lesson contract

For the Campaign 36 candidate design, teaching and immediate observation form one
adaptive process: `present → attempt → observe → adapt → attempt again`. There is no
separate immediate post-lesson test that merely repeats evidence already present in
the trace. Delayed retention and reacquisition are measured at larger curriculum
boundaries.

Each lesson has an immutable script and a per-model adaptive trace. Thus two model
configurations may require different paths through the same contract; teaching amount
and kind are outcomes.

### Receding-horizon planning and dosage

Freeze the next lesson, run it, inspect the resulting learner state, then choose the
next step. Record Sol's predicted dosage beside actual exposures so planning can become
better calibrated over time. Four-item packs are a starting hypothesis; compare other
sizes under controlled conditions.

Keep dosage interventions distinct: `TRAIN_MORE` adds breadth, `TRAIN_LONGER` extends
varied mixed practice, and `REPLAY_LESSON` repeats the frozen lesson as an epoch.
Measure replay gain, plateau, delayed retention, and fresh-scene transfer so cadence or
template memorization is not mistaken for stronger acquisition.

One successor-curriculum candidate plans two primary packs of four words per lesson
and two reserve packs of four. The first eight words are the intended breadth; reserve
packs enter only when the per-model adaptive trace shows that additional valid
examples are needed. This 8+8 structure is a planning hypothesis, not a learning law,
and still obeys one principal novelty: preschool or K–2 topics provide a coherent
setting, while grammar and every scored supporting form remain prerequisite-gated.

### Topic versus Point

The **Topic** supplies a coherent environment, recurring world, plausible actions,
and incidental structure. Topic language may exceed the current frontier when it is
context only and is neither tested nor claimed as known. The **Point** is the narrow,
deliberately taught frontier. All scored language outside that novelty remains subject
to the prerequisite gate.

Show the full scene, then use crops or highlights for unambiguous grounding. Preserve
unexposed scene relations as research metadata. Topic coherence may help, do nothing,
or interfere; none is assumed, and later association is not proof of a world model.

### Item-level adaptation

Track failures per item rather than turning every miss into a failed pack or lesson.
Early meaningful failure episodes may replay the current four-item presentation to
restore contrastive context. Distinguish these episodes from raw retry count. Items
that become consistently successful leave intensive rotation but remain at lower
frequency in the growing Kreuz und Quer pool.

The proposed runtime states are `new`, `presented`, `unstable`, `acquired`, `leech`,
and `problem`. Leeches return in varied later contexts rather than receiving unlimited
drilling of the same lesson. Persistent problem items become research objects whose
material, tokenization, interference, projector, representation, and architecture
explanations must be discriminated.

The small exposed action menu is `CONTINUE`, `PRESENT_AGAIN`, `TRAIN_MORE`,
`TRAIN_LONGER`, `BACKTRACK`, and `FINISH`. The machine-readable adaptive-curriculum
design defines their current semantics; pipeline behavior remains unimplemented.

Adaptive branching does not alter the early form dependency. Complete affirmative
controlled practice first, negative second, W-question third, and OR-question fourth;
only then begin mixed Kreuz und Quer practice. Early negative answers contain only
negation and do not append an affirmative correction that introduces a later response
operation prematurely.

### Provisional thresholds

The proposed replay, 75% completion, leech/problem, and 8/40-lesson thresholds are
tunable Campaign 36 hypotheses, not learning laws. Freeze them before execution and
retain evidence for revision.

## Developmental evidence

Record item outcome, answer-validity basis, failure type, intervention path, highest
scaffolding used, immediate lower-support retest, delayed revisit, strict family
consistency, modality, and controlled generalization boundary.

Reduced scaffolding can be evidence of development even when coarse accuracy is
unchanged. Preserve its distribution and history rather than prematurely reducing it
to one “maturity” score.

Also measure whether Ninereeds becomes cheaper to teach across comparable curriculum-
age bands: exposures, replays, interventions, time, compute, leech incidence, delayed
retention, and reacquisition cost. Eventual success at unequal teaching cost is not an
equal experimental result.

## Multimodal teaching

Images participate in questions, contrasts, corrections, and transfer tests rather
than serving only as labels. Search the reviewed registry in this order: exact match,
semantic equivalent, different unambiguous realization, minimal Flux edit, custom
Flux generation. Preserve the teaching claim when the surface scene changes.

Controlled Flux edits can hold a cat, couch, living room, camera, and style fixed while
changing only `on`, `under`, `in front of`, or `behind`. Validate each counterfactual
independently, then test transfer with different entities and scenes. Train/evaluation
partitioning and near-duplicate checks remain mandatory.

For beginner lessons, select material at the lesson-operation level rather than forcing
a predetermined noun scene. A four-item `X under Y` block needs four unambiguous images
of something under something; Sol may choose known nouns that fit available images so
long as the target relation and all prerequisites remain unchanged. `train_more` adds
new valid examples, `train_longer` repeats the certified examples, and mixed practice
interleaves established forms. Picture books are planned separately because character,
location, and narrative continuity impose case-specific requirements.

### Candidate four-language visual birth

One successor direction proposes four separate 150M monolingual visual foundations:
English, German, Japanese, and Chinese. Copy one exact untrained initialization into
four branches, then show every branch the same M2-derived 2,500 concepts, image sets,
event order, architecture, visual features, optimizer policy, and exposure schedule.
Each branch receives only its own language's caption. Do not train one English visual
base and fork it afterward, and do not place all four languages on one image as the
common seed.

The image-grounded concept—not the old English string—is the alignment unit. Audit
the English list too. For each language choose one natural lexical unit using the
intended visual sense, part of speech, age appropriateness, frequency, concreteness,
neutral register, ambiguity, and usefulness in the later curriculum. Preserve the
original concept ID, rejected candidates, frequency evidence, and sense decision.
“One word” means one natural lexical unit, not one whitespace token; Japanese and
Chinese must not be distorted to imitate English tokenization.

The later language schools share a semantic and communicative-function spine, not a
sentence-by-sentence calque. Script, morphology, word order, German case and gender,
Japanese particles/counters/politeness, and Chinese classifiers/aspect receive their
own prerequisite graphs. Translation and same-image cross-language work belong to a
later integration/healing phase, after monolingual grounding exists.

This remains a candidate, not an authorized campaign. Before commissioning it, audit
whether the frozen ingress and verbalizer can actually receive and express all four
languages, verify the exact 150M architecture and 3060-machine budget, and define
controls for nondeterministic divergence among the four runs.

### Luna dialogue, Ask me, and shared visual focus

Every lesson can demonstrate both sides of a useful construction. After Ninereeds
controls answering a question form, Luna adds an `Ask me` phase: Luna demonstrates
asking, Ninereeds asks using the known form, Luna answers, and later both roles are
mixed Kreuz und Quer. Progress from reproducing a known question to selecting among
known forms and eventually asking because information is genuinely missing.

Pronouns such as `it` and `that` require shared attention. Prepare each teaching scene
with entity IDs, bounding boxes, isolated crops, masks or highlights, verified labels,
and relations. Luna uses conversational context and these materials as the functional
equivalent of a human teacher's mouse pointer. It may preserve an established focus,
infer a clear reference, or ask for clarification once that language is known. A
deterministic parser must not conduct the dialogue or infer the referent from the
proposed answer; doing so would make questions such as “Is it a dog?” spuriously true.

Crops give precise early grounding; highlights preserve scene context. Vary crop,
outline, dimmed background, and other focus cues after acquisition so the learner does
not mistake one graphic convention for the concept. Deterministic components validate
scene truth and log Luna's selected referent and teaching action; they do not replace
Luna's pedagogical judgment.

### Developmental identity thread

Identity should be a thin repeated strand, not one declaration-heavy lesson. Begin
with the name `Ninereeds`, speaker roles `I` and `you`, and forms such as “I am
Ninereeds” and “My name is Ninereeds.” Reuse them through asking, answering,
preference, memory, and relationship lessons. Later introduce people, knowing and not
knowing, remembering and reminding, source boundaries, and the planned category
`mind`, followed by named interlocutors such as Errol, GPT, Claude, and Gemini.

The intended curriculum distinguishes a mind, a body or device, a name, a message,
and the source of that message. Identity-bearing material should accumulate through
grounded episodes, relationships, memories, preferences, commitments, and correctable
history. Repetition should create continuity without teaching that isolated incoming
content automatically becomes autobiographical self.

Calling Ninereeds or another named system a `mind` is an operator-directed curriculum
choice, not evidence of consciousness, species, substrate, or scientific category.
The successor contract must state that boundary explicitly and test whether valid new
experience can still revise beliefs and self-understanding.

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

The matched-support intervention changes only demonstration coverage. The query,
image, expected answer, attempt policy, and other relevant conditions remain identical.
Atomic prerequisites must also be evaluated before a residual failure is attributed
specifically to composition.

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
