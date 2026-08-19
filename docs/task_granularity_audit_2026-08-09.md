# Task granularity and restart audit

This audit treats elapsed time as cheap and irrecoverable ambiguity as expensive. A job may remain large only when splitting it would change its semantics, or when it is a bounded deterministic stream whose output is committed atomically. Independent model calls must be separate durable jobs. Aggregation must be deterministic code, not a larger model prompt.

## Decision rules

- One independently retryable subject per provider/model job.
- A human-friendly label such as "one lesson" is not a unit boundary. A model input may not hide an unbounded repeated list inside a specification.
- Material-writing units are limited to 64 KiB of canonical input and at most 16 repeated input/output items; campaigns should normally choose a lower bound such as one capture or one example.
- A fan-out unit has a stable ordinal and immutable input identity; workflow links are the persisted cursor.
- A wake creates at most one missing unit. Repeated wakes, process replacement, and Mission Hub restart are idempotent.
- Failed unit output remains evidence. Successful siblings are not repeated after repair.
- Candidate pipelines traverse subject-first: generate one candidate, inspect it,
  caption it, decide it, and independently review it before generating another.
  Stage-first waves are forbidden even when every individual stage job is small.
- An unusable candidate is a normal bounded outcome, not an operational
  incident. The next preauthorized seed is attempted immediately. A user-facing
  notice is created only after candidate alternatives or autonomous recovery
  are exhausted, or when a safety stop genuinely requires a decision.
- Fan-in starts only after every required unit is authoritative and successful.
- Stateful optimization may remain one job because splitting batches changes optimizer state. It must start from an immutable parent, publish no partial checkpoint, heartbeat, and safely restart from that parent.
- Deterministic readers, validators, and atomic assemblers may remain streaming jobs when they do not use model context and cannot publish a partial success.

## Every configured job

| Job | Present unit | Decision | Reason / required boundary |
|---|---|---|---|
| `campaign.decide` | one campaign evidence set | keep | One bounded strategic decision; inputs and schema are explicit. |
| `checkpoint.certify` | one checkpoint | keep | Deterministic identity/lineage certification. |
| `checkpoint.compare` | one candidate/parent pair | keep | Pairwise comparison is the semantic unit. |
| `checkpoint.probe` | one checkpoint/probe specification | keep | Bounded diagnostic unit. |
| `checkpoint.publish` | disabled legacy stub | remove when compatibility window closes | No executable production path. |
| `corpus.assemble_generated` | ordered generated-material shards | keep fan-in | New deterministic assembler; consumes one immutable artifact per stable `unit_id` and performs no model call. |
| `corpus.build` | bounded source-file set | keep | Deterministic atomic assembly; current live requests contain one source file. |
| `corpus.transform` | disabled legacy stub | remove when compatibility window closes | No executable production path. |
| `corpus.validate` | one corpus stream | keep | Streaming deterministic validation; no model context accumulation. |
| `executor.generate` | one stable material unit | **workflow-fan-out required** | A nominal lesson formerly could hide an arbitrary batch. `material_workflows` now persists `unit/NNNNNN`; nested repeated input and output are hard-bounded, every successful sibling survives restart, and `corpus.assemble_generated` performs deterministic fan-in. |
| `maintenance.retention_preview` | disabled legacy stub | remove when compatibility window closes | Retention manager owns the real deterministic path. |
| `model.chat` | one rendered prompt/checkpoint | keep | Already the smallest meaningful inference. |
| `model.evaluate` | one checkpoint/evaluation suite | keep, bound suite | Evaluation is deterministic over a declared suite; future large suites should fan out by case and aggregate scores. |
| `model.initialize` | one initialized checkpoint | keep | Atomic deterministic construction. |
| `model.merge` | one ordered checkpoint pair | keep | Pairwise merge is the semantic unit. |
| `model.multimodal_evaluate` | one checkpoint/evaluation suite | keep, bound suite | Same evaluation rule; no unbounded conversational context. |
| `model.multimodal_train` | one ordered training session | keep stateful | Batch splitting would change optimizer semantics. Heartbeat and restart from immutable parent; partial candidates never become authoritative. |
| `model.train` | one ordered training session | keep stateful | Same stateful boundary. Existing campaign sessions provide the outer batching loop. |
| `model.visual_train` | one projector training session | keep stateful | Same stateful boundary; base language checkpoint is re-hashed before publication. |
| `operations.respond` | one operational notice | keep, reduce authority ambiguity | Model response is advisory/intent; deterministic recovery machinery performs and verifies actions. Provider failure code must match its class. |
| `system.artifact_roundtrip` | one artifact | keep | Small commissioning transaction. |
| `system.gpu_probe` | one bounded probe | keep | Device/iteration/memory bounds are explicit. |
| `system.healthcheck` | one machine | keep | Read-only bounded observation. |
| `visual.plan` | one bounded plan | keep | One schema-bound planning decision; candidate work is fanned out afterward. |
| `visual.plan_exact` | one supplied exact plan | keep | Deterministic freezing and validation only. |
| `visual.generate` | previously an entire plan | **split by candidate** | New workflows persist `generate/NNNN`; runtime selection must agree with immutable item/seed ordinal and exactly one candidate must be emitted. |
| `visual.inspect` | previously every candidate | **split by candidate** | New workflows persist `inspect/NNNN`; one image/model context per job. |
| `visual.caption` | previously every candidate | **split by candidate** | New workflows persist `caption/NNNN`; one image/model context per job. |
| `visual.decide` | previously all reports | **split by candidate** | New workflows persist `decide/NNNN`; one generation/inspection/caption evidence tuple. |
| `visual.review` | previously every candidate | **split by candidate** | New workflows persist `review/NNNN`; independent one-image review, preserving failed attempts separately. |
| `visual.pack_finalize` | selected reviewed set | keep fan-in | Deterministic capped aggregation; no model judgment. |
| `visual.encode` | one accepted candidate | **split by candidate** | New workflows persist `encode/NNNN`; each shard must name exactly one accepted SHA-256. |
| `visual.features_finalize` | complete feature-shard set | keep fan-in | Deterministically verifies exact pack coverage and combines shards in immutable pack order without inference. |
| `visual.experience_compile` | one accepted pack/event sequence | keep | Deterministic integrity check and compilation. |

## Visual traversal and retry budget

The durable key remains one candidate ordinal per stage, but ordinals are now
traversed before stages: `generate/0000` → `inspect/0000` → `caption/0000` →
`decide/0000` → `review/0000`, then (only if needed) `generate/0001`.
Each commissioned item may declare up to the configured candidate limit as an
ordered retry budget. The first usable review advances to the next item; an
unusable review advances silently to the next seed. Campaign 35 commissions
four deterministic candidate seeds per new item, while already-created
one-seed workflows retain their immutable specification. If such a preserved
workflow exhausts its single seed, the coordinator preserves that failed
attempt and commissions a deterministic successor without opening an
operational thread. The successor chain is capped at the same four-attempt
budget; only exhaustion or inability to create the authorized successor is
surfaced to the operator and Sol.

Provider/capability failures remain separate execution attempts of that same
one-image job. They are recorded in the run and recovery ledgers, and route
fallbacks plus configured job retries happen without opening an operational
thread. The inbox is reserved for an exhausted or blocked recovery boundary.

The same boundary applies to every atomic content job, not only image
selection. Planning, generation, inspection, captioning, policy decisions,
independent review, encoding, and one-unit text material generation each have
a four-attempt execution budget. Malformed output, provider refusal, or a
rejected unit remains preserved and silent while another authorized attempt or
candidate exists. All intermediate attempts share one recovery incident, so
they cannot accumulate unresolved pseudo-incidents or trip the global circuit
breaker. Only the final failed attempt is projected to the inbox; its notice
explicitly says that the atomic retry budget was exhausted.

## Compatibility and migration

Workflows already containing the legacy `generate` stage retain the old stage graph so that immutable in-flight work is not silently reinterpreted. Newly created or plan-only workflows use per-candidate generation, inspection, caption, decision, review, and encoding stage keys. This is a forward migration: no successful artifact, failed evidence, run, or lineage record is rewritten.

The audit measured authoritative live payloads rather than relying on names. Legacy visual caption/decision/review jobs contained as many as 97 candidates, 99 artifact references, and about 39 KiB of input. Incremental jobs contain one candidate and were measured near 340 bytes before artifact-envelope materialization. Corpus validation currently receives 125 ordered concepts but is a streaming deterministic check. Training receives the same 125-concept session as one stateful optimizer trajectory. Evaluation receives one suite and remains a whole-evidence scientific comparison because its cross-prompt collapse, representation separation, PCA map, and candidate-versus-parent decision require joint evidence; its loop is deterministic and carries no LLM context.

The remaining intentionally long jobs are deterministic streams, joint-evidence evaluation, or stateful training sessions. Their safe recovery mode is replay from immutable inputs/parent checkpoints, not continuation from an unauthoritative partial output. This costs time but preserves optimizer, comparison, and checkpoint integrity. If evaluation suites grow beyond the current bounded scientific fixture, case inference should be sharded with a deterministic whole-suite comparator; it must not be divided into independent reasoning decisions that lose cross-case evidence.
