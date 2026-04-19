# Rounds

Each round gets its own folder named by the canonical round id, for example:

- `R001-TR-A01-WATER/`
- `R002-DR-A01-SOCROLE/`

Where:

- `R001` = global round 1
- `TR` / `DR` = intervention code (`train_longer`, `teacher_student_drill`, etc.)
- `A01` = local attempt number for the current intervention on the current cluster
- `WATER` / `SOCROLE` = target cluster code

Each round folder should usually contain:

- `plan.md`
- `summary.md`
- `metrics.json`
- `decision.json`
- `claude_report.json`

These JSON files should follow the canonical shapes defined in:

- `training/harness/artifact_schemas.md`
- the corresponding `*.template.json` files in `training/harness/`

Additional files may be added as needed, but every file should help explain what happened in that round.
