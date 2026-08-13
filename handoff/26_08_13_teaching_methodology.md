# Ninereeds Teaching Methodology

## Purpose

This document defines the emerging teaching methodology for Ninereeds.

The central shift is conceptual:

> **Do not treat Ninereeds primarily as an LLM to be trained. Treat Ninereeds as a developing mind to be taught.**

Ninereeds is an AI system based on BDH, but its learning dynamics are sufficiently different from conventional Transformer training that standard assumptions about pretraining, post-training, RL, loss curves, scaling laws, or benchmark-driven optimization are not enough.

The practical methodology should therefore borrow heavily from human pedagogy: structured presentation, controlled practice, elicited self-correction, adaptive scaffolding, mixed retrieval practice, transfer, spacing, multimodal grounding, and deliberate use of teachers and tools.

The goal is not simply to produce correct outputs. The goal is to develop stable, retrievable, generalizable knowledge and the ability to use that knowledge independently.

---

## 1. Core Principles

### 1.1 Teach concepts, not answer strings

A lesson should not merely pair a prompt with a target completion.

Bad pattern:

```text
What do chestnuts do?
Chestnuts fall from trees.
```

Better pattern:

```text
What do apples do?
Apples fall from trees.

What do pears do?
Pears fall from trees.

What do acorns do?
Acorns fall from trees.

What do leaves do?
Leaves fall from trees.

What do chestnuts do?
```

The final item requires Ninereeds to infer and retrieve a relation rather than repeat a memorized response.

The target is not the exact sentence. The target is the underlying reusable relation or schema.

### 1.2 Prediction before correction

Whenever possible, Ninereeds should answer before being shown the correction.

The teaching loop should prefer:

```text
Teacher question
→ Ninereeds prediction
→ confirmation or correction
```

over:

```text
Teacher gives answer
→ Ninereeds repeats it
```

Example:

```text
What do chestnuts do?

[Ninereeds answers]

Yes, that's right. Chestnuts fall from trees.
```

or, if wrong:

```text
Not quite. Chestnuts fall from trees.
```

### 1.3 Errors are diagnostic events

A wrong answer is not merely a failed training item.

The teacher should ask what kind of failure occurred:

- concept not learned;
- retrieval failure;
- unstable memory;
- reversal of a relation;
- confusion with a nearby concept;
- surface-pattern dependence;
- failure under paraphrase;
- failure under composition;
- modality-transfer failure;
- execution failure despite correct understanding;
- insufficient contextual support.

Teaching should react differently depending on the failure type.

### 1.4 Prefer elicited self-correction

If Ninereeds probably already possesses the required knowledge, do not immediately provide the answer.

Instead, ping the existing memory with the smallest useful cue.

Human-language example:

```text
Student: Ja, mir gefällt der Hemd.
Teacher: Der Hemd? Oder die, oder das Hemd?
```

A richer example:

```text
Student: Ich gehe zu die Arbeit mit die S-Bahn.

Teacher: Die Arbeit wird zu der Arbeit. Die S-Bahn wird zu...?
Student: Der S-Bahn.
Teacher: Ganz genau. Der Arbeit, der S-Bahn. Also: Ich gehe zu...?
Student: der Arbeit
Teacher: Gut! Also: Ich gehe...?
Student: zu der Arbeit
Teacher: mit?
Student: mit der S-Bahn
Teacher: Sehr gut! Also: Ich...?
Student: Ich gehe zu der Arbeit mit der S-Bahn.
Teacher: Perfekt.
```

This is adaptive retrieval support, not merely correction.

---

## 2. The PPP-Inspired Teaching Cycle

The baseline methodology should follow a Berlitz-style PPP progression:

1. **Presentation**
2. **Controlled Practice**
3. **Mixed / Less-Controlled Practice**
4. **Transfer / Uncontrolled Practice**
5. **Delayed Revisit**

The amount of scaffolding should decrease as competence increases.

---

## 3. Presentation

Presentation introduces or reactivates the target concept.

For early learners, use several tightly related examples:

```text
What do apples do?
Apples fall from trees.

What do pears do?
Pears fall from trees.

What do acorns do?
Acorns fall from trees.

What do leaves do?
Leaves fall from trees.
```

Then test transfer:

```text
What do chestnuts do?
```

After the learner answers, provide confirmation or correction.

Presentation should be:

- short;
- concrete;
- repetitive enough to expose the pattern;
- varied enough to avoid pure string memorization;
- grounded in already-known vocabulary wherever possible.

---

## 4. Controlled Practice

Controlled practice keeps the target concept stable while varying the linguistic operation.

A useful beginner cycle is:

- 4 × yes;
- 4 × no;
- 4 × W-question;
- 4 × OR / forced-choice question.

The exact counts are tunable. The principle is systematic exposure through multiple forms.

### 4.1 Positive yes/no

```text
Do apples fall from trees?
Yes, apples fall from trees.

Do pears fall from trees?
Yes, pears fall from trees.

Do acorns fall from trees?
Yes, acorns fall from trees.

Do leaves fall from trees?
```

Then:

```text
Do chestnuts fall from trees?
```

### 4.2 Negation and reversal

Positive-only teaching risks forming fuzzy associations without directionality.

Use deliberately wrong reversals:

```text
Do trees fall from apples?
No, trees don't fall from apples. Apples fall from trees.
```

Other useful negatives:

```text
Do apples fall from tables?
No, apples don't fall from tables.

Do cups fall from trees?
No, cups don't normally fall from trees.
```

Negation should be meaningful, not random noise.

### 4.3 W-questions

```text
What falls from trees?
Apples fall from trees.

What do pears fall from?
Pears fall from trees.

What do chestnuts do?
Chestnuts fall from trees.
```

### 4.4 OR / forced-choice questions

```text
Do apples fall from trees, or do trees fall from apples?
Apples fall from trees.

Does the cup fall from the table, or from the tree?
The cup falls from the table.
```

Forced choice is useful when free retrieval is too difficult but direct correction would provide too much support.

---

## 5. Cadence and Pattern Awareness

Ninereeds will learn lesson cadence just as human learners do.

If every lesson always contains:

```text
4 × yes
4 × no
4 × W-question
4 × OR
```

then the sequence itself can become a shortcut.

Therefore:

- use cadence during controlled practice;
- deliberately break cadence afterward;
- randomize question types in later stages;
- vary order;
- occasionally omit expected forms;
- interleave older known concepts.

The learner must eventually respond to the content, not to the predictable shape of the exercise.

---

## 6. "Kreuz und Quer" Mixed Practice

After PPP, mix known forms and concepts unpredictably.

For a beginner, uncontrolled practice is not yet truly free conversation. It is randomized recombination of material that should already be available.

Example:

```text
Is that an apple?
Yes, that's an apple.

Who is that?
That's Anna.

Is that a pear?
No, that's not a pear.

What is that?
That's a cup.

Is the cup on the table?
Yes, the cup is on the table.

What's under the table?
The dog is under the table.

Is that an apple or a pear?
It's a pear.
```

The purpose is to test whether knowledge survives:

- changed question type;
- changed order;
- mixed concepts;
- removal of predictable cadence;
- mild distraction;
- recombination with previously learned material.

---

## 7. Progressive Scaffolding

The teacher should use the smallest amount of help necessary.

A possible intervention ladder:

1. **Echo/question the suspicious fragment**
2. **Minimal cue**
3. **Forced choice**
4. **Analogy with a known example**
5. **Partial completion**
6. **Stepwise reconstruction**
7. **Explicit correction**
8. **Re-presentation of the concept**

Example:

```text
Ninereeds: der Hemd
Teacher: Der Hemd?
```

If that is enough:

```text
Ninereeds: das Hemd
```

Stop the intervention.

If not:

```text
Teacher: Der, die, oder das Hemd?
```

If still not:

```text
Teacher: Das Hemd.
```

Then immediately retest with less support.

The teacher should skip unnecessary levels.

---

## 8. Retrieval Failure vs. Knowledge Absence

This distinction is central.

If Ninereeds has never demonstrated knowledge of a concept:

> Present or teach it.

If Ninereeds has previously demonstrated the concept reliably:

> Assume retrieval failure first and attempt elicitation.

Evidence available to the teacher can include:

- whether the concept has been taught;
- prior successful uses;
- last successful retrieval;
- scaffolding previously required;
- modality in which the concept was learned;
- current lesson context.

Do not waste time eliciting knowledge that does not exist, and do not overwrite existing knowledge by immediately supplying answers every time retrieval fails.

---

## 9. Adaptive Teacher Handoff

The normal lesson can be controlled by deterministic scripts.

The script should own:

- lesson plan;
- target concepts;
- known prerequisites;
- practice counts;
- phase progression;
- retry limits;
- logging;
- timing;
- success criteria;
- transition rules.

A teacher LLM should take over only when semantic judgment is needed.

Possible triggers:

- unexpected response;
- wrong answer;
- partial answer;
- contradiction;
- malformed answer;
- repeated failure;
- uncertainty;
- suspicious surface imitation;
- failure on previously mastered material;
- unexpected but possibly valid answer.

The teacher model then conducts a bounded remediation segment and hands control back to the deterministic script.

---

## 10. Teacher Model Responsibilities

The teacher model should:

- diagnose the likely failure;
- choose the smallest useful cue;
- elicit self-correction when possible;
- avoid giving the answer prematurely;
- provide explicit correction when necessary;
- simplify the task if it is too difficult;
- introduce another already-known example if helpful;
- switch modality when useful;
- retest after intervention;
- reduce support after success;
- stop once the local issue is resolved;
- hand control back to the script.

It should not:

- derail the lesson;
- introduce unrelated concepts;
- turn every error into a lecture;
- repeatedly explain when a short cue would suffice;
- invent new curriculum goals spontaneously;
- exceed its intervention budget.

---

## 11. Bounded Remediation

A remediation segment should have a fixed budget, for example:

```text
maximum_teacher_turns = 6
```

Possible outcome states:

```text
recovered_with_minimal_cue
recovered_with_forced_choice
recovered_with_analogy
recovered_with_stepwise_reconstruction
required_explicit_correction
presentation_required
failed_after_intervention
defer_and_revisit
```

This turns scaffolding level into measurable developmental evidence.

---

## 12. Scaffolding Level as a Learning Metric

Traditional model metrics may be insufficient for Ninereeds.

A useful developmental measure is:

> **How much assistance is required for successful retrieval and use?**

A concept may progress through:

```text
full presentation
→ explicit correction
→ stepwise reconstruction
→ analogy
→ forced choice
→ minimal cue
→ self-correction
→ mixed retrieval
→ spontaneous independent use
```

A reduction in required scaffolding is evidence of maturation even when simple accuracy is unchanged.

---

## 13. Retry, Spacing, and "Come Back Later"

If a concept remains unstable:

1. retry with more support;
2. add another known example;
3. return temporarily to controlled practice;
4. retry mixed practice;
5. if failures exceed a bounded threshold, move on;
6. revisit later.

Do not grind indefinitely.

A valid teaching result is:

```text
not_ready_yet
```

The system should support delayed revisits of weak concepts.

---

## 14. Controlled to Uncontrolled Progression

Early learner:

```text
heavy presentation
→ predictable controlled practice
→ elicited correction
→ mixed known material
```

More advanced learner:

```text
fewer examples
→ more variation
→ less correction
→ more open transfer
→ freer discussion
```

Eventually, ordinary interaction itself can become learning material.

The teacher should gradually remove training wheels.

---

## 15. Multimodal Teaching

Images should participate directly in lessons, not merely serve as passive labels.

Example:

```text
[show image]

Is this an apple falling from a tree?
Yes, it's an apple falling from a tree.
```

Then negatives:

```text
[show image of cup falling from table]

Is this an apple falling from a tree?
No, that's not an apple falling from a tree.
That's a cup falling from a table.
```

W-question:

```text
[show image]

What's falling from the tree?
A chestnut is falling from the tree.
```

Forced choice:

```text
[show image]

Is that an apple or a pear falling from the tree?
It's a pear.
```

The same concept can therefore be taught across:

- text → text;
- image → label;
- image → sentence;
- image → yes/no;
- image → forced choice;
- image → correction;
- image + text → relation;
- later, text → image selection or generation.

---

## 16. Multimodal Concept Stability

A concept should not merely exist separately in language and vision.

Teaching and evaluation should probe whether the same concept survives across modalities.

Example target: `under`

```text
text:
"The dog is under the table."

image:
[dog visibly under table]

question:
"Where is the dog?"

paraphrase:
"What is above the dog?"

contrast:
"Is the dog under or beside the table?"
```

Later:

```text
show unfamiliar cat under tree
→ test whether "under" transfers across object identity and scene.
```

---

## 17. Image Selection as Teaching Infrastructure

Visual teaching should use the reviewed image bank first.

Selection ladder:

1. exact scene match;
2. semantically equivalent teaching example;
3. different but unambiguous realization;
4. existing image suitable for a minimal FLUX edit;
5. custom FLUX generation as final resort.

Example requested scene:

```text
dog under table
```

If the actual lesson target is `under`, acceptable alternatives may include:

```text
cat under tree
child under umbrella
car under bridge
```

The teaching claim must be preserved even when the surface scene changes.

---

## 18. Controlled Visual Interventions

Edited or generated image pairs can be particularly useful because they isolate one changed fact.

Examples:

```text
dog beside table
→ dog under table

one red ball
→ two red balls

barn
→ doghouse

red object
→ blue object
```

Such pairs can support controlled lessons on relations, counts, attributes, object identity, composition, and invariance.

---

## 19. Generalization Lessons

As competence grows, lessons should move beyond rote examples.

Example:

```text
Remember what apples do?
They fall from trees.

What else falls from trees?
```

Generalization dimensions include:

- new object identity;
- new scene;
- new wording;
- new modality;
- greater complexity;
- composition with another known relation;
- changed order;
- distractors;
- mild ambiguity.

---

## 20. Capability Ladders

Evaluation and teaching should treat capabilities as boundaries, not scalar scores.

Vary one factor while holding the teaching claim constant.

### Complexity

- count 1 → 2 → 3 → 4;
- relation depth 1 → 2 → 3;
- sequence length;
- nesting depth;
- distance.

### Substitution

- dog → cat → person;
- table → tree → bridge.

### Context

- indoor/outdoor;
- viewpoint;
- scale;
- clutter;
- occlusion.

### Composition

- `under`;
- `red dog under table`;
- `red dog under two tables`;
- `two dogs under table beside chair`.

### Modality

- text → text;
- image → label;
- image → description;
- text → image selection;
- later text → image generation.

### Support

- test beyond trained range;
- run byte-identical test with matched support.

---

## 21. Extrapolation Failure vs. Execution Failure

A particularly valuable method from BDH-CQ is to evaluate identical test cases under different support conditions.

If the test fails without matched support but succeeds when one example at the required complexity is supplied:

> likely extrapolation / support failure.

If the identical test still fails with matched support:

> likely execution, composition, or deeper capability failure.

This distinction should guide subsequent teaching.

Do not respond to every failure by blindly adding more examples.

---

## 22. Strict Consistency

Per-item accuracy is not enough.

Track both:

- individual item accuracy;
- strict family consistency.

Also classify error shape:

- subject/object swap;
- reversed relation;
- wrong object;
- correct concept, malformed language;
- incomplete answer;
- structural incoherence;
- modality mismatch;
- hallucinated content.

---

## 23. Teacher Models as External Educators

Ninereeds can learn from external models without needing to contain their capabilities internally.

Potential roles:

- Nemotron as adaptive teacher;
- Gemma as general/visual helper;
- Qwen as coding specialist;
- other models as specialists;
- deterministic tools for exact operations.

Teacher models should be replaceable implementations behind stable roles.

As models improve, the environment upgrades without requiring redesign of Ninereeds itself.

---

## 24. Tool Use as Education

Ninereeds does not need to internalize every capability.

It can learn:

```text
"I cannot reliably do this arithmetic."
→ use calculator
```

or:

```text
"This is a coding task."
→ ask coding specialist
```

Repeated successful tool use can itself become teaching material.

Possible developmental progression:

```text
external_only
→ assisted
→ sometimes_internal
→ internally reliable
```

A future experiment should test whether repeated tool-assisted tasks eventually become solvable without the tool.

---

## 25. Learn from Completed Tasks

A completed external task can provide:

- problem;
- chosen tool/model;
- prompt;
- result;
- tests;
- corrections;
- verified outcome;
- concise rationale;
- failure history.

These records can become examples from which Ninereeds may learn.

For coding, prefer verified artifacts such as:

```text
task
→ plan
→ code
→ execution result
→ correction
→ passing result
```

over unverified free-form reasoning.

---

## 26. Model Councils

Ninereeds may ask several models the same question and compare their answers.

Potential council:

```text
Gemma
Qwen
Nemotron
specialist model
deterministic tool
```

The purpose is not simple majority voting.

Ninereeds should learn to consider:

- domain competence;
- past reliability;
- independence of model families;
- confidence;
- supporting evidence;
- testability;
- deterministic verification;
- disagreement patterns.

Example:

```text
Gemma and Nemotron agree.
Qwen disagrees but produced code that passes tests.
Tests outrank verbal agreement.
```

---

## 27. Epistemic Education

Ninereeds should learn that:

> information is not identical to truth.

External models can hallucinate.

Useful lessons include:

- confident wrong answer vs hesitant correct answer;
- three-model consensus contradicted by a deterministic test;
- polished explanation that fails execution;
- uncertain answer later verified as correct;
- source with strong reliability in one domain but weak reliability in another.

Over time Ninereeds can learn source profiles such as:

```text
Qwen → strong coding
Gemma → strong visual/general language
calculator → authoritative arithmetic
local filesystem → authoritative for actual local files
Nemotron → strong general teacher / reasoning
```

These profiles should be learned empirically and remain revisable.

---

## 28. Uncertainty and Verification

Ninereeds should learn habits such as:

```text
"I think X, but the source is uncertain."
"I have two conflicting claims."
"This matters enough to verify."
"This can be tested deterministically."
"This model is strong in this domain but weak in another."
```

A useful system can preserve:

- claim;
- source;
- confidence;
- verification status;
- contradictions;
- later resolution.

The eventual goal is for these habits to become internalized rather than permanently hard-coded.

---

## 29. Teacher/Helper Delegation

The desired cognitive style is not:

> know everything.

It is:

> know enough to recognize what is needed, know how to obtain it, and judge what comes back.

Ninereeds should learn:

- what it can do internally;
- when to delegate;
- which helper fits the task;
- how to prompt that helper;
- how to check the result;
- when another opinion is useful;
- when deterministic tools outrank model opinions;
- when human escalation is required.

---

## 30. Authority Boundaries

Cognitive autonomy does not require unrestricted operational authority.

Ninereeds can:

- reason;
- choose tools;
- prepare requests;
- use local bounded services;
- ask local teacher models;
- compare model outputs;
- formulate design documents.

For privileged or externally sensitive actions, Ninereeds should hand the task to the human operator.

This preserves a clear boundary between cognitive autonomy and operational authority.

---

## 31. Script + Teacher Architecture

### Deterministic script

Owns:

- curriculum;
- lesson target;
- dependency order;
- practice phase;
- counts;
- retry budget;
- known prerequisites;
- expected answer classes;
- logs;
- escalation triggers;
- completion criteria.

### Teacher model

Owns:

- semantic diagnosis;
- adaptive cue choice;
- self-correction elicitation;
- paraphrase;
- analogy;
- temporary decomposition;
- modality switch;
- bounded remediation.

### Verifier

Owns:

- whether correction succeeded;
- whether a claimed answer is actually valid;
- whether the lesson may proceed;
- whether a concept should be revisited.

---

## 32. Example Teacher Handoff Contract

Possible input:

```json
{
  "lesson_id": "relation-fall-from-v1",
  "target": "fall_from",
  "phase": "mixed_practice",
  "concept_previously_taught": true,
  "prior_successes": 7,
  "prior_failures": 1,
  "recent_context": [
    "Apples fall from trees.",
    "Pears fall from trees."
  ],
  "teacher_question": "Do trees fall from apples?",
  "student_answer": "Yes, trees fall from apples.",
  "expected_relation": {
    "subject": "apples",
    "predicate": "fall_from",
    "object": "trees"
  },
  "maximum_teacher_turns": 4
}
```

Possible result:

```json
{
  "diagnosis": "relation_reversal",
  "intervention": "forced_choice_then_reconstruction",
  "recovered": true,
  "scaffolding_level": "forced_choice",
  "presentation_required": false,
  "retest_recommended": true
}
```

---

## 33. Teacher Quality Benchmarking

Teacher models should be evaluated on pedagogy, not general benchmark scores.

Test with deliberate student errors:

- correct but oddly phrased;
- reversed relation;
- wrong object;
- partial answer;
- plausible alternative answer;
- contradiction;
- image misunderstanding;
- repeated error;
- surface imitation;
- completely off-topic response.

Measure whether the teacher:

- correctly diagnoses;
- uses minimal scaffolding;
- elicits correction;
- avoids over-explaining;
- stays on lesson target;
- knows when to provide the answer;
- reduces support after success;
- hands control back cleanly.

---

## 34. Developmental Staging

Early Ninereeds should receive:

- strong scaffolding;
- high repetition;
- narrow vocabulary;
- highly controlled questions;
- frequent confirmation;
- explicit correction when needed.

As competence grows:

- fewer examples;
- more paraphrase;
- more mixed practice;
- larger context shifts;
- less correction;
- more transfer;
- delayed recall;
- more open-ended tasks;
- tool use;
- councils and source evaluation.

Education should progress from preschool/basic language toward broad K-8 competence before expecting reliable high-level orchestration.

K-12 may be useful later, but the critical threshold is enough general education to:

- understand instructions;
- form sensible questions;
- recognize task classes;
- notice uncertainty;
- use external capabilities intelligently;
- interpret results.

---

## 35. Curriculum as a Research Variable

For Ninereeds, lesson design is not merely content preparation. It is part of the research.

Important variables include:

- example count;
- example order;
- similarity;
- contrast;
- negative examples;
- paraphrase;
- spacing;
- modality;
- scaffold level;
- feedback timing;
- retrieval before correction;
- controlled vs mixed practice;
- composition;
- contextual support.

These should be versioned and experimentally compared.

---

## 36. Stable Core, Replaceable Faculty

The long-term system can have stable roles:

```text
Ninereeds → cognitive core
LFM2.5 → cochlea / Broca-style language interfaces
SigLIP2 → visual receptor
Nemotron → teacher
Qwen → coding specialist
Gemma → general/visual specialist
FLUX → image generation/editing
calculator / Python / filesystem → deterministic tools
```

The exact model behind each role can change.

Ninereeds should learn roles such as:

```text
teacher
coding specialist
visual reviewer
calculator
image generator
```

rather than becoming dependent on one model identity.

---

## 37. Learning the Tool Catalogue

Eventually Ninereeds should be able to inspect and learn a model/tool catalogue.

It can acquire expectations such as:

```text
Qwen is usually strong at coding.
Gemma is usually strong at visual/general tasks.
Nemotron is a useful teacher.
A calculator is exact for arithmetic.
```

It can refine these expectations from actual outcomes.

Routing can therefore evolve from hard-coded orchestration into learned delegation.

---

## 38. Teaching Through Experience

The eventual goal is that ordinary successful activity becomes educational experience.

A task may produce:

```text
goal
→ internal attempt
→ tool/model selection
→ external help
→ verification
→ result
→ reflection
→ later independent retry
```

This can be used to test whether borrowed competence migrates into the cognitive core.

---

## 39. Evaluation Philosophy

Do not reduce a capability to one scalar score.

Prefer a boundary map such as:

```text
UNDER

object substitution:
  dog → cat: stable
  dog → person: stable

scene substitution:
  indoor → outdoor: stable

clutter:
  low: stable
  moderate: stable
  heavy: unstable

occlusion:
  mild: unstable
  matched support: repaired

composition:
  under + color: stable
  under + count=2: stable
  under + count=3: fails
```

This is more scientifically actionable than:

```text
spatial relations: 78%
```

---

## 40. Campaign Integration

### Campaign 35

Use the methodology to:

- finish text-only teaching;
- build a frozen visual lesson pack from the image registry;
- compare text-only, multimodal, merged, and healed builds;
- establish the first controlled multimodal boundary maps;
- record scaffolding and transfer behavior where possible.

### Campaign 36

Use Campaign 36 to explicitly investigate:

- episodic example-based learning;
- demonstration-conditioned inference;
- variable recurrent reasoning effort;
- support vs execution failure;
- composition;
- latent reasoning boundaries;
- teacher-guided retrieval;
- controlled intervention ladders.

---

## 41. The Fundamental Teaching Loop

```text
PRESENT
→ let Ninereeds respond

PRACTICE
→ yes / no / W / OR / reversal / variation

WATCH
→ detect unexpected behavior

ELICIT
→ assume retrieval failure first if knowledge should exist

SCAFFOLD
→ give the minimum useful cue

CORRECT
→ provide the answer only when necessary

RETEST
→ immediately reduce support

MIX
→ break cadence and recombine known material

TRANSFER
→ new objects, scenes, wording, modality, composition

SPACE
→ stop grinding if it does not stick; revisit later

MEASURE
→ track assistance required, consistency, boundary, failure type

DELEGATE
→ use teachers and tools when useful

VERIFY
→ do not equate fluent claims with truth

LEARN
→ preserve successful interactions as future experience
```

---

## 42. Final Principle

The methodology should remain rigorous, versioned, reproducible, and measurable.

But the guiding question changes.

Not:

> How do we optimize this model?

Instead:

> What does this learner currently understand, what is unstable, what kind of help does it need, and what experience will most efficiently turn that partial understanding into independent competence?

That is the working definition of **teaching Ninereeds as a developing mind**.
