# Campaign 33 final review: Play regression and recovery

**Reviewed:** 2026-08-07  
**Campaign:** `campaign-33-play-recovery-recommissioned-v1`  
**Mode:** evolutionary comparison with an experimental purpose  
**Decision basis:** behavioral chat plus MRI; loss is telemetry only

## Outcome

Campaign 33 answered its principal experimental question: ordered training can
produce large, reversible, and highly non-monotonic changes in Ninereeds'
immediate behavior. In the clean comparison, putting protected material last was
substantially more effective than putting the same material first.

This is not evidence that one branch learned more of the 1,500-word curriculum.
The original suite does not measure that question well enough.

## Four branches

| Branch | Provenance | Terminal overall | Terminal protected | Terminal pathologies | Interpretation |
|---|---|---:|---:|---:|---|
| 1 | historical; terminal weights unavailable | 0.288889 | 0.75 | 1 | Useful behavioral/MRI history, but cannot be rescanned or used as a new parent. |
| 2 | historical; begins from branch 1 and contains confounded interventions | 0.266667 | 0.75 | 2 | Demonstrates collapse and recovery, but not a clean causal comparison. Terminal bytes still exist on the trainbox. |
| 3 | recommissioned; protected 50 rows last | 0.288889 | 0.75 | 3 | Clean evidence that last-position rehearsal protected the immediately evaluated behaviors. |
| 4 | recommissioned; identical protected 50 rows first | 0.022222 | 0.0 | 13 | Clean terminal failure of first-position protection under the tested schedule. |

Branches 3 and 4 used the common baseline and identical seed, optimizer policy,
training parameters, per-block row multisets, and twelve 500-row blocks. Branch 4
is an exact rotation of branch 3 inside every block: the same 50 protected rows
moved from the end to the beginning.

Across all twelve evaluations, branch 3 averaged overall `0.1713`, protected
`0.5104`, capability `0.0480`, and 6.75 pathologies. Branch 4 averaged overall
`0.1056`, protected `0.2708`, capability `0.04545`, and 8.25 pathologies.

## Regression and recovery

The trajectories were oscillatory. Branch 3 began at `0.055556`, rose to
`0.222222`, later reached `0.0` at block 10, and ended at `0.288889`. Branch 4
reached `0.188889` at block 11 and then collapsed to `0.022222` at block 12.

Historical branch 2 contains an even larger collapse and recovery: block 48
reached overall/protected `0`, while block 50 returned to `0.288889/0.75`.
However, its recovery changed multiple variables, including RMS policy,
stochastic rounding, and contrast material. It cannot identify a single cause.

The conservative conclusion is that accessible behavior can regress and recover.
The campaign does not prove whether recovery is relearning, unmasking,
reconsolidation, or short-lived recency.

## MRI and Atlas

No recommissioned terminal showed dead or saturated layers. Co-firing density was
approximately `0.303–0.305`, and hidden-state standard deviation remained near
`1`, even when branch 4 behavior collapsed. Pooled core representations had
between-concept cosine near `0.999` and negative concept separation.

Therefore the existing MRI is useful for numerical and activation health, but
its coarse summaries do not explain the behavioral divergence. Chat and MRI must
remain paired.

## Evidence limitations

- Branch 1 terminal weights are missing.
- Branch 2 is historically confounded and is not a clean counterpart.
- The original 15-case suite mostly tests old anchors and epistemic boundaries.
- Protected scoring is keyword-brittle; irrelevant output containing
  `I do not know` can pass.
- Immediate terminal evaluation does not measure delayed retention.
- Loss is excluded from all conclusions.

## Follow-up

1. Preserve and formally close Campaign 33 without selecting an automatic winner.
2. Run a paraphrased held-out new-concept suite against every available terminal.
3. Commission checkpoint-pinned chat so qualitative probes are immutable evidence.
4. Start Campaign 34 as a bounded observational gate-credit experiment, with
   diagnostics disabled by default and proven behavior-preserving before the
   representative block is authorized.

The reusable architecture findings from this review are recorded as `NRK-0004`
through `NRK-0008` in `docs/ninereeds_architecture_knowledge.md`.

