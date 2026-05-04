#!/bin/bash
# run_all_regen.sh
# Runs regen for all 6 phases sequentially.
# Phases 1/2/3/6: batch 20. Phases 4/5: batch 40.

cd /home/aomukai/Ninereeds

bash run_regen.sh 1 20
bash run_regen.sh 2 20
bash run_regen.sh 3 20
bash run_regen.sh 4 40
bash run_regen.sh 5 40
bash run_regen.sh 6 20
bash run_regen.sh 2 20

echo "[$(date)] All phases complete."
