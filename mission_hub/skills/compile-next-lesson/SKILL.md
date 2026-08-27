---
name: compile-next-lesson
description: Select, prepare, validate, review, and freeze the next prerequisite-safe Ninereeds language lesson. Use for deterministic selection from the frozen v6 conducted sequence, bounded Luna lesson authorship, independent Sol review in handhold mode, operation-specific visual evidence, grounded-world chronology, Instructor qualification, and immutable compilation without training dispatch.
---

# Compile the next lesson

Produce one frozen lesson from current learner evidence. Do not authorize training or run the
lesson. Deterministic code selects the next frozen v6 entry and proves prerequisites; Luna authors
the bounded lesson script and may conduct a later authorized lesson; Sol independently reviews
every handhold-mode lesson; the verifier gates learning claims. Compilation never advances the
learner cursor.

Read [lesson-contract.md](references/lesson-contract.md) before drafting. Read
[visual-and-world-policy.md](references/visual-and-world-policy.md) whenever images, recurring
characters, locations, or picture books are involved. Read
[instructor-qualification.md](references/instructor-qualification.md) before deciding whether
to rehearse Luna. Read [rehearsal-protocol.md](references/rehearsal-protocol.md) before preparing
or running any rehearsal, anonymous review, alarm, repair, or suite.

## Workflow

1. Load the exact learner-state artifact, known closure, recent lesson traces, curriculum plan,
   teaching methodology, world bible, active identity policy, and Instructor qualification
   record. Treat missing or stale evidence as a blocker, not an invitation to guess.
2. Use `select-next` to select the exact next entry from the hash-bound 666-entry prefix cursor.
   Record predicted dosage and every prerequisite. Do not substitute another Point or skip an
   entry inside the compiler; a learner-state exception requires a separate reviewed cursor or
   curriculum decision. Topic coherence is context, not extra curriculum.

   ```bash
   python3 mission_hub/skills/compile-next-lesson/scripts/compile_lesson.py select-next \
     --curriculum docs/curriculum_v6_sol/curriculum_v6.json \
     --rehearsal-layer docs/curriculum_v6_sol/rehearsal_layer_v6.json \
     --cursor <cursor.json> --known-closure <known-closure.json> \
     --output <new-selection-packet.json>
   ```
3. Use `picture_book` for every new handhold-mode entry in the full 666-entry conducted sequence,
   including acquisition and scheduled rehearsal. Every lesson is dual-use: it teaches or
   retrieves language and compatible world knowledge through reviewed visual presentation,
   level-appropriate controlled practice, bounded mixed practice, a coherent visual story,
   comprehension, and recap. Historical `dialogue_only` artifacts remain readable. A curriculum-
   v6 `picture_book: no` field is legacy planning provenance and does not waive the current
   operator format policy. Never import later grammar merely to fill a structural part. Require one
   coherent micro-event with an initial state or goal, meaningful development, and resolution.
   Page order or a shared topic alone is not a story, and coherence outranks squeezing every form
   into the book. In L000, never score first-person identity output as anyone except Ninereeds;
   quoted-character completion is separately typed and supplies no self-identity evidence.
4. Give Luna the frozen selection packet and bounded authoring contract. Start from the matching
   JSON template under `assets/`. Replace every placeholder and every
   open-ended shorthand such as `etc.` with a closed list.
5. Preflight the draft:

   ```bash
   python3 mission_hub/skills/compile-next-lesson/scripts/compile_lesson.py \
     validate --input <lesson-draft.json> --stage draft
   ```

6. Resolve visual needs with an explicit operation type: `reuse`, `literal_crop`, `highlight`,
   `flux_generate`, `flux_edit`, `imagegen_generate`, or `imagegen_fallback`. For the ordinary
   image bank, prefer reviewed registry material, then external acquisition or a minimal Flux
   edit, then custom Flux; use ImageGen fallback only when Flux cannot reliably satisfy the
   teaching claim. Route canonical recurring entities and continuity-sensitive picture-book
   compositions directly to ImageGen under the visual/world policy.
   Return every acquired or generated asset through normal review. Never treat a provider's
   successful response as pixel-level acceptance.
7. Build complex scenes as reviewed masters. Add a literal crop only when it resolves a named
   pointing or salience problem that the full scene does not resolve. Relational teaching claims
   such as greeting, turn-taking, or dialogue normally require the full participants and must not
   be cropped merely to satisfy a production checklist. When a crop is justified, derive it
   deterministically from the approved master; do not regenerate it. Record entity counts, spatial
   facts, canonical references, parent asset, hashes, and review receipts.
8. Obtain an independent Sol assembly review. While mode is `handhold`, every lesson requires a
   passing receipt; the graduation rule remains deliberately undecided. This is separate from
   Instructor qualification and pixel verification.
9. During handhold mode, rehearse every lesson. One Sol session simulates Ninereeds at the exact
   current level while Luna teaches. A fresh, separate Sol session reviews the frozen log with
   anonymous actor labels, current learner evidence, lesson script, teacher-language policy, and
   hash-bound wiki access. It must not receive actor model identities or the hidden roleplay
   behavior profile. Instructor qualification suites may later reduce ordinary rehearsal cadence
   only after an explicit graduation decision; they do not waive the handhold requirement.
10. Freeze `USE_MARKERS` as an available intervention. Preserve the fixed role delimiters and
   `+...+` frontier span, the one-in-four presentation default, smallest-useful-marker rule,
   unmarked immediate retest, fading gates, prompt budget, unchanged-strategy budget, and
   `defer_and_revisit` terminal outcome. Do not count marked performance as mastery.
11. Freeze only after all assets are `reviewed_usable`, all references resolve, every practice
   form is separately represented before mixing, and the rehearsal decision is evidence-backed:

   ```bash
   python3 mission_hub/skills/compile-next-lesson/scripts/compile_lesson.py \
     compile --input <lesson-draft.json> --output-dir <new-empty-directory>
   ```

12. Render the inspection PDF. The JSON is machine authority; the PDF is the canonical human
    review projection and must be regenerated when the lesson hash changes.

    ```bash
    python3 mission_hub/skills/compile-next-lesson/scripts/render_lesson_pdf.py \
      --lesson <compiled-directory>/lesson.json \
      --output <compiled-directory>/lesson.pdf
    ```

13. Initialize and conduct the rehearsal with `scripts/rehearse_lesson.py`. Append only validated
    Luna, Sol, and tool events. Use its `alarm` command to freeze immediately. Then create the
    anonymized `review-packet`, obtain the fresh Sol verdict, `finalize`, and `verify`. A failed or
    alarm-frozen run is repaired only through a new linked run and byte-changing repair receipt.
14. Return the compiled lesson, manifest, Markdown and PDF human projections, hashes, event log,
    anonymized review packet, verdict, asset/review receipts, qualification decision, and any
    blocker. Do not dispatch training.

## Fail-closed boundaries

- Do not introduce more than one principal novelty.
- Do not advance, repair, or infer the cursor as a compilation side effect.
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

Immediately afterward, `render_lesson_pdf.py` adds `lesson.pdf`, the no-special-software operator
proof. Every exercise page places the exact full image, prepared crop, or highlight Luna shows
beside the dialogue and answer contract; a visual cannot be represented only by an asset ID.
The proof also contains controls and alarm conditions. It is a deterministic projection of
`lesson.json`, not an additional authority.

The compiler selects the frozen next entry, validates, and packages. It does not invent or swap
the Point, call providers, approve pixels, conduct rehearsals, advance learner state, or authorize
a campaign.
