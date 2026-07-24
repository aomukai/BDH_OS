# Local Executor Bake-off

This directory contains the model-independent comparison harness for the local
laboratory executor. The model never receives shell access. It reads one bounded
job and returns a proposal through a strict JSON envelope; the harness validates
the proposal and records results without applying it.

The trainbox installation lives outside the repository under `~/executor`:

- `runtimes/llama.cpp-b10107` serves Gemma and Qwen.
- `runtimes/llama.cpp-prism-7529fdaa` serves Ternary Bonsai.
- `models/` contains revision-pinned GGUF files.
- `logs/bakeoff/` receives ignored, machine-local benchmark results.

Exact source commits, model revisions, byte sizes, and SHA-256 checksums are
recorded in `artifact_manifest.json`.

The baseline exposes only GPU 0 to the executor. GPU 1 remains available to
Ninereeds training. Gemma and Qwen may spill weights into system RAM; Bonsai is
fully resident. Bonsai is configured for a 128K context with reasoning disabled;
this avoids its observed tendency to consume a bounded response entirely with
repetitive hidden reasoning.

The commissioning results and current routing recommendation are recorded in
[`BAKEOFF_2026-07-25.md`](BAKEOFF_2026-07-25.md).

Run the static checks:

```bash
python3 training/executor/run_bakeoff.py verify
```

Run the short representative suite:

```bash
python3 training/executor/run_bakeoff.py run --model all
```

Run one model or task:

```bash
python3 training/executor/run_bakeoff.py run \
  --model ternary-bonsai-27b \
  --task msm-script-authoring
```

Re-audit stored results with the current deterministic validators:

```bash
python3 training/executor/run_bakeoff.py audit \
  --from-dir ~/executor/logs/bakeoff/RESULT_DIRECTORY
```

Give only the failed proposals one bounded repair turn:

```bash
python3 training/executor/run_bakeoff.py repair \
  --from-dir ~/executor/logs/bakeoff/RESULT_DIRECTORY
```

Results include the raw response, parsed proposal, validation errors, elapsed
time, API timings when exposed by llama.cpp, and peak GPU memory observed by
the harness. Model output is never written to a proposed repository path.
