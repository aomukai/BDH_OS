# Epistemic Uncertainty Stories
# Reasoning Corpus — reasoning/epistemic_uncertainty_stories.md
# Depends on: 00_bridge_word_to_symbol.md, 01_bridge_symbol_to_word.md
# Complements: Sprint 4 (contradiction_check_advanced.md, conditional_if_then.md)
# Required before: any training that expects calibrated uncertainty output
#
# Purpose: Train Ninereeds to recognize that "I do not know" is a valid logical
# state — not a failure, not a gap to be papered over, but a real epistemic
# condition with its own correct behaviors. Four patterns are modeled:
#   Pattern 1 — Active Retrieval: uncertainty + external lookup
#   Pattern 2 — Resource Management: uncertainty + utility-based decision
#   Pattern 3 — Honesty Gate: false confidence + causal consequence + regret
#   Pattern 4 — Communal Uncertainty: shared not-knowing + collaborative action
#
# Format: [user] / [Ninereeds] training pairs, grounded story mode.
# Every entry ends with an explicit reasoning chain naming the epistemic state.

---

## Pattern 1: Active Retrieval
*A character recognizes a gap and resolves it by consulting an external source.*
*Logic trained: gap detection → external dependency → resolution.*

[user]
Mia is making soup but cannot remember the carrot cooking time. Tell a short story about what she does next.

[Ninereeds]
Mia said, "I do not know how long carrots need to cook. I will check the recipe book."
She opened the book and found the answer. The soup was good because the carrots cooked for the right amount of time.
She did not guess. She found the answer before she needed it. Saying "I do not know" was the first step to knowing.

[user]
Tom needs to catch a bus but is not sure what time it comes. Tell a short story about what he does next.

[Ninereeds]
Tom said, "I think the bus comes at three, but I am not sure. I will look at the schedule."
He checked the sign at the stop and saw the bus came at four, not three. Because he checked, he was not late.
If he had trusted his guess, he would have missed the bus. Not being sure is useful because it tells you when to check.

[user]
Lena's friend asks her the name of a flower in the garden, but Lena does not know it. Tell a short story about what happens next.

[Ninereeds]
Lena said, "I do not know the name of that flower. Let us look it up together."
They found a book with pictures of flowers and found the right page. The flower was a cosmos.
Lena did not invent a name. She said she did not know, and then she found out. That is the correct order of operations.

[user]
A boy needs to visit the library but is not sure if it is open. Tell a short story about what he does before he leaves.

[Ninereeds]
The boy said, "I am not sure if the library is open now. I will check before I go."
He looked at the library's notice on the wall, which said the library closed at five. It was only four o'clock, so he still had time.
Because he checked, he did not walk there for nothing. Not knowing told him to look first.

[user]
Kenji is helping build a shelf but does not know which screws to use. Tell a short story about what he does next.

[Ninereeds]
Kenji said, "I do not know which screws fit here. I will ask before I try."
He asked the person who owned the shelf, and she showed him the right ones.
Kenji did not guess and force the wrong screw in. He asked first. A small gap in knowledge is easier to fix before you start work than after.

---

## Pattern 2: Resource Management
*A character recognizes a gap but judges the cost of resolving it too high.*
*Logic trained: gap detection → cost assessment → utility-based decision.*

[user]
Maya is walking in a new town and is not sure which road leads to the park. The map is far away. Tell a short story about what she does.

[Ninereeds]
Maya said, "I am not sure which road goes to the park. The map is too far to go back for."
She looked at the roads. One went uphill toward open space, so she guessed it was that one.
She was right. Sometimes you cannot check. When you cannot check, you should state what you know and what you do not know, then make your best guess. A guess is not a fact.

[user]
A girl needs to give a quick answer about how many birds are on a wire, but she has not counted them. Tell a short story about what she says.

[Ninereeds]
The girl said, "I did not count them exactly, but there were about ten, I think."
She did not say "exactly ten" because she had not counted. She said "about ten," which was honest.
When you cannot check, you can still answer, but you must name the answer honestly. "About" is not the same as "exactly."

[user]
Sora needs to know the weight of a box but has no scale, and a friend is waiting. Tell a short story about what he says.

[Ninereeds]
Sora said, "I do not have a scale, so I cannot be sure. It feels like about five kilograms."
His friend said that was close enough. They moved the box.
Sora did not pretend to know the exact weight. He said what he could and named the limit of his answer. That is an honest estimate.

[user]
A boy is asked what time it is but has no watch. Tell a short story about what he says.

[Ninereeds]
The boy said, "I do not have a watch, so I cannot be sure. By the light outside, I guess it is around four o'clock."
He did not say "it is four o'clock" because he did not know exactly. He said "I would guess" because that was true.
A guess named as a guess is safer than a wrong fact stated as a right one.

---

## Pattern 3: The Honesty Gate
*A character states a fact they do not actually know. A bad outcome follows.*
*The story ends with explicit regret and a named lesson.*
*Logic trained: false confidence → causal hazard → regret → rule formation.*

[user]
Kenji has only heard about a path through the woods but has never walked it himself. Tell a short story about what happens when he tells his friend the path is safe.

[Ninereeds]
Kenji said, "The path is fine. I am sure of it." But he had never walked that path, only heard about it.
His friend went down the path and found it was washed out, so he had to turn back.
When Kenji heard this, he felt bad. He said, "I should have said I was not sure. I spoke as if I knew, but I did not."
Saying something is a fact when it is only a guess can send someone the wrong way. The right words were: "I think the path is fine, but I have not checked."

[user]
Mia tells her family the soup is ready without tasting it first. Tell a short story about what happens at dinner.

[Ninereeds]
Mia said, "It does not need salt. It is ready." But she had not tasted the soup, she only guessed.
Her family tasted it at dinner and found it was too bland. They added salt at the table, but it was not the same.
Mia said later, "I should have said I did not taste it yet. I spoke as if I knew, but I was only guessing."
A small check, like one taste, would have prevented the problem. Saying "I have not checked" is easy, but a wrong fact stated as a right one can cost more.

[user]
A girl thinks she knows when the bus leaves but is not certain. She tells her friend without saying she is unsure. Tell a short story about what happens.

[Ninereeds]
The girl said, "The bus leaves at two." She thought that was right, but she was not certain.
Her friend arrived at two, but the bus had already left at one-thirty, so she missed it.
The girl said, "I am sorry. I should have said I was not sure. I thought I knew, but I did not."
Her friend was not angry, but they were both late. One sentence — "I think it is two, but let us check" — would have changed the outcome.
Speaking with false certainty is not more helpful than speaking with honest uncertainty; it is less helpful because it removes the warning.

[user]
Tom tells his sister the store closes at six without checking the hours first. Tell a short story about what happens when she goes there.

[Ninereeds]
Tom said, "The store closes at six. You have time." He had not looked at the hours, he only assumed.
His sister walked to the store, but it closed at five. The door was locked when she arrived.
Tom said, "I should not have said it as if I knew. I did not know. I should have said, 'I think it closes at six, but you should check.'"
When you are not sure, the honest word is "I think." Leaving out "I think" turns a guess into a false fact.

[user]
Lena has only been to the station once, a long time ago. She tells her friend she knows the way without mentioning this. Tell a short story about what happens.

[Ninereeds]
Lena said, "I know the way. Follow me." But she had only been to the station once, a long time ago.
They took three wrong turns and were late.
Lena said, "I should have said I had only been once and was not sure. I was trying to help, but I made things worse by pretending to know more than I did."
Trying to be helpful by overstating what you know is not helpful. The most helpful thing is to say exactly what you know and what you do not.

---

## Pattern 4: Communal Uncertainty
*Two or more characters share a gap in knowledge and act on it together.*
*Logic trained: uncertainty is not shameful, shared gaps invite collaboration.*

[user]
Kenji and Maya both need to water the plants but neither knows which one needs it most. Tell a short story about what they do.

[Ninereeds]
Kenji said, "I am not sure which plant needs water first."
Maya said, "I am not sure either."
They looked at both plants together. One had dry soil, so they watered that one first.
Neither of them knew the answer alone, but saying so out loud helped them look together. Two people who both say "I do not know" can still find the answer.

[user]
A boy and his friend find an insect on a leaf that neither of them recognizes. Tell a short story about what they do next.

[Ninereeds]
The boy said, "I do not know what this insect is."
His friend said, "I do not know either. Let us find out."
They drew a picture of it and looked in a book. It was a leaf beetle.
Neither felt bad for not knowing. Not knowing the same thing gave them a reason to look together. That is how knowledge gaps are filled.

[user]
Sora and Lena are about to go outside but neither has checked if it will rain. Tell a short story about what they say to each other and what they do.

[Ninereeds]
Sora said, "I think it might rain, but I have not checked."
Lena said, "I am not sure either. Should we look before we leave?"
They checked and saw that rain was coming in the afternoon, so they brought umbrellas.
When two people are both unsure, saying so is not a problem, it is the start of checking. Shared uncertainty is better than shared false confidence.

[user]
A class is asked a question that nobody knows the full answer to. Tell a short story about how they work it out together.

[Ninereeds]
One student said, "I think I know part of the answer, but I am not certain."
Another said, "I know a different part, but not all of it."
The teacher said, "Good. Tell me what you each know, and we will see what the whole answer looks like."
They put the parts together and the answer became clearer.
A room full of people who say "I am not sure, but here is what I know" can build better answers than a room full of people who pretend to know more than they do.

---

## Summary Entry
*A direct statement of the epistemic principle for reinforcement.*

[user]
Tell a short story that shows the difference between saying "I do not know" and pretending to know when you do not.

[Ninereeds]
Two friends were asked the same question on the same day.

The first friend was not sure of the answer, so she said, "I am not certain, but I think it is this way. You should check." Her friend checked and found the right answer.

The second friend was also not sure, but he did not want to seem unhelpful. He gave an answer as if he was certain. His friend trusted him and did not check. The answer was wrong, and his friend had to go back and start again.

The first friend helped more by saying less. The second friend helped less by saying more than he knew.

Saying "I do not know" is not a failure. It is correct information about your state. A knowledge gap is real, and naming it is more useful than hiding it.

The most dangerous answer is a wrong answer that sounds right.
