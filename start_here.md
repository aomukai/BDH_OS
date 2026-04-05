I'm building a cognitive OS for a small language model called BDH. Read bdh_cognitive_os_design.md for the full spec and bdh.py for the model architecture. The trained model is at core/bdh_100m_final.pt. Do not modify bdh.py — treat it as a read-only dependency.

## Status

### Milestone 1 — complete
- inference.py: loads checkpoint, byte-level tokenisation, seeded generation
- harness.py: full live loop — classify → shape → specialist → reload → final output → save artifacts
- prompt_shaper.py: routes user input to completion-friendly shapes (definition, qa, story, passthrough, fill)
- eval.py: comparative eval with scoring and failure mode detection
- Locked generation settings: temperature=0.8, top_k=None

### Milestone 2 — LoRA research complete, ready to build OS

**What we built:**
- HebbianLoRA on encoder + encoder_v (design doc spec) — 540K params, 2.09%
- SurfaceLoRA on lm_head — 2K additional params, output-layer only
- Three-layer training data structure: short anchor → expanded Q/A → subject repetition
- Contrastive pairs: similar concepts adjacent to maximise disambiguation pressure

**What we learned (v1 → v4 datasets, multiple LR/epoch sweeps):**

| experiment | finding |
|------------|---------|
| lr=1e-3, 30 epochs | too loud — delta 26% of base, template attractor |
| lr=1e-4, 15 epochs | too quiet — delta < 5%, no signal |
| lr=1e-4, 50 epochs | right scale — concepts activating, cross-contamination visible |
| v3 dataset (3-layer) | concept anchors building, leaking into unrelated prompts |
| v4 + surface LoRA | surface LoRA confirmed: "A X is" structure now appears even on unseen prompts |
| v4 + contrastive pairs | water concepts separated; routing still unresolved |

**Core finding:**
The HebbianLoRA on the shared encoder is a **global bias**, not local selection.
All six layers share one encoder — any delta shifts the whole representation space.
Concepts activate but cannot be routed independently from the prompt context.

The surface LoRA (lm_head) **works**: it shapes output structure without touching latent space.
Outputs now start with definition form even on prompts never seen in training.

**What the model needs next:**
Not more LoRA iterations. The model is not learning language anymore — it's learning a world model.
56 examples cannot build the concept separation needed for reliable routing.
The OS infrastructure (Dream queue, run logging, provenance tracking) is what makes
systematic training *possible*. Build the OS first; return to training with the full system in place.

### Next: build the OS
Continue from design doc §3–§9:
- LoRA index (loras/index.json) with centroid vectors and metadata
- Classification logic: latent similarity → LoRA selection
- Dream queue: flag gaps, store candidates for offline training
- chat.py: interactive interface over the live loop

Build the system described in the design doc. Update this file as the project evolves.
