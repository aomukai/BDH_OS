# Image review queue

The image registry SQLite database is the canonical work ledger. A queue is an ordered,
immutable projection of a registry selection; `export-list` produces the human-readable
filename list. Workers never coordinate through JSONL files.

## Lease rules

- A worker has a registered backend, exact model identity, and maximum claim count.
- Claims use an atomic SQLite write transaction, so concurrent workers cannot receive the
  same image.
- A worker cannot claim another batch while any item in its current batch is active.
- Every item has a secret claim token and expiry. Only its owner can renew, complete, or
  fail it.
- Expired and retryable claims return to the queue. Every attempt remains in the audit
  table; stale workers cannot submit after losing a lease.
- Completed results live in the database and retain worker/backend/model provenance.
- The registry uses WAL mode and a 30-second busy timeout for concurrent local processes.

## Create and inspect a queue

```bash
python3 -m image_registry.review_queue_cli create corpus-review-v1 \
  --selection corpus-review-v1
python3 -m image_registry.review_queue_cli export-list corpus-review-v1 \
  /media/aomukai/FILES/Ninereeds/image-corpus/exports/corpus-review-v1-files.jsonl
python3 -m image_registry.review_queue_cli status corpus-review-v1
```

Queue creation fails if any selected image lacks a local path or SHA-256. It also refuses
to overwrite an existing queue.

## API workers

`image_benchmark.queue_worker_api` consumes any OpenAI-compatible vision endpoint. Each
process handles its own batch sequentially; launch multiple processes for parallelism.

Local worker example:

```bash
python3 -m image_benchmark.queue_worker_api \
  --queue corpus-review-v1 --worker-id local-gpu0 \
  --backend llama.cpp-q4km-gpu0 --endpoint http://127.0.0.1:8782/v1/chat/completions \
  --model gemma-4-26b-a4b-it-q4km --max-claims 4 --disable-thinking
```

Run one llama.cpp server per card with `CUDA_VISIBLE_DEVICES=0` and
`CUDA_VISIBLE_DEVICES=1`, different loopback ports, `--split-mode none`, `--parallel 1`,
the same Q4_K_M GGUF/mmproj pair, and automatic GPU fitting. Restricting device visibility
is important: otherwise each server may split itself across both cards and defeat the
two-worker design.

OpenRouter worker example:

```bash
python3 -m image_benchmark.queue_worker_api \
  --queue corpus-review-v1 --worker-id openrouter-01 \
  --backend openrouter --endpoint https://openrouter.ai/api/v1/chat/completions \
  --token-env OPENROUTER_API_KEY --model google/gemma-4-26b-a4b-it \
  --max-claims 8 --disable-thinking
```

Additional OpenRouter processes use distinct worker IDs (`openrouter-02`, etc.). Set the
maximum number of remote processes and the provider/account spend limit before launch;
the lease limit bounds work ownership, not total API expenditure.

After completion:

```bash
python3 -m image_registry.review_queue_cli export-results corpus-review-v1 \
  /media/aomukai/FILES/Ninereeds/image-corpus/exports/corpus-review-v1-results.jsonl
```

The existing deterministic admission and Luna watermark-adjudication pass consumes that
export. Prompt-contamination canaries remain in benchmark queues, not production corpus
queues.
