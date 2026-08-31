# Campaign 36C Checkpoint 04: repository evidence handoff

This small-file handoff supplies the repository evidence requested during the
Campaign 36C cell-boundary discussion. It intentionally contains no model
weights, generated datasets, frozen encoder assets, or training outputs.

## Exact 1.2B BDH configuration

The production 1.2B configuration is defined as `CORTEX_1_2B_CONFIG` in
`cortex/student.py`:

```text
n_layer = 12
n_embd = 512
n_head = 8
mlp_internal_dim_multiplier = 128
vocab_size = 256
per_layer_weights = true
architecture_variant = bdh_v1 (dataclass default)
```

Therefore, for each layer and head:

```text
D = 512
N = multiplier * D / heads = 128 * 512 / 8 = 8192 gates
rotary pairs per head = 4096
```

One layer-local, head-local rotary pair owns two columns of `encoder`, two
columns of `encoder_v`, and two corresponding rows of `decoder`. Its trainable
BDH core is therefore `6D = 3072` parameters. A microcohort of `P` aligned
pairs owns `3072P` parameters. Because `per_layer_weights=true`, layer identity
is part of the atom's ownership; a pair slice is not implicitly shared across
the twelve layers.

The 1.2B description comes from the twelve per-layer sparse matrices. Each of
`encoder`, `encoder_v`, and `decoder` owns 33,554,432 parameters per layer, or
100,663,296 per layer collectively and 1,207,959,552 across twelve layers,
before the comparatively small embedding and output tensors.

## Mechanically important qualification

The parameter slice is exact, but the existing dense forward operation is not
already a set of independent cells. In `bdh.py`, rotary-pair contributions are
summed into a head-wide temporal score by `QR @ KR.mT`; that score is then
applied to the latent value tensor and normalized before `encoder_v` and the
multiplicative sparse firing. Consequently, independently loading a pair or
microcohort is an architectural experiment, not a lossless extraction claim.

The required repository experiment is:

1. mask all pairs except one candidate aligned cohort in the dense model;
2. execute the same cohort through an independently loaded cell-local operator;
3. compare outputs and gradients under an explicitly declared tolerance;
4. sweep `P = 1, 2, 4, 8, ...` for usefulness, latency, paging cost, active
   compute, and improvement per parameter;
5. select the smallest useful execution cohort without allowing storage-page
   boundaries to define logical identity.

If exact independent execution cannot preserve the required BDH behavior, 36C
must define a new cell-local BDH operator derived from the original mechanism.
It must not describe arbitrary dense slices as independent cells when they
retain hidden head-wide dependencies.

## Included sources

### BDH model and 1.2B checkpoint contract

- `bdh.py`: exact BDH tensors, rotary operation, collective attention,
  normalization, sparse multiplicative firing, and decoder mapping.
- `cortex/student.py`: exact 1.2B configuration; checkpoint schema;
  trainable-state ownership; save and restore implementation.
- `cortex/config.py`: frozen LFM encoder/expression configuration associated
  with the 1.2B Cortex lineage.
- `meta/scripts/train_cortex.py`: optimizer construction, optimizer restore,
  bounded training, and checkpoint save call.
- `training/optim/factored_adamw.py`: optimizer-state allocation and update
  semantics used by the 1.2B training path.

### Campaign 35 merge and healing evidence

- `meta/scripts/merge_cortex.py`: the actual sparse-neuron-axis concatenation,
  shared-bridge averaging, visual-state inheritance, and optimizer discard
  policy used for the 1.2B + 1.2B merge.
- `meta/scripts/analyze_campaign35_m4_merge.py`: exact inheritance and tensor
  geometry audit.
- `meta/scripts/analyze_campaign35_m5_checkpoint_healing.py`: post-merge
  checkpoint healing analysis.

Campaign 35 establishes that concatenating the BDH sparse-neuron axis can
preserve both source halves mechanically. It does not establish that arbitrary
cells can be fused into a single independently executable local operator; 36C
fusion and fission still require their own reversible representation and tests.

### Campaign 36B dynamic-cell implementation evidence

- `amorphous/config.py`: fixed 36B substrate and growth-policy configuration.
- `amorphous/growth.py`: deterministic three-condition birth gate, patience,
  cooldown, and persisted controller state.
- `amorphous/substrate.py`: cohort identities, lifecycle states, dense
  all-cohort execution, growth, anatomy, and substrate checkpoint round trip.
- `amorphous/student.py`: shared organ integration and complete 36B checkpoint
  save/restore contract.
- `amorphous/selection.py`: selective birth, promotion, and dormancy decisions
  designed after the unfiltered baseline began.
- `meta/scripts/initialize_amorphous_cortex.py`: embryo creation.
- `meta/scripts/train_campaign36b_bootstrap.py`: real birth/admission loop,
  optimizer extension, journalling, checkpointing, and storage guards.
- `meta/scripts/audit_campaign36b_anatomy.py`: read-only cohort ablation audit.

36B is evidence that persistent distributed cells can grow and learn as one
system. Its substrate intentionally executes every non-dormant cohort, so it is
also the dense-execution control rather than an implementation of 36C waves.

### Tests and current contract

- `tests/test_cortex_checkpoint_schema.py`
- `tests/test_amorphous_substrate.py`
- `tests/test_amorphous_selection.py`
- `tests/test_campaign36b_bootstrap_policy.py`
- `tests/test_campaign36b_audit_selection.py`
- `docs/2026_08_30_campaign36c_local_propagation_contract.md`

The tests document the behavior actually enforced today. The 36C contract
documents the intended architecture; it is not evidence that those mechanisms
have already been implemented.
