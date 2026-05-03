#!/bin/bash

REPORT="training_data/audit_report.txt"

# Empty the report file first
> "$REPORT"

# Define reference files per phase
declare -A REFERENCE
REFERENCE[phase_1]="training_data/phases/phase_1/phase_1_001.md"
REFERENCE[phase_2]="training_data/phases/phase_2/phase_2_01.md"
REFERENCE[phase_3]="training_data/phases/phase_3/phase_3_01.md"
REFERENCE[phase_4]="training_data/phases/phase_4/phase_4_01.md"
REFERENCE[phase_5]="training_data/phases/phase_5/phase_5_01.md"
REFERENCE[phase_6]="training_data/phases/phase_6/phase_6_01.md"

# Loop over each phase
for PHASE in phase_1 phase_2 phase_3 phase_4 phase_5 phase_6; do
    REF="${REFERENCE[$PHASE]}"
    
    # Get reference [user] count
    REF_COUNT=$(grep -c '\[user\]' "$REF")
    
    # Loop over .md files in the phase folder
    for FILE in "training_data/phases/$PHASE"/*.md; do
        [ -f "$FILE" ] || continue
        
        FILE_COUNT=$(grep -c '\[user\]' "$FILE")
        
        if [ "$FILE_COUNT" -ne "$REF_COUNT" ]; then
            echo "$FILE" >> "$REPORT"
        fi
    done
done
