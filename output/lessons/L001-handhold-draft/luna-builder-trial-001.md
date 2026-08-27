# Luna builder trial 001 — L001

**Actor:** Luna  
**Lesson:** L001 (`kitchen_labels`)  
**Decision:** `alarm_blocked`  
**Mode:** handhold, authoring only; no pixels approved, no training dispatched

## Diagnosis

The frozen Point is coherent and small: `cup`, `plate`, `spoon`, `bowl`. I select one
complete lexical set (four things), not the default sixteen things. The default is a
dosage guideline; adding unrelated table nouns would change the Point. The set still
requires all sixteen controlled cells: four affirmative/yes, four negative/no, four
W-question, and four OR-question cells, in that order, before mixed practice.

The existing `lesson-draft.json` is not a proof of this. Its negative cells repeat a
label and its W cells are silent image-yields; neither is a real negative/no or
W-question family. Its affirmative cells are immediate repetitions rather than an
elicited yes operation. Its five “book” pages are a label parade, not a small story,
and it has no closing recap. The asset records are commissioned/pending and have no
review receipt, so their visual claims are not yet usable evidence.

The current learner artifacts are explicitly handhold fixtures. They establish the
starting boundary (random 1.2B parameters, no bankable grounding, system, grammar,
or context) and report only `Hello!` and `I'm X.` as eligible closure vocabulary.
They do not establish object-reference questions or their response contracts. The
curriculum's nominal L000 frontier lists such forms, but a curriculum listing is not
learner evidence, and the supplied closure does not bind them. Therefore a real,
understandable 4×4 L001 cannot be executed from the current evidence. This is an
alarm, not permission to smuggle grammar into L001.

## Scope judgment

| Decision | Bound |
|---|---|
| Point | Exactly `cup`, `plate`, `spoon`, `bowl` |
| Sets | 1 set, `set-table-objects-01` |
| Controlled cells | 16 total: 4 affirmative/yes + 4 negative/no + 4 W + 4 OR |
| Mixed practice | 8 planned prompts, extendable to 16 scored prompts only under the frozen stop rule |
| New vocabulary | No words beyond the four Point items |
| World status | Noncanonical instructional display; no people, place, event, relationship, or persistent state |
| Story status | Required by the current full-lesson policy, despite curriculum-v6's earlier `picture_book: no` field |

The selected count is four because the Point itself contains exactly four distinct
referents and the learner is at the first post-bootstrap boundary. A second set would
require four more Point-safe referents not present in the frozen Point; it is not
justified.

## Language and prerequisite gate

The target novelty is lexical only. A usable L001 4×4 needs the learner to understand
at least these non-target forms before L001: `this`, `is`, `a`, `what`, `yes`, `no`,
and `or`, plus the question/answer constructions:

* `Is this a X?` → `Yes.` or `No.`
* `What is this?` → `X.`
* `Is this a X or a Y?` → `X.` or `Y.`

These are not vocabulary slots, but they are still language prerequisites. Neither
`this is`, `is this`, `what`, the article `a`, nor object-directed yes/no/W/OR use is
in the supplied known closure. L000's `Are you X?`, `Who are you?`, and identity
responses cannot be silently repurposed as object-reference grammar. “Cup?” or a
silent turn is not a real W-question, and selecting a crop is not a negative/no answer.

Smallest repair: before compiling L001, obtain an operator-approved, hash-bound
evidence artifact from an actual prerequisite lesson (or a revised L000 evidence
package only if that lesson really taught these forms) that demonstrates comprehension
and controlled use of the three constructions and `Yes.`/`No.`. The repair must list
the exact forms, response contracts, attempts, and immediate lower-support retests.
It must not merely add them to `known-closure.json` by assertion. If a new bridge
lesson is needed, insert it before L001 and leave L001's Point unchanged. Until that
repair exists, all routine cells below are proposals, not executable teacher text.

## Proposed lesson routine (after the language and visual gates pass)

Every teacher turn would carry the known/frontier/rescue labels in the runtime trace.
The only frontier words are the four object labels. The bridge forms above must be
marked `established` by evidence before this routine is admitted.

### 1. Presentation

1. Show one reviewed full scene containing exactly one cup, one plate, one spoon, and
   one bowl, spatially separated. Focus one object at a time with a literal crop.
2. For each object, show the crop, say its label once (`Cup.` etc.), then yield a
   non-scored attend/point or image-match response. Do not count pointing as target
   language production.
3. Re-show the full scene and demonstrate the repaired question contracts with the
   cup, then a different object. Elicit a prediction before confirming. No new noun,
   property, relation, or story fact is introduced.
4. Confirm that `yes`, `no`, `what`, `this`, `is`, `a`, and `or` are understood from
   prerequisite evidence; if not, freeze and call the alarm rather than reteaching
   them inside L001.

### 2. Controlled square — separate blocks

The following is the complete one-set square. Each row is one real cell, with the
answer contract shown explicitly. The same four object kinds are rotated through each
family; object order and distractors are not used as hidden cues.

#### Affirmative/yes block (4)

| ID | Stimulus | Expected answer | Claim |
|---|---|---|---|
| A-CUP | Focus the cup crop; `Is this a cup?` | `Yes.` | The focused referent is cup. |
| A-PLATE | Focus the plate crop; `Is this a plate?` | `Yes.` | The focused referent is plate. |
| A-SPOON | Focus the spoon crop; `Is this a spoon?` | `Yes.` | The focused referent is spoon. |
| A-BOWL | Focus the bowl crop; `Is this a bowl?` | `Yes.` | The focused referent is bowl. |

These are yes predictions, not label echoes. `Yes.` is scored separately from the
object concept and target-language production.

#### Negative/no block (4)

| ID | Stimulus | Expected answer | Claim |
|---|---|---|---|
| N-CUP | Focus the cup crop; `Is this a plate?` | `No.` | Cup is not plate. |
| N-PLATE | Focus the plate crop; `Is this a cup?` | `No.` | Plate is not cup. |
| N-SPOON | Focus the spoon crop; `Is this a bowl?` | `No.` | Spoon is not bowl. |
| N-BOWL | Focus the bowl crop; `Is this a spoon?` | `No.` | Bowl is not spoon. |

Negative feedback remains only `No.` during this block. Luna may then use the
smallest licensed cue and immediately retest the same item unmarked; it must not append
`This is ...` or another later operation.

#### W-question block (4)

| ID | Stimulus | Expected answer | Claim |
|---|---|---|---|
| W-CUP | Focus the cup crop; `What is this?` | `Cup.` | Retrieve the focused label. |
| W-PLATE | Focus the plate crop; `What is this?` | `Plate.` | Retrieve the focused label. |
| W-SPOON | Focus the spoon crop; `What is this?` | `Spoon.` | Retrieve the focused label. |
| W-BOWL | Focus the bowl crop; `What is this?` | `Bowl.` | Retrieve the focused label. |

The W prompt is spoken and asks for information. A silent crop is presentation or
retrieval, not a W-question cell.

#### OR-question block (4)

| ID | Stimulus | Expected answer | Claim |
|---|---|---|---|
| O-CUP-PLATE | Focus cup; `Is this a cup or a plate?` | `Cup.` | Select the correct first alternative. |
| O-PLATE-CUP | Focus plate; `Is this a plate or a cup?` | `Plate.` | Reversal prevents first-position guessing. |
| O-SPOON-BOWL | Focus spoon; `Is this a spoon or a bowl?` | `Spoon.` | Select the correct first alternative. |
| O-BOWL-SPOON | Focus bowl; `Is this a bowl or a spoon?` | `Bowl.` | Reversal prevents first-position guessing. |

Both alternatives are Point items and must be known before an OR cell is run. An
answer naming the wrong alternative is an object-label error, not a grammar success.

### 3. Mixed practice and transfer

After all four blocks complete, sample this eight-prompt mixed pool in a declared
seed/order: W-SPOON, O-PLATE-CUP, A-BOWL, N-CUP, W-PLATE, A-CUP, O-BOWL-SPOON,
N-SPOON. Add the remaining eight family-balanced prompts only when needed and only
within the cap of 16 scored mixed prompts. Vary crop versus full-scene focus and
position, while changing one visual factor at a time. Score first attempts,
intervention, lower-support retest, family consistency, and target-language output
separately. A semantically correct non-English answer can show concept understanding
but not English production.

The optional transfer is one fresh reviewed arrangement with the same four object
kinds, no new object, style, or relation. Ask one prompt from each family, not a new
lesson. Do not claim transfer if the learner succeeds only with a crop or position cue.

### 4. Picture book and comprehension

The story is noncanonical and does not update the world. It is a visual sequence in
which the same four objects gather on one neutral tabletop: a cup is present; a plate
joins; a spoon joins; a bowl joins; then all four remain together in a new arrangement.
The event is shown by persistent object identity and changing composition, not by
introducing an unlicensed verb or noun in the captions. The book therefore has a
small visual arc rather than five isolated labelled crops. See the storyboard below.

After the page sequence, ask five closed comprehension checks using only the repaired
question forms and the four Point labels: W-CUP, A-PLATE, N-SPOON (with a plate
distractor), O-BOWL-SPOON, then a final full-scene W check. A page caption may be the
single licensed object label; it must not be treated as evidence merely because it
was read aloud. Focus and page identity are logged.

### 5. Closing recap

Show the full scene without labels. Ask one unmarked W question per object in a
randomized order, then one yes and one OR item selected from the already completed
blocks. Recap success only if the learner answers without markers or copied captions;
record object concept, response family, and English production independently.

## Picture-book storyboard and asset commissions

No asset is approved by this trial. Each generated master needs mechanical checks and
independent pixel review before it can enter a frozen lesson. Crops must be literal,
derived from an accepted parent with integer coordinates, and retain parent/output
hashes.

| Page | Visual story beat | Required language | Commission / acceptance |
|---|---|---|---|
| B1 | Neutral tabletop; one cup at a stable, clearly visible position | `Cup.` | Reviewed photograph or clean instructional illustration; exactly one cup, handle visible, no other lesson object, text, hand, person, logo, or extra prop. |
| B2 | Same tabletop/camera; the plate is now present beside the cup | `Cup. Plate.` | Identity and cup persistence match B1; exactly one shallow plate; no extra object or scene change that implies a new lesson fact. |
| B3 | Same scene; spoon has joined the pair | `Cup. Plate. Spoon.` | Exactly one ordinary spoon, complete and separable; cup and plate remain identifiable and in-frame. |
| B4 | Same scene; bowl has joined the group | `Cup. Plate. Spoon. Bowl.` | Exactly one deep bowl; all four remain distinct; no food, people, hands, labels, or hidden duplicate. |
| B5 | The four objects remain together in a changed, uncluttered arrangement | Point labels only | Fresh composition for transfer, preserving four identities; no extra relation or object is scored. |

Commission one accepted neutral-table master for the sequence plus a separately
reviewed varied-realization master (photograph or drawing) for transfer. Derive
`cup-crop`, `plate-crop`, `spoon-crop`, and `bowl-crop` deterministically from each
accepted parent. Record entity boxes, crop margins, parent hash, output hash, review
receipt, and claim-by-claim results. The existing pending assets cannot be presumed to
meet these requirements, and this document does not generate, edit, or approve them.

## Intervention decision rules

* `CONTINUE` only after a valid answer or a bounded lower-support retest.
* `PRESENT_AGAIN` / `BACKTRACK` after a meaningful item failure, replaying the same
  four-object contrast without changing the Point. Presentation replay is capped at
  three episodes per item and does not erase the original failure.
* Use the smallest cue: refocus crop, repeat the licensed question, forced choice,
  then a model answer. Pair any support with an immediate unmarked retest; supported
  output is never independent mastery. Do not use grammar markers for a lexical item
  unless the repaired contract explicitly licenses them.
* `TRAIN_MORE` only when the trace indicates a breadth/visual-instance problem:
  commission or select one additional reviewed realization for each of the four same
  objects and run a bounded family-balanced check. It may not add nouns, relations,
  or grammar and may not dispatch training.
* `TRAIN_LONGER` only when the four items are understood but mixed retrieval is weak:
  extend varied mixed practice, changing order/scene/focus while holding the Point
  fixed, up to 16 scored mixed prompts.
* `CALL_SOL` for unresolved language interpretation, contradictory answers, malformed
  output, visual ambiguity, missing review, or any action outside this contract.
* `FINISH` only after the declared mixed/comprehension/recap stop rule is met and no
  alarm is active. Otherwise use `defer_and_revisit`; never grind past the bound.

Provisional completion: at least 80% of scored mixed prompts correct on the first
attempt, with every object and family represented, plus a lower-support retest after
any intervention. This threshold is a trial parameter, not proof of stable retention.

## Alarm points

Freeze immediately, append no later events, and preserve the turn/transcript if any
of these occurs:

1. Required object-question forms or `Yes.`/`No.` are not hash-bound prerequisites.
2. The Point is changed, an extra noun/concept is required, or a function word is
   presented as if already known.
3. A negative, W, or OR cell is replaced by pointing, silence, a label echo, or an
   answer contract that does not test that family.
4. A story becomes a page-by-page label list, introduces an action/relation as scored
   language, or changes canonical/persistent world state.
5. Any parent image, crop, identity, count, or relation fails mechanical or
   independent visual review; pending/imagined hashes are not accepted.
6. A distractor is ambiguous, an object is occluded, or focus cannot be determined.
7. Luna exhausts replay/intervention/teacher-turn budgets, cannot classify the error,
   or would need to invent biography, chronology, or rescue language.

## Unresolved blockers

* No evidence-bearing learner closure for `Is this a X?`, `What is this?`,
  `Is this a X or a Y?`, `Yes.`, or `No.`; the supplied closure is fixture-only and
  lexical-only.
* No approved prerequisite bridge may be inserted by Luna, and L001's Point may not
  be broadened to absorb the missing grammar.
* All draft visual operations and output hashes are pending; no pixel claim is
  reviewable yet.
* The required independent Sol review/qualification remains pending.

The minimum safe disposition is `alarm_blocked`: repair the prerequisite evidence
and visual review, then run this same one-set routine as a new linked authoring
attempt. Do not modify the frozen Point or claim that this trial taught anything.
