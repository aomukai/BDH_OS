<!-- ninereeds-wiki: {"schema_version":"ninereeds_research_wiki_page_v1","page_id":"wiki-tools","page_type":"tool_catalogue","status":"active","updated":"2026-08-25","source_ids":["src-visual-material-tool-v1","src-foundation-corpus-expansion-v1","src-foundation-corpus-expansion-auditor-v1","src-sol-planning-procedure-v1"]} -->
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

## Foundation corpus expansion

Status: reusable contract and deterministic audit CLI implemented; acquisition and
generation remain separately authorized work.

Use this route when an established visual foundation set needs new prerequisite words
or sense-specific contracts. The maintained contract records the complete procedure:

```text
identify direct missing prerequisites and select one sense per contract
→ search the local reviewed pool
→ search metadata, then download bounded candidates
→ review visible pixels with Luna
→ generate only deficits through the bounded Flux → ImageGen ladder
→ reconcile exactly ten images per contract
→ add claim-driven and conservative obvious-component edges
→ topologically fold the curriculum
→ recheck newly introduced labels
→ independently verify every manifest and file
```

The important boundaries are fail-closed:

- a contract has one intended meaning before images are admitted;
- noun countability and articles are never inferred mechanically;
- direct compound dependencies such as `back → backpack` count, while loose
  derivations such as `locate → location` do not count by default;
- exact image reuse is allowed only when every placement fits, with a maximum of four
  uses in the folded curriculum;
- Luna admission and target verdicts decide usability; a stylistic quality note alone
  does not silently override an otherwise usable decision;
- explicit operator overrides preserve the original review, reason, actor, and hash;
- training-ready requires exact image counts, complete files, matching SHA-256 values,
  unique labels and slots, and dependency-respecting order.

Run the acquisition gate after merging the accepted local, metadata, and generated
ledgers:

```bash
python3 -m image_registry.foundation_corpus_expansion audit-acquisition \
  --contracts COMMISSION_CONTRACTS.jsonl \
  --ledger LOCAL_SELECTED.jsonl \
  --ledger METADATA_SELECTED.jsonl \
  --ledger GENERATED_ACCEPTED.jsonl \
  --images-per-contract 10 \
  --max-image-reuse 4 \
  --output ACQUISITION_AUDIT.json
```

Run the independent final gate after the topological fold:

```bash
python3 -m image_registry.foundation_corpus_expansion audit-curriculum \
  --curriculum FOLDED_CURRICULUM_DIRECTORY \
  --images-per-contract 10 \
  --max-image-reuse 4 \
  --output FINAL_AUDIT.json
```

Both commands exit with status 2 when an invariant fails. The curriculum audit
re-hashes every distinct file and also checks that each contract's and asset's
serialized `depends_on` list exactly matches the edge graph.

Campaign 36's reference completion is `expanded-curriculum-v3`: 3,022 contracts,
30,220 images, 1,163 dependency edges, no missing files or hash mismatches, no order
violations, and maximum exact-image reuse of four.

Canonical specification: `mission_hub/research/foundation-corpus-expansion.json`.

Executable implementation: `image_registry/foundation_corpus_expansion.py`.

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
