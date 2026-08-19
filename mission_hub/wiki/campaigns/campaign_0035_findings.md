<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-campaign-0035-findings","page_type":"campaign_findings","status":"active","updated":"2026-08-19","source_ids":["src-campaign35-contract-v1","src-campaign35-m5-longitudinal-20260818","src-campaign35-session20-reconstruction-20260819","src-campaign35-post-reconstruction-planning-20260819"]} -->
# Campaign 0035 findings

This page is the evidence index for Campaign 35. It records verified artifacts,
literal observations, anomalies, and missing measurements. It does not answer the
research questions or select a model.

## Closure

- Mission Hub campaign: `campaign-35-multimodal-foundation-v1`
- Campaign contract hash: `20c59510bbfdbb5b5b8d56ff9318dc1bbb2e6b78041c4a70876720a2ac0e9f56`
- Status: completed
- Completed: 2026-08-18
- Terminal operating state: pipeline paused; no live or queued campaign runs
- Strategic decision: `art-bc86f0a71d8634c3`; authorize no new campaign, preserve
  M3/M4/M5, and perform evidence-only merge-healing analysis before new training

Campaign 35 predates the integrated Luna/Sol transition workflow. Its immutable
Mission Hub contract and commissioned mission document are the frozen goals authority;
no retrospective goals decision was manufactured.

## Artifact index

| Artifact ID | Role | Status | Note |
|---|---|---|---|
| `art-eab3b81cb31574e7` | M1 terminal checkpoint | present_verified | Text-only sibling |
| `art-e6e021bd4374e37e` | M2 terminal checkpoint | present_verified | Image-only sibling |
| `art-978a4284b9d17cba` | M3 terminal checkpoint | present_verified | Joint sibling; canonical M5 curriculum source |
| `art-64304ea099fd2b9f` | M4 terminal checkpoint | present_verified | Exact separately authorized M1/M2 merge |
| `art-e8a98ec940c7b2f8` | M5 terminal checkpoint | present_verified | M4 after exact M3 replay |
| `art-ef3519ea4e471404` | M1 terminal language/MRI evaluation | present_verified | 28 cases |
| `art-9a2d4762df28554c` | M3 terminal language/MRI evaluation | present_verified | 28 cases |
| `art-4a2982978ddb0a9c` | M4 terminal language/MRI evaluation | present_verified | 28 cases |
| `art-220b15eecd07e865` | M5 terminal language/MRI evaluation | present_verified | 28 cases |
| `art-9d8b3384105ea70c` | M1 terminal modality probe | present_verified | Visual path absent |
| `art-729c719b5009e990` | M2 terminal modality probe | present_verified | Visual-structure mode |
| `art-692711877aa18ddb` | M3 terminal modality probe | present_verified | Visual-structure mode |
| `art-bc61b82467d9ec48` | M4 terminal modality probe | present_verified | Visual-structure mode |
| `art-b64ce966e65b306d` | M5 terminal modality probe | present_verified | Cross-modal mode |
| `art-e3e1844f195f2777` | M4 exact-merge and geometry audit | present_verified | 54 tensor-policy checks |
| `art-bc86f0a71d8634c3` | Authoritative strategic decision | present_verified | No foundational base selected; no new campaign authorized |
| `art-a59cc56a0217a68d` | M5 session 20 checkpoint | missing | Registered bytes were deleted by frontier retention; SHA `fa7f913aab2e379e8029fc207c442e3e84bb319d2c7073e1bdcf6b95fdc5b288` |
| `art-edc4526318656198` | M5 session 20 training report | present_verified | Available on Mission Hub and trainbox |
| `art-523beb816c68b775` | M5 session 20 gate-credit report | present_verified | Available on Mission Hub and trainbox |
| `art-61a51fbe559635fd` | M5 session 20 paired evaluation | present_verified | Recorded 0/28 pathological cases |
| `art-9ec73a3c976e49d5` | Reconstructed M5 session 20 checkpoint | protected | SHA `68560d83d82c871506716b084744448aa2d8f99ad3e6cf6ae5d04e7b14d5089c` |
| `art-8ff729bbf7bfb0d4` | Reconstructed session 20 evaluation | protected | Recorded 1/28 pathological cases |
| `art-52c802aa4ea60106` | Reconstructed M5 session 25 checkpoint | protected | SHA `b9dfac3de2e5305e7720e861f8b744840453eb2d290cde175cc81196f1a697b8` |
| `art-d628b89be6e1bedb` | Reconstructed session 25 evaluation | protected | Recorded 4/28 pathological cases |

M2 language evaluation is `not_produced` by contract because M2 is image-only. The
complete M5 longitudinal source resolves 51 training reports, 51 gate-credit reports,
and 51 paired evaluation reports by exact artifact hash.

## Literal observations

### `obs-0035-01` — M5 lineage and completeness

- Observation: M5 contains 51 complete train/evaluate pairs, 22,288 ordered events,
  and one continuous checkpoint chain from M4 SHA
  `203a6c96730d6d5f502eafe5d790453374d1de4257bb3735c8daff1a98bf4244`
  to M5 SHA
  `9af8070d7d9452aee855d9b4cf4f84dd3ccd6eca1808bd4fbf77377a77e400eb`,
  with no lineage break.
- Evidence: `src-campaign35-m5-longitudinal-20260818`

### `obs-0035-02` — terminal language behavior

- Observation: M1, M3, M4, and M5 each passed 0/28 terminal behavioral cases.
  Pathological generation occurred in 20/28 M1 cases, 13/28 M3 cases, 28/28 M4
  cases, and 14/28 M5 cases.
- Artifacts: `art-ef3519ea4e471404`, `art-9a2d4762df28554c`,
  `art-4a2982978ddb0a9c`, `art-220b15eecd07e865`

### `obs-0035-03` — healing was non-monotonic

- Observation: M5 sessions 7, 20, and 36 each recorded 0/28 pathological cases.
  Across 50 adjacent paired evaluations, pathological fraction improved 24 times,
  worsened 24 times, and tied twice. The final session recorded 14/28 pathological
  cases.
- Evidence: `src-campaign35-m5-longitudinal-20260818`

### `obs-0035-04` — local representation trajectory

- Observation: evaluation-defined parent-relative drift contracted from session 0
  to session 50: core 0.06191042 to 0.00267292, ingress 0.06744459 to 0.00422982,
  and intentions 0.4111593 to 0.02044915. Ingress concept-separation phase means rose
  from 0.042909329 early to 0.068406071 late. These values are local to each immediate
  parent and do not measure cumulative distance from M3 or M4.
- Evidence: `src-campaign35-m5-longitudinal-20260818`

### `obs-0035-05` — M4 merge execution

- Observation: the M4 audit passed all 54 tensor-policy checks, copied M2 visual
  state exactly, widened the MLP multiplier from 128 to 256, and found no optimizer
  state in M4. Relative L2 distance from canonical M3 was 0.736/0.787 for the two
  widened encoder halves and 0.901/0.930 for decoder halves.
- Artifact: `art-e3e1844f195f2777`

### `obs-0035-06` — terminal modality evidence

- Observation: M4 visual-structure concept separation was 0.010763. M5's cross-modal
  probe found an available visual adapter, mean caption-token recall 0.236415, matched
  cosine 0.536811 versus all-pairs cosine 0.534278, and retrieval 0/168.
- Artifacts: `art-bc61b82467d9ec48`, `art-b64ce966e65b306d`

### `obs-0035-07` — observer evidence

- Observation: M5 gate-credit evidence contains 481 sampled steps and 5,772 layer
  observations. No sampled optimizer family reported a non-finite gradient. Effective
  gate credit was positive in 50.48% of layer observations.
- Evidence: `src-campaign35-m5-longitudinal-20260818`

### `obs-0035-08` — strategic disposition

- Observation: the authoritative decision designated no foundational base,
  authorized no successor campaign, preserved M3/M4/M5, and requested evidence-only
  merge-healing analysis before any new training proposal.
- Artifact: `art-bc86f0a71d8634c3`

### `obs-0035-09` — session 20 was reproducible only at coarse scale

- Observation: exact replay from protected M4 through session 20 did not reproduce
  the original whole-file SHA. The original was
  `fa7f913aab2e379e8029fc207c442e3e84bb319d2c7073e1bdcf6b95fdc5b288`;
  the reconstruction was
  `68560d83d82c871506716b084744448aa2d8f99ad3e6cf6ae5d04e7b14d5089c`.
  The original and reconstruction had the same 23/28 response uniqueness and 3/28
  dominant-response count, but pathological generation was 0/28 versus 1/28 and
  only 5/28 response strings matched exactly.
- Evidence: `src-campaign35-session20-reconstruction-20260819`,
  `art-61a51fbe559635fd`, `art-8ff729bbf7bfb0d4`

### `obs-0035-10` — macro representation geometry did not identify the microstate

- Observation: at reconstructed session 20, original-versus-reconstruction pairwise
  geometry correlations were 0.999479 ingress, 0.998363 core, and 0.999321
  intentions. Mean concept-neuron Jaccard overlap was only 0.311142. At session 25,
  geometry correlations remained 0.996529–0.999236 while mean concept-neuron overlap
  fell to 0.176263.
- Evidence: `src-campaign35-session20-reconstruction-20260819`

### `obs-0035-11` — matched session 20 profiles diverged under sessions 21–25

- Observation: the original session 25 evaluation recorded 11/28 pathological cases
  and 22 unique responses; the reconstruction recorded 4/28 pathological cases and
  19 unique responses. Only 2/28 endpoint response strings matched. Original
  concept-neuron identity was 0.829215 stable from session 20 to 25, while the
  reconstruction retained 0.376010.
- Evidence: `src-campaign35-session20-reconstruction-20260819`,
  `art-2a135493e89812f8`, `art-d628b89be6e1bedb`

### `obs-0035-12` — loss concealed different parameter movement

- Observation: sessions 21–25 used identical event order, visual-experience bytes,
  and visual-feature bytes. Their step-loss correlations were 0.998776–0.999067,
  but optimizer-movement alignment correlations were only 0.290628–0.533590. The
  reconstruction's mean update-to-parameter ratio was higher in every session.
- Evidence: `src-campaign35-session20-reconstruction-20260819`

## Durable interpretation and planning boundary

Campaign 35 supports an operational distinction among at least three kinds of
similarity:

1. **snapshot behavior:** current answers, pathological-output count, and response
   diversity;
2. **macro representation:** aggregate separation and evaluation-defined geometry;
3. **continuation phenotype:** what the checkpoint retains, reorganizes, or loses
   under a frozen subsequent experience.

The reconstructed session 20 was close to the original on the first two levels and
different on the third. Thus behavioral equivalence does not imply representational
equivalence, and coarse representational similarity does not imply identical future
learning dynamics. In this evidence, a checkpoint's response to controlled further
training is part of its experimentally relevant phenotype.

“Healed” remains a narrow observational label here. It means that pathological
generation temporarily fell to zero or near zero; it does not mean broad competence,
because every language-capable Campaign 35 checkpoint passed 0/28 behavioral cases
and terminal retrieval remained zero. Concept-neuron overlap is also an
evaluation-defined summary, not a complete tensor-coordinate proof.

The result makes the failed exact reconstruction scientifically useful: it provides
one existence proof that the same parent, curriculum, event order, visual bytes, and
near-identical loss path can lead to a similar macro state through a different local
training trajectory. It does not estimate how many such trajectories exist or how
often each occurs.

Any successor plan that selects, merges, heals, or grafts a checkpoint should
therefore preserve the candidate and run a frozen short continuation challenge. That
challenge should measure current behavior, delayed retention, representation change,
gate response, optimizer movement, relative update magnitude, and recovery after
controlled interference. Stability and plasticity are separate axes; neither should
be reduced to “best behavior now.” Repeated seeds or reconstructions are required
before treating one continuation response as a stable basin property.

These are planning constraints, not authorization for Campaign 36. The latent-
iteration experiment and the four-language 150M developmental program remain separate
candidate directions. Combining them immediately would confound architecture, scale,
curriculum, language, and merge effects.

## Operational anomalies and interpretation limits

### `anomaly-0035-01` — terminal probe-mode mismatch

- Effect on interpretation: material
- Evidence: `art-692711877aa18ddb`, `art-bc61b82467d9ec48`,
  `art-b64ce966e65b306d`
- Note: M3 and M4 terminal modality jobs emitted visual-structure probes, whereas M5
  emitted a cross-modal probe. Their modality values are not direct like-for-like
  measurements.

### `anomaly-0035-02` — cumulative checkpoint geometry absent

- Effect on interpretation: possible
- Evidence: `art-e3e1844f195f2777`, `src-campaign35-m5-longitudinal-20260818`
- Note: the M4 audit measures source and pre-healing merge geometry, while paired M5
  reports measure drift from each immediate parent. Direct M4-to-M5 and M3-relative
  terminal weight geometry was not produced. Whether M5's widened halves moved toward
  canonical M3 remains unknown.

### `anomaly-0035-03` — best intermediate checkpoint bytes were pruned

- Effect on interpretation: material
- Evidence: `art-a59cc56a0217a68d`, `art-edc4526318656198`,
  `art-523beb816c68b775`, `art-61a51fbe559635fd`
- Note: session 20's checkpoint record, exact SHA, training report, observer report,
  and paired evaluation survive, but the 14,525,970,511 checkpoint bytes have lifecycle
  `deleted` and the trainbox location is unavailable. Reconstruction subsequently
  produced a different whole-file SHA. Direct tensor comparison with the original
  remains impossible; session 20 can only be compared through its surviving reports
  and reconstruction evidence.

### `anomaly-0035-04` — checkpoint serialization prevents tensor-identity inference

- Effect on interpretation: material
- Evidence: `src-campaign35-session20-reconstruction-20260819`
- Note: the session 25 original and reconstructed checkpoint files had identical byte
  size but different SHA. Checkpoints contain nondeterministic duration and parent-path
  metadata. Whole-file mismatch therefore rejects exact file identity but neither
  proves nor disproves tensor identity without both original files and a normalized
  tensor comparison.

## Evidence by research question

### `rq-0035-01` — Do visual and verbal experiences join the same representations?

- Measurement status: partially_measured
- Relevant observations: `obs-0035-04`, `obs-0035-06`, `obs-0035-07`
- Missing evidence: like-for-like cross-modal terminal probes for M2, M3, M4, and M5;
  successful held-out retrieval; controlled representation-level causal probes
- Epistemic answer: deliberately omitted; Sol decides during planning

### `rq-0035-02` — What did the M1/M2 merge preserve or disrupt?

- Measurement status: partially_measured
- Relevant observations: `obs-0035-02`, `obs-0035-05`, `obs-0035-06`
- Missing evidence: matched pre/post-merge behavioral and modality probes using one
  probe mode; causal localization of the observed disruption
- Epistemic answer: deliberately omitted; Sol decides during planning

### `rq-0035-03` — Does exact M3 replay heal M4?

- Measurement status: partially_measured
- Relevant observations: `obs-0035-01`, `obs-0035-02`, `obs-0035-03`,
  `obs-0035-04`, `obs-0035-06`, `obs-0035-07`, `obs-0035-09`,
  `obs-0035-10`, `obs-0035-11`, `obs-0035-12`
- Missing evidence: direct tensor comparison with the deleted original session 20,
  stable behavioral recovery, nonzero retrieval, repeated reconstruction seeds, and
  controls separating bridge repair from replay recency
- Epistemic answer: deliberately omitted; Sol decides during planning

### `rq-0035-04` — Which checkpoint should become the foundational base?

- Measurement status: indeterminate
- Relevant observations: `obs-0035-02`, `obs-0035-03`, `obs-0035-06`,
  `obs-0035-08`
- Missing evidence: a checkpoint with reliable terminal behavior and retrieval,
  direct healing geometry, and controlled evidence resolving repair versus recency
- Epistemic answer: deliberately omitted; the authoritative decision selected none
