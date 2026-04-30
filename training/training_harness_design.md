# Integrated BDH Training Harness Design

This document defines the offline autonomous training, evaluation, branching, and merge harness for the BDH-based system. It supersedes the earlier base draft and revised addendum. It preserves the base design’s bounded round loop, explicit intervention registry, verifier gate, structured artefacts, and hourly cadence, while incorporating the revised campaign layer, branch/archive outcomes, `compare_branch`, `merge_candidate`, `retention_probe`, tiered evaluation, and the artefact rename to `worker_report.json`. It also elevates merge supervision into a first-class orchestration task, because BDH supports unusually direct structural composition and the broader model-merging literature shows that systematic branch selection and merge policy are far more reliable than intuition-led trial and error. fileciteturn0file1 fileciteturn0file0 citeturn3view0turn1view1turn4search10

## 2. Purpose and doctrine

The harness exists to improve the model through explicit, auditable interventions rather than opaque self-modification. Its target remains the same as in the existing design: a coherent BDH-based conversational model with broad, shallow knowledge, deeper capability deferred to Skill LoRA, and continued growth through a controlled offline Dream LoRA process. The revised document does not change that target; it changes the machinery used to reach it by adding campaign memory, archive-aware evolution, and structured retention testing. fileciteturn0file1 fileciteturn0file0

The new doctrine is that goal-specific capability can be developed on side branches and only then integrated into mainline through a supervised merge pipeline. That addition is justified by the BDH paper itself: it reports that BDH-GPU can be scaled by varying the number of neurons, and demonstrates a direct merge in which neuron-dimension tensors are concatenated and shared parameters are averaged. In that experiment, the merged model immediately preserved a meaningful subset of capabilities and then improved quickly with a small amount of post-merge training, which makes branch-specialise-and-integrate a sensible design pattern for this architecture. It also makes one crucial point clear: a merge that looks promising in raw parameter space still requires post-merge validation and, in many cases, a bounded repair phase before it should be treated as production-ready mainline material. citeturn3view0turn3view1turn3view2

Nothing in this design turns growth itself into the objective. The original guard rails remain valid: transparency over opacity, one bounded round at a time, one major intervention per round, verifier-gated teacher output, and human oversight at the strategic level. The addition of branching and merging is therefore not a licence for open-ended population search. It is a controlled extension of the same philosophy: local search around explicit hypotheses, with narrow promotion rules and a bias toward reversibility. That is also consistent with current research on evolutionary model merging, which argues that search over merge recipes can be productive, but only when the search space is made explicit and auditable rather than improvised. fileciteturn0file1 fileciteturn0file0 citeturn1view1turn10view1

## Roles and decision boundaries

The role split should now be stated in model-neutral, operational language. GPT-5.4 is the orchestrator and policy owner. Gemini 3 Pro is the executor and bounded worker. A verifier remains mandatory whenever student-facing content, evaluation judgments that affect promotion, draft training data, or merge promotion decisions are involved. This preserves the original structure of the harness while removing any lingering dependence on vendor-specific naming in the artefacts. fileciteturn0file1 fileciteturn0file0

The orchestrator now owns two classes of decision. The first is the existing intervention question: what should happen next inside the current failure cluster or campaign. The second is the new integration question: if a branch has become locally useful, should it remain an archived specialist, continue as a branch champion, or be merged into mainline. Those must stay separate. A branch can be successful as a specialist and still be non-promotable as a parent for mainline integration. The revised draft’s addition of `compare_branch` and `merge_candidate` already points in this direction, and the BDH merge experiment makes the distinction necessary because raw merges can preserve some behaviour while still introducing interference or representational drift. fileciteturn0file0 citeturn3view1turn3view2

The executor still runs one bounded round and then stops. That constraint matters more once merging becomes first-class. The executor may materialise a branch, compare branches, produce a sandbox merge, run a repair round, or write reports, but it does not invent policy, widen scope, or silently promote anything. The verifier’s remit should also expand. In addition to checking teacher-produced content, it should now validate lineage completeness, merge-plan correctness, evaluation integrity, and whether a proposed promotion package actually supports the decision being claimed. This is a direct extension of the base rule that no raw teacher output should reach the student or accepted corpus without verification. fileciteturn0file1 citeturn11view0turn11view1

## Bias-Balancing Circuit Breaker

The harness uses a deliberately simple arbitration rule to prevent either the Orchestrator or Executor from becoming the de facto sole authority during unattended operation.

This is not an intelligent judge. It is a low-cost anti-dominance mechanism.

The goal is to prevent systematic drift toward one model’s training culture, preferences, blind spots, or refusal/overreach patterns without introducing heavy multi-agent overhead.

---

### Protocol

1. The Orchestrator proposes the next action.
2. The Executor may accept or raise a technical objection.
3. Objections must cite concrete artefacts:
   - `metrics.json`
   - `worker_report.json`
   - `decision.json`
   - evaluation gate failures
4. Each side is limited to two evidence-bearing turns.
5. If no agreement is reached, a deterministic parity rule is applied:
   - even global rounds → Orchestrator wins
   - odd global rounds → Executor wins

---

### Scope Constraints (Critical)

The circuit breaker may only resolve decisions where **both options are already valid under harness policy**.

It must never override:

- verifier failures
- Tier 1 evaluation failures
- promotion gate failures
- missing or invalid artefacts
- invalid lineage / merge plan
- out-of-scope or unsafe data generation

If any policy gate fails, arbitration is not allowed. The decision is automatically rejected.

---

### Audit Requirements

Every arbitration event must be logged in `ROUND_STATE.json`:

```json
{
  "arbitration_applied": true,
  "tie_break_winner": "orchestrator",
  "global_round": 42,
  "losing_objection": "Executor flagged insufficient retention evidence",
  "policy_gates_passed": true
}
```

---

### Rationale

This mechanism intentionally trades adjudication quality for:

- zero additional compute cost
- bounded latency
- resistance to single-model dominance

It is not a truth-finding system. It is a bias-balancing circuit breaker for cases where two policy-valid paths remain in conflict.

## State model

The harness now has three nested units of state. The atomic unit remains the round. The persistent local-search unit is the campaign, which already exists in the revised draft as a cluster- or hypothesis-centred container with a parent checkpoint, allowed interventions, stop conditions, and outcome classification. The new unit introduced here is the frontier: the small live set of branches and merge candidates that a campaign is currently allowed to manipulate. Campaigns already give the system memory and local research continuity; the frontier makes the new evolutionary behaviour bounded enough to be safe and interpretable. 

A practical way to implement that frontier is to keep at most three live candidates per campaign: a champion, a challenger, and, only when progress plateaus, one explorer. The champion is the best current branch or merge path on the campaign objective. The challenger is the most plausible alternative produced by a different intervention or merge recipe. The explorer is reserved for deliberate diversity, usually a lower-kinship merge parent or a materially different recipe added to escape local optima. This is an inference from the revised archive-aware campaign design and from kinship-guided iterative model-merging work, which frames model evolution as a selection-merge-recycle process and shows that controlled diversity is useful when greedy improvement plateaus.

Branch state should therefore be formalised as part of the canonical state, not left implicit in folder names. The minimally useful classes are: `mainline`, `campaign_branch`, `merge_candidate`, `archive_promising`, `archive_failed_but_informative`, and `reverted_snapshot`. The minimally useful decisions are: `keep_as_mainline`, `keep_as_branch_champion`, `archive_promising`, `archive_failed_but_informative`, `revert`, and `request_more_data`. This preserves the revised draft’s archival logic while making room for the distinction between local branch success and global integration success. Archived branches are reusable assets, not dead ends; they may later re-enter the frontier as comparison baselines, merge parents, or exploratory outliers. 

All merge-eligible branches should originate from the current mainline or from an explicitly named merge base, not from arbitrary distant archives. Research at scale finds that merge outcomes depend strongly on base-model quality, while the theory work on task arithmetic identifies data heterogeneity and training heterogeneity as key determinants of merge failure. In practice, that means the orchestrator must treat ancestry, training schedule, optimiser regime, steps, data ratio, and target cluster as part of branch identity. If those fields are unknown, the branch is weaker as a merge parent and should usually be downgraded to archive or research-only status. 7view3

## Intervention and merge policy

The intervention registry should now be organised into three layers. The first layer is unchanged from the base design: `train_longer`, `teacher_student_drill`, `oversample_cluster`, `reorder_curriculum`, `add_contrastive_pairs`, `simplify_wording`, `verify_teacher_output`, and `request_more_data`. The second layer is the revised addendum’s extension: `compare_branch`, `merge_candidate`, and `retention_probe`. The third layer should be made explicit now that merging is first-class: `premerge_align` and `postmerge_repair`. These two are not optional embellishments. They correspond to recognisable classes in the model-merging literature—alignment before merging and calibration or surgery after merging—and they are precisely the kind of recurring, policy-relevant operation that should exist as visible skills rather than hidden subroutines. 

Parent selection for `merge_candidate` should be rule-driven, not intuitive. The default policy is homologous merging only: same BDH family, same tokenizer, compatible tensor topology, and preferably a shared checkpoint ancestor. DARE’s LLM results explicitly operate on homologous models, and both the one-shot federated-learning view of task arithmetic and the newer scaling-law analysis show why this matters: training heterogeneity and data heterogeneity degrade merge quality, while over-trained experts can collapse when fused. That means the orchestrator should carry a mergeability budget for every branch, covering divergence from base, fine-tuning depth, learning-rate regime, data ratio, rehearsal exposure, and interference history. Branches intended for later integration should be trained to be useful specialists, but not trained so far or so idiosyncratically that they stop being merge-friendly.

Recipe selection should follow a clear escalation ladder. If two branches are close siblings and differ mainly by light specialisation or hyperparameter path, start with the simplest compatible merge: soup-style averaging or task arithmetic, because weight averaging performs well when fine-tuned models remain in a shared basin and task arithmetic is the natural low-complexity baseline. If interference is likely—especially sign conflict, redundant low-magnitude changes, or more than two source experts—prefer TIES or DARE, because both methods explicitly target parameter conflict by trimming, sparsifying, or resolving sign disagreement. If the issue appears to be geometric misalignment rather than task conflict, run `premerge_align` first with a weight-alignment method such as Git Re-Basin. If the merged checkpoint passes most evaluations but exhibits residual internal bias or calibration drift, apply `postmerge_repair` rather than discarding the candidate immediately. The newer theory literature explicitly treats these as pre-merge, during-merge, and post-merge stages that solve different parts of the same problem.

BDH-specific structural merging should be treated as its own recipe family rather than folded into generic task-vector merging. When the goal is deliberate capacity expansion or composition of disjoint specialists that were kept close to a common base, the default BDH recipe should follow the paper’s direct procedure: concatenate tensors along the neuron dimension and average the shared tensors. But the orchestrator should never confuse “architecture-native” with “safe to promote”. The same experiment that shows the method’s feasibility also shows asymmetric degradation after raw merge: the merged model retained useful translation into English while mixing Spanish, French, and Portuguese when generating outward from English. That pattern strongly argues for a required repair stage—brief joint rehearsal, calibration, or a temporary corrective LoRA—before any mainline promotion.

The orchestrator may search over merge recipes, but only inside a bounded and recorded search space. The legitimate search dimensions are parent pair or parent set, recipe family, coefficients, sparsity density, alignment choice, repair budget, and stopping rule. Evolutionary optimisation of merge recipes has empirical support, and kinship-guided iterative merging shows that deliberate exploration can escape local optima that greedy exploitation cannot. But uncontrolled breeding is still out of scope. The frontier stays small, every merge proposal must be attached to a campaign or explicit integration objective, and high kinship among the best surviving candidates can be used as a convergence signal rather than an excuse to keep generating nearly identical descendants.

## Evaluation and promotion policy

The evaluation spine remains tiered, but it is now governed by the Sparsity-Gated Handshake to ensure that "progress" is verified by two different model architectures before any state change occurs.
### Tiered Evaluation Gates
    Tier 1 (The Cheap Gate): Syntax stability, formatting correctness, checkpoint loadability, and blatant output corruption.
    Tier 2 (The Seismic Gate): Concept integrity, reasoning consistency, grounding, and behavioural health.
    The Retention Anchor: Retention is a first-class requirement measured through delayed recall and distraction robustness. A model that passes immediately but loses knowledge after a distractor sequence is classified as "excited" rather than "integrated" and fails promotion.

### Promotion Sequence
A branch only moves to the mainline if it clears four specific comparisons:
    Target Improvement: Branch vs. Parent on the specific campaign goal.
    Merge Integrity: Sandbox merge vs. Winning branch (did the merge erase the gain?).
    Global Safety: Sandbox merge vs. Mainline on the global regression suite.
    Retention Probe: The merged model must hold knowledge across a distractor sequence.
If a merge is "almost ready" but shows minor residuals, the orchestrator may allocate one bounded postmerge_repair round. If this fails, the outcome is archive_promising, not promotion.

### State Tracking (New Fields)
To audit this process and detect model bias, the following fields must be updated in ROUND_STATE.json at the end of each hour:
    consensus_rounds: Integer (1 or 2) — Tracks how many turns were needed to reach agreement.
    arbitration_applied: Boolean — True if the Round Robin circuit breaker was triggered.
    tie_break_winner: String (model_name) — Records which model won the tie-break.
    rejection_reason: String (optional) — Brief summary if the Executor blocked an Orchestrator proposal.

### Emergency Exit (Merge-Aware)
The request_more_data trigger is tied to campaign exhaustion. A request must specify the bottleneck: missing target competence, incompatible branch ancestry, or unresolved interference between specialists. Merge attempts, repair failures, and Arbitration Deadlocks are now officially part of the "exhausted intervention" record that justifies a human data request.

## Artefacts, lineage, and cadence

The original artefact discipline remains a strength and should be extended rather than replaced. The required round artefacts should remain `plan.md`, `summary.md`, `metrics.json`, `decision.json`, and `worker_report.json`. When a round mutates or evaluates a checkpoint, it should also emit `branch_card.json`. When a round performs or evaluates a merge, it should additionally emit `merge_plan.json`, `merge_metrics.json`, `lineage.json`, and `promotion_review.json`. `verifier_report.json`, `draft_data_request.json`, `draft_training_data.md`, and `notes.md` remain conditional. The revised draft already standardises the rename to `worker_report.json`, and current systems work on iterative LLM merging shows why the rest of the extension matters: reproducible merging needs explicit plans, lineage, transactional snapshotting, and cost semantics rather than a stateless one-shot script.

`branch_card.json` should record the branch’s base checkpoint, training objective, target cluster, data provenance, optimiser regime, steps, learning-rate schedule, rehearsal exposure, verifier status, and mergeability budget. `merge_plan.json` should record parent hashes, common ancestor, kinship summary, chosen recipe, coefficients, sparsity or density settings, alignment transform if any, repair allowance, and the exact evaluation suites required for promotion. `lineage.json` should capture the atomic publish chain from merge plan to materialised checkpoint to mainline decision. These records are not administrative overhead. They are the minimum needed for the orchestrator to reason across campaigns instead of relearning the same lessons repeatedly, and they align closely with recent systems work that treats merge plans and lineage as first-class data objects. 

The logs should therefore expand beyond the original `round_index.jsonl`, `intervention_history.jsonl`, and `emergency_requests.jsonl`. Add `campaign_index.jsonl`, `branch_registry.jsonl`, `merge_registry.jsonl`, and `retention_history.jsonl`. `merge_registry.jsonl` is especially important because the orchestrator will otherwise lose the empirical history of which parent combinations, recipes, sparsity levels, and repair budgets produced useful descendants and which only produced noise. This is also where kinship, convergence, and archive reuse become operational rather than conceptual. Each published checkpoint should be atomically materialised, reversible, and linked back to its decision artefacts so that `revert` is a state transition, not an improvisation. 

The cadence remains one round per hour, with campaign context persisting across rounds. That cadence still makes sense because it enforces bounded progress, clean checkpoints, and reliable historical reasoning. Merge work may span several rounds—screening in one, sandbox materialisation in the next, repair in a third—but each round should still make one major change only. If the corpus gate remains closed, the harness should stay in dry-run mode: compare branches, run verifier checks, plan merges, simulate promotion logic, and draft data requests, but do not mutate mainline until the corpus state allows live training. That preserves the base design’s current readiness model while letting the new merge-aware policy be exercised before activation.

The result is a harness that is still round-based, campaign-driven, archive-aware, and verifier-protected, but now also frontier-bounded and merge-supervised. In practical terms, that gives the orchestrator a coherent autonomous plan: identify a failure cluster, create or improve a targeted branch, compare it rigorously, decide whether it is worth integrating, choose a merge recipe appropriate to its ancestry and interference profile, repair only when the residuals justify it, and promote into mainline only when the gain survives retention and broad regression testing. That is the disciplined version of evolutionary improvement that fits both the original design philosophy and the emerging evidence on BDH composability and model merging.

### Generation Tracking and Lineage Diversity

To avoid structurally redundant merges and to better estimate merge value, the harness introduces **generation tracking and lineage-aware merge evaluation**.

The core insight:

- Branches with a **recent common ancestor** are likely to be **structurally similar**
- Merging such branches has **low value** and increases risk of **representation redundancy**
- Lineage depth and ancestry distance must therefore be tracked explicitly

---

### Branch Registry Extensions

Each branch must record its lineage:

```json
{
  "branch_id": "B014-SOCROLE",
  "parent_branch_id": "B009-SOCROLE",
  "base_checkpoint": "ckpt_001",
  "generation_depth": 4,
  "campaign_id": "C003-SOCROLE",
  "ancestor_chain": [
    "mainline_001",
    "B002",
    "B006",
    "B009"
  ],
  "lineage_family": "SOCROLE_A"
}
```

Definitions:

- `generation_depth`: number of steps from base checkpoint
- `ancestor_chain`: ordered lineage for ancestry tracing
- `lineage_family`: optional grouping for campaign-level specialization

---

### Merge Plan Lineage Evaluation

Every merge proposal must include lineage compatibility:

```json
{
  "lineage_compatibility": {
    "common_ancestor": "B009-SOCROLE",
    "generations_since_common_ancestor": 1,
    "recent_common_ancestor_flag": true,
    "structural_redundancy_risk": "high",
    "expected_merge_value": "low"
  }
}
```

Derived rules:

- `generations_since_common_ancestor <= 2` → likely redundant
- close lineage → low diversity → low merge value
- distant lineage → higher diversity → higher value, but higher risk

---

### Lineage Metrics

Each branch should expose computed lineage metrics:

```json
{
  "lineage_metrics": {
    "generation_depth": 4,
    "generations_since_common_ancestor": 1,
    "lineage_diversity_score": 0.18
  }
}
```

Where:

- `lineage_diversity_score` is a normalized measure of ancestry divergence
- low score → high overlap → low merge value
- high score → meaningful diversity → candidate for integration

---

### Merge Decision Policy

Lineage becomes a third axis in merge evaluation:

```text
merge risk        → likelihood of regression
merge value       → capability gain
lineage diversity → whether merge is worth attempting
```

Guidelines:

- low diversity + low value → reject or archive
- low diversity + specific repair goal → allow (repair merge)
- high diversity + low risk → strong merge candidate
- high diversity + high risk → sandbox merge + strict evaluation

---

### Constraint Rule

Default policy:

> Do not merge branches with recent common ancestry unless the merge is explicitly classified as a repair or reconciliation step.

---

### Rationale

This prevents:

- redundant merges of near-identical branches
- wasted evaluation cycles
- false sense of progress from structurally similar variants

And enables:

- targeted integration of genuinely distinct capabilities
- controlled evolutionary exploration
- clearer separation between specialization and integration