# Operational Experience Ledger

Ninereeds keeps reusable orchestration experience in
`CONTROL_ROOT/experience.sqlite3`. This database complements the immutable control
ledger:

- the control ledger answers **what ran and what it reported**;
- the experience ledger answers **what was tried, whether it worked, and what guidance
  has earned reuse**.

Every strategic boundary searches the ledger using its current problem title and
instructions. It receives a bounded `operational_memory` digest containing:

- the closest matching problem records;
- compact success/failure counters for each exact ordered method;
- open outcome reversals;
- active and candidate lessons;
- only the recent attempts relevant to those matches.

If no problem matches, the child attempt creates a new problem record automatically. The
digest is capped so experience cannot consume the whole model context.

## Evidence Model

An attempt records:

- the problem and relevant context;
- an ordered list of method steps;
- the execution outcome;
- a separate effectiveness assessment;
- evidence references, notes, and tags.

Execution success deliberately does not imply that the method worked. For example, a
training command can finish successfully while its checkpoint exhibits concept bleed.
The orchestrator automatically reconciles pending attempts with terminal control reports,
but leaves effectiveness as `unknown` until evaluation evidence assesses it. A report may
set `result.effectiveness` to `working`, `not_working`, `mixed`, or `unknown`, or provide
an explicit boolean `result.working`. Only effectiveness assessments contribute to method
success rates.

Problem titles are normalized and close title variants can reuse one problem record. Each
distinct ordered step list becomes a method under that problem. Thus `A, B, C` and
`A, C, B` accumulate separate statistics without duplicating the problem.

When a method works after at least two consecutive failures, or fails after at least two
consecutive successes, the ledger opens a persistent anomaly. Strategic prompts are told
to investigate these reversals with a bounded experiment rather than silently discarding
the earlier rule.

A lesson records:

- conditions and scope;
- recommended and avoided steps;
- confidence and supporting attempt IDs;
- `candidate`, `active`, or `retired` status.

Candidate lessons are hypotheses. Promote a lesson to active only when the evidence is
strong enough to guide later decisions. This prevents a single lucky run from becoming a
false universal rule.

## Command-Line Use

Record an ordered attempt:

```bash
python3 -m training.pipeline.control.experience record \
  --problem "Concept bleed among A, B, and C" \
  --step "train A" \
  --step "train B" \
  --step "train C" \
  --outcome failed \
  --effectiveness not_working \
  --evidence training/logs/example-report.json \
  --tag concept_bleed
```

Assess a previously pending attempt:

```bash
python3 -m training.pipeline.control.experience assess ATTEMPT_ID \
  --outcome succeeded \
  --effectiveness working \
  --evidence training/logs/example-eval.json
```

Add a scoped lesson:

```bash
python3 -m training.pipeline.control.experience rule \
  --title "Separate the two nearest concepts" \
  --scope "concept family A/B/C" \
  --condition "A, B, and C share nearby representations" \
  --recommend "train A" \
  --recommend "train C" \
  --recommend "train B" \
  --avoid "train A, then B, then C" \
  --confidence 0.7 \
  --status candidate \
  --evidence-attempt ATTEMPT_ID
```

Promote a candidate after further evidence:

```bash
python3 -m training.pipeline.control.experience promote LESSON_ID \
  --confidence 0.9 \
  --evidence-attempt SECOND_ATTEMPT_ID
```

Inspect exactly what the orchestrator will see:

```bash
python3 -m training.pipeline.control.experience digest \
  --query "concept bleed among A, B, and C"
```

Search the compact problem/method index directly:

```bash
python3 -m training.pipeline.control.experience search \
  "concept bleed among A, B, and C" \
  --tag concept_bleed
```

After investigating a reversal, acknowledge its persistent alert:

```bash
python3 -m training.pipeline.control.experience acknowledge ANOMALY_ID
```

Pass `--control-root PATH` before the subcommand when using a non-default control root.
