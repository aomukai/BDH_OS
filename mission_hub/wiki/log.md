<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-log","page_type":"operation_log","status":"active","updated":"2026-08-13","source_ids":["src-training-modes-v1","src-current-intervention-catalogue-v1","src-historical-intervention-registry-20260806","src-historical-decision-policy-20260806","src-historical-training-harness-design-20260515"]} -->
# Research wiki operation log

This file is append-only. Every librarian ingest, retained query, lint pass, and
campaign transition adds a dated entry identifying its inputs and affected pages.

## [2026-08-13] bootstrap | Research wiki structure

- Actor: Codex, under operator direction
- Added the source registry, librarian contract, Sol planning checklist, page schema,
  initial catalogues, and structural linter.
- Historical sources are registered but not yet ingested.

## [2026-08-13] design | Triggered librarian lifecycle

- Actor: Codex, under operator direction
- Replaced the provisional periodic-scan idea with a campaign-transition trigger.
- The planned handoff contains both prior-campaign closure evidence and Sol's next
  campaign decision, allowing Luna to reconcile answered questions and record the
  new mission in one bounded update.

## [2026-08-13] design | Epistemic question dispositions

- Actor: Codex, under operator direction
- Added campaign goals/findings contracts and separate Luna and Sol runbooks.
- Made abstention, missing evidence, invalid questions, and no-campaign outcomes
  first-class valid results.
- Positive, negative, and conflicting-evidence answers require artifact citations
  and an explicit applicability boundary.

## [2026-08-13] ingest | Historical intervention taxonomy

- Actor: Codex, under operator direction, performing the initial librarian ingest.
- Registered the historical intervention registry, decision policy, and richer BDH
  training-harness design after locating them outside the original documentation
  surfaces.
- Salvaged the enduring intervention families into `methods.md` and bounded obsolete
  orchestrator, timing, filesystem, and recipe details as historical proposals.
- Reinterpreted `train_longer` as exposure depth through complete varied instructional
  cycles, and corpus growth as bounded curriculum breadth with complete cycles and
  prerequisite-work checks.
- Added branch/specialize, sandbox merge, and bounded post-merge healing to the
  maintained taxonomy without treating historical merge recipes as commissioned.
