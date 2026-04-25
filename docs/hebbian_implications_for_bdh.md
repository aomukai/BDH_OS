# Hebbian Implications for BDH

## Why this note exists

BDH is not being trained like a large modern transformer that can absorb huge
amounts of mixed text and let scale sort things out. The current curriculum and
wiki are much closer to a structured teaching environment. That makes several
Hebbian-learning concerns directly relevant, even if BDH does not implement a
pure Hebbian rule today.

This note captures the practical implications for corpus design and later
training decisions.

---

## Core insight

For a Hebbian-style learner, input order, repetition, and local co-occurrence
matter a great deal. Whatever activates early or often can become a default
pattern and spread into unrelated outputs.

This matches observed failure modes in BDH experiments:

- over-weighting of `water` as a general medium
- over-weighting of repeated state frames like `hungry bunny`

These are not random glitches. They are exactly the kind of pattern-entrenchment
problems a Hebbian-sensitive system is likely to show.

---

## What the current corpus already does well

### 1. Dependency ordering

`training_data/phases/training_sequence.txt` is a major
strength.

- the sequence is not random
- anchor concepts come before derived concepts
- compounds come after parts
- relations come after entities

This is highly compatible with Hebbian concerns about input order.

### 2. Controlled early curriculum

The `phase 1–5` files constrain:

- vocabulary introduction
- sentence shape
- concept scope
- relation growth

That reduces noise during the earliest learning period, which is likely the most
sensitive period for representation formation.

### 3. Manual wiki cleanup

The current wiki cleanup strategy is also Hebbian-friendly:

- duplicate anchors are being removed
- concept ownership is becoming clearer
- broader concepts usually come before narrower ones
- encyclopedic density is being reduced

This lowers the chance that one concept gets accidentally overweighted just
because it appears in several domains with slightly different prose.

---

## What the corpus cannot solve by itself

### 1. Stability

Raw Hebbian updates tend to grow without bound unless something regulates them.
The corpus can reduce chaos, but it cannot replace an actual stabilization rule.

If BDH later uses online or incremental Hebbian-style updates, practical
stability mechanisms should be considered from day one:

- Oja's rule
- BCM
- other norm- or threshold-based controls

### 2. Competition

Without competition, multiple units may learn the same dominant pattern.
Curriculum design can reduce redundancy, but it cannot guarantee diverse
internal features.

If BDH later moves toward more biologically inspired online learning, it may
need:

- lateral inhibition
- winner-take-all or k-winners
- sparsity constraints

### 3. Monitoring

A well-ordered corpus is not enough. Training should still monitor internal
health, not just surface outputs.

Useful things to watch:

- activation histograms
- weight norms
- repeated-output collapse
- concept-frequency skew
- preservation of early anchors after later training

---

## Corpus rules that matter most under Hebbian pressure

### Prefer one canonical home per concept

If `forest`, `river`, or `button` appear as full wiki entries in many files,
they will not just be "covered twice." They may become overweighted.

Current policy should remain:

- one canonical `what is X?` anchor whenever possible
- duplicate only when clearly justified
- move stray concepts into their proper category home

### Be careful with repeated sentence frames

A small learner can absorb a relation pattern as a default continuation.

Examples of risk:

- one medium overused everywhere (`in water`)
- one animal-state combination repeated too often
- one contrast structure dominating many entries

Coverage matters, but frame diversity matters too.

### General before specific

This rule is useful both pedagogically and Hebbianly.

- `tree` before `birch`
- `hill` before `hilltop`
- `tool` before named tool types
- `school` before `classroom` and `lesson`

This reduces the chance that a narrow concept becomes the main anchor for a
broader cluster.

### Study before dialogue-like reinforcement

One important implication from Hebbian and McClelland-style concerns:

- clean observation should come before self-generated pattern reinforcement

For BDH, this supports the existing instinct to:

- teach through clean curriculum first
- add controlled wiki breadth second
- delay more interactive or self-updating systems until the hatchling is stable

---

## Current assessment of BDH against Hebbian concerns

### Strong

- dependency ordering in `phase 1–5`
- explicit concept grounding
- recent wiki dedupe and concept ownership cleanup
- manual avoidance of noisy or encyclopedic prose

### Medium

- balance across categories and verbs
- balance across sentence frames
- contrast consistency and dangling contrast cleanup

### Weak or not yet implemented

- formal stability controls during online learning
- competitive or sparse update mechanisms
- internal monitoring of representation health during training

---

## Practical guidance going forward

1. Keep cleaning existing wiki files before adding many new categories.
2. Keep treating duplicate entries as training-risk, not just housekeeping.
3. Audit high-frequency verbs and high-frequency relation frames later.
4. Preserve dependency-aware ordering across both curriculum and wiki.
5. If online learning is introduced later, do not use raw Hebbian updates
   without stabilization and monitoring.

---

## Bottom line

The current BDH corpus is becoming increasingly compatible with Hebbian-style
concerns at the level of structure and ordering.

That does **not** mean the full training system is Hebbian-safe yet.

The corpus is doing the right kind of preparatory work:

- reducing noise
- clarifying concept ownership
- controlling order
- avoiding accidental over-weighting

Those decisions should make later biologically inspired or online learning much
more viable than a loose pile of mixed text ever would.
