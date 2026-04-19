# Skill: request_more_data

## Purpose

Emergency-exit intervention for when the harness has exhausted realistic internal interventions and the likely bottleneck is missing data.

## Use When

- all relevant interventions are exhausted or ruled out
- the likely remaining problem is insufficient data
- the requested additions can be specified concretely

## Inputs

- target cluster
- failure taxonomy
- exhausted interventions list
- project goal-state rules

## Steps

1. Define the failing cluster precisely.
2. Summarize the dominant failure types.
3. List exhausted interventions and why they failed.
4. Draft a targeted data request.
5. Keep the request bounded and tied to project goals.
6. If Hermes approves the emergency exit, prepare draft data pieces for review.

## Output Requirements

A valid request must include:

- target cluster
- dominant failures
- exhausted interventions
- requested data shape
- why this request helps BDH as a coherent broad-knowledge chatting model
- what remains out of scope

## Hard Rule

This skill must not become a back door to endless expansion.
If the request is vague, unbounded, or inconsistent with the project scope, it should be rejected.
