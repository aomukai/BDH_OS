# Visual Toolchain Bootstrap

This toolchain is deliberately separate from the canonical foundational
bootstrap. It prepares an image generator, visual receptor, and independent
multimodal judge for shadow experiments and later visual-grounding campaigns.

The future control-plane, asset, validation, MSM, Cortex, evaluation, and
autonomy contracts are specified in
`docs/visual_experience_pipeline_design.md`. That document is the starting point
for implementation after the foundational bootstrap is complete.

The heavyweight runtime belongs on the headless trainbox. The workstation only
authors lesson specifications, submits bounded jobs through the durable control
plane, and reviews reports or accepted images. It must not run routine
generation or validation workloads.

## Pinned anatomy

| Role | Default model |
|---|---|
| curriculum image generation | `black-forest-labs/FLUX.2-klein-4B` |
| optional generator bakeoff | `black-forest-labs/FLUX.2-klein-9B` |
| permanent frozen visual receptor | `google/siglip2-base-patch16-naflex` |
| multimodal image-quality judge | `google/gemma-4-E4B-it` |

The exact immutable revisions live in `vision/model_registry.py`.

Klein 4B is the default on the trainbox's RTX 3060 12 GB cards. Klein 9B remains an
optional quality benchmark: its published BF16 footprint is about 29 GB and its
Hugging Face checkpoint requires accepting the FLUX Non-Commercial License.
NineReeds is non-commercial, but the accepted license and model revision must
still be recorded.

## Environment

Install the runtime on the trainbox under its existing `~/.venvs` and Hugging
Face cache conventions:

```bash
ssh ninereeds-trainbox
cd ~/Ninereeds

~/.local/bin/uv venv --python 3.12 ~/.venvs/ninereeds-vision

~/.local/bin/uv pip install \
  --python ~/.venvs/ninereeds-vision/bin/python \
  torch torchvision \
  --index-url https://download.pytorch.org/whl/cu130

~/.local/bin/uv pip install \
  --python ~/.venvs/ninereeds-vision/bin/python \
  -r vision/requirements.txt
```

Download the default local stack:

```bash
PYTHONPATH=. ~/.venvs/ninereeds-vision/bin/python \
  meta/scripts/download_visual_models.py
```

The command records resolved snapshot paths in
`tmp/vision/model_manifest.json`. Model weights remain in
`~/.cache/huggingface` and must not be committed.

To add the gated 9B benchmark after accepting its license:

```bash
~/.venvs/ninereeds-vision/bin/hf auth login

PYTHONPATH=. ~/.venvs/ninereeds-vision/bin/python \
  meta/scripts/download_visual_models.py --model flux9b
```

## Verification

Metadata and processor verification is inexpensive:

```bash
PYTHONPATH=. ~/.venvs/ninereeds-vision/bin/python \
  meta/scripts/probe_visual_models.py
```

Full probes load model weights. The FLUX probe also renders one deterministic
512-pixel image into `tmp/vision/probes/` and uses sequential CPU offload on the
12 GB GPU. The Gemma smoke probe intentionally runs in BF16 on CPU so it does
not compete with the active foundational bootstrap for GPU memory:

```bash
PYTHONPATH=. ~/.venvs/ninereeds-vision/bin/python \
  meta/scripts/probe_visual_models.py --model siglip2 --full

PYTHONPATH=. ~/.venvs/ninereeds-vision/bin/python \
  meta/scripts/probe_visual_models.py --model gemma --full

PYTHONPATH=. ~/.venvs/ninereeds-vision/bin/python \
  meta/scripts/probe_visual_models.py --model flux4b --full
```

## Generator selection

Do not select 4B or quantized 9B from vendor aggregate scores alone. Build a
human-labelled qualification set of clean and malformed curriculum requests and
measure:

- accepted images per GPU-hour;
- content pass rate;
- malformed-image false-accept rate;
- cleanliness pass rate;
- style compliance and diversity.

Use 9B only if its verified yield materially exceeds the faster 4B path on the
actual NineReeds curriculum.

## Workstation commissioning evidence

On 2026-07-28:

- the pinned SigLIP2 NaFlex checkpoint loaded offline and produced a `1 × 1`
  image/text similarity result;
- Gemma 4 E4B Instruct loaded offline in BF16 on CPU and correctly identified
  the dominant color of a synthetic image;
- FLUX.2 Klein 4B loaded offline with sequential CPU offload and completed a
  four-step 512 × 512 render on the RTX 3060.

The 9B checkpoint has not been downloaded. It remains a gated, optional
quantized bakeoff candidate rather than a dependency of the first visual
pipeline.

These workstation probes commissioned the pinned software stack only. Routine
visual work must run on the trainbox and must acquire the same global execution
boundary used by Cortex jobs; Cortex training occupies both GPUs. FLUX
generation, Gemma validation, and SigLIP2 extraction should execute sequentially
and unload between stages.

The corresponding trainbox deployment and full-probe evidence is recorded in
`docs/visual_toolchain_trainbox_2026-07-29.md`.
