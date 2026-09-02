# Ninereeds research memory

This directory governs the research wiki in `mission_hub/wiki/`. It is not a
second operational ledger and it is not a place for informal notes.

Authority is deliberately separated:

1. Mission Hub SQLite records are authoritative for campaigns, jobs, runs,
   artifacts, deployments, events, and operating state.
2. Bytes identified in `sources.json` are evidentiary truth. Repository sources
   must be present in every checkout; `operator_local` sources may live in the
   excluded training library but are still verified whenever those bytes are
   available. A registered hash identifies the exact source version Luna read.
3. `mission_hub/wiki/` is Luna-maintained synthesis. It may interpret registered
   sources, but a wiki page may never be cited as evidence for another wiki claim.
4. Sol reads the current wiki to plan research, but must complete every blocking
   item in `sol-planning-checklist.json` with evidence before proposing a campaign.

## Lifecycle

- **Register:** identify a source by repository-relative path and SHA-256, or by
  an immutable Mission Hub artifact identity.
- **Ingest:** Luna reads registered sources, reconciles their claims with the
  existing synthesis, updates every affected page and the index, then appends one
  operation record to the wiki log.
- **Maintain:** a triggered source sweep inventories `docs/` and `handoff/`, queues
  deliberate intake, and rechecks claims whose registered source hash changed. A
  sweep is not permission to ingest every file or infer current state from it.
- **Query:** an agent begins at the index, reads only relevant pages, and traces
  material claims to registered sources.
- **Lint:** validate source hashes, page metadata, citations, links, stale or
  contradictory claims, and missing research questions.
- **Campaign closure:** Luna receives the exact artifact manifest and writes one
  evidence-index page named `campaign_NNNN_findings.md`. Luna records observations,
  missing evidence, and operational anomalies, but does not answer the campaign's
  research questions.
- **Campaign planning:** Sol reads `campaign_NNNN_goals.md` and
  `campaign_NNNN_findings.md`, gives every old question one epistemic and lifecycle
  disposition, then designs the successor. A completed planning job triggers Luna
  to file Sol's decision as `campaign_MMMM_goals.md` and update the wiki indexes.
- **Prerequisite work:** when no scientifically useful campaign can yet be specified,
  Sol emits a bounded preparation request. Luna catalogues it without commissioning
  it. Once its acceptance evidence exists, Sol replans; completion never silently
  authorizes a campaign.

The canonical wiki still does not schedule a cron scan. Its full refinery is invoked
by an explicit pipeline transition or a manual librarian request. The autonomous Lab
does have one deliberately narrower integration: Mission Hub deterministically renders
a grep-friendly runtime campaign journal from durable experiment rows, and a separate
low-priority Luna job may add search keywords plus one evidence-bound sentence for one
terminal experiment. That runtime note is not canonical wiki synthesis, has no
experimental authority, never blocks Sol, and is promoted to the source-controlled wiki
only through the ordinary campaign-closure librarian process.

The permanent representation rule is: **human docs explain why; machine contracts
say what**. Wiki pages preserve rationale, evidence boundaries, examples, and open
questions. Structured contracts use compact IDs, states, actions, invariants, and
validation rules with references back to that explanation. Compact never means
ambiguous: units, scope, provenance, and operational semantics remain mandatory.

Campaign goals and findings are the only intentional per-campaign Markdown files.
They are frozen records, not overlapping current summaries. The current synthesis
remains in the small catalogue pages under `mission_hub/wiki/`.

Only the librarian workflow writes research synthesis. Other agents may propose
changes, sources, questions, or contradictions, but those proposals enter through
the ingest workflow. Routine edits must not be scattered into additional Markdown
files elsewhere in the repository.

The initial registry contains historical sources useful for bootstrapping.
Registration does not endorse their claims. Ingestion must retain their historical
scope and record contradictions or supersession explicitly.

## Prepared contracts

- `luna-librarian-runbook.md` defines the evidence-only closure and filing jobs.
- `information-maintenance-contract.json` defines the inventory-to-wiki information
  refinery and its anti-sprawl, freshness, and authority rules.
- `intake/source-census.json` is the reproducible discovery surface;
  `intake/source-triage.json` assigns every candidate to one bounded review batch.
- `sol-research-runbook.md` defines question review and campaign planning.
- `question-dispositions.json` defines the multiple-choice epistemic and lifecycle
  answers.
- `campaign-design-catalogue.json` separates research purpose from execution design.
- `intervention-catalogue.json` maps diagnosed learning conditions to bounded modern
  intervention families, including PPP-aware exposure and curriculum growth.
- `evaluation-methodology.json` adapts BDH-CQ's controlled behavioral analysis into
  a planning contract for boundary ladders, strict consistency, matched support,
  composition, contamination controls, effort, and failure structure.
- `teaching-methodology.json` separates teaching doctrine, lesson phases,
  scaffolding, failure diagnosis, runtime ownership, and future research proposals.
- `visual-material-tool.json` defines Sol's executable registry-first retrieval stage
  and the separately authorized acquisition/edit/generation boundary;
  `../skills/select-images-for-curriculum/SKILL.md` provides the executable completion loop.
- `sol-planning-procedure.json` is the ordered “read these, fill these forms, decide”
  assignment; `mission_hub.research_brief` compiles its exact bounded context packet.
- `permanent-campaign-questions.json` defines the questions considered for every
  campaign without forcing invented answers to inapplicable ones.
- `schemas/` contains machine-checkable goals, findings, question-review, and atomic
  source-claim shapes.
- `schemas/teacher-handoff.schema.json` prepares the bounded script-to-teacher return
  contract without integrating or selecting a teacher implementation.
- `schemas/sol-planning-decision.schema.json` makes one decision object authoritative
  for both Luna filing and the Lab's human-readable projection.
- `schemas/prerequisite-work.schema.json` defines material, evaluation, tooling, and
  infrastructure preparation requests, including unresolved dependencies and frozen
  source-selection requirements.
- `templates/` shows the two frozen Markdown projections created per campaign.
- `examples/` is illustrative only and must never be ingested as campaign evidence.

```bash
python3 -m mission_hub.research.source_inventory \
  --output mission_hub/research/intake/source-census.json
python3 -m mission_hub.research_brief --live-state LIVE_STATE.json \
  --prior-goals campaign_NNNN_goals.md --prior-findings campaign_NNNN_findings.md \
  --output /tmp/sol-planning-brief.json
python3 -m mission_hub.research_wiki lint
```
