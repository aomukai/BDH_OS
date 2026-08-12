# Image reviewer benchmark

The first benchmark uses the same frozen 100 images, prompt, JSON schema, decoding
settings, and intended deployment quantization for every model. Human inspection—not
model agreement—establishes the gold record.

## Models

- Gemma 4 E2B
- Gemma 4 E4B
- Gemma 4 26B A4B, Q4_K_M (Q2 is explicitly excluded)
- LFM2.5-VL-3B, pinned at `b6855f330c15558bfe55038ec3c1c4a7b6825bd1`
- Luna only for unresolved gold/adjudication cases, not as a routine first-pass contestant

## Selection decision

The operational reviewer is Gemma 4 26B A4B Q4_K_M. Its 100-image run produced a valid
full-schema response for every image; its tendency to report `usable` alongside a detected
watermark is handled by the deterministic admission policy below. Luna adjudicates the
comparatively small watermark-alarm set.

LFM2.5-VL-1.6B and 3B result logs are retained as experimental provenance, but their model
weights were removed from the corpus drive. The 3B run produced zero fully valid schemas
despite 93 parseable JSON responses. Gemma E2B was stopped after 55 images once the model
choice was clear, and E4B was skipped.

The generic LFM2.5-VL-1.6B run is retained as an additional baseline. The newly released
3B checkpoint is the core LFM contestant because its published grounding, real-world, and
counting results are directly relevant to corpus review and it still fits on a 12 GB GPU.
`LFM2.5-VL-1.6B-Extract` is downloaded as an optional follow-up but is not a first-pass
contestant. A generic-LFM parser or this specialized checkpoint is tested only after the
raw four-model results identify an error pattern worth solving.

Use each model's published decoding settings while keeping the semantic prompt and output
contract fixed. For LFM2.5-VL-3B those settings are temperature 0.2, top-k 50, repetition
penalty 1.0, and the pinned processor configuration.

## Measurements

Report schema validity, admission accuracy, unsafe false accepts, false rejects,
watermark/text precision and recall, exact-count accuracy, relationship accuracy,
caption-claim precision, calibrated uncertainty, cold/warm latency, images/minute, and
peak VRAM separately.

Headline accuracy is insufficient. For every ordered model pair also report:

- shared correct, shared miss, and disagreement counts;
- unique catches: errors caught by one model and missed by the other;
- oracle-union accuracy: either model supplied the correct answer;
- escalation yield: additional errors caught per 100 escalations;
- escalation cost: added seconds and GPU-seconds per additional catch;
- confidence routing: results when only uncertain/flagged cases reach the second model.

This distinguishes complementary reviewers from redundant same-family votes. A slightly
lower-scoring model can be the better escalation partner if it catches systematic misses.
The 26B model belongs in the ordinary path only if its marginal catches justify its runtime.

## Permanent canaries

Ordinal 65 (`f31f7ea2b00813ef`) is permanently retained as a prompt-example-contamination
canary. It is a handwritten leaf-pattern instruction diagram. A model fails the canary if
it repeats the example's dog/table/under claims instead of describing the actual image.
Its benchmark membership is independent of the eventual policy for admitting diagrams
to the training corpus.

## Admission policy

The model's `admission` field is advisory evidence, not the final decision. After raw
scoring, `python -m image_benchmark.adjudicate RESULTS --output OUTPUT` applies one
deterministic gate to every model: watermarks and explicitly severe defects are rejected,
while ambiguous cases are routed to human/Luna review. The original response remains in
the output alongside the policy decision for auditability.

Pass `--watermark-review training_data/image_registry/benchmark-100-luna-watermark-review.jsonl`
to incorporate explicit alarm adjudications without changing the model's raw record. In
the first 26B run, Luna confirmed 8 overlays, cleared 5 in-scene text/branding alarms, and
left 4 alarms unresolved. The resulting policy output contains 87 usable, 8 unusable, and
5 unresolved images; the fifth unresolved image came from the model's non-watermark
uncertainty.
