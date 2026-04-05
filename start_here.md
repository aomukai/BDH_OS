I'm building a cognitive OS for a small language model called BDH. Read bdh_cognitive_os_design.md for the full spec and bdh.py for the model architecture. The trained model is at core/bdh_100m_final.pt. Do not modify bdh.py — treat it as a read-only dependency.

## Status

### Milestone 1 — complete
- inference.py: loads checkpoint, byte-level tokenisation, seeded generation
- harness.py: full live loop — classify → shape → specialist → reload → final output → save artifacts
- prompt_shaper.py: routes user input to completion-friendly shapes (definition, qa, story, passthrough, fill)
- eval.py: comparative eval with scoring (printable ratio, word ratio, repetition, sentence formation) and failure mode detection
- Locked generation settings: temperature=0.8, top_k=None

### Milestone 2 — in progress: QA behavior micro LoRA
Goal: teach the model a structural habit — when given a Q:/A: or definition prompt, start the completion directly (noun/article first, no narrative drift).

What we learned:
- HebbianLoRA (rank=8) on encoder + encoder_v — 2.09% of parameters, 540K trainable
- lr=1e-3 / 30 epochs: too loud — delta overwhelmed base (26% ratio), produced template attractor
- lr=1e-4 / 50 epochs: correct scale (delta ~8% of base), concept anchors activating
- v1 dataset (70 examples): near-identical structures collapsed into one template
- v2 dataset (50 examples): better concept diversity, definition structure emerged, Q/A subject grounding still weak
- v3 dataset (56 examples, current): three-layer structure — short anchor + bidirectional + expanded Q/A + subject repetition
  - Concept anchors now leaking into cross-prompt outputs (feathers, drops, bread, flows appearing in unrelated answers)
  - This is a step forward: the concepts are activating. Routing is the remaining problem.

Core finding: the shared encoder architecture means LoRA is a global dial, not a per-concept switch. Concepts activate together rather than routing independently from the prompt.

### Next decision point
Options:
1. Continue LoRA work — try surface LoRA on lm_head as a complement, or higher rank
2. Accept current LoRA state and build the OS layer that uses it — LoRA index, routing logic, Dream queue
3. Revisit training data with even stronger contrastive pressure

Build the system described in the design doc. Update this file as the project evolves — treat it as the living spec, not a static prompt.
