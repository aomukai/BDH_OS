# Story Layer Rules

Canonical rules for writing, reviewing, and evaluating Story Layer content.

This document serves as the prompt/rubric when drafting stories in external models (ChatGPT, Gemini, local models) and during quality-assurance passes.

Use this file together with:
- `training_data/triplet_stories/story_tier_specs.md` — canonical Tier 1 / Tier 2 rewrite-stage shape and goals
- `training_data/wiki/story_triplet_candidates.md` — semantically coherent triplets for story generation
- `docs/training_pipeline.md` — canonical training sequence and stage definitions
- `todo.md` — active working queue

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

### 5. Dialogue enters in stages

Do not jump directly from definitional curriculum files into highly compressed quoted dialogue.

Use this progression:
- **Phase 6 bridge:** explicit proposition form
  - `What is a dog?`
  - `A dog is an animal.`
- **Story Layer 1:** narrated indirect discourse
  - `The child asks what a dog is.`
  - `The teacher says a dog is an animal.`
- **Story Layer 2:** quoted dialogue with speaker tags
  - `"What is a dog?" the child asks.`
  - `"A dog is an animal," the teacher says.`
- **Story Layer 3+:** only then allow short elliptical dialogue
  - `"What is that?"`
  - `"A dog."`

This progression avoids early collapse by keeping the referent, proposition, and speaker roles explicit before later compression.

### 6. Concrete and daily-life

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

**Canonical rewrite-stage spec:** `training_data/triplet_stories/story_tier_specs.md`

**Sentence length target:** short to medium child-readable sentences, usually about 5–10 words
**Story length:** 8 sentences
**Structure:** one anchor concept + two supporting concepts + one small concrete event

Characteristics:
- one main subject only
- clear beginning, middle, and end
- simple visible action over abstract explanation
- basic pronoun use is allowed only after the main subject is clearly introduced
- do not force names, multi-character tracking, or heavy discourse variation yet
- **dialogue:** use narrated indirect discourse only (no raw quotes)

Example triplet: `bird + nest + tree`

Example story shape:
```
[clear subject introduction]
[support concept enters the scene]
[simple action]
[another simple action]
[support concept matters again]
[safe pronoun use if clear]
[small settling or result]
[end inside the scene]
```

### Story Layer 2

**Canonical rewrite-stage spec:** `training_data/triplet_stories/story_tier_specs.md`

**Sentence length target:** short to medium child-readable sentences, often about 8–15 words
**Story length:** 12 sentences
**Structure:** one anchor + two supporting concepts + a longer event chain with one mild obstacle or change

Characteristics:
- scene-setting may come before the main subject introduction
- named characters may be introduced where useful (for example, `a boy named Timmy`)
- if a Tier 2 story assigns a recurring name, that name should be kept consistent in the corresponding Tier 3 and Tier 4 story thread via `training_data/triplet_stories/character_registry.md`
- noun → name → pronoun alternation should stay clear and easy to follow
- `and` is allowed
- `then` is allowed (temporal sequence)
- limited `because` is allowed (one simple causation per story)
- **dialogue:** quoted dialogue with explicit speaker tags is allowed (keep it sparing; do not use short elliptical dialogue)
- avoid complex conditionals and adult-sounding prose

Example structure:
```
[scene-setting]
[main subject introduction]
[name if useful]
[first action]
[support concept in action]
[longer event chain]
[one mild obstacle, delay, or surprise]
[clear resolution or settling point]
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
| 1     | 5–10 words      | 3        | none      | light event sequencing only | noun-to-pronoun introduction only |
| 2     | 8–15 words      | 3–4      | 1 simple  | yes         | noun → name → pronoun clarity |
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
- unclear pronouns in Story Layer 1

### Verification step

Before finalizing a story:
1. List all nouns and verbs
2. Check each against `concept_index.md` (Phase 1–5) or wiki entry files
3. Remove or replace any ungrounded word

---

## Ending Convention

Stories should usually end inside the scene rather than with a definition, slogan, or moral.

If a contrast line is used, it must feel grounded and helpful rather than mechanically appended.

---

## Generation Workflow

When drafting stories in external models:

1. **Select triplet** from `story_triplet_candidates.md`
2. **Set constraints** using this document together with `training_data/triplet_stories/story_tier_specs.md`
3. **Generate draft** following the appropriate story level rules
4. **Verify vocabulary** against Phase 1–5 and Wiki Level 1
5. **Check ending shape** — end inside the scene unless a grounded contrast is genuinely useful
6. **Check truthfulness** — remove speculation, pretend-certainty, or forced conflict
7. **Trim if needed** — keep early levels tight and readable

---

## Quality Checklist

Use this checklist during quality passes:

### Structure
- [ ] Sentence length within target range for level
- [ ] Story length within target range for level
- [ ] All triplet concepts appear in the story
- [ ] Ending matches the current tier spec

### Vocabulary
- [ ] All nouns grounded in curriculum or wiki
- [ ] All verbs grounded in curriculum or wiki
- [ ] Tier 1 pronouns appear only after the main subject is clearly introduced
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

### 6. Weak ending shape

Stories that end weakly because an old contrast template was removed but nothing better replaced it.

Fix: End inside the scene, or use a grounded contrast only when it truly helps.

---

## Example Prompts for External Models

Use these prompts when generating stories in ChatGPT, Gemini, or local models.

### Story Layer 1 prompt

```
Write an 8-sentence Tier 1 story using these three concepts: [anchor], [support1], [support2].

Rules:
- Keep the story concrete and easy for a young child to picture
- Use one main subject only
- Introduce the main subject clearly before using he, she, or it
- Show one small event using the anchor and both support concepts
- End inside the scene
- All vocabulary must be concrete and child-friendly
- No surprises or twists — just describe what happens
```

### Story Layer 2 prompt

```
Write a 12-sentence Tier 2 story using these concepts: [anchor], [support1], [support2].

Rules:
- Set the scene before or around the main subject when useful
- A simple recurring name may be introduced for the main subject
- Use a longer event chain with one mild obstacle, delay, or change
- Keep noun → name → pronoun references easy to follow
- You may use "and" and "then"
- You may use "because" once for a simple cause-effect
- Quoted dialogue with speaker tags is allowed when useful but should not become the default pattern
- End inside the scene
- All vocabulary must come from grounded sources
```

---

## Version

Created: 2026-04-18
Purpose: Story generation rules and quality rubric
Status: Ready for use in story drafting and quality passes
