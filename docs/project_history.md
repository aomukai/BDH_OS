# BDH Cognitive OS — Project History

This document records how the project started, what was tried, what failed, and what those failures taught.

The goal is not to present a smooth success story. The goal is to preserve the actual path taken, because the path is part of the method.

---

## 1. Starting Point

The project began as an experiment around the **BDH architecture**.

At the start, the main question was simple:

> Can a BDH model be trained locally at all, and if so, what kind of data does the architecture respond to?

The first setup was pragmatic rather than carefully planned. A Hermes agent was used for orchestration, with **Nemotron** acting as the executing LLM. Nemotron was given a simple instruction: there was interest in the BDH architecture, and an attempt should be made to train one.

Nemotron interpreted that as a direct command, cloned the upstream BDH repository, fetched a small dataset, and launched training.

That first run mattered because it established something basic but important:

- the tooling stack could be made to run
- a BDH training pass could complete
- the resulting checkpoint could generate output at all

Even when the output was weak, the fact that the system produced language was enough to justify continuing.

---

## 2. Tiny Shakespeare: Proof Of Life

The first dataset used was **Tiny Shakespeare**.

This was not chosen because it matched the long-term goal. It was chosen because it was small, familiar, and useful for proving that the training process worked end to end.

The resulting model produced outputs in the rough shape of:

> "to be or not to be ggg lllll aaa"

This was not meaningful language, but it was still a milestone. The model had clearly learned enough structure to emit fragments with recognizable rhythm and token continuity.

The lesson from this stage was:

- BDH could be trained successfully in a local setup
- the architecture could produce language-like output after training
- proof of execution had been established, but not useful knowledge

This stage answered the question "does the pipeline work?" but not "can the model learn a world?"

---

## 3. BabyLM: More Data, Better Surface, No Grounding

After Tiny Shakespeare, the next step was to try a more child-relevant corpus. The **BabyLM** dataset was used, first the 10M set and then the 100M set.

This was a natural escalation:

- the text was broader
- the amount of data was larger
- the content was closer to ordinary language exposure

The model improved in a superficial but noticeable way. Outputs became more lexical and more grounded in familiar words, with examples along the lines of:

> "the moon dog fly water"

This looked better than Shakespeare fragments, but it still did not amount to coherent understanding.

The key question at this point was whether the model simply needed more data in order to infer knowledge from exposure.

That was a reasonable hypothesis, especially if one came from the world of transformer-based language models, where broad pattern absorption often produces surprising emergent behaviors.

But BDH did not appear to be responding in that way.

The lesson from BabyLM was:

- more data improved local token plausibility
- more data did not automatically produce relational understanding
- the model could emit familiar words without actually organizing them into a stable concept system

This was the first sign that BDH might require a different teaching strategy from standard large-scale text immersion.

---

## 4. Cosmopedia: The Large-Corpus Failure

The next experiment pushed the "maybe the model just needs more text" hypothesis much harder.

A story subset of **Cosmopedia** was downloaded, around 200,000 stories were extracted, and the model was trained on that corpus.

Instead of improvement, the result was collapse. Output degraded into repetition, such as:

> "a dog ... the the the the the"

This stage was important because it functioned as a negative result with real diagnostic value.

The conclusion was not merely that this particular run went badly. The stronger conclusion was that flooding the model with large amounts of prose did not teach BDH the kind of structure it needed. In fact, it appeared to damage whatever fragile internal organization had already formed.

This became the turning point of the project.

The lesson from Cosmopedia was:

- unrestricted natural-language volume was not helping
- the architecture did not seem to infer stable knowledge from broad text exposure alone
- data quality, structure, and sequencing were likely more important than raw dataset size

This was the moment the project stopped being "train on increasingly larger corpora" and became "design instruction that this architecture can actually absorb."

---

## 5. Building A Foundational Curriculum By Hand

After the Cosmopedia failure, the approach changed completely.

Instead of searching for a better large corpus, a custom curriculum was written by hand. This became the **phase 1 to 5** training set.

The underlying idea was simple:

> If the architecture does not build concepts reliably from broad text exposure, then concepts must be introduced deliberately, in order, and with controlled language.

The curriculum was built in phases, each phase teaching a different level of conceptual structure.

Core design choices included:

- very small, repeatable Q-and-A units
- concrete language
- strong control over vocabulary introduction
- stable conceptual arcs inside each file
- cumulative dependencies instead of random exposure

Over time, the curriculum format solidified into the current structure:

- four `[user]` / `[assistant]` exchanges per file
- each file centered on one concept
- each exchange following a consistent question pattern
- summary definitions constrained by the vocabulary already introduced

This was a move away from "let the model discover structure" and toward "give the model structure directly."

---

## 6. The Seismic Test

An early large test was run before the corpus had its current fine-grained file layout.

At that time, each phase existed as a combined file rather than the more carefully split and indexed version now in the repository. The model was trained through all five phases in sequence in what became an important stress test for the idea.

The rough results were:

- Phase 1: 6/9
- Phase 2: 4/9
- Phase 3: 9/11
- Phase 4: 4/9
- Phase 5: 4/9

These scores did not mean the project was done, but they did mean something important:

- the custom curriculum could move the model measurably
- some phases were clearly working better than others
- performance was uneven in a way that suggested structural causes, not just random variance

This was enough to justify a careful review of the curriculum itself.

---

## 7. The Dependency Insight

Looking back at the curriculum after the seismic test led to one of the most important ideas in the project:

> **Dependency ordering might be crucial.**

The issue was not only whether the model had seen a word before. The issue was whether the model had seen the right conceptual supports before encountering a more complex concept.

For example:

- `bee` before `honey`
- `honey` before `beehive`
- `beehive` before `jar of honey`

This is more than vocabulary order. It is **concept graph order**.

That insight led to the current cleanup and reorganization work:

- splitting the phases into many individual files
- creating a canonical `training_sequence.txt`
- adding `concept_index.md`
- generating `dependency_graph.json`
- tracking vocabulary introduction in `training_data/phases/concept_vocab_bank.md`

The curriculum became much more explicit after this point. It was no longer just hand-authored educational data. It became a shaped path through a dependency network.

---

## 8. From Text Completion To Chat

Another major shift in the project was a change in format philosophy.

Early language-model experiments can easily drift toward plain text completion, because that is the easiest format to generate in bulk. But the actual goal of the project was not to make BDH continue text. The goal was to make BDH **chat**, at least to some degree, and to support some degree of reasoning inside that chat.

That realization led to an important rule:

> Introduce the `[user]` / `[assistant]` format from the start.

This was not a cosmetic decision. It was a training-shape decision.

The curriculum now aims to teach at least three things at once:

- concepts
- controlled language
- interaction format

In other words, the model is not just being taught "what a dog is." It is being taught how such knowledge appears inside an exchange.

---

## 9. The Wiki Layer

The next major idea was to build a **knowledge base for a first grader**.

That idea became the wiki layer described in [wiki.md](wiki.md).

The wiki was designed to do something different from the phase curriculum.

The phases teach:

- anchoring
- vocabulary control
- compact concept introduction
- tightly constrained response structure

The wiki is meant to add:

- broader but still shallow knowledge
- relational and social context
- more natural explanatory prose
- the "glue" that makes conversation possible

The target is not expert knowledge. The target is the kind of broad, ordinary, connected knowledge that a child uses to understand daily life.

This distinction matters:

- the curriculum teaches the model to see
- the wiki teaches the model to relate

That is why the wiki is intentionally broad but not deep.

---

## 10. Current Strategy

At the current stage of the project, the work is focused on two main corpus tracks.

### 10.1 Foundational Curriculum

The **phase 1 to 5** corpus is being cleaned, reorganized, and made more rigorous.

Current priorities include:

- anchoring concepts carefully
- preserving strict ordering and dependencies
- keeping the files parser-friendly and reproducible
- tightening vocabulary control
- improving consistency after the file split and reindexing work

### 10.2 Wiki Corpus

The wiki corpus in `training_data/wiki/` is being developed as the second layer of instruction.

Current priorities include:

- expanding missing categories
- cleaning older encyclopedic entries into a tighter grade 4-6 style
- preserving clear contrast structure
- building broad, practical knowledge without losing conceptual discipline

Together, these two corpora are meant to support a model that can:

- answer in chat format
- hold onto simple concepts
- generalize across closely related concepts
- perform some amount of lightweight reasoning

The ambition is deliberately modest and architectural rather than benchmark-driven.

---

## 11. Mommy Says Machine

The next planned stage after the foundational curriculum and wiki are in place is described in [mommy_says_machine.md](mommy_says_machine.md).

The Mommy Says Machine is not meant to train the model live. It is meant to **diagnose** the model, test correction behavior, and generate high-quality correction data for future offline training.

Its role is to answer questions like:

- What does the dragon currently know?
- What happens when the dragon is corrected?
- Does correction hold inside a session?

This continues one of the central principles of the project:

> Learning should be deliberate, inspectable, and offline.

The model is not supposed to absorb random interaction history and silently change. It is supposed to be tested, corrected, logged, and retrained cleanly when appropriate.

---

## 12. Main Lessons So Far

At this point, several working beliefs have emerged from the experiments:

1. **A successful training run is not the same as a useful training run.**
   Tiny Shakespeare proved the pipeline worked, but not that the model knew anything.

2. **More text is not automatically better for BDH.**
   BabyLM improved token plausibility, but not grounded understanding.

3. **Large prose corpora can actively damage performance.**
   The Cosmopedia run was a failure, but a productive one.

4. **Structure matters more than volume.**
   Controlled concept introduction appears far more useful than broad immersion.

5. **Dependency order probably matters.**
   Concepts seem to need prerequisite concepts, not just co-occurring words.

6. **Chat format should be taught, not assumed.**
   If the goal is dialogue, dialogue form belongs in the training data from the beginning.

7. **Breadth and depth should be separated.**
   The phase curriculum and the wiki serve different educational functions and should stay distinct.

---

## 13. Status Of This Document

This history is a first draft.

It is meant to capture the arc of the project while the reasoning behind each step is still fresh. It should be expanded over time with:

- dates
- checkpoint names
- training settings
- evaluation notes
- examples of outputs
- screenshots or logs where useful
- reflections on what later turned out to be wrong

That fuller version may eventually be useful as both:

- internal project documentation
- a public write-up for others interested in experimenting with BDH

For now, the main purpose is simpler:

> preserve the reasoning, not just the files.
