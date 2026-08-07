# Model Observatory contract

The Lab's Model Observatory is a read-only projection of Mission Hub evidence. It does
not create a second campaign registry, infer missing measurements, or use training loss
to rank checkpoints.

## Views

Every interactive view is generated in the browser from one immutable
`evaluation_report` artifact:

- **MRI** shows candidate-versus-parent activation density, magnitude, layer health,
  and captured high-scoring co-firing dimensions.
- **Atlas** shows concept and probe geometry at ingress, core, and intentions stages,
  with the behavioral prompt and response evidence beside it.
- **3D map** shows the core representation points as a rotatable diagnostic map.

These are activation-geometry diagnostics. They do not prove semantic neuron identity
or consciousness, and they do not replace the behavioral chat evaluation.

## Campaign-completion scan

Every training block must still finish with its required behavioral chat and MRI
evaluation. The evaluation of the terminal block sets `branch_complete=true`.

For a campaign with declared branches, the campaign-completion scan is complete only
when every declared branch has terminal chat-and-MRI evidence. The Observatory then
exposes the terminal MRI, Atlas, and 3D map for every branch together. It never selects
a winner automatically.

Historical evidence may satisfy a declared historical branch only when its imported
artifact explicitly identifies itself as historical evidence. If the detailed scan is
missing, the Observatory labels it as a historical summary and disables the visualizer
links instead of reconstructing data.

This reuses the terminal evaluation that the workflow is already required to run. It
does not launch a duplicate GPU pass after the same checkpoint has just been scanned.
If a future campaign needs a wider probe battery, that battery belongs in the declared
evaluation suite before authorization; the resulting terminal evaluation remains the
campaign scan.

## Statistics

The page derives its statistics from authoritative ledgers:

- things taught: distinct concept keys appended to `knowledge_records` for the campaign;
- lesson records: all append-only knowledge records, including branch repetitions;
- training blocks and evaluations: succeeded jobs of the corresponding types;
- attempts and retries: recorded runs and their attempt numbers;
- model routing: attempts recorded inside immutable `provider_transcript` artifacts.

A route is marked **Review primary** only after at least three routed jobs and a fallback
use rate of 50% or more. This is an operational prompt to inspect the configured primary,
not an automatic model switch. Deterministic jobs are never counted as model fallbacks.

Loss may be displayed elsewhere as telemetry, but it is not an Observatory evaluation,
success criterion, ranking input, admission gate, rollback trigger, or routing-health
statistic.
