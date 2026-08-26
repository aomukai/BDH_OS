---
name: compile-next-lesson
description: Select, prepare, validate, rehearse when required, and freeze the next prerequisite-safe Ninereeds language lesson. Use when Sol must reason from the current learner state, choose the next Topic and single principal Point, build either a dialogue-only or picture-book lesson, commission and verify visual assets through the registry/Flux/OpenAI ImageGen escalation path, preserve grounded-world chronology, decide whether the Luna Instructor needs qualification or a regression rehearsal, and emit an immutable compiled lesson rather than an informal lesson note.
---

# Compile the next lesson

Produce one frozen lesson from current learner evidence. Do not authorize training or run the
lesson. Sol owns Point selection and bounded commissioning; Luna conducts a later authorized
lesson; the verifier gates learning claims.

Read [lesson-contract.md](references/lesson-contract.md) before drafting. Read
[visual-and-world-policy.md](references/visual-and-world-policy.md) whenever images, recurring
characters, locations, or picture books are involved. Read
[instructor-qualification.md](references/instructor-qualification.md) before deciding whether
to rehearse Luna.

## Workflow

1. Load the exact learner-state artifact, known closure, recent lesson traces, curriculum plan,
   teaching methodology, world bible, active identity policy, and Instructor qualification
   record. Treat missing or stale evidence as a blocker, not an invitation to guess.
2. Select one principal Point that is useful now. Record why it follows from the learner state,
   predicted dosage, and every prerequisite. Topic coherence is context, not extra curriculum.
3. Choose exactly one variant:
   - `dialogue_only`: presentation, controlled practice, mixed practice, and optional transfer;
     no picture-book pages or comprehension block.
   - `picture_book`: the same instructional core plus a prerequisite-safe story, page-ordered
     master scenes/crops, and comprehension/transfer questions.
4. Start from the matching JSON template under `assets/`. Replace every placeholder and every
   open-ended shorthand such as `etc.` with a closed list.
5. Preflight the draft:

   ```bash
   python3 mission_hub/skills/compile-next-lesson/scripts/compile_lesson.py \
     validate --input <lesson-draft.json> --stage draft
   ```

6. Resolve visual needs. Prefer reviewed registry material, then external acquisition or a
   minimal Flux edit, then custom Flux. Use OpenAI ImageGen only when Flux cannot reliably
   satisfy a complex composition, canonical-identity constraint, or surgical correction.
   Return every acquired or generated asset through normal review. Never treat a provider's
   successful response as pixel-level acceptance.
7. Build complex scenes as reviewed masters. Derive literal crops deterministically from the
   approved master; do not regenerate them. Record entity counts, spatial facts, canonical
   references, parent asset, hashes, and review receipts.
8. Apply the Instructor qualification policy. Rehearse only when the exact Instructor bundle
   is unqualified, a mandatory invalidation occurred, a new lesson pattern is introduced, a
   scheduled spot check is due, or recent evidence shows a failure. Sol plays the student in
   adversarial rehearsals; a separate verifier grades Luna.
9. Freeze `USE_MARKERS` as an available intervention. Preserve the fixed role delimiters and
   `+...+` frontier span, the one-in-four presentation default, smallest-useful-marker rule,
   unmarked immediate retest, fading gates, prompt budget, unchanged-strategy budget, and
   `defer_and_revisit` terminal outcome. Do not count marked performance as mastery.
10. Freeze only after all assets are `reviewed_usable`, all references resolve, every practice
   form is separately represented before mixing, and the rehearsal decision is evidence-backed:

   ```bash
   python3 mission_hub/skills/compile-next-lesson/scripts/compile_lesson.py \
     compile --input <lesson-draft.json> --output-dir <new-empty-directory>
   ```

11. Return the compiled lesson, manifest, human projection, hashes, asset/review receipts,
    qualification decision, and any blocker. Do not dispatch training.

## Fail-closed boundaries

- Do not introduce more than one principal novelty.
- Do not infer knowledge from incidental exposure.
- Do not admit unknown supporting language, grammar, visual relations, or discourse forms.
- Do not use a recurring entity or location before its world-bible introduction.
- Do not create persistent history for unnamed extras.
- Do not let Luna expand the Point, continue an off-topic conversation, or count an answer in
  another language as target-language production.
- Do not create a new master image for a crop or silently repair a failed teaching claim by
  changing the claim.
- Do not call a lesson immutable while assets, review, world chronology, or Instructor
  qualification remain unresolved.

## Outputs

`compile` creates exactly three files in a new directory:

- `lesson.json`: canonical immutable lesson bytes;
- `manifest.json`: lesson, source, asset, policy, and qualification hashes;
- `lesson.md`: concise human projection for review.

The compiler validates and packages. It does not choose the Point, call providers, approve
pixels, conduct rehearsals, or authorize a campaign.
