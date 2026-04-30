
import os
import re
from collections import Counter, defaultdict

def get_files(path):
    all_files = []
    if os.path.isfile(path):
        return [path]
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

# Pronouns to exclude from backfill recommendations
PRONOUNS = {
    "i", "me", "my", "mine", "myself",
    "you", "your", "yours", "yourself", "yourselves",
    "he", "him", "his", "himself",
    "she", "her", "hers", "herself",
    "it", "its", "itself",
    "we", "us", "our", "ours", "ourselves",
    "they", "them", "their", "theirs", "themselves",
    "who", "whom", "whose", "which", "that",
    "this", "those", "these"
}

# Concept families for grouping
CONCEPT_FAMILIES = {
    "friend": ["friend", "friends", "friendship", "friendly"],
    "share": ["share", "sharing", "shared", "shares"],
    "care": ["care", "careful", "carefully", "cares", "caring"],
    "try": ["try", "tries", "trying", "tried"],
    "wait": ["wait", "waiting", "waits", "waited"],
    "hurt": ["hurt", "hurts", "hurting"],
    "reason": ["reason", "reasoning", "reasons"],
    "know": ["know", "knowing", "known", "knows"],
    "think": ["think", "thinking", "thinks", "thought", "thoughts"],
    "equal": ["equal", "equals", "equality", "equally"],
    "math": ["add", "addition", "plus", "minus", "subtract", "subtraction", "sum", "total", "totals"],
    "sequence": ["finally", "first", "then", "after", "before", "next", "last"]
}

def main():
    baseline_paths = ["training_data/phases"]
    target_corpora = {
        "wiki": "training_data/wiki",
        "stories": "training_data/triplet_stories",
        "reasoning": "training_data/reasoning"
    }

    baseline_vocab = set()
    for path in baseline_paths:
        for f_path in get_files(path):
            with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                baseline_vocab.update(extract_words(f.read()))

    word_file_counts = Counter()
    word_corpus_map = defaultdict(set)
    total_target_files = 0

    for corpus_name, path in target_corpora.items():
        files = get_files(path)
        total_target_files += len(files)
        for f_path in files:
            with open(f_path, "r", encoding="utf-8", errors="ignore") as f:
                words = extract_words(f.read())
                for word in words:
                    if word not in baseline_vocab and word not in PRONOUNS:
                        word_file_counts[word] += 1
                        word_corpus_map[word].add(corpus_name)

    high_leverage_seeds = {
        "epistemic": ["know", "guess", "sure", "check", "fact", "true", "real", "reason", "certain", "uncertain", "maybe", "probably", "possibly", "perhaps", "evidence", "proof", "justification", "believe", "thought", "idea", "doubt", "correct", "false", "wrong", "right"],
        "connectives": ["because", "if", "then", "so", "but", "instead", "therefore", "however", "though", "since", "unless"],
        "meta": ["word", "sentence", "letter", "meaning", "symbol", "phrase", "language", "name", "label", "category"],
        "math_logic": ["add", "plus", "minus", "total", "equal", "same", "different", "more", "less", "most", "least", "all", "some", "none", "every", "each", "both", "neither", "either"],
        "sequence": ["first", "then", "after", "finally", "before", "next", "last", "during", "while", "until"]
    }

    family_stats = {}
    for fam_name, members in CONCEPT_FAMILIES.items():
        fam_count = 0
        fam_corpora = set()
        missing_members = []
        for m in members:
            if m in word_file_counts:
                fam_count += word_file_counts[m]
                fam_corpora.update(word_corpus_map[m])
                missing_members.append(m)
        if missing_members:
            family_stats[fam_name] = {
                "count": fam_count,
                "corpora": ", ".join(sorted(list(fam_corpora))),
                "members": missing_members
            }

    gap_report = []
    processed_words = set()

    # Process families first
    for fam_name, stats in family_stats.items():
        priority = "high" if stats["count"] > 20 else "medium"
        gap_report.append({
            "item": f"{fam_name} family",
            "priority": priority,
            "category": "family",
            "count": stats["count"],
            "corpora": stats["corpora"],
            "notes": f"Includes: {', '.join(stats['members'])}"
        })
        for m in stats["members"]:
            processed_words.add(m)

    # Process remaining words
    for word, count in word_file_counts.most_common():
        if word in processed_words:
            continue
        
        priority = "medium"
        category = "general"
        
        is_high_leverage = False
        for cat, seeds in high_leverage_seeds.items():
            if word in seeds:
                is_high_leverage = True
                priority = "high"
                category = cat
                break
        
        if count > total_target_files * 0.1:
            priority = "high"
        
        if is_high_leverage or count > 15:
            gap_report.append({
                "item": word,
                "priority": priority,
                "category": category,
                "count": count,
                "corpora": ", ".join(sorted(list(word_corpus_map[word]))),
                "notes": ""
            })

    print("# Vocabulary Gap Analysis Report\n")
    print("## High-Priority Bounded Backfill Queue\n")
    print("| Item | Priority | Category | Total Count | Corpora | Notes |")
    print("|------|----------|----------|-------------|---------|-------|")
    for entry in gap_report:
        if entry["priority"] == "high":
            print(f"| {entry['item']} | {entry['priority']} | {entry['category']} | {entry['count']} | {entry['corpora']} | {entry['notes']} |")

    print("\n## Secondary Queue (Lower Priority or Deferred)\n")
    print("| Item | Priority | Category | Total Count | Corpora | Notes |")
    print("|------|----------|----------|-------------|---------|-------|")
    for entry in gap_report:
        if entry["priority"] == "medium":
            print(f"| {entry['item']} | {entry['priority']} | {entry['category']} | {entry['count']} | {entry['corpora']} | {entry['notes']} |")

if __name__ == "__main__":
    main()
