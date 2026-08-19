# Commands and artifacts

Run commands from the Ninereeds repository root. Use a dedicated explicit output directory
outside `/media/aomukai/FILES/Downloads`.

## Registry-first proposal

```bash
python3 -m image_registry.campaign35_material --output <audit-root>
python3 -m image_registry.material_gap_analysis \
  --db training_data/image_registry/registry.sqlite3 \
  --material-root <campaign-material-root> \
  --mission <campaign-contract.json> \
  --audit <audit-root> \
  --output <proposal-root> \
  --review-policy <optional-policy.json>
```

The proposal root must contain `selection_proposal.jsonl`, `wishlist.jsonl`,
`query_expansions.jsonl`, `summary.json`, and `validation_report.json`.

## Pixel verification

```bash
python3 -m image_registry.lesson_verification \
  --proposal <proposal-root>/selection_proposal.jsonl initialize

python3 -m image_benchmark.luna_lesson_worker \
  --proposal <proposal-root>/selection_proposal.jsonl \
  --worker-id <unique-worker-id>

python3 -m image_registry.lesson_verification \
  --proposal <proposal-root>/selection_proposal.jsonl export \
  --output <verification-root> \
  --base-wishlist <proposal-root>/wishlist.jsonl
```

Use several unique worker IDs for concurrency. Inspect queue health through:

```bash
python3 -m image_registry.review_queue_cli status <queue-name>
```

`metadata_needs.jsonl` is authoritative only after the queue has zero pending, leased, or failed
items. It combines original gaps with final cascade rejections. Luna `uncertain` outcomes must
first receive a recorded Sol final judgment.

## Required acquisition records

For each external metadata candidate, record:

- item ID and exact teaching claim;
- representation class;
- dataset, release/version, split, and source image ID;
- matched annotations and query tier;
- pixel URL or official downloader identity;
- license and provenance fields;
- prior rejected asset IDs;
- shortlist rank and rationale;
- download, mechanical check, corpus review, registry, and review-cascade statuses.

Keep metadata and pixel acquisition separate. Search the full metadata locally; download only a
bounded shortlist. Prefer Open Images train metadata first because the registry already supports
its schema and exact-ID downloads, then relation/caption-rich sources such as Visual Genome and
COCO when their license/provenance fits the research use.

For broad web-caption coverage, maintain local searchable indexes for Conceptual Captions
(`image_registry.conceptual_captions_index`) and PixMo-Cap
(`image_registry.pixmo_cap_index`). Both workflows download metadata first and leave image pixels
remote until a bounded shortlist is formed. Pass every earlier `candidates.jsonl` to each later
shortlister so the complete wave approaches the configured overfetch target without duplicate
over-acquisition. Source captions in languages other than English remain provenance; any machine
translation is an additional annotation and must not overwrite the source text.

## Tested external-acquisition sequence

Use a separate metadata index on corpus storage. Do not project millions of unreviewed source
records into the trusted registry.

1. Build the Open Images annotation index with `image_registry.open_images_index`, then create
   a conservative shortlist with `image_registry.open_images_shortlist`.
2. Build the Visual Genome caption/relationship index with `image_registry.visual_genome_index`,
   then use `image_registry.visual_genome_shortlist`. Require at least two independent content
   terms; require concept anchoring or at least three unanchored concrete terms.
3. Build the COCO caption index with `image_registry.coco_index`, then use
   `image_registry.coco_shortlist`. Pass prior Visual Genome verification directories so accepted
   images with COCO IDs cannot reappear under a different dataset name.
4. Admit only the bounded shortlist with the source-specific shortlist registry module. Download,
   run `image_registry inspect`, and derive a mechanically valid selection.
5. Create a fresh corpus-review queue. Gemma handles the complete queue; Luna consumes only
   watermark, usability, and uncertainty escalations. Apply a named-queue preview and exact-count
   finalization through `image_registry.finalize_review`.
6. Create a claim proposal with `image_registry.open_images_claim_proposal` (the proposal builder
   accepts any recorded source), initialize `image_registry.lesson_verification`, and run several
   uniquely named Luna workers. Route only Luna's residual uncertain cases to Sol.
7. For another bounded candidate pass, supply every prior verification directory to the proposal
   builder. It skips accepted items and excludes every rejected or uncertain asset.
8. Fold completed passes into the authoritative partition with
   `image_registry.acquisition_round_reconciliation`.

If a provider worker stalls, stop that exact worker before returning its lease. Record a failed
attempt with `retry=true`, then let a healthy worker claim the item. Never requeue a live request;
it could later complete with stale ownership. The queue must finish with only `completed` items.

## Completion artifact

The final handoff must prove:

- the complete curriculum item partition;
- zero unresolved visually teachable items;
- accepted asset path and SHA-256 per single-image assignment;
- explicit manifests for pairs/sequences/stories;
- evidence for rewrites and nonvisual dispositions;
- no accidental asset reuse and recorded intentional reuse;
- all external provenance/licenses;
- all Gemma decisions, Luna escalations, and Sol final judgments;
- all Flux requests and validation outcomes;
- hashes of authoritative inputs and outputs.

Notify Sol with `task complete` plus the completion-artifact path only after validation passes.

## Specialist Flux production

After representation reconciliation has isolated the `single_image` residual:

1. Build an exact gap inventory with `image_registry.campaign35_flux_gap_inventory`.
2. Ask DeepSeek V4 Flash to profile and group only naturally compatible claims with
   `image_registry.campaign35_scene_bundle_plan`. The allowed group size is 1–4, not a target of
   four.
3. Audit every group with `image_registry.campaign35_scene_bundle_luna_audit`; retain Luna's
   splits rather than recombining them for efficiency.
4. Compose generation/edit briefs with `image_registry.campaign35_scene_prompt_compose`. The
   model prompt must explain the M2 teaching objective and frozen reuse/validation constraints.
5. Generate resumable GPU shards with `image_registry.campaign35_flux_generate`, ingest pixels
   through `image_registry.campaign35_flux_ingest`, then inspect, mechanically filter, register,
   and run the ordinary Gemma-to-Luna-to-Sol cascade.
6. Reconcile accepted bindings into the authoritative decision ledger. Feed only rejected or
   mechanically failed single-image slots into the next production pass. Repeat until that route
   has zero residual slots.

For a genuinely tiny semantic tail after repeated generated attempts:

```bash
python3 -m image_registry.campaign35_hard_tail_luna \
  --decisions <authoritative-decisions.jsonl> \
  --inventory <gap-inventory.jsonl> \
  --source <exact-generated-source> \
  --output <hard-tail-luna-output>
```

This is an adjudication ripcord, not a bulk-review shortcut. Include its `adjudications.jsonl`
as review evidence in the final Sol handoff. Luna `uncertain` remains unresolved for Sol.

Keep pair, sequence, contextual, story, rewrite, text-only, and nonvisual routes out of this still
generator. Their explicit dispositions are part of completion evidence, not missing stills to be
disguised.
