# Missing Curriculum Terms

This file tracks foundational high-frequency terms that the wiki corpus relies on but the phase 1-5 curriculum does not yet teach explicitly.

---

## Purpose

The wiki corpus uses abstract scaffold language that the curriculum never explicitly grounds. This creates a comprehension gap: the model encounters terms like `word`, `sentence`, `thought`, and `thing` throughout the wiki but has no curriculum anchor for them.

This file:
1. Identifies the highest-impact missing terms
2. Prioritizes them by dependency count and cross-file usage
3. Recommends resolution strategy for each

---

## Analysis Summary (2026-04-18)

### Current curriculum coverage

The phase 1-5 curriculum covers:
- **352 files** across 5 phases
- Primarily concrete nouns: animals, objects, body parts, places, food, clothing, tools, vehicles
- Some compound words and part-of phrases in Phases 2-3
- Animal action scenarios in Phase 5

**What the curriculum does not cover:**
- Meta-linguistic terms (`word`, `sentence`, `letter`)
- Abstract cognitive terms (`thought`, `idea`, `meaning`)
- Epistemic terms (`true`, `real`, `fact`)
- Economic terms (`money`, `cent`, `price`)

### Wiki dependency analysis

Cross-referencing `ranked_gap_list.md` and `dependency_ledger.md`:

| Term | Wiki files using it | Centrality | Current status |
|------|---------------------|------------|----------------|
| `thing`/`object` | ~50+ files | Very high | No anchor |
| `word` | ~20+ files | High | No anchor |
| `sentence` | ~15+ files | Medium-high | No anchor |
| `idea`/`thought` | ~15+ files | Medium-high | No anchor |
| `true` | ~10+ files | Medium | No anchor |
| `real` | ~8+ files | Medium | No anchor |
| `money` | ~5+ files | Medium | No anchor |

---

## Tier 1 — Critical (Recommended for backfill)

These terms are foundational scaffolding that the wiki assumes but never explains.

### 1. `thing` / `object`

**Impact:** Very high — nearly all "what is X?" entries implicitly assume understanding of "thing"

**Usage in wiki:**
- `abstract_operators_entries.md` teaches `category` but not `thing`
- Countless entries say "X is a thing that..." or "X is an object used for..."

**Recommendation:** Add a curriculum entry defining `thing` as the most general anchor for physical items. Definition could be: "A thing is something that can be seen or touched."

**Curriculum placement:** Early Phase 5 or new Phase 5B bridging batch

---

### 2. `word`

**Impact:** High — communication, storytelling, and language wiki files all depend on it

**Usage in wiki:**
- `communication_acts_and_language_entries.md` uses `word` without defining it
- `storytelling_and_narrative_structure_entries.md` uses `word` frequently

**Recommendation:** Add a curriculum entry defining `word` as a unit of speech/writing. Definition could be: "A word is a sound or a group of letters with a meaning."

**Curriculum placement:** Phase 5B or late Phase 4 extension

---

### 3. `sentence`

**Impact:** Medium-high — storytelling, communication, and logic files assume sentence-level understanding

**Usage in wiki:**
- Used in story structure and communication entries
- Needed for teaching what a question, statement, or command is

**Recommendation:** Add after `word`. Definition could be: "A sentence is a group of words that tells a whole thought."

**Curriculum placement:** Phase 5B (after `word`)

---

### 4. `idea` / `thought`

**Impact:** Medium-high — logic, learning, metacognition, opinion files all depend on it

**Usage in wiki:**
- `logic_entries.md` uses `thought` implicitly
- `learning_memory_and_metacognition_entries.md` needs cognitive vocabulary
- `opinions_persuasion_and_simple_debate_entries.md` uses `idea` heavily

**Recommendation:** Add a curriculum entry treating `thought` as a noun (distinct from `think` verb). Definition could be: "A thought is something that happens in your mind."

**Curriculum placement:** Phase 5B

---

## Tier 2 — Important (Recommended for curriculum extension batch)

These terms are important for wiki comprehension but less universally assumed than Tier 1.

### 5. `true`

**Impact:** Medium — logic, evidence, and fact/opinion language depends on it

**Usage in wiki:**
- `logic_entries.md` teaches `truth` and `fact` but the adjective `true` needs grounding
- `evidence_and_justification_entries.md` uses "true" frequently

**Recommendation:** Add curriculum entry. Definition could be: "True means something that really happened or really is."

**Curriculum placement:** Phase 5B (after `thought`)

---

### 6. `real`

**Impact:** Medium — needed for reality checks, exist-language, and truth-related concepts

**Usage in wiki:**
- Needed to distinguish real from imaginary
- `imagination_and_pretend_play_entries.md` benefits from this contrast

**Recommendation:** Add curriculum entry. Definition could be: "Real means something that is there and can be found."

**Curriculum placement:** Phase 5B (after `true`)

---

### 7. `money`

**Impact:** Medium — economic and shopping wiki files depend on it

**Usage in wiki:**
- `money_trade_and_shopping_entries.md` has 22 entries about economic concepts
- All coin/price/value entries assume understanding of `money`

**Recommendation:** Add curriculum entry. Definition could be: "Money is what people use to buy and sell things."

**Curriculum placement:** Phase 5B (practical-life extension)

---

## Tier 3 — Lower priority (Document but defer)

These terms are useful but less critical for immediate wiki comprehension.

| Term | Notes | Status |
|------|-------|--------|
| `truth` | Noun form of `true`; depends on `true` first | Defer until `true` is added |
| `reality` | Noun form of `real`; more abstract | Defer until `real` is added |
| `cent` | Supports coin-value talk | Defer unless coin curriculum expands |
| `meaning` | Abstract; depends on `word` | Defer until `word` is added |
| `fact` | Covered in `logic_entries.md` wiki | Wiki anchor may suffice |
| `opinion` | Covered in wiki files | Wiki anchor may suffice |

---

## Resolution Strategy

### Phase 5B bridging batch (recommended)

Create a small curriculum extension batch (~8-12 files) covering the Tier 1 and Tier 2 terms. This batch would:

1. Follow the standard curriculum format:
   - 4 `[user]`/`[assistant]` blocks per file
   - 5 lines per assistant response (4 body + 1 summary)
   - No pronouns
   - No vocab in summary that hasn't appeared earlier

2. Sequence properly:
   - `thing` first (most foundational)
   - `word` second
   - `sentence` third (depends on `word`)
   - `thought`/`idea` fourth
   - `true` fifth
   - `real` sixth
   - `money` seventh (practical extension)

3. Use concrete examples throughout:
   - "A ball is a thing" (grounding `thing`)
   - "Dog is a word" (grounding `word`)
   - "The dog runs is a sentence" (grounding `sentence`)

### Alternative: Wiki-only coverage

If curriculum backfill is too disruptive, consider adding wiki entries instead:
- Add `thing`/`object` to `abstract_operators_entries.md`
- Add `word`/`sentence` to `communication_acts_and_language_entries.md`
- Add `thought`/`idea` to `logic_entries.md`

This is a less robust solution because:
- Wiki entries don't have the same repetition structure as curriculum
- No 4-block drilling format
- May create dependency loops (wiki teaches what wiki needs)

**Recommended approach:** Curriculum backfill with Phase 5B batch is preferred.

---

## Implementation Notes

When creating the Phase 5B batch:

1. **Follow curriculum constraints strictly**
   - See `docs/wiki.md` and `AGENTS.md` for format rules
   - Each file: 4 blocks, each block: question + 5-line answer
   - Cumulative vocabulary bank applies

2. **Update training sequence**
   - Add new files to `training_sequence.txt`
   - Place after Phase 5 but before wiki training
   - Update `concept_index.md` with new entries

3. **Validate dependencies**
   - Ensure `thing` appears before any file using "a thing"
   - Ensure `word` appears before `sentence`
   - Cross-check against wiki files that use these terms

---

## Status

| Term | Priority | Resolution | Status |
|------|----------|------------|--------|
| `thing`/`object` | Tier 1 | Phase 5B curriculum | Planned |
| `word` | Tier 1 | Phase 5B curriculum | Planned |
| `sentence` | Tier 1 | Phase 5B curriculum | Planned |
| `thought`/`idea` | Tier 1 | Phase 5B curriculum | Planned |
| `true` | Tier 2 | Phase 5B curriculum | Planned |
| `real` | Tier 2 | Phase 5B curriculum | Planned |
| `money` | Tier 2 | Phase 5B curriculum | Planned |
| `truth` | Tier 3 | Defer | -- |
| `reality` | Tier 3 | Defer | -- |
| `cent` | Tier 3 | Defer | -- |

---

## Change Log

| Date | Change |
|------|--------|
| Initial | Created with candidates: thought, real, reality, true, truth, money, cent |
| 2026-04-18 | Step 16 analysis: Identified Tier 1-3 priorities, cross-referenced with ranked_gap_list.md and dependency_ledger.md, recommended Phase 5B bridging batch strategy |
