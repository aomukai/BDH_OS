# Visual-material decision policy

## Preserve the claim

Judge substitutions against the exact property being taught.

- A substitute may vary irrelevant details while preserving the subject class, relation,
  cardinality, action, state, and contrast required by the claim.
- A generic target may accept any genuine member of its class. A specific target may not be
  replaced by a sibling, lookalike, fictional analogue, or broader superclass.
- `marsupial` may use a koala or kangaroo. `kangaroo` requires a kangaroo. `bear` requires an
  ursid; a koala or fictional drop bear is not a bear.
- If the target is the relation `under`, a cat under a tree may replace a dog under a table
  only when animal/object identities are irrelevant to that lesson.
- Preserve quantity exactly when quantity is taught. Preserve direction and argument order
  exactly when a relation is taught.

When taxonomy is uncertain, consult an authoritative taxonomy or mark the candidate uncertain.
Do not let visual resemblance decide class membership.

## Choose the representation before sourcing

- `single_image`: one still can directly and unambiguously demonstrate the claim.
- `contrast_pair`: meaning emerges only from a controlled comparison.
- `image_sequence`: order, transition, rate, causality, or before/after requires frames.
- `image_plus_context`: a still becomes meaningful only after known language or story context.
- `story_or_activity`: intention, remembering, deciding, sharing, or similar meaning requires an
  unfolding situation and discussion.
- `text_only`: the target is linguistic, logical, epistemic, or otherwise better taught without
  visual evidence.
- `curriculum_rewrite`: a nearby formulation preserves the learning objective and becomes
  honestly teachable.
- `not_visually_teachable`: images cannot provide honest evidence for this target at this stage.

Do not commission a single still for a claim classified into another representation.

## Rewrite gate

Approve a rewrite only when all are true:

1. The same concept and semantic scope remain the evaluation target.
2. No required prerequisite is introduced early.
3. No exception, stereotype, or merely correlated scene replaces the definition.
4. The rewritten claim is more visually observable, not merely easier to source.
5. The old and new claims, preserved invariant, and justification are recorded.

Otherwise preserve the original claim and choose another representation or mark it nonvisual.

## Source order

1. Unused reviewed local asset.
2. Previously used local asset when reuse is pedagogically justified and usage limits allow it.
3. External training-set metadata candidate, followed by bounded pixel download.
4. Minimal Flux edit of a reviewed reference.
5. Custom Flux generation.
6. OpenAI ImageGen after a recorded Flux failure involving dense composition, exact counts or
   relations, canonical identity, or a surgical correction.

Every route returns to mechanical validation, corpus review, registry admission, and the
Gemma-to-Luna-to-Sol review cascade. Sol is used only when Luna remains uncertain. Never accept
from metadata, prompts, filenames, or captions alone.

OpenAI ImageGen is a fallback executor, not an acceptance authority. Record the Flux attempt,
its concrete failure, the canonical references and frozen scene inventory supplied to ImageGen,
and every subsequent correction. Prefer one reviewed master scene and deterministic literal
crops over separate generative redraws.

## Acquisition wave size

- Default each external acquisition wave to `ceil(residual slots × 2.0)` distinct candidates.
  This is an aspirational candidate target, not a promise that two images will pass review.
- Treat at least 80% of that target as sufficient coverage for the wave. Proceed to review rather
  than adding progressively weaker sources merely to fill the last 20%.
- Below 80%, consider another source only when its metadata quality, provenance, and likely
  marginal yield justify widening the search space. Candidate count alone is not sufficient.
- Count candidates already assembled in the current wave before asking later metadata sources
  to fill the remaining positions. Do not download two more from every source independently.
- Preserve all accepted surplus images in the general registry, with captions and provenance,
  even when only one accepted image is selected for a particular curriculum slot.
- Keep the factor explicit in the frozen campaign configuration. Re-estimate it from observed
  download and review yield when later campaigns provide enough evidence. A later residual wave
  is preferable to forcing a low-quality source into an otherwise clean current wave.

## External-to-Flux switch floor

- Define external target-fit yield as newly accepted curriculum slots divided by newly reviewed
  mechanically valid external images. General corpus usability is recorded separately and does
  not count as target fit.
- After one complete wave through the frozen high-quality metadata source stack, stop broad
  external acquisition when target-fit yield is below 15%, provided at least 500 candidates were
  reviewed. A smaller wave uses the per-slot rule instead of a noisy aggregate estimate.
- Maintain a per-curriculum-concept yield ledger. Do not combine repeated surface words when
  their `concept_id` differs. Route a concept out of broad acquisition when at least eight
  reviewed claims across at least two rounds produced less than 15% target fit and it still has
  unresolved slots. Aggregate success on easy concepts must not hide a consistent low performer.
- The switch does not send every residual directly to image generation. Reclassify representation
  first. Only concrete `single_image` residuals proceed to a minimal Flux edit and then custom
  generation. Pairs, sequences, contextual/story targets, rewrites, text-only targets, and
  nonvisual targets follow their declared route.
- Every Flux result re-enters mechanical validation, registry admission, and the complete review
  cascade. The floor changes the sourcing route, never the acceptance standard.

## Reuse policy

- Reuse across different concepts is desirable when the pixels genuinely teach each claim; a
  brown dog may teach both `brown` and `dog`.
- Default to at most four accepted curriculum slots per asset. A campaign may choose another
  explicit cap in the 3–5 range, but it must freeze that value before selection.
- Prefer the least-used suitable asset. At the cap, choose another candidate or return the slot
  to the wishlist.
- Treat the specialist residual as a production brief. Deliberately compose compatible concrete
  claims into one clean scene when the resulting pixels honestly teach every claim; apply the
  same reuse cap and record each assignment. Do not add unrelated objects merely to maximize
  ledger coverage.
- When applying a cap retroactively, retain scarcer concepts first, then stronger explicit
  image/caption evidence, then stable curriculum order. Record every retained and released slot.

## Flux scene-brief policy

- A production image may carry one to four target keywords. One is a valid and often preferable
  result; four is a hard ceiling, never a quota.
- Group targets only when a single ordinary scene makes every target visually prominent and
  independently teachable. Split a group as soon as satisfying one claim makes another obscure,
  contrived, ambiguous, or likely to fail in generation.
- Give the prompt-composition model the actual research context: M2 teaches one curriculum word
  plus pixels, Ninereeds cannot be assumed to supply missing world knowledge, ten distinct
  exposures are required, accepted assets may serve at most the frozen reuse cap, and every image
  will face pixel-level target validation.
- Plan the scene and its evidence first, then write the Flux prompt. Record one explicit visible
  evidence statement per keyword. A filename, prompt, caption, or intended association is never
  evidence that the generated pixels succeeded.
- Prefer a clean base generation followed by controlled edits when the teaching claims stay
  invariant. Variants must differ in incidental properties, not merely seed noise, while retaining
  all target evidence. Each variant re-enters the full review cascade independently.
- Failed variants return their exact slots to a new production pass. Do not weaken the target,
  silently reuse a rejected image, or expand a scene merely to reduce job count.
- When a tiny generated hard tail repeatedly receives Gemma `target_not_visible` decisions despite
  clear pixels, route the actual images and exact target words to Luna for durable word-fit
  adjudication. Accept only an explicit Luna `accept`; an `uncertain` result remains unresolved for
  Sol. Preserve the adjudication transcript and hash it into the final completion proof.

## Metadata confidence

- Prefer explicit subject-predicate-object annotations over co-occurring object labels.
- Prefer captions containing the concept plus at least one independent concrete constraint.
  A stem and its inflection count as one signal (`ensure`/`ensuring`), not two.
- Permit an unanchored caption only when at least three independent concrete terms jointly
  describe the realization; the pixel-review cascade must still judge whether it teaches the
  target concept.
- Reject homonym and stemming shortcuts such as `range`/Range Rover, `sum`/dim sum,
  `angle`/camera angle, `addition`/additional, `land`/landing, and `news`/new.
- Prefer a single clean annotated instance for an introductory identity claim. Large object
  counts and crowded scenes are not a relevance bonus.
- Never search every weak one-word hit merely because a dataset can return it. Preserve those
  items as unresolved for another dataset or representation reassessment.
