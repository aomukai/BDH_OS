#!/usr/bin/env python3
"""Build lesson-aware Ninereeds vocabulary teaching blocks.

The source lesson header and PPP example are treated as immutable.  Generation
starts after PPP and is idempotent: an existing VOCAB_BLOCK_1 and everything
after it are replaced.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


ROOT = Path(__file__).resolve().parents[1]
LANGUAGE = ROOT / "language"


@dataclass(frozen=True)
class Stages:
    affirmative_question: str
    affirmative_answer: str
    negative_question: str
    negative_answer: str
    w_question: str
    w_answer: str
    or_question: str
    or_answer: str


def stages(
    aq: str,
    aa: str,
    na: str,
    wq: str,
    wa: str,
    oq: str,
    oa: str,
    nq: str | None = None,
) -> Stages:
    return Stages(aq, aa, nq or aq, na, wq, wa, oq, oa)


def article(word: str) -> str:
    return "an" if word[:1].lower() in "aeiou" else "a"


def with_article(word: str) -> str:
    return f"{article(word)} {word}"


def plural(word: str) -> str:
    irregular = {"person": "people", "child": "children"}
    if word in irregular:
        return irregular[word]
    if word.endswith(("s", "sh", "ch", "x", "z")):
        return word + "es"
    if word.endswith("o"):
        return word + "es"
    if word.endswith("y") and len(word) > 1 and word[-2] not in "aeiou":
        return word[:-1] + "ies"
    return word + "s"


def possessive(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def past(verb: str) -> str:
    irregular = {
        "begin": "began", "bring": "brought", "build": "built",
        "buy": "bought", "catch": "caught", "come": "came",
        "cut": "cut", "do": "did", "draw": "drew", "drink": "drank",
        "drive": "drove", "eat": "ate", "fall": "fell", "find": "found",
        "fly": "flew", "forget": "forgot", "freeze": "froze",
        "give": "gave", "go": "went", "have": "had", "hear": "heard",
        "hold": "held", "keep": "kept", "leave": "left", "make": "made",
        "meet": "met", "pay": "paid", "read": "read", "ride": "rode",
        "ring": "rang", "rise": "rose", "run": "ran", "say": "said",
        "see": "saw", "sell": "sold", "send": "sent", "sit": "sat",
        "sleep": "slept", "speak": "spoke", "spend": "spent",
        "stand": "stood", "take": "took", "tell": "told", "think": "thought",
        "wake": "woke", "wear": "wore", "write": "wrote",
    }
    if verb in irregular:
        return irregular[verb]
    if verb.endswith("e"):
        return verb + "d"
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in "aeiou":
        return verb[:-1] + "ied"
    return verb + "ed"


def third(verb: str) -> str:
    irregular = {"have": "has", "do": "does", "go": "goes"}
    if verb in irregular:
        return irregular[verb]
    if verb.endswith(("s", "sh", "ch", "x", "z", "o")):
        return verb + "es"
    if verb.endswith("y") and len(verb) > 1 and verb[-2] not in "aeiou":
        return verb[:-1] + "ies"
    return verb + "s"


def gerund(verb: str) -> str:
    if verb.endswith("ing"):
        return verb
    if verb.endswith("ie"):
        return verb[:-2] + "ying"
    if verb.endswith("e") and not verb.endswith("ee"):
        return verb[:-1] + "ing"
    doubles = {"sit", "run", "swim", "stop", "drop", "plan", "cut"}
    if verb in doubles:
        return verb + verb[-1] + "ing"
    return verb + "ing"


def render_block(number: int, instances: list[Stages]) -> str:
    if len(instances) != 4:
        raise ValueError(f"VOCAB_BLOCK_{number} has {len(instances)} instances")
    out = [f"VOCAB_BLOCK_{number}:"]
    for x in instances:
        out.extend([
            f"- AFFIRMATIVE_PRESENTATION_QUESTION: {x.affirmative_question}",
            f"- AFFIRMATIVE_PRESENTATION_ANSWER: {x.affirmative_answer}",
            f"- AFFIRMATIVE_TEST_QUESTION: {x.affirmative_question}",
            "- AFFIRMATIVE_TEST_ANSWER:",
            f"- NEGATIVE_PRESENTATION_QUESTION: {x.negative_question}",
            f"- NEGATIVE_PRESENTATION_ANSWER: {x.negative_answer}",
            f"- NEGATIVE_TEST_QUESTION: {x.negative_question}",
            "- NEGATIVE_TEST_ANSWER:",
            f"- W_PRESENTATION_QUESTION: {x.w_question}",
            f"- W_PRESENTATION_ANSWER: {x.w_answer}",
            f"- W_TEST_QUESTION: {x.w_question}",
            "- W_TEST_ANSWER:",
            f"- OR_PRESENTATION_QUESTION: {x.or_question}",
            f"- OR_PRESENTATION_ANSWER: {x.or_answer}",
            f"- OR_TEST_QUESTION: {x.or_question}",
            "- OR_TEST_ANSWER:",
        ])
    return "\n".join(out)


def parse_sets(text: str) -> list[list[str]]:
    found = re.findall(r"^VOCAB_SET_(\d+): (.+)$", text, re.MULTILINE)
    found.sort(key=lambda pair: int(pair[0]))
    return [[item.strip() for item in value.split(",")] for _, value in found]


Renderer = Callable[[int, str, str, int], Stages]


def generate_lesson(lesson: int, sets: list[list[str]]) -> list[list[Stages]]:
    render = RENDERERS.get(lesson)
    if render is None:
        raise KeyError(f"No renderer for L{lesson:03d}")
    blocks: list[list[Stages]] = []
    for set_index, words in enumerate(sets, start=1):
        if len(words) != 4:
            raise ValueError(f"L{lesson:03d} VOCAB_SET_{set_index} has {len(words)} items")
        blocks.append([
            render(set_index, word, words[(i + 1) % 4], i)
            for i, word in enumerate(words)
        ])
    return blocks


# Renderers are registered in numbered batches below.  Each renderer receives
# the vocabulary-set number, the target item, a same-set fallback, and item
# index.  Same-set fallbacks keep OR questions within the demonstrated pattern.
RENDERERS: dict[int, Renderer] = {}


def register(number: int):
    def decorator(fn: Renderer) -> Renderer:
        RENDERERS[number] = fn
        return fn
    return decorator


@register(1)
def l001(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is this {x}?", f"Yes, this is {x}.", f"No, this isn't {x}.",
        "What is this?", f"This is {x}.",
        f"Is this {x} or {y}?", f"This is {x}.")


@register(2)
def l002(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is that {x}?", f"Yes, that is {x}.", f"No, that isn't {x}.",
        "What is that?", f"That is {x}.",
        f"Is that {x} or {y}?", f"That is {x}.")


@register(3)
def l003(s: int, x: str, y: str, i: int) -> Stages:
    demonstrative = "these" if i % 2 == 0 else "those"
    cap = demonstrative.capitalize()
    return stages(
        f"Are {demonstrative} {x}?", f"Yes, {demonstrative} are {x}.", f"No, {demonstrative} aren't {x}.",
        f"What are {demonstrative}?", f"{cap} are {x}.",
        f"Are {demonstrative} {x} or {y}?", f"{cap} are {x}.")


@register(4)
def l004(s: int, x: str, y: str, i: int) -> Stages:
    noun = "a set of speakers" if x == "speakers" else with_article(x)
    nouny = "a set of speakers" if y == "speakers" else with_article(y)
    return stages(
        f"Is this component {noun}?", f"Yes, it is {noun}.",
        f"No, it isn't {noun}.", "What is this component?", f"It is {noun}.",
        f"Is this component {noun} or {nouny}?", f"It is {noun}.")


@register(5)
def l005(s: int, x: str, y: str, i: int) -> Stages:
    variant = ((s - 1) * 4 + i) % 6
    if variant == 0:
        return stages(f"Are you {with_article(x)}?", f"Yes, I am {with_article(x)}.", f"No, I am not {with_article(x)}.",
                      "What is your job?", f"I am {with_article(x)}.",
                      f"Are you {with_article(x)} or {with_article(y)}?", f"I am {with_article(x)}.")
    if variant == 1:
        subject, be, neg, pronoun = "you", "are", "aren't", "You"
    elif variant == 2:
        subject, be, neg, pronoun = "he", "is", "isn't", "He"
    elif variant == 3:
        subject, be, neg, pronoun = "she", "is", "isn't", "She"
    elif variant == 4:
        subject, be, neg, pronoun = "we", "are", "aren't", "We"
    else:
        subject, be, neg, pronoun = "they", "are", "aren't", "They"
    return stages(
        f"{be.capitalize()} {subject} {with_article(x)}?", f"Yes, {subject} {be} {with_article(x)}.",
        f"No, {subject} {neg} {with_article(x)}.", "What is the participant's job?",
        f"{pronoun} {be} {with_article(x)}.",
        f"{be.capitalize()} {subject} {with_article(x)} or {with_article(y)}?", f"{pronoun} {be} {with_article(x)}.")


@register(6)
def l006(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is this {with_article(x)}?", f"Yes, this is {with_article(x)}.",
        f"No, this isn't {with_article(x)}.", "What is this?",
        f"This is {with_article(x)}.",
        f"Is this {with_article(x)} or {with_article(y)}?", f"This is {with_article(x)}.")


@register(7)
def l007(s: int, x: str, y: str, i: int) -> Stages:
    xs, ys = plural(x), plural(y)
    if i % 2 == 0:
        return stages(
            f"Is this {with_article(x)}?", f"Yes, this is {with_article(x)}.", f"No, this isn't {with_article(x)}.",
            "What is this?", f"This is {with_article(x)}.",
            f"Is this {with_article(x)} or {with_article(y)}?", f"This is {with_article(x)}.")
    return stages(
        f"Are these {xs}?", f"Yes, these are {xs}.", f"No, these aren't {xs}.",
        "What are these?", f"These are {xs}.",
        f"Are these {xs} or {ys}?", f"These are {xs}.")


@register(8)
def l008(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is this the {x}?", f"Yes, this is the {x}.", f"No, this isn't the {x}.",
        "What is this check-in item?", f"This is the {x}.",
        f"Is this the {x} or the {y}?", f"This is the {x}.")


@register(9)
def l009(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is this {article(x)} {x} suitcase?", f"Yes, this is {article(x)} {x} suitcase; the suitcase is {x}.",
        f"No, this isn't {article(x)} {x} suitcase; the suitcase isn't {x}.",
        "What is this suitcase like?", f"This is {article(x)} {x} suitcase; the suitcase is {x}.",
        f"Is this suitcase {x} or {y}?", f"This is {article(x)} {x} suitcase; the suitcase is {x}.")


@register(10)
def l010(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is this Maya's {x}?", f"Yes, this is Maya's {x}; it is her {x}.",
        f"No, this isn't Maya's {x}; it isn't her {x}.", f"Whose {x} is this?",
        f"This is Maya's {x}; it is her {x}.",
        f"Is this Maya's {x} or Leo's {x}?", f"This is Maya's {x}; it is her {x}.")


@register(11)
def l011(s: int, x: str, y: str, i: int) -> Stages:
    female = x in {"Maya", "Eva", "Lina", "Priya"}
    subj, obj = ("she", "her") if female else ("he", "him")
    cap = subj.capitalize()
    recipient = "Leo" if x != "Leo" else "Maya"
    recipient_pronoun = "him" if recipient == "Leo" else "her"
    return stages(
        f"Did {x} give {recipient} the file?", f"Yes, {x} gave {recipient} the file; {subj} gave it to {recipient_pronoun}.",
        f"No, {x} didn't give {recipient} the file; {subj} didn't give it to {recipient_pronoun}.",
        f"Who gave {recipient} the file?", f"{x} gave {recipient} the file; {subj} gave it to {recipient_pronoun}.",
        f"Did {x} give {recipient_pronoun} the file, or did {recipient} give it to {obj}?",
        f"{x} gave {recipient} the file; {subj} gave it to {recipient_pronoun}.")


@register(12)
def l012(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is this {x} yours?", f"Yes, this {x} is mine.", f"No, this {x} isn't mine.",
        f"Whose is this {x}?", f"This {x} is mine.",
        f"Is this {x} mine or yours?", f"This {x} is mine.")


@register(13)
def l013(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is the red {x} yours?", f"Yes, the red one is mine.", f"No, the red one isn't mine.",
        f"Which {x} is yours?", "The red one is mine.",
        f"Is your {x} the red one or the blue one?", f"My {x} is the red one.")


@register(14)
def l014(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        aq = f"Does the mill grind {x} every day?"
        pos = f"the mill grinds {x} every day"
        wq = "What does the mill grind every day?"
    elif s == 2:
        aq = f"Does the baker check the {x} every morning?"
        pos = f"the baker checks the {x} every morning"
        wq = "What does the baker check every morning?"
    else:
        facts = {
            "baker": ("Does the baker make bread every day?", "the baker makes bread every day", "Who makes bread every day?"),
            "mill": ("Does the mill grind wheat every day?", "the mill grinds wheat every day", "What grinds wheat every day?"),
            "oven": ("Does the oven bake bread every morning?", "the oven bakes bread every morning", "What bakes bread every morning?"),
            "yeast": ("Does yeast make dough rise?", "yeast makes dough rise", "What makes dough rise?"),
        }
        aq, pos, wq = facts[x]
    cap = pos[0].upper() + pos[1:]
    neg = re.sub(r"\b(does|do)\b", r"\1n't", aq.replace("?", ""), count=1)
    # Explicit subject negation is clearer than deriving from the question.
    if s == 1:
        na = f"No, the mill doesn't grind {x} every day."
        oq = f"Does the mill grind {x} or {y} every day?"
    elif s == 2:
        na = f"No, the baker doesn't check the {x} every morning."
        oq = f"Does the baker check the {x} or the {y} every morning?"
    else:
        subject = pos.split()[0]
        if x == "baker":
            na, oq = "No, the baker doesn't make bread every day.", "Does the baker make bread every day or only on weekends?"
        elif x == "mill":
            na, oq = "No, the mill doesn't grind wheat every day.", "Does the mill grind wheat or bake bread every day?"
        elif x == "oven":
            na, oq = "No, the oven doesn't bake bread every morning.", "Does the oven bake bread or grind wheat every morning?"
        else:
            na, oq = "No, yeast doesn't make dough rise.", "Does yeast make dough rise or make it cold?"
    return stages(aq, f"Yes, {pos}.", na, wq, f"{cap}.", oq, f"{cap}.")


@register(15)
def l015(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        return stages(
            f"The room is stuffy. Should I open the {x}?", f"Yes. Open the {x}.",
            f"No. Don't open the {x}.", f"The room is stuffy. What should I open?", f"Open the {x}.",
            f"Should I open the {x} or the {y}?", f"Open the {x}.")
    objects = {"open": "window", "close": "window", "turn on": "fan", "turn off": "fan"}
    obj = objects[x]
    yobj = objects[y]
    return stages(
        f"The room needs fresh air. Should I {x} the {obj}?", f"Yes. {x.capitalize()} the {obj}.",
        f"No. Don't {x} the {obj}.", "The room needs fresh air. What should I do?", f"{x.capitalize()} the {obj}.",
        f"Should I {x} the {obj} or {y} the {yobj}?", f"{x.capitalize()} the {obj}.")


@register(16)
def l016(s: int, x: str, y: str, i: int) -> Stages:
    gx, gy = gerund(x), gerund(y)
    return stages(
        f"Is the child {gx}?", f"Yes, the child is {gx}.", f"No, the child isn't {gx}.",
        "What is the child doing?", f"The child is {gx}.",
        f"Is the child {gx} or {gy}?", f"The child is {gx}.")


@register(17)
def l017(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Can Lina play the {x}?", f"Yes, Lina can play the {x}.", f"No, Lina can't play the {x}.",
        "What can Lina play?", f"Lina can play the {x}.",
        f"Can Lina play the {x} or the {y}?", f"Lina can play the {x}.")


@register(18)
def l018(s: int, x: str, y: str, i: int) -> Stages:
    phrases = {
        "borrow": "borrow the stapler", "use": "use the phone", "enter": "enter the room", "sit": "sit here",
        "open": "open the window", "touch": "touch the display", "take": "take the key", "leave": "leave now",
    }
    px, py = phrases[x], phrases[y]
    return stages(
        f"Can I {px}?", f"Yes, you can {px}.", f"No, you can't {px}.",
        "What can I ask permission to do?", f"You can ask, “Can I {px}?”",
        f"Can I {px} or {py}?", f"You can {px}.")


@register(19)
def l019(s: int, x: str, y: str, i: int) -> Stages:
    nx = "a pair of binoculars" if x == "binoculars" else with_article(x)
    ny = "a pair of binoculars" if y == "binoculars" else with_article(y)
    return stages(
        f"Has Amir got {nx}?", f"Yes, Amir has got {nx}.", f"No, Amir hasn't got {nx}.",
        "What has Amir got?", f"Amir has got {nx}.",
        f"Has Amir got {nx} or {ny}?", f"Amir has got {nx}.")


@register(20)
def l020(s: int, x: str, y: str, i: int) -> Stages:
    # Every item is the first conjunct once; the same-set neighbor supplies the
    # second compatible food item.
    return stages(
        f"Does the meal include {x} and {y}?", f"Yes, the meal includes {x} and {y}.",
        f"No, the meal doesn't include {x} and {y}.", "What does the meal include?",
        f"The meal includes {x} and {y}.",
        f"Does the meal include {x} and {y}, or fruit and vegetables?", f"The meal includes {x} and {y}.")


@register(21)
def l021(s: int, x: str, y: str, i: int) -> Stages:
    on = {"shelf", "desk", "tray"}
    px, py = ("on" if x in on else "in"), ("on" if y in on else "in")
    return stages(
        f"Is the key {px} the {x}?", f"Yes, the key is {px} the {x}, and Maya is at the {x}.",
        f"No, the key isn't {px} the {x}.", "Where is the key?", f"The key is {px} the {x}.",
        f"Is the key {px} the {x} or {py} the {y}?", f"The key is {px} the {x}, and Maya is at the {x}.")


@register(22)
def l022(s: int, x: str, y: str, i: int) -> Stages:
    prep = "in" if s == 1 and x != "night" else "at" if s == 3 or x == "night" else "on"
    prepy = "in" if s == 1 and y != "night" else "at" if s == 3 or y == "night" else "on"
    return stages(
        f"Is the class {prep} {x}?", f"Yes, the class is {prep} {x}.",
        f"No, the class isn't {prep} {x}.", "When is the class?", f"The class is {prep} {x}.",
        f"Is the class {prep} {x} or {prepy} {y}?", f"The class is {prep} {x}.")


@register(23)
def l023(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Who is the {x}? Is it Maya?", f"Yes, Maya is the {x}.",
        f"No, Maya isn't the {x}.", "What is Maya's job?", f"Maya is the {x}.",
        f"Who is the {x}, Maya or Leo?", f"Maya is the {x}.")


@register(24)
def l024(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is the bus stop next to the {x}?", f"Yes, the bus stop is next to the {x}.",
        f"No, the bus stop isn't next to the {x}.", "Where is the bus stop?",
        f"The bus stop is next to the {x}.",
        f"Is the bus stop next to the {x} or the {y}?", f"The bus stop is next to the {x}.")


@register(25)
def l025(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Which pattern is on the fabric? Is it the {x} one?", f"Yes, the {x} one is on the fabric.",
        f"No, the {x} one isn't on the fabric.", "Which pattern is on the fabric?",
        f"The {x} one is on the fabric.",
        f"Which one is on the fabric, the {x} pattern or the {y} pattern?", f"The {x} one is on the fabric.")


@register(26)
def l026(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        actions = {"ticket": "buy a ticket", "fare": "pay the fare", "pass": "show a pass", "receipt": "keep the receipt"}
        ax, ay = actions[x], actions[y]
        return stages(
            f"At this station, do people {ax}?", f"Yes, at this station, you {ax}.",
            f"No, at this station, you don't {ax}.",
            f"At this station, what do people do with the {x}?", f"At this station, you {ax}.",
            f"At this station, do people {ax} or {ay}?", f"At this station, you {ax}.")
    prep = lambda z: z if z == "online" else f"at the {z}"
    return stages(
        f"At this station, do people buy tickets {prep(x)}?", f"Yes, at this station, you buy tickets {prep(x)}.",
        f"No, at this station, you don't buy tickets {prep(x)}.",
        "At this station, where do people buy tickets?", f"At this station, you buy tickets {prep(x)}.",
        f"At this station, do people buy tickets {prep(x)} or {prep(y)}?", f"At this station, you buy tickets {prep(x)}.")


@register(27)
def l027(s: int, x: str, y: str, i: int) -> Stages:
    actions = {
        1: {"report": "finish", "form": "complete", "email": "send", "letter": "write"},
        2: {"printer": "use", "computer": "use", "phone": "answer", "file": "open"},
        3: {"meeting": "attend", "deadline": "meet", "task": "finish", "message": "answer"},
    }
    vx, vy = actions[s][x], actions[s][y]
    nx, ny = with_article(x), with_article(y)
    return stages(
        f"Do we have {nx} to {vx}?", f"Yes, we have {nx} to {vx}.",
        f"No, we don't have {nx} to {vx}.", "What do we have to do?",
        f"We have {nx} to {vx}.",
        f"Do we have {nx} to {vx} or {ny} to {vy}?", f"We have {nx} to {vx}.")


@register(28)
def l028(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is {x} part of the exercise session?", f"Yes, {x} is part of the exercise session.",
        f"No, {x} isn't part of the exercise session.", "What is part of the exercise session?",
        f"{x.capitalize()} is part of the exercise session.",
        f"Which is part of the exercise session, {x} or {y}?", f"{x.capitalize()} is part of the exercise session.")


@register(29)
def l029(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        obj, objy, rec = plural(x), plural(y), "Maya"
    else:
        obj, objy, rec = "parcels", "parcels", f"the {x}"
    if s == 1:
        oq = f"Does Niko give {obj} or {objy} to Maya?"
    else:
        oq = f"Does Niko give parcels to the {x} or to the {y}?"
    return stages(
        f"Does Niko give {obj} to {rec}?", f"Yes, Niko gives {obj} to {rec}.",
        f"No, Niko doesn't give {obj} to {rec}.", "Who or what receives the delivery?",
        f"Niko gives {obj} to {rec}.", oq, f"Niko gives {obj} to {rec}.")


@register(30)
def l030(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        comp = {"heavy": "heavier", "light": "lighter", "dense": "denser", "hollow": "more hollow"}[x]
        return stages(
            f"Is object A {comp} than object B?", f"Yes, object A is {comp} than object B.",
            f"No, object A isn't {comp} than object B.", "How does object A compare with object B?",
            f"Object A is {comp} than object B.",
            f"Is object A {comp} than object B, or are they the same?", f"Object A is {comp} than object B.")
    if s == 2:
        return stages(
            f"Is the blue load one {x} heavier than the red load?", f"Yes, the blue load is one {x} heavier than the red load.",
            f"No, the blue load isn't one {x} heavier than the red load.", "How much heavier is the blue load?",
            f"The blue load is one {x} heavier than the red load.",
            f"Is the blue load one {x} or one {y} heavier than the red load?", f"The blue load is one {x} heavier than the red load.")
    facts = {
        "rock": ("heavier", "feather"), "feather": ("lighter", "brick"),
        "brick": ("heavier", "balloon"), "balloon": ("lighter", "rock"),
    }
    comp, other = facts[x]
    return stages(
        f"Is the {x} {comp} than the {other}?", f"Yes, the {x} is {comp} than the {other}.",
        f"No, the {x} isn't {comp} than the {other}.", f"How does the {x} compare with the {other}?",
        f"The {x} is {comp} than the {other}.",
        f"Is the {x} {comp} than the {other}, or are they the same weight?", f"The {x} is {comp} than the {other}.")


@register(31)
def l031(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        phrase = f"the highest {x} in the group"
        return stages(
            f"Is Feature A {phrase}?", f"Yes, Feature A is {phrase}.", f"No, Feature A isn't {phrase}.",
            f"Which is the highest {x} in the group?", f"Feature A is {phrase}.",
            f"Is Feature A or Feature B the highest {x} in the group?", f"Feature A is {phrase}.")
    if s == 2:
        sup = {"steep": "steepest", "gentle": "gentlest", "rocky": "rockiest", "snowy": "snowiest"}[x]
        return stages(
            f"Is Route A the {sup} route in the group?", f"Yes, Route A is the {sup} route in the group.",
            f"No, Route A isn't the {sup} route in the group.", f"Which route is the {sup}?",
            f"Route A is the {sup} route in the group.",
            f"Is Route A or Route B the {sup} route?", f"Route A is the {sup} route in the group.")
    sup = {"ridge": "longest", "valley": "deepest", "plateau": "largest", "pass": "lowest"}[x]
    return stages(
        f"Is Feature A the {sup} {x} in the picture?", f"Yes, Feature A is the {sup} {x} in the picture.",
        f"No, Feature A isn't the {sup} {x} in the picture.", f"Which is the {sup} {x}?",
        f"Feature A is the {sup} {x} in the picture.",
        f"Is Feature A or Feature B the {sup} {x}?", f"Feature A is the {sup} {x} in the picture.")


@register(32)
def l032(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Did Priya repair the {x} yesterday?", f"Yes, Priya repaired the {x} yesterday.",
        f"No, Priya didn't repair the {x} yesterday.", "What did Priya repair yesterday?",
        f"Priya repaired the {x} yesterday.",
        f"Did Priya repair the {x} or the {y} yesterday?", f"Priya repaired the {x} yesterday.")


@register(33)
def l033(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{x} the kayak", f"{y} the kayak"
    else:
        nx = x if x == "tools" else with_article(x)
        ny = y if y == "tools" else with_article(y)
        px, py = f"rent {nx}", f"rent {ny}"
    return stages(
        f"Did Omar decide to {px}?", f"Yes, Omar decided to {px}.",
        f"No, Omar didn't decide to {px}.", "What did Omar decide to do?",
        f"Omar decided to {px}.",
        f"Did Omar decide to {px} or to {py}?", f"Omar decided to {px}.")


@register(34)
def l034(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        px = f"painting {with_article(x)}"
        py = f"painting {with_article(y)}"
    else:
        px, py = f"{x} landscapes", f"{y} landscapes"
    return stages(
        f"Does Mei enjoy {px}?", f"Yes, Mei enjoys {px}.", f"No, Mei doesn't enjoy {px}.",
        "What does Mei enjoy doing?", f"Mei enjoys {px}.",
        f"Does Mei enjoy {px} or {py}?", f"Mei enjoys {px}.")


@register(35)
def l035(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"use the {x} to reach the roof", f"use the {y} to reach the roof"
    elif s == 2:
        px, py = f"use the ladder to reach the {x}", f"use the ladder to reach the {y}"
    else:
        objects = {"reach": "the roof", "climb": "to the roof", "inspect": "the roof", "paint": "the roof"}
        px, py = f"use the ladder to {x} {objects[x]}", f"use the ladder to {y} {objects[y]}"
    return stages(
        f"Did they {px}?", f"Yes, they {past(px.split()[0]) + px[len(px.split()[0]):]}.",
        f"No, they didn't {px}.", "Why did they use the access equipment?",
        f"They {past(px.split()[0]) + px[len(px.split()[0]):]}.",
        f"Did they {px} or {py}?", f"They {past(px.split()[0]) + px[len(px.split()[0]):]}.")


@register(36)
def l036(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"open the {x}", f"open the {y}"
    else:
        px, py = f"{x} the report", f"{y} the report"
        if s == 3:
            px, py = f"{x} the file", f"{y} the file"
    if i % 2 == 0:
        return stages(
            f"Does the manager want Hana to {px}?", f"Yes, the manager wants Hana to {px}.",
            f"No, the manager doesn't want Hana to {px}.", "What does the manager want Hana to do?",
            f"The manager wants Hana to {px}.",
            f"Does the manager want Hana to {px} or to {py}?", f"The manager wants Hana to {px}.")
    return stages(
        f"Did the manager ask Hana to {px}?", f"Yes, the manager asked Hana to {px}.",
        f"No, the manager didn't ask Hana to {px}.", "What did the manager ask Hana to do?",
        f"The manager asked Hana to {px}.",
        f"Did the manager ask Hana to {px} or to {py}?", f"The manager asked Hana to {px}.")


@register(37)
def l037(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        item = x if x in {"gloves", "goggles"} else with_article(x)
        itemy = y if y in {"gloves", "goggles"} else with_article(y)
        px, py = f"wear {item}", f"wear {itemy}"
    else:
        objects = {"wear": "a badge", "touch": "the controls", "enter": "through the gate", "smoke": "inside",
                   "wait": "in line", "stop": "at the sign", "pay": "at the desk", "sign": "the form"}
        px, py = f"{x} {objects[x]}", f"{y} {objects[y]}"
    return stages(
        f"Must visitors {px}?", f"Yes, visitors must {px}.",
        f"No, visitors mustn't {px}.", "What must visitors do?", f"Visitors must {px}.",
        f"Must visitors {px} or {py}?", f"Visitors must {px}.")


@register(38)
def l038(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        actions = {"passport": "carry a passport", "visa": "obtain a visa", "permit": "show a permit", "customs": "pass through customs"}
        px, py = actions[x], actions[y]
    elif s == 2:
        px, py = f"go to the {x}", f"go to the {y}"
    else:
        objects = {"enter": "the country", "leave": "the country", "cross": "the border", "renew": "the passport"}
        px, py = f"{x} {objects[x]}", f"{y} {objects[y]}"
    return stages(
        f"Does Mina have to {px}?", f"Yes, Mina has to {px}.",
        f"No, Mina doesn't have to {px}.", "What has Mina got to do?", f"Mina has got to {px}.",
        f"Did Mina have to {px} or {py}?", f"Mina had to {px}.")


@register(39)
def l039(s: int, x: str, y: str, i: int) -> Stages:
    actions = {"carry": "carry your suitcase", "lift": "lift this box", "hold": "hold the door", "move": "move this bag",
               "door": "open the door", "window": "open the window", "taxi": "call a taxi", "seat": "save a seat"}
    if s == 1:
        px, py = actions[x], actions[y]
    elif s == 2:
        px, py = f"carry your {x}", f"carry your {y}"
    else:
        px, py = actions[x], actions[y]
    return stages(
        f"Shall I {px}?", f"Yes, please {px}.", f"No, please don't {px}.",
        "What can I offer to do?", f"Shall I {px}?",
        f"Shall I {px} or {py}?", f"Please {px}.")


@register(40)
def l040(s: int, x: str, y: str, i: int) -> Stages:
    verb = "identify" if s < 3 else "recognize"
    return stages(
        f"Could Ada {verb} the {x} at six?", f"Yes, Ada could {verb} the {x} at six.",
        f"No, Ada couldn't {verb} the {x} at six.", f"What could Ada {verb} at six?",
        f"Ada could {verb} the {x} at six.",
        f"Could Ada {verb} the {x} or the {y} at six?", f"Ada could {verb} the {x} at six.")


@register(41)
def l041(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        clause, clausey = f"Sara {x} practises music", f"Sara {y} practises music"
    elif s == 2:
        clause, clausey = f"Sara has {x} missed practice", f"Sara has {y} missed practice"
    else:
        clause, clausey = f"Sara practises music {x}", f"Sara practises music {y}"
    return stages(
        f"Does the schedule show that {clause}?", f"Yes, {clause}.",
        f"No, it isn't true that {clause}.", "How often does Sara practise music?",
        f"{clause[0].upper() + clause[1:]}.",
        f"Does the schedule show that {clause} or that {clausey}?", f"{clause[0].upper() + clause[1:]}.")


@register(42)
def l042(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Did Jun carry the glass {x}?", f"Yes, Jun carried the glass {x}.",
        f"No, Jun didn't carry the glass {x}.", "How did Jun carry the glass?",
        f"Jun carried the glass {x}.",
        f"Did Jun carry the glass {x} or {y}?", f"Jun carried the glass {x}.")


@register(43)
def l043(s: int, x: str, y: str, i: int) -> Stages:
    comp = {"quickly": "more quickly", "slowly": "more slowly", "early": "earlier", "late": "later",
            "rapidly": "more rapidly", "steadily": "more steadily", "promptly": "more promptly", "gradually": "more gradually"}[x]
    return stages(
        f"Did Ava finish {comp} than Ben?", f"Yes, Ava finished {comp} than Ben.",
        f"No, Ava didn't finish {comp} than Ben.", "How did Ava finish compared with Ben?",
        f"Ava finished {comp} than Ben.",
        f"Did Ava or Ben finish {comp}?", f"Ava finished {comp} than Ben.")


@register(44)
def l044(s: int, x: str, y: str, i: int) -> Stages:
    forms = {
        "good": ("Ava's result was good", "it was the best result"),
        "well": ("Ava performed well", "she performed best"),
        "bad": ("Ava's result was bad", "it was the worst result"),
        "badly": ("Ava performed badly", "she performed worst"),
        "quick": ("Ava's finish was quick", "it was the quickest finish"),
        "quickly": ("Ava finished quickly", "she finished most quickly"),
        "slow": ("Ava's finish was slow", "it was the slowest finish"),
        "slowly": ("Ava finished slowly", "she finished most slowly"),
        "early": ("Ava arrived early", "she arrived earliest"),
        "late": ("Ava arrived late", "she arrived latest"),
        "steadily": ("Ava moved steadily", "she moved most steadily"),
        "smoothly": ("Ava moved smoothly", "she moved most smoothly"),
    }
    base, extreme = forms[x]
    full = f"{base}; {extreme} of the three"
    cap = full[0].upper() + full[1:]
    return stages(
        f"Was this description true of Ava: {full}?", f"Yes, {full}.", f"No, it wasn't true that {full}.",
        "What was true of Ava's performance?", f"{cap}.",
        "Was that description true of Ava or Ben?", f"{cap}.")


@register(45)
def l045(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        reason, reason_y = f"there was {x}", f"there was {y}"
        main = "Ravi stayed home"
    elif s == 2:
        subjects = {"cold": "the air", "dark": "the sky", "cloudy": "the sky", "slippery": "the path"}
        reason, reason_y = f"{subjects[x]} was {x}", f"{subjects[y]} was {y}"
        main = "Ravi turned back"
    else:
        reasons = {"freeze": "the water was freezing", "shiver": "he was shivering", "slip": "people were slipping", "stay": "he was staying late"}
        reason, reason_y = reasons[x], reasons[y]
        main = "Ravi went inside"
    base_main = {"Ravi stayed home": "stay home", "Ravi turned back": "turn back", "Ravi went inside": "go inside"}[main]
    return stages(
        f"Did Ravi {base_main} because {reason}?", f"Yes, {main} because {reason}.",
        f"No, Ravi didn't {base_main} because {reason}.", "Why did Ravi do that?",
        f"{main} because {reason}.",
        f"Did Ravi {base_main} because {reason} or because {reason_y}?", f"{main} because {reason}.")


@register(46)
def l046(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        event = {"snow": "snow fell", "ice": "ice formed", "frost": "frost formed", "hail": "hail fell"}[x]
        eventy = {"snow": "snow fell", "ice": "ice formed", "frost": "frost formed", "hail": "hail fell"}[y]
        return stages(
            f"Why is the ground white? Is it because {event}?", f"Yes, the ground is white because {event}.",
            f"No, the ground isn't white because {event}.", "Why is the ground white?",
            f"The ground is white because {event}.",
            f"Why is the ground white, because {event} or because {eventy}?", f"The ground is white because {event}.")
    if s == 2:
        pairs = {"melt": ("ice", "gets warm"), "freeze": ("water", "gets cold"), "fall": ("snow", "forms in clouds"), "form": ("frost", "surfaces cool")}
        subj, cond = pairs[x]
        return stages(
            f"When does {subj} {x}? Does it {x} when it {cond}?", f"Yes, {subj} {third(x)} when it {cond}.",
            f"No, {subj} doesn't {x} when it {cond}.", f"When does {subj} {x}?",
            f"{subj.capitalize()} {third(x)} when it {cond}.",
            f"Does {subj} {x} when it {cond} or at another time?", f"{subj.capitalize()} {third(x)} when it {cond}.")
    phrase = "at night" if x == "night" else f"in the {x}"
    phrasey = "at night" if y == "night" else f"in the {y}"
    return stages(
        f"When does frost form? Does it form {phrase}?", f"Yes, frost forms {phrase}.",
        f"No, frost doesn't form {phrase}.", "When does frost form?", f"Frost forms {phrase}.",
        f"Does frost form {phrase} or {phrasey}?", f"Frost forms {phrase}.")


@register(47)
def l047(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        head, rel, rely = x, "speaks Arabic", "doesn't speak Arabic"
    elif s == 2:
        head, rel, rely = "guide", f"has {with_article(x)}", f"has {with_article(y)}"
    else:
        vx = "speaks" if x in {"Arabic", "French"} else "knows"
        vy = "speaks" if y in {"Arabic", "French"} else "knows"
        head, rel, rely = "guide", f"{vx} {x}", f"{vy} {y}"
    return stages(
        f"Is Mira the {head} who {rel}?", f"Yes, Mira is the {head} who {rel}.",
        f"No, Mira isn't the {head} who {rel}.", f"Which {head} is Mira?",
        f"Mira is the {head} who {rel}.",
        f"Is Mira the {head} who {rel} or the {head} who {rely}?", f"Mira is the {head} who {rel}.")


@register(48)
def l048(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        rel, rely = f"shows {x}", f"shows {y}"
    else:
        nx = x if x == "symbols" else f"a {x}"
        ny = y if y == "symbols" else f"a {y}"
        rel, rely = f"includes {nx}", f"includes {ny}"
    return stages(
        f"Is this the map which {rel}?", f"Yes, this is the map which {rel}.",
        f"No, this isn't the map which {rel}.", "Which map should we use?",
        f"We should use the map which {rel}.",
        f"Should we use the map which {rel} or the map which {rely}?", f"We should use the map which {rel}.")


@register(49)
def l049(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        head, rel, rely = "square", f"the {x} is located", f"the {y} is located"
    else:
        head, rel, rely = x, "we meet", f"we meet at the {y}"
    return stages(
        f"Is the {head} where {rel} our meeting point?", f"Yes, the {head} where {rel} is our meeting point.",
        f"No, the {head} where {rel} isn't our meeting point.", "Which place is our meeting point?",
        f"The {head} where {rel} is our meeting point.",
        (f"Is our meeting point the {head} where {rel} or the square where {rely}?" if s == 1 else
         f"Is our meeting point the {x} where we meet or the {y} where we meet?"),
        f"The {head} where {rel} is our meeting point.")


@register(50)
def l050(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        subj, desc, descy = "hostel", x, y
        ans = f"the hostel was {x}"
        neg = f"the hostel wasn't {x}"
    elif s == 2:
        subj, desc, descy = "hostel", f"full of a low {x}", f"full of a low {y}"
        ans = f"the hostel was full of a low {x}"
        neg = f"the hostel wasn't full of a low {x}"
    else:
        subj, desc, descy = x, "quiet", "noisy"
        ans = f"the {x} was quiet"
        neg = f"the {x} wasn't quiet"
    cap = ans[0].upper() + ans[1:]
    return stages(
        f"What was the {subj} like? Was it {desc}?", f"Yes, {ans}.", f"No, {neg}.",
        f"What was the {subj} like?", f"{cap}.",
        f"What was the {subj} like, {desc} or {descy}?", f"{cap}.")


@register(51)
def l051(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"What's the matter with the printer? Is it {x}?", f"Yes, the printer is {x}.",
        f"No, the printer isn't {x}.", "What's the matter with the printer?",
        f"The printer is {x}.",
        f"What's the matter with the printer? Is it {x} or {y}?", f"The printer is {x}.")


@register(52)
def l052(s: int, x: str, y: str, i: int) -> Stages:
    def suggestion(z: str) -> str:
        if s in {1, 2}:
            return with_article(z)
        return z
    sx, sy = suggestion(x), suggestion(y)
    opener = "What about" if i % 2 else "How about"
    return stages(
        f"{opener} {sx}?", f"Yes. {opener} {sx}? That is a good suggestion.",
        f"No. Let's not choose {sx}.", "What could we suggest?", f"{opener} {sx}?",
        f"Should we suggest {sx} or {sy}?", f"{opener} {sx}?")


@register(53)
def l053(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        events = {"alarm": "the alarm rang", "siren": "the siren sounded", "smoke": "smoke appeared", "fire": "the fire started"}
        ex, ey = events[x], events[y]
        action = "Lia called Maya"
    elif s == 2:
        acts = {"call": "called Maya", "leave": "left the building", "warn": "warned Maya", "wait": "waited outside"}
        ex, ey = "the alarm rang", "the alarm rang"
        action = f"Lia {acts[x]}"
    else:
        acts = {"firefighter": "called the firefighter", "ambulance": "called an ambulance", "exit": "went to the exit", "shelter": "went to the shelter"}
        ex, ey = "the alarm rang", "the alarm rang"
        action = f"Lia {acts[x]}"
    verb_phrase = action.split(" ", 1)[1]
    base_phrase = verb_phrase.replace("called", "call", 1).replace("left", "leave", 1).replace("warned", "warn", 1).replace("waited", "wait", 1).replace("went", "go", 1)
    if s == 1:
        oq = f"Did Lia call Maya when {ex} or when {ey}?"
    else:
        next_action = ({"call": "called Maya", "leave": "left the building", "warn": "warned Maya", "wait": "waited outside"} if s == 2 else
                       {"firefighter": "called the firefighter", "ambulance": "called an ambulance", "exit": "went to the exit", "shelter": "went to the shelter"})[y]
        next_base = next_action.replace("called", "call", 1).replace("left", "leave", 1).replace("warned", "warn", 1).replace("waited", "wait", 1).replace("went", "go", 1)
        oq = f"Did Lia {base_phrase} or {next_base} when the alarm rang?"
    return stages(
        f"Did Lia {base_phrase} when {ex}?", f"Yes, {action} when {ex}.",
        f"No, Lia didn't {base_phrase} when {ex}.",
        f"What did Lia do when {ex}?", f"{action} when {ex}.", oq, f"{action} when {ex}.")


@register(54)
def l054(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Did Ken go for a {x}?", f"Yes, Ken went for a {x}.", f"No, Ken didn't go for a {x}.",
        "What did Ken do outside?", f"Ken went for a {x}.",
        f"Did Ken go for a {x} or a {y}?", f"Ken went for a {x}.")


@register(55)
def l055(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        nx, ny, subj = with_article(x), with_article(y), "this instrument"
    else:
        nx = "a string" if x == "strings" else with_article(x)
        ny = "a string" if y == "strings" else with_article(y)
        subj = "this part"
    return stages(
        f"Is {subj} called {nx}?", f"Yes, {subj} is called {nx}.",
        f"No, {subj} isn't called {nx}.", f"What is {subj} called?",
        f"{subj.capitalize()} is called {nx}.",
        f"Is {subj} called {nx} or {ny}?", f"{subj.capitalize()} is called {nx}.")


@register(56)
def l056(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is Pavel good at {x}?", f"Yes, Pavel is good at {x}.", f"No, Pavel isn't good at {x}.",
        "What is Pavel good at?", f"Pavel is good at {x}.",
        f"Is Pavel good at {x} or {y}?", f"Pavel is good at {x}.")


@register(57)
def l057(s: int, x: str, y: str, i: int) -> Stages:
    phrases = {"upstairs": "upstairs", "downstairs": "downstairs", "above": "above the shelf", "below": "below the shelf",
               "over": "over the desk", "under": "under the desk", "top": "at the top", "bottom": "at the bottom"}
    px, py = phrases[x], phrases[y]
    verb = "think" if i % 2 == 0 else "know"
    return stages(
        f"Do you {verb} the parcel is {px}?", f"Yes, I {verb} the parcel is {px}.",
        f"No, I don't {verb} the parcel is {px}.", f"What do you {verb}?", f"I {verb} the parcel is {px}.",
        f"Do you {verb} the parcel is {px} or {py}?", f"I {verb} the parcel is {px}.")


@register(58)
def l058(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        subj, pred = "Inez", x
        subjy, predy = "Inez", y
    else:
        subjects = {"raining": "it", "ringing": "the phone", "arriving": "the ferry", "leaving": "the ferry"}
        subj, pred = subjects[x], x
        subjy, predy = subjects[y], y
    be = "was"
    return stages(
        f"Was {subj} {pred} when the lights went out?", f"Yes, {subj} was {pred} when the lights went out.",
        f"No, {subj} wasn't {pred} when the lights went out.", "What was happening when the lights went out?",
        f"{subj[0].upper() + subj[1:]} was {pred} when the lights went out.",
        f"Was {subj} {pred}, or was {subjy} {predy}, when the lights went out?", f"{subj[0].upper() + subj[1:]} was {pred} when the lights went out.")


@register(59)
def l059(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Has Tom repaired the {x}?", f"Yes, Tom has repaired the {x}.", f"No, Tom hasn't repaired the {x}.",
        "What has Tom repaired?", f"Tom has repaired the {x}.",
        f"Has Tom repaired the {x} or the {y}?", f"Tom has repaired the {x}.")


@register(60)
def l060(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        px, py = f"plant {plural(x)}", f"plant {plural(y)}"
    else:
        nx = f"the {x}" if x != "weed" else "a weed"
        ny = f"the {y}" if y != "weed" else "a weed"
        px, py = f"remove {nx}", f"remove {ny}"
    return stages(
        f"Is Noor going to {px}?", f"Yes, Noor is going to {px}.",
        f"No, Noor isn't going to {px}.", "What is Noor going to do?", f"Noor is going to {px}.",
        f"Is Noor going to {px} or {py}?", f"Noor is going to {px}.")


@register(61)
def l061(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        acts = {"call": "call Maya", "visit": "visit Maya", "meet": "meet Maya", "travel": "travel tomorrow"}
        px, py = acts[x], acts[y]
    elif s == 2:
        acts = {"help": "help Maya", "carry": "carry the bags", "cook": "cook dinner", "pay": "pay the bill"}
        px, py = acts[x], acts[y]
    else:
        prep = lambda z: f"on {z}" if z == "Monday" else z
        px, py = f"call Maya {prep(x)}", f"call Maya {prep(y)}"
    return stages(
        f"Will you {px}?", f"Yes, I will {px}.", f"No, I won't {px}.",
        "What will you do?", f"I will {px}.",
        f"Will you {px} or {py}?", f"I will {px}.")


@register(62)
def l062(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        preds = {"early": "arrive early", "late": "arrive late", "on time": "arrive on time", "delayed": "be delayed"}
        px, py = preds[x], preds[y]
        subj = "train"
    elif s == 2:
        px, py = f"{x} late", f"{y} late"
        subj = "train"
    else:
        px, py = "arrive late", "arrive late"
        subj = x
    modal = "may" if i % 2 == 0 else "might"
    return stages(
        f"{modal.capitalize()} the {subj} {px}?", f"Yes, the {subj} {modal} {px}.",
        f"No, the {subj} {modal} not {px}.", f"What {modal} happen to the {subj}?",
        f"The {subj} {modal} {px}.",
        (f"{modal.capitalize()} the {subj} {px} or {py}?" if s < 3 else f"{modal.capitalize()} the {x} or the {y} arrive late?"),
        f"The {subj} {modal} {px}.")


@register(63)
def l063(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        px, py = f"visit the {x}", f"visit the {y}"
    else:
        acts = {"hike": "go for a hike", "picnic": "have a picnic", "boat ride": "take a boat ride", "city tour": "take a city tour"}
        px, py = acts[x], acts[y]
    return stages(
        f"Could we {px}?", f"Yes, we could {px}.", f"No, we couldn't {px}.",
        "What could we do this afternoon?", f"We could {px}.",
        f"Shall we {px} or {py}?", f"We could {px}.")


@register(64)
def l064(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"back up the {x}", f"back up the {y}"
    elif s == 2:
        acts = {"copy": "make a copy", "backup": "create a backup", "drive": "use a backup drive", "cloud": "use the cloud"}
        px, py = acts[x], acts[y]
    else:
        px, py = f"{x} the file", f"{y} the file"
    return stages(
        f"Should I {px}?", f"Yes, you should {px}.", f"No, you shouldn't {px}.",
        "What should I do?", f"You should {px}.",
        f"Should I {px} or {py}?", f"You should {px}.")


@register(65)
def l065(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        clauses = {"library": ("The library is open", "isn't it"), "librarian": ("The librarian is here", "isn't she"),
                   "book": ("The book is on the shelf", "isn't it"), "shelf": ("The shelf is full", "isn't it")}
        clause, tag = clauses[x]
    elif s == 2:
        clause, tag = f"The library is {x}", "isn't it"
    else:
        objs = {"borrow": "the book", "return": "the book", "read": "the book", "study": "here"}
        clause, tag = f"Maya {third(x)} {objs[x]}", "doesn't she"
    tagged = f"{clause}, {tag}?"
    if s == 1 and x == "librarian":
        negative = "No, the librarian isn't here."
    elif s < 3:
        negative = f"No, the {('library' if s == 2 else x)} isn't {x if s == 2 else ('open' if x == 'library' else 'as described')}."
    else:
        negative = f"No, Maya doesn't {x} {objs[x]}."
    return stages(
        tagged, f"Yes, {clause[0].lower() + clause[1:]}.", negative,
        "How can you check that assumption with a tag question?", tagged,
        f"Do you check the assumption by saying “{tag}” or by making a new statement?", tagged)


@register(66)
def l066(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"submitted the {x}", f"submitted the {y}"
    elif s == 2:
        acts = {"deadline": "met the deadline", "target": "reached the target", "milestone": "reached the milestone", "limit": "reached the limit"}
        px, py = acts[x], acts[y]
    else:
        acts = {"submit": "submitted the form", "finish": "finished the report", "miss": "missed the deadline", "reach": "reached the target"}
        px, py = acts[x], acts[y]
    return stages(
        f"Has Uma already {px}?", f"Yes, Uma has already {px}.",
        f"No, Uma hasn't {px} yet.", "What has Uma just done?", f"Uma has just {px}.",
        f"Has Uma already {px}, or has she only {py}?", f"Uma has already {px}.")


@register(67)
def l067(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        facts = {"slippery": ("the path was slippery", "the hiker slipped"), "rough": ("the surface was rough", "the shoe gripped"),
                 "smooth": ("the surface was smooth", "the box slid"), "sticky": ("the tape was sticky", "the label stayed on")}
    elif s == 2:
        facts = {"ice": ("there was ice on the path", "the hiker slipped"), "sand": ("there was sand on the path", "the shoe gripped"),
                 "rubber": ("the tire was rubber", "it gripped the road"), "oil": ("there was oil on the floor", "the worker slipped")}
    else:
        facts = {"slide": ("the ice was smooth", "the sled slid"), "grip": ("the rubber was rough", "the tire gripped"),
                 "slip": ("there was oil on the floor", "the worker slipped"), "stop": ("the brake worked", "the bicycle stopped")}
    cause, result = facts[x]
    capcause = cause[0].upper() + cause[1:]
    result_base = result.replace("slipped", "slip", 1).replace("gripped", "grip", 1).replace("slid", "slide", 1).replace("stayed", "stay", 1).replace("stopped", "stop", 1)
    return stages(
        f"Did this happen: {cause}, so {result}?", f"Yes. {capcause}, so {result}.",
        f"No, it didn't happen that {cause}, so {result}.", "What was the result?",
        f"{capcause}, so {result}.",
        f"Did {result_base}, or did nothing happen, because {cause}?", f"{capcause}, so {result}.")


@register(68)
def l068(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        rules = {"solid": ("a solid gets warm enough", "it melts"), "liquid": ("a liquid gets cold enough", "it freezes"),
                 "gas": ("a gas cools enough", "it condenses"), "vapor": ("vapor cools enough", "it condenses")}
    elif s == 2:
        rules = {"melt": ("ice gets warm", "it melts"), "freeze": ("water gets cold", "it freezes"),
                 "boil": ("water reaches its boiling point", "it boils"), "condense": ("steam cools", "it condenses")}
    else:
        rules = {"ice": ("ice gets warm", "it melts"), "water": ("water gets cold enough", "it freezes"),
                 "steam": ("steam cools", "it condenses"), "wax": ("wax gets warm", "it melts")}
    cond, result = rules[x]
    base = result[3:]
    base = {"melts": "melt", "freezes": "freeze", "condenses": "condense", "boils": "boil"}.get(base, base)
    return stages(
        f"If {cond}, does it {base}?", f"Yes, if {cond}, {result}.",
        f"No, if {cond}, it does not {base}.",
        f"What happens if {cond}?", f"If {cond}, {result}.",
        f"If {cond}, does it {base}, or does it stay unchanged?", f"If {cond}, {result}.")


@register(69)
def l069(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        bex, bey = ("are" if x == "glasses" else "is"), ("are" if y == "glasses" else "is")
        px, py = f"know where the {x} {bex}", f"know where the {y} {bey}"
    elif s == 2:
        forms = {"remember": "remember where the key is", "forget": "forget where the key is",
                 "remind": "remind me where the key is", "recall": "recall where the key is"}
        px, py = forms[x], forms[y]
    else:
        px, py = f"use the {x} to remember where the key is", f"use the {y} to remember where the key is"
    return stages(
        f"Does Maya {px}?", f"Yes, Maya does {px}.", f"No, Maya doesn't {px}.",
        "What place information does Maya have?", f"Maya does {px}.",
        f"Does Maya {px} or {py}?", f"Maya does {px}.")


@register(70)
def l070(s: int, x: str, y: str, i: int) -> Stages:
    facts = {
        "lock": ("lock the door after the guests left", "locked the door after the guests left"),
        "unlock": ("unlock the door before the guests arrived", "unlocked the door before the guests arrived"),
        "enter": ("enter after the owner arrived", "entered after the owner arrived"),
        "leave": ("leave after the meeting ended", "left after the meeting ended"),
        "wash": ("wash the dishes before drying them", "washed the dishes before drying them"),
        "dry": ("dry the dishes after washing them", "dried the dishes after washing them"),
        "cook": ("cook the rice before eating it", "cooked the rice before eating it"),
        "eat": ("eat the rice after cooking it", "ate the rice after cooking it"),
        "wake": ("wake before getting dressed", "woke before getting dressed"),
        "dress": ("dress before traveling", "dressed before traveling"),
        "travel": ("travel before arriving", "traveled before arriving"),
        "arrive": ("arrive after traveling", "arrived after traveling"),
    }
    base, px = facts[x]
    basey, py = facts[y]
    return stages(
        f"Did Sol {base}?", f"Yes, Sol {px}.", f"No, Sol didn't {base}.",
        "What did Sol do, and in what order?", f"Sol {px}.",
        f"Did Sol {base}, or did Sol {basey}?", f"Sol {px}.")


@register(71)
def l071(s: int, x: str, y: str, i: int) -> Stages:
    sense = {1: "taste", 2: "feel", 3: "sound", 4: "smell"}[s]
    subject = {1: "drink", 2: "surface", 3: "instrument", 4: "flower"}[s]
    return stages(
        f"Does the {subject} {sense} like something {x}?", f"Yes, the {subject} {sense}s like something {x}.",
        f"No, the {subject} doesn't {sense} like something {x}.", f"What does the {subject} {sense} like?",
        f"The {subject} {sense}s like something {x}.",
        f"Does the {subject} {sense} like something {x} or something {y}?", f"The {subject} {sense}s like something {x}.")


@register(72)
def l072(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Does this music make Elena {x}?", f"Yes, this music makes Elena {x}.",
        f"No, this music doesn't make Elena {x}.", "How does this music make Elena feel?",
        f"This music makes Elena {x}.",
        f"Does this music make Elena {x} or {y}?", f"This music makes Elena {x}.")


@register(73)
def l073(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        return stages(
            f"What time does the {x} show? Does it show 7:15?", f"Yes, the {x} shows 7:15.",
            f"No, the {x} doesn't show 7:15.", f"What time does the {x} show?", f"The {x} shows 7:15.",
            f"What time does the {x} show, 7:15 or 7:30?", f"The {x} shows 7:15.")
    return stages(
        f"What time does the train leave? Does it leave at {x}?", f"Yes, the train leaves at {x}.",
        f"No, the train doesn't leave at {x}.", "What time does the train leave?", f"The train leaves at {x}.",
        f"What time does the train leave, {x} or {y}?", f"The train leaves at {x}.")


@register(74)
def l074(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        return stages(
            f"We have the bowl. Do we need {x} too?", f"Yes, we need {x}. What else do we need?",
            f"No, we don't need {x}. What else do we need?", f"How do you request another ingredient after adding {x}?",
            f"We have {x}. What else do we need?",
            f"Do we need {x} or {y} next?", f"We need {x} next. What next?")
    gx, gy = gerund(x), gerund(y)
    return stages(
        f"Is {gx} the next step?", f"Yes. Next, {x}. What next?",
        f"No. Don't {x} next. What next?", f"How do you ask for the step after {gx}?",
        f"We have finished {gx}. What next?",
        f"Is {gx} or {gy} the next step?", f"{gx.capitalize()} is next. What next?")


@register(75)
def l075(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Will I see you {x}?", f"Yes, you will see me {x}. See you {x}.",
        f"No, you won't see me before {x}. See you {x}.", "When will I see you?",
        f"You will see me {x}. See you {x}.",
        f"Will I see you {x} or {y}?", f"You will see me {x}. See you {x}.",
        nq=f"Will I see you before {x}?")


@register(76)
def l076(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        line, liney = f"{x.capitalize()}, Maya", f"{y.capitalize()}, Maya"
        context = "greet"
    elif s == 2:
        line, liney = f"{x.capitalize()}, Maya", f"{y.capitalize()}, Maya"
        context = "respond to Maya at the end of their conversation"
    else:
        line, liney = f"Good morning, {x} Patel", f"Good morning, {y} Patel"
        context = "greet"
    return stages(
        f"Did Leo {context} by saying, “{line}”?", f"Yes, Leo said, “{line},” and Maya responded, “{line.replace('Maya', 'Leo')}.”",
        f"No, Leo didn't {context} by saying, “{line}.”",
        f"What did Leo say to {context}?", f"Leo said, “{line},” and Maya responded, “{line.replace('Maya', 'Leo')}.”",
        f"Did Leo say, “{line},” or “{liney}”?", f"Leo said, “{line},” and Maya responded, “{line.replace('Maya', 'Leo')}.”")


@register(77)
def l077(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1 and x in {"thank you", "thanks"}:
        response = "You're welcome"
        target = x.capitalize()
        fact = f"Leo thanked Maya by saying, “{target},” and Maya replied, “{response}.“"
    elif s == 1:
        fact = f"Leo said, “Thank you,” and Maya replied, “{x.capitalize()}.“"
    elif s == 2:
        action = {"helping": "helping Leo", "sharing": "sharing the tools", "carrying": "carrying the box", "building": "building the shelter"}[x]
        fact = f"Leo said, “Thank you for {action},” and Maya replied, “You're welcome.”"
    else:
        fact = f"Leo thanked the {x} by saying, “Thank you,” and the {x} replied, “You're welcome.”"
    cap = fact[0].upper() + fact[1:]
    return stages(
        f"Did this exchange express thanks: {fact}?", f"Yes. {cap}.",
        f"No, that exchange didn't express thanks: {fact}.", "What exchange expressed thanks?", f"{Cap if False else cap}.",
        f"Did the speakers exchange thanks, or did they complain?", f"{cap}.")


@register(78)
def l078(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        line = f"{x.capitalize()}. I arrived late because the bus was delayed."
    elif s == 2:
        line = f"I'm sorry I was {x}. I understand the problem I caused."
    else:
        explanations = {"delay": "I'm sorry about the delay. The bus arrived late.",
                        "breakdown": "I'm sorry I'm late. A breakdown stopped the bus.",
                        "traffic": "I'm sorry I'm late. Traffic delayed the bus.",
                        "illness": "I'm sorry I was absent. Illness kept me home."}
        line = explanations[x]
    return stages(
        f"Did Leo apologize and explain by saying, “{line}”?", f"Yes, Leo apologized and explained, “{line}”",
        f"No, Leo didn't apologize and explain by saying, “{line}”",
        "What did Leo say to apologize and explain?", f"Leo said, “{line}”",
        f"Did Leo apologize with that explanation or avoid explaining?", f"Leo apologized and explained, “{line}”")


@register(79)
def l079(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        line = x.capitalize()
    elif s == 2:
        lines = {"accept": "I accept your apology", "forgive": "I forgive you", "discuss": "Let's discuss what happened", "resolve": "Let's resolve this together"}
        line = lines[x]
    else:
        line = f"That's all right; we can deal with the {x}"
    return stages(
        f"Did Maya respond to the apology by saying, “{line}”?", f"Yes, Maya responded, “{line}.”",
        f"No, Maya didn't respond to the apology by saying, “{line}.”",
        "What did Maya say in response to the apology?", f"Maya responded, “{line}.”",
        f"Did Maya respond, “{line},” or reject the apology?", f"Maya responded, “{line}.”")


@register(80)
def l080(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        line = f"Your painting is {x}"
    elif s == 2:
        line = f"Your {x} is beautiful"
    else:
        line = f"You are a talented {x}"
    return stages(
        f"Did Leo compliment Maya by saying, “{line}”?", f"Yes, Leo complimented Maya. He said, “{line}.”",
        f"No, Leo didn't compliment Maya by saying, “{line}.”",
        "What did Leo say to compliment Maya?", f"Leo said, “{line}.”",
        f"Did Leo say, “{line},” or criticize Maya?", f"Leo complimented Maya. He said, “{line}.”")


@register(81)
def l081(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        line = x.capitalize()
        fact = f"Maya accepted the compliment and replied, “{line}.“"
    elif s == 2:
        facts = {"accept": "Maya accepted the compliment and said, “Thank you.”",
                 "smile": "Maya smiled and said, “Thank you.”", "thank": "Maya thanked Leo and said, “I appreciate that.”",
                 "reply": "Maya replied, “I'm glad you like it.”"}
        fact = facts[x]
    else:
        fact = f"Maya responded to the compliment about her {x} by saying, “Thank you; I'm glad you like it.”"
    cap = fact[0].upper() + fact[1:]
    return stages(
        f"Did Maya respond graciously: {fact}?", f"Yes. {cap}", f"No, Maya didn't respond graciously in that way.",
        "How did Maya respond to the compliment?", cap,
        "Did Maya respond graciously or reject the compliment?", cap)


@register(82)
def l082(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        line, situation = x.capitalize(), "Maya lost her bicycle"
    elif s == 2:
        situations = {"lost": "Maya said that she had lost her bicycle", "hurt": "Maya said that she was hurt",
                      "sick": "Maya said that she was sick", "disappointed": "Maya said that she was disappointed"}
        situation, line = situations[x], "I'm sorry to hear that"
    else:
        acts = {"listen": "listen to Maya", "comfort": "comfort Maya", "help": "help Maya", "visit": "visit Maya"}
        situation, line = "Maya described a difficult day", f"I'm sorry to hear that. I can {acts[x]}"
    return stages(
        f"After {situation[0].lower() + situation[1:]}, did Leo express sympathy by saying, “{line}”?",
        f"Yes, Leo expressed sympathy. He said, “{line}.”",
        f"No, Leo didn't express sympathy by saying, “{line}.”",
        "What did Leo say to express sympathy?", f"Leo said, “{line}.”",
        f"Did Leo express sympathy by saying, “{line},” or ignore the problem?", f"Leo expressed sympathy. He said, “{line}.”")


@register(83)
def l083(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        subject, material, materialy = "bowl", x, y
    else:
        subject, material, materialy = x, "bamboo", "plastic"
    return stages(
        f"Is the {subject} made of {material}?", f"Yes, the {subject} is made of {material}.",
        f"No, the {subject} isn't made of {material}.", f"What is the {subject} made of?",
        f"The {subject} is made of {material}.",
        f"Is the {subject} made of {material} or {materialy}?", f"The {subject} is made of {material}.")


@register(84)
def l084(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"open the {x}", f"open the {y}"
    elif s == 2:
        objects = {"open": "the door", "close": "the door", "lock": "the gate", "unlock": "the gate"}
        px, py = f"{x} {objects[x]}", f"{y} {objects[y]}"
    else:
        objects = {"slide": "the curtain", "pull": "the curtain", "push": "the door", "lift": "the curtain"}
        px, py = f"{x} {objects[x]}", f"{y} {objects[y]}"
    return stages(
        f"Would you {px}, please?", f"Certainly. I would be happy to {px}.",
        f"Sorry, I wouldn't {px} while it is being repaired.", "What would you like me to do?",
        f"Would you {px}, please?",
        f"Would you {px} or {py}, please?", f"Would you {px}, please?")


@register(85)
def l085(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"ask the {x}", f"ask the {y}"
    elif s == 2:
        acts = {"table": "reserve a table", "menu": "read the menu", "meal": "order the meal", "bill": "check the bill"}
        px, py = acts[x], acts[y]
    else:
        acts = {"reserve": "reserve a table", "order": "order a meal", "serve": "serve the meal", "clean": "clean the table"}
        px, py = acts[x], acts[y]
    return stages(
        f"Ought we to {px}?", f"Yes, we ought to {px}.", f"No, we ought not to {px}.",
        "What ought we to do?", f"We ought to {px}.",
        f"Ought we to {px} or {py}?", f"We ought to {px}.")


@register(86)
def l086(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        nx = x if x == "luggage" else f"the {x}"
        ny = y if y == "luggage" else f"the {y}"
        px, py = f"bring {nx}", f"bring {ny}"
    elif s == 2:
        acts = {"check-in": "complete check-in", "security": "go through security", "gate": "go to the gate", "customs": "go through customs"}
        px, py = acts[x], acts[y]
    else:
        acts = {"bring": "bring the passport", "show": "show the boarding pass", "remove": "remove the belt", "wait": "wait at the gate"}
        px, py = acts[x], acts[y]
    return stages(
        f"Do I need to {px}?", f"Yes, you need to {px}.", f"No, you needn't {px}.",
        "What do I need to do?", f"You need to {px}.",
        f"Do I need to {px} or {py}?", f"You need to {px}.")


@register(87)
def l087(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        px, py = f"keep {plural(x)}", f"keep {plural(y)}"
    else:
        px, py = f"produce {x}", f"produce {y}"
    return stages(
        f"Did Mara use to {px}?", f"Yes, Mara used to {px}.", f"No, Mara didn't use to {px}.",
        "What did Mara use to do?", f"Mara used to {px}.",
        f"Did Mara use to {px} or {py}?", f"Mara used to {px}.")


@register(88)
def l088(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{third(x)} each page", f"{third(y)} each page"
        subj = "scanner"
    elif s == 2:
        subj = "library" if x in {"open", "close"} else "ferry"
        subjy = "library" if y in {"open", "close"} else "ferry"
        px, py = f"{third(x)} at nine", f"{third(y)} at nine"
    else:
        px, py = f"runs {x}", f"runs {y}"
        subj = "scanner"
    return stages(
        f"Does the {subj} {px[:-1] if False else px}?", f"Yes, the {subj} {px}.",
        f"No, the {subj} doesn't {x if s < 3 else 'run'} as described.", "What does the schedule or routine show?",
        f"The {subj} {px}.",
        f"Does the {subj} {px}, or does the {subjy if s == 2 else subj} {py}?", f"The {subj} {px}.")


@register(89)
def l089(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"meeting the {x} tomorrow", f"meeting the {y} tomorrow"
    elif s == 2:
        acts = {"appointment": "attending an appointment tomorrow", "reservation": "making a reservation tomorrow",
                "meeting": "attending a meeting tomorrow", "visit": "making a visit tomorrow"}
        px, py = acts[x], acts[y]
    else:
        prep = lambda z: f"on {z}" if z == "Monday morning" else z
        px, py = f"meeting the architect {prep(x)}", f"meeting the architect {prep(y)}"
    return stages(
        f"Is Zoya {px}?", f"Yes, Zoya is {px}.", f"No, Zoya isn't {px}.",
        "What arrangement has Zoya made?", f"Zoya is {px}.",
        f"Is Zoya {px} or {py}?", f"Zoya is {px}.")


@register(90)
def l090(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        preds = {"move": "wanted to move for a year", "live": "lived here for a year", "stay": "stayed here for a year", "work": "worked here for a year"}
        px, py = preds[x], preds[y]
    elif s == 2:
        px, py = f"lived in the {x} since 2022", f"lived in the {y} since 2022"
    else:
        duration = f"for {x}" if x in {"a year", "a month"} else f"since {x}"
        durationy = f"for {y}" if y in {"a year", "a month"} else f"since {y}"
        px, py = f"lived here {duration}", f"lived here {durationy}"
    return stages(
        f"Has Ian {px}?", f"Yes, Ian has {px}.", f"No, Ian hasn't {px}.",
        "How long has Ian's unfinished situation continued?", f"Ian has {px}.",
        f"Has Ian {px} or {py}?", f"Ian has {px}.")


@register(91)
def l091(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{x} the wall for two hours", f"{y} the wall for two hours"
    elif s == 2:
        px, py = f"painting the {x} for two hours", f"painting the {y} for two hours"
    else:
        duration = f"for {x}" if x in {"one hour", "two days"} else x
        durationy = f"for {y}" if y in {"one hour", "two days"} else y
        px, py = f"painting the wall {duration}", f"painting the wall {durationy}"
    return stages(
        f"Has Mina been {px}?", f"Yes, Mina has been {px}.", f"No, Mina hasn't been {px}.",
        "What has Mina been doing, and for how long?", f"Mina has been {px}.",
        f"Has Mina been {px} or {py}?", f"Mina has been {px}.")


@register(92)
def l092(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        nx = x if x in {"bread", "biscuits"} else with_article(x)
        ny = y if y in {"bread", "biscuits"} else with_article(y)
        px, py = f"bake {nx}", f"bake {ny}"
    elif s == 2:
        px, py = f"use {x}", f"use {y}"
    else:
        acts = {"melt": "let the butter melt", "rise": "let the bread rise", "brown": "let the crust brown", "burn": "let the sugar burn"}
        px, py = acts[x], acts[y]
    return stages(
        f"Was Nina going to {px}?", f"Yes, Nina was going to {px}.", f"No, Nina wasn't going to {px}.",
        "What was Nina going to do?", f"Nina was going to {px}.",
        f"Was Nina going to {px} or {py}?", f"Nina was going to {px}.")


@register(93)
def l093(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{x} to solve", f"{y} to solve"
        subj = "puzzle"
    elif s == 2:
        objects = {"solve": "puzzle", "finish": "jigsaw", "open": "lock", "build": "model"}
        px, py = f"easy to {x}", f"easy to {y}"
        subj = objects[x]
    else:
        actions = {"maze": "solve", "riddle": "solve", "jigsaw": "finish", "lock": "open"}
        px, py = f"easy to {actions[x]}", f"easy to {actions[y]}"
        subj = x
    return stages(
        f"Is the {subj} {px}?", f"Yes, the {subj} is {px}.", f"No, the {subj} isn't {px}.",
        f"What is the {subj} like to work on?", f"The {subj} is {px}.",
        f"Is the {subj} {px} or {py}?", f"The {subj} is {px}.")


@register(94)
def l094(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{x} the crate", f"{y} the crate"
    elif s == 2:
        px, py = f"lift the {x}", f"lift the {y}"
    else:
        px, py = f"make the crate {x}", f"make the crate {y}"
        # Avoid doubling "make" below.
        return stages(
            f"Did the coach {px}?", f"Yes, the coach did {px}.", f"No, the coach didn't {px}.",
            "What did the coach make the crate do?", f"The coach made the crate {x}.",
            f"Did the coach make the crate {x} or {y}?", f"The coach made the crate {x}.")
    return stages(
        f"Did the coach make Rosa {px}?", f"Yes, the coach made Rosa {px}.",
        f"No, the coach didn't make Rosa {px}.", "What did the coach make Rosa do?", f"The coach made Rosa {px}.",
        f"Did the coach make Rosa {px} or {py}?", f"The coach made Rosa {px}.")


@register(95)
def l095(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{gerund(x)} the machine", f"{gerund(y)} the machine"
    elif s == 2:
        px, py = f"repairing {plural(x)}", f"repairing {plural(y)}"
    else:
        px, py = f"finding a {x} part", f"finding a {y} part"
    return stages(
        f"Does Teo rest after {px}?", f"Yes, Teo rests after {px}.",
        f"No, Teo doesn't rest after {px}.", "What does Teo do after the repair step?", f"Teo rests after {px}.",
        f"Does Teo rest after {px} or after {py}?", f"Teo rests after {px}.")


@register(96)
def l096(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{x} repairing radios", f"{y} repairing radios"
    elif s == 2:
        px, py = f"{x} to repair radios", f"{y} to repair radios"
    else:
        px, py = f"enjoy repairing the {x}", f"enjoy repairing the {y}"
    return stages(
        f"Does Lila {px}?", f"Yes, Lila {third(px.split()[0]) + px[len(px.split()[0]):]}.",
        f"No, Lila doesn't {px}.", "What complement does Lila use with the verb?",
        f"Lila {third(px.split()[0]) + px[len(px.split()[0]):]}.",
        f"Does Lila {px} or {py}?", f"Lila {third(px.split()[0]) + px[len(px.split()[0]):]}.")


@register(97)
def l097(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        subj, action, actiony = x, "restored", "cleaned"
    elif s == 2:
        subj, action, actiony = "mural", past(x), past(y)
    else:
        subj, action, actiony = f"{x} mural", "restored", "cleaned"
    return stages(
        f"Was the {subj} {action} last year?", f"Yes, the {subj} was {action} last year.",
        f"No, the {subj} wasn't {action} last year.", f"What was done to the {subj} last year?",
        f"The {subj} was {action} last year.",
        f"Was the {subj} {action} or {actiony} last year?", f"The {subj} was {action} last year.")


@register(98)
def l098(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        acts = {"badge": "worn", "key": "carried", "password": "entered", "pass": "shown"}
        subj, pp, ppy, modal = f"the {x}", acts[x], acts[y], "must"
    elif s == 2:
        forms = {"enter": ("the room", "entered"), "remove": ("the badge", "removed"),
                 "copy": ("the file", "copied"), "share": ("the password", "shared")}
        subj, pp = forms[x]
        ppy = forms[y][1]
        modal = "may"
    else:
        subj, pp, ppy, modal = "access", f"marked {x}", f"marked {y}", "can"
    return stages(
        f"{modal.capitalize()} {subj} be {pp}?", f"Yes, {subj} {modal} be {pp}.",
        f"No, {subj} {modal} not be {pp}.", f"What {modal} be done or marked?",
        f"{subj.capitalize()} {modal} be {pp}.",
        f"{modal.capitalize()} {subj} be {pp} or {ppy}?", f"{subj.capitalize()} {modal} be {pp}.")


@register(99)
def l099(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        vx = past(x)
        vy = past(y)
        px, py = f"{vx} Mina to continue", f"{vy} Mina to continue"
        qx, qy = f"{x} Mina to continue", f"{y} Mina to continue"
        subj = "coach"
    elif s == 2:
        px, py = f"encouraged Mina to {x}", f"encouraged Mina to {y}"
        qx, qy = f"encourage Mina to {x}", f"encourage Mina to {y}"
        subj = "coach"
    else:
        px, py = f"{x} encouraged Mina to continue", f"{y} encouraged Mina to continue"
        qx, qy = f"the {x} encourage Mina to continue", f"the {y} encourage Mina to continue"
        subj = x
    if s == 3:
        return stages(
            f"Did the {x} encourage Mina to continue?", f"Yes, the {x} encouraged Mina to continue.",
            f"No, the {x} didn't encourage Mina to continue.", "Who encouraged Mina to continue?",
            f"The {x} encouraged Mina to continue.",
            f"Did the {x} or the {y} encourage Mina to continue?", f"The {x} encouraged Mina to continue.")
    return stages(
        f"Did the coach {qx}?", f"Yes, the coach {px}.", f"No, the coach didn't {qx}.",
        "What did the coach cause or request Mina to do?", f"The coach {px}.",
        f"Did the coach {qx} or {qy}?", f"The coach {px}.")


@register(100)
def l100(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        nx, ny = with_article(x), with_article(y)
        qx, qy = f"give Leo {nx}", f"give Leo {ny}"
        ax = f"gave Leo {nx}"
        wq = "What did Aya give Leo?"
    elif s == 2:
        qx, qy = f"{x} Leo a postcard", f"{y} Leo a postcard"
        ax = f"{past(x)} Leo a postcard"
        wq = "What did Aya do for Leo with the postcard?"
    else:
        qx, qy = f"give the {x} a postcard", f"give the {y} a postcard"
        ax = f"gave the {x} a postcard"
        wq = "Who did Aya give a postcard to?"
    return stages(
        f"Did Aya {qx}?", f"Yes, Aya {ax}.", f"No, Aya didn't {qx}.", wq, f"Aya {ax}.",
        f"Did Aya {qx} or {qy}?", f"Aya {ax}.")


@register(101)
def l101(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        obj, pp, ppy = x, "repaired", "replaced"
    elif s == 2:
        obj, pp, ppy = "roof", past(x), past(y)
    else:
        obj, pp, ppy = "pipe", f"repaired by the {x}", f"repaired by the {y}"
    return stages(
        f"Did Sam have the {obj} {pp}?", f"Yes, Sam had the {obj} {pp}.",
        f"No, Sam didn't have the {obj} {pp}.", "What did Sam arrange to have done?",
        f"Sam had the {obj} {pp}.",
        f"Did Sam have the {obj} {pp} or {ppy}?", f"Sam had the {obj} {pp}.")


@register(102)
def l102(s: int, x: str, y: str, i: int) -> Stages:
    obj = "jazz" if s < 3 else x
    verb = x if s < 3 else "like"
    other_obj = "jazz" if s < 3 else y
    return stages(
        f"Maya {third(verb)} {obj}. Does Leo agree positively?", f"Yes. Maya {third(verb)} {obj}, and so does Leo.",
        f"No. Maya doesn't {verb} {obj}, and neither does Leo.", "Who else has the same preference?",
        f"Maya {third(verb)} {obj}, and so does Leo.",
        f"Do both Maya and Leo {verb} {obj}, or do they {verb} {other_obj}?", f"Maya {third(verb)} {obj}, and so does Leo.")


@register(103)
def l103(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        base, past_form, obj = "turn off", "turned off", x
        other = y
    else:
        base, past_form, obj = x, past(x.split()[0]) + " " + x.split()[1], "lamp"
        other = "radio"
    verb, particle = base.split()
    pverb = past(verb)
    return stages(
        f"Did Rina {base} the {obj}?", f"Yes, Rina {pverb} the {obj} {particle}; she {pverb} it {particle}.",
        f"No, Rina didn't {base} the {obj}; she didn't {pverb} it {particle}.", f"What did Rina {base}?",
        f"Rina {pverb} the {obj} {particle}; she {pverb} it {particle}.",
        f"Did Rina {base} the {obj} or the {other}?", f"Rina {pverb} the {obj} {particle}; she {pverb} it {particle}.")


@register(104)
def l104(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        px, py, obj = x, y, "puppy"
    else:
        px, py, obj = "look after", "look after", x
    return stages(
        f"Did Bo {px} the {obj}?", f"Yes, Bo {past(px.split()[0]) + px[len(px.split()[0]):]} the {obj}; Bo {past(px.split()[0]) + px[len(px.split()[0]):]} it.",
        f"No, Bo didn't {px} the {obj}; Bo didn't {px} it.", f"What did Bo {px}?",
        f"Bo {past(px.split()[0]) + px[len(px.split()[0]):]} the {obj}; Bo {past(px.split()[0]) + px[len(px.split()[0]):]} it.",
        (f"Did Bo {px} the puppy or {py} the puppy?" if s < 3 else f"Did Bo look after the {x} or the {y}?"),
        f"Bo {past(px.split()[0]) + px[len(px.split()[0]):]} the {obj}; Bo {past(px.split()[0]) + px[len(px.split()[0]):]} it.")


@register(105)
def l105(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        conds = {"rain": "it rains", "snow": "it snows", "thunder": "thunder sounds", "lightning": "lightning strikes"}
        cond, condy = conds[x], conds[y]
        action = "take shelter"
    elif s == 2:
        cond, condy = "it rains", "it rains"
        action = f"take the {x}"
    else:
        cond, condy = "the weather worsens", "the weather worsens"
        action = x
    return stages(
        f"Will Jia {action} if {cond}?", f"Yes, Jia will {action} if {cond}.",
        f"No, Jia won't {action} if {cond}.", f"What will Jia do if {cond}?",
        f"Jia will {action} if {cond}.",
        (f"Will Jia {action} if {cond} or if {condy}?" if s == 1 else f"Will Jia {action} or {y if s == 3 else 'take the ' + y} if {cond}?"),
        f"Jia will {action} if {cond}.")


@register(106)
def l106(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        acts = {"save": "save more money", "spend": "spend more money", "buy": "buy a car", "sell": "sell the car"}
        px, py = acts[x], acts[y]
    elif s == 2:
        acts = {"money": "save more money", "coins": "collect more coins", "cash": "keep more cash", "savings": "add to his savings"}
        px, py = acts[x], acts[y]
    else:
        nx = x if x == "holiday" else with_article(x)
        ny = y if y == "holiday" else with_article(y)
        px, py = f"buy {nx}" if x != "holiday" else "take a holiday", f"buy {ny}" if y != "holiday" else "take a holiday"
    return stages(
        f"Would Eli {px} if he won the lottery?", f"Yes, Eli would {px} if he won the lottery.",
        f"No, Eli wouldn't {px} if he won the lottery.", "What would Eli do if he won the lottery?",
        f"Eli would {px} if he won the lottery.",
        f"Would Eli {px} or {py} if he won the lottery?", f"Eli would {px} if he won the lottery.")


@register(107)
def l107(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        advice = {"honest": "be honest and tell the truth", "dishonest": "not be dishonest",
                  "helpful": "be helpful and offer support", "selfish": "not be selfish"}
        px, py = advice[x], advice[y]
    elif s == 2:
        advice = {"promise": "keep the promise", "secret": "keep the secret", "truth": "tell the truth", "lie": "not tell a lie"}
        px, py = advice[x], advice[y]
    else:
        objects = {"apologize": "apologize", "explain": "explain what happened", "return": "return the item", "admit": "admit the mistake"}
        px, py = objects[x], objects[y]
    return stages(
        f"Would you {px}?", f"Yes. If I were you, I would {px}.",
        f"No. If I were you, I wouldn't {px}.", "What would you advise?",
        f"If I were you, I would {px}.",
        f"Would you {px} or {py}?", f"If I were you, I would {px}.")


@register(108)
def l108(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"said that the {x} was locked", f"said that the {y} was locked"
    elif s == 2:
        px, py = f"said that the gate was {x}", f"said that the gate was {y}"
    else:
        forms = {"say": "said that the gate was locked", "tell": "told us that the gate was locked",
                 "report": "reported that the gate was locked", "explain": "explained that the gate was locked"}
        px, py = forms[x], forms[y]
    return stages(
        f"Did Nia {px.replace('said ', 'say ', 1).replace('told ', 'tell ', 1).replace('reported ', 'report ', 1).replace('explained ', 'explain ', 1)}?",
        f"Yes, Nia {px}.",
        f"No, Nia didn't {px.replace('said ', 'say ', 1).replace('told ', 'tell ', 1).replace('reported ', 'report ', 1).replace('explained ', 'explain ', 1)}.",
        "What did Nia report?", f"Nia {px}.",
        f"Did Nia {px.replace('said ', 'say ', 1)} or {py}?", f"Nia {px}.")


@register(109)
def l109(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        clause, clausey = f"where the {x} is", f"where the {y} is"
        q = f"Do you know {clause}?"
        ans = f"I know {clause}"
    elif s == 2:
        clause, clausey = f"what the {x} is", f"what the {y} is"
        q = f"Do you know {clause}?"
        ans = f"I know {clause}"
    else:
        forms = {"know": "know where the archive is", "remember": "remember where the archive is",
                 "ask": "ask where the archive is", "tell": "tell me where the archive is"}
        clause, clausey = forms[x], forms[y]
        q = f"Do you {clause}?"
        ans = f"I {clause}"
    return stages(
        q, f"Yes, {ans}.", f"No, I don't {ans[2:]}.", "What embedded question can you report?",
        f"{ans[0].upper() + ans[1:]}.",
        f"Do you {ans[2:]} or {clausey}?", f"{ans[0].upper() + ans[1:]}.")


@register(110)
def l110(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        item, owner, ownery = x, "Taro", "Mina"
    elif s == 2:
        item, owner, ownery = "helmet", x, y
    else:
        item, owner, ownery = x, "Taro", "Mina"
    return stages(
        f"Whose {item} is this? Is it {possessive(owner)}?", f"Yes, this {item} is {possessive(owner)}.",
        f"No, this {item} isn't {possessive(owner)}.", f"Whose {item} is this?", f"This {item} is {possessive(owner)}.",
        f"Whose {item} is this, {possessive(owner)} or {possessive(ownery)}?", f"This {item} is {possessive(owner)}.")


@register(111)
def l111(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        noun = plural(x)
        q, ans, oq = f"How many {noun} has Mina got? Has she got six?", f"Mina has got six {noun}", f"How many {noun} has Mina got, six or eight?"
    elif s == 2:
        unit = "liter" if x in {"milk", "water"} else "kilogram"
        q, ans, oq = f"How much {x} has Mina got? Has she got one {unit}?", f"Mina has got one {unit} of {x}", f"How much {x} has Mina got, one {unit} or two?"
    else:
        facts = {"gram": ("does the sample weigh", "The sample weighs one gram"),
                 "kilogram": ("does the parcel weigh", "The parcel weighs one kilogram"),
                 "liter": ("water is in the bottle", "There is one liter of water in the bottle"),
                 "dozen": ("candles are in the box", "There is one dozen candles in the box")}
        prompt, answer = facts[x]
        q, ans, oq = f"How much or how many {prompt}? Is it one {x}?", answer, f"Is the measured quantity one {x} or two {x}s?"
    return stages(q, f"Yes, {ans}.", f"No, it isn't true that {ans[0].lower() + ans[1:]}.", q.split("?", 1)[0] + "?", f"{ans}.", oq, f"{ans}.")


@register(112)
def l112(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        ans, ansy = f"Pia practises {x}", f"Pia practises {y}"
        wh = "How often does Pia practise?"
    elif s == 2:
        fx = x if x == "often" else f"{x} a week"
        fy = y if y == "often" else f"{y} a week"
        ans, ansy, wh = f"Pia practises {fx}", f"Pia practises {fy}", "How often does Pia practise?"
    else:
        ans, ansy, wh = f"Pia has practised for {x}", f"Pia has practised for {y}", "How long has Pia practised?"
    return stages(
        f"{wh[:-1]}? Is this the answer: {ans}?", f"Yes, {ans}.", f"No, it isn't true that {ans[0].lower() + ans[1:]}.",
        wh, f"{ans}.", f"Is the answer “{ans}” or “{ansy}”?", f"{ans}.")


@register(113)
def l113(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        heads = {"boat": "two red boats with white sails", "sail": "two red sails on the boats",
                 "mast": "two tall masts on the boats", "rope": "two thick ropes on the boats"}
        np, npy = f"{heads[x]} near the bridge", f"{heads[y]} near the bridge"
    elif s == 2:
        np, npy = f"the two {x} wooden boats with white sails near the bridge", f"the two {y} wooden boats with white sails near the bridge"
    else:
        np, npy = f"the two red boats with white sails near the {x}", f"the two red boats with white sails near the {y}"
    return stages(
        f"Did you see {np}?", f"Yes, I saw {np}.", f"No, I didn't see {np}.",
        "Which detailed noun phrase identifies what you saw?", f"I saw {np}.",
        f"Did you see {np} or {npy}?", f"I saw {np}.")


@register(114)
def l114(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        owner, item, ownery = f"the {x}", "book", f"the {y}"
    elif s == 2:
        owner, item, ownery = "Maya", x, "Leo"
    else:
        owner, item, ownery = x, "sketch", y
    return stages(
        f"Is this {possessive(owner)} {item}?", f"Yes, this is {possessive(owner)} {item}.",
        f"No, this isn't {possessive(owner)} {item}.", f"Whose {item} is this?", f"This is {possessive(owner)} {item}.",
        f"Is this {possessive(owner)} {item} or {possessive(ownery)} {item}?", f"This is {possessive(owner)} {item}.")


@register(115)
def l115(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        item, owners, ownersy = plural(x), "students", "teachers"
    elif s == 2:
        item, owners, ownersy = "brushes", plural(x), plural(y)
    else:
        item, owners, ownersy = plural(x), "students", "teachers"
    poss, possy = possessive(owners), possessive(ownersy)
    return stages(
        f"Are these the {poss} {item}?", f"Yes, these are the {poss} {item}.",
        f"No, these aren't the {poss} {item}.", f"Whose {item} are these?", f"These are the {poss} {item}.",
        f"Are these the {poss} {item} or the {possy} {item}?", f"These are the {poss} {item}.")


@register(116)
def l116(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        item, itemy, owner = x, y, "Maya"
    else:
        item, itemy, owner = "work", "work", f"the {x}"
    return stages(
        f"Is this {with_article(item)} of {possessive(owner)}?", f"Yes, this is {with_article(item)} of {possessive(owner)}.",
        f"No, this isn't {with_article(item)} of {possessive(owner)}.", "Whose work is this?",
        f"This is {with_article(item)} of {possessive(owner)}.",
        f"Is this {with_article(item)} of {possessive(owner)} or {with_article(itemy)} of Leo's?", f"This is {with_article(item)} of {possessive(owner)}.")


@register(117)
def l117(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        px, py = f"sewed the {x}", f"sewed the {y}"
    else:
        px, py = f"{past(x)} the fabric", f"{past(y)} the fabric"
    base = px.replace("sewed", "sew", 1).replace(past(x), x, 1) if s == 3 else px.replace("sewed", "sew", 1)
    return stages(
        f"Did Ava {base} herself?", f"Yes, Ava {px} herself.",
        f"No, Ava didn't {base} herself.", "Who did the work?", f"Ava herself {px}.",
        f"Did Ava {base} herself, or did Leo do it?", f"Ava {px} herself.")


@register(118)
def l118(s: int, x: str, y: str, i: int) -> Stages:
    if s == 2:
        return stages(
            f"Is it {x} in the hall?", f"Yes, it is {x} in the hall.", f"No, it isn't {x} in the hall.",
            "What is it like in the hall?", f"It is {x} in the hall.",
            f"Is it {x} or {y} in the hall?", f"It is {x} in the hall.")
    noun = (lambda z: z if z in {"smoke", "heat"} else with_article(z))
    nx, ny = noun(x), noun(y)
    return stages(
        f"Is there {nx} in the hall?", f"Yes, there is {nx} in the hall.",
        f"No, there isn't {nx} in the hall.", "What is there in the hall?", f"There is {nx} in the hall.",
        f"Is there {nx} or {ny} in the hall?", f"There is {nx} in the hall.")


@register(119)
def l119(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        return stages(
            f"Did someone leave {with_article(x)} here?", f"Yes, someone left {with_article(x)} here.",
            f"No, no one left {with_article(x)} here.", "What did someone leave here?", f"Someone left {with_article(x)} here.",
            f"Did someone leave {with_article(x)} or {with_article(y)} here?", f"Someone left {with_article(x)} here.")
    return stages(
        f"Is anything here {x}?", f"Yes, something here is {x}.", f"No, nothing here is {x}.",
        "What can you say without naming the garment?", f"Something here is {x}.",
        f"Is something here {x} or {y}?", f"Something here is {x}.")


@register(120)
def l120(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is this the {x} that has the green mark?", f"Yes, this is the {x} that has the green mark.",
        f"No, this isn't the {x} that has the green mark.", "Which device is this?",
        f"This is the {x} that has the green mark.",
        f"Is this the {x} that has the green mark or the {y} that has the blue mark?", f"This is the {x} that has the green mark.")


@register(121)
def l121(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        sentence = f"a {x} brought the parcel, and the {x} left after the delivery"
        sentencey = f"a {y} brought the parcel, and the {y} left after the delivery"
    elif s == 2:
        sentence = f"a courier brought {with_article(x)}, and the {x} was sealed"
        sentencey = f"a courier brought {with_article(y)}, and the {y} was sealed"
    else:
        sentence = f"a courier {third(x)} a parcel, and the courier records it"
        sentencey = f"a courier {third(y)} a parcel, and the courier records it"
    cap = sentence[0].upper() + sentence[1:]
    return stages(
        f"Did this happen: {sentence}?", f"Yes. {cap}.", f"No, it didn't happen that {sentence}.",
        "How do you introduce and then identify the referent?", f"{cap}.",
        f"Did this happen: {sentence}, or {sentencey}?", f"{cap}.")


@register(122)
def l122(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        return stages(
            f"Did you buy some {x}?", f"Yes, I bought some {x}; I bought many {x}.",
            f"No, I didn't buy any {x}.", f"How many {x} did you buy?", f"I bought many {x}.",
            f"Did you buy many {x} or many {y}?", f"I bought many {x}.")
    if s == 2:
        return stages(
            f"Did you buy some {x}?", f"Yes, I bought some {x}; I bought a lot of {x}.",
            f"No, I didn't buy any {x}.", f"How much {x} did you buy?", f"I bought a lot of {x}.",
            f"Did you buy a lot of {x} or a lot of {y}?", f"I bought a lot of {x}.")
    phrases = {"more": "more apples", "less": "less rice", "equal": "an equal number of apples", "full": "a full bag of apples"}
    px, py = phrases[x], phrases[y]
    return stages(
        f"Is there {px}?", f"Yes, there is {px}.", f"No, there isn't {px}.",
        "What quantity is shown?", f"There is {px}.",
        f"Is there {px} or {py}?", f"There is {px}.")


@register(123)
def l123(s: int, x: str, y: str, i: int) -> Stages:
    quant = "a few" if s == 1 else "a little"
    verb = "are" if s == 1 else "is"
    return stages(
        f"{verb.capitalize()} there {quant} {x} left?", f"Yes, there {verb} {quant} {x} left.",
        f"No, there {verb}n't {quant} {x} left.", f"How much or how many {x} are left?",
        f"There {verb} {quant} {x} left.",
        f"{verb.capitalize()} there {quant} {x} or {quant} {y} left?", f"There {verb} {quant} {x} left.")


@register(124)
def l124(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        participant, item = x, "medal"
    else:
        participant, item = "runner", x
    return stages(
        f"Did every {participant} receive {with_article(item)}?", f"Yes, every {participant} received {with_article(item)}; each {participant} received one.",
        f"No, not every {participant} received {with_article(item)}.", f"What did each {participant} receive?",
        f"Each {participant} received {with_article(item)}.",
        f"Did every {participant} receive {with_article(item)}, or did only some receive one?", f"Every {participant} received {with_article(item)}; each received one.")


@register(125)
def l125(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Would you like another {x}?", f"Yes, I would like another {x}.",
        f"No, I don't want another {x}.", f"One {x} is unavailable. What do you want?", f"I want another {x}.",
        f"Do you want another {x} or the other {x}?", f"I want another {x}.")


@register(126)
def l126(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        subject, adj, adjy, comparison = "green object", x, y, "blue object"
    else:
        adjs = {"rope": "long", "box": "wide", "tower": "tall", "bridge": "long"}
        subject, adj, adjy, comparison = x, adjs[x], adjs[x], "marked example"
    return stages(
        f"Is the {subject} as {adj} as the {comparison}?", f"Yes, the {subject} is as {adj} as the {comparison}.",
        f"No, the {subject} isn't as {adj} as the {comparison}.", f"Which item is as {adj} as the {comparison}?",
        f"The {subject} is as {adj} as the {comparison}.",
        f"Is the {subject} as {adj} as the {comparison}, or is it less {adj}?", f"The {subject} is as {adj} as the {comparison}.")


@register(127)
def l127(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        preds = {"strong": "strong enough to hold the books", "weak": "weak enough to bend under the load",
                 "large": "large enough for the books", "small": "small enough to fit on the shelf"}
        px, py = preds[x], preds[y]
        return stages(
            f"Is the container {px}?", f"Yes, the container is {px}.", f"No, the container isn't {px}.",
            "What constraint does the container satisfy?", f"The container is {px}.",
            f"Is the container {px} or {py}?", f"The container is {px}.")
    if s == 2:
        nx, ny = plural(x), plural(y)
        return stages(
            f"Do we have enough {nx} for the books?", f"Yes, we have enough {nx} for the books.",
            f"No, we don't have enough {nx} for the books.", "What resource do we have in a sufficient quantity?",
            f"We have enough {nx} for the books.",
            f"Do we have enough {nx} or enough {ny}?", f"We have enough {nx} for the books.")
    verb = "are" if x in {"books", "people"} else "is"
    return stages(
        f"{verb.capitalize()} there enough {x}?", f"Yes, there {verb} enough {x}.", f"No, there {verb}n't enough {x}.",
        "What resource is sufficient?", f"There {verb} enough {x}.",
        f"Is there enough {x} or enough {y}?", f"There {verb} enough {x}.")


@register(128)
def l128(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        subject, action = "soup", "serve"
        adj, adjy = x, y
    elif s == 2:
        subject, action = "sauce", "eat"
        adj, adjy = x, y
    else:
        subject = x
        action = "drink" if x == "tea" else "eat"
        adj, adjy = "hot", "salty"
    return stages(
        f"Is the {subject} too {adj} to {action}?", f"Yes, the {subject} is too {adj} to {action}.",
        f"No, the {subject} isn't too {adj} to {action}.", f"Why can't we {action} the {subject}?",
        f"The {subject} is too {adj} to {action}.",
        f"Is the {subject} too {adj} or too {adjy} to {action}?", f"The {subject} is too {adj} to {action}.")


@register(129)
def l129(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        np, npy = f"a {x} old wooden chair", f"a {y} old wooden chair"
    elif s == 2:
        np, npy = f"a beautiful {x} wooden chair", f"a beautiful {y} wooden chair"
    elif s == 3:
        np, npy = f"a beautiful old {x} chair", f"a beautiful old {y} chair"
    else:
        np, npy = f"a beautiful old wooden {x}", f"a beautiful old wooden {y}"
    return stages(
        f"Did Mira buy {np}?", f"Yes, Mira bought {np}.", f"No, Mira didn't buy {np}.",
        "What did Mira buy?", f"Mira bought {np}.",
        f"Did Mira buy {np} or {npy}?", f"Mira bought {np}.")


@register(130)
def l130(s: int, x: str, y: str, i: int) -> Stages:
    noun = {1: "report", 2: "course", 3: "container"}[s]
    return stages(
        f"Is this {with_article(x)} {noun}?", f"Yes, this is {with_article(x)} {noun}.",
        f"No, this isn't {with_article(x)} {noun}.", f"What kind of {noun} is this?", f"This is {with_article(x)} {noun}.",
        f"Is this {with_article(x)} {noun} or {with_article(y)} {noun}?", f"This is {with_article(x)} {noun}.")


@register(131)
def l131(s: int, x: str, y: str, i: int) -> Stages:
    pairs = {"boring": ("boring", "bored"), "bored": ("boring", "bored"),
             "exciting": ("exciting", "excited"), "excited": ("exciting", "excited"),
             "frightening": ("frightening", "frightened"), "frightened": ("frightening", "frightened"),
             "tiring": ("tiring", "tired"), "tired": ("tiring", "tired"),
             "surprising": ("surprising", "surprised"), "surprised": ("surprising", "surprised"),
             "confusing": ("confusing", "confused"), "confused": ("confusing", "confused")}
    cause, feeling = pairs[x]
    statement = f"the event was {cause}, and Niko was {feeling}"
    return stages(
        f"Was this true: {statement}?", f"Yes, {statement}.", f"No, it wasn't true that {statement}.",
        "How did the event affect Niko?", f"The event was {cause}, so Niko was {feeling}.",
        f"Was the event {cause}, leaving Niko {feeling}, or was it neutral?", f"The event was {cause}, so Niko was {feeling}.")


@register(132)
def l132(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        clause, clausey = f"packed the camera {x}", f"packed the camera {y}"
    elif s == 2:
        clause, clausey = f"has {x} packed the camera", f"has {y} packed the camera"
    else:
        clause, clausey = f"has left the camera {x}", f"has left the camera {y}"
    qclause = clause.replace("has ", "", 1) if clause.startswith("has ") else clause
    if s == 1:
        aq = f"Did Kim {clause}?"
        aa = f"Yes, Kim {past(clause.split()[0]) + clause[len(clause.split()[0]):]}."
        na = f"No, Kim didn't {clause}."
        wa = f"Kim {past(clause.split()[0]) + clause[len(clause.split()[0]):]}."
    else:
        aq = f"Has Kim {clause[4:] if clause.startswith('has ') else clause}?"
        aa = f"Yes, Kim {clause}."
        na = f"No, Kim hasn't {clause[4:] if clause.startswith('has ') else clause}."
        wa = f"Kim {clause}."
    return stages(aq, aa, na, "Where or how is the adverb placed?", wa,
                  f"Is this true: Kim {clause}, or Kim {clausey}?", wa)


@register(133)
def l133(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        moves = {"tunnel": "went through the tunnel", "bridge": "went across the bridge", "field": "went across the field", "woods": "went through the woods"}
        px, py = moves[x], moves[y]
    elif s == 2:
        moves = {"wall": "climbed over the wall", "fence": "climbed over the fence", "river": "went across the river", "ditch": "went across the ditch"}
        px, py = moves[x], moves[y]
    else:
        moves = {"enter": "entered into the tunnel", "cross": "crossed over the bridge", "climb": "climbed onto the wall", "pass": "passed through the woods"}
        px, py = moves[x], moves[y]
    base = px.replace("went", "go", 1).replace("climbed", "climb", 1).replace("entered", "enter", 1).replace("crossed", "cross", 1).replace("passed", "pass", 1)
    return stages(
        f"Did the fox {base}?", f"Yes, the fox {px}.", f"No, the fox didn't {base}.",
        "Where and how did the fox move?", f"The fox {px}.",
        f"Did the fox {base}, or did it {py}?", f"The fox {px}.")


@register(134)
def l134(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        return stages(
            f"Did Sumi travel by {x}?", f"Yes, Sumi travelled by {x}.", f"No, Sumi didn't travel by {x}.",
            "How did Sumi travel?", f"Sumi travelled by {x}.",
            f"Did Sumi travel by {x} or by {y}?", f"Sumi travelled by {x}.")
    return stages(
        f"Did Sumi enter with the {x}?", f"Yes, Sumi entered with the {x}.", f"No, Sumi didn't enter with the {x}.",
        "What did Sumi use to enter?", f"Sumi entered with the {x}.",
        f"Did Sumi enter with the {x} or with the {y}?", f"Sumi entered with the {x}.")


@register(135)
def l135(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Is the fountain {x} the museum?", f"Yes, the fountain is {x} the museum.",
        f"No, the fountain isn't {x} the museum.", "Where is the fountain?", f"The fountain is {x} the museum.",
        f"Is the fountain {x} or {y} the museum?", f"The fountain is {x} the museum.")


@register(136)
def l136(s: int, x: str, y: str, i: int) -> Stages:
    return stages(
        f"Was the service interrupted because of the {x}?", f"Yes, the service was interrupted because of the {x}.",
        f"No, the service wasn't interrupted because of the {x}.", "Why was the service interrupted?",
        f"The service was interrupted because of the {x}.",
        f"Was the service interrupted because of the {x} or because of the {y}?", f"The service was interrupted because of the {x}.")


@register(137)
def l137(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        px, py = f"interested in {x}", f"interested in {y}"
    elif s == 3:
        forms = {"astronomy": "interested in astronomy", "gravity": "dependent on gravity",
                 "orbit": "known for its unusual orbit", "atmosphere": "known for its atmosphere"}
        px, py = forms[x], forms[y]
    else:
        forms = {"interested in": ("interested in astronomy", "interested in geology"),
                 "afraid of": ("afraid of space travel", "afraid of darkness"),
                 "depend on": ("depend on solar power", "depend on batteries"),
                 "known for": ("known for its rings", "known for its storms")}
        px, py = forms[x]
    return stages(
        f"Is Hana {px}?", f"Yes, Hana is {px}.", f"No, Hana isn't {px}.",
        "Which dependent-preposition phrase describes Hana?", f"Hana is {px}.",
        f"Is Hana {px} or {py}?", f"Hana is {px}.")


@register(138)
def l138(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{x} and play guitar", f"{y} and play guitar"
    elif s == 2:
        px, py = f"sing and play {x}", f"sing and play {y}"
    else:
        px, py = f"sing {x} and play guitar {x}", f"sing {y} and play guitar {y}"
    return stages(
        f"Can Theo {px}?", f"Yes, Theo can {px}.", f"No, Theo can't {px}.",
        "What two coordinated things can Theo do?", f"Theo can {px}.",
        f"Can Theo either {px.split(' and ')[0]} or {px.split(' and ')[1]}?", f"Theo can do both: {px}.")


@register(139)
def l139(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        clauses = {"start": "started work", "finish": "finished work", "arrive": "arrived", "leave": "left"}
        px, py = f"called Maya when she {clauses[x]}", f"called Maya when she {clauses[y]}"
    elif s == 2:
        px, py = f"{past(x)} after she arrived", f"{past(y)} after she arrived"
    else:
        prep = "until"
        px, py = f"worked until {x}", f"worked until {y}"
    base = px.replace("called", "call", 1).replace(past(x), x, 1) if s == 2 else px.replace("called", "call", 1).replace("worked", "work", 1)
    return stages(
        f"Did Ema {base}?", f"Yes, Ema {px}.", f"No, Ema didn't {base}.",
        "How were the events related in time?", f"Ema {px}.",
        f"Did Ema {base}, or did she {py}?", f"Ema {px}.")


@register(140)
def l140(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"we can see the {x}", f"we can see the {y}"
    elif s == 2:
        px, py = f"the {x} gives a clear view", f"the {y} gives a clear view"
    else:
        forms = {"see": "we can see the screen", "overlook": "the balcony overlooks the harbor",
                 "face": "the windows face the field", "block": "no wall blocks the view"}
        px, py = forms[x], forms[y]
    return stages(
        f"Should we stand where {px}?", f"Yes, we should stand where {px}.",
        f"No, we shouldn't stand where {px}.", "Where should we stand?", f"We should stand where {px}.",
        f"Should we stand where {px} or where {py}?", f"We should stand where {px}.")


@register(141)
def l141(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        reason, reasony, result = f"there was {x}", f"there was {y}", "the event stopped"
    elif s == 2:
        reason, reasony, result = f"there was a {x}", f"there was a {y}", "the event stopped"
    else:
        reason, reasony, result = "there was heavy rain", "there was strong wind", f"the system {past(x)}"
    return stages(
        f"Did {result} because {reason}?", f"Yes, {result.capitalize()} because {reason}.",
        f"No, {result.capitalize()} did not happen because {reason}.", "Why did that happen?",
        f"Since {reason}, {result}.",
        f"Did {result} because {reason} or because {reasony}?", f"As {reason}, {result}.")


@register(142)
def l142(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"whisper so that the {x} can sleep", f"whisper so that the {y} can sleep"
    elif s == 2:
        acts = {"whisper": "whisper", "tiptoe": "tiptoe", "dim": "dim the light", "close": "close the curtain"}
        px, py = f"{acts[x]} so that the baby can sleep", f"{acts[y]} so that the baby can sleep"
    else:
        acts = {"alarm": "set the alarm so that the worker can wake", "clock": "check the clock in order to wake on time",
                "curtain": "close the curtain so that the baby can sleep", "light": "dim the light so that the baby can sleep"}
        px, py = acts[x], acts[y]
    return stages(
        f"Did Ivo {px}?", f"Yes, Ivo {past(px.split()[0]) + px[len(px.split()[0]):]}.",
        f"No, Ivo didn't {px}.", "Why did Ivo do that?", f"Ivo {past(px.split()[0]) + px[len(px.split()[0]):]}.",
        f"Did Ivo {px} or {py}?", f"Ivo {past(px.split()[0]) + px[len(px.split()[0]):]}.")


@register(143)
def l143(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        results = {"heavy": "Ana dropped it", "light": "Ana lifted it easily", "balanced": "it stayed upright", "uneven": "it tipped over"}
        clause, clausey = f"the load was so {x} that {results[x]}", f"the load was so {y} that {results[y]}"
    elif s == 2:
        clause, clausey = f"it was such a heavy {x} that Ana dropped it", f"it was such a heavy {y} that Ana dropped it"
    else:
        results = {"drop": "Ana dropped it", "lift": "Ana could not lift it", "carry": "Ana could not carry it", "tip": "it tipped over"}
        clause, clausey = f"the load was so heavy that {results[x]}", f"the load was so heavy that {results[y]}"
    return stages(
        f"Was this true: {clause}?", f"Yes, {clause}.", f"No, it wasn't true that {clause}.",
        "What degree and result were shown?", f"{clause[0].upper() + clause[1:]}.",
        f"Was {clause}, or was {clausey}?", f"{clause[0].upper() + clause[1:]}.")


@register(144)
def l144(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"there is {x}", f"there is {y}"
        main = "the plan will continue"
    elif s == 2:
        px, py = "it rains", "it snows"
        main = f"the group will {x}"
    else:
        px, py = "it rains", "it snows"
        main = f"the {x} will continue"
    return stages(
        f"Will this happen: {main} unless {px}?", f"Yes, {main.capitalize()} unless {px}.",
        f"No, {main.capitalize()} won't happen unless {px}.", "What is the exception to the plan?",
        f"{main.capitalize()} unless {px}.",
        f"Will {main} unless {px}, or unless {py}?", f"{main.capitalize()} unless {px}.")


@register(145)
def l145(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"the {x} waited although it was raining", f"the {y} waited although it was raining"
    elif s == 2:
        px, py = f"Maya walked on the {x} although it was raining", f"Maya walked on the {y} although it was raining"
    else:
        px, py = f"Maya {past(x)} although it was raining", f"Maya {past(y)} although it was raining"
    return stages(
        f"Was this true: {px}?", f"Yes, {px}.", f"No, it wasn't true that {px}.",
        "What happened despite the rain?", f"{px[0].upper() + px[1:]}.",
        f"Was {px}, or was {py}?", f"{px[0].upper() + px[1:]}.")


@register(146)
def l146(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        request = f"Sorry, did you say {x}? Could you clarify whether it was {x} or {y}?"
    elif s == 2:
        request = f"Could you clarify what you mean by “{x}”?"
    else:
        requests = {"repeat": "Could you repeat that, please?", "clarify": "Could you clarify that, please?",
                    "spell": "Could you spell that, please?", "confirm": "Could you confirm that, please?"}
        request = requests[x]
    return stages(
        f"Should you ask, “{request}”?", f"Yes. Ask, “{request}”",
        f"No. Don't guess; ask, “{request}”",
        "What should you say to request repetition or clarification?", request,
        f"Should you ask, “{request},” or silently guess?", request)


@register(147)
def l147(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        meanings = {"stop": "drivers must stop", "exit": "this is the way out", "entrance": "this is the way in", "detour": "drivers must use another route"}
    elif s == 2:
        meanings = {"closed": "the route cannot be used", "forbidden": "the action is not allowed", "caution": "people must be careful", "danger": "there is a serious hazard"}
    else:
        meanings = {"drivers": "drivers cannot enter", "pedestrians": "pedestrians cannot enter", "visitors": "visitors cannot enter", "cyclists": "cyclists cannot enter"}
    meaning, meaningy = meanings[x], meanings[y]
    return stages(
        f"Does the sign mean that {meaning}?", f"Yes. In other words, {meaning}.",
        f"No. It doesn't mean that {meaning}.", "How can you restate the sign?", f"Put another way, {meaning}.",
        f"Does the sign mean that {meaning} or that {meaningy}?", f"In other words, {meaning}.")


@register(148)
def l148(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"I should {x} the report", f"I should {y} the report"
    elif s == 2:
        px, py = f"you mean the {x}", f"you mean the {y}"
    else:
        forms = {"exactly": "I should revise exactly this section", "only": "I should revise only this section",
                 "partly": "I should revise the report partly", "instead": "I should replace the chart instead"}
        px, py = forms[x], forms[y]
    return stages(
        f"Do you mean that {px}?", f"Yes, that is exactly what I mean: {px}.",
        f"No, I don't mean that {px}.", "What meaning or intention are you checking?", f"I am checking whether {px}.",
        f"Do you mean that {px} or that {py}?", f"I mean that {px}.")


@register(149)
def l149(s: int, x: str, y: str, i: int) -> Stages:
    noun = "word" if s < 3 else "material"
    return stages(
        f"Is “{x}” the {noun} the speaker needs?", f"Yes. You can help by asking, “Do you mean {x}?”",
        f"No. Don't supply an unrelated {noun}; ask, “Do you mean {x}?”",
        f"How can you help the speaker formulate the idea with {x}?", f"Ask, “Do you mean {x}?”",
        f"Should you offer {x} or {y}?", f"Ask, “Do you mean {x}?”")


@register(150)
def l150(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        line = f"Sorry to interrupt. May I add one point about {x}? Afterward, please continue."
        alt = f"Let's move directly to {y}."
    else:
        lines = {"interrupt": "Sorry to interrupt, but may I add one point?", "resume": "Let's resume the budget discussion.",
                 "continue": "To continue, the budget also covers training.", "return": "Let me return to the budget point."}
        line, alt = lines[x], lines[y]
    return stages(
        f"Does the speaker manage the interaction by saying, “{line}”?", f"Yes. The speaker says, “{line}”",
        f"No. The speaker doesn't manage it that way.", "What can the speaker say to manage the interruption or resumption?", line,
        f"Should the speaker say, “{line},” or “{alt}”?", line)


@register(151)
def l151(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        line, alt = f"Let's begin with the {x}.", f"Let's begin with the {y}."
    elif s == 2:
        line, alt = f"Turning to {x}, what is scheduled?", f"Turning to {y}, what is scheduled?"
    else:
        lines = {"begin": "Let's begin with the schedule.", "discuss": "Let's discuss the deadline now.",
                 "change": "Let's change the topic to the new date.", "close": "That closes our discussion of the calendar."}
        line, alt = lines[x], lines[y]
    return stages(
        f"Should the speaker manage the topic by saying, “{line}”?", f"Yes. The speaker should say, “{line}”",
        f"No. The speaker shouldn't continue the old topic; the speaker should say, “{line}”",
        "What can the speaker say to manage the topic?", line,
        f"Should the speaker say, “{line},” or “{alt}”?", line)


@register(152)
def l152(s: int, x: str, y: str, i: int) -> Stages:
    definitions = {
        "port": "a place where ships load and unload", "harbor": "a sheltered place for boats",
        "dock": "a place where a ship is loaded or repaired", "pier": "a platform extending over water",
        "ship": "a large vessel that travels on water", "boat": "a smaller vessel that travels on water",
        "ferry": "a vessel that carries people or vehicles on a regular route", "cargo": "goods carried by a ship",
    }
    if s < 3:
        dx, dy = definitions[x], definitions[y]
        return stages(
            f"Does “{x}” mean {dx}?", f"Yes, “{x}” means {dx}.",
            f"No, “{x}” doesn't mean {dx}.", f"What does “{x}” mean?", f"“{x}” means {dx}.",
            f"Does “{x}” mean {dx} or {dy}?", f"“{x}” means {dx}.")
    facts = {"spell": ("How do you spell “port”?", "“Port” is spelled P-O-R-T"),
             "mean": ("What does “port” mean?", "“Port” means a place where ships load and unload"),
             "pronounce": ("How do you pronounce “port”?", "“Port” is pronounced /pɔːrt/"),
             "define": ("How do you define “port”?", "“Port” is defined as a place where ships load and unload")}
    qx, ax = facts[x]
    qy, ay = facts[y]
    return stages(
        f"Is this the right request: {qx}", f"Yes. {qx} {ax}.",
        f"No. That request isn't answered incorrectly; the answer is: {ax}.", qx, f"{ax}.",
        f"Should you ask “{qx}” or “{qy}”?", f"Ask, “{qx}” {ax}.")


@register(153)
def l153(s: int, x: str, y: str, i: int) -> Stages:
    values = {"given name": "Maya", "family name": "Patel", "address": "4 River Road", "phone number": "555-0142",
              "date of birth": "12 May 2018", "nationality": "Japanese", "email": "maya@example.com", "signature": "Maya Patel"}
    if s < 3:
        value, valuey = values[x], values[y]
        context = f"The form states that Maya's {x} is “{value}.”"
        return stages(
            f"{context} Should Maya enter “{value}” in the field labeled “{x.title()}”?",
            f"Yes, Maya should enter “{value}” in the “{x.title()}” field.",
            f"No, Maya shouldn't leave the “{x.title()}” field blank.",
            f"{context} What should Maya enter in the “{x.title()}” field?",
            f"Maya should enter “{value}” in the “{x.title()}” field.",
            f"{context} Should Maya enter “{value}” or “{valuey}” in the “{x.title()}” field?",
            f"Maya should enter “{value}” in the “{x.title()}” field.")
    actions = {"enter": ("enter “Maya” in the Given name field", "leave it blank"),
               "select": ("select “Japanese” for Nationality", "select the wrong nationality"),
               "tick": ("tick the consent box", "leave the required box unticked"),
               "write": ("write “Maya Patel” in the Signature field", "write it in the Address field")}
    px, wrong = actions[x]
    return stages(
        f"Should Maya {px}?", f"Yes, Maya should {px}.", f"No, Maya shouldn't {wrong}.",
        "What should Maya do on the form?", f"Maya should {px}.",
        f"Should Maya {px} or {wrong}?", f"Maya should {px}.")


@register(154)
def l154(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        lines = {"beginning": "At the beginning, Kira found a key.", "middle": "In the middle, Kira opened the attic.",
                 "end": "At the end, Kira left the house.", "scene": "In the next scene, Kira discovered a trunk."}
        line, alt = lines[x], lines[y]
    elif s == 2:
        lines = {"first": "First, Kira found a key.", "next": "Next, Kira opened the attic.",
                 "then": "Then, Kira discovered a trunk.", "finally": "Finally, Kira left the house."}
        line, alt = lines[x], lines[y]
    else:
        verbs = {"find": "found a key", "open": "opened the attic", "discover": "discovered a trunk", "leave": "left the house"}
        line = f"First, Kira {verbs[x]}; then the story continued."
        alt = f"First, Kira {verbs[y]}; then the story continued."
    return stages(
        f"Does the narrative include this ordered sentence: “{line}”?", f"Yes. {line}",
        f"No. The narrative doesn't omit that stage; it says, “{line}”",
        "How can that part of the narrative be told in sequence?", line,
        f"Should the narrative say, “{line},” or “{alt}”?", line)


@register(155)
def l155(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{x} the scanner by pressing the {x} button", f"{y} the scanner by pressing the {y} button"
    elif s == 2:
        objects = {"press": "press the green button", "push": "push the tray inward", "hold": "hold the button for two seconds", "release": "release the button after the beep"}
        px, py = objects[x], objects[y]
    else:
        px, py = f"start the {x} by pressing its green button", f"start the {y} by pressing its green button"
    return stages(
        f"Do I {px}?", f"Yes. To operate it, {px}.", f"No. Don't use the wrong control; {px}.",
        "How do I operate it?", f"To operate it, {px}.",
        f"Do I {px} or {py}?", f"To operate it, {px}.")


@register(156)
def l156(s: int, x: str, y: str, i: int) -> Stages:
    bean_steps = {"first": "First, wash the beans.", "second": "Second, dry the beans.",
                  "next": "Next, roast the beans.", "finally": "Finally, grind the beans."}
    action_steps = {"wash": ("What happens first?", "First, wash the beans."),
                    "dry": ("What happens after washing?", "Next, dry the beans."),
                    "roast": ("What happens after drying?", "Then, roast the beans."),
                    "grind": ("What happens last?", "Finally, grind the beans.")}
    processes = {"beans": "First, wash the beans; next, dry them; then, roast them; finally, grind them.",
                 "rice": "First, measure the rice; next, rinse it; then, cook it; finally, serve it.",
                 "clothes": "First, wash the clothes; next, rinse them; then, dry them; finally, fold them.",
                 "dishes": "First, wash the dishes; next, rinse them; then, dry them; finally, put them away."}
    if s == 1:
        line, alt, wq = bean_steps[x], bean_steps[y], "Which sequence marker introduces this stage?"
    elif s == 2:
        wq, line = action_steps[x]
        _, alt = action_steps[y]
    else:
        line, alt, wq = processes[x], processes[y], f"What is the ordered process for {x}?"
    return stages(
        f"Is this stage or process correct: “{line}”?", f"Yes. {line}",
        f"No. The process doesn't omit that stage; it says, “{line}”",
        wq, line,
        f"Should the process use “{line}” or “{alt}” here?", line)


@register(157)
def l157(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        explanations = {"insulation": "Because heat was escaping, the team added insulation to retain heat; as a result, energy use fell",
                        "window": "Because heat escaped through the window, the team sealed it to retain heat; as a result, energy use fell",
                        "heater": "Because the heater was inefficient, the team serviced it to save gas; as a result, gas use fell",
                        "light": "Because the light was left on, the team added a timer to save electricity; as a result, electricity use fell"}
    elif s == 2:
        explanations = {z: f"Because {z} was being wasted, the team monitored it to reduce waste; as a result, {z} use fell" for z in ["heat", "electricity", "gas", "water"]}
    else:
        explanations = {"reduce": "Because energy use was high, the team added insulation to reduce it; as a result, use fell",
                        "save": "Because electricity was being wasted, the team switched off lights to save it; as a result, use fell",
                        "retain": "Because heat was escaping, the team added insulation to retain it; as a result, heater use fell",
                        "waste": "Because open windows waste heat, the team closed them to prevent waste; as a result, heater use fell"}
    exp = explanations[x]
    return stages(
        f"Does this explanation give purpose, cause, and result: “{exp}”?", f"Yes. {exp}.",
        f"No. The explanation doesn't deny the cause; it states, “{exp}.”",
        "How are the purpose, cause, and result connected?", f"{exp}.",
        f"Does the explanation connect all three relations, or only name {x}?", f"{exp}.")


@register(158)
def l158(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        evidence = {"witness": "a witness says the door was locked", "record": "the entry record shows no visit",
                    "footprint": "a fresh footprint leads to the door", "fingerprint": "a fingerprint is on the handle"}[x]
        conclusion = "someone approached the door"
    elif s == 2:
        evidence = {"light": "the light is off", "door": "the door is locked", "window": "the window is shut", "lock": "the lock is undamaged"}[x]
        conclusion = "the shop is closed"
    else:
        evidence = "the door is locked and the lights are off"
        conclusions = {"show": "the evidence shows that the shop is closed", "suggest": "the evidence suggests that the shop is closed",
                       "prove": "the complete record proves that no one entered", "indicate": "the evidence indicates that the shop is closed"}
        conclusion = conclusions[x]
    if s < 3:
        answer = f"From the fact that {evidence}, we can conclude that {conclusion}"
    else:
        answer = f"Because {evidence}, {conclusion}"
    return stages(
        f"Does the evidence support this conclusion: {answer}?", f"Yes. {answer}.",
        f"No. The evidence doesn't support the opposite conclusion.", "What can we conclude from the evidence?",
        f"{answer}.",
        f"Does the evidence support that conclusion or its opposite?", f"{answer}.")


@register(159)
def l159(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        choices = {"route": "Route A", "stop": "the Pine Street stop", "station": "Central Station", "transfer": "the transfer at Central"}
        choice, alt = choices[x], choices[y]
        reason = "it makes the journey direct"
    elif s == 2:
        if x in {"crowded", "slow"}:
            choice, alt, reason = f"avoiding the {x} service", f"using the {y} service", f"it is {x}"
        else:
            choice, alt, reason = f"the {x} service", f"the {y} service", f"it is {x}"
    else:
        choice, alt, reason = f"the {x}", f"the {y}", "it is direct and frequent"
    return stages(
        f"Would you recommend {choice}?", f"Yes. I recommend {choice} because {reason}.",
        f"No. I wouldn't recommend {choice} without that supporting reason.",
        "What do you recommend, and why?", f"I recommend {choice} because {reason}.",
        f"Would you recommend {choice} or {alt}?", f"I recommend {choice} because {reason}.")


@register(160)
def l160(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        claim, alt = f"the {x} should be protected", f"the {y} should be protected"
        response = f"I agree that {claim}"
    elif s == 2:
        claim, alt = f"the town should {x} the park", f"the town should {y} the park"
        response = f"I agree that {claim}"
    else:
        forms = {"agree": "I agree with the conservation plan", "disagree": "I disagree with the plan to remove trees",
                 "support": "I support the pond-restoration plan", "oppose": "I oppose the plan to remove the garden"}
        response, alt = forms[x], forms[y]
        claim = "that position"
    return stages(
        f"Does the speaker take this position: {response}?", f"Yes. {response}.",
        f"No. The speaker doesn't take the opposite position; {response}.",
        "What is the speaker's agreement or disagreement?", f"{response}.",
        f"Does the speaker say “{response}” or “{alt}”?", f"{response}.")


@register(161)
def l161(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        supports = {"claim": "My claim is that the market should remain because it serves local shops",
                    "reason": "In my opinion, the market should remain; my reason is that it serves local shops",
                    "evidence": "I think the market should remain because the sales evidence shows that local shops depend on it",
                    "example": "I think the market is useful; for example, it gives local farmers a place to sell food"}
        statement = supports[x]
    elif s == 2:
        statement = f"In my opinion, the town should {x} the market because it serves the community"
    else:
        statement = f"I think the market is {x} because it serves the community"
    return stages(
        f"Does the speaker give an opinion and a reason: “{statement}”?", f"Yes. {statement}.",
        f"No. The speaker doesn't hold the opposite opinion.", "What is the supported opinion?", f"{statement}.",
        f"Does the speaker support that opinion or the opposite one?", f"{statement}.")


@register(162)
def l162(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        statement = f"I would choose option A because it is {x} than option B, even though option B has other strengths"
        alt = f"option B because it is {y}"
    elif s == 2:
        statements = {"cost": "I would choose the bus because its lower cost outweighs its longer travel time",
                      "benefit": "I would choose the train because its main benefit is a faster journey",
                      "advantage": "I would choose the bicycle because its main advantage is that it produces no exhaust",
                      "disadvantage": "I would choose the train because the car's main disadvantage is congestion"}
        statement, alt = statements[x], statements[y]
    else:
        statement = f"I would choose the {x} because it offers the best balance of cost and travel time"
        alt = f"the {y}"
    return stages(
        f"Does the speaker compare alternatives and choose this option: “{statement}”?", f"Yes. {statement}.",
        f"No. The speaker doesn't choose without comparing the trade-off.",
        "Which alternative does the speaker choose, and why?", f"{statement}.",
        f"Does the speaker choose that option or {alt}?", f"{statement}.")


@register(163)
def l163(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        statement = f"It is {x} that the package will arrive today"
        alt = f"it is {y} that it will arrive today"
    elif s == 2:
        statement = f"The package will {x} arrive today"
        alt = f"it will {y} arrive today"
    else:
        statement = f"The package {x} arrive today"
        alt = f"it {y} arrive today"
    return stages(
        f"Is this the intended degree of certainty: {statement}?", f"Yes. {statement}.",
        f"No. It isn't true that {statement[0].lower() + statement[1:]}.", "How certain is the claim?",
        f"{statement}.",
        f"Is the claim that {statement[0].lower() + statement[1:]}, or that {alt}?", f"{statement}.")


@register(164)
def l164(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        statement = f"Dr. Sen, who is a {x}, is leading the project"
        alt = f"Dr. Sen, who is a {y}, is leading the project"
    elif s == 2:
        statement = f"Dr. Sen, who studies {x}, is leading the project"
        alt = f"Dr. Sen, who studies {y}, is leading the project"
    else:
        objects = {"study": "plants", "investigate": "chemicals", "measure": "energy", "discover": "new minerals"}
        statement = f"Dr. Sen, who {third(x)} {objects[x]}, is leading the project"
        alt = f"Dr. Sen, who {third(y)} {objects[y]}, is leading the project"
    return stages(
        f"Is this true: {statement}?", f"Yes, {statement}.", f"No, it isn't true that {statement}.",
        "Who is leading the project, with supplementary information?", f"{statement}.",
        f"Is it {statement}, or {alt}?", f"{statement}.")


@register(165)
def l165(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        acts = {"door": "locked the door", "window": "closed the window", "roof": "repaired the roof", "gate": "locked the gate"}
        px, py = acts[x], acts[y]
        ref = "the storm began"
    elif s == 2:
        objects = {"lock": "the door", "close": "the window", "repair": "the roof", "cover": "the gate"}
        px, py = f"{past(x)} {objects[x]}", f"{past(y)} {objects[y]}"
        ref = "the storm began"
    else:
        px, py = "locked the door", "closed the window"
        ref = f"the {x} began"
    base = px.replace("locked", "lock", 1).replace("closed", "close", 1).replace("repaired", "repair", 1).replace("covered", "cover", 1)
    return stages(
        f"Had Mila {px} before {ref}?", f"Yes, Mila had {px} before {ref}.",
        f"No, Mila hadn't {px} before {ref}.", f"What had Mila done before {ref}?", f"Mila had {px} before {ref}.",
        f"Had Mila {px} or {py} before {ref}?", f"Mila had {px} before {ref}.")


@register(166)
def l166(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{gerund(x)} the boat for two hours", f"{gerund(y)} the boat for two hours"
        ref = "when the rain began"
    elif s == 2:
        unit = "an hour" if x == "hour" else f"a {x}"
        unity = "an hour" if y == "hour" else f"a {y}"
        px, py = f"repairing the boat for {unit}", f"repairing the boat for {unity}"
        ref = "when the rain began"
    else:
        forms = {"since morning": ("repairing the boat since morning", "when the rain began"),
                 "for two hours": ("repairing the boat for two hours", "when the rain began"),
                 "all day": ("repairing the boat all day", "when the rain began"),
                 "by noon": ("repairing the boat for three hours", "by noon")}
        px, ref = forms[x]
        py, _ = forms[y]
    return stages(
        f"Had Sora been {px} {ref}?", f"Yes, Sora had been {px} {ref}.",
        f"No, Sora hadn't been {px} {ref}.", f"What had Sora been doing, and for how long, {ref}?",
        f"Sora had been {px} {ref}.",
        f"Had Sora been {px} or {py} {ref}?", f"Sora had been {px} {ref}.")


@register(167)
def l167(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        px, py = f"{gerund(x)} the boat at ten tomorrow", f"{gerund(y)} the boat at ten tomorrow"
    elif s == 2:
        px, py = f"repairing the {x} at ten tomorrow", f"repairing the {y} at ten tomorrow"
    else:
        prep = lambda z: z if z in {"tomorrow", "afternoon"} else f"at {z}"
        px, py = f"repairing the boat {prep(x)}", f"repairing the boat {prep(y)}"
    return stages(
        f"Will Sora be {px}?", f"Yes, Sora will be {px}.", f"No, Sora won't be {px}.",
        "What will Sora be doing at that future time?", f"Sora will be {px}.",
        f"Will Sora be {px} or {py}?", f"Sora will be {px}.")


@register(168)
def l168(s: int, x: str, y: str, i: int) -> Stages:
    pps = {"repair": "repaired", "finish": "finished", "submit": "submitted", "complete": "completed"}
    if s == 1:
        px, py = f"{pps[x]} the project by Friday", f"{pps[y]} the project by Friday"
    elif s == 2:
        px, py = f"completed the {x} by Friday", f"completed the {y} by Friday"
    else:
        deadline = f"by {x}" if x == "deadline" else f"by {x}"
        deadliney = f"by {y}"
        px, py = f"completed the project {deadline}", f"completed the project {deadliney}"
    return stages(
        f"Will Sora have {px}?", f"Yes, Sora will have {px}.", f"No, Sora won't have {px}.",
        "What will Sora have completed before the future reference point?", f"Sora will have {px}.",
        f"Will Sora have {px} or {py}?", f"Sora will have {px}.")


@register(169)
def l169(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        subj, pp, alt = x, "repaired", "closed"
    elif s == 2:
        subj, pp, alt = "bridge", x, y
    else:
        subj, pp, alt = f"bridge over the {x}", "built", "repaired"
    return stages(
        f"Was the {subj} {pp} last year?", f"Yes, the {subj} was {pp} last year.",
        f"No, the {subj} wasn't {pp} last year.", f"What happened to the {subj} last year?",
        f"The {subj} was {pp} last year.",
        f"Was the {subj} {pp} or {alt} last year?", f"The {subj} was {pp} last year.")


@register(170)
def l170(s: int, x: str, y: str, i: int) -> Stages:
    pp = {"inspect": "inspected", "repair": "repaired", "close": "closed", "reopen": "reopened"}
    if s == 1:
        subj, action, alty = "bridge", pp[x], pp[y]
    elif s == 2:
        subj, action, alty = x, "inspected", "repaired"
    else:
        subj, action, alty = "bridge", f"inspected after the {x}", f"inspected after the {y}"
    return stages(
        f"Has the {subj} been {action}?", f"Yes, the {subj} has been {action}.",
        f"No, the {subj} hasn't been {action}.", f"What has been done to the {subj}?",
        f"The {subj} has been {action}.",
        f"Has the {subj} been {action} or {alty}?", f"The {subj} has been {action}.")


@register(171)
def l171(s: int, x: str, y: str, i: int) -> Stages:
    pp = {"repair": "repaired", "paint": "painted", "inspect": "inspected", "test": "tested"}
    if s == 1:
        subj, action, alty = "bridge", pp[x], pp[y]
    elif s == 2:
        subj, action, alty = x, "repaired", "painted"
    else:
        subj, action, alty = "repair", x, y
    return stages(
        f"Is the {subj} being {action} now?", f"Yes, the {subj} is being {action} now.",
        f"No, the {subj} isn't being {action} now.", f"What is being done to the {subj} now?",
        f"The {subj} is being {action} now.",
        f"Is the {subj} being {action} or {alty} now?", f"The {subj} is being {action} now.")


@register(172)
def l172(s: int, x: str, y: str, i: int) -> Stages:
    if s < 3:
        subj, state, statey = "bridge", x, y
    else:
        subj, state, statey = x, "closed", "open"
    return stages(
        f"Is the {subj} {state} now?", f"Yes, the {subj} is {state} now.",
        f"No, the {subj} isn't {state} now.", f"What is the {subj}'s current state?",
        f"The {subj} is {state} now.",
        f"Is the {subj} {state} or {statey} now?", f"The {subj} is {state} now.")


@register(173)
def l173(s: int, x: str, y: str, i: int) -> Stages:
    pp = {"build": "built", "repair": "repaired", "reopen": "reopened", "complete": "completed"}
    if s == 1:
        subj, action, time, alt = x, "reopened", "in June", y
        oq = f"Will the {x} or the {y} be reopened in June?"
    elif s == 2:
        subj, action, time = "bridge", pp[x], "in June"
        oq = f"Will the bridge be {pp[x]} or {pp[y]} in June?"
    else:
        subj, action = "bridge", "reopened"
        time = x if x in {"summer", "next year"} else f"in {x}"
        timey = y if y in {"summer", "next year"} else f"in {y}"
        oq = f"Will the bridge be reopened {time} or {timey}?"
    return stages(
        f"Will the {subj} be {action} {time}?", f"Yes, the {subj} will be {action} {time}.",
        f"No, the {subj} won't be {action} {time}.", f"What will happen to the {subj} {time}?",
        f"The {subj} will be {action} {time}.", oq, f"The {subj} will be {action} {time}.")


@register(174)
def l174(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        subj, status, place, alty = x, "missing", "Rome", y
        oq = f"Is the {x} or the {y} believed to be in Rome?"
    elif s == 2:
        subj, status, place = "painting", x, "Rome"
        oq = f"Is the painting believed to be {x} or {y}?"
    else:
        subj, status, place = "painting", "missing", x
        oq = f"Is the missing painting believed to be in {x} or {y}?"
    return stages(
        f"Is the {status} {subj} believed to be in {place}?", f"Yes, the {status} {subj} is believed to be in {place}.",
        f"No, the {status} {subj} isn't believed to be in {place}.", "What is reported about the artwork?",
        f"The {status} {subj} is believed to be in {place}.", oq,
        f"The {status} {subj} is believed to be in {place}.")


@register(175)
def l175(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        modals = {"certain": "must", "likely": "must", "possible": "might", "impossible": "can't"}
        modal = modals[x]
        statement = f"Given the evidence, it is {x} that someone is inside; someone {modal} be inside"
        alt = f"it is {y} that someone is inside"
    elif s == 2:
        statement = f"Given the evidence, someone {x} be inside"
        alt = f"someone {y} be inside"
    else:
        statement = f"Given the evidence, the {x} might be inside"
        alt = f"the {y} might be inside"
    return stages(
        f"Does the evidence support this deduction: {statement}?", f"Yes. {statement}.",
        f"No. The evidence doesn't support that deduction.", "What present deduction does the evidence support?",
        f"{statement}.",
        f"Does the evidence support that {statement[0].lower() + statement[1:]}, or that {alt}?", f"{statement}.")


@register(176)
def l176(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        deductions = {"rained": "it could have rained overnight", "leaked": "the pipe might have leaked overnight",
                      "spilled": "someone may have spilled water", "overflowed": "the tank could have overflowed"}
        statement, alt = deductions[x], deductions[y]
    elif s == 2:
        deductions = {"sprinkler": "the sprinkler might have run", "pipe": "the pipe could have leaked",
                      "tank": "the tank may have overflowed", "bucket": "the bucket might have tipped over"}
        statement, alt = deductions[x], deductions[y]
    else:
        deductions = {"footprint": "the footprint might have been left last night", "lock": "the lock must have been opened with a tool",
                      "window": "someone could have entered through the window", "key": "someone may have used the key"}
        statement, alt = deductions[x], deductions[y]
    return stages(
        f"Does the evidence support this past deduction: {statement}?", f"Yes. The evidence shows that {statement}.",
        f"No. The evidence doesn't show that {statement}.", "What might have happened in the past?",
        f"The evidence suggests that {statement}.",
        f"Does the evidence suggest that {statement}, or that {alt}?", f"The evidence suggests that {statement}.")


@register(177)
def l177(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        conditions = {"leave": "left earlier", "wait": "waited for the next service", "turn back": "turned back sooner", "continue": "continued along the route"}
        condition, conditiony = conditions[x], conditions[y]
        result = "caught the train"
    elif s == 2:
        results = {"catch": "caught the train", "miss": "missed the train", "arrive": "arrived on time", "delay": "avoided the delay"}
        result, resulty = results[x], results[y]
        condition = conditiony = "left earlier"
    else:
        result, resulty = f"caught the {x}", f"caught the {y}"
        condition = conditiony = "left earlier"
    result_base = result.replace("caught", "catch", 1).replace("missed", "miss", 1).replace("arrived", "arrive", 1).replace("avoided", "avoid", 1)
    return stages(
        f"Would Jo have {result_base} if she had {condition}?", f"Yes, Jo would have {result} if she had {condition}.",
        f"No, Jo wouldn't have {result_base} if she had {condition}.",
        "What would have happened under that unreal past condition?", f"Jo would have {result} if she had {condition}.",
        (f"Would Jo have {result_base} if she had {condition} or if she had {conditiony}?" if s == 1 else
         f"Would Jo have {result_base} or {resulty} if she had {condition}?"),
        f"Jo would have {result} if she had {condition}.")


@register(178)
def l178(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        phrases = {"near": "near the station", "far": "far from the station", "nearby": "nearby", "distant": "in a distant place"}
        px, py = phrases[x], phrases[y]
        wish = f"Lia wishes she lived {px}"
        wishy = f"Lia wishes she lived {py}"
    elif s == 2:
        wish, wishy = f"Lia wishes she lived near the {x}", f"Lia wishes she lived near the {y}"
    else:
        forms = {"live": "Lia wishes she lived near the station", "work": "Lia wishes she worked near the station",
                 "stay": "Lia wishes she stayed near the station", "move": "Lia wishes she could move near the station"}
        wish, wishy = forms[x], forms[y]
    return stages(
        f"Does Lia express this unreal present wish: {wish}?", f"Yes. {wish}.",
        f"No. Lia doesn't express the opposite wish.", "What does Lia wish about her present situation?", f"{wish}.",
        f"Does Lia express that {wish[4:]}, or that {wishy[4:]}?", f"{wish}.")


@register(179)
def l179(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        wish, wishy = f"Lia wishes she had been {x}", f"Lia wishes she had been {y}"
    elif s == 2:
        pp = {"leave": "left earlier", "wait": "waited longer", "study": "studied more", "sleep": "slept earlier"}
        wish, wishy = f"Lia wishes she had {pp[x]}", f"Lia wishes she had {pp[y]}"
    else:
        forms = {"catch": "Lia wishes she had caught the train", "miss": "Lia wishes she had not missed the train",
                 "pass": "Lia wishes she had passed the test", "fail": "Lia wishes she had not failed the test"}
        wish, wishy = forms[x], forms[y]
    return stages(
        f"Does Lia express this past regret: {wish}?", f"Yes. {wish}.", f"No. Lia doesn't express the opposite regret.",
        "What does Lia wish had happened differently?", f"{wish}.",
        f"Does Lia express that {wish[4:]}, or that {wishy[4:]}?", f"{wish}.")


@register(180)
def l180(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        pairs = {"today": ("I will leave today", "he would leave that day"),
                 "yesterday": ("I arrived yesterday", "he had arrived the previous day"),
                 "tomorrow": ("I will arrive tomorrow", "he would arrive the next day"),
                 "next day": ("The parcel will arrive the next day", "the parcel would arrive the following day")}
        direct, report = pairs[x]
        directy, reporty = pairs[y]
    elif s == 2:
        pairs = {"this": ("I will bring this file", "he would bring that file"),
                 "that": ("I will bring that file", "he would bring that file"),
                 "here": ("I will wait here", "he would wait there"),
                 "there": ("I will wait there", "he would wait there")}
        direct, report = pairs[x]
        directy, reporty = pairs[y]
    else:
        pairs = {"bring": ("I will bring the file tomorrow", "he would bring the file the next day"),
                 "send": ("I will send the file tomorrow", "he would send the file the next day"),
                 "arrive": ("I will arrive tomorrow", "he would arrive the next day"),
                 "leave": ("I will leave tomorrow", "he would leave the next day")}
        direct, report = pairs[x]
        directy, reporty = pairs[y]
    return stages(
        f"Did Kai say, “{direct}”?", f"Yes. Kai said that {report}.",
        f"No. Kai didn't say, “{direct}.”",
        "How should Kai's words be reported with the references maintained?", f"Kai said that {report}.",
        f"Did Kai say, “{direct},” or “{directy}”?", f"Kai said that {report}.")


@register(181)
def l181(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        clause, clausey = f"whether the {x} is open", f"whether the {y} is open"
        matrix = "know"
    elif s == 2:
        clause, clausey = f"that the road is {x}", f"that the road is {y}"
        matrix = "know"
    else:
        matrices = {"know": "know that the road is open", "ask": "ask whether the road is open",
                    "remember": "remember when the ferry leaves", "discover": "discover why the train was delayed"}
        clause, clausey = matrices[x], matrices[y]
        matrix = None
    if matrix:
        full, fully = f"we {matrix} {clause}", f"we {matrix} {clausey}"
    else:
        full, fully = f"we {clause}", f"we {clausey}"
    return stages(
        f"Is this embedded proposition correct: {full}?", f"Yes, {full}.", f"No, {full.replace('we ', 'we do not ', 1)}.",
        "What proposition or question is embedded?", f"{full[0].upper() + full[1:]}.",
        f"Is it that {full}, or that {fully}?", f"{full[0].upper() + full[1:]}.")


@register(182)
def l182(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        np, npy = f"the {x} carrying the lantern", f"the {y} carrying the lantern"
    elif s == 2:
        forms = {"carrying": "the woman carrying the lantern", "holding": "the woman holding the map",
                 "wearing": "the woman wearing the badge", "named": "the woman named in the email"}
        np, npy = forms[x], forms[y]
    else:
        np, npy = f"the woman carrying the {x}", f"the woman carrying the {y}"
    return stages(
        f"Is {np} our guide?", f"Yes, {np} is our guide.", f"No, {np} isn't our guide.",
        "Which reduced relative clause identifies our guide?", f"{np[0].upper() + np[1:]} is our guide.",
        f"Is our guide {np} or {npy}?", f"{np[0].upper() + np[1:]} is our guide.")


@register(183)
def l183(s: int, x: str, y: str, i: int) -> Stages:
    clauses = {"walking": ("Walking along the platform", "Ren waved to us"),
               "waving": ("Waving to us", "Ren walked along the platform"),
               "smiling": ("Smiling at Maya", "Ren waved to us"),
               "talking": ("Talking to Maya", "Ren walked along the platform"),
               "cooking": ("Cooking dinner", "Ren listened to music"),
               "listening": ("Listening to music", "Ren cooked dinner"),
               "singing": ("Singing softly", "Ren cooked dinner"),
               "dancing": ("Dancing in the kitchen", "Ren sang softly")}
    part, main = clauses[x]
    party, mainy = clauses[y]
    return stages(
        f"Did both actions happen together: {part}, {main}?", f"Yes. {part}, {main}.",
        f"No. {part}, {main.replace('Ren ', 'Ren did not ', 1)}.", "How can the simultaneous actions be combined?",
        f"{part}, {main}.",
        f"Was it “{part}, {main},” or “{party}, {mainy}”?", f"{part}, {main}.")


@register(184)
def l184(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        clauses = {"board": ("Having boarded the train", "Ren sat down"), "leave": ("Having left the station", "Ren called Maya"),
                   "arrive": ("Having arrived at the station", "Ren checked the platform"), "sit": ("Having sat down", "Ren opened a book")}
    elif s == 2:
        clauses = {"train": ("Having boarded the train", "Ren sat down"), "platform": ("Having left the platform", "Ren called Maya"),
                   "carriage": ("Having entered the carriage", "Ren found a seat"), "station": ("Having reached the station", "Ren checked the time")}
    else:
        clauses = {"ticket": ("Having checked the ticket", "Ren boarded the train"), "bag": ("Having packed the bag", "Ren left home"),
                   "seat": ("Having found a seat", "Ren put down the bag"), "door": ("Having closed the door", "Ren sat down")}
    part, main = clauses[x]
    party, mainy = clauses[y]
    return stages(
        f"Did the completed action come first: {part}, {main}?", f"Yes. {part}, {main}.",
        f"No. It wasn't the case that {part.lower()}, {main.lower()}.", "How can the earlier completed action be placed first?",
        f"{part}, {main}.",
        f"Was it “{part}, {main},” or “{party}, {mainy}”?", f"{part}, {main}.")


@register(185)
def l185(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        part = f"Realizing that his {x} was missing"
        party = f"Realizing that his {y} was missing"
        main = "Ren ran back"
    elif s == 2:
        parts = {"missing": "Realizing that his bag was missing", "forgotten": "Remembering his forgotten bag",
                 "dropped": "Noticing his dropped phone", "stolen": "Realizing that his phone was stolen"}
        part, party, main = parts[x], parts[y], "Ren returned to the station"
    else:
        parts = {"realize": "Realizing that his bag was missing", "notice": "Noticing that his bag was missing",
                 "search": "Realizing that he needed to search for his bag", "return": "Realizing that he needed to return for his bag"}
        part, party, main = parts[x], parts[y], "Ren left the train"
    return stages(
        f"Did this reason lead to the action: {part}, {main}?", f"Yes. {part}, {main}.",
        f"No. {part}, Ren did not ignore the problem.", "Why did Ren act?", f"{part}, {main}.",
        f"Was the reason expressed as “{part}” or “{party}”?", f"{part}, {main}.")


@register(186)
def l186(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        clauses = {"drop": ("The folder slipped", "dropping the papers"), "fall": ("The box tipped", "falling to the floor"),
                   "scatter": ("Ren dropped the folder", "scattering the papers"), "roll": ("The ball fell", "rolling across the floor")}
        main, result = clauses[x]
        mainy, resulty = clauses[y]
    elif s == 2:
        main, result = f"The wind lifted the {x}", f"sending the {x} across the floor"
        mainy, resulty = f"The wind lifted the {y}", f"sending the {y} across the floor"
    else:
        main, result = "Ren dropped the folder", f"scattering the papers across the {x}"
        mainy, resulty = "Ren dropped the folder", f"scattering the papers across the {y}"
    return stages(
        f"Did the first action produce this result: {main}, {result}?", f"Yes. {main}, {result}.",
        f"No. It wasn't the case that {main.lower()}, {result}.", "What result followed the first action?",
        f"{main}, {result}.",
        f"Was the result “{result}” or “{resulty}”?", f"{main}, {result}.")


@register(187)
def l187(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        cleft, clefty = f"What we need is a {x} room", f"What we need is a {y} room"
    elif s == 2:
        cleft, clefty = f"What we need is a quieter {x}", f"What we need is a quieter {y}"
    else:
        forms = {"need": "What we need is a quieter room", "want": "What we want is a quieter room",
                 "prefer": "What we prefer is a quieter room", "choose": "What we choose is the quieter room"}
        cleft, clefty = forms[x], forms[y]
    return stages(
        f"Does the what-cleft focus the needed information: {cleft}?", f"Yes. {cleft}.",
        f"No. {cleft.replace(' is ', ' is not ', 1)}.", "What does the team need or choose?", f"{cleft}.",
        f"Is it “{cleft}” or “{clefty}”?", f"{cleft}.")


@register(188)
def l188(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        statement, alt = f"Nara does {x} the plan", f"Nara does {y} the plan"
    elif s == 2:
        forms = {"promise": "Nara does keep her promise", "action": "Nara does take action",
                 "claim": "Nara does support the claim", "evidence": "Nara does examine the evidence"}
        statement, alt = forms[x], forms[y]
    else:
        forms = {"revised": "Nara does support the revised plan", "original": "Nara does support the original plan",
                 "consistent": "Nara does remain consistent", "contradictory": "Nara does seem contradictory"}
        statement, alt = forms[x], forms[y]
    return stages(
        f"Despite the doubt, is this emphatic statement true: {statement}?", f"Yes. {statement}.",
        f"No. It isn't true that {statement}.", "What is Nara's actual position, with contrastive emphasis?",
        f"{statement}.",
        f"Is the emphatic statement “{statement}” or “{alt}”?", f"{statement}.")


@register(189)
def l189(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        statement, alt = f"it is important to add a {x}", f"it is important to add a {y}"
    elif s == 2:
        statement, alt = f"it is important to label the {x}", f"it is important to label the {y}"
    else:
        statement, alt = f"it is {x} to label the sample", f"it is {y} to label the sample"
    return stages(
        f"Is this evaluation correct: {statement}?", f"Yes, {statement}.", f"No, {statement.replace(' is ', ' is not ', 1)}.",
        "What stance or evaluation is expressed?", f"{statement[0].upper() + statement[1:]}.",
        f"Is the evaluation that {statement}, or that {alt}?", f"{statement[0].upper() + statement[1:]}.")


@register(190)
def l190(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        statement, alt = f"The {x} may suggest that the pond is recovering", f"the {y} may suggest that it is recovering"
    elif s == 2:
        forms = {"suggest": "The results suggest that the pond may be recovering", "indicate": "The results indicate that the pond may be recovering",
                 "appear": "The pond appears to be recovering", "seem": "The pond seems to be recovering"}
        statement, alt = forms[x], forms[y]
    else:
        statement, alt = f"The pond is {x} recovering", f"the pond is {y} recovering"
    return stages(
        f"Does this claim use an appropriate hedge: {statement}?", f"Yes. {statement}.",
        f"No. The evidence doesn't prove the unhedged opposite claim.", "How can the claim be hedged?", f"{statement}.",
        f"Should the hedged claim be “{statement}” or “{alt}”?", f"{statement}.")


@register(191)
def l191(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        text = f"The town should improve the {x} service because roads are crowded. Although the change will cost money, it will reduce congestion; therefore, journeys will become faster"
    elif s == 2:
        text = f"The town should address {x} because it lengthens journeys. Although the solution will cost money, it will improve travel; therefore, the project is justified"
    elif s == 3:
        text = f"The town should {x} the service because congestion is severe. Although the work will cost money, it will reduce delays; therefore, the plan is justified"
    else:
        texts = {"however": "The plan costs more. However, it reduces congestion, so the town should adopt it",
                 "therefore": "Congestion delays buses. Therefore, the town should add a bus lane",
                 "because": "The town should add buses because congestion delays every journey",
                 "although": "Although new buses cost money, they reduce congestion; therefore, the town should add them"}
        text = texts[x]
    return stages(
        f"Does this linked explanation support the plan: “{text}”?", f"Yes. {text}.",
        f"No. The explanation doesn't support the opposite conclusion.", "How are the claims linked across sentences?",
        f"{text}.",
        f"Does the explanation support the plan or reject it?", f"{text}.")


@register(192)
def l192(s: int, x: str, y: str, i: int) -> Stages:
    text = f"Mara bought the {x} tent. She tested it that evening, but she left the {y} one at the shop"
    return stages(
        f"Does this text maintain reference clearly: “{text}”?", f"Yes. {text}.",
        f"No. Mara didn't buy both tents; {text}.", "How can the referents be maintained without needless repetition?",
        f"{text}.",
        f"Did Mara test the {x} tent or the {y} one?", f"Mara tested the {x} tent; she tested it that evening.")


@register(193)
def l193(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        text = f"{x.capitalize()} is central to the system. First, the process begins with it; next, the system produces electricity; finally, the electricity reaches the user"
    elif s == 2:
        text = f"Solar cells process sunlight in stages. First, they {x} energy; next, they continue the conversion; finally, electricity reaches the grid"
    elif s == 3:
        text = f"Solar power has practical considerations. First, consider the {x}; furthermore, connect that issue to system performance; finally, summarize its effect"
    else:
        texts = {"first": "First, introduce the main claim. Next, give evidence; finally, summarize the result",
                 "next": "Begin with the main claim. Next, give the conversion evidence; finally, summarize the result",
                 "furthermore": "State the cost evidence. Furthermore, connect it to maintenance; finally, summarize the result",
                 "finally": "First, state the claim; next, give evidence; finally, summarize the result"}
        text = texts[x]
    return stages(
        f"Is this passage organized with a topic and links: “{text}”?", f"Yes. {text}.",
        f"No. The passage doesn't begin with an unrelated detail.", "How should the passage be organized?", f"{text}.",
        f"Should the passage follow that organization or begin with an unrelated detail?", f"{text}.")


@register(194)
def l194(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        examples = {"fact": "The survey included 500 people; this is a fact",
                    "opinion": "In my opinion, the service is excellent",
                    "interpretation": "My interpretation is that the rise reflects stronger demand",
                    "inference": "From the empty shelves, we can infer that demand exceeded supply"}
        statement, alt = examples[x], examples[y]
    elif s == 2:
        statement = f"The {x} states that 500 people participated; that reported number is a fact"
        alt = f"the {y} states the number"
    else:
        forms = {"show": "The measured figure shows that sales rose", "suggest": "The empty shelves suggest that demand rose",
                 "imply": "The pattern implies that demand rose", "prove": "The complete record proves that the payment was made"}
        statement, alt = forms[x], forms[y]
    return stages(
        f"Is this classification or signal correct: {statement}?", f"Yes. {statement}.",
        f"No. It isn't correct to signal the opposite category.", "How should the information be classified or signaled?",
        f"{statement}.",
        f"Is the correct reading “{statement}” or “{alt}”?", f"{statement}.")


@register(195)
def l195(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        statement, alt = f"According to the {x}, air quality improved", f"according to the {y}, air quality improved"
    elif s == 2:
        statement, alt = f"According to the {x}, air quality improved", f"according to the {y}, air quality improved"
    else:
        forms = {"according to": "According to the agency, air quality improved",
                 "reports": "The agency reports that air quality improved", "states": "The agency states that air quality improved",
                 "claims": "The agency claims that air quality improved"}
        statement, alt = forms[x], forms[y]
    return stages(
        f"Is the claim attributed this way: {statement}?", f"Yes. {statement}.",
        f"No. The claim isn't left without a source.", "How should the claim be attributed?", f"{statement}.",
        f"Should the attribution be “{statement}” or “{alt}”?", f"{statement}.")


@register(196)
def l196(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        text = f"In summary, the {x} stores water, reduces flooding, and supports wildlife habitat"
    elif s == 2:
        texts = {"flood": "In summary, wetlands reduce flood risk while supporting wildlife",
                 "wildlife": "In summary, wetlands support wildlife while reducing flood risk",
                 "habitat": "In summary, wetlands provide habitat and store floodwater",
                 "pollution": "In summary, wetlands filter some pollution while supporting habitat"}
        text = texts[x]
    else:
        texts = {"reduce": "In summary, wetlands reduce flooding and support wildlife",
                 "store": "In summary, wetlands store water and support wildlife",
                 "support": "In summary, wetlands support wildlife and reduce flooding",
                 "filter": "In summary, wetlands filter water and support wildlife"}
        text = texts[x]
    return stages(
        f"Does this summary preserve the central relations: {text}?", f"Yes. {text}.",
        f"No. The source doesn't claim that wetlands eliminate every problem.", "What is the central summary?", f"{text}.",
        f"Does the source support that summary or an unrelated claim about roads?", f"{text}.")


@register(197)
def l197(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        source = f"The treatment may reduce {x}"
        para = f"The treatment might lessen {x}"
    elif s == 2:
        pairs = {"reduce": ("The treatment may reduce pain", "The treatment might lessen pain"),
                 "lessen": ("The treatment may lessen pain", "The treatment might reduce pain"),
                 "heal": ("The wound may heal", "It is possible that the wound will recover"),
                 "cure": ("The treatment may cure the condition", "It is possible that the treatment will eliminate the condition")}
        source, para = pairs[x]
    else:
        pairs = {"may": ("The treatment may reduce pain", "It is possible that the treatment will lessen pain"),
                 "might": ("The treatment might reduce pain", "The treatment may possibly lessen pain"),
                 "certainly": ("The treatment will certainly reduce pain", "Pain reduction is certain"),
                 "definitely": ("The treatment will definitely reduce pain", "The treatment is certain to lessen pain")}
        source, para = pairs[x]
    return stages(
        f"Does “{para}” preserve the meaning of “{source}”?", f"Yes. {para}.",
        f"No. It doesn't change the claim into its negative or make it more certain.",
        f"How can you paraphrase “{source}”?", f"{para}.",
        f"Does the source mean “{para},” or does it make the opposite claim?", f"{para}.")


@register(198)
def l198(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        text = f"Source A and Source B report {x} results. Taken together, they support the same general conclusion"
    elif s == 2:
        text = f"Source A and Source B report {x} results. Taken together, they show that the exact effect remains uncertain"
    else:
        text = f"The first {x} and the second source point in the same direction. Taken together, they support a shared conclusion"
    return stages(
        f"Does this synthesis compare both sources: {text}?", f"Yes. {text}.",
        f"No. The sources don't justify a conclusion that ignores their difference.",
        "What do the sources show when compared and synthesized?", f"{text}.",
        f"Do the sources support that synthesis or completely opposite conclusions?", f"{text}.")


@register(199)
def l199(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        defs = {"fur": "Fur is a covering of hair that helps some mammals retain heat",
                "feathers": "Feathers are structures that cover birds and can provide insulation",
                "scales": "Scales are protective plates that cover parts of some animals",
                "shell": "A shell is a hard outer covering that protects an animal"}
        statement, alt = defs[x], defs[y]
    elif s == 2:
        defs = {"camouflage": "Camouflage is an adaptation that helps an organism hide",
                "webbed feet": "Webbed feet are an adaptation that can help an animal swim",
                "thick skin": "Thick skin is an adaptation that can reduce water loss or injury",
                "long roots": "Long roots are an adaptation that can reach deep water"}
        statement, alt = defs[x], defs[y]
    elif s == 3:
        statement = f"A {x} is a habitat; organisms there have adaptations suited to its conditions"
        alt = f"a {y} is that habitat"
    else:
        defs = {"survive": "An adaptation is a feature that helps an organism survive",
                "hide": "Camouflage is an adaptation that helps an organism hide",
                "swim": "Webbed feet are an adaptation that helps an animal swim",
                "retain water": "Long roots and thick skin can help an organism retain water"}
        statement, alt = defs[x], defs[y]
    return stages(
        f"Is this definition or classification accurate: {statement}?", f"Yes. {statement}.",
        f"No. The concept isn't defined by the opposite function.", "How should the concept be defined or classified?",
        f"{statement}.",
        f"Is the accurate definition “{statement}” or “{alt}”?", f"{statement}.")


@register(200)
def l200(s: int, x: str, y: str, i: int) -> Stages:
    if s == 1:
        reasoning = f"Measurements show that the {x} level has fallen for six weeks; therefore, fresh-water supply is shrinking, so restrictions are justified"
    elif s == 2:
        reasoning = f"Records show that {x} has changed while supply is limited; therefore, the balance is worsening, so conservation is justified"
    elif s == 3:
        reasoning = f"Measurements show a sustained {x}; this is evidence of pressure on supply, so conservation measures are justified"
    else:
        forms = {"measure": "We measure the reservoir level each week; the measurements show a decline, so restrictions are justified",
                 "show": "The records show a six-week decline; therefore, supply is shrinking, so restrictions are justified",
                 "indicate": "The measurements indicate sustained water loss; therefore, restrictions are justified",
                 "justify": "A sustained decline and rising demand justify restrictions because supply is shrinking"}
        reasoning = forms[x]
    return stages(
        f"Does the evidence support this reasoned conclusion: {reasoning}?", f"Yes. {reasoning}.",
        f"No. The evidence doesn't support the opposite conclusion of unrestricted use.",
        "Why is the conclusion justified?", f"{reasoning}.",
        f"Does the evidence support that conclusion or unrestricted use?", f"{reasoning}.")


def main() -> None:
    for path in sorted(LANGUAGE.glob("L[0-9][0-9][0-9].md")):
        lesson = int(path.stem[1:])
        original = path.read_text(encoding="utf-8")
        source = re.split(r"\nVOCAB_BLOCK_1:\n", original, maxsplit=1)[0].rstrip()
        vocab_sets = parse_sets(source)
        blocks = generate_lesson(lesson, vocab_sets)
        addition = "\n\n".join(render_block(i, block) for i, block in enumerate(blocks, 1))
        path.write_text(source + "\n\n" + addition + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
