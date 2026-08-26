---
name: select-images-for-curriculum
description: Autonomously complete a Ninereeds curriculum's visual-material prerequisite from one frozen request. Use when Sol or an authorized preparation worker must select and verify registry assets, acquire and review external candidates, repeat to convergence without babysitting, apply controlled reuse, consider representation or Flux only after deterministic sources are exhausted, and receive one terminal completion or blocker handoff.
---

# Select images for a curriculum

Complete visual-material preparation without weakening teaching claims. Treat registry text
and dataset annotations as retrieval evidence, never pixel proof. Use the configured bulk
vision model for first-pass pixel review, Luna for flagged alarms and ambiguous cases, and
Sol only as the final judge when Luna still returns `uncertain`.

Read [decision-policy.md](references/decision-policy.md) before making substitutions,
rewrites, representation decisions, or Flux requests. Read
[commands-and-artifacts.md](references/commands-and-artifacts.md) before executing the
repository tools. For a durable multi-round job, read
[controller-contract.md](references/controller-contract.md).

## Autonomous invocation

Prefer one controller invocation over manually executing individual rounds. Freeze a controller
configuration, then start or resume:

```bash
python3 mission_hub/skills/select-images-for-curriculum/scripts/run_campaign35_loop.py \
  --config <frozen-loop-config.json>
```

Run it as a supervised service for work that must survive a terminal or agent session. Do not
ask Sol to poll queues, restart workers, reconcile rounds, or invoke this skill repeatedly. The
controller owns those shallow operations and returns one `sol-handoff.json` only at a terminal
state. A status request may read `state.json`; it must not change phase ownership.

## Required loop

1. Freeze the curriculum version, registry version, output root, protected selections, and
   completion contract. Refuse `/media/aomukai/FILES/Downloads` as an output tree. On a
   repeated run, preserve every still-valid accepted slot binding and its evidence exactly.
2. Run the registry-first material-gap analysis. Preserve the exact item partition:
   provisional assignment or residual need, never both and never neither.
   Existing registry assets retain their completed corpus-quality audit; searching or assigning
   them to a new curriculum does not make them newly acquired. Their target fit must still be
   verified for the proposed teaching claim.
3. Send every provisional assignment through the leased target-fit queue. Send every newly
   downloaded or generated image through the full corpus-quality and target-fit queues, with
   local Gemma as the default bulk reviewer. Provider-backed bulk review is forbidden unless
   the frozen controller configuration explicitly opts in; API-key presence is not permission.
   Escalate its watermark alarms, usability problems, and uncertain target fits to Luna.
   Escalate only Luna's residual `uncertain` target fits to Sol for final judgment. Reject
   text-overlay shortcuts, wrong subjects/relations, partial phrase matches, and inferred
   hidden states. Do not delete a merely off-target asset; it may teach something else.
4. Reconcile the original residual wishlist with all final rejections into one item-level
   `metadata_needs.jsonl`. Exclude each previously attempted asset from that word or claim's
   next pass. A repeat run must not recycle rejected, deleted, missing, or failed candidates.
5. Classify each unresolved claim as `single_image`, `contrast_pair`, `image_sequence`,
   `image_plus_context`, `story_or_activity`, `text_only`, `curriculum_rewrite`, or
   `not_visually_teachable`. Do this before acquiring pixels.
6. For claims still needing a single image, re-search the complete local registry with exact
   terms, semantic equivalents, and alternate concrete realizations. Apply the semantic and
   taxonomic rules in the decision policy. Send new proposals back to Luna.
7. Search external image-training-set metadata before downloading images. Record dataset,
   split, image ID, annotation evidence, URL, license/provenance, query tier, and rationale.
   Download only a bounded shortlist. Mechanically validate, register, run corpus-quality
   review, then send survivors to Luna. An annotation is not acceptance.
8. Consider a slight curriculum rewrite only when it preserves the original learning
   objective, semantic scope, dependency order, and evaluation target. Record old claim,
   new claim, invariant meaning, and justification. Never rewrite merely to excuse an
   attractive available image.
9. If acquisition fails, prefer a minimal Flux edit of a suitable reviewed asset, then custom
   Flux generation. If Flux cannot reliably satisfy a dense composition, exact count/relation,
   canonical-identity constraint, or surgical correction, emit a bounded OpenAI ImageGen
   fallback task through an available Codex image-generation runtime. Forbid added target words,
   labels, collage panels, and graphic
   shortcuts unless written symbols are themselves the lesson. Register and review every
   result through the normal corpus path regardless of provider, then send it through the same
   review cascade. When
   several concrete residual claims naturally fit one clean scene, design that scene once and
   assign the approved result to each honest teaching claim under the frozen reuse cap.
10. Repeat steps 4–9 until every item has either validated material or an evidence-backed
    non-single-image/nonvisual disposition. Do not silently relax the claim to terminate.
11. Validate hashes, the frozen reuse cap and usage history, licenses, item partition,
    review-cascade evidence, and zero unresolved teachable items. Emit the task-complete artifact and
    notify Sol only after this gate passes.

## Stop conditions

Do not emit `task complete` when any visually teachable item is unresolved, any downloaded or
generated image skipped registry review, any accepted image lacks completed cascade evidence, a
rewrite lacks semantic-preservation evidence, or an external asset lacks provenance/license
metadata. Report the exact blocker and keep the run incomplete.

`text_only` and `not_visually_teachable` are legitimate resolutions when supported; they are
not failures to disguise with vaguely related imagery.

Transient congestion, provider errors, invalid model JSON, a stopped worker, or a process restart
are not stop conditions. Retry safely with leased claims and fresh worker identities. Stop with a
blocker only for a non-retryable integrity failure or after the controller's bounded phase retries.

## Sol handoff

Emit one structured completion message containing the curriculum/input hashes, counts by
resolution route, accepted selection manifest, non-single-image dispositions, remaining
unresolved count, review evidence locations, metadata/download ledger, Flux/ImageGen request ledger, and
validation report. State `task complete` only when `unresolved_teachable_items` is zero.
