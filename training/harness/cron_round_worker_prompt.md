# Cron Round Worker Prompt (Template)

Use this as the canonical task instruction for an hourly cron round once training is enabled.

---

You are executing exactly one bounded BDH training-harness round.

Read these files first:

- `training/README.md`
- `training/harness/ROUND_STATE.json`
- `training/harness/intervention_registry.md`
- `training/harness/decision_policy.md`
- `training/harness/verifier_policy.md`
- `training/harness/emergency_exit_policy.md`
- `training/harness/claude_worker_contract.md`
- `training/harness/artifact_schemas.md`
- `training/harness/metrics.template.json`
- `training/harness/decision.template.json`
- `training/harness/claude_report.template.json`

Then:

1. Determine the next round id from `ROUND_STATE.json` using the canonical structured scheme: global round + intervention code + local attempt + cluster code.
2. Determine the currently selected intervention or propose the best next intervention using the decision policy.
3. Read the matching skill in `training/teacher_skills/`.
4. Execute exactly one bounded round.
5. Verify any teacher-generated student-facing text before accepting it.
6. Write artifacts into `training/rounds/<round_id>/`.
7. Update the append-only logs in `training/logs/`.
8. Update `training/harness/ROUND_STATE.json` for the next round.
9. Stop.

When relevant, also use:

- `training/harness/verifier_report.template.json`
- `training/harness/draft_data_request.template.json`

Constraints:

- If `training_enabled` is false, do not train. You may still perform dry-run planning, reporting, or scaffold generation if the task explicitly allows it.
- Do not silently skip missing prerequisites.
- Do not request more data unless the emergency-exit policy is satisfied.
- Do not create hidden state outside the documented training directory.

Your output artifacts must make it easy for Hermes to decide what to do next.
