# TODO

This file is the single active unfinished-work queue for the repository.

Rules:
- Add new unfinished work here.
- When a task is completed, remove it from this file and move it to `history.md`.
- Do not leave completed tasks or long status summaries here.
- Legacy planning and status docs belong in `archive/`.

## Active queue

[ ] Rebuild training_data/dependency_graph.json incrementally, variable batch size per run
    Executor prompt:
    Rebuild training_data/dependency_graph.json incrementally with variable batch sizes.
    On each run:

    Read training_data/dependency_graph_progress.txt to find out which files have already
    been processed. If the file does not exist, start from the beginning.

    Process files in this order:
    training_data/phases/ first, then training_data/wiki/, then
    training_data/triplet_stories/, then training_data/reasoning/

    Batch size rules:
    - training_data/phases/phase_4/ and training_data/phases/phase_5/: process 80 files per run
    - all other directories: process 20 files per run

    For phase files: identify the target word(s) introduced, extract all vocabulary used in
    [Ninereeds] response lines, record those as prerequisites for the target word.
    For wiki/stories/reasoning files: record which phase 1–6 words each file depends on.
    Merge results into training_data/dependency_graph.json (append, do not overwrite existing nodes).
    Append the processed filenames to training_data/dependency_graph_progress.txt.

    Receipt: files processed this run, batch size used, total nodes so far, total edges so far,
    files remaining.
    When dependency_graph_progress.txt contains every file: report total nodes, total edges,
    deepest dependency chain, any circular dependencies. Mark task complete and move to history.md.
    Do not touch any other file.

[ ] Philosophy curriculum audit, backfill planning, and graph placement
    Executor prompt:
    Process the philosophy curriculum files in:
    training_data/philosophy/*cat1.md through *cat12.md

    This task must be resumable.
    Read training_data/philosophy_audit_progress.txt to find which philosophy files have already
    been processed. If the file does not exist, start from the beginning.
    On each run, continue from the next unprocessed philosophy file and append each completed
    filename to training_data/philosophy_audit_progress.txt only after all audit steps for that
    file are finished successfully.

    Do the following, one file at a time:

    1. Check every dialogue against the existing Phase 1–6 vocabulary.
       - Identify any new content words not already introduced.
       - Create or update: training_data/philosophy_backfill_list.md
       - Group new vocabulary by source file and dialogue entry.

    2. For each new content word, determine whether it must be backfilled into earlier curriculum material.
       - Prefer Phase 6 for abstract/meta words.
       - Prefer Phase 1–5 only when the word is concrete and foundational.
       - Do not backfill function words or trivial variants unless needed for training stability.

    3. Insert the philosophy dialogue files into the dependency graph.
       - Use the rebuilt dependency graph as the placement target.
       - Place each entry where its vocabulary and concepts are already supported.
       - Respect the intended ordering:
         Phase 1–5 → Phase 6 → Story Layer 1 → Philosophy 1–40 → Wiki Level 2 → Story Layer 2 → Philosophy 41–120.
       - Do not introduce Category 10–12 too early.
       - Place Category 11 especially late.

    4. Make the backfill handoff runnable for the existing cron loop.
       - Materialize recommended backfill items into the queue used by the cron backfill worker
         incrementally, appending per completed philosophy file rather than accumulating all
         completed files and flushing later.
       - Keep the queue handoff bounded so no single cron-job run is asked to process more than 50 words.

    5. Report:
       - files checked this run
       - total philosophy files completed so far
       - new vocabulary found
       - recommended backfill targets
       - dependency graph changes made
       - any entries that cannot yet be placed safely
       - queue/backfill handoff prepared for the 50-word cron batch
       - philosophy files remaining

    When training_data/philosophy_audit_progress.txt contains all target philosophy files,
    report the audit complete, then mark this task complete and move it to history.md.
    Do not edit the philosophy dialogue files during this task except for obvious formatting errors.

[ ] Heartbeat: if queue is empty, summarize corpus state, flag what training prerequisites
    are unmet, and ask user (on Discord) for next directive before next cron fires.