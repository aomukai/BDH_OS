# Visual Toolchain Trainbox Deployment — 2026-07-29

## Outcome

The pinned visual toolchain is installed and verified on the headless trainbox.
No routine visual worker or autonomous visual plan kind has been commissioned
yet.

## Installed state

| Role | Model | Revision |
|---|---|---|
| generator | `black-forest-labs/FLUX.2-klein-4B` | `e7b7dc27f91deacad38e78976d1f2b499d76a294` |
| receptor | `google/siglip2-base-patch16-naflex` | `b53b807d3a2d5e2b3911292f2d69e5341cdc064c` |
| judge | `google/gemma-4-E4B-it` | `ee0ef6023621cff504d758262d4e04895a5af4a2` |

- Python environment: `/home/aomukai/.venvs/ninereeds-vision`
- Model cache: `/home/aomukai/.cache/huggingface`
- Resolved-path manifest:
  `/home/aomukai/Ninereeds/tmp/vision/model_manifest.json`
- Environment size after installation: approximately 5 GiB
- Hugging Face cache after download: approximately 33 GiB
- Trainbox free space after deployment: approximately 377 GiB

The environment contains Torch 2.13.0 with CUDA 13.0, Transformers 5.14.1,
Diffusers 0.39.0, Accelerate 1.14.0, and bitsandbytes 0.50.0.

## Verification

All probes used pinned local snapshots with Hub and Transformers offline modes
enabled.

1. All three configurations and processors loaded locally.
2. SigLIP2 completed an image/text forward pass and returned a `1 × 1`
   similarity result.
3. Gemma loaded in BF16 on CPU, processed a synthetic image, and answered
   `Red` when asked for its dominant color.
4. FLUX was isolated to physical GPU 0, loaded with sequential CPU offload, and
   completed a four-step 512 × 512 render. Physical GPU 1 remained unused.
5. Both GPUs returned to approximately 1 MiB allocated memory after the FLUX
   process exited.

The deterministic render is:

```text
/home/aomukai/Ninereeds/tmp/vision/probes/flux4b_red_ball.png
sha256 99dd46c8c2c8cab66f9a978cafec0218b47089614c6408df6bb7049385c69e17
```

## Scheduling boundary

Cortex training partitions the 1.2B model across both trainbox GPUs. Visual
work therefore cannot rely only on `CUDA_VISIBLE_DEVICES`; it must participate
in the same durable execution boundary as Cortex plans.

The intended visual sequence is:

```text
acquire global trainbox execution lease
  -> FLUX generation on GPU 0
  -> unload FLUX
  -> Gemma validation
  -> unload Gemma
  -> SigLIP2 activation extraction
  -> unload SigLIP2
  -> persist report and release lease
```

Until a bounded `visual_pack` plan kind, schemas, receipts, retry limits, and
artifact confinement are implemented and tested, the deployment is prepared
but not authorized for routine autonomous generation.

## Remaining generator decision

FLUX.2 Klein 9B was not downloaded. It is a gated optional comparison rather
than a dependency. A later bakeoff should compare 4B against a hardware-feasible
quantized 9B using accepted images per GPU-hour and the human-labelled
content/correctness/cleanliness qualification set.

