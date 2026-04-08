This is already a strong plan—you just need it tightened into something **clean, structured, and executable** so Claude (or you) can follow it without ambiguity.

Here’s a rewritten version that keeps everything but makes it sharper, more systematic, and easier to act on:

---

# Curriculum Expansion Plan (Post Phase 1–5)

## Goal

Move from structured curriculum sentences to **controlled natural language**, without introducing chaos.

The objective is **not expertise**, but:

* exposure to clear, rational text
* reinforcement of known concepts
* gradual increase in linguistic flexibility

The model should learn to express the **same knowledge in different forms**, not learn new domains.

---

## Scope

* Base all content on **existing curriculum concepts (P1–P5)**
* Estimated concept set: ~500
* Topics should remain:

  * concrete
  * familiar
  * already grounded in training

Examples:

* animals: dog, cat, fish, bird
* environments: river, sea, house
* objects: car, bowl, tree
* processes: rain, growth

---

## Core Method: Concept → Snowflake Expansion

Each concept is built from a **concept card**, then expanded into text levels.

---

## Concept Card Structure

Each concept must define:

**Identity**

* category
* supercategory

**Core facts (5)**

* essential properties and behaviors

**Relations (3)**

* links to other known concepts

**Contrasts (1–2 pairs)**

* include both directions

  * dog ≠ cat
  * cat ≠ dog

**Actions / states (1–2)**

* typical behaviors or conditions

**Optional boundary**

* explicit exclusion if needed

  * “a whale is not a fish”

---

### Example (Dog)

Core facts:

* a dog is an animal
* many dogs live with people
* dogs have fur, four legs, and teeth
* dogs can bark, run, and play
* dogs come in many breeds

Relations:

* dog ↔ person
* dog ↔ house
* dog ↔ other dogs

Contrast:

* a dog is not a cat
* not all animals are dogs

---

## Additional Constraints (Stability Layer)

To prevent drift:

**Canonical forms**

* dog / dogs / puppy

**Allowed verbs (small set)**

* run, bark, eat, sleep, play

**Allowed adjectives**

* furry, friendly, loud

**Common sentence frames (2–3)**

* “This is X.”
* “X is Y.”
* “X has Z.”

---

## Text Generation Levels

Each concept expands into four levels:

---

### Level 1 — Gist (5–6 sentences)

Purpose:

* bridge curriculum → text

Rules:

* identity + 2–3 facts + 1 relation
* no clauses
* no “because”
* no lists

---

### Level 2 — Simple Text (10–12 sentences)

Purpose:

* introduce flow

Add:

* “and”, “but”, limited “because”
* slightly varied phrasing

---

### Level 3 — Expanded Text (150–250 words)

Purpose:

* introduce reasoning structure

Add:

* one causal chain
* one contrast

Example:

* “Dogs bark because they react to sounds, but they are not cats.”

---

### Level 4 — Full Article (300–500 words)

Purpose:

* natural short-form explanation

Allow:

* 2–3 paragraphs
* varied sentence openings
* one comparison with a related concept

Constraints:

* reading level: grade 4–6
* no encyclopedic depth

---

## Hard Language Rules

* max sentence length:

  * early: 12–15 words
  * later: 18–20 words

* max clause depth: 1

* avoid passive voice until Level 4

* use only allowed connectives

---

## Cluster-Based Construction

Do not build isolated concepts.

Build **clusters**:

Examples:

* dog, cat, pet, house, bowl
* fish, pond, river, water, boat
* bird, tree, nest, sky, worm
* car, road, driver, wheel, fuel

Reason:

> Concepts strengthen when their neighbors are learned together.

---

## Cross-Concept Texts (Important)

Each cluster should include:

* comparison texts

  * “Dogs and cats”

* relation texts

  * “A pet in a home”

This builds:

* boundaries
* relational understanding

---

## QA Layer (Retrieval Training)

After Level 2 and Level 3, include 2–3 Q→A pairs:

Example:

* What is a dog? → A dog is an animal.
* Where do dogs live? → Many dogs live with people.

Purpose:

* improve recall
* reduce drift during prompting

---

## Dataset Scale

Target:

* ~500 concepts
* ~500 words max per concept
* total ≈ 250k words

This is:

* large enough for structure learning
* small enough to stay controlled

---

## Training Strategy

* mix levels:

  * ~50% Level 1–2
  * ~50% Level 3–4

* always keep earlier levels present

* introduce new data with **low LR**

* avoid narrow fine-tune passes (already proven harmful)

---

## Failure Modes to Avoid

**1. Over-regularity**

* everything sounds identical
  → fix with controlled variation (Phase 1B idea)

**2. Over-entropy**

* too many new patterns at once
  → fix with constraints and gradual expansion

---

## Key Principle

> First teach meaning.
> Then teach variation.
> Then teach flow.

---

## Bottom Line

This approach will:

* scale cleanly
* preserve semantic clarity
* gradually expand linguistic flexibility

The model learns:

> not just facts,
> but how to express the same fact in multiple ways.