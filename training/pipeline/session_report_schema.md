# MSM Session Report Schema

The executor fills these artifacts after every session. The orchestrator reads the JSON.

Machine-readable schema: `training/pipeline/session_report_schema.json`.
Training-turn record schema: `training/pipeline/training_turn_schema.json`.
Script/raw-log schemas: `training/pipeline/script_and_raw_log_schema.md`.

---

## `report_card.json`

Required top-level fields:

```json
{
  "schema_version": "msm_session_report_v1",
  "session_id": "string",
  "concept": "string",
  "card_id": "string",
  "checkpoint_before": "string",
  "checkpoint_after": "string|null",
  "session_mode": "scripted_trainer_session|probe_session|repair_replay_session|contrast_session|protected_anchor_session",
  "script": {
    "script_id": "string",
    "script_author": "string",
    "script_mode": "fixed",
    "orchestrator_plan_id": "string",
    "intended_stage": "string",
    "intended_failure_targets": ["string"],
    "executor_context": {
      "executor_id": "local:gemma-4-26b-a4b",
      "selection_method": "fixed",
      "meta_scratchpad_injected": false,
      "meta_scratchpad_path": null
    },
    "script_fingerprint": {
      "algorithm": "msm_script_fingerprint_v1",
      "structural_hash": "sha256...",
      "prompt_hash": "sha256...",
      "question_type_sequence": ["yes_no"],
      "contrast_pairs": [["cat", "dog"]]
    }
  },
  "counts": {
    "script_items": 0,
    "ninereeds_original_answers": 0,
    "ninereeds_after_correction_answers": 0,
    "original_correct": 0,
    "original_wrong_on_topic": 0,
    "original_wrong_off_topic": 0,
    "after_correction_correct": 0,
    "after_correction_wrong_on_topic": 0,
    "after_correction_wrong_off_topic": 0,
    "malformed": 0,
    "repetition_collapse": 0,
    "empty_or_near_empty": 0
  },
  "scores": {
    "original_correct_rate": 0.0,
    "after_correction_correct_rate": 0.0,
    "on_topic_rate": 0.0,
    "malformed_rate": 0.0,
    "session_passed": false,
    "executor_may_auto_advance": false,
    "requires_orchestrator": true
  },
  "failure_modes": [],
  "successful_axes": [],
  "weak_axes": [],
  "protected_anchor_status": {
    "tested": false,
    "passed": null,
    "failures": []
  },
  "recommended_extraction": {
    "proposed_training_turns": 0,
    "rejected_turns": 0,
    "extraction_file": "proposed_training.jsonl|null",
    "do_not_train_raw_log": true
  },
  "executor_recommendation": {
    "recommendation_type": "accept|continue_same_word|continue_next_word|repair_replay|probe|brain_scan|micro_update|escalate|reject",
    "suggested_next_session_mode": "string|null",
    "suggested_focus": [],
    "requires_orchestrator_decision": true,
    "requires_human_attention": false
  },
  "artifacts": {
    "raw_log": "raw_chat.jsonl",
    "script": "script.json",
    "report_md": "report.md",
    "turn_grades": "turn_grades.jsonl",
    "proposed_training": "proposed_training.jsonl|null",
    "failed_turns": "failed_turns.jsonl"
  }
}
```

`card_id` and `concept` may be identical for simple cards. They should diverge when one
concept has multiple staged cards, such as `cat_boundary_l1` for concept `cat` or
`potato_food_l1` for concept `potato`. Multi-cluster concepts should report the specific
cluster card being taught, not only the base concept.

`requires_orchestrator_decision` may be `false` only when the active campaign policy allows
the executor to auto-advance and no escalation condition fired.

The `script.executor_context` fields are required so later analysis can distinguish clean
runs from scratchpad-assisted runs. In v1, `selection_method` is always `fixed`.

The `script.script_fingerprint` fields are required for deterministic duplicate detection.
Do not use embedding similarity for v1 MSM de-duplication unless the orchestrator records a
separate experiment.

---

## Failure Mode Object

```json
{
  "type": "same_category_confusion",
  "severity": "low|medium|high|critical",
  "item_ids": ["i006"],
  "example": "A cat is a dog.",
  "interpretation": "Cat and dog share animal category, but identity boundary failed."
}
```

Common failure types:

- `missing_anchor`
- `wrong_attractor`
- `same_category_confusion`
- `cross_category_confusion`
- `unknown_boundary_failure`
- `identity_failure`
- `topic_drift`
- `malformed_language`
- `repetition_collapse`
- `empty_output`
- `script_deviation`

---

## `turn_grades.jsonl`

One object per scripted item:

```json
{
  "item_id": "i006",
  "user_prompt": "Is a cat a dog?",
  "ninereeds_original_answer": "A cat is an animal. A dog is an animal. A cat is a dog.",
  "teacher_correction": "A cat is not a dog.",
  "ninereeds_after_correction_answer": "A cat is not a dog.",
  "original_answer_status": "wrong_on_topic",
  "after_correction_status": "correct",
  "malformed": false,
  "failure_modes": ["same_category_confusion"],
  "required_hits": ["cat", "dog"],
  "required_misses": ["not a dog"],
  "forbidden_hits": ["cat is a dog"],
  "eligible_for_training": true,
  "suggested_correction": "A cat is not a dog."
}
```

Allowed answer statuses:

- `correct`
- `wrong_on_topic`
- `wrong_off_topic`
- `ungradable`
- `not_applicable` for `after_correction_status` only

---

## `proposed_training.jsonl`

The executor writes grading-validated proposed turns here. These are not approved for
weight updates until the orchestrator copies accepted records into an update buffer as
`approved_training.jsonl`.

```json
{
  "schema_version": "msm_training_turn_v1",
  "session_id": "string",
  "concept": "cat",
  "card_id": "cat_boundary_l1",
  "turn_id": "i006_repair",
  "prompt": "[user]Is a cat a dog?\n[Ninereeds]",
  "training_answer": "A cat is not a dog.",
  "source": "executor_proposed_correction",
  "target_failure": "same_category_confusion",
  "executor_validated": true,
  "orchestrator_approved": false
}
```

Wrong Ninereeds answers must not appear in this file.
