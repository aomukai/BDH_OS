# Campaign 36B retrospective: dense amorphous growth control

**Date:** 2026-08-30
**Run:** `campaign36b-20260829T203221-11dfa19b`
**Disposition:** deliberately stopped after the architectural result became clear

## Executive finding

Campaign 36B established that a Ninereeds lineage can begin as a small
population of persistent parameter-owning cells, allocate genuinely new cells
during training, checkpoint and resume that changing anatomy, and train the
population together through one shared latent workspace and one output path.

It also established that growth alone is not enough. Every non-dormant 36B cell
executed for every exposure and for both propagation steps. As the population
grew, training time rose from 4.6 minutes for session 0 to 97.4 minutes for
session 17. The same 1,000-event session became 21.17 times slower while the
committed population grew from the 256-cell embryo to 3,720 cells. The live,
uncheckpointed population reached 3,948 cells before termination.

The run was not stopped because it had learned the entire bootstrap. It had
not: target residual remained high and exact teacher-forced token prediction
remained rare. It was stopped because the experiment had already answered its
architectural question. Distributed growth trained coherently, but dense
execution made continued growth progressively less usable. More sessions would
primarily have repeated that scaling result at greater cost.

This makes 36B the control for Campaign 36C:

```text
36B = distributed cells + endogenous growth + dense population execution
36C = distributed cells + endogenous growth + local sparse wave execution
      + persistent state + metabolism and residency
```

## Why 36B existed

Campaign 36A was the fixed 1.2B BDH lineage. The original Campaign 36 plan was
to teach 36A and an independent growing architecture on the same material and
in the same order, creating a comparison rather than replacing either model.

The 3,022-concept visual bootstrap was chosen first because it already existed
as the starting course that grounded the shared SigLIP2/LFM interfaces. Its
frozen program contained:

- 3,022 teaching contracts;
- 10 image exposures per contract;
- 30,220 total exposures;
- 31 bounded sessions;
- declared order only, with shuffling forbidden;
- input manifest SHA-256
  `e1d760e264717d05676076429a2e13e46cd05da6d8376169feaad579121ac2fb`.

The intention was to complete that bootstrap before alternating future v8
language lessons between 36A and 36B. The v8 curriculum was never started on
36B.

## What the model was

36B was an independent model named `ninereeds-amorphous`. It did not contain,
wrap, extend, or initialize from the 1.2B BDH core.

Its full interface was:

```text
text:   frozen LFM Encoder -> trainable ingress projection --+
                                                           |
image: precomputed SigLIP2 features -> trainable resampler -+
                                                           v
                                              [B, T, 512] latent state
                                                           |
                                              amorphous cell substrate
                                                           |
                                              trainable intention head
                                                           |
                                      trainable expression projection
                                                           |
                                         frozen LFM expression model
```

The large organs existed once. Cells did not replicate SigLIP2, the LFM
encoder, the LFM expression model, tokenizers, projectors, or the intention
head. The frozen organ weights were not embedded in every checkpoint.

The visual bootstrap used precomputed SigLIP2 feature archives, the trainable
visual resampler, the cell substrate, the intention head, the expression
projection, and the frozen LFM expression model. The text ingress path existed
for later language teaching but was not exercised by these visual exposures.

## What one 36B cell was

Each cell was a width-512, rank-16 low-rank residual module containing:

- an ingress matrix, shape `512 x 16`;
- an egress matrix, shape `16 x 512`;
- a width-512 activation key;
- a rank-16 latent bias.

That is 16,912 trainable parameters per cell. The embryo's 256 cells therefore
owned 4,329,472 cell parameters.

For each propagation step, a cell:

1. compared its normalized key to a pooled representation of the current
   latent state;
2. converted that similarity to a sigmoid gate;
3. projected the complete latent sequence down to rank 16;
4. applied GELU;
5. projected back to width 512;
6. multiplied its contribution by its gate.

The substrate summed all cell contributions, divided by summed gate strength,
applied a residual scale of 0.25, and normalized the result. It repeated this
for two propagation steps.

New cells had deterministic IDs and initialization seeds. Their egress matrix
began at zero, so a newborn initially changed nothing and acquired influence
through training. Provisional cells had their gate contribution scaled to 0.1.

Despite the gates, execution was not sparse: every admitted and provisional
cell performed its transform on every exposure. The gate changed contribution
strength, not whether the calculation occurred.

## Embryo and frozen defaults

- latent width: 512;
- cell rank: 16;
- seed population: 256 admitted cells;
- birth cohort: 4 cells;
- propagation steps: 2;
- residual scale: 0.25;
- provisional contribution scale: 0.1;
- activation threshold: 0.5;
- initialization seed: 36,002;
- substrate schema ceiling: 65,536 cells;
- bootstrap-specific ceiling: 8,192 cells.

The independent root checkpoint was 31,594,317 bytes with SHA-256
`1ed57ef6fe9b660889e45c8a5b1d7dab75a501e3489b3588c74eda9bbf95dad8`.
It had consumed zero training events.

Before the full run, a two-exposure smoke test produced an optimizer-bearing
checkpoint. A separate process cold-loaded it, restored RNG and optimizer
state, and trained the next exposure. This verified that the changing cohort
list and optimizer-group identity survived a cold resume.

## How growth worked in the actual baseline

The baseline used the `unfiltered` policy. A birth required all three evidence
conditions:

1. internal residual at least 0.25;
2. externally verified failure;
3. capacity saturation.

The evidence definitions were:

- residual: one minus mean teacher-forced probability of the target tokens;
- external failure: the target token sequence was not an exact top-1 match
  under teacher forcing;
- saturation: every allocated cell executed and at least 45% of admitted cells
  crossed the activation threshold.

All three had to persist for eight consecutive observations. A birth then
created four real new cells and enrolled their parameters as a new optimizer
group. An eight-observation cooldown followed. With permanently qualifying
evidence, the shortest interval between births was therefore 16 events.

Across the 18,997 journaled updates:

| Gate observation | Events | Fraction |
|---|---:|---:|
| residual at least 0.25 | 18,986 | 99.94% |
| external failure | 18,928 | 99.64% |
| capacity saturation | 15,858 | 83.48% |
| all three together | 15,804 | 83.19% |

Residual and external failure were almost always true. Capacity saturation was
the practical bottleneck. Mean active-admitted fraction was 0.533, with an
observed range of 0.315 to 0.759.

The run produced 923 birth events in total. Birth gaps had a minimum and median
of 16 events, a mean of 20.58, and a maximum of 434. Early and some later
sessions therefore ran at or near the maximum allocation cadence, while spans
below the 45% activation threshold held growth closed.

### Promotion was not a fitness filter

In the unfiltered baseline, every provisional cohort was automatically promoted
at the end of a successfully completed finite session. No causal usefulness,
retention, or ablation criterion was applied. Consequently, all completed
session reports end with zero provisional and zero dormant cells.

The later `selection.py` design added concept-block plateaus, a minimum age of
128 exposures, online credit, enabled-versus-ablated replay, retention anchors,
and two-strike dormancy. That policy was intended for a separate replay from
the original embryo. It was never applied to this baseline, and the replay was
cancelled when 36B itself was retired.

The 228 cells born during the interrupted part of session 18 remained
provisional in live memory. They were not promoted and were not written into a
completed checkpoint.

## Training recipe

- run ID: `campaign36b-20260829T203221-11dfa19b`;
- start: 2026-08-29 20:32:14 JST;
- stop: 2026-08-30 14:32:18 JST;
- training seed: 3,603,022;
- optimizer: FactoredAdamW;
- learning rate: `2e-4`;
- weight decay: 0;
- momentum: enabled;
- RMS clipping: 0.125;
- stochastic bfloat16 rounding: enabled;
- visual resampler device: `cuda:0`;
- substrate, intention, and expression side: `cuda:1`;
- frozen assets restricted to local files;
- gradient norm clipping: 1.0 per device.

Each exposure performed teacher-forced target-token cross-entropy through the
frozen LFM expression model. The loss, target probability, exact-token result,
residual, active-cell count, executed-cell count, delta magnitude, anatomy, and
growth decision were appended to the journal.

The optimizer and all mutable model state were checkpointed only at session
boundaries. Checkpoints were atomic. The runner retained milestone checkpoints
and the latest two resumable checkpoints, rejected projected checkpoints over
16 GiB, and required at least 20 GiB plus twice the next projected checkpoint
size to remain free.

## Completed-session trajectory

Every listed session contained 1,000 exposures.

| Session | Cells after | Birth cohorts | Duration | Mean loss | Mean residual | Exact |
|---:|---:|---:|---:|---:|---:|---:|
| 0 | 500 | 61 | 4.6 min | 8.838 | 0.970 | 1.4% |
| 1 | 752 | 63 | 11.4 min | 7.871 | 0.982 | 0.1% |
| 2 | 1,000 | 62 | 18.3 min | 7.397 | 0.986 | 0.1% |
| 3 | 1,200 | 50 | 24.2 min | 6.589 | 0.970 | 0.7% |
| 4 | 1,376 | 44 | 30.3 min | 6.493 | 0.974 | 0.0% |
| 5 | 1,572 | 49 | 34.6 min | 5.899 | 0.940 | 0.1% |
| 6 | 1,800 | 57 | 41.1 min | 6.497 | 0.926 | 0.0% |
| 7 | 2,024 | 56 | 47.0 min | 5.898 | 0.936 | 0.0% |
| 8 | 2,272 | 62 | 53.8 min | 5.157 | 0.910 | 1.3% |
| 9 | 2,412 | 35 | 59.5 min | 5.510 | 0.911 | 0.4% |
| 10 | 2,488 | 19 | 62.0 min | 5.597 | 0.924 | 1.3% |
| 11 | 2,700 | 53 | 66.3 min | 6.209 | 0.935 | 0.0% |
| 12 | 2,948 | 62 | 73.1 min | 5.697 | 0.917 | 0.3% |
| 13 | 3,200 | 63 | 80.0 min | 6.025 | 0.939 | 0.0% |
| 14 | 3,436 | 59 | 86.9 min | 6.178 | 0.940 | 0.2% |
| 15 | 3,520 | 21 | 91.9 min | 6.463 | 0.920 | 0.0% |
| 16 | 3,620 | 25 | 94.7 min | 6.088 | 0.949 | 0.0% |
| 17 | 3,720 | 25 | 97.4 min | 5.429 | 0.917 | 1.0% |

The 18 completed sessions consumed 18,000 exposures, created 866 four-cell
birth cohorts, and took 58,622.824 seconds of measured session time, or 16.28
hours. The weighted mean residual was 0.9414 and weighted exact fraction was
0.383%.

Mean loss fell materially from 8.838 in session 0 to 5.429 in session 17, with
the lowest session mean of 5.157 at session 8. It did not decline monotonically;
later sessions ranged from 5.429 to 6.463. This is evidence that the full system
was trainable and changed usefully under the objective, but it is not a
behavioral evaluation, a retention measurement, or evidence that the course
was mastered.

## Exact stopping point

The last fully committed checkpoint is session 17:

```text
/home/aomukai/.local/share/ninereeds/trainbox-agent/
campaign36b/bootstrap/checkpoints/session-17.pt
```

- completed exposures: 18,000;
- admitted cells: 3,720;
- provisional cells: 0;
- dormant cells: 0;
- cell parameters: 62,912,640;
- total trainable parameters represented by the reported bfloat16 parameter
  bytes: 66,478,208;
- checkpoint size: 413,343,807 bytes;
- checkpoint SHA-256:
  `da0b20a062ad1417f469a9c78bbe3fbfab2b4482aa76d2b441e6348a7344c13d`.

Session 18 was interrupted after journal event 18,997. The progress file showed
18,990 because it was updated every ten events; the append-only journal is the
more precise source. At interruption, live anatomy was:

- 3,948 allocated cells;
- 3,720 admitted cells;
- 228 provisional cells;
- 0 dormant cells;
- 66,768,576 allocated cell parameters;
- 923 total four-cell birth events.

Those final 997 updates and 228 newborn cells are retained as event evidence,
not as a resumable model state. A valid resume would begin from session 17's
checkpoint and replay session 18 from its start.

The service stopped cleanly with systemd result `success`. No training process
remained. The anatomy audit, selective replay, v8 training, and 36C build were
not launched. The continuation automation was deleted.

## The scaling failure

Session duration rose from 276.167 seconds to 5,845.600 seconds for the same
number of events: a 21.17-fold slowdown. Event time rose from 0.276 seconds to
5.846 seconds.

The mechanism is direct:

- every non-dormant cell executes;
- each event performs two full propagation passes;
- every birth adds another separately stored and separately invoked cohort;
- every new parameter group adds forward, backward, optimizer, and dispatch
  work;
- trace collection also materializes activation telemetry for the complete
  population.

Live inspection found one CPU core saturated while the substrate GPU was only
lightly utilized, consistent with a Python/cohort-dispatch bottleneck layered
on top of unavoidable dense cell compute. The stopped service reported 18 hours
1 minute 49 seconds of CPU time, 7.2 GiB peak memory, and no swap.

Checkpoint size grew from the 31.6 MB embryo to 413.3 MB at session 17. From
session 0 to session 17 it increased 5.76-fold. Optimizer state at session 17
was 275,593,600 bytes and reported trainable parameter storage was 132,956,416
bytes. The output directory occupied about 1.1 GiB because old ordinary
checkpoints were pruned. Approximately 167 GB remained free before the final
completed checkpoint.

The SSD was therefore not the limiting resource. Session-boundary atomic saves,
checkpoint pruning, and free-space guards worked. Compute and dispatch were the
failure mode.

## What 36B proved

1. A separate Ninereeds lineage can start from a small deterministic cellular
   embryo without inheriting the 1.2B core.
2. Real parameter-owning cells can be allocated during learning rather than
   exposed from a preallocated masked tensor.
3. Stable cell IDs, birth seeds, lifecycle state, weights, growth-controller
   state, RNG state, and optimizer groups can survive checkpoints and cold
   resume.
4. Shared SigLIP2/LFM organs can exist once outside the tissue.
5. Thousands of independently parameterized cells can contribute through one
   latent workspace and train as one end-to-end organism.
6. Growth pressure can be expressed using separate internal residual, external
   failure, and saturation evidence.
7. Dense population execution becomes progressively impractical as the
   organism grows.
8. Storage safeguards were adequate; computation, not SSD wear or capacity,
   ended the experiment.

## What 36B did not prove

36B did not implement or test:

- BDH multiplicative sparse activations inside cells;
- learned local graph neighborhoods;
- wave propagation across node boundaries;
- conditional frontier execution;
- route provenance or a wave-completion mapper;
- recurrent loops or convergence handling;
- persistent private cell state;
- local Hebbian neighbor-to-neighbor teaching;
- meaningful selective admission in the baseline;
- reactivation, reclamation, or metabolism;
- hot/warm/cool/cold VRAM/RAM/SSD residency;
- packed cold storage with stable logical identity;
- rigidity, fusion, reversible fission, or emergent expert-like clusters;
- behavioral acquisition, retention, or epistemic calibration;
- v8 language learning;
- the complete 30,220-exposure bootstrap.

The sigmoid activation key was not a router and did not save compute. Dormancy
existed as a reversible lifecycle state in code, but the unfiltered run never
used it. Cells were stateless, equally shaped, globally mixed residual modules,
not yet local mycelial tissue.

## Why stopping was the correct experimental decision

At 18,997 events, the two principal observations were already stable:

1. growth and joint training continued to function;
2. cost continued to rise with total living tissue because all tissue executed.

The population had not naturally converged on a bounded size. Session 18 had
already produced 57 additional birth cohorts in 997 events, close to the
maximum cadence again. Continuing the remaining course would therefore have
made the model larger and slower without testing sparse thought propagation,
metabolism, or any other mechanism that could change the scaling law.

Stopping preserved the useful control while avoiding sunk-cost continuation.
36B remains evidence that the organism can grow. 36C must test whether thought
can move locally through that organism so compute scales with unresolved
uncertainty rather than total accumulated tissue.
