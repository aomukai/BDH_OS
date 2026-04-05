"""Generate training data for the QA behavior micro LoRA.

Writes loras/skills/qa_behavior/train.jsonl — ~80 examples across
four prompt shapes: what/why/how questions and definition completions.

Run with:
    python loras/skills/qa_behavior/generate_training_data.py
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent

# ---------------------------------------------------------------------------
# Training examples
# Completions must:
#   - start directly (no "I", "Well", "So", "Once")
#   - be one sentence
#   - match the register of the prompt shape
# ---------------------------------------------------------------------------

WHAT_IS = [
    ("What is a book?",         "A book is a written work made of pages bound together."),
    ("What is a school?",       "A school is a place where children learn and study."),
    ("What is a friend?",       "A friend is a person you trust and enjoy being with."),
    ("What is water?",          "Water is a clear liquid that all living things need to survive."),
    ("What is a tree?",         "A tree is a tall plant with a trunk, branches, and leaves."),
    ("What is a river?",        "A river is a large stream of water that flows to the sea."),
    ("What is a family?",       "A family is a group of people who are related and care for each other."),
    ("What is a home?",         "A home is a place where a person or family lives."),
    ("What is a word?",         "A word is a unit of language that carries meaning."),
    ("What is a number?",       "A number is a symbol used to count or measure things."),
    ("What is a city?",         "A city is a large place where many people live and work."),
    ("What is an animal?",      "An animal is a living creature that can move and feel."),
    ("What is a season?",       "A season is one of the four parts of the year: spring, summer, autumn, winter."),
    ("What is a cloud?",        "A cloud is a mass of tiny water droplets floating in the sky."),
    ("What is a language?",     "A language is a system of sounds and words used to communicate."),
    ("What is music?",          "Music is a pattern of sounds organised to create rhythm and melody."),
    ("What is a story?",        "A story is a sequence of events told in words."),
    ("What is a question?",     "A question is a sentence used to ask for information."),
    ("What is a garden?",       "A garden is a piece of land where plants and flowers are grown."),
    ("What is the sun?",        "The sun is a star at the centre of our solar system that gives us light and warmth."),
]

WHY = [
    ("Why do birds sing?",              "Birds sing to communicate with each other and attract mates."),
    ("Why do we sleep?",                "Sleep allows the body and brain to rest and recover."),
    ("Why do leaves fall?",             "Leaves fall because trees reduce water loss during winter."),
    ("Why do we eat?",                  "Eating gives the body the energy and nutrients it needs to function."),
    ("Why do we breathe?",              "Breathing brings oxygen into the body and removes carbon dioxide."),
    ("Why do rivers flow?",             "Rivers flow because gravity pulls water downhill toward the sea."),
    ("Why do children go to school?",   "Children go to school to learn, develop skills, and prepare for life."),
    ("Why do we read?",                 "Reading builds knowledge, vocabulary, and understanding of the world."),
    ("Why do plants need sunlight?",    "Plants need sunlight to produce food through photosynthesis."),
    ("Why do we wear clothes?",         "Clothes protect the body from cold, heat, and injury."),
    ("Why do dogs bark?",               "Dogs bark to warn, communicate, or express excitement."),
    ("Why do seasons change?",          "Seasons change because the Earth tilts on its axis as it orbits the sun."),
    ("Why do we drink water?",          "Water keeps the body hydrated and helps organs work properly."),
    ("Why do stars shine?",             "Stars shine because nuclear reactions inside them release enormous energy."),
    ("Why do we laugh?",                "Laughter is a natural response to things we find funny or surprising."),
]

HOW = [
    ("How does rain form?",             "Rain forms when water vapour in clouds cools and turns into droplets."),
    ("How do fish breathe?",            "Fish breathe by pulling oxygen from water through their gills."),
    ("How do plants grow?",             "Plants grow by absorbing water, sunlight, and nutrients from the soil."),
    ("How do birds fly?",               "Birds fly by using their wings to push air downward and lift themselves up."),
    ("How do we learn a language?",     "Language is learned by listening, practising, and using it regularly."),
    ("How does a rainbow form?",        "A rainbow forms when sunlight passes through raindrops and bends into colours."),
    ("How does fire start?",            "Fire starts when a fuel source reaches enough heat to begin burning."),
    ("How do trees get water?",         "Trees absorb water through their roots and carry it up through the trunk."),
    ("How does bread rise?",            "Bread rises because yeast produces gas that makes the dough expand."),
    ("How does memory work?",           "Memory works by storing patterns of neural connections in the brain."),
]

DEFINITION = [
    ("A book is",           "a written or printed work composed of pages bound together."),
    ("A school is",         "a place where students gather to learn under the guidance of teachers."),
    ("An ocean is",         "a vast body of salt water covering most of the Earth's surface."),
    ("A tree is",           "a large plant with a woody trunk, branches, and leaves."),
    ("A river is",          "a natural flow of water that travels across land toward the sea."),
    ("A word is",           "the smallest unit of language that carries a complete meaning."),
    ("A city is",           "a large, densely populated area where people live, work, and trade."),
    ("A family is",         "a group of people connected by blood, care, or close relationship."),
    ("A season is",         "one of the four periods of the year, each with its own weather pattern."),
    ("A cloud is",          "a visible mass of water droplets suspended in the atmosphere."),
    ("An animal is",        "a living organism that can move, sense its environment, and grow."),
    ("A story is",          "a sequence of connected events told to inform or entertain."),
    ("A garden is",         "a cultivated outdoor space used for growing plants, flowers, or food."),
    ("Music is",            "an art form that organises sound into patterns of rhythm and melody."),
    ("Language is",         "a shared system of words and grammar used by people to communicate."),
]

CAUSAL = [
    ("The reason birds sing is",        "to mark territory and attract a mate."),
    ("The reason we eat is",            "to provide the body with energy and essential nutrients."),
    ("The reason leaves fall is",       "that trees conserve energy and water during colder months."),
    ("The reason we sleep is",          "that the body and brain need time to rest and repair."),
    ("The reason plants need water is", "that water carries nutrients and supports all their growth processes."),
    ("Sleep is important because",      "the body repairs itself and the brain processes new information."),
    ("Reading is valuable because",     "it builds vocabulary, knowledge, and the ability to think clearly."),
    ("Language matters because",        "it allows people to share thoughts, feelings, and knowledge with each other."),
    ("Exercise is good because",        "it strengthens the body, improves mood, and supports long-term health."),
    ("Schools exist because",           "children need a structured place to learn skills and develop as people."),
]

# ---------------------------------------------------------------------------
# Build JSONL
# ---------------------------------------------------------------------------

def build_examples() -> list[dict]:
    examples = []

    for question, answer in WHAT_IS:
        examples.append({
            "prompt":     f"Q: {question}\nA:",
            "completion": f" {answer}",
        })

    for question, answer in WHY:
        examples.append({
            "prompt":     f"Q: {question}\nA:",
            "completion": f" {answer}",
        })

    for question, answer in HOW:
        examples.append({
            "prompt":     f"Q: {question}\nA:",
            "completion": f" {answer}",
        })

    for stem, continuation in DEFINITION:
        examples.append({
            "prompt":     stem,
            "completion": f" {continuation}",
        })

    for stem, continuation in CAUSAL:
        examples.append({
            "prompt":     stem,
            "completion": f" {continuation}",
        })

    return examples


def main() -> None:
    examples = build_examples()
    out_path = HERE / "train.jsonl"
    with out_path.open("w", encoding="utf-8") as f:
        for ex in examples:
            f.write(json.dumps(ex, ensure_ascii=False) + "\n")
    print(f"Wrote {len(examples)} examples to {out_path}")

    # Quick sanity check — read back and verify
    loaded = [json.loads(line) for line in out_path.read_text(encoding="utf-8").splitlines()]
    assert len(loaded) == len(examples), "Line count mismatch"
    for ex in loaded:
        assert "prompt" in ex and "completion" in ex
        assert not ex["completion"].lstrip().startswith(("I ", "Well", "So,", "Once")), \
            f"Bad completion start: {ex['completion']!r}"
    print("Sanity check passed.")


if __name__ == "__main__":
    main()
