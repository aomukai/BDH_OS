<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-tools","page_type":"tool_catalogue","status":"active","updated":"2026-08-13","source_ids":["src-visual-material-tool-v1","src-sol-planning-procedure-v1"]} -->
# Tools

## Visual material retrieval and request

Status: implemented as a direct CLI; not integrated into automatic campaign planning.

Sol can submit a structured visual-material request to the reviewed image registry.
The tool searches ordered exact, semantic-equivalent, and alternate-realization tiers,
excludes protected selections, and freezes successful candidates as an immutable
registry selection plus a hash-bearing manifest.

Only `reviewed_usable` assets are eligible. Metadata-only search may help assess
coverage, but it cannot place pending material into a lesson.

When reviewed material is insufficient, the same operation emits a residual-gap
request containing the missing quantity, teaching claim, existing reference assets,
fallback order, and acceptance criteria. Sol may turn that into prerequisite work.
Actual acquisition, Flux editing, or Flux generation requires a separately authorized
workflow, and every new asset must pass registry review before use.

This makes the old `request_more_data` intervention concrete:

```text
state exact teaching need
→ search reviewed registry
→ accept equivalent realizations that preserve the claim
→ freeze existing candidates
→ quantify the residual gap
→ commission only that gap
→ review and register new assets
→ rerun retrieval
```

Canonical contract: `mission_hub/research/visual-material-tool.json`.

## Sol planning briefing

Status: briefing compiler and decision contract implemented; pipeline and Lab rendering
not yet integrated.

The compiler turns the maintained research memory into one bounded ordered reading
packet. It includes exact content and hashes for the overview, predecessor contract and
findings, question/campaign synthesis, methods, teaching, materials, tools, choice
catalogues, checklist, and runbook. An authoritative Mission Hub live-state snapshot is
required for a planning-ready packet. Sol follows deep evidence links only when a form
or contradiction requires them.

Sol then completes question-review choices and checklist dispositions before selecting
`no_campaign`, `prerequisite_work`, or `campaign_proposal`. One validated decision
object contains both:

- Luna's artifact-oriented filing handoff; and
- the compact headline, reasons, known unknowns, next step, and evidence links shown by
  the Lab.

The Lab view is therefore a projection, not a competing narrative record.

Canonical procedure: `mission_hub/research/sol-planning-procedure.json`.
