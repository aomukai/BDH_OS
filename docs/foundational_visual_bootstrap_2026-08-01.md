# First foundational visual bootstrap

Status: live commissioning; candidate production complete, validation in progress.

## Frozen scope

`foundation-objects-v1` is the first breadth test after the Oxford cat/dog
projector probe. It contains 24 concrete concepts already present in
`training/corpus_admin/kernel/kernel_full_words.jsonl`, with four unique images
per concept. The immutable plan records each word's foundation rank, category,
source, exact prompt, and seed. Abstract words, verbs, adjectives, relations,
and story continuity are deferred to later experience types rather than forced
into misleading single-image labels.

The plan is `training/pipeline/visual/foundation_objects_v1.plan.json`.

## Authority and stages

1. Search the content-addressed catalog for an already accepted exact claim.
2. Generate missing candidates with pinned FLUX.2 Klein 4B.
3. Run a blind Gemma E2B description, then a separate goal-aware rubric.
4. Give only that structured evidence to DeepSeek v4 Flash. DeepSeek returns
   `accept`, `check_again`, or `reject`; transient failures use bounded
   exponential backoff and the official v4 call disables thinking for reliable
   compact JSON.
5. Sol inspects the pixels and the complete evidence packet. Only Sol can set
   the final asset disposition and accepted teaching caption.
6. Failed commissions remain failed. Sol may still admit the pixels for a
   different, explicitly verified foundation caption. The manifest separately
   records `commission_status`, `asset_status`, `actual_facts`,
   `potential_uses`, and `failure_reason`.
7. A pack is accepted only if every planned concept has three training images
   and one held-out validation image. Rejected slots are recommissioned with a
   versioned replacement specification; superseded pixels and failure reasons
   remain in the catalog and receipt.
8. Train only the SigLIP2 resampler sidecar. The language foundation checkpoint
   and both encoders remain frozen, and the checkpoint hash is checked before
   and after training.

All heavyweight stages take
`/home/aomukai/.local/state/ninereeds-control/worker/trainbox-worker.lock`.
Receipts are atomically rewritten after every image, so a killed process resumes
by asset hash.

## Live production evidence

The first FLUX pass produced all 96 candidates locally:

- model: `black-forest-labs/FLUX.2-klein-4B`;
- revision: `e7b7dc27f91deacad38e78976d1f2b499d76a294`;
- profile: FP16 sequential CPU offload, 512 × 384, four steps;
- measured inference: 919.748 seconds total, 9.581 seconds/image mean;
- catalog reuse: zero, because the Oxford labels are intentionally still
  `candidate` claims rather than accepted claims.

The exact remote receipt is
`/home/aomukai/.local/share/ninereeds/visual/reports/foundation-objects-v1.candidates.json`.

Two identical full-precision Gemma E2B workers now use one GPU each under the
same global lease. This preserves the qualified single-GPU model profile while
roughly doubling stage throughput. Early evidence includes a useful
contradiction: the blind pass called one candidate a picture frame, while its
goal-aware pass accepted it as a board. This is why neither Gemma nor DeepSeek
has admission authority.

## Projector evaluation

The accepted pack is divided by immutable item ID: images 01–03 train and image
04 is held out for every concept. The projector report includes 24-way held-out
retrieval before and after training, the full learning curve, and an independent
Oxford-IIIT Pet test slice for cat/dog transfer. The independent slice never
enters projector training. Because only the sidecar is saved, language retention
is structurally protected and the language-only checkpoint SHA-256 must remain
unchanged.
