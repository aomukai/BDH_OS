# FLUX curriculum-image commissioning probe

Date: 2026-07-31

Status: qualified for bounded candidate generation; not an autonomous visual
pack worker.

## Qualified runtime profile

The probe pinned `black-forest-labs/FLUX.2-klein-4B` at revision
`e7b7dc27f91deacad38e78976d1f2b499d76a294` and used FP16, four inference
steps, guidance 1.0, 512 x 384 output, and sequential CPU offload on one 12 GB
trainbox GPU.

- warm generation or edit time: approximately 9.5--12.7 seconds per image;
- observed model-load time after cache warm-up: approximately 5--15 seconds;
- first probe load: approximately 48 seconds;
- peak CUDA allocation with sequential CPU offload: 0.968 GiB;
- model CPU offload also fit, at 7.987 GiB peak, but was slower at
  approximately 16.0--16.7 seconds per image.
- an exact rerun of the pinned prompt, seed, dimensions, and inference profile
  reproduced SHA-256 `8654669c8e763ab246e63a96ce41e52671bcefa07739e9cb6ce6e5131f605717`.

The worker should keep one pipeline resident for a bounded candidate batch,
use sequential CPU offload on this machine, then unload it before visual
judging or SigLIP extraction. Full-model CUDA residency was not commissioned.

## Image quality

The initial four-image probe produced photorealistic, usable candidates for a
plain dog, a dog under a table with two balls, adding balls to an Oxford Pet
photograph, and moving the dog under a table. The edits preserved the broad
appearance, pose, framing, and lighting well, but they reconstructed fine
identity details rather than performing a literal pixel-local edit.

The generator is suitable for special curriculum requests and controlled
variations. Oxford Pet remains the economical source for ordinary cat/dog
examples; generating the entire foundational image set is not justified.

## Prompt qualification

For generation, both a detailed positive narrative and structured JSON
produced good plain and relational scenes. The default compiler should use a
30--80 word narrative ordered as subject, action/relation, style, and context.
Structured JSON is an optional representation for complex generated scenes,
not an accuracy guarantee.

For a localized edit, state the delta first and enumerate what must remain
unchanged. Counts are stochastic and always require pixel-level validation.
In the replicated two-red-ball edit:

| prompt style | exact-count successes | qualification result |
| --- | ---: | --- |
| preserve list + `Change nothing else` + `no extra balls` | 4/4 | provisional default for exact-count edits |
| concise edit + preserve list | 2/4 | candidate only |
| structured JSON edit | 0/4 | do not prefer for exact counts |
| positive final-total wording | 0/3 | do not prefer for exact counts |

This task-specific result does not overturn the general FLUX guidance to
describe desired content positively. It establishes that, for this model,
source image, and exact-count edit, the explicit exclusion was materially more
reliable. The commissioning system must retain prompt family, seed, and attempt
history so this policy can be revised with more evidence.

## Validation policy

Gemma E2B BF16 parsed all four generated-image records and recognized dog
content, but accepted only one of four. It mislabeled both `under the table`
relations as `in front of the table` and produced contradictory ball-count
evidence on one edit. Luna independently accepted all four and correctly
identified the tested counts and relations.

Therefore:

1. mechanical checks run first;
2. Gemma supplies a blind description and structured first opinion;
3. DeepSeek checks that textual evidence and assigns policy buckets;
4. every count, spatial-relation, or edit-preservation claim receives a second
   independent visual inspection even if DeepSeek did not say `check_again`;
5. disagreement consumes a bounded retry or goes to human audit, never to
   automatic acceptance.

Simple species-only dataset curation may use Gemma as the first visual pass
after a larger human-labeled qualification set, but Gemma remains provisional
and is not an autonomous acceptance authority.

## Evidence locations

Authoritative trainbox reports are under
`/home/aomukai/.local/share/ninereeds/visual/reports/`:

- `flux_curriculum_probe_20260731.json`;
- `flux_prompt_style_probe_20260731.json`;
- `flux_model_offload_probe_20260731.json`;
- `flux_determinism_rerun_20260731.json`;
- `flux_edit_count_styles_offset_{100,200,300}.json`;
- `flux_curriculum_gemma_e2b_20260731.json`;
- `siglip2_catdog_subset_{101,202,303,404,505}.json`.

The generator script is `meta/scripts/probe_flux_curriculum.py`. Every output
was imported into the content-addressed visual catalog with model revision,
prompt, seed, source parent, intended delta, and search terms.

## External prompting references

- BFL fast prompting guide:
  <https://help.bfl.ai/articles/7592221790-how-do-i-generate-quickly-with-flux-2-klein>
- BFL FLUX.2 prompting guide:
  <https://docs.bfl.ai/guides/prompting_guide_flux2>
- BFL single-reference editing guide:
  <https://docs.bfl.ai/guides/prompting_editing_single_reference>
- BFL FLUX.2 repository: <https://github.com/black-forest-labs/flux2>
- Hugging Face Diffusers FLUX.2 pipeline:
  <https://huggingface.co/docs/diffusers/api/pipelines/flux2>
