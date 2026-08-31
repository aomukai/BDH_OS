# Campaign 36B embryo: code-grounded starting specification

**Date:** 2026-08-29
**Status:** Bootstrap training live on trainbox

## Independent architecture

Campaign 36B is an independent model named `ninereeds-amorphous`. It uses the
same pinned organ interfaces as the fixed lineage where compatible, but it does
not contain, parent, or attach to the 1.2B BDH core.

The implemented path is:

```text
frozen LFM Encoder -> trainable ingress projection [B,T,512]
                   -> amorphous cell substrate [B,T,512]
                   -> trainable intention head [B,K,512]
                   -> trainable expression projection
                   -> frozen LFM expression model
```

The existing SigLIP2 resampler can supply projected visual observations at the
same width. It exists once outside the population; no cell contains a receptor,
tokenizer, language model, or image projector.

## Embryonic population

The current provisional defaults are:

- latent width: 512;
- cell rank: 16;
- seed population: 256 admitted cells;
- birth cohort: 4 provisional cells;
- propagation: 2 steps;
- bounded residual scale: 0.25;
- provisional contribution scale: 0.1;
- maximum population safety ceiling: 65,536 cells;
- complete execution of every admitted and provisional cell.

One cell contains two low-rank matrices, one activation key, and one latent
bias: 16,912 parameters at the default width and rank. The 256-cell seed tissue
therefore contains 4,329,472 cell parameters. Organ bridges and organs are
accounted separately.

Cells are stateless in this first implementation. Private recurrent cell state,
learned neighborhoods, sparse retrieval, local plasticity, and physical paging
remain later controlled experiments. This keeps the first bootstrap result
attributable to population growth rather than several untested mechanisms.

## Birth and lifecycle

Cells are allocated as real new parameter cohorts. The implementation does not
preallocate a large masked tensor and later relabel it as growth.

A cohort begins `provisional`, can be promoted to `admitted`, and can become
reversibly `dormant`. Dormant cohorts remain checkpointed for rollback and
retention tests but do not execute or receive gradients.

The provisional default birth gate requires:

1. internal residual at or above a frozen threshold;
2. a separately supplied externally verified failure;
3. a separately supplied capacity-saturation diagnosis;
4. eight consecutive qualifying observations;
5. an eight-observation cooldown after birth.

Raw training loss is telemetry and does not itself satisfy these conditions.
For the bootstrap, each declared visual exposure is a registered observation.
The frozen evidence definitions are:

- internal residual: one minus the mean teacher-forced probability assigned to
  the target lexical tokens;
- externally verified failure: the target lexical token sequence is not an
  exact top-1 match under teacher forcing;
- capacity saturation: every allocated cell executed and at least 45% of the
  admitted population crossed the frozen activation threshold.

The three values are journaled separately. A birth remains contingent on all
three, the eight-observation persistence requirement, and the eight-observation
cooldown. New cohorts remain provisional until the end of the current frozen
bootstrap session, then become admitted if the session completed with finite
training telemetry.

New cohorts receive deterministic stable IDs and seeds. When an optimizer is
present, their parameters are enrolled as a new optimizer group at birth.

## Recovered bootstrap course

The original visual birth program is locally recoverable and content-addressed:

- campaign: `foundation-visual-3022-v1`;
- teaching contracts: 3,022;
- visual exposures: 30,220;
- images per contract: 10;
- bounded sessions: 31;
- input manifest SHA-256:
  `e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb`;
- generated-session manifest SHA-256:
  `062c9878f63410516ab87a2a43ebc7910ab8268b8a83c63de6f06b4e2ea2de8c`;
- teaching-contract SHA-256:
  `eb15bd89c5a094990965d394e7cd96ed4db01d38050de18be5d838861540877b`;
- accepted-assets SHA-256:
  `4794b35855f63c8406344b58411d0aa99a580d360053f0c6d2a15c7060211f3c`;
- dependency-edge SHA-256:
  `12ce3bb626cc563dc73ab1e54f9d0d11d854f26ee4c5261af3123dc09e22014b`.

The fixed-lineage run completed all 31 visual sessions. Its protected terminal
comparator is Mission Hub artifact `art-927dcf4896c9b0b4`, SHA-256
`fe1598dded9d517f413f706713a6e6556b77d264b47fdd9d3a3c03a838072fd6`.
Campaign 36B does not load that checkpoint.

## Initialized 36B root

The independent, untrained root organism now exists outside the repository:

- checkpoint:
  `/home/aomukai/.local/share/ninereeds/campaign36b/amorphous-root.pt`;
- receipt:
  `/home/aomukai/.local/share/ninereeds/campaign36b/amorphous-root.receipt.json`;
- checkpoint SHA-256:
  `1ed57ef6fe9b660889e45c8a5b1d7dab75a501e3489b3588c74eda9bbf95dad8`;
- checkpoint size: 31,594,317 bytes;
- initialization seed: 36,002;
- training events consumed: 0.

The checkpoint embeds no frozen LFM or SigLIP2 organ weights. It contains the
new cell substrate, organ bridges, intention interface, visual resampler,
growth-controller state, configuration, and source binding required to begin
the 36B lineage. It contains no 1.2B weights.

## Bootstrap journal epochs

Each 36B bootstrap session must journal:

- source session ID and hashes;
- parent and candidate checkpoint identities;
- event and exposure counts;
- population before and after training;
- provisional, admitted, active, and dormant tissue;
- cell births, promotions, and dormancy transitions;
- active cell-time and propagation-step telemetry;
- behavioral and representation observations;
- internal residual and capacity evidence;
- the explicit growth decision;
- runtime, memory, optimizer-state, and failure telemetry.

Bootstrap and v8 teaching are distinct journal epochs. When v8 becomes frozen,
the alternating lesson order is:

```text
v8 lesson N -> Campaign 36A -> evaluate and journal
v8 lesson N -> Campaign 36B -> evaluate and journal
advance to lesson N+1 only after both records are complete or one track has a
declared failure record
```

No result may be silently omitted to keep the lineages visually synchronized.

## Implemented verification

The current CPU-scale suite verifies:

- exact cell-parameter accounting;
- deterministic forward execution and full-population traces;
- grounded persistence and saturation requirements for birth;
- optimizer enrollment of newborn parameters;
- provisional, admitted, and dormant lifecycle transitions;
- checkpoint restoration of weights, anatomy, IDs, and growth state;
- learning of a small synthetic latent residual.

## Storage and execution boundary

The dedicated runner is `meta/scripts/train_campaign36b_bootstrap.py`. It
consumes the immutable 31-session manifest in declared order and writes:

- compact append-only JSONL event evidence;
- one small atomic progress document;
- one full checkpoint at each session boundary, never at each exposure;
- compact per-session reports;
- milestone checkpoints for sessions 0, 9, 19, 29, and 30 plus the latest two
  resumable checkpoints.

The runner stops before a checkpoint if projected checkpoint size exceeds 16
GiB, or if free storage would fall below 20 GiB plus twice the projected
checkpoint size. Bootstrap tissue is additionally bounded to 8,192 cells,
below the general substrate schema's larger research ceiling. Raw activation
tensors are not persisted.

The immediate execution milestone is one tiny visual smoke run on trainbox.
The full 31-session bootstrap may begin only after that smoke checkpoint can be
cold-loaded and resumed without changing optimizer group identity.

## Live execution record

The visual smoke trained two immutable exposures and produced a 45,944,377-byte
optimizer-bearing checkpoint. A separate process cold-loaded that checkpoint,
restored its RNG and optimizer state, and successfully trained the next
session's first exposure.

The full bootstrap started on 2026-08-29 at 20:32 JST as trainbox user service
`campaign36b-bootstrap.service` with run ID
`campaign36b-20260829T203221-11dfa19b`. Its state root is:

`/home/aomukai/.local/share/ninereeds/trainbox-agent/campaign36b/bootstrap`

At the first recorded live inspection, exposure 190 had allocated 11 four-cell
cohorts: 256 admitted seed cells and 44 provisional newborn cells, 300 cells in
total. The trainbox state volume had approximately 157 GiB free. An hourly
thread heartbeat monitors material progress and failure recovery without
changing the frozen experiment.
