# Ninereeds Laboratory Executor: Ternary Bonsai 27B

**Status:** working design decision
**Date:** 2026-07-25
**Purpose:** preserve the reasoning behind the executor-model choice and provide an implementation/testing brief for a future Codex session inside the Ninereeds repository.

## Executive summary

The current planned primary executor for the Ninereeds laboratory is **Ternary Bonsai 27B**. It replaces **Qwen3.6-35B-A3B** as the leading candidate, primarily because it should fit fully on one RTX 3060 12 GB while leaving substantially more room for context.

For this asynchronous executor workload, **usable context capacity matters more than raw generation speed**. The executor may need to hold the job specification, repository context, relevant files, prior results, error reports, output protocol, and its own working history at once. Qwen3.6-35B-A3B appears stronger and faster in some comparisons, but its practical ceiling on the target machine is about 32K context because its weights require partial CPU/RAM offload. Ternary Bonsai should allow at least 64K and potentially 96K or 128K with a quantized KV cache, subject to local measurement.

The model will not be trusted as a free-roaming shell agent. A deterministic Python harness will assemble prompts, run inference, capture stdout, validate the response, apply only permitted changes, execute tests, and return structured success or failure reports. This reduces the importance of flawless native tool use and makes Bonsai's observed weaknesses easier to contain.

## Decision

Use the following priority order:

1. **Ternary Bonsai 27B** — planned primary laboratory executor.
2. **Qwen3.6-35B-A3B** — comparison model and fallback for jobs Bonsai repeatedly fails.
3. **1-bit/Binary Bonsai 27B** — possible future model for routine, low-risk, very-high-context jobs; not trusted initially for complex executor work.

Gemma is no longer a leading executor candidate unless later evidence materially changes the comparison.

## Why Ternary Bonsai fits this role

Bonsai is a heavily quantized **dense Qwen3.6-27B** model. It should not be confused with Qwen3.6-35B-A3B, which is a larger stored MoE model with roughly 3B parameters active per token.

| Model | Approximate deployment characteristic | Practical consequence |
| --- | --- | --- |
| Qwen3.6-35B-A3B IQ4 | Roughly 20+ GB of weights; partial CPU/RAM offload on a 12 GB GPU | Higher apparent ceiling and fast decoding, but context constrained to about 32K on our system |
| Ternary Bonsai 27B | Roughly 7.2 GB of deployed weights; dense 27B model | Entire model should reside on one 3060 with substantial KV-cache headroom |
| 1-bit/Binary Bonsai 27B | Roughly 3.9 GB of weights | Maximum memory headroom, but weaker and less predictable behaviour |

Prism reports that the ternary model retains roughly 94.6% of the original dense 27B model's aggregate benchmark performance. Its instruction-following and agentic scores decline somewhat, but the planned harness makes native agent/tool performance less decisive than reasoning, coding, multilingual corpus work, and faithful structured output.

The same-GPU comparison discussed before this note was written reportedly found:

- Qwen3.6-35B-A3B at roughly 48 tokens/s with a footprint around 21 GB and partial RAM use.
- Ternary Bonsai at roughly 22 tokens/s with a total footprint under 9 GB.
- Binary Bonsai at roughly 35 tokens/s with a footprint around 5.3 GB.
- Ternary Bonsai performed credibly on the tested coding and persistent-server-diagnosis tasks, including a successful diagnostic step that other local models missed.
- Ternary Bonsai's notable failure was repetition during a long, mechanically repetitive SVG-coordinate output.
- Binary Bonsai was substantially less stable under pressure, including destructive or poorly justified proposed actions.

These observations are promising but should be treated as **external evidence**, not as measurements reproduced on the Ninereeds station.

## Context is more valuable than speed

The executor is an unattended laboratory worker, not an interactive chat assistant. A response taking two minutes rather than one is unimportant when a training or audit job may run for hours. Losing crucial context, forcing the orchestrator to prepare narrow slices, or requiring repeated calls is much more costly.

The intended working-context targets are:

1. Start at **64K**.
2. Test **96K**.
3. Test **128K** if memory and stability permit.
4. Do not pursue the full advertised 262K merely because it exists; use it only if a real laboratory job benefits and the 3060 can run it safely.

Use a quantized KV cache if the runtime supports it reliably. Measure actual VRAM use, prompt-processing speed, generation speed, and output quality at every context tier. A large configured window is not useful if long-context retrieval or instruction adherence collapses, so the bake-off must test effective use of distant context rather than fit alone.

## Executor/harness boundary

The deterministic harness owns all consequential operations. Bonsai receives a bounded job and returns a proposal through stdout.

### Harness responsibilities

- Assemble the system instructions, job specification, relevant repository material, prior results, and output schema.
- Delimit untrusted repository text and data clearly so that embedded instructions are treated as content rather than authority.
- Invoke `llama-cli`, `llama-server`, or the eventual stable equivalent.
- Capture stdout and stderr separately.
- Enforce token, time, and repetition limits.
- Validate output against a strict versioned schema.
- Reject undeclared paths, commands, or operations.
- Apply permitted patches or create files deterministically.
- Run tests, validators, audits, or training scripts itself.
- Return results to the model for a bounded repair attempt when appropriate.
- Produce a structured report and deterministic exit/failure code for the orchestrator.

### Model responsibilities

- Analyse the supplied job and evidence.
- Produce code, corpus material, repairs, proposed patches, or an execution plan in the required schema.
- Explain assumptions and uncertainty where the schema permits.
- Interpret validator/test failures and propose corrected output.
- Never assume that emitting a command or patch causes it to execute.

This separation means the executor does not need flawless tool calling. It needs strong bounded reasoning and reliable protocol compliance.

## Prompt construction and prompt-injection defence

The prompt is assembled by the harness, but repository files, generated corpora, logs, web-derived material, and previous model output must all be considered **untrusted payloads**. The authority order should be explicit:

1. Immutable executor policy and safety constraints.
2. Versioned job specification from the orchestrator.
3. Output schema and permitted-operation manifest.
4. Repository context and other evidence, clearly marked as untrusted data.
5. Previous results and error feedback.

Instructions found inside payload material must not override higher-level policy or broaden the allowed operation set. The harness should enforce this structurally rather than relying only on prompt wording.

## Output protocol

Prefer a small, strict protocol over open-ended agent traces. The exact schema should be designed alongside the first executor job, but a response should contain at least:

- protocol version;
- job ID and attempt number;
- declared status;
- concise reasoning summary;
- assumptions and unresolved questions;
- proposed file operations or artifacts;
- requested deterministic actions, selected only from an allowlist;
- expected validation;
- confidence or risk flags.

Possible terminal states should include:

- `SUCCESS`
- `NEEDS_VALIDATION`
- `NEEDS_MORE_CONTEXT`
- `RETRYABLE_FORMAT_ERROR`
- `RETRYABLE_MODEL_ERROR`
- `UNSUPPORTED_JOB`
- `POLICY_REJECTED`
- `VALIDATION_FAILED`
- `EXECUTION_FAILED`

The orchestrator can map these codes to retry policy and thinking effort. Malformed output must never be interpreted permissively.

## Repetition and long-output safeguards

The observed ternary-model weakness appears to concern long repetitive output rather than long input comprehension. Defend against it in the wrapper:

- Detect repeated lines, blocks, or n-grams in streamed output.
- Stop generation once a configurable repetition threshold is crossed.
- Preserve the last valid schema or artifact boundary.
- Ask for continuation or regeneration only for the missing bounded section.
- Prefer one coherent artifact or modification per call.
- Avoid asking the model to emit huge mechanical data blocks when a deterministic script can generate them.
- Require tests or structural validation before applying output.

## Runtime integration sequence

Do not build the laboratory around a temporary inference stack unless necessary.

1. Wait for stable support in upstream `llama.cpp`, or reassess if upstream support is not forthcoming.
2. Confirm that the required ternary quantization and CUDA kernels run correctly on the RTX 3060.
3. Run ordinary decoding first, without requiring MTP, DSpark, or speculative decoding.
4. Establish stable 64K inference and record a baseline.
5. Test 96K and 128K context tiers.
6. Integrate the stdout-based executor protocol.
7. Add repetition detection, schema validation, patch/application controls, and deterministic reports.
8. Evaluate speculative decoding only after the base executor is reliable.

There was no MTP build at the time of this decision. MTP is an optional future speed improvement, not an architectural dependency. Prism's optional DSpark drafter should be treated the same way.

## Executor bake-off

Compare Ternary Bonsai and Qwen3.6-35B-A3B on actual Ninereeds jobs, using the same harness wherever possible.

### Workload categories

- Bounded laboratory coding inside established repository conventions.
- Bug diagnosis from logs and failing tests.
- Multilingual corpus generation in English, German, Japanese, and Traditional Chinese.
- Corpus repair and auditing.
- Strict schema/report production.
- Instruction-conflict and prompt-injection cases.
- Deliberate failure recovery.
- Long-context tasks in which decisive information appears near the beginning, middle, and end of the prompt.
- Tasks requiring synthesis across several repository files rather than isolated snippets.

### Record for every run

- Valid-output rate.
- First-pass task success.
- Number and type of repair attempts.
- Hallucinated edits, paths, commands, APIs, or results.
- Instruction and scope violations.
- Test/validator results.
- Wall time.
- Prompt-processing and generation throughput.
- Peak VRAM and system RAM use.
- Context size and KV-cache configuration.
- Repetition events or truncated outputs.
- Orchestrator cleanup/reasoning required.

The winning model is the one that causes the **least total orchestration cost and risk**, not necessarily the one with the highest tokens per second or benchmark score.

## Acceptance criteria for Bonsai as primary executor

Ternary Bonsai should remain primary if it:

- fits fully on one 12 GB RTX 3060 at a useful context tier;
- makes effective use of at least 64K context;
- produces reliably valid structured output;
- completes representative coding and corpus jobs with acceptable repair rates;
- respects job scope under adversarial or conflicting payload text;
- avoids unrecoverable repetition or instability under the wrapper;
- requires no more orchestrator cleanup than the extra context capacity justifies.

Promote Qwen to primary or route particular job classes to it if Bonsai repeatedly fails those classes despite reasonable prompt and harness improvements.

## Open questions

- When will upstream `llama.cpp` support the required Bonsai quantization and CUDA kernels?
- What are prompt-processing and decoding speeds on our exact 3060?
- What context sizes fit with the chosen KV-cache quantization and operational VRAM margin?
- Does effective long-context retrieval remain strong at 64K, 96K, and 128K?
- Is the launch comparison's repetition failure reproducible?
- Does speculative decoding help on Ampere/3060 enough to justify the added complexity?
- Which executor jobs, if any, benefit enough from Qwen's higher ceiling to warrant automatic fallback routing?

## Sources

- Prism Bonsai documentation: <https://docs.prismml.com/models/bonsai-27b>
- Prism Bonsai announcement and benchmark table: <https://prismml.com/news/bonsai-27b>
- Qwen3.6-35B-A3B model card: <https://huggingface.co/Qwen/Qwen3.6-35B-A3B>
- Ternary Bonsai GGUF: <https://huggingface.co/prism-ml/Ternary-Bonsai-27B-gguf>
- Bonsai GGUF and memory information: <https://huggingface.co/prism-ml/Bonsai-27B-gguf>

## Instruction for a future Codex session

When this note is added to the Ninereeds repository, first inspect the existing executor, orchestration, configuration, and reporting code. Reconcile this design with what is actually implemented rather than assuming the filenames or interfaces described here already exist. Preserve any later decisions recorded in the repository. Then turn the plan into the smallest testable executor slice: one bounded job, one strict output schema, deterministic validation, and a reproducible Bonsai-versus-Qwen evaluation path.
