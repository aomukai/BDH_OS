# Verifier Policy

The verifier policy exists because teacher models can make subtle conceptual mistakes.
No raw teacher output should reach the student or the accepted training corpus without passing this policy.

## What Must Be Verified

The following artifacts require verification:

- student-facing corrections
- teacher/student drill prompts and corrections
- generated contrastive pairs
- proposed curriculum reorder justifications
- emergency-exit data requests
- Claude-authored draft data created in response to an emergency exit

## Required Checks

### 1. Local Factual Correctness
Is the statement itself true?

### 2. Ontology Consistency
Does it preserve parent/child and sibling-category structure?

Example:
- dog is a mammal
- bird is an animal
- mammal is an animal
- dog is not a bird

The verifier must reject corrections that accidentally collapse or distort shared parents.

### 3. Contrast Safety
If a correction says `X is not Y`, does it also preserve important common structure where needed?

### 4. Curriculum-Level Fit
Is the wording simple and concrete enough for the current BDH target level?

### 5. Dependency Fit
Does the correction depend on concepts the student likely has not stabilized yet?

### 6. Internal Corpus Consistency
Does the candidate conflict with existing accepted curriculum/wiki language or rules?

### 7. Pedagogical Usefulness
Even if factually true, is it likely to teach the right thing at this stage?

## Verifier Outcomes

The verifier should emit one of:

- `approve`
- `approve_with_rewrite`
- `reject`
- `needs_higher_level_dependency_check`

## Required Output Shape

Every verifier decision should include:

- artifact id
- reviewed text
- outcome
- reasons
- rewritten version if applicable
- warnings

## Hard Rejection Cases

Reject when a candidate:

- introduces factual falsehood
- introduces ontology confusion
- exceeds current curriculum level badly
- contradicts accepted design constraints
- creates student-facing text that is likely to poison category structure

## Design Principle

The teacher is a fallible optimizer, not a guaranteed truth source.
The verifier exists to make the harness safer, more legible, and less vulnerable to silent corruption.
