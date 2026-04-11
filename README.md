# BDH Cognitive OS

A modular cognitive operating system built around the **Baby Dragon Hatchling (BDH)** architecture.

This project explores a different approach to intelligence:

- a **clean core model** for reasoning
- **modular skill adapters (LoRAs)** for specialization
- **explicit memory and artifact tracking**
- a **two-phase execution loop** (specialist → clean integration)
- controlled learning via a future "Dream" system

---

## Current Status

🚧 Early development

Milestone 1 in progress:
> Minimal vertical slice of the execution loop

---

## Repository Structure

```text
core/                        # trained BDH model (read-only)
bdh.py                       # BDH architecture (read-only)
bdh_cognitive_os_design.md   # system design
start_here.md                # evolving spec
AGENTS.md                    # implementation contract for coding agents
harness.py                   # top-level orchestration entry point
inference.py                 # BDH loading and generation wrapper
```

---

## Design Overview

The system operates in two phases:

### 1. Specialist Phase
- optionally attach Skill LoRA
- perform task
- produce artifact

### 2. Clean Core Phase
- unload LoRA
- reload clean model
- interpret artifact
- produce final output

This ensures:
- stable core identity
- modular specialization
- reproducible behavior

---

## Attribution

BDH architecture and core model (`bdh.py`) by Pathway Technology, Inc.

- Paper: https://arxiv.org/abs/2509.26507
- Repository: https://github.com/pathwaycom/bdh

---

## License

- BDH core: original repository license
- BDH Cognitive OS harness: MIT License  
  © Andi Omukai (aomukai.com)

---

## Philosophy

This project is not about scaling models.

It is about building systems that:

- **know when they don’t know**
- **delegate instead of memorizing**
- **learn selectively, not blindly**

---

## Next Steps

- implement minimal execution loop
- add run artifact system
- introduce Skill LoRA attachment
- design Dream system (offline learning)
