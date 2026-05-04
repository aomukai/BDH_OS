# Training Data Directory Manifest

This document describes the purpose, format, and content rules for every directory and file in `training_data/`. Use this as a reference when adding new content so that new material fits the structure, vocabulary level, and format of what is already there.

---

## Root-level files

| File | Purpose |
|---|---|
| `audit_report.txt` | Master word list sorted by phase. Ground truth for which vocabulary word belongs in which phase. Consult before creating new phase files. |
| `dependency_graph.json` | Machine-readable graph of concept dependencies (3865 nodes). Used by the training harness to sequence learning. |
| `dependency_graph_progress.txt` | Progress ledger for incremental graph builds. Resume point if a build is interrupted. |
| `philosophy_audit_progress.txt` | Resume point for the philosophy file audit pass. |

---

## `phases/`

The phases directory contains the core vocabulary curriculum. Each phase targets a different vocabulary type and uses one of two answer formats. Every file covers exactly one word or phrase. Files are named `phase_N_NNN.md`.

### Format A — "This is X" (used in phases 1, 2, 3, 4, 6)

Each answer block has this structure:
- Opening anchor: `This is [X].`
- Five short declarative sentences describing the word
- One summary sentence combining two aspects: `[X] is [property A] and [property B].`

Questions vary slightly by phase but follow the pattern:
- What does X look like?
- Where is/does X appear?
- What does X do / how does X behave?
- What is X for / what does X give?

### Format B — "X is here" (used in phases 5 and 6, lighter vocabulary)

Each answer block has this structure:
- Opening anchor: `[X] is here.` (word is lowercased)
- Three simple sentences (definition, location, usage or quality)
- One closing restatement: `[X] means [definition].` or `[X] can be [context].`

Questions follow the pattern:
- What is X?
- Where is X?
- What does X do?
- What is X like?

---

### `phases/phase_1/` — Basic concrete physical nouns (1229 files)

**Vocabulary type:** Common physical objects and natural phenomena (acorn, bird, book, bread, sun, water, tree, etc.). The most fundamental and concrete layer of the vocabulary.

**Format:** Format A, four questions per file.

**What Ninereeds learns:** Multi-sensory grounding of concrete nouns — appearance, location, action, and purpose. The goal is that every basic object has a web of associated properties before any higher-order concept is introduced.

**Rules for new content:**
- Word must be a tangible, observable physical thing or natural phenomenon
- Answers must use simple subject-verb sentences, no subordinate clauses
- The summary sentence must combine exactly two properties
- Vocabulary in the answers should itself be phase_1 words where possible

---

### `phases/phase_2/` — Complex concrete nouns and built environments (343 files)

**Vocabulary type:** Places, built structures, social settings, and compound everyday objects (airport, apartment, bathroom, bedroom, bridge, camp, castle, kitchen, king, kit, etc.). More socially situated and structurally complex than phase 1.

**Format:** Format A, four questions per file. Question phrasing may be slightly varied (e.g., "how does X behave?" in place of "what does X do?").

**What Ninereeds learns:** Grounding for the social and built world — concepts that have contextual presence rather than purely physical presence. Introduces spatial and relational vocabulary.

**Rules for new content:**
- Word should be a noun that implies a social context or built environment
- Answers can reference human roles or actions (e.g., "a king rules a country")
- Still uses simple sentence structure — no complex subordination
- See `audit_report.txt` Phase 2 list for the canonical vocabulary set

---

### `phases/phase_3/` — Action verbs and "of-noun" compound phrases (602 files)

**Vocabulary type:** Two sub-types that appear in this phase:

1. **Action verbs used as concepts** (bang, beat, blend, blow, boil, build, burn, climb, etc.) — treated as observable phenomena rather than instructions
2. **"of-noun" compound phrases** (cup of water, glass of milk, pot of water, bowl of soup, bag of flour, etc.) — physical container-contents combinations

**Format:** Format A, four questions per file. For verbs, the word is used as a noun/concept ("This is boil." / "Boil is hot water with bubbles."). For of-nouns, the compound is the subject ("This is a cup of water.").

**What Ninereeds learns:**
- For verbs: that actions are observable physical processes with appearance, location, and function — not just commands
- For of-nouns: how containers and contents combine to form new concepts, and how physical state can change (tips, spills, boils)

**Rules for new content:**
- For verb entries: write the verb as a nominalized concept; do not write in the imperative
- For of-noun entries: the phrase must name a real physical combination (not a metaphor)
- Summary sentence must still combine two properties of the full compound phrase
- See `audit_report.txt` Phase 3 list for the canonical verb vocabulary

---

### `phases/phase_4/` — Biological and natural life processes (95 files)

**Vocabulary type:** Life-cycle and biological process words (birth, bleed, bloom, breath, cocoon, dead, fever, germ, hatch, heartbeat, infection, tadpole, yeast). A small, focused set.

**Format:** Format A, but **only one or two questions per file** (not four). Questions are process-oriented: "how does X form?", "where does X go?", "what does X do?", "what is X like?".

**What Ninereeds learns:** That living things undergo processes with causal structure — things form, change, grow, and end. Shorter files because the process itself is the teaching unit, not a full property grid.

**Rules for new content:**
- Word must describe a biological or natural life-cycle stage or process
- Use only one or two questions per file — do not pad to four
- Sentences must describe observable physical change (frost forms on grass, yeast makes dough rise)
- This is a small, curated set — adding here should be intentional

---

### `phases/phase_5/` — Goal-directed action sequences and social/emotional vocabulary (2001 files)

**Vocabulary type:** Two distinct sub-types in this phase:

1. **Goal-directed action sequences** (~243 files): Agent in an emotional/physical state (hungry, thirsty, tired, scared) takes a sequence of steps to resolve it (fly → reach → eat)
2. **Social/emotional/relational vocabulary** (~1800 files, Format B): Words for human roles, emotional actions, and relational concepts (ache, blame, brave, celebrate, family, farmer, etc.)

**Format:**
- Action sequences: Format A, single question per file ("what does a hungry bird do?"). Answer is a 6-line motion chain: location → movement → approach → action → outcome → summary goal sentence.
- Vocabulary entries: Format B ("X is here"), four questions per file.

**What Ninereeds learns:**
- Action sequences: that agents have states that motivate goal-directed behavior; that motion has structure (go-to, reach, act)
- Vocabulary entries: that social roles and emotional states are real things with location, behavior, and character — the same grounding applied to abstract human concepts

**Rules for new content:**
- Action sequence: agent must have a clear motivating state; the chain must resolve (bird reaches goal); summary sentence must state the purpose ("the bird flies to X to Y")
- Vocabulary entry (Format B): use lowercase word name throughout; keep answers short and simple; do not use complex subordinate clauses
- See `audit_report.txt` Phase 5 list for the canonical social vocabulary set

---

### `phases/phase_6/` — Abstract and cultural concepts (1151 files)

**Vocabulary type:** Cultural constructs, abstract social artifacts, and conceptual words (art, brand, chance, character, code, crime, deal, dollar, fault, festival, game, gift, grade, graph, etc.).

**Format:** Both Format A and Format B appear in this phase. Earlier files use Format A ("This is accord."), later vocabulary entries may use Format B ("nothing is here."). Match the format of neighboring files when adding new content.

**What Ninereeds learns:** That abstract ideas can be grounded in observable instances, purposes, and effects — even words like "coincidence" or "accord" can be described in terms of what they look like in the world.

**Rules for new content:**
- Even abstract concepts must be grounded in observable examples in the answers
- Avoid circular definitions ("X is when you feel X")
- If the word has a concrete manifestation (a chart, a grid, a dollar bill), lead with that
- Summary sentence should combine a defining property with a purpose or effect
- See `audit_report.txt` Phase 6 list for the canonical vocabulary set

---

## `philosophy/` — Socratic dialogue pairs (12 files)

**Vocabulary type:** Deep philosophical and conceptual topics organized into categories (World-as-Information, Knowledge and Doubt, etc.). Files are named `ninereeds_dialogues_cat[N].md`.

**Format:** Three-turn Socratic exchanges:
```
[STATEMENT]
A philosophical claim in plain language.

[USER]
A genuine objection or confusion — not a softball, a real pushback.

[NINEREEDS]
A substantive response that engages the objection, extends the idea,
and ends with a follow-up question for the user.
```

**What Ninereeds learns:** How to hold and develop a philosophical position; how to respond to genuine disagreement without capitulating or dismissing; how to ask productive follow-up questions rather than closing conversations.

**Rules for new content:**
- The USER objection must be a real challenge — something that would actually stump or test the claim
- The NINEREEDS response must engage the objection directly before extending the idea
- Every NINEREEDS response ends with a question that invites further reflection
- Responses are conversational, not lecture-like — no numbered lists or headers
- Topics should be genuinely interesting to think about, not trivially resolved

---

## `reasoning/` — Math and logic training (27 files)

**Vocabulary type:** Numbers, arithmetic operations, logical patterns, and quantitative reasoning.

**Format:** Varies by file type:

**Arithmetic fact files** (addition, subtraction, multiplication, division):
```
[user]
Teach me about [expression].

[Ninereeds]
Symbolic Mode:
[expression] = [result]

Verbal Mode:
[expression in words] equals [result in words].

Grounded Story Mode:
[concrete story with countable objects]

Reasoning Chain:
[one sentence explaining why the total changed]
```

**Bridge files** (00_bridge_word_to_symbol, 01_bridge_symbol_to_word):
Simple Q&A mapping number words ↔ numerals. Short 3–4 sentence answers.

**Logic and reasoning files** (conditional_if_then, basic_contradiction_checks, etc.):
Q&A format with plain-language explanations of logical relationships.

**What Ninereeds learns:** That symbols and words refer to the same quantities; that arithmetic describes real changes in the world; that logical statements have structural relationships that can be checked.

**Rules for new content:**
- Every arithmetic entry must include all four modes (Symbolic, Verbal, Grounded Story, Reasoning Chain)
- Grounded stories must use concrete, countable, familiar objects
- Bridge entries must be bidirectional — if you add a word→symbol entry, ensure the reverse exists
- Logic entries should use everyday scenarios, not abstract variables

---

## `triplet_stories/` — Narrative story training (4 tiers × 10 topics)

**Vocabulary type:** Story-format training across 10 thematic topic areas (animals and nature, body and health, food and meals, home and daily life, people and relationships, plus others). Each tier contains one file per topic.

**Format:** All tiers use the same prompt structure:
```
[user]tell me a story about [subject].
[Ninereeds][story text]
```

The tiers differ in complexity:

| Tier | Complexity level | Key features |
|---|---|---|
| 1 | Simple, 8-line stories | Present tense, concrete action, no characters |
| 2 | 12-line stories | Named child characters (Fern, Gus, Iris, Drew), basic dialogue, linear plot |
| 3 | Multi-paragraph | Causal connectives ("because", "so", "but then"), contrasts, multi-character |
| 4 | Grade 4–6 level | Multi-step sequences, explicit reasoning, "if/then" logic, temporal connectives ("first", "after", "finally") |

**What Ninereeds learns:**
- Tier 1: Basic story structure and subject-verb-object sentences
- Tier 2: That stories involve people, intentions, and dialogue
- Tier 3: Causal reasoning — events have causes and effects
- Tier 4: Multi-step reasoning, conditions, and explicit logical structure

**Rules for new content:**
- A new story within a tier must match the complexity level of the other stories in that tier
- Tier 2+ stories use the same recurring character names across topics (Fern, Gus, Iris, Drew, Clara, etc.)
- Every story must resolve — the character achieves or fails to achieve their goal by the end
- Do not introduce vocabulary above the tier's reading level
- When adding a new topic, create one file per tier and keep the topic consistent across all four

---

## `wiki/` — Encyclopedic concept articles (4 levels × ~10 topics per level)

**Vocabulary type:** Conceptual and domain knowledge organized by topic (emotions, communication, evidence and justification, perspective taking, etc.). Each level builds on the one before.

**Format:** Q&A format within section headers:
```
[user]what is X?
[Ninereeds][paragraph answer]
```

Level headers mark the source: `**Source Level N file:** training_data/wiki/wiki_N/filename.md`.

The levels differ in answer depth:

| Level | Style | Answer length | Key features |
|---|---|---|---|
| 1 | Definitional | 3–5 sentences | Direct definitions, concrete examples, one contrast ("X is not Y") |
| 2 | Subcategorization | 4–8 sentences, sectioned | Breaks concepts into sub-types; explains mechanics; grouped by section |
| 3 | Causal prose | 2 paragraphs | Explains how and why; contrasts related concepts; uses connectives |
| 4 | Explicit reasoning | 3 paragraphs | If/then chains; multiple causal links; emotional regulation examples; Grade 4–6 level |

**What Ninereeds learns:**
- Level 1: What key concepts mean at their most basic
- Level 2: How concepts subdivide and how their mechanics work
- Level 3: Why concepts work the way they do; how related concepts differ
- Level 4: How to reason explicitly about multi-step causal relationships

**Rules for new content:**
- A level N entry must trace back to a level N-1 source; document the source file in the header
- Level 1 answers must include at least one explicit contrast ("X is not Y")
- Each successive level must genuinely add depth — do not just pad level 1 text
- Topic consistency: if a topic exists at level 2, it should eventually exist at levels 3 and 4
- Do not introduce new topics at level 3 or 4 without a level 1 or 2 foundation

---

## Summary table

| Directory | Count | Vocabulary type | Format | What it teaches |
|---|---|---|---|---|
| `phases/phase_1/` | 1229 | Basic concrete nouns | 4-question, "This is X" | Physical object grounding |
| `phases/phase_2/` | 343 | Built environments, complex nouns | 4-question, "This is X" | Social and spatial context |
| `phases/phase_3/` | 602 | Action verbs + of-noun compounds | 4-question, "This is X" | Actions as observable phenomena; compound objects |
| `phases/phase_4/` | 95 | Biological/life-cycle processes | 1–2 question, "This is X" | Living processes and physical change |
| `phases/phase_5/` | 2001 | Goal-directed sequences + social vocab | Action chain or "X is here" | Agent motivation and social/emotional grounding |
| `phases/phase_6/` | 1151 | Abstract/cultural concepts | "This is X" or "X is here" | Abstract concept grounding |
| `philosophy/` | 12 | Philosophical topics | 3-turn Socratic dialogue | Position-holding, productive disagreement |
| `reasoning/` | 27 | Math and logic | Multi-mode Q&A | Symbol-world correspondence; arithmetic reasoning |
| `triplet_stories/` | 40 (4×10) | Narrative by topic | Story Q&A, 4 tiers | Story structure, causal reasoning, reading level |
| `wiki/` | ~36 (4×9) | Conceptual domains | Section Q&A, 4 levels | Definitional → causal → explicit reasoning |
