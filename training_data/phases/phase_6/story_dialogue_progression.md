# Story Dialogue Progression

Canonical note for how dialogue should enter the training stack without causing an early collapse into brittle quoted-speech patterns.

## Principle

Dialogue should be introduced in a clean staged progression.

Do **not** jump directly from definitional curriculum files to sparse quoted dialogue like:
- "What is that?"
- "A dog."

That kind of exchange is useful later, but it is too compressed as an early bridge target.

## Clean progression

### Phase 6 bridge
Use explicit proposition-shaped teaching.

Example:
- "What is a dog?"
- "A dog is an animal."

This keeps the concept fully visible and structurally grounded.

### Story Layer 1
If interaction appears, move the exchange into narrated indirect discourse.

Example:
- "The child asks what a dog is."
- "The teacher says a dog is an animal."

This preserves full proposition structure while introducing interaction, but Story Layer 1 does not need dialogue in every story.

### Story Layer 2
Quoted dialogue with speaker tags may be introduced where useful.

Example:
- "What is a dog?" the child asks.
- "A dog is an animal," the teacher says.

This adds quotation marks and turn structure without collapsing the semantic content, but it should not become the default pattern for every Tier 2 story.

### Story Layer 3+
Only later allow highly compressed elliptical dialogue.

Example:
- "What is that?"
- "A dog."

This stage assumes the earlier layers already taught the full proposition and speaker-role mapping.

## Why this matters

This progression avoids early collapse because it keeps:
- the referent explicit
- the proposition explicit
- the speaker role explicit
- the answer structure explicit

Only after those are stable should the corpus rely on short elliptical dialogue.

## Implementation rule

When drafting Phase 6 files or Story Layer 1 examples:
- prefer full proposition forms
- if interaction appears, prefer narrated interaction over raw quotes
- do not introduce bare two-line dialogue exchanges as the primary early pattern

When drafting Story Layer 2:
- quoted dialogue is allowed
- keep speaker tags explicit
- do not overuse quoted dialogue or extremely short replies yet

When drafting Story Layer 3 and later:
- compressed replies are allowed when the referent is recoverable from context
- still avoid ambiguity for its own sake

## Intended use

Use this document together with:
- `training_data/phases/phase_6/phase_6_spec.md`
- `training_data/wiki/story_layer_rules.md`
- `docs/training_pipeline.md`

This note should guide both curriculum drafting and later story-generation prompts.