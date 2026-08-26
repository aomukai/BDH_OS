<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-findings","page_type":"finding_catalogue","status":"active","updated":"2026-08-22","source_ids":["src-campaign33-findings-20260807","src-campaign33-posthoc-acquisition-20260807","src-campaign34-gate-credit-phase1-20260807","src-campaign35-contract-v1","src-campaign35-m5-longitudinal-20260818","src-campaign35-session20-reconstruction-20260819","src-campaign35-post-reconstruction-planning-20260819"]} -->
# Findings

## Campaign 33: curriculum order, regression, and narrow acquisition

With matched data and training settings, placing the same protected material last was
substantially more effective than placing it first under the tested 12-block schedule.
The protected-last branch ended at overall `0.288889`, protected `0.75`, and three
pathological cases; protected-first ended at `0.022222`, protected `0`, and thirteen.
Trajectories were strongly non-monotonic, while coarse MRI summaries remained finite
and similar enough that they did not explain the behavioral divergence.

A corrected 28-case post-hoc suite found only narrow held-out acquisition: every
surviving trained branch passed the same one of 24 sampled new concepts, while 23 did
not meet the strict criterion. The protected-last effect survived paraphrasing at 3/4
protected anchors versus 0/4 for protected-first. This supports an ordering effect on
accessible behavior, not broad vocabulary acquisition or a resolved mechanism.

## Campaign 34: observational gate credit

The read-only gate-credit observer passed its transparency test under the Campaign 34
configuration: all 358 compared learned and optimizer leaves were bit-identical
between control and observed branches, as were per-step losses and generated output.
Measured overhead was approximately 18.1% wall time and 3.1% peak VRAM.

Sparse effective density remained active across layers at approximately 0.199–0.260.
Active-unit pressure was strongly mixed, with strengthening and suppressing fractions
commonly around 0.43–0.50 each. Whole-vector cosine was approximately zero because
opposing local signals cancelled, so that aggregate is not a useful training
criterion. The observation supports token-, unit-, layer-, and phase-local follow-up;
it does not authorize Error Diffusion or any independent local update.

## Campaign 35: merge and healing

Campaign 35 completed all five declared model paths. The complete evidence index is
[Campaign 0035 findings](campaigns/campaign_0035_findings.md).

Verified terminal observations show that the exact M1/M2 merge produced a valid M4
artifact but sharply disrupted measured language behavior and visual separation.
Replaying the exact frozen M3 curriculum as M5 reduced pathological language output
from 28/28 terminal cases to 14/28. This nearly returned to M3's 13/28 result, but no
language-capable terminal passed a behavioral case.

The full M5 trajectory was non-monotonic. Sessions 7, 20, and 36 each produced 0/28
pathological cases, while the final session returned to 14/28. Across the 50 adjacent
session transitions there were 24 improvements, 24 regressions, and two ties. The
evidence therefore supports partial functional healing, not stable recovery.

M5 exposed an executable cross-modal path with mean caption-token recall 0.236415 and
a matched-cosine advantage of 0.002533, but retrieval remained 0/168. M3 and M4 used
visual-structure terminal probes while M5 used a cross-modal probe, so their modality
values are not direct like-for-like measurements.

The M4 tensor audit passed all 54 merge-policy checks and copied M2 visual state
exactly. The merge was mechanically correct; its observed harm was functional rather
than evidence of file corruption or an incorrect tensor splice. Direct cumulative
M4-to-M5 checkpoint geometry remains not measured, so the evidence does not establish
whether M5's widened halves converged toward canonical M3.

Session 20 was reconstructed by exact replay from protected M4. The checkpoint did
not match the original whole-file SHA, but it reproduced the same 23/28 response
uniqueness and nearly identical aggregate representation geometry; pathological
generation was 1/28 rather than 0/28. Neuron-level overlap was much weaker than the
macro geometry suggested.

The reconstructed lineage then diverged under the exact original sessions 21–25.
Original session 25 had 11/28 pathological cases and 22 unique responses, while the
reconstruction had 4/28 and 19. Loss trajectories correlated above 0.9987, yet
optimizer-movement alignment correlated only 0.29–0.53 and reconstructed parameter
updates were consistently larger relative to parameter norm. A healed-looking
behavioral profile and similar aggregate representation geometry therefore did not
identify a unique coordinate state or determine the response to subsequent training.

The durable interpretation is that checkpoint similarity has multiple levels.
Current behavior, macro representation geometry, neuron-level organization, and
response to further learning can agree or disagree. Campaign 35 provides evidence
that a continuation response is part of the checkpoint phenotype: two checkpoints
that look nearly equivalent now can occupy different local learning basins and have
different futures.

This changes checkpoint qualification for modular growth. A healed merge should not
be selected from snapshot behavior alone. Preserve promising candidates and apply a
frozen short continuation challenge that measures retention, behavior, representation
change, gate response, optimizer movement, and relative update magnitude. Replicate
seeds or reconstructions before calling the observed stability or plasticity a general
property.

The scope remains narrow. “Healed” means reduced pathological generation here, not
general competence; all evaluated checkpoints passed 0/28 cases. Concept-neuron
overlap is a diagnostic summary, not complete tensor proof, and one reconstruction
does not estimate the distribution of possible healed states.
