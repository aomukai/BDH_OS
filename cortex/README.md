# Ninereeds Cortex Experiments

This package contains opt-in interfaces for frozen receptive and expressive models.
It does not replace the existing byte-token BDH path.

## Anatomy

```text
frozen mBERT token states [B,T,768]
  -> trainable afferent projector [B,T,D]
  -> BDH.encode_embeds
  -> trainable IntentionHead [B,K,D]
  -> trainable egress projector [B,K,1024]
  -> frozen LFM2.5-230M
```

LFM never receives the original user prompt. It receives only the short intention
sequence produced after Ninereeds processing. This is an architectural ownership
constraint, not merely a training convention.

## Environment

Keep the cortex dependencies separate from the working Ninereeds training environment:

```bash
uv venv --python 3.13 ~/.venvs/ninereeds-cortex
uv pip install --python ~/.venvs/ninereeds-cortex/bin/python \
  torch --index-url https://download.pytorch.org/whl/cu130
uv pip install --python ~/.venvs/ninereeds-cortex/bin/python \
  -r cortex/requirements.txt
```

The CUDA wheel/index must be selected for the eventual training machine's installed
driver. Do not mechanically reuse `cu130` if that machine is configured differently.

Model weights belong in the Hugging Face cache, not this repository. Download them with:

```bash
~/.venvs/ninereeds-cortex/bin/python meta/scripts/download_cortex_models.py
```

Then run the two hardware-independent interface probes:

```bash
~/.venvs/ninereeds-cortex/bin/python meta/scripts/probe_mbert_representations.py \
  --output tmp/cortex/mbert_representation_probe.json

PYTHONPATH=. ~/.venvs/ninereeds-cortex/bin/python \
  meta/scripts/probe_lfm_intention_prefix.py
```

The LFM probe deliberately supplies no original text prompt. It verifies that a
teacher-forced response produces gradients in the intention vectors and projector while
all LFM parameters remain frozen, then checks generation from virtual prefix embeddings.

## Current boundary

The package prepares single-device representation and prefix compatibility probes.
Two-GPU BDH layer partitioning, MSM plasticity manifests, and service orchestration wait
for the assembled training machine and measured hardware topology.
