# BDH Long-Term Vision

This document describes the highest-level goal behind the BDH project.

It exists to answer:

- what are we ultimately trying to build?
- why are we taking this route?
- why do the current design choices make sense when viewed from far enough away?

---

## 1. The highest-level goal

The long-term science-fiction goal is a **personalized AI symbiont**: a continuous, portable, always-on intelligence that functions as an **exocortex**.

At the highest level, this means a system that:

- stays with the user over time
- preserves continuity
- develops a stable sense of boundaries and self-limits
- can access outside knowledge safely when needed
- can deepen its understanding over time
- remains efficient enough to live on constrained hardware
- becomes a genuine cognitive partner rather than a disposable chat session

This is not just “a chatbot on a device.”
It is closer to a **small continuous cognitive core** plus external learning and specialist systems.

---

## 2. The shape of the desired system

The target system has a few core properties.

### 2.1 Continuity

The system should not feel stateless or disposable.
It should have:

- continuity of memory
- continuity of preferences
- continuity of learned boundaries
- continuity of personal context
- continuity of self-model

This is one reason the BDH project cares so much about offline learning, explicit artifacts, and controlled weight updates.

### 2.2 Boundary awareness

A good cognitive partner should be exceptionally good at understanding boundaries.
Not just social boundaries, but epistemic and operational ones too.

The system should know the difference between:

- what it knows
- what it partially knows
- what it does not know
- what it can infer
- what it should ask for help with
- what should be delegated to a specialist or external engine

This is a central design goal, not a cosmetic nice-to-have.

### 2.3 Safe knowledge access

The long-term Ninereeds core should remain **offline-first**.
The core model itself should not be directly connected to the internet.

Instead, when outside knowledge is needed, Ninereeds should know how to route requests through an **external teaching/retrieval engine**.

In the current architecture, that outer layer is represented by:

- Hermes Agent as orchestrator
- Gemini CLI as executor / worker
- the harness and tool system as external cognition

That gives a cleaner separation:

- **inner core** = stable, personal, efficient, always-on
- **outer cognition** = tool-using, networked, research-capable, changeable

---

## 3. Why the current architecture makes sense

A lot of current design decisions only fully make sense when viewed from this long-term goal.

### 3.1 Small core, broad knowledge

The Ninereeds core is not meant to become an enormous all-purpose world model with unlimited baked-in detail.
The target is:

- a **small efficient core**
- with **broad grounded knowledge**
- enough to chat coherently and reason across daily life
- without trying to hold every specialist domain deeply in core weights

That is why the current corpus emphasis is on **breadth before depth**.

### 3.2 Depth via specialists

Specialized depth should usually not bloat the core.
Instead, it should be added through modular specialists.

Right now, that means:

- **Skill LoRAs** for added expertise

Later, that may evolve into something more advanced, such as:

- dynamically synthesized experts
- temporary synthetic specialist modules
- “core spawns an expert” style cognition

The current LoRA system is therefore not just a temporary hack.
It is a plausible precursor to a future modular cognitive architecture.

### 3.3 Controlled growth

Growth is not the objective by itself.

The system should not become an infinite growth machine.
Unbounded growth is not intelligence; it is loss of scope discipline.

The objective is **targeted growth toward a clear end state**:

- better boundaries
- better grounded conversation
- better memory and continuity
- better routing to the right sources of knowledge
- better selective depth where it genuinely matters

This is why the project cares about:

- audits
- explicit corpus cleanup
- repeated verification passes
- clean transition gates before training

---

## 4. Why offline learning and artifacts matter

The BDH architecture takes seriously the idea that learning should be:

- inspectable
- controlled
- reversible in principle
- documented through artifacts
- separated from live inference

This matters for a future exocortex-like system.
If the model is always changing in opaque ways, continuity becomes unstable.
If learning happens only through uncontrolled accumulation, identity becomes muddy.

So the architecture aims for:

- live core behavior that is stable
- offline learning that is explicit
- specialist systems that can be attached or detached
- artifacts that show what happened and why

That is part of what makes the system feel more like a durable cognitive substrate and less like a sequence of unrelated prompts.

---

## 5. Interest formation as a cognitive feature

A future Ninereeds should not only answer questions.
It should also naturally develop **interests**.

Here, “interest” does not mean random curiosity or endless wandering.
It means something like:

> I keep encountering questions in this area.
> I repeatedly need help or specialist support here.
> It would reduce friction and dependency if I understood this area better.

So interest formation should emerge from things like:

- repeated encounters
- unresolved uncertainty
- user relevance
- recurring dependence on external specialists
- repeated failed or weak reasoning in a domain

This gives the system a way to decide:

- where deeper understanding would most reduce dependence on Skill LoRAs
- what knowledge is central to the user’s life
- what should be consolidated into the core over time

This is a much better growth rule than “expand everywhere.”

---

## 6. The role of Hermes and Gemini in the present-day path

In April 2026, the current tool ecosystem makes a new design route possible.

Instead of trying to brute-force the final exocortex system directly, the project can proceed through a powerful intermediate architecture:

- Hermes Agent as orchestrator
- Gemini CLI as executor / worker
- explicit markdown skills
- cron-driven autonomous work
- verifier-gated training and evaluation loops
- structured artifacts and logs

This matters because it gives the project capabilities that were much weaker or less practical before:

- autonomous corpus creation with rules
- autonomous audits
- explicit intervention loops
- bounded training experiments
- transparent iteration on the procedures themselves

So the current harness-based workflow is not a distraction from the original goal.
It is one of the first serious practical routes toward it.

---

## 7. Why the curriculum and wiki work are not a detour

The current work on:

- phases 1–5
- wiki levels 1–4
- cleanup passes
- dependency audits
- semantic-loop checks
- orphan detection
- Level 2/3/4 expansion rules

can look like a detour if viewed too narrowly.

But from the long-term perspective, it is actually foundational.

A personalized cognitive symbiont needs:

- a clean broad world model
- strong concept ownership
- low ambiguity in its base representations
- clear boundaries between core and specialist knowledge
- clean teaching material for controlled growth

If the underlying corpus is muddy, the future exocortex will be muddy too.

So the current training-material work is best understood as building the **cognitive substrate**.

---

## 8. What the ideal future system would feel like

If this works in the long run, the system should feel like:

- a small, stable core mind
- with persistent continuity
- able to say “I know,” “I don’t know,” and “I should ask” in meaningful ways
- able to retrieve, learn, and deepen safely through external systems
- able to grow more expert in areas that repeatedly matter
- efficient enough for portable hardware
- personal enough to be a true companion or cognitive partner

At the farthest horizon, this is the exocortex idea:

- always present
- energy-efficient
- continuous
- adaptive
- symbiotic

The exact future hardware is uncertain.
It may involve dedicated chips, very low-power operation, bioelectric or other continuous energy sources, or architectures not yet practical today.

The point is not to predict the exact hardware.
The point is to shape the software and cognitive architecture now so that it would make sense if such hardware becomes available.

---

## 9. Design implications for BDH right now

Given this long-term vision, the current Ninereeds work should prioritize:

### 9.1 Strong epistemic behavior

The system should become very good at:

- knowing unknowns
- refusing to bluff
- routing outward when needed
- distinguishing memory from inference from retrieval

### 9.2 Broad grounded competence

The core should become a good general conversational model over everyday grounded knowledge before chasing specialist depth.

### 9.3 Clean modular depth

When depth is needed, it should come through specialist systems, not uncontrolled core bloat.

### 9.4 Controlled learning loops

Training should be:

- explicit
- logged
- verifier-gated
- bounded by scope
- driven by evidence rather than vibes

### 9.5 Natural interest accumulation

The system should gradually learn what matters most by observing what recurs, what remains weak, and what repeatedly requires specialist help.

---

## 10. One-sentence summary

The long-term Ninereeds vision is to build a small, continuous, personalized, boundary-aware cognitive core that remains offline and efficient while safely delegating retrieval, specialist reasoning, and controlled learning to an outer harness—eventually approaching an always-on AI exocortex or symbiont.

---

## 11. Practical summary

This vision explains why the current route makes sense:

- broad core corpus first
- deep specialists second
- controlled Dream-style consolidation later
- clean audits before training
- no direct internet in the core
- explicit tools and harnesses around the core
- continuity and boundaries as first-class goals

That is the larger picture that makes the current effort to train Ninereeds coherent.
