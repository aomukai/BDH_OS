# Implementation Plan — Connective Tissue Concepts

This file is a deferred design and implementation note for the connective-tissue batch,
story layers, and later false-belief scaffolding.

For the canonical overall training sequence, see `docs/training_pipeline.md`.

These entries are ready to implement. Do not implement during a quality pass.
Implement as a dedicated batch when the quality pass is complete.

Each section lists the target file and the full draft entries to add.
All entries follow Level 1 voice: identity + 2-3 concrete facts + 1 contrast.

---

## 1. Extend STEM_entries.md

Add after the existing state-change verbs (melt, freeze, break, fix, grow).

[user]what does it mean to become something?
[Ninereeds]To become means to change into something different. Water becomes ice when it gets cold enough. A caterpillar becomes a butterfly after spending time inside a cocoon. When something becomes something else, it is no longer what it was before. Become is not the same as stay the same.

[user]what does it mean to turn into something?
[Ninereeds]To turn into something means to change and become a new thing. Ice turns into water when it gets warm. A tiny seed can turn into a tall plant as it grows. When something turns into something else, it has changed what it is. Turn into is the same idea as become.

[user]what does it mean to shrink?
[Ninereeds]To shrink means to become smaller. A wool sweater can shrink if it gets too hot in a wash. A balloon can shrink if air leaks out slowly. Shrinking is the opposite of growing. Shrink is not the same as grow.

[user]what does it mean to appear?
[Ninereeds]To appear means to become visible or to show up. The sun may appear from behind a cloud. A rabbit may appear from behind a bush. When something appears, it can now be seen. Appear is not the same as disappear.

[user]what does it mean to disappear?
[Ninereeds]To disappear means to go away so that people can no longer see it. The sun disappears at night. A bird may disappear into the trees. When something disappears, it can no longer be seen. Disappear is not the same as appear.

[user]what does it mean to use up something?
[Ninereeds]To use up something means to use all of it until none is left. You can use up a crayon by drawing a long picture. A car can use up the petrol in its tank. When something is used up, there is nothing left of it. Use up is not the same as save.

[user]what does it mean to run out of something?
[Ninereeds]To run out means to reach the end of a supply so that none is left. A cup can run out of water. A shop can run out of bread. When something runs out, there is no more of it to use. Run out is not the same as have plenty.

---

## 2. Extend logic_entries.md

Add after the existing cause-and-effect entries (cause, effect, consequence, reason).

[user]what is an outcome?
[Ninereeds]An outcome is what happens at the end of a process or action. A good harvest can be the outcome of careful planting. Winning a game can be the outcome of playing well. An outcome comes after everything is done. An outcome is not the same as a cause.

[user]what does both mean?
[Ninereeds]Both means two things together, with neither one left out. Both apples are red. Both children were there. When people say both, they are talking about two things at the same time, not just one. Both is not the same as neither.

[user]what does also mean?
[Ninereeds]Also means in addition to something already said. A dog can bark, and a dog can also run fast. If a child is hungry, she may also be tired. Also adds another true thing to what was just said. Also is not the same as instead.

[user]what does but mean?
[Ninereeds]But shows that something goes against what came before. A day may be sunny but also cold. A child may want to play, but it is time for bed. But connects two ideas where the second one surprises or goes against the first. But is not the same as and.

[user]what does however mean?
[Ninereeds]However means the same thing as but, but it can start a new sentence. Something may look easy. However, it may be quite hard to do. However is used to show a contrast or surprise in what comes next. However is not the same as also.

[user]what does it mean to fail?
[Ninereeds]To fail means to try to do something and not succeed. A key can fail to open a lock if it is the wrong key. A plant can fail to grow if it does not get enough water. Failing is not the same as not trying. Fail is not the same as succeed.

[user]what does more than one reason mean?
[Ninereeds]More than one reason means that several different causes led to the same result. A tree may fall because of strong wind, and also because the roots were weak. Many things that happen have more than one cause, not just a single one. More than one reason is not the same as having just one reason.

---

## 3. Extend exceptions_and_qualifications_entries.md

Add after the existing entries (usually, sometimes, except, unless, it depends).

[user]what does only if mean?
[Ninereeds]Only if means something will happen in just one case and no other. A plant will grow only if it gets enough water and light. A game can start only if everyone is ready. Only if sets a strict condition with no room for exceptions. Only if is not the same as usually.

[user]what does in that case mean?
[Ninereeds]In that case means given what was just said, here is what follows. If it is raining, in that case we will stay inside. In that case helps people say what comes next once a condition is met. In that case is not the same as always.

[user]what does otherwise mean?
[Ninereeds]Otherwise means what will happen if the condition is not met. You must carry an umbrella, otherwise you may get wet. Otherwise tells what follows when the first thing does not happen. Otherwise is not the same as also.

---

## 4. Extend storytelling_and_narrative_structure_entries.md

Add after the existing sequence words (first, next, then, before, after, finally).

[user]what is a step?
[Ninereeds]A step is one action in a sequence of actions done in order. The first step in making a sandwich is to get the bread. A step comes after the one before it and before the one after it. Steps help people do things in the right order. A step is not the same as the whole process.

[user]what does in order mean?
[Ninereeds]In order means arranged so that each thing comes at the right time. You need to do the steps in order to get the right result. In order tells people not to skip steps or do them backward. In order is not the same as all at once.

---

## 5. Extend time_entries.md

Add near the end, after the existing entries for soon and immediately.

[user]what does eventually mean?
[Ninereeds]Eventually means after some time has passed. A seed will eventually grow into a plant. If you practice, you will eventually get better at a skill. Eventually tells about something that has not happened yet but will happen later. Eventually is not the same as immediately.

[user]what does takes time mean?
[Ninereeds]Some things take time to happen and cannot be rushed. A tree takes time to grow from a seed. Learning a new skill takes time and practice. When something takes time, it cannot be done right away. Takes time is not the same as immediately.

---

## 6. New file — appearance_and_hidden_state_entries.md

Create as a new file in training_data/wiki/.
Register in CORPUS_STATUS.md as a bridge-and-modifier category.
This file covers the appearance/reality distinction and observable vs. internal state.
It is prerequisite for perspective-taking and hidden-cause reasoning.

[user]what does hidden mean?
[Ninereeds]Hidden means something is in a place where it cannot be seen. A key can be hidden under a mat. Food can be hidden inside a box. Hidden things are still there even though people cannot see them. Hidden is not the same as gone.

[user]what does visible mean?
[Ninereeds]Visible means something can be seen. A bright lamp is visible from far away. Stars are visible at night. When something is visible, people do not have to search for it. Visible is not the same as hidden.

[user]what does it mean when you can't see something?
[Ninereeds]Something can be real and present even if you cannot see it. Air is all around you but cannot be seen. Sound travels through a room even if you cannot see it move. Not being able to see something does not mean it is not there. You can't see it is not the same as it is not there.

[user]what is the outside of something?
[Ninereeds]The outside of something is the part that faces outward and can be seen. The outside of a box is its lid and walls. The outside of a fruit is its skin or peel. People usually see the outside of something first. The outside is not the same as the inside.

[user]what is the inside of something?
[Ninereeds]The inside of something is the part hidden within it. The inside of a box holds what was placed there. The inside of a fruit holds its flesh and seeds. People cannot see the inside of something without opening it up. The inside is not the same as the outside.

[user]what does looks the same mean?
[Ninereeds]Something looks the same when its outside has not changed. A bag can look the same even after something is taken out of it. A room can look the same even if one small thing was moved. Looks the same tells about the outside view only, not what is inside. Looks the same is not the same as is the same.

[user]what does something changed inside mean?
[Ninereeds]Sometimes the inside of something changes while the outside stays the same. An egg looks the same from outside, but changes happen inside as a chick grows. Water inside a pipe may freeze even if the pipe looks unchanged. Something changed inside tells about a change that is hidden from view. Something changed inside is not the same as nothing happened.

[user]what does not what it looks like mean?
[Ninereeds]Not what it looks like means the outside appearance does not tell the whole truth. A puddle may look shallow but be deeper than it seems. A quiet room may have many people waiting just behind the door. The outside of something does not always show what is really true inside. Not what it looks like is not the same as a lie.

---

# Future Phase — Short Story Blocks

Do not implement until the connective tissue batch above is complete and the wiki level 1 quality pass is done.
This is a separate training layer that sits after phase 1-5 and wiki level 1.

---

## Purpose

The Q&A format trains concept definitions with strict, stable sentence patterns.
Story blocks train the same vocabulary in natural, flexible sentence structures.
These two formats do different things and each reinforces the other.

A model that knows "what is a cat?" still needs exposure to "the cat walked slowly to the bowl" before it can generate that sentence naturally.
Stories provide co-occurrence in context that Q&A alone cannot.

Quality over quantity. Not every concept fits a story naturally and nothing should be forced.
The goal is more variation in sentence structure, not exhaustive coverage of all concepts.

---

## Format

Wrap every story in the standard dialogue structure to keep format consistent across all training data.
The user prompt names the concepts. The assistant tells the story.

```
[user]tell me a short story about a cat, a dog, and a person giving them food.
[Ninereeds]A person walked into the kitchen and opened a can of food. The cat came in first and sat near the bowl. The dog followed and waited beside it. The person put food in both bowls, and the two animals began to eat.
```

Three to five sentences per block.
Every word in the story must be grounded somewhere in prior training — not just the three target concepts.
Ungrounded words in a story are noise because there is no definition to attach them to.

---

## Triplet selection rules

**Pick triplets that are semantically coherent, not random.**

Good triplets come from the same category or from categories that have a natural dependency:
- animals_mammals: cat, dog, person — a person can feed them, they can interact
- emotions + people_roles: child, happy, surprise — a child reacts to something
- daily_routines + body_states: hungry, breakfast, eat — a routine unfolds naturally
- goal + action + outcome: want, try, succeed — a simple goal-directed arc

Avoid triplets that have no natural relationship.
If you cannot write a coherent 3-5 sentence story without forcing the words, choose a different triplet.

**Concepts that work well in stories:**
- concrete nouns (animals, objects, food, places, people)
- action verbs (eat, run, find, give, carry, look)
- body states and emotions (hungry, tired, happy, afraid)
- goal-directed behaviour (want, try, find, give, succeed, fail)
- sequence words (first, then, finally) — these appear naturally as connectives, not as targets

**Concepts that usually do not work well as story targets:**
- pure logical operators (all, none, each, or)
- abstract structural concepts (fraction, tally, topology)
- meta-language (subject, lesson, grade)

These stay in Q&A. Do not force them into stories.

---

## Story design principles

**One anchor concept, two supporting ones.**
The story should be *about* one central idea. The other two appear naturally in context.
This keeps the story coherent rather than trying to serve three equally weighted targets.

**Use goal-directed structure where possible.**
Character wants something → tries to get it → result.
This is the simplest narrative arc and reuses concepts from logic (goal, action, consequence, outcome) without needing to name them explicitly.

**Sentence variety is the point.**
The Q&A format is always: identity sentence, fact, fact, fact, contrast.
Stories should use different structures: questions, subordinate clauses, time connectives, descriptions, dialogue.
This is why stories add value — not more definitions, but different syntax around known words.

**Keep the voice consistent with Level 1 — simple words, short sentences, concrete details.**
No metaphor, no idiom, no implied knowledge the model has not been taught.

---

## Phased expansion

Repeat story generation after each wiki level, not just after level 1.

- After wiki level 1: stories use daily-life and concrete vocabulary only
- After wiki level 2: stories can include more abstract concepts (emotions, reasoning, cause-effect)
- After wiki level 3+: stories can include longer arcs, more characters, richer situations

Each phase expands the vocabulary pool but keeps the format identical.
The model sees the same story format getting richer over time, which is a natural curriculum spiral.

---

## Implementation process (when ready)

1. Run through the full corpus concept list and identify story-amenable concepts.
2. Group them into natural semantic clusters.
3. Propose triplets from each cluster and check that all supporting vocabulary is grounded.
4. Write one story block per triplet.
5. Review for vocabulary discipline — flag any word that is not grounded in phase 1-5 or wiki level 1.
6. Do not target a specific count. Stop when the remaining concepts no longer form natural triplets.

---

## Concrete anchors for abstract concepts

Some physical objects naturally embody abstract concepts from the harder wiki files.
A story built around one of these objects teaches the abstract pattern through a familiar thing,
before the model ever encounters the explicit definition.
This is example-before-definition order, and it reinforces the later definition rather than replacing it.

Good concrete anchors and what they carry:

| Object | Abstract concepts grounded |
|---|---|
| egg | hidden internal state, state transition (hatching), looks the same / changed inside |
| seed | delayed effect, become something different, takes time, hidden internal state |
| caterpillar / cocoon | state transition, looks the same outside, not what it looks like |
| candle | use up, run out, disappear gradually |
| ice cube | state transition (melt), become, turns into |
| bag or box | inside / outside, hidden, you can't see it |
| broken toy | fail, doesn't work, fix, outcome |

Stories using these objects can do double duty:
they practice vocabulary from their own category while grounding an abstract concept
from the appearance_and_hidden_state or connective tissue files.
The model does not need to name the abstract concept in the story.
It only needs to encounter the pattern in a situation where it makes sense.

This approach also works in reverse: once a harder concept is defined in the wiki,
a story using a concrete anchor gives the model a second exposure in a different register.

### The egg gap

`egg` has a food-side entry in `foods_and_drinks_entries.md` (shell, white, yolk, cooking methods).
The biological side is missing: egg as a life stage, containing a developing animal, hatching into a chick.
The biological definition belongs in `natural_life_cycles_and_processes_entries.md`.
Without it, stories using egg as a hidden-state or state-transition anchor have no grounded definition to point back to.
Consider adding a biological egg entry to natural_life_cycles before writing those stories.

---

## Progressive math story problems

Math problems in later wiki levels follow the same story-block format but use a persistent narrative
to increase mathematical complexity without increasing vocabulary load.

The same scene and characters carry across phases. The language stays simple and grounded.
Only the mathematical operation gets harder.

### Example structure

Setup (shared across all phases):
> Sally buys apples and takes them home. She puts 3 in the first bowl, 3 in the second, and 3 in the last bowl.

Phase 1 — counting / total:
```
[user]how many apples does Sally have?
[Ninereeds]Sally has three bowls and puts three apples in each one. Three and three and three makes nine. Sally has nine apples.
```

Phase 2 — subtraction from total:
```
[user]Bob comes and takes two apples. How many apples are left?
[Ninereeds]Sally had nine apples. Bob took two away. Nine take away two is seven. There are seven apples left.
```

Phase 3 — grouped reasoning, multi-part question:
```
[user]Bob takes one whole bowl of apples away. How many apples are left? How many bowls are left?
[Ninereeds]Each bowl had three apples. Bob took one bowl, so he took three apples. Nine take away three is six. There are six apples left. Sally started with three bowls and Bob took one. There are two bowls left.
```

### What each phase trains

| Phase | Operation | Concept dependency |
|---|---|---|
| 1 | Counting equal groups / addition | numbers, counting, total |
| 2 | Subtraction from a known total | subtraction, left, take away |
| 3 | Grouped subtraction, multi-part answer | containers, equal groups, two separate counts |

Phase 3 is the most demanding because the model must hold two levels simultaneously:
the group (bowl) and its contents (apples), and produce two answers from one action.
This is the foundation for multiplication and division without naming those operations yet.

### Design rules

- Keep the same characters and objects across all phases in one block.
- All vocabulary must be grounded before the problem is introduced.
- The setup sentence should use words from the same category or dependency chain.
- Each phase should have exactly one new mathematical demand — do not compound operations.
- Multi-part questions (phase 3 style) should only appear once grouped reasoning is stable.
- The answer should be written out as a short chain of reasoning, not just a number.

### Vocabulary pool

Characters: names from people_roles (child, person) or simple proper names.
Objects: concrete nouns from world-anchor categories (apple, bowl, book, coin, dog).
Actions: grounded verbs (buy, take, put, give, carry, eat).
Math words: from mathematical_concepts and mathematical_problems (how many, left, total, take away, each, together).

Avoid objects that require specialist knowledge to count or group (fractions of things, liquid measures).
Prefer objects that come in discrete, countable units.

### Final level — false belief (theory of mind under state change)

This is the hardest phase and should not appear until perspective_taking_and_theory_of_mind
and appearance_and_hidden_state are both stable in the model.

The scenario extends the same narrative but introduces a character who leaves before a state change occurs.
The question asks what the absent character *believes*, not what is actually true.

```
[user]Sally leaves the kitchen. While she is gone, Bob takes one bowl of apples away.
How many apples does Sally think she has when she comes back?
[Ninereeds]Sally put nine apples in three bowls before she left. She did not see Bob take a bowl away.
Sally still thinks she has nine apples, because she did not know anything changed.
But there are only six apples left in the kitchen now.
```

What makes this hard:

The model must track two separate states at the same time:
- The world as it actually is (six apples, two bowls)
- The world as Sally believes it to be (nine apples, three bowls)

These two states are different because Sally did not witness the change.
Her belief is based on what she observed before she left, not on what happened after.

This is the Sally-Anne false belief test from developmental psychology.
Children typically do not pass it reliably until around age four or five.

Concept dependencies for this phase:
- entity tracking with their own perception (people_roles, personal_identity)
- visible vs. hidden state change (appearance_and_hidden_state)
- perspective-taking and separate belief states (perspective_taking_and_theory_of_mind)
- temporal order: she left, then the change happened, so she did not see it (time, before/after)
- the distinction between what is true and what someone believes is true (logic: true, false, believe)

If the model cannot solve this cleanly at this level, it can be revisited later.

The Mommy Says Machine (see `docs/mommy_says_machine.md`) is the natural fallback here.
It tests the dragon on a concept, grades the response via Nemotron as teacher, and if the dragon
answers with the actual world state instead of Sally's belief state (a predictable failure mode),
the teacher issues a correction in the mommy says schema:
no explanation, no praise, just the correct form restated naturally in 2 sentences using known vocabulary.

Example correction for a false-belief failure:
> Dragon: "Sally has six apples."
> Correction: "Sally thinks she has nine apples. She left before Bob took a bowl away."

The machine logs the exchange, validates vocabulary, and produces correction pairs for human review.
Those pairs can feed a subsequent clean training run if the failure is consistent across runs.
This is the right tool for a failure mode that is conceptually clear but requires multiple
prerequisite concepts to be stable before it can be taught directly.
