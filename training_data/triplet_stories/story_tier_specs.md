# Story Tier Specs

Canonical rewrite-stage spec for `training_data/triplet_stories/`.

These stories are short training scenes for a language model with Hebbian learning.
They are not wiki entries, not definitions, and not moral lessons.

Their job is to:
- show familiar words in clear grounded situations
- vary sentence structures without becoming confusing
- build a bridge between language and world-knowledge through simple events
- stay easy for a young child to follow

---

## Required stored-file format for all story tiers

Every stored story file in `training_data/triplet_stories/` should use repeated training pairs instead of markdown tables or `##` story headings.

Canonical storage pattern:
- `[user]tell me a story about <anchor>.`
- `[Ninereeds]` followed by the story text for that one item

Format rules:
- one story = one `[user]` / `[Ninereeds]` pair
- the assistant block contains only the story text for that item
- keep the tier-specific structure inside the story body (sentence count, dialogue rules, paragraphing, etc.)
- Tier 1 retrofit work and all future Tier 2 / Tier 3 / Tier 4 creation or review should enforce this stored-file format

---

## Tier 1

### Purpose
Tier 1 is the first story layer after the earlier definitional curriculum and wiki material.

Tier 1 should:
- keep scenes simple, concrete, and easy to picture
- show the anchor and support concepts together in a small event
- introduce basic pronoun use in the clearest possible way
- help the model move from repeated noun phrases toward simple reference tracking
- stay close to immediate visible action, not explanation

### Required shape
- 8 sentences per story
- one anchor + two support concepts
- one small scene or event
- one main subject only
- clear beginning, middle, and end
- end inside the scene, not with a lesson or summary

### Tier 1 should contain
- a clearly visible anchor
- both support concepts used naturally in the event
- simple concrete actions
- simple locations, objects, and sensory details when useful
- a clear first mention of the main subject
- later sentences may use `he`, `she`, or `it` only after the referent is obvious

### Tier 1 is teaching
- noun-to-pronoun reference in a clear single-subject story
- simple event sequencing
- familiar words appearing in slightly varied sentence shapes
- grounded co-occurrence of anchor and support concepts

### Avoid in Tier 1
- names for recurring characters
- multi-character social tracking
- long causal chains
- abstract lessons or morals
- textbook phrasing
- poetic or literary inversion
- heavy description with little action
- ambiguous pronouns
- **quoted dialogue** (Tier 1 uses narrated indirect discourse only; e.g., "The child asks what a dog is.")

---

## Tier 2

### Purpose
Tier 2 builds on Tier 1 by adding more narrative structure and discourse variety.

Tier 2 should:
- keep stories concrete and child-readable
- make event chains longer
- introduce named characters where useful
- expand reference handling from noun to name to pronoun
- give the model richer but still controlled sentence variation

### Required shape
- 12 sentences per story
- one anchor + two support concepts
- one clear scene with a longer event chain
- usually one main character, sometimes one secondary participant if needed
- the story moves through a fuller sequence of actions
- end inside the scene, with the event resolved or naturally paused

### Tier 2 should contain
- a clear setting or scene frame
- the anchor introduced as the central subject
- when useful, a simple recurring name for the main subject
- support concepts integrated into the action, not pasted in
- a longer chain of events than Tier 1
- one mild obstacle, surprise, delay, or change
- a clear resolution or settling point by the end
- **quoted dialogue with explicit speaker tags** where useful (e.g., "'What is a dog?' the child asks.")

### Tier 2 is teaching
- setting-first or scene-first framing
- noun to name to pronoun alternation
- longer reference chains without confusion
- richer temporal flow across a story
- broader sentence variation than Tier 1
- coherent mini-narratives built from familiar vocabulary
- **basic quotation and speaker-tag usage**

### Avoid in Tier 2
- dense adult-sounding prose
- too many characters
- confusing pronoun chains
- abstract reflection or hidden psychological narration
- sudden jumps in time with no clear bridge
- moralizing or summary endings
- **overuse of quoted dialogue** (keep it sparing and always tagged)
- **short elliptical dialogue** (save for Tier 3+)
- clever phrasing that reduces clarity

---

## Tier 3

### Purpose
Tier 3 introduces more complex reasoning and structural variety while maintaining a grounded narrative.

Tier 3 should:
- introduce explicit causal chains ("because", "so", "if... then")
- include contrasts and comparisons using "but" or "instead"
- move into multi-paragraph structure to show topical grouping
- transition into more natural, elliptical dialogue
- keep vocabulary strictly grounded in Phase 1-5 and Wiki Level 1

### Required shape
- 8–12 sentences per story
- 2–3 small paragraphs
- one anchor + 3-4 related concepts
- one explicit cause-effect chain
- one comparison or contrast with a related concept
- end with a settling point or a summarizing observation within the scene

### Tier 3 should contain
- varied sentence openings
- "but" used to show contrast or exception (max one per story)
- "because" or "so" to show reasoning or result
- named characters reused from the corresponding Tier 2 story thread
- **short elliptical dialogue** where appropriate (e.g., "'Where is it?' 'In the tree.'")

### Tier 3 is teaching
- multi-paragraph coherence
- causal reasoning and "because" links
- contrastive reasoning with "but"
- ellipsis in dialogue (relying on context)
- broader syntactic variety (varied sentence starts)

### Avoid in Tier 3
- more than one "but" per story
- overly dense or flowery prose
- ungrounded vocabulary
- abstract themes or metaphors
- confusing character tracking

---

## Tier 4

### Purpose
Tier 4 is the most advanced story layer, approaching natural short-form explanation through narrative.

Tier 4 should:
- handle multiple cause-effect links and explicit reasoning
- show sequences involving multiple steps across time or logic
- maintain a consistent Grade 4-6 reading level
- reinforce world-knowledge through complex but grounded scenarios
- provide the highest level of linguistic variety in the story corpus

### Required shape
- 10–15 sentences per story
- 2–3 paragraphs
- one anchor + 4-5 related concepts
- multiple cause-effect links
- at least one explicit sequence across multiple steps
- at least one comparison with a related concept

### Tier 4 should contain
- explicit reasoning about actions or outcomes
- temporal markers for multi-step sequences ("first," "after," "finally")
- 1-2 contrasts or exceptions
- consistent reuse of character names from Tier 2 and Tier 3
- natural dialogue patterns, including ellipsis and questions

### Tier 4 is teaching
- tracking multiple causal links
- multi-step temporal and logical sequences
- advanced sentence variety and paragraph flow
- integrated reasoning within a narrative
- Grade 4-6 reading level structures

### Avoid in Tier 4
- encyclopedic depth (keep it narrative, not a textbook)
- adult-level abstraction
- confusing or overlapping causal chains
- excessive dialogue that obscures the action
- poetic or archaic language

---

## Tier difference at a glance

### Tier 1
- 8 sentences
- one simple concrete event
- one clearly introduced subject
- first safe use of pronouns
- no names needed
- minimal discourse complexity

### Tier 2
- 12 sentences
- longer event chain
- scene-setting matters more
- named characters can appear
- noun / name / pronoun alternation
- one mild obstacle or change is allowed
- more sentence variety, still tightly controlled

### Tier 3
- 8–12 sentences
- 2–3 paragraphs
- explicit cause-effect chain
- contrast ("but") and comparison
- short elliptical dialogue allowed
- reuse of named characters from Tier 2

### Tier 4
- 10–15 sentences
- 2–3 paragraphs
- multiple causal links
- multi-step sequences
- explicit reasoning
- Grade 4–6 reading level

---

## Global rules for all tiers
- stories are scenes, not definitions
- teach through what happens, not through explanation
- anchor and support concepts must all visibly matter
- keep everything grounded in child-level everyday reality unless the source material clearly requires otherwise
- avoid filler sentences that only add atmosphere
- do not end with "the lesson is" energy
- keep the meaning recoverable from context
- simplicity matters more than prettiness
