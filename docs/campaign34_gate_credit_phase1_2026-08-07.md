# Campaign 34 Phase 1 review: observational gate credit

**Reviewed:** 2026-08-07  
**Campaign:** `campaign-34-gate-credit-phase1-v1`  
**Mode:** paired evolutionary experiment  
**Decision basis:** behavioral chat plus MRI; loss and gate-credit values are telemetry and mechanistic evidence  
**Promotion authority:** none

## Outcome

Phase 1 succeeded as an instrumentation experiment. The read-only observer
captured all 16 declared steps without changing the training trajectory. The
control and observed checkpoints have different container hashes because their
run metadata differs, but all 358 compared leaves in `trainable_state` and
`optimizer_state` are bit-identical.

The observer therefore qualifies for further observational experiments under
the tested configuration. This does not authorize a local learning rule, Error
Diffusion, checkpoint promotion, or a claim that the measured scalar predicts
learning.

## Paired run

Both branches used:

- parent checkpoint `art-20c96f701d529b15` / `5ef4f84ad5796d05622e0d2b962b9c240736875fc8c8a432a8c924f3728b82e7`;
- ordered corpus `art-f45d4331165068b0` / `719246e60a78110f8a993e64a970a4aeae4b687da69485537e6556eea0d51e4b`;
- 16 examples, one epoch, batch size 1, seed 1337, declared order, no shuffle;
- identical optimizer, stochastic-rounding, device, and evaluation settings.

| Evidence | Control | Observed |
|---|---|---|
| Checkpoint | `art-882d6a2618e2091c` / `0cef7926…` | `art-72a869494d284385` / `d516ae5a…` |
| Training report | `art-7c4efefc0cde2f70` | `art-4318cc60099fec22` |
| Evaluation report | `art-017dfc45fedbb9c7` | `art-7d2df1b170beb003` |
| Duration | `39.108 s` | `46.199 s` |
| Peak VRAM, GPU 0 | `6,594,201,600` bytes | `6,796,314,624` bytes |
| Peak VRAM, GPU 1 | `6,604,241,920` bytes | `6,806,092,800` bytes |
| Observer artifact | none | `art-9c2b9e2533608409` / `81b5cb83…` |

The measured observer overhead was approximately 18.1% wall time and 3.1% peak
VRAM. Every per-step loss telemetry value and the short post-training generation
were identical. Loss is recorded here only as an additional trajectory-identity
check, not as evidence of learning.

The behavioral and MRI evaluations were also identical, including every output:
overall `0.288889`, capability `0.121212`, protected `0.75`, 5/15 pathological
outputs, and representation drift of ingress `0.00004692`, core `0.00005209`,
and intentions `0.00026064` from the common parent. The short lesson did not
produce an observable gain on the old suite.

The bit comparison is `art-eb987fa8de23951b` / SHA-256
`9ea80e1bf8e874c8b5c709d72f2be07e5b2fd2016f1b9ea3db3163e3f4f67ff6`.
It reports `learned_state_equal: true`, `identity_equal: true`, and zero
mismatch paths across 358 leaves.

## Gate observations

The observer sampled raw and post-dropout effective gates at all 12 layers for
all 16 steps. All measured activations and gradients were finite.

- Mean effective density by layer ranged from approximately `0.199` to `0.260`.
  The sparse path was active throughout the core rather than dead or saturated.
- Active-unit teaching pressure was mixed. Across most layers, the fractions
  receiving strengthening and suppressing pressure were close, commonly around
  `0.43–0.50` each. No simple “active means reinforce” rule is supported.
- Whole-vector `cos(h, -dL/dh)` was effectively zero at every layer after
  aggregation, on the order of `10^-17`. Positive and negative local pressure
  cancels in this global scalar, making it uninformative in this smoke test.
- The gradient-to-gate norm ratio generally decreased with depth: approximately
  `2.93e-4` at layer 0, below `2e-5` in several middle/deep layers, and `4.75e-6`
  at layer 11. This is a scale observation, not yet evidence of vanishing useful
  credit.
- Intended optimizer movement was finite in every parameter family. Mean
  descent-to-movement cosine was positive but modest: decoder `0.277`, encoder
  `0.222`, value encoder `0.186`, ingress projector `0.217`, intention `0.301`,
  and expression projector `0.356`.
- Relative movement was larger in the interface components than in the large
  core tensors: mean update-to-parameter-norm ratio was about `3.06e-4` for the
  ingress projector, `2.26e-4` for intention, `2.17e-4` for the expression
  projector, and `1.73e-5–4.29e-5` for core families.

## Interpretation

The differentiable sparse gate receives structured but strongly mixed backward
pressure. A single global alignment cosine loses that structure and should not
be elevated into a training criterion. Per-layer active-unit sign fractions,
token/step-local measurements, and parameter-family movement are more promising
observational views.

The relatively larger normalized movement in the encoder/expression interfaces
is consistent with those components adapting faster per unit parameter norm
than the very large core tensors. It does not establish that they are more
important, nor that the core is failing to learn.

## Next discriminating experiment

A longer observational run is technically safe only under the same observer
configuration proven here. Before running one, define a lesson with meaningful
within-session phases or contrasts so gate pressure can be compared by concept,
example type, and time. Preserve the diagnostics-off twin if causal transparency
still matters. Do not implement a local rule until repeated observations suggest
a specific, falsifiable rule and a separate authorization explicitly permits it.

