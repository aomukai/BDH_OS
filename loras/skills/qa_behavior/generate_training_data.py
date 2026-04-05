"""Generate training data for the QA behavior micro LoRA — v3.

Three-layer structure per concept (inspired by toddler language acquisition):

  Layer 1 — short anchor
    Forward:  "A bird is" → "feathers."
    Backward: "Feathers are" → "part of a bird."  (only where exclusive)

  Layer 2 — expanded definition (Q/A frame)
    "Q: What is a bird?\nA:" → "A bird is an animal with feathers and wings."

  Layer 3 — subject repetition (expansion technique)
    "A bird has feathers." → "A bird uses feathers to fly and stay warm."

Backward pairs only used where the attribute is exclusive to that concept.
"Flows" and "salty" alone are too broad — those concepts get forward-only.

Run with:
    python loras/skills/qa_behavior/generate_training_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Layer 1 — short anchors
# Forward: concept → its most exclusive attribute (single word or tight phrase)
# Backward: attribute → concept  (only where the attribute is truly exclusive)
# ---------------------------------------------------------------------------

ANCHORS_FORWARD = [
    ("A bird is",           "feathers."),
    ("A book is",           "pages."),
    ("A tree is",           "a trunk."),
    ("Rain is",             "drops falling from clouds."),
    ("A shoe is",           "a covering for the foot."),
    ("Bread is",            "baked dough."),
    ("A chair is",          "a seat with a back."),
    ("A river is",          "flowing fresh water."),
    ("A school is",         "where children learn."),
    ("An ocean is",         "vast salt water."),
]

# Only concepts whose attribute is exclusive enough to run backwards safely
ANCHORS_BACKWARD = [
    ("Feathers are",        "part of a bird."),
    ("Pages are",           "part of a book."),
    ("A trunk belongs to",  "a tree."),
    ("Baked dough is",      "bread."),
]

# ---------------------------------------------------------------------------
# Layer 2 — expanded definitions (Q/A frame)
# Same ten concepts, full sentence, attribute anchored immediately.
# ---------------------------------------------------------------------------

DEFINITIONS_QA = [
    ("What is a bird?",
     "A bird is an animal with feathers and wings."),
    ("What is a book?",
     "A book is a written work made of pages with words or pictures."),
    ("What is a tree?",
     "A tree is a tall plant with a woody trunk, branches, and leaves."),
    ("What is rain?",
     "Rain is water that falls from clouds in small drops."),
    ("What is a shoe?",
     "A shoe is a covering worn on the foot to protect it."),
    ("What is bread?",
     "Bread is a food made by baking dough from flour and water."),
    ("What is a chair?",
     "A chair is a piece of furniture made for one person to sit on."),
    ("What is a river?",
     "A river is a long body of fresh water that flows across land."),
    ("What is a school?",
     "A school is a place where children go to learn and study."),
    ("What is an ocean?",
     "An ocean is a vast body of salt water covering much of the Earth."),
]

# ---------------------------------------------------------------------------
# Layer 3 — subject repetition
# Short statement, then same subject expanded with function or consequence.
# Keeps the concept active across both sentences.
# ---------------------------------------------------------------------------

SUBJECT_REPETITION = [
    ("A bird has feathers.",
     "A bird uses feathers to fly and stay warm."),
    ("A book has pages.",
     "A book carries words and pictures on its pages."),
    ("A tree has a trunk.",
     "A tree grows its trunk tall to reach the light."),
    ("Rain falls in drops.",
     "Rain drops fall from clouds and land on the ground."),
    ("A shoe covers the foot.",
     "A shoe protects the foot from the ground and sharp objects."),
    ("Bread is made from dough.",
     "Bread is made from dough that is baked in an oven."),
    ("A chair has a seat.",
     "A chair has a seat and a back to lean against."),
    ("A river flows downhill.",
     "A river flows downhill and carries water to the sea."),
    ("A school has lessons.",
     "A school has lessons and teachers to help children learn."),
    ("An ocean is full of salt water.",
     "An ocean is full of salt water and covers most of the Earth."),
]

# ---------------------------------------------------------------------------
# Why / How / Causal — kept for structural variety, trimmed for focus
# ---------------------------------------------------------------------------

WHY = [
    ("Why do birds have feathers?",
     "Feathers keep a bird warm and help it fly."),
    ("Why do we read books?",
     "Books carry knowledge and stories on their pages."),
    ("Why does rain fall?",
     "Water in clouds grows heavy and falls as drops."),
    ("Why do rivers flow?",
     "Gravity pulls water downhill toward lower ground."),
    ("Why do we wear shoes?",
     "Shoes protect the foot from the ground."),
    ("Why does bread need an oven?",
     "Heat turns the soft dough into firm, baked bread."),
    ("Why do children go to school?",
     "School gives children lessons and teachers to learn from."),
    ("Why is the ocean salty?",
     "Rivers carry salt from the land into the ocean over time."),
]

HOW = [
    ("How do birds fly?",
     "Birds push air down with their wings to lift themselves up."),
    ("How does rain form?",
     "Water vapour rises, cools, and becomes drops that fall."),
    ("How does bread bake?",
     "Heat dries the wet dough and makes it firm and golden."),
    ("How does a river start?",
     "Rain collects on high ground and flows downhill together."),
    ("How does a tree grow?",
     "A tree absorbs water through roots and light through leaves."),
    ("How does a school work?",
     "Teachers give children lessons in different subjects each day."),
]

CAUSAL = [
    ("The reason birds have feathers is",
     "to fly and to stay warm."),
    ("The reason bread rises is",
     "yeast in the dough releases gas as it feeds."),
    ("The reason rivers flow is",
     "gravity pulls water toward lower ground."),
    ("The reason shoes wear out is",
     "the sole rubs against the ground with every step."),
    ("The reason we go to school is",
     "to learn from teachers and study many subjects."),
    ("Trees grow tall because",
     "they reach up for sunlight above other plants."),
    ("Rain is cold because",
     "it falls from high clouds where the air is cool."),
    ("An ocean is salty because",
     "rivers wash salt from the land into it over many years."),
]

# ---------------------------------------------------------------------------
# Build JSONL
# ---------------------------------------------------------------------------

def build_examples() -> list[dict]:
    examples = []

    for stem, completion in ANCHORS_FORWARD:
        examples.append({"prompt": stem, "completion": f" {completion}"})

    for stem, completion in ANCHORS_BACKWARD:
        examples.append({"prompt": stem, "completion": f" {completion}"})

    for question, answer in DEFINITIONS_QA:
        examples.append({"prompt": f"Q: {question}\nA:", "completion": f" {answer}"})

    for sentence, expansion in SUBJECT_REPETITION:
        examples.append({"prompt": sentence, "completion": f" {expansion}"})

    for question, answer in WHY:
        examples.append({"prompt": f"Q: {question}\nA:", "completion": f" {answer}"})

    for question, answer in HOW:
        examples.append({"prompt": f"Q: {question}\nA:", "completion": f" {answer}"})

    for stem, completion in CAUSAL:
        examples.append({"prompt": stem, "completion": f" {completion}"})

    return examples


def main() -> None:
    examples = build_examples()
    out_path = HERE / "train.jsonl"

    with out_path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")

    print(f"Wrote {len(examples)} examples to {out_path}")

    loaded = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert len(loaded) == len(examples)
    for ex in loaded:
        assert "prompt" in ex and "completion" in ex
        c = ex["completion"].lstrip()
        assert not c.startswith(("I ", "Well", "So,", "Once")), \
            f"Bad completion start: {ex['completion']!r}"

    print(f"  Layer 1 forward  : {len(ANCHORS_FORWARD)}")
    print(f"  Layer 1 backward : {len(ANCHORS_BACKWARD)}")
    print(f"  Layer 2 Q/A      : {len(DEFINITIONS_QA)}")
    print(f"  Layer 3 repeat   : {len(SUBJECT_REPETITION)}")
    print(f"  Why              : {len(WHY)}")
    print(f"  How              : {len(HOW)}")
    print(f"  Causal           : {len(CAUSAL)}")
    print("Sanity check passed.")


if __name__ == "__main__":
    main()
