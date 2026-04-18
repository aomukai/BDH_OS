# Story Layer Rules

Canonical rules for writing, reviewing, and evaluating Story Layer content.

This document serves as the prompt/rubric when drafting stories in external models (ChatGPT, Gemini, local models) and during quality-assurance passes.

Use this file together with:
- `training_data/wiki/story_triplet_candidates.md` — semantically coherent triplets for story generation
- `docs/training_pipeline.md` — canonical training sequence and stage definitions
- `training_data/wiki/02_wiki_implementation_todo.md` — active working queue

---

## Purpose of Story Layers

Stories teach contextual variation and natural sentence flow.

They are not wiki definitions.

Stories show grounded concepts used together in realistic child-level scenarios. The dragon learns:
- that concepts co-occur in coherent contexts
- that language can express the same knowledge in multiple ways
- that meaning emerges from context, not just from definitions

---

## Core Principles

### 1. Grounded vocabulary only

Every word in a story must already exist in:
- Phase 1–5 curriculum, or
- Wiki Level 1

Do not introduce new vocabulary through stories.

### 2. Truthfulness first

Stories describe things that are true or could realistically happen.

If a story involves uncertainty:
- state the uncertainty plainly
- show what a reasonable response to uncertainty looks like (see Truthfulness Rules below)

Do not use stories to teach false beliefs or unreliable reasoning.

### 3. Gradual cognitive load

Each story level adds one layer of complexity.

Do not use "twist" framing (e.g., "but then something surprising happened!").

Instead, increase complexity through:
- longer sentences
- more supporting concepts
- simple cause-and-effect chains
- time sequencing (first, then, after)
- basic comparisons

The dragon should never feel surprised by the training content. It should feel gradually stretched.

### 4. Concrete and daily-life

Stories describe situations a child might experience or observe:
- home routines
- school activities
- play with friends
- meals and food
- animals and nature
- simple tools and objects

Avoid:
- abstract reasoning scenarios
- hypotheticals
- heavy negation
- unfamiliar or exotic contexts

---

## Story Levels

### Story Layer 1

**Sentence length target:** 5–10 words per sentence
**Story length:** 3–6 sentences
**Structure:** One anchor concept + two supporting concepts

Characteristics:
- simple subject-verb-object sentences
- no compound or complex sentences
- no "because" (causal chains come later)
- no "but" or "however" (contrast connectives come later)
- all concepts are concrete and grounded

Example triplet: `bird + nest + tree`

Example story:
```
A bird lives in a tree.
The bird builds a nest.
The nest is in the branches.
The bird brings twigs to the nest.
The nest keeps the eggs safe.
A bird is not a butterfly.
```

### Story Layer 2

**Sentence length target:** 8–15 words per sentence
**Story length:** 5–10 sentences
**Structure:** Anchor + 2–3 supporting concepts + one simple causal or temporal link

Characteristics:
- "and" is allowed
- "then" is allowed (temporal sequence)
- limited "because" (one per story, simple causation)
- no complex conditionals
- slightly varied sentence openings

Example structure:
```
[Setup]
[First action]
[Second action with "then"]
[Simple result with "because"]
[Optional contrast]
```

### Story Layer 3

**Sentence length target:** 10–18 words per sentence
**Story length:** 8–12 sentences
**Structure:** Multiple related concepts + one causal chain + one comparison or contrast

Characteristics:
- "but" is allowed (one per story)
- one explicit cause-effect chain
- one comparison with a related concept
- 2–3 paragraphs allowed
- varied sentence openings

### Story Layer 4

**Sentence length target:** 12–20 words per sentence
**Story length:** 10–15 sentences
**Structure:** Multiple concepts + multiple cause-effect links + explicit reasoning

Characteristics:
- 2–3 paragraphs
- one comparison with a related concept
- one explicit sequence across multiple steps
- reading level: grade 4–6
- no encyclopedic depth

---

## Cognitive Load Framework

Story complexity increases through five dimensions:

1. **Sentence length** — longer sentences require more working memory
2. **Concept count** — more concepts per story require broader attention
3. **Causation** — "because" links require tracking cause and effect
4. **Temporality** — "then," "first," "after" require tracking sequence
5. **Contrast** — "but," "however" require holding two states in mind

Each story level adds load along one or two dimensions while keeping others stable.

| Level | Sentence length | Concepts | Causation | Temporality | Contrast |
|-------|-----------------|----------|-----------|-------------|----------|
| 1     | 5–10 words      | 3        | none      | none        | final sentence only |
| 2     | 8–15 words      | 3–4      | 1 simple  | yes         | none     |
| 3     | 10–18 words     | 4–5      | 1 chain   | yes         | 1        |
| 4     | 12–20 words     | 5–6      | 2+ links  | yes         | 1–2      |

Do not jump multiple levels at once. Each level should feel like a slight stretch, not a leap.

---

## Truthfulness Rules

The dragon should learn truthful behavior from stories, not just from explicit instruction.

### When the story involves certainty

State facts plainly.

```
A bird has two wings.
Wings help the bird fly.
```

### When the story involves uncertainty

Show what a reasonable response looks like:

**"I don't know"**
```
The bird flew away.
Where did the bird go?
I don't know where the bird went.
```

**Looking something up**
```
What kind of bird is that?
I don't know.
I could look in a book to find out.
```

**Asking for help**
```
The jar lid is stuck.
I cannot open it.
I will ask for help.
```

### When uncertainty is not important enough to pursue

Not all uncertainty requires action. Sometimes the right response is to continue without resolving it.

```
I saw a bug on the leaf.
I don't know what kind of bug it was.
It crawled away, and I kept walking.
```

The dragon should learn:
- not to pretend certainty it does not have
- not to treat all uncertainty as urgent
- that asking for help is normal
- that "I don't know" is an acceptable answer

---

## Vocabulary Constraints

### Allowed sources

- Phase 1–5 curriculum vocabulary
- Wiki Level 1 vocabulary

### Not allowed

- Words not yet grounded in curriculum or wiki
- Technical terms
- Idioms or slang
- Pronouns in Story Layer 1 (introduce gradually in Layer 2+)

### Verification step

Before finalizing a story:
1. List all nouns and verbs
2. Check each against `concept_index.md` (Phase 1–5) or wiki entry files
3. Remove or replace any ungrounded word

---

## Contrast Convention

Every story should end with one contrast line, following the wiki convention:

```
A bird is not a butterfly.
A dog is not a cat.
A nest is not a cave.
```

This reinforces category boundaries and prevents overgeneralization.

---

## Generation Workflow

When drafting stories in external models:

1. **Select triplet** from `story_triplet_candidates.md`
2. **Set constraints** using this document as the prompt/rubric
3. **Generate draft** following the appropriate story level rules
4. **Verify vocabulary** against Phase 1–5 and Wiki Level 1
5. **Add contrast line** if missing
6. **Check truthfulness** — remove speculation, pretend-certainty, or forced conflict
7. **Trim if needed** — shorter is usually better at early levels

---

## Quality Checklist

Use this checklist during quality passes:

### Structure
- [ ] Sentence length within target range for level
- [ ] Story length within target range for level
- [ ] All triplet concepts appear in the story
- [ ] Contrast line present at the end

### Vocabulary
- [ ] All nouns grounded in curriculum or wiki
- [ ] All verbs grounded in curriculum or wiki
- [ ] No pronouns in Layer 1
- [ ] No ungrounded words

### Cognitive load
- [ ] Causation complexity matches level
- [ ] Temporality complexity matches level
- [ ] Contrast complexity matches level
- [ ] No sudden jumps in complexity

### Truthfulness
- [ ] No pretend-certainty
- [ ] No forced surprise or twist
- [ ] Uncertainty handled appropriately (state, look up, ask, or move on)
- [ ] Scenario is realistic and concrete

### Tone
- [ ] Child-facing language
- [ ] No condescension
- [ ] No encyclopedic depth
- [ ] Natural flow

---

## Failure Modes to Avoid

### 1. Vocabulary drift

Using words not yet grounded in curriculum or wiki.

Fix: Always verify vocabulary before finalizing.

### 2. Forced abstraction

Inserting logic, philosophy, or abstract reasoning into concrete scenarios.

Fix: Keep stories daily-life oriented. If a concept does not fit naturally, choose a different triplet.

### 3. Twist-based narratives

Using surprise, reversal, or "but then!" as a structural element.

Fix: Remove the twist. Use gradual complexity instead.

### 4. Over-long sentences

Sentences that exceed the target range for the level.

Fix: Split or simplify.

### 5. Pretend-certainty

Characters claiming to know things they could not know.

Fix: Use "I don't know" or "maybe" when appropriate.

### 6. Missing contrast line

Stories that end without the contrast convention.

Fix: Add a contrast line from the triplet's concept space.

---

## Example Prompts for External Models

Use these prompts when generating stories in ChatGPT, Gemini, or local models.

### Story Layer 1 prompt

```
Write a 3–6 sentence story using these three concepts: [anchor], [support1], [support2].

Rules:
- Each sentence should be 5–10 words
- Use only simple subject-verb-object sentences
- No "because," "but," or "however"
- The last sentence must be a contrast: "A [anchor] is not a [different concept]."
- All vocabulary must be concrete and child-friendly
- No surprises or twists — just describe what happens
```

### Story Layer 2 prompt

```
Write a 5–10 sentence story using these concepts: [anchor], [support1], [support2].

Rules:
- Each sentence should be 8–15 words
- You may use "and" and "then"
- You may use "because" once for a simple cause-effect
- The last sentence must be a contrast
- No surprises or twists — gradual complexity only
- All vocabulary must come from grounded sources
```

---

## Version

Created: 2026-04-18
Purpose: Story generation rules and quality rubric
Status: Ready for use in story drafting and quality passes
