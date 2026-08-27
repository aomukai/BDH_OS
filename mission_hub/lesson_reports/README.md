# Canonical lesson outcome reports

This is the durable, grep-friendly history used for later lesson planning. Rehearsal run
directories retain raw actor reports and logs; this library contains only independently reviewed
canonical outcomes.

Layout:

```text
mission_hub/lesson_reports/
  L001/
    <run-id>/
      luna-report.json
      sol-verdict.json
      canonical-report.json
  index.jsonl
  index.md
```

`canonical-report.json` declares `report_authority` as either `luna_verified` or
`sol_reconstructed`. In the first mode, Sol found Luna's report calibrated against the raw log. In
the second, Sol rebuilt the outcome because Luna's report was materially incomplete or wrong.
Both modes retain bindings to the original Luna report, event log, lesson, and Sol verdict.

Only a canonical report may inform a later lesson commission. Rehearsal reports never advance real
learner state. Live reports propose learner-state changes, but those changes still require the
independent verdict and the normal state-update gate.

Run `scripts/index_lesson_reports.py` after adding or superseding a canonical report. The generated
JSONL and Markdown indices include lesson ID, Point, Topic, tested items, capabilities,
difficulties, failure tags, and review recommendations so ordinary `rg` searches are sufficient.

