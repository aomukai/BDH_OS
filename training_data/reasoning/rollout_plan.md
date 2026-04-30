# Reasoning Corpus Rollout Plan

This document outlines the executable plan for creating the standalone reasoning corpus. The goal of this corpus is to provide a structured, sequential, and rigorous foundation for logical, mathematical, and causal reasoning.

## Global Invariants

All files and entries created for the reasoning corpus MUST adhere to the following invariants.

### 1. Canonical Entry Format

Every entry in every file must include the following three representations to ensure the model learns to map between symbolic, verbal, and grounded contexts:

1.  **Symbolic Mode:** The core logical or mathematical operation in its most compact, symbolic form.
    *   *Example:* `5 + 3 = 8`
2.  **Verbal Mode:** The symbolic operation translated into a direct, non-narrative verbal statement.
    *   *Example:* `Five plus three equals eight.`
3.  **Grounded Story Mode:** A short (2-4 sentence) narrative that grounds the abstract operation in a concrete, real-world scenario.
    *   *Example:* `A girl has 5 apples. A boy gives the girl 3 more apples. Now the girl has 8 apples.`
4.  **Reasoning Chain:** A brief, explicit explanation of the underlying principle or state change.
    *   *Example:* `The number of apples increased because a new group was added.`

### 2. Stateful Reasoning

All answers, especially in story-based problems, must be explained with a short, explicit reasoning chain. The model should not only provide the correct answer but also articulate the state change or logical principle that led to it.

### 3. Number Distance Language

Explanations involving numerical operations should consistently use "step" and "distance" terminology where appropriate to reinforce the concept of magnitude and the relationships between numbers on a number line.

### 4. Allowed Format Exception for Bridge / Epistemic Calibration Files

The default target for the reasoning corpus is the four-part canonical entry format above. However, the bridge files and `epistemic_uncertainty_stories.md` are allowed to stay primarily in direct Q&A or grounded-story mode when symbolic mode would be artificial or low-value.

Use this exception narrowly:

* `00_bridge_word_to_symbol.md` and `01_bridge_symbol_to_word.md` may stay bridge-like because they teach representation alignment rather than arithmetic transformation drills.
* `epistemic_uncertainty_stories.md` may stay story-first because it teaches calibrated uncertainty, honest guessing, lookup behavior, and false-certainty hazards rather than a compact symbolic operator.
* Even when using the exception, each entry must still end in an explicit reasoning chain that names the epistemic or logical state being trained.

---

## Sprint-based Rollout

The corpus will be built in five sprints, starting with foundational concepts and progressively building to more complex, abstract reasoning.

### Sprint 0: Foundational State and Constraints

This sprint establishes the basic building blocks of logic: identity, difference, and contradiction.

*   `number_mechanics_successor.md`: Teaches `n+1` / `n-1` relationships and the concept of "one step before/after".
*   `same_vs_different_base.md`: Provides explicit training on equality (`A is A`) and non-equality (`A is not B`).
*   `basic_contradiction_checks.md`: Introduces state consistency (e.g., "A box cannot have both 3 balls and 4 balls at the same time.").

### Sprint 1: Linear Arithmetic and Semantic Mapping

This sprint focuses on basic arithmetic and mapping mathematical operations to verbal and narrative contexts.

*   `zero_and_identity_facts.md`: Establishes "no change" patterns (`X + 0 = X`, `X - 0 = X`, `X - X = 0`).
*   `addition_1_digit_facts.md`: High-density drills for single-digit addition.
*   `addition_1_digit_stories.md`: Maps addition to verbs like "gets," "joins," and "total."
*   `subtraction_1_digit_facts.md`: High-density drills for single-digit subtraction.
*   `subtraction_1_digit_stories.md`: Maps subtraction to verbs like "gives away," "lost," and "left."
*   `greater_than_less_than.md`: Teaches magnitude comparison.

### Sprint 2: Positional Logic and Representation

This sprint expands on arithmetic and focuses on translating between symbolic, verbal, and narrative forms.

*   `representation_translation_reinforcement.md`: Dedicated drills for aligning symbolic, verbal, and story representations.
*   `addition_2_digit_facts.md`: Drills for two-digit addition, including carrying.
*   `subtraction_2_digit_facts.md`: Drills for two-digit subtraction, including borrowing.
*   `ordinal_sequencing.md`: Anchors temporal markers ("first," "then," "last") to numerical sequences.
*   `addition_3_digit_facts.md`: Drills for three-digit addition.
*   `subtraction_3_digit_facts.md`: Drills for three-digit subtraction.

### Sprint 3: Grouping, Abstraction, and Reversibility

This sprint introduces more abstract concepts like multiplication, division, and the reversibility of operations.

*   `multiplication_repeated_addition.md`: Teaches multiplication as repeated addition (e.g., `3 x 5` is `5 + 5 + 5`).
*   `division_fair_sharing.md`: Teaches division as the decomposition of a whole into equal parts.
*   `inverse_operations_check.md`: Reinforces cognitive reversibility (e.g., "If you add 5 then subtract 5, you return to the start.").
*   `conservation_of_quantity.md`: Teaches state persistence through transformations (e.g., changing the shape of clay does not change the amount of clay).

### Sprint 4: Abstract and Higher-Order Reasoning

This final sprint introduces more complex logical structures and symbolic reasoning.

*   `inclusion_exclusion.md`: Teaches categorical boundaries and the "not" operator.
*   `conditional_if_then.md`: Establishes foundational state-checks ("If X is true, then Y happens.").
*   `symbolic_substitution.md`: Decouples logic from concrete nouns by replacing objects with variables (e.g., `A + B`).
*   `contradiction_check_advanced.md`: Teaches multi-step logical inconsistency checking.

### Bridge and Epistemic Calibration Adjuncts

These files are part of the reasoning track even though they do not fit neatly inside the arithmetic Sprint 0-4 ladder.

*   `00_bridge_word_to_symbol.md`: Bridges natural-language math terms into symbolic forms.
*   `01_bridge_symbol_to_word.md`: Bridges symbolic forms back into natural-language interpretations.
*   `epistemic_uncertainty_stories.md`: Specialized story corpus for calibrated uncertainty. It teaches four behaviors: active retrieval when unsure, careful guessing when checking is too costly, explicit regret after false certainty, and collaborative handling of shared uncertainty.

`epistemic_uncertainty_stories.md` should be treated as a bridge-dependent adjunct that complements `conditional_if_then.md` and `contradiction_check_advanced.md`, and it should be present before any training stage that expects Ninereeds to express uncertainty honestly and usefully.

---

## Seed Material

The legacy file `training_data/reasoning/mathematical_problems_seed_corpus.md` contains a set of mathematical word problems. This file should be used as a source of inspiration and examples when creating the new, structured reasoning files. The content from this seed file should be adapted to fit the canonical entry format defined in this plan.
