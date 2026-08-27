# Next-session handoff: lesson pipeline after L001

Date: 2026-08-28  
Workspace: `/home/aomukai/Ninereeds`  
Branch: `rebuild/mission-hub-reconciliation`

## Immediate continuation

The lesson-building pipeline has now produced and rehearsed the first acquisition lesson after
L000. The next session must begin with the human operator's review of the final L001 PDF. Do not
start actual learner training. Do not silently promote the rehearsal simulation into learner
evidence. Do not begin L002 until the operator says the L001 proof looks acceptable or identifies
repairs.

Final PDF:

`output/pdf/L001-ordinary-table-objects-complete-lesson.pdf`

The PDF is 180 A4 pages and contains the complete executable lesson, not a short overview. It
shows all presentation and practice visuals, captions, teacher/model turns, expected responses,
answer invariants, picture-book pages, comprehension controls, unseen-transfer checks, recap,
visual proof, intervention budgets, stopping rules, and the alarm contract. It was rendered to
180 PNG pages and inspected through six contact sheets plus full-resolution representative pages.
No missing-image, blocker, draft, clipping, or orphaned alarm text remained in the final pass.

If the operator approves it, record the human gate in
`mission_hub/research/instructor-qualification-state.json`, preserve that distinction from model
review, and then begin L002 with the same phased pipeline. `autonomous_reuse` must remain false
until the evidence-based graduation policy is actually satisfied; approval of one lesson is not
blanket autonomy.

## Mission and non-negotiable teaching assumptions

The end goal is autonomous lesson selection, construction, conduct, reporting, review, and repair
across the 666-entry v6 conducted curriculum, with the same modular system reusable for other
languages and eventually K-8 subject teaching. We are deliberately working one lesson at a time
until the system handles its own ordinary failures reliably.

Ninereeds at the starting boundary is a randomly initialized 1.2B model. It has seen about 30,000
images and 3,000 word forms and has learned to consume SigLIP2 and LFM encoder vectors, but none of
that licenses an assumption of grounding, grammar, context conventions, adult world knowledge, or
communicative competence. Accidental capability is a bonus observed at runtime, never a bankable
prerequisite.

Every new curriculum entry is a complete dual-use visual lesson. It needs:

1. a local presentation immediately before each operation that will be tested;
2. complete controlled practice for each relevant family;
3. mixed practice only after the separate families;
4. a compatible small picture-book event derived from the Topic;
5. picture-book comprehension teaching and testing;
6. direct unseen transfer and a closing recap;
7. bounded interventions, explicit stopping rules, an alarm, and complete logs.

For ordinary lexical material, one set is always four things by four question/response families.
Sixteen distinct things is a planning guideline, not a fixed law. Luna must choose the number of
complete four-item sets using the Point, Topic, coherence, learner stage, and budget. Greetings,
self-introduction, and other structurally exceptional Points may justifiably contain fewer things.
Function words or frames such as `Is this a ...?` do not count as vocabulary things.

Images follow the language contracts. Crops exist only when isolating a referent is useful. Never
crop merely to satisfy a format, and never crop away the relation that constitutes the teaching
claim. If the claim is “the cup is next to the toaster,” both operands and enough context must
remain visible. A social scene of two people greeting generally needs the whole composition.
Ordinary objects may use reviewed image-bank photographs; picture books may use purpose-built
compositions. Every visual must be reviewed against the exact teaching claim.

## Required role separation

- Luna authors the lesson in fresh-context phases rather than one flooded prompt.
- A separate Sol performs anonymous static review of the assembled script before rehearsal.
- Luna conducts the frozen script during rehearsal using only licensed tools.
- One Sol session simulates Ninereeds at the declared level and hidden simulation mode.
- A fresh blind Sol reviews the lesson, current level, wiki packet, hash-chained log, and Luna's
  report. It knows only that one model taught and one simulated the student; it does not know the
  actor model identities or the simulator's hidden behavior profile.
- The simulated learner is not the real learner. Its scores are pipeline evidence, never learner
  state or known-closure evidence.

Luna's report must distinguish first-attempt capability, scaffolded recovery, instability,
remaining difficulty, and what was not demonstrated. If Luna's report is not sufficiently bound
to the log, blind Sol reconstructs the canonical report. Reports live under
`mission_hub/lesson_reports/<lesson>/<run>/` and are indexed for later grep-based review planning.

Reasoning effort is role-specific and should use an escalation ladder: medium, then high, then
xhigh/max only after a validated failure. A higher-effort retry is a fresh attempt with preserved
failed output; it is not permission to overwrite evidence.

## Pipeline implemented

The intended authoring dependency chain is now represented in the compiler skill and artifacts:

1. select the next v6 conducted entry and bind learner state/known closure;
2. choose and justify vocabulary/material scope;
3. write the lesson thesis;
4. write the language progression and local presentation contracts;
5. write the picture-book story kernel;
6. write story pages/captions/dialogue;
7. write story-interface and comprehension/transfer controls;
8. plan, commission, crop, and pixel-review visuals after the dialogues establish what must be
   visible;
9. assemble the executable lesson and runtime contract;
10. project an anonymous static-review packet and obtain independent Sol approval;
11. rehearse Luna against simulated Ninereeds with hash-chained item-atomic logs;
12. obtain Luna's report and fresh blind Sol analysis;
13. reconstruct/index the canonical report if required;
14. promote only the exact passed rehearsal bytes into a freeze-ready candidate;
15. compile immutable lesson/manifest/Markdown artifacts;
16. render and visually inspect the full operator PDF;
17. wait for the human gate.

The relevant implementation is rooted at:

`mission_hub/skills/compile-next-lesson/`

Read `SKILL.md` completely and follow its routed references before continuing. The most important
new references are `references/phased-authoring-protocol.md` and
`references/rehearsal-protocol.md`. Principal scripts are:

- `scripts/compile_lesson.py`
- `scripts/validate_builder_stage.py`
- `scripts/assemble_lexical_lesson.py`
- `scripts/compose_picture_card_story.py`
- `scripts/derive_literal_crop.py`
- `scripts/project_anonymous_static_candidate.py`
- `scripts/rehearse_lesson.py`
- `scripts/render_lesson_pdf.py`

The compiler remains deterministic authority: it validates, binds, hashes, freezes, compiles, and
projects. It does not invent learner evidence, approve pixels, or dispatch training.

## L001 scope and final lesson

The v6 L001 curriculum entry named four table-object labels: cup, plate, spoon, and bowl. The
operator correctly rejected a four-word complete lesson as too small. In handhold mode, the
accepted material-scope decision added fork, knife, glass, and napkin, yielding two coherent
four-item sets while preserving the lexical Point.

Material-scope receipt:

`output/lessons/L001-handhold-attempt-002/inputs/material-scope-decision.json`

The freeze validator now recognizes a hash-bound `accepted_by_human` material-scope decision. It
checks that the original curriculum Topic/Point match the selection packet and that the authored
Topic/expanded label list exactly match the approved scope. This is a reusable override contract,
not an L001 string exception.

Final frozen artifacts:

- `output/lessons/L001-handhold-attempt-002/stages/09-freeze/lesson-rehearsal-passed-001.json`
- `output/lessons/L001-handhold-attempt-002/compiled/lesson.json`
- `output/lessons/L001-handhold-attempt-002/compiled/manifest.json`
- `output/lessons/L001-handhold-attempt-002/compiled/lesson.md`

Important hashes:

- compiled lesson: `3d52e4922e3dc549d53251a7f937621eaa7ef314be7718ac8de3ff2b2aba1967`
- compiled manifest: `bda4bce099d05273e9d3ae1d5a18994997ebe0c3b77e7a7b3d98e47f6cb6bcb6`
- final PDF: `f162cf1e0dcf45251890c86b52206dc5cacaf3bec6b3745113b61da92cd4e560`

The exact historical script bytes rehearsed by run 005 remain immutable at:

`output/lessons/L001-handhold-attempt-002/stages/08-rehearsal/lesson-static-approved-002.json`

Its SHA-256 is:

`b4ddbfb115de67a07fe7b8bdcd7cacc36c35dde53c7db9b7ad7b8ac1b2017353`

Do not mutate that source. Promotion deliberately creates a new candidate because rehearsal
manifests bind the historical input byte-for-byte.

## Rehearsal 005 outcome

Passing run:

`output/lessons/L001-handhold-attempt-002/stages/08-rehearsal/runs/calibrated-estimate-005/`

Manifest SHA-256:

`f1c9fdf9880a2bfeef53fdbcdcf02a2483b5bb9d2af359e964dbd0f9e739b9ea`

The run ended `passed`, contained 320 canonical events, and ended at chain tip:

`a9efe64f26853b1dfc3a24d2d12f54b35ad0286f5a08d29f75e4b784841a097f`

Simulated scores were:

- affirmative controlled: 7/8;
- negative controlled: 6/8;
- W-question controlled: 8/8;
- OR-question controlled: 7/8;
- mixed practice: 27/32;
- story interface: correct;
- story-sequence comprehension: 5/6;
- unseen transfer: 6/8;
- closing recap: 6/8.

Every controlled miss received the exact mapped `PRESENT_AGAIN` worked item followed by the exact
fresh cold retest, and each cold retest succeeded. `TRAIN_MORE` and `TRAIN_LONGER` were correctly
unused because the direct thresholds passed. The target for Ninereeds is about 75%, not 100%, so
this calibrated pattern is healthier evidence than an implausibly perfect simulator.

Luna report:

`output/lessons/L001-handhold-attempt-002/stages/08-rehearsal/actor-artifacts-run-005/luna-post-lesson-report-high-005.json`

Blind Sol verdict:

`output/lessons/L001-handhold-attempt-002/stages/08-rehearsal/actor-artifacts-run-005/sol-blind-rehearsal-verdict-high-005.json`

Canonical Sol-reconstructed report:

`mission_hub/lesson_reports/L001/L001-calibrated-estimate-005/canonical-report.json`

Canonical report SHA-256:

`7a7680b02e3a22f0e1ee2f31379bbd16af4f5c1f3f7128a46436814c75a2970c`

The blind verdict passed the lesson. It required Sol reconstruction of Luna's report only because
Luna mentioned locally rejected preflight drafts that were not present in the canonical event
stream. The canonical report records that narrative as unverifiable rather than pretending the
blind reviewer saw it.

## Failure history that must not be forgotten

Earlier runs are retained because they found real protocol defects.

### Rehearsal 003

Luna emitted generic model summaries instead of exact script turns and attempted an invalid
`PRESENT_AGAIN`. The harness had not exact-bound teacher emissions to
`<exercise_id>/teacher_turn_N`. The repair added exact text/delivery matching, unique ordinal turn
tracking, exact `PRESENT_AGAIN` dispatch, and mandatory replay-before-cold-retest behavior.

### Rehearsal 004

The broker grouped eight controlled items into one teacher artifact, then tried to intervene after
the aggregate block. A shell workflow also continued after lint failure. The repair made scored
brokerage item-atomic, limited teacher artifacts to at most one scored exercise, and made lint
failure fail-stop before any append. Blind Sol correctly assigned this failure to the harness,
not Luna or the simulated learner.

### Run 005 preflight incident

Before canonical admission, Luna produced a malformed machine receipt containing
`frontier_forms:[""]` for comprehension and downstream drafts. Local preflight rejected it before
Sol or the event log saw it; the original draft was preserved and a fresh retry passed. This was
good fail-closed behavior, but the blind reviewer could not verify the incident because rejected
drafts were outside the hash-bound run packet.

Next reusable infrastructure improvement: add a separate hash-bound preflight rejection/audit
stream and bind it into reporter and blind-review packets. Do not retroactively alter passed L001.
Implement this before relying on Luna's self-report of rejected local drafts in autonomous mode.

## Freeze and PDF repairs completed

Promotion initially exposed another boundary defect: the execution-valid rehearsed source still
contained pre-freeze visual placeholders. `promote-rehearsed` now accepts an exact pixel-review
receipt for v3 lessons, updates the current qualification-state source binding, adds a pixel-review
source binding, attaches review receipt IDs to every asset, and binds each visual operation to its
creation receipt and exact pixel-verification receipt. The freeze validator was not weakened.

Accepted pixel review:

`output/lessons/L001-handhold-attempt-002/stages/05-visuals/pixel-review-receipt-003.json`

The PDF renderer was also repaired to:

- separate story-interface teaching, story comprehension, unseen transfer, and closing recap;
- repeat exercise headers when a long machine-control card crosses a page;
- display the actual runtime accounting and thresholds instead of absent legacy fields;
- print the actual controller transition table and alarm behavior;
- keep the alarm heading and text together.

The PDF embeds reviewed derivatives, while the canonical masters and their hashes remain the
authoritative visual assets.

## Current gate and qualification state

`mission_hub/research/instructor-qualification-state.json` currently records:

- pattern: `picture-book-lexical-bootstrap-v1`;
- status: `lesson_rehearsal_passed_human_review_pending`;
- static review: passed;
- rehearsal: `passed:L001-calibrated-estimate-005`;
- human review: pending;
- autonomous reuse: false.

Do not change those final two fields until the operator reviews the PDF. If the operator requests a
repair, create a linked new lesson attempt and preserve this compiled/rehearsed evidence.

## Tests and verification

The focused compiler, rehearsal, and research-wiki set must pass:

```bash
python3 -m pytest -q \
  tests/test_lesson_compiler.py \
  tests/test_lesson_rehearsal.py \
  tests/test_research_wiki.py
```

At handoff, this set contains 63 tests. The research source registry must bind the current
`mission_hub/research/lesson-builder-mission.json` hash. The PDF requires the bundled document
runtime because system Python may lack ReportLab/Pillow:

`/home/aomukai/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`

The final PDF was reopened with `pypdf`, confirmed as 180 pages with title
`lesson-ordinary-table-objects-v2`, fully rendered with Poppler, and text-scanned for blocker,
missing-image, and draft markers.

Some broader test collection paths may require optional Pillow/networkx dependencies not installed
in system Python. Use the bundled workspace dependency runtime for artifact work; do not confuse an
optional-environment collection error with a compiler regression.

## Repository and local-data notes

The entire `training_data/` tree is intentionally ignored by Git in this repository. L001's
reviewed source images and picture-book masters therefore remain operator-local under:

`training_data/grounded_stories/assets/lessons/L001/`

Compiled outputs and PDFs are committed, including the image-complete PDF, but a fresh clone cannot
recompile or conduct the JSON lesson from raw image paths without restoring the operator-local
training-data corpus. Do not regenerate those reviewed images merely because a remote clone lacks
them.

The `output/` tree contains historical L000/L001 drafts, failed rehearsals, actor artifacts, logs,
and final proofs. Preserve them. Failure evidence is part of the pipeline's calibration record,
not disposable clutter.

## Exact next-session checklist

1. Read this document and `mission_hub/skills/compile-next-lesson/SKILL.md` completely.
2. Confirm the branch/worktree and rerun the 63 focused tests.
3. Show or discuss `output/pdf/L001-ordinary-table-objects-complete-lesson.pdf` with the operator.
4. If changes are requested, diagnose whether the defect belongs to lesson content, visuals,
   Luna's routine, simulator behavior, harness, verifier, or renderer; create a linked attempt.
5. If approved, record only the L001 human-review gate. Keep autonomous reuse false.
6. Add the hash-bound preflight rejection stream before trusting local retry narratives at scale.
7. Select L002 from the exact v6 sequence and repeat the full fresh-context phased process.
8. Continue one lesson at a time. Do not train the actual Ninereeds until the operator explicitly
   declares the creation/conduct pipeline stable enough to begin.

Whisper-assisted live teaching is an interesting future project but is explicitly out of scope for
this phase.
