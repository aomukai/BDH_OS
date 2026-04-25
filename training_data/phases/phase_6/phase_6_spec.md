# Phase 6 Bridge Spec

Canonical planning doc for the post-Phase-5 bridge curriculum.

## Goal

Teach the missing scaffold vocabulary that the dragon needs before Story Layer 1 and later higher-level wiki/story reasoning, while preserving the controlled style of the earlier curriculum.

## Why this exists

Phase 1–5 gives the dragon a concrete early language foundation, but it still under-teaches words like:
- `word`
- `sentence`
- `thought`
- `idea`
- `true`
- `real`
- `question`
- `answer`
- `plan`
- `goal`
- `rule`
- `fair`
- `money`

The bridge should fill those gaps without jumping straight into unconstrained story prose.

## Core rule

Do not treat Phase 6 as a random word bucket.

Each concept family should be taught through:
1. a small word set
2. a minimal pattern grid
3. repeated controlled substitutions
4. simple dependency order

## Minimal pattern grid

Each major concept group should define 2–4 required patterns.

### Meta-language
- "A word is a unit of language."
- "A sentence is a group of words."
- "What is a sentence?"
- "This sentence has five words."

### Thought / knowledge
- "A child thinks about the problem."
- "The child knows the answer."
- "The child does not know the answer."
- "How does the child learn?"

### Truth / reasoning
- "This statement is true."
- "This statement is not true."
- "The reason is that ..."
- "Why does this happen? Because ..."

### Communication
- "The child asks a question."
- "The teacher answers the question."
- "The child explains the answer."
- "The student repeats the sentence."

### Planning / sequence
- "First, the child reads."
- "Next, the child writes."
- "The goal is to finish the task."
- "The child follows the steps."

## Candidate first bridge families

### Family A — Meta-language
Priority words:
- word
- sentence
- question
- answer
- meaning

### Family B — Thought / knowledge
Priority words:
- thought
- idea
- think
- know
- learn
- understand

### Family C — Truth / reasoning
Priority words:
- true
- real
- fact
- opinion
- reason
- because

### Family D — Communication control
Priority words:
- ask
- answer
- explain
- say
- repeat

### Family E — Planning / sequence
Priority words:
- plan
- goal
- step
- first
- next
- follow

## File-shape expectations

Unless a later explicit decision changes this, the first implementation pass should stay close to the established curriculum discipline:
- 4 `[user]` / `[assistant]` blocks per file
- strongly controlled wording
- repeated pattern frames
- no unnecessary flourish
- gradual introduction of new terms

Open design question for implementation:
- whether every bridge file should keep the exact Phase 1–5 five-line assistant structure, or whether a slightly relaxed bridge-specific format is acceptable

Current default: **stay as close as possible to the existing curriculum format until a human explicitly approves a divergence**.

## Recommended implementation order

1. Finalize the bridge word families.
2. Finalize the minimal pattern grid for each family.
3. Decide the exact file format contract.
4. Create a manifest of planned bridge files.
5. Draft the first file batch.
6. Audit the batch for vocabulary leakage and pattern drift.
7. Only after that, connect it to Story Layer 1 generation rules.

## Deliverables Gemini CLI can work on

1. A bridge manifest listing the planned file order.
2. A first-pass Phase 6 file set for the top-priority families.
3. A vocabulary-leak audit comparing each draft against earlier curriculum support.
4. A pattern-grid compliance check for each file.
5. A sync pass on `missing_curriculum_terms.md`, `docs/training_pipeline.md`, and `training_data/wiki/story_layer_rules.md`.
