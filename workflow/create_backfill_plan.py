
import os
from collections import defaultdict

def parse_ledger(ledger_path):
    high_priority_items = []
    if not os.path.exists(ledger_path):
        print(f"Ledger file not found at {ledger_path}")
        return high_priority_items

    with open(ledger_path, "r") as f:
        lines = f.readlines()

    header_line_index = -1
    for i, line in enumerate(lines):
        if line.strip().startswith('| item |'):
            header_line_index = i
            break

    if header_line_index == -1:
        print("Header row not found in ledger file.")
        return high_priority_items

    header = [h.strip() for h in lines[header_line_index].strip().split('|') if h.strip()]
    
    for line in lines[header_line_index + 1:]:
        if line.startswith('|') and '---' not in line:
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) == len(header):
                row = dict(zip(header, parts))
                if row.get('priority') in ('critical', 'high') and row.get('phase_1_6_status') == 'missing':
                    high_priority_items.append(row)
    
    return high_priority_items

def create_backfill_plan(items, plan_path):
    plan_content = """# Phase 1–6 Curriculum Backfill Plan

This document outlines the bounded, low-noise backfill plan for incorporating high-priority vocabulary into the Phase 1–6 curriculum. The items listed below were identified as 'critical' or 'high' priority and are currently missing from the foundational curriculum.

## Backfill Batches by Landing Zone
"""
    
    items_by_zone = defaultdict(list)
    for item in items:
        items_by_zone[item['recommended_landing_zone']].append(item)

    for zone, zone_items in sorted(items_by_zone.items()):
        plan_content += f"\n### Recommended Landing Zone: {zone}\n\n"
        plan_content += "| Item | Priority | Earliest Appearance |\n"
        plan_content += "|------|----------|---------------------|\n"
        for item in sorted(zone_items, key=lambda x: x['item']):
            plan_content += f"| {item['item']} | {item['priority']} | {item['earliest_non_curriculum_layer']} |\n"

    with open(plan_path, "w") as f:
        f.write(plan_content)

def main():
    ledger_path = "training_files/cross_corpus_introduced_vocabulary_ledger.md"
    plan_path = "training_data/phases/phase_1_6_backfill_plan.md"
    
    print("Parsing vocabulary ledger...")
    high_priority_items = parse_ledger(ledger_path)
    
    if high_priority_items:
        print(f"Found {len(high_priority_items)} high-priority items to backfill.")
        print("Creating backfill plan...")
        create_backfill_plan(high_priority_items, plan_path)
        print(f"Backfill plan created at {plan_path}")
    else:
        print("No high-priority items found to backfill.")

if __name__ == "__main__":
    main()
