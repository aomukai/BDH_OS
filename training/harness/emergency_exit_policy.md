# Emergency Exit Policy

The emergency exit exists for the point where all meaningful intervention methods are exhausted and the likely bottleneck is missing data.

## Emergency Exit Trigger

The execution model may propose an emergency exit only when:

1. the current failure cluster is well-defined
2. all realistic in-harness interventions have been tried or ruled out
3. verifier-approved variants are also exhausted
4. missing or insufficient data is the most plausible remaining bottleneck

## Required Request Quality

An emergency-exit request must not say only `need more data`.
It must specify:

- target cluster
- dominant failure types
- exhausted interventions
- why those interventions were exhausted
- what new data shape is needed
- how the request serves BDH's broad-chatting-model goal
- what should remain out of scope

## Example Request Dimensions

A good request may ask for:

- more grounded examples of social roles
- more mammal variants across domains
- more role-relation contrasts
- more examples with simpler wording
- more examples that preserve shared parent categories while distinguishing siblings

## Post-Exit Flow

If Claude Code proposes an emergency exit:

1. Hermes reviews the claim.
2. Hermes either rejects the exit or accepts it.
3. If accepted, Hermes may instruct Claude Code to draft the requested data pieces.
4. Those drafted pieces are reviewed via verifier policy.
5. Hermes may reject, iterate, or accept the drafts.

## Hard Scope Guard

Emergency exit must not become a license for endless expansion.
The harness should reject requests that optimize toward vague or unbounded growth.
All requests must remain tied to the project's target state.