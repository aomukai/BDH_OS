# Mommy Says Machine — System Design Document

---

## 1. Purpose

The Mommy Says Machine is a **diagnostic and training data 
generation tool** for the BDH language model.

It is not a trainer.
It does not modify model weights.
It does not persist dragon state between runs.

Its purpose is to answer three questions:

1. What does the dragon currently know?
2. How does the dragon process correction?
3. Does correction hold within a session?

The output is a structured report and a set of validated
correction pairs for use in a subsequent clean training run.

---

## 2. Core Principle

> The dragon is tested, not trained.
> The checkpoint is always reloaded clean before each run.
> Learning happens offline, in a controlled training pass,
> not inside the machine.

---

## 3. System Components

| Component | Role |
|---|---|
| Dragon | Student. Local BDH model, frozen. Read-only. |
| Teacher | Nemotron 3 Super 120B via build.nvidia.com API |
| Hermes Agent | Orchestration. Manages the run loop. |
| Vocab Guard | Validates vocabulary in all exchanges. |
| Run Logger | Records all exchanges and grades. |
| Report Writer | Produces structured output at run end. |

---

## 4. Run Structure

### 4.1 Pass Types

Each run consists of up to three passes, executed in order.

#### Pass 1 — Baseline (always runs)

- Test every concept in the concept list once.
- Dragon answers. Teacher grades. No correction given.
- Purpose: establish ground truth for this checkpoint.
- Output: `baseline_grades.json`

#### Pass 2 — Correction (runs if Pass 1 has failures)

- Target only concepts that received FAIL or WEAK in Pass 1.
- For each failed concept:
  - Teacher asks question.
  - Dragon answers.
  - Teacher grades response.
  - If FAIL or WEAK: teacher issues correction
    (mommy says schema — see Section 6).
  - Dragon's response to correction is logged.
- Purpose: measure how the dragon processes correction.
- Output: `correction_exchanges.json`

#### Pass 3 — Retention (runs after Pass 2)

- Retest all concepts corrected in Pass 2.
- No correction given regardless of response.
- Purpose: measure within-session retention.
- Output: `retention_grades.json`

### 4.2 Control Sample

Every run includes a control sample:
- 20% of concepts that passed in the previous run
  are retested in Pass 1.
- Purpose: detect regression caused by any external change.
- Control concepts are selected randomly but logged,
  so the same concept is not always selected.

### 4.3 Run Sequence

Run 000 — full baseline, no prior history
Run 001 — targets Run 000 failures + control sample
Run 002 — targets Run 001 failures + control sample
Run N   — STOP (see Section 8: Shutdown Threshold)

After shutdown: human analysis before restart.

---

## 5. Grading Schema

Teacher grades each dragon response on three levels:

| Grade | Meaning |
|---|---|
| PASS | Correct concept, correct structure |
| WEAK | Correct concept, wrong or missing detail |
| FAIL | Wrong concept, incoherent, or no response |

### 5.1 Grading Instructions for Teacher

The teacher prompt includes:

Grade the following response to the question:
  Question: [prompt]
  Response: [dragon output]

Grade using exactly one of: PASS, WEAK, FAIL.

PASS: the response correctly identifies the concept
  and uses appropriate vocabulary.
WEAK: the response shows partial understanding
  but contains errors or omissions.
FAIL: the response does not correctly address
  the concept.

Known vocabulary for this concept: [vocab list]
Reply with only the grade on the first line,
then one sentence of reasoning.

---

## 6. Mommy Says Schema

When a response is graded FAIL or WEAK, the teacher
issues a correction.

### Rules

- No explanation.
- No praise.
- No "that is wrong" or "good try".
- Restate the correct form naturally.
- Maximum 2 sentences.
- All words must be in the known vocabulary list
  for the current concept.
- Use the same grammatical frame as the question
  where possible.

### Example

Question:   "where does a dog live?"
Dragon:     "dog is ground near house"
Correction: "A dog lives near a house.
             A dog stays on the ground."

### Teacher prompt for correction

Issue a correction in the mommy says style.
The learner said: [dragon output]
The correct answer is: [expected answer]
Known vocabulary: [vocab list]

Rules:
- No explanation. No praise. No judgment.
- Restate correctly and naturally.
- Maximum 2 sentences.
- Use only words from the known vocabulary list.

---

## 7. Vocabulary Guard

Every exchange is checked by the Vocab Guard before logging.

### What is checked

- Dragon response: any token not in the known vocabulary
  list is flagged as a vocab violation.
- Teacher correction: any token not in the known vocabulary
  list causes the correction to be REJECTED and regenerated
  (up to 3 attempts, then the exchange is logged as
  CORRECTION_FAILED).

### Known vocabulary source

The known vocabulary list is derived from:
- The wiki schema (wiki_schema_v2.yaml)
- Filtered to concepts confirmed present in the
  training corpus at the current checkpoint.

The vocab list is passed to the teacher at the start
of each run and attached to every teacher prompt.

---

## 8. Concept List and Ordering

Concepts are drawn from the wiki schema and ordered
by dependency:

1. Concepts with no sub_concepts and no cross-domain
   appearances first.
2. Parent concepts before their sub_concepts.
3. Multi-domain concepts last.

The concept list for each run is stored in
`run_NNN/concept_list.json` so runs are reproducible.

### Question generation

The teacher generates questions for each concept
using this instruction:

Generate a simple question about [concept].
The question must:
- Use only words from the known vocabulary list.
- Be answerable in 1-2 short sentences.
- Match one of these question types:
    "what is X?"
    "where does X live / go / stay?"
    "what does X do?"
    "is X a Y?"
    "tell me about X"
- Vary the type across concepts.
  Do not use the same type twice in a row.
Maximum question length: 10 words.

---

## 9. Logging

Every exchange is logged in full.

### Exchange record

```json
{
  "run": 1,
  "pass": "correction",
  "concept": "dog",
  "prompt": "where does a dog live?",
  "dragon_response": "dog is ground near house",
  "grade": "WEAK",
  "grade_reasoning": "correct habitat but missing verb structure",
  "correction": "A dog lives near a house. A dog stays on the ground.",
  "correction_vocab_check": "PASS",
  "dragon_response_to_correction": "dog lives near house on ground",
  "retention_grade": "WEAK",
  "timestamp": "2026-04-11T03:29:00Z",
  "vocab_violations": []
}
```

---

## 10. Run Output

Each run produces a directory:

runs/
  run_000/
    concept_list.json
    baseline_grades.json
    correction_exchanges.json
    retention_grades.json
    correction_pairs.jsonl
    vocab_violations.json
    summary.md

### correction_pairs.jsonl

Clean prompt/completion pairs derived from correction
exchanges where the correction passed vocab check.

Format:
```json
{"prompt": "where does a dog live?",
 "completion": "A dog lives near a house on the ground."}
```

The dragon's wrong answer is discarded.
Only the teacher's validated correction is used.

These pairs are candidates for the next clean
training run. They require human review before use.

### summary.md

Human-readable overview including:
- Total concepts tested
- Pass / Weak / Fail counts per pass
- Control sample results (regression check)
- Concepts still failing after correction pass
- Vocab violation count
- Recommendation: continue / stop / investigate

---

## 11. Shutdown Threshold

The machine stops automatically when any of these
conditions are met:

| Condition | Meaning |
|---|---|
| Run count reaches MAX_RUNS (default: 10) | Hard limit |
| Pass rate in baseline reaches 95% | Mastery threshold |
| Control sample regression > 10% | Possible damage |
| Correction pass produces 0 improvement over 3 runs | Plateau |
| CORRECTION_FAILED count > 5 in one run | Teacher malfunction |

On shutdown, the machine writes `SHUTDOWN_REASON.txt`
and exits cleanly.

Human analysis is required before the machine restarts.

---

## 12. File System Structure

mommy_says_machine/
  config.yaml           ← vocab list, concept list,
                           thresholds, API settings
  run_log.json          ← index of all runs
  runs/
    run_000/
    run_001/
    ...
  machine.py            ← main orchestration loop
  teacher.py            ← nemotron API wrapper +
                           prompt templates
  vocab_guard.py        ← vocabulary checker
  grader.py             ← grade parsing and validation
  report_writer.py      ← summary.md generator
  dragon_interface.py   ← local BDH inference wrapper

---

## 13. Config

```yaml
# config.yaml

dragon:
  checkpoint: "core/bdh_150m_current.pt"
  device: "cuda"
  max_new_tokens: 64
  temperature: 0.8
  top_k: 40

teacher:
  model: "nvidia/nemotron-3-super-120b-a12b"
  api_base: "https://integrate.api.nvidia.com/v1"
  max_tokens: 128
  temperature: 0.3

run:
  max_runs: 10
  mastery_threshold: 0.95
  regression_threshold: 0.10
  plateau_runs: 3
  control_sample_ratio: 0.20

vocab:
  source: "wiki_schema_v2.yaml"
  confirmed_phases: [1, 2, 3]

output:
  runs_dir: "runs/"
  log_file: "run_log.json"
```

---

## 14. Constraints

### MUST NOT
- Modify dragon weights during any run.
- Allow teacher corrections containing out-of-vocabulary words.
- Continue after shutdown threshold is reached.
- Reuse a stale dragon state between runs.

### MUST
- Reload dragon from checkpoint at the start of every run.
- Log every exchange in full, including failures.
- Run vocab check on every teacher correction before delivery.
- Write summary.md before exiting any run.
- Timestamp all log entries in UTC.

---

## 15. What This Does Not Do

This machine does not train the dragon.
It does not update weights.
It does not create LoRAs.
It does not decide what goes into the next training run.

It produces evidence.
A human reads the evidence.
A human decides what training to do next.

---

## 16. Future Extensions

- Automated dependency-ordered concept traversal
- Per-concept difficulty scoring based on run history
- Integration with anchor_probe.py for pre/post comparison
- Teacher model swap (codex, gemma, other local models)
- Parallel concept testing for faster baseline runs