# Prompt: Wiki Category Suggestions for BDH

---

## Context

We are training a small language model called **BDH** (Baby Dragon Hatchling) to hold natural conversations with children aged 6–10. The model is intentionally small and runs offline on a single consumer GPU. Its entire knowledge comes from a hand-built training corpus — it knows nothing it has not been explicitly taught.

The corpus has two layers:

1. **Curriculum files (phases 1–5):** Short Q&A exchanges that teach the model basic concepts — objects, animals, nature, simple logic, actions, states. Think of this as the model learning to "see the world."

2. **Wiki files:** Slightly longer "what is X?" entries that define concepts at a Grade 4–6 reading level. Format is always:

```
[user]what is a X?
[assistant]5–6 simple sentences. Identity + 2–3 concrete facts + 1 contrast.
X is not Y.
```

The wiki layer is where the model learns the **relational, social, and conversational glue** that lets it actually talk to children — not just label objects, but understand routines, relationships, rules, and feelings.

---

## What the wiki already covers

These topic files already exist in the corpus:

- Animals (mammals, birds, fish/sea, insects, reptiles/amphibians)
- Body parts
- Colors
- Emotions — 31 entries (happiness, sadness, anger, fear, surprise, love, pride, shame, excitement, boredom, and more)
- Foods and drinks (general, fruits, vegetables)
- Home objects (three files)
- Home rooms
- Logic concepts (cause/effect, fact/opinion, goal/problem/solution, logical operators)
- Mathematical concepts (numbers 0–10, shapes, operations)
- Mathematical problems (Grade 1 arithmetic)
- People and family roles (father, mother, brother, sister, family, boy, girl, neighbour, etc.)
- Places and landforms
- Plants and nature
- Professions (21 entries: farmer, doctor, nurse, teacher, baker, builder, sailor, carpenter, etc.)
- Space (celestial objects)
- STEM concepts (temperature, states of matter, forces, biology, senses, motion)
- Time (temporal anchors, calendar vocabulary)
- Tools and kitchenware
- Topology / spatial parts
- Vehicles and transport
- Verbs (give, take, hold, drop, catch, make, talk, listen, help, etc.)
- Weather and celestial phenomena

---

## What has already been proposed

Nine AI models were previously consulted and their suggestions merged into the following backlog. **Do not repeat these categories** — we already have them.

### Already in backlog (do not suggest again):

Animal Care and Pet Keeping · Animal Habitats and Homes · Art and Creative Expression · Boundaries and Consent · Chores and Home Responsibilities · Civic Responsibility and Community Rules · Clothing and Apparel · Communication Acts and Language · Community Places and Services · Conflict Resolution and Relationship Repair · Construction and Material Transformations · Cooking and Food Preparation · Daily Routines and Self-Care · Data, Charts, and Graphs · Directions and Navigation · Emotions Beyond Basic States · Environmental Care and Stewardship · Family Roles and Kinship (COVERED) · Food Groups and Nutrition · Fractions and Sharing Quantities · Friends and Peer Interactions · Future Planning and Goals · Garden and Planting Basics · Greetings and Social Salutations · Growth and Life Stages · Health and Wellness · Hobbies and Interests · Holidays and Celebrations · Home Rooms and Household Spaces (COVERED) · Humor and Figurative Language · Imagination and Pretend Play · Inclusion, Bullying, and Kindness · Learning, Memory, and Metacognition · Levels of Intensity and Gradation · Machines and Simple Mechanisms · Manners, Politeness, and Social Etiquette · Material Composition · Meals and Mealtime Talk · Measurement and Comparison · Money, Trade, and Shopping · Movement and Physical Action · Musical Instruments · Natural Life Cycles and Processes · Numbers Beyond 10 · Online Safety and Privacy · Opinions, Persuasion, and Simple Debate · Ownership and Sharing · Personal Identity and Self-Description · Perspective-Taking and Theory of Mind · Play, Games, and Sports · Professions and Community Helpers (COVERED) · Safety, Rules, and Emergency Awareness · School Life and Learning · Seasonal Activities · Sensory Experiences · Shadow and Light Phenomena · Simple Physics: Energy and Power · Sleep and Rest · Social-Emotional Learning Competencies · States of Being and Condition · Storytelling and Narrative Structure · Technology and Digital Media · Time, Schedules, and Calendar (COVERED) · Transport and Travel (COVERED) · Wants, Needs, and Preferences · Weather and Seasons (COVERED)

---

## Your task

Suggest **new wiki categories** that are NOT in the list above and NOT already covered by the existing files.

Think about what a child aged 6–10 actually talks about in daily life that is missing. Consider:

- Concepts the child encounters at home, school, outdoors, or in social situations
- Language the child needs to *describe*, *explain*, *ask about*, or *reason about* their world
- Things the model would need to know to respond naturally when a child brings up a topic

For each category you suggest, provide:

```
CATEGORY: [name]
EXAMPLES: [5–8 concrete examples of concepts or vocabulary within this category]
DEPENDS ON: [concepts from the existing corpus this builds on]
SEQUENCE: early / middle / late
REASON: [one or two sentences explaining why this is a genuine gap]
```

**Sequence guide:**
- **early** — foundational for daily interaction; needed before most other topics
- **middle** — expands explanation, comparison, and social reasoning
- **late** — higher-level pragmatics, abstraction, or specialist knowledge

Aim for **10–20 genuinely new categories**. Focus on quality over quantity. If you are unsure whether something is already covered, include it anyway with a note.
