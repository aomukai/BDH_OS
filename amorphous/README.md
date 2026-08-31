# Ninereeds amorphous substrate

This package is the independent Campaign 36B architecture experiment. It does
not wrap, load, or extend the 1.2B BDH cognitive core.

The shared LFM and SigLIP2 organs remain outside the cell population. Projected
observations enter the substrate at width 512; cell propagation returns the same
tensor contract to the existing intention and expression interfaces.

The first implementation deliberately contains less machinery than the full
research proposal:

- low-rank residual cells are born in vectorized cohorts;
- all admitted and provisional cells execute, so routing cannot starve them;
- provisional cells contribute at a bounded scale;
- cohorts can be promoted or made reversibly dormant;
- cell IDs, birth seeds, lifecycle state, growth-controller state, and weights
  round-trip through checkpoints;
- cell birth requires a persistent residual, organism-level failure evidence,
  and a separate capacity-saturation diagnosis;
- no local Hebbian update, semantic expert labels, topology learning, physical
  reclamation, or SSD paging is claimed yet.

Run the substrate tests in the isolated Cortex environment:

```bash
/home/aomukai/.venvs/ninereeds-cortex/bin/python -m pytest -q \
  tests/test_amorphous_substrate.py
```

The code is an experiment surface, not authorization to begin a long training
run. Bootstrap sessions must retain their immutable source order and receive
Mission Hub receipts before their observations can be compared with the 1.2B
lineage.
