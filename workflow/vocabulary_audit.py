
import os
import re
from collections import OrderedDict

def get_files(path):
    all_files = []
    for root, _, files in os.walk(path):
        for file in files:
            if file.endswith(".md"):
                all_files.append(os.path.join(root, file))
    return all_files

def extract_words(text):
    text = text.lower()
    text = re.sub(r"\[user\]|\[ninereeds\]", "", text)
    words = re.findall(r"\b[a-z][a-z-]*\b", text)
    return set(words)

def update_ledger(ledger_path, new_entries):
    header = "| item | type | earliest_non_curriculum_layer | seen_in | phase_1_6_status | priority | recommended_landing_zone | notes |\n"
    separator = "|------|------|-------------------------------|---------|------------------|----------|--------------------------|-------|\n"

    existing_items = set()
    if os.path.exists(ledger_path):
        with open(ledger_path, "r") as f:
            for line in f:
                if line.startswith("|") and not line.startswith("| item") and not line.startswith("|------"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) > 2:
                        existing_items.add(parts[1])

    with open(ledger_path, "a") as f:
        # if the file is new, write the header
        if f.tell() == 0:
            f.write(header)
            f.write(separator)

        for entry in new_entries:
            if entry["item"] not in existing_items:
                row = f'| {entry["item"]} | {entry["type"]} | {entry["earliest_non_curriculum_layer"]} | {entry["seen_in"]} | {entry["phase_1_6_status"]} | {entry["priority"]} | {entry["recommended_landing_zone"]} | {entry["notes"]} |\n'
                f.write(row)
                existing_items.add(entry["item"])

def main():
    corpora = OrderedDict()
    corpora["phase_1_6"] = "training_data/phases"
    corpora["wiki_l1_l4"] = "training_data/wiki"
    corpora["story_t1_t4"] = "training_data/triplet_stories"
    corpora["reasoning"] = "training_data/reasoning"

    vocab_by_corpus = {name: set() for name in corpora}
    all_words = set()
    new_entries = []

    print("Processing corpora...")
    for name, path in corpora.items():
        print(f"  - {name}")
        files = get_files(path)
        for file_path in files:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                words = extract_words(content)
                vocab_by_corpus[name].update(words)
    
    phase_1_6_vocab = vocab_by_corpus["phase_1_6"]
    cumulative_vocab = set()
    cumulative_vocab.update(phase_1_6_vocab)

    print("\nAuditing corpora...")
    for name, vocab in vocab_by_corpus.items():
        if name == "phase_1_6":
            continue

        new_words = vocab - cumulative_vocab
        print(f"  - {name}: found {len(new_words)} new words.")

        for word in sorted(list(new_words)):
            seen_in = [n for n, v in vocab_by_corpus.items() if word in v]
            
            phase_status = "covered" if word in phase_1_6_vocab else "missing"

            entry = {
                "item": word,
                "type": "word",
                "earliest_non_curriculum_layer": name,
                "seen_in": ", ".join(seen_in),
                "phase_1_6_status": phase_status,
                "priority": "medium",
                "recommended_landing_zone": "phase_6",
                "notes": ""
            }
            new_entries.append(entry)

        cumulative_vocab.update(vocab)
    
    ledger_path = "training_files/cross_corpus_introduced_vocabulary_ledger.md"
    print(f"\nUpdating ledger at {ledger_path} with {len(new_entries)} new entries.")
    update_ledger(ledger_path, new_entries)
    print("Done.")

if __name__ == "__main__":
    main()
