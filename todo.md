# TODO

This file is the single active unfinished-work queue for the repository.

Rules:
- Add new unfinished work here.
- When a task is completed, remove it from this file and move it to `history.md`.
- Do not leave completed tasks or long status summaries here.
- Legacy planning and status docs belong in `archive/`.

## Active queue

[ ] task: regen phase files — reclassify and rewrite phase_5_47 through phase_5_1858 in correct phases
- Phase 1: done (files up to phase_1_1249.md)
- Phase 2: 60 words remaining — resume file: training_data/phases/phase_2_words.txt
- Phase 3: 99 words remaining — resume file: training_data/phases/phase_3_words.txt
- Phase 4: 14 words remaining — resume file: training_data/phases/phase_4_words.txt
- Phase 5: 108 words remaining — resume file: training_data/phases/phase_5_words.txt
- Phase 6: 72 words remaining — resume file: training_data/phases/phase_6_words.txt
- Resume command: nohup bash /home/aomukai/Ninereeds/run_all_regen.sh >> /tmp/regen.log 2>&1 &

[ ] task: post-regen cleanup
- delete phase_5 files 47–1858 (the old broken-format batch)
- remove those entries from dependency_graph.json
