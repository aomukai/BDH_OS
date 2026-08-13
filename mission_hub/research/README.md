# Ninereeds research memory

This directory governs the research wiki in `mission_hub/wiki/`. It is not a
second operational ledger and it is not a place for informal notes.

Authority is deliberately separated:

1. Mission Hub SQLite records are authoritative for campaigns, jobs, runs,
   artifacts, deployments, events, and operating state.
2. Bytes identified in `sources.json` are evidentiary truth. A registered hash
   identifies the exact source version Luna read.
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
- **Query:** an agent begins at the index, reads only relevant pages, and traces
  material claims to registered sources.
- **Lint:** validate source hashes, page metadata, citations, links, stale or
  contradictory claims, and missing research questions.
- **Campaign transition:** Sol reads the last committed wiki plus the exact new
  closure evidence, completes the planning checklist, and selects a proposed next
  campaign. The completed planning job then triggers one Luna librarian handoff.
  Luna records what the prior campaign answered, what remains open, the new mission
  and goals, why Sol selected them, and which questions the new campaign is designed
  to answer.

The current design does not schedule a cron scan. Luna is invoked by an explicit
pipeline transition or a manual librarian request. Integration and scheduling remain
future work; these files currently preserve the intended contract only.

Only the librarian workflow writes research synthesis. Other agents may propose
changes, sources, questions, or contradictions, but those proposals enter through
the ingest workflow. Routine edits must not be scattered into additional Markdown
files elsewhere in the repository.

The initial registry contains historical sources useful for bootstrapping.
Registration does not endorse their claims. Ingestion must retain their historical
scope and record contradictions or supersession explicitly.

```bash
python3 -m mission_hub.research_wiki lint
```
