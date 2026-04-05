# BDH Cognitive OS — System Design Document

---

## 1. Overview

The **BDH Cognitive OS** is a modular, layered AI system built around:

- a **clean core model (BDH)** for language and reasoning
- **Skill LoRAs** for specialized capabilities
- a **two-phase execution loop** (specialist → clean integration)
- an **offline Dream system** for controlled learning

The system explicitly separates:

| Layer | Responsibility |
|------|----------------|
| Core BDH | Language, reasoning, orchestration |
| Skill LoRAs | Specialized task execution |
| External Memory | Knowledge and artifacts |
| Dream System | Controlled consolidation |

---

## 2. Core Principle

> The system does not accumulate knowledge blindly.  
> It **delegates, records, reflects, and selectively consolidates**.

---

## 3. Execution Model

### 3.1 Live Loop (Synchronous)

Always runs. Deterministic. No training allowed.

### Step 1 — Intake

- Receive:
  - user prompt
  - scheduled task
  - heartbeat event
- Classify:
  - task type
  - complexity
  - required specialization

### Step 2 — Selection

- Query LoRA index
- Decide:
  - core-only
  - or core + Skill_LoRA
- Snapshot session state

### Step 3 — Specialist Run

- Load:
  - core model
  - selected Skill_LoRA(s)
- Execute task
- Produce artifact

### Step 4 — Artifact Record

Save to disk:

- prompt
- inputs
- files used
- LoRAs active
- output
- metadata:
  - timestamp
  - confidence
  - gaps flagged

### Step 5 — Clean Handoff

- Unload LoRA(s)
- Reload clean core
- Restore session snapshot
- Load artifact

### Step 6 — Output

- Clean core:
  - interprets artifact
  - generates final response
- Flag unresolved gaps → Dream Queue

---

## 4. Dream System (Asynchronous)

Never runs in live loop.

### Step 7 — Queue Candidate

- Store:
  - artifact
  - session
  - metadata

### Step 8 — Dream Step

Triggered manually or scheduled.

Process:

1. Analyze repeated patterns
2. Extract reusable knowledge/skills
3. Propose Dream_LoRA

Requires:
- human approval
- evaluation

---

## 5. Architecture Layers

### 5.1 Core BDH

Responsibilities:
- language understanding
- reasoning
- orchestration
- epistemic behavior ("I don't know")

Constraints:
- never modified during live loop
- only updated via controlled training

### 5.2 Skill LoRAs

Purpose:
- perform specialized tasks

Examples:
- Japanese grammar
- MRU writing analysis
- structured reasoning

Properties:
- modular
- versioned
- attached temporarily
- no persistence after run

### 5.3 Dream LoRAs

Purpose:
- consolidate repeated patterns
- improve system capability

Properties:
- created offline
- require approval
- may be promoted to Skill LoRA

### 5.4 External Memory

Stores:
- documents
- artifacts
- structured knowledge

NOT:
- embedded directly into core weights

---

## 6. LoRA Design

### 6.1 Hebbian LoRA (BDH-specific)

Instead of standard transformer LoRA, modify:

- `encoder`
- `encoder_v`

Example:

    class HebbianLoRA(nn.Module):
        def __init__(self, base_encoder, rank=8):
            nh, D, N = base_encoder.shape

            self.lora_A = nn.Parameter(torch.randn(nh, D, rank) * 0.02)
            self.lora_B = nn.Parameter(torch.randn(nh, rank, N) * 0.02)
            self.scaling = 1.0 / rank

        def forward(self, base_encoder):
            encoder_delta = (self.lora_A @ self.lora_B) * self.scaling
            return base_encoder + encoder_delta

Effect:

- modifies perception
- reshapes latent space
- activates specialized pathways

### 6.2 LoRA Types

| Type | Scope | Risk |
|------|------|------|
| Surface LoRA | output/style | low |
| Deep LoRA | encoder/latent | high |

Constraint:

> Only ONE deep LoRA active at a time.

---

## 7. Classification Logic

### 7.1 Zero-Shot Latent Classification

1. Run prompt through clean core
2. Extract latent activation (`x_sparse`)
3. Compare with LoRA centroids

Decision:

- similarity > 0.85 → attach LoRA
- otherwise → core only

### 7.2 LoRA Index

Stored in `loras/index.json`.

Contains:
- centroid vectors
- metadata
- compatibility info

---

## 8. File System Structure

    bdh_os/
      core/
      loras/
        skills/
        dreams/
        index.json
      sessions/
      runs/
      dream_queue/
      knowledge/
      workflow/
      inference.py
      harness.py
      chat.py

---

## 9. Run Artifact Structure

    runs/<timestamp>/
      request.json
      session_snapshot.json
      selected_lora.json
      specialist_output.md
      final_output.md
      metadata.json
      logs.txt

---

## 10. System Constraints

### MUST NOT

- modify core weights during live loop
- train LoRAs during active session
- auto-promote Dream LoRAs
- create hidden state outside session logs
- use multiple deep LoRAs simultaneously

### MUST

- save all runs to disk
- keep core clean between runs
- track LoRA provenance
- maintain reproducibility

---

## 11. Learning Model

### Wake Phase

- execute tasks
- log results
- identify gaps

### Sleep Phase

- analyze logs
- extract patterns
- propose improvements

### Key Principle

> Learning is **curated**, not automatic.

---

## 12. First Implementation Milestone

Build a minimal vertical slice:

- load core model
- attach dummy Skill_LoRA
- run task
- save artifact
- unload LoRA
- reload core
- produce final output

No Dream system yet.

---

## 13. Definition of Done

System can:

- run full live loop
- produce run artifacts
- switch between core and LoRA cleanly
- generate final output from clean core

---

## 14. Future Extensions

- multi-LoRA composition (controlled)
- structured knowledge retrieval
- automated Dream proposal scoring
- adaptive routing improvement

---

## Final Note

This system is not:

> a single model that learns everything

It is:

> a structured intelligence system that manages knowledge, skills, and learning explicitly

