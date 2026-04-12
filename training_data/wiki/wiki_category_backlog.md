# Wiki Category Backlog

> **Note on path:** Source files live in `training_data/wiki/`, not the `wiki/` root referenced
> in the prompt. Output written here to match actual file locations.
>
> **Sources:** 7 files parsed. `concept_ideas_LFM.md` is identical to `concept_ideas_gemini.md`
> — counted as 1 source (gemini/LiquidAI). `concept_ideas_nemotron.md` contains no category
> suggestions (orphan-check output only) — excluded from counts.
>
> **Effective sources (6):** gpt · deepseek · gemini · grok · mistral · sakana
>
> **Additional sources (local models):** LFM 2.5 — 1 accepted · Gemma 4-26B — 6 accepted, 1 expansion (Sensory Experiences), 1 coverage flag (Family Roles) · Qwen 3.5-9B — 5 accepted, 2 expansions (Material Composition, Clothing and Apparel) · Sakana — 4 accepted, 1 expansion (Daily Routines)
> **Additional sources (SOTA models):** ChatGPT — 7 accepted (micro-structure / interaction layer) · DeepSeek — 8 accepted · Gemini — 3 accepted, 1 expansion (Imagination and Pretend Play), 1 expansion (Sleep and Rest), 1 expansion (Categories and Grouping)

---

## Recommended Implementation Order

This is the practical write order for the remaining wiki categories.
It is not just "early before middle before late" — it also tries to respect
dependency chains, category ownership, and the need for BDH to first sound like
a child in daily conversation before moving into heavier abstraction.

### Wave 1 — finish the partial early anchors

These already exist in some form and unlock many other categories:

1. School Life and Learning
2. Clothing and Apparel
3. Money, Trade, and Shopping
4. Movement and Physical Action
5. Directions and Navigation
6. Meals and Mealtime Talk
7. Sensory Experiences

### Wave 2 — daily life and state language

These provide the "ordinary day" structure that many later categories assume:

8. Daily Routines and Self-Care
9. States of Being and Condition
10. Body States and Internal Cues
11. Wants, Needs, and Preferences
12. Greetings and Social Salutations
13. Waiting and Patience
14. Containers and Capacity

### Wave 3 — conversation glue and peer interaction

These let BDH handle ordinary child dialogue naturally:

15. Manners, Politeness, and Social Etiquette
16. Communication Acts and Language
17. Agreement and Disagreement
18. Ownership and Sharing
19. Friends and Peer Interactions
20. Personal Identity and Self-Description
21. Lost and Found / Misplacing Objects
22. Uncertainty and Guessing

### Wave 4 — school/play/action environment

These build on the daily and social layers and match common child topics:

23. Classroom Objects and School Tools
24. Play, Games, and Sports
25. Art and Creative Expression
26. Hobbies and Interests
27. Location and Direction in Action
28. Animal Care and Pet Keeping
29. Safety, Rules, and Emergency Awareness
30. Safety Signs and Symbols

### Wave 5 — imagination, story, home, and care

These are very important, but they sit more cleanly once daily routines,
communication, play, and school are already grounded:

31. Imagination and Pretend Play
32. Storytelling and Narrative Structure
33. Chores and Home Responsibilities
34. Sleep and Rest
35. Holidays and Celebrations
36. Conflict Resolution and Relationship Repair
37. Boundaries and Consent

### Wave 6 — finish the remaining partial middle categories

These can now be expanded more cleanly because the everyday glue is in place:

38. Health and Wellness
39. Emotions Beyond Basic States
40. Measurement and Comparison
41. Natural Life Cycles and Processes
42. Construction and Material Transformations
43. Cooking and Food Preparation
44. Community Places and Services

### Wave 7 — structured middle abstractions

These depend more heavily on already having strong everyday and school language:

45. Seasonal Activities
46. Data, Charts, and Graphs
47. Material Composition
48. Simple Physics: Energy and Power
49. Animal Habitats and Homes
50. Levels of Intensity and Gradation
51. Food Groups and Nutrition
52. Musical Instruments
53. Shadow and Light Phenomena
54. Garden and Planting Basics
55. Group Roles and Participation
56. Evidence and Justification
57. Categories and Grouping
58. Exceptions and Qualifications
59. Intentions and Plans in Action
60. Accidents and Mistakes
61. Smells and Tastes
62. Collections and Collecting
63. Sibling Relationships and Dynamics
64. Degrees of Truth

### Wave 8 — late pragmatic and reflective layers

These are important, but they are safest after the child-facing core and
middle layers are stable:

65. Technology and Digital Media
66. Environmental Care and Stewardship
67. Fractions and Sharing Quantities
68. Perspective-Taking and Theory of Mind
69. Humor and Figurative Language
70. Inclusion, Bullying, and Kindness
71. Online Safety and Privacy
72. Civic Responsibility and Community Rules
73. Learning, Memory, and Metacognition
74. Future Planning and Goals
75. Story Roles and Plot Elements
76. Social-Emotional Learning Competencies
77. Secrets, Surprises, and Keeping Promises
78. Praise, Criticism, and Feedback

### Wave 9 — finish the remaining partial late categories

These should come after the missing dependency-heavy late categories above:

79. Opinions, Persuasion, and Simple Debate
80. Numbers Beyond 10 and Large-Number Talk
81. Machines and Simple Mechanisms
82. Growth and Life Stages (Human)

### Notes

- Finish partial categories before starting too many new sibling categories.
- Prefer categories that unlock many others before specialist or late-pragmatic topics.
- When two categories overlap, write the broader social or daily-life category first.
- Keep concept ownership clear to avoid duplicate anchors before later expansion.

---

## [COVERED] — Daily Routines and Self-Care
Sequence: early
Suggested by: 6 models (gpt, deepseek, gemini, grok, mistral, sakana)
Examples: wake up, get dressed, brush teeth, eat breakfast, go to school, go to bed, wash hands, take a shower, comb hair, pack backpack, pajamas, line up, switch activities, "time to…"
Depends on: time (morning/afternoon/evening/night), body (hand, tooth, hair, face), clothing (shirt, pants, shoe, sock), food and drink, home, bed
Reason: Children structure their day around predictable routines that anchor time, actions, and objects together; middle-childhood development includes growing independence in managing daily tasks and talking about them in longer, connected sequences.
Existing coverage: `daily_routines_and_self_care_entries.md` now anchors `routine`, `wake up`, `get ready`, `get dressed`, `wash your hands`, `eat breakfast`, `go to school`, `pack a backpack`, `line up`, `go to bed`, and `pajamas`.

---

## [PARTIAL] — School Life and Learning
Sequence: early
Suggested by: 6 models (gpt, deepseek, gemini, grok, mistral, sakana)
Examples: classroom, teacher, desk, homework, recess, lesson, test, backpack, school bus, grade, subject (math, reading, science, art, PE), lunchbox
Depends on: book, paper, crayon, desk, chair, table, bus, road, time (day/week)
Reason: School is the primary workplace for children aged 6–10 and the main source of daily conversational topics, spanning people, places, activities, subjects, and social norms; children constantly reference teachers, classmates, and school events.
Existing coverage: `school_life_and_learning_entries.md` anchors school, classroom, lesson, homework, book, paper, pencil, pen, and crayon. Broader school routines, roles, places, and events still missing.

---

## [MISSING] — Manners, Politeness, and Social Etiquette
Sequence: early
Suggested by: 5 models (gpt, deepseek, gemini, grok, mistral)
Examples: please, thank you, excuse me, sorry, you're welcome, raise hand, take turns speaking, wait your turn, may I?, can I?, "I'm sorry I interrupted"
Depends on: logic (rule, goal), feeling (happy/sad), time (present), friend
Reason: Standards for child communication emphasise respectful communication, kindness, and empathy as foundational social tools; to function as an authentic peer the model must operate within the same social constraints as the child.
Existing coverage: —

---

## [MISSING] — Safety, Rules, and Emergency Awareness
Sequence: early
Suggested by: 5 models (gpt, deepseek, grok, mistral, sakana)
Examples: danger, careful, stop, look both ways, call for help, trusted adult, emergency, helmet, seatbelt, fire safety, stranger danger, consequences, "not safe"
Depends on: road, car, fire, logic (rule, cause/effect, possible/impossible), feeling (scared), home
Reason: Critical real-world topic; children learn and repeat safety rules for roads, bikes, and emergencies daily; early health education expects children to tell trusted adults when unsafe and to practise refusal and help-seeking strategies.
Existing coverage: —

---

## [MISSING] — Play, Games, and Sports
Sequence: early
Suggested by: 5 models (gpt, deepseek, grok, mistral, sakana)
Examples: tag, hide and seek, jump rope, board game, team, score, win, lose, fair, cheat, playground equipment, rules, catch, kick, throw, puzzle, seesaw
Depends on: ball, sandbox, seesaw, rope, block, doll, logic (rule, order, goal, begin/middle/end), feeling (happy/sad)
Reason: Playtime rules and games are what children negotiate and argue about most with friends; playground and PE vocabulary is essential for inclusion and understanding fairness; school-age benchmarks highlight richer narrative development through play.
Existing coverage: —

---

## [MISSING] — Communication Acts and Language
Sequence: early
Suggested by: 5 models (gpt, deepseek, gemini, grok, mistral)
Examples: ask, answer, whisper, shout, explain, promise, lie, truth, joke, "What does that mean?", "Can you say it again?", "I meant…", take turns speaking, clarify, repair
Depends on: mouth, ear, paper, book, logic (truth, fact/opinion, cause/effect), feeling (happy/sad/angry), time (past/present)
Reason: Repairing misunderstandings and asking clarifying questions are hallmarks of growing school-age conversational competence; the model needs to understand the mechanics of the conversation it is currently having, not just vocabulary items.
Existing coverage: —

---

## [MISSING] — Friends and Peer Interactions
Sequence: early
Suggested by: 4 models (gpt, deepseek, grok, sakana)
Examples: friend, best friend, classmate, teammate, neighbour, share, take turns, play together, invite, argue, make up, playdate, "be my friend"
Depends on: feeling (happy/sad/angry), logic (same/different, rule, problem/solution), body (hand), ball, doll, block
Reason: School-age communication places growing weight on friendships and peer interaction, driving much daily conversation; peer interaction requires cooperation, conflict resolution, and turn-taking — all language the model needs for authentic child-level exchange.
Existing coverage: —

---

## [MISSING] — Art and Creative Expression
Sequence: early
Suggested by: 3 models (gpt, deepseek, mistral)
Examples: draw, colour, paint, glue, fold, clay, craft, decorate, erase, sing, dance, build with blocks, make a card, collage
Depends on: paper, crayon, scissors, stick, block, colour, shape, feeling (happy)
Reason: Daily classroom activity requiring fine motor action verbs and result descriptions; creativity is fundamental to expression, learning, and problem-solving in the elementary setting.
Existing coverage: —

---

## [PARTIAL] — Imagination and Pretend Play
Sequence: early
Suggested by: 3 models (gpt, grok, sakana)
Examples: pretend, make-believe, story character, superhero, dragon, castle, magic, adventure, invent a game, pretend store, pretend doctor, "let's say you are…", imaginary friend, role assignment
Depends on: book, doll, crayon, paper, logic (possible/impossible, change), feeling (happy/excited)
Reason: Pretend play and storytelling fill children's free time and fuel conversations about what "could happen"; imaginative play expands creative conversation and is a primary mode of peer interaction.
Existing coverage: `imagination_and_pretend_play_entries.md` now anchors `imagination`, `pretend`, `pretend play`, `make-believe`, `dress up`, `role play`, `imaginary friend`, `symbolic play`, and `game of pretend`.

---

## [MISSING] — Ownership and Sharing
Sequence: early
Suggested by: 2 models (gemini, deepseek)
Examples: mine, yours, giving, taking, gift, belonging, fair share, "that's mine", borrow, return, "can I use that?"
Depends on: objects (ball, doll, book, home), friend, logic (rule, goal), feeling (happy/angry)
Reason: Much of early social negotiation revolves around the concept of property and the ethics of sharing; the language of ownership and borrowing appears in almost every play interaction.
Existing coverage: —

---

## [MISSING] — Hobbies and Interests
Sequence: early
Suggested by: 2 models (gpt, sakana)
Examples: drawing, sports, music, crafts, collecting cards or stickers, reading, building, singing, "I like to…", "my favourite thing is…"
Depends on: crayon, paper, ball, logic (goal), feeling (happy)
Reason: Elementary children use conversational space to express interests and self-identity; sharing preferences is foundational for conversation openers, friendship, and identity language.
Existing coverage: —

---

## [MISSING] — Greetings and Social Salutations
Sequence: early
Suggested by: 1 model (gpt)
Examples: hello, goodbye, good morning, good night, see you tomorrow, how are you?, nice to meet you, "have a good day"
Depends on: time (morning/afternoon/evening/night, day/week), feeling (happy/sad)
Reason: High-frequency "conversation glue" tightly tied to expressing time-of-day and social intent; essential for opening and closing every exchange — the model will need these before almost anything else.
Existing coverage: —

---

## [MISSING] — Personal Identity and Self-Description
Sequence: early
Suggested by: 1 model (gpt)
Examples: name, age, birthday, grade, "about me" facts, favourites, "I like…", "I am…", "I live in…"
Depends on: number (0-10), time (day/week/month/year/season), feeling, logic (same/different)
Reason: Elementary children frequently introduce themselves and share basic personal information as conversation openers and in school talk; self-description is the entry point for almost all peer interaction.
Existing coverage: —

---

## [MISSING] — Wants, Needs, and Preferences
Sequence: early
Suggested by: 1 model (deepseek)
Examples: want, need, like, don't like, choose, favourite, rather, prefer, "I wish", "I would rather", "I need…"
Depends on: feeling (happy/sad), logic (same/different, fact/opinion), food, objects
Reason: Expressing preferences is foundational for identity and negotiation; the distinction between wants and needs is a key early concept for self-advocacy and requesting language.
Existing coverage: —

---

## [PARTIAL] — Clothing and Apparel
Sequence: early
Suggested by: 1 model (gemma)
Examples: shirt, pants, hat, shoes, coat, socks, sweater, dress, helmet, jacket, gloves, scarf, glasses, backpack, umbrella, belt, watch, zipper, button, velcro, snap, buckle
Depends on: body parts, weather and seasons, home objects
Reason: Children frequently discuss what they are wearing or what they need to wear for specific weather or activities; clothing items appear as dependencies across many other categories but have no dedicated wiki entries of their own.
Existing coverage: `clothing_and_apparel_entries.md` now anchors coat, glove, hat, pants, and button. Broader coverage still missing.

---

## [COVERED] — States of Being and Condition
Sequence: early
Suggested by: 1 model (gemma)
Examples: broken, fixed, full, empty, open, closed, on, off, wet, dry, clean, dirty, heavy, light, awake, asleep
Depends on: objects (home objects, tools), STEM concepts (states of matter), verbs (give, take, make)
Reason: Essential object-state adjectives that are neither emotions nor sensory qualities; a child needs to say "the door is open", "the cup is full", or "the toy is broken" — none of which are addressed by existing entries.
Existing coverage: `states_of_being_and_condition_entries.md` now anchors the core state/adjective layer with `condition`, `open`, `closed`, `on`, `off`, `clean`, `dirty`, `broken`, `fixed`, and `asleep`. Related condition words such as `full`, `empty`, `wet`, `dry`, `heavy`, `light`, and `awake` are already covered in `STEM_entries.md` or nearby domain files.

---

## [MISSING] — Animal Care and Pet Keeping
Sequence: early
Suggested by: 1 model (qwen)
Examples: feed the fish, clean the cage, change the water, brush the dog, fill the bowl, grooming, hutch, tank, lead, collar, litter tray, "my pet needs…"
Depends on: animals (mammals, birds, fish/sea), home objects, verbs (give, take, hold, make), daily routines (backlog)
Reason: Many children have pets and talk about the routines of caring for them daily; this is distinct from Animal Habitats (where animals live) and from Chores (household tasks) — it is the specific practice of responsible animal ownership.
Existing coverage: —

---

## [PARTIAL] — Safety Signs and Symbols
Sequence: early
Suggested by: 1 model (sakana)
Examples: stop sign, traffic light, crosswalk sign, poison symbol, slippery floor sign, emergency exit sign, railway crossing sign, fire alarm, no entry sign, recycling symbol
Depends on: safety, rules, and emergency awareness (backlog), vehicles and transport, places and landforms
Reason: Children encounter signs everywhere but often don't know what they mean; "what is a stop sign?", "what is a poison symbol?" are valid wiki entries covering physical objects whose purpose is to communicate rules — distinct from the Safety/Rules category which covers behaviours.
Existing coverage: `safety_signs_and_symbols_entries.md` now anchors `sign`, `symbol`, `stop sign`, `exit sign`, `danger sign`, `caution sign`, `no entry sign`, `pedestrian crossing sign`, `poison symbol`, `first aid symbol`, and `slippery floor sign`.

---

## [MISSING] — Classroom Objects and School Tools
Sequence: early
Suggested by: 1 model (sakana)
Examples: ruler, eraser, glue, scissors, whiteboard, marker, stapler, folder, sharpener, calculator, sticky note, paint brush
Depends on: school life and learning (backlog), home objects, tools and kitchenware
Reason: Three home-object wiki files exist but no school-object file; classroom items like ruler, scissors, and whiteboard are central to a child's daily environment and have no dedicated wiki entries.
Existing coverage: —

---

## [MISSING] — Location and Direction in Action
Sequence: early
Suggested by: 1 model (gpt)
Examples: come here, go there, bring it to me, put it on the table, take it outside, move it over, pass it across, set it down, point to it
Depends on: topology / spatial parts, verbs (give, take, hold, move), directions and navigation (backlog)
Reason: Action-linked spatial language — where something must go as part of a command — is distinct from static spatial descriptions and from bare verb entries; these imperative spatial phrases are among the most common utterances in child-directed and child-produced speech.
Existing coverage: —

---

## [MISSING] — Agreement and Disagreement
Sequence: early
Suggested by: 1 model (gpt)
Examples: yes, no, I agree, I don't think so, that's right, that's wrong, me too, not me, exactly, I think differently
Depends on: logic (truth, fact/opinion), communication acts and language (backlog), feeling (happy/sad)
Reason: The most primitive conversational moves — affirming or contesting what someone just said — are not addressed by any existing or backlog entry; without them the model cannot participate naturally in the back-and-forth of real dialogue.
Existing coverage: —

---

## [MISSING] — Uncertainty and Guessing
Sequence: early
Suggested by: 1 model (gpt)
Examples: maybe, I think, I guess, not sure, probably, could be, I'm not certain, perhaps, it might be, I wonder
Depends on: logic (possible/impossible, fact/opinion), perspective-taking and theory of mind (backlog)
Reason: Epistemic hedging is essential for conversational authenticity; without it the model sounds robotically certain about everything — hedges like "maybe" and "I think" are among the most frequent words in child speech.
Existing coverage: —

---

## [MISSING] — Lost and Found / Misplacing Objects
Sequence: early
Suggested by: 1 model (deepseek)
Examples: lost, found, where is it, look for, search, I can't find it, have you seen my…?, it's gone, left it somewhere, check the lost and found, put it back, retrace steps
Depends on: topology / spatial parts, home objects, school life and learning (backlog), logic (problem/solution)
Reason: Children constantly misplace objects and need to describe and ask about them; "I lost my pencil" and "have you seen my lunch box?" are among the most common elementary speech acts; distinct from Ownership (mine/yours) and Directions (spatial instructions) — it is the active search vocabulary.
Existing coverage: —

---

## [MISSING] — Waiting and Patience
Sequence: early
Suggested by: 1 model (deepseek)
Examples: wait, turn, soon, not yet, a little longer, hurry up, it's almost time, be patient, stand in line, "wait your turn", "how much longer?", almost ready
Depends on: time (soon/later/not yet), logic (rule, order), feeling (excited/frustrated/bored)
Reason: Waiting and patience are regulatory concepts embedded in almost every school and social routine; children encounter them in queues, games, and family settings constantly and need language to name and manage the experience.
Existing coverage: —

---

## [MISSING] — Containers and Capacity
Sequence: early
Suggested by: 1 model (gemini)
Examples: box, bag, cup, bucket, bowl, jar, bottle, basket, pocket, drawer, full, empty, "put it in the…", "it's too full", "pour it out", spill, overflow, "does it fit?"
Depends on: home objects, tools and kitchenware, verbs (give/take/hold/drop), logic (part/whole, more/less)
Reason: Container vocabulary bridges object knowledge to physical reasoning; children need to describe where things go, whether something fits, and actions with containers across daily routines at home and school — a foundational practical-language layer.
Existing coverage: —

---

## [MISSING] — Body States and Internal Cues
Sequence: early
Suggested by: 1 model (gemini)
Examples: hungry, thirsty, tired, cold, hot, full, dizzy, itchy, sore, need the bathroom, "my tummy hurts", "I need water", breathe fast, heart beating fast, shiver, sweat
Depends on: body parts, feeling (tired/happy/sad), STEM concepts (senses), food and drink
Reason: Children need to report and understand their own body's signals to communicate basic physical needs; distinct from Emotions (feelings about events) and Health and Wellness (illness/medicine) — these are moment-to-moment physical sensations driving immediate requests.
Existing coverage: —

---

## [MISSING] — Holidays and Celebrations
Sequence: middle
Suggested by: 4 models (deepseek, grok, mistral, sakana)
Examples: birthday, party, gift, cake, candle, holiday, celebration, tradition, parade, festival, special day, present, decorate
Depends on: time (year/season/day), food (cake, cookie), family, objects (candle), feeling (happy/excited)
Reason: Holidays and birthdays are the most emotionally salient events children look forward to and recount afterward; cultural events provide shared experiences and context for social and emotional discussion.
Existing coverage: —

---

## [PARTIAL] — Money, Trade, and Shopping
Sequence: middle
Suggested by: 4 models (gpt, deepseek, mistral, sakana)
Examples: buy, sell, cost, penny, nickel, dime, quarter, dollar, pay, save, earn, allowance, change, store, "how much does it cost?"
Depends on: number (0-10), addition/subtraction, logic (more/less), objects, time (day/week)
Reason: Elementary standards explicitly include money word problems; children commonly talk about buying, saving, and allowances; money language teaches exchange, value, and practical arithmetic in real-world context.
Existing coverage: `money_trade_and_shopping_entries.md` now anchors `money`, `coin`, `dollar`, `store`, `buy`, `sell`, `pay`, `cost`, `price`, `save`, and `spend`. Smaller units, allowances, and shopping situations still missing.

---

## [PARTIAL] — Storytelling and Narrative Structure
Sequence: middle
Suggested by: 3 models (gpt, deepseek, sakana)
Examples: once upon a time, first, next, then, finally, before, after, suddenly, at the end, beginning-middle-end, main idea, retell, "and then…", "so then…"
Depends on: time (past/present/future), logic (begin/middle/end, cause/effect), feeling (happy/sad)
Reason: School-age benchmarks highlight causally sequenced narratives ("story grammar") as a key development in communication; children retell events and make up stories using these discourse markers to organise thought across school and home settings.
Existing coverage: `storytelling_and_narrative_structure_entries.md` now anchors `story`, `beginning`, `middle`, `end`, `first`, `next`, `then`, `before`, `after`, `finally`, and `at the end`.

---

## [PARTIAL] — Chores and Home Responsibilities
Sequence: middle
Suggested by: 3 models (gpt, deepseek, sakana)
Examples: clean up, put away, set the table, sweep, water plants, feed pet, make the bed, take out trash, tidy up, "my job is…"
Depends on: home, broom, bucket, cup/plate/bowl, spoon, dog/cat, water, logic (rule, goal)
Reason: School-age children increasingly do chores and discuss duties and group welfare in home and classroom contexts; teaches cause/effect (clean vs dirty) and part/whole of shared household responsibility.
Existing coverage: `chores_and_home_responsibilities_entries.md` now anchors `chore`, `responsibility`, `clean up`, `put something away`, `make the bed`, `set the table`, `sweep the floor`, `water plants`, `feed a pet`, `take out the trash`, and `tidy up`.

---

## [MISSING] — Sleep and Rest
Sequence: middle
Suggested by: 1 model (deepseek)
Examples: sleepy, yawn, blanket, pillow, dream, nightmare, quiet, dark, alarm, rest, nap, "time for bed", story time, lullaby, night light, scared of the dark
Depends on: bed, night, tired (feeling), light, moon, star, time (night/morning)
Reason: Sleep issues (bad dreams, bedtime resistance) are common conversation topics for young children; understanding rest as a physical need connects to energy, health, and daily cycles.
Existing coverage: —

---

## [MISSING] — Conflict Resolution and Relationship Repair
Sequence: middle
Suggested by: 1 model (gpt)
Examples: compromise, forgive, apologise, negotiate, "let's try again", make up, agree to disagree, "I'm sorry", "that's okay", "how can we fix this?"
Depends on: logic (problem/solution, goal, rule), feeling (sad/angry), time (future), friend
Reason: Communication standards in health education include negotiating and managing conflict; this is distinct from general manners — it covers repair after a breakdown has already occurred, which is a specific and frequent child language event.
Existing coverage: —

---

## [MISSING] — Boundaries and Consent
Sequence: middle
Suggested by: 1 model (gpt)
Examples: personal space, boundaries, "stop", "not okay", "my body", "you may not", refusal, consent, "I don't want to"
Depends on: space (near/far/between), logic (rule, necessary), feeling (scared/angry)
Reason: Health-education standards explicitly expect boundary-setting and refusal skills as children progress through elementary years; the model needs this language to respond safely and appropriately in child welfare contexts.
Existing coverage: —

---

## [MISSING] — Seasonal Activities
Sequence: middle
Suggested by: 1 model (LFM)
Examples: spring planting and puddle-jumping, summer picnics and swimming, autumn leaf piles and harvest, winter snowball fights and sledging, dressing for each season, seasonal foods
Depends on: weather and seasons (COVERED), time (season), clothing (shirt, coat, boot), natural world (rain, snow, sun, leaf)
Reason: The model will know what seasons are but not what people do in them; behavioural seasonal knowledge — activities, clothing choices, and seasonal rhythms — is a genuine gap not addressed by the Weather and Seasons or Natural Life Cycles entries.
Existing coverage: —

---

## [MISSING] — Data, Charts, and Graphs
Sequence: middle
Suggested by: 1 model (gpt)
Examples: chart, graph, tally, "most/least", count, result, bar chart, survey, "more than/fewer than", pictograph
Depends on: number (0-10), counting, logic (all/some/none, same/different), size (more/less)
Reason: Measurement-and-data work in early grades includes generating and representing data; this shows up in classroom conversation and science activities and is not yet addressed by the existing math concepts file.
Existing coverage: —

---

## [MISSING] — Material Composition
Sequence: middle
Suggested by: 1 model (gemma)
Examples: wood, metal, plastic, glass, paper, stone, fabric, rubber, cardboard, clay, leather, cotton, wool, polyester, silk, nylon, denim
Depends on: home objects, tools and kitchenware, STEM concepts (states of matter, properties), clothing and apparel (backlog)
Reason: The model knows objects but not what they are made of; "what is glass?", "what is plastic?" entries provide the connective layer between objects and their physical properties, enabling richer descriptions ("the window is made of glass"). Fabric types (cotton, wool, polyester, silk, nylon) added on suggestion from qwen — these are the textile sub-domain of materials, most relevant to clothing.
Existing coverage: —

---

## [MISSING] — Simple Physics: Energy and Power
Sequence: middle
Suggested by: 1 model (gemma)
Examples: battery, electricity, heat, light, energy, power, fuel, solar, plug, switch, flashlight, candle
Depends on: STEM concepts (forces, motion, temperature), weather and seasons (sun, wind), tools and kitchenware
Reason: STEM entries cover forces and motion but not energy sources; children frequently ask "how does this work?" and need the vocabulary for where light, heat, and movement come from.
Existing coverage: STEM_entries.md (forces, temperature, and motion covered; energy as a concept and named power sources not yet present)

---

## [MISSING] — Animal Habitats and Homes
Sequence: middle
Suggested by: 1 model (gemma)
Examples: nest, burrow, hive, den, kennel, stable, pond, warren, web, shell, reef, cave
Depends on: animals (mammals, birds, insects, fish/sea, reptiles), places and landforms
Reason: The model knows what animals are but not where they live; habitat entries connect the animal corpus to the places corpus and answer one of children's most common animal questions.
Existing coverage: —

---

## [MISSING] — Levels of Intensity and Gradation
Sequence: middle
Suggested by: 1 model (gemma)
Examples: a little, very, extremely, slightly, quite, enough, too much, a bit, barely, really, sort of, kind of
Depends on: emotions, measurement and comparison (backlog), logic (more/less, all/some/none)
Reason: A child does not just feel "sad" — they feel "a little sad" or "very upset"; degree modifiers are essential for conversational nuance and are not addressed by any existing entry or backlog category.
Existing coverage: —

---

## [MISSING] — Food Groups and Nutrition
Sequence: middle
Suggested by: 1 model (qwen)
Examples: protein, carbohydrate, dairy, grain, fruit, vegetable, fat, sugar, fibre, vitamin, mineral, "this gives you energy", balanced meal
Depends on: foods and drinks, foods fruits, foods vegetables, health and wellness (backlog)
Reason: The corpus names food items but does not categorise them by nutritional function; children frequently learn and discuss food groups in health class and need the conceptual layer ("bread is a grain", "milk has protein") to reason about food beyond naming it.
Existing coverage: —

---

## [MISSING] — Musical Instruments
Sequence: middle
Suggested by: 1 model (qwen)
Examples: guitar, piano, drum, violin, flute, trumpet, recorder, xylophone, string instrument, percussion, wind instrument, keyboard, "play an instrument"
Depends on: art and creative expression (backlog), sensory experiences (backlog — sound), verbs (make, hold)
Reason: No existing or backlog entry covers instruments; children encounter them in school music lessons and bands regularly and need vocabulary to name and describe what they see and hear.
Existing coverage: —

---

## [MISSING] — Shadow and Light Phenomena
Sequence: middle
Suggested by: 1 model (qwen)
Examples: shadow, reflection, rainbow, silhouette, beam, glare, transparent, opaque, mirror, "blocks the light", shine, glow
Depends on: STEM concepts (forces, senses), simple physics: energy and power (backlog), weather and celestial entries (sun, moon)
Reason: Light behaviour — how it bounces, blocks, and bends — is distinct from light as an energy source (Simple Physics) and from weather states; children ask about shadows and rainbows constantly and neither STEM nor the weather file addresses visual phenomena.
Existing coverage: STEM_entries.md (senses/sight covered; light behaviour not explicitly present)

---

## [MISSING] — Garden and Planting Basics
Sequence: middle
Suggested by: 1 model (qwen)
Examples: soil, compost, pot, seed, water, grow, dig, weed, root, sprout, garden bed, germinate, "plant a seed", "give it water and sun"
Depends on: plants and nature, natural life cycles (backlog), environmental care (backlog), tools and kitchenware
Reason: The corpus knows plant species and life cycles but not the practice of gardening; children do planting projects at school and home and need vocabulary for the soil, containers, and actions involved in growing something.
Existing coverage: plants_and_nature_entries.md (plant species defined; growing medium and gardening practice not present)

---

## [MISSING] — Group Roles and Participation
Sequence: middle
Suggested by: 1 model (sakana)
Examples: leader, follower, helper, partner, team member, audience, volunteer, turn-taker, captain, judge, timekeeper, "whose turn is it?"
Depends on: friends and peer interactions (backlog), play, games, and sports (backlog), people and family roles, communication acts and language (backlog)
Reason: Children constantly negotiate roles in group play and classroom tasks; "what does it mean to be the leader?" and "what is an audience?" are specific vocabulary gaps not addressed by the broader Friends or Play categories.
Existing coverage: —

---

## [MISSING] — Evidence and Justification
Sequence: middle
Suggested by: 1 model (gpt)
Examples: because I saw it, I know this because, proof, example, for instance, reason why, that proves, I can show you, evidence
Depends on: logic (fact/opinion, cause/effect, truth), opinions, persuasion, and simple debate (backlog)
Reason: Backing up claims with evidence and examples is reasoning language that goes beyond the abstract logical operators in logic_entries.md; children use it constantly in school arguments and explanations and it is the bridge between "I think X" and "I think X because Y."
Existing coverage: logic_entries.md (cause/effect, fact/opinion covered; evidential language and justification discourse not present)

---

## [MISSING] — Categories and Grouping
Sequence: middle
Suggested by: 1 model (gpt)
Examples: types of, kinds of, belongs to, does not belong, sort, group, set, category, in the same group, classify, "which one fits?", pile, pair, bunch, crowd, row
Depends on: logic concepts (all/some/none), abstract operators, existing taxonomy knowledge (animals, foods, etc.)
Reason: Logic_entries.md has all/some/none but not the classification vocabulary children use to generalise; "what type of animal is a whale?" requires grouping language that the model currently lacks as an explicit register.
Existing coverage: logic_entries.md (all/some/none covered; types-of and grouping vocabulary not present)

---

## [MISSING] — Exceptions and Qualifications
Sequence: middle
Suggested by: 1 model (gpt)
Examples: usually, but sometimes, except, not always, most of the time, in this case, special case, it depends, unless
Depends on: logic (rule, cause/effect, all/some/none), natural life cycles (backlog), safety rules (backlog)
Reason: Without qualification language the model produces rigid absolute statements ("all birds fly"); usually/except/sometimes are the vocabulary of flexible, accurate reasoning and are not addressed anywhere in the corpus or backlog.
Existing coverage: —

---

## [MISSING] — Intentions and Plans in Action
Sequence: middle
Suggested by: 1 model (gpt)
Examples: I'm going to, I plan to, I want to do, next I will, I'm about to, let's, shall we, I decided to, I changed my mind
Depends on: time (future), verbs, wants, needs, and preferences (backlog)
Reason: Short-term conversational intent ("I'm going to pick that up") is distinct from long-term Future Planning and Goals (career aspirations, "when I grow up"); it is the immediate planning language woven through every task and play sequence.
Existing coverage: —

---

## [MISSING] — Accidents and Mistakes
Sequence: middle
Suggested by: 1 model (deepseek)
Examples: accident, oops, by mistake, I didn't mean to, spill, break, bump, fall down, sorry, fix it, consequence, "I wasn't careful", "it was an accident", "how do we fix this?"
Depends on: feeling (sorry/sad/embarrassed), logic (cause/effect, problem/solution), verbs (drop/break/fall)
Reason: Accidents and unintended consequences are a constant feature of children's social narrative; managing them requires a vocabulary of intent, apology, and repair that spans emotional and logical registers — not fully addressed by Manners, Conflict Resolution, or Learning/Memory entries, each of which covers a narrower slice.
Existing coverage: —

---

## [MISSING] — Smells and Tastes
Sequence: middle
Suggested by: 1 model (deepseek)
Examples: sweet, sour, salty, bitter, spicy, smell, stinky, fresh, yummy, yucky, delicious, "it smells like…", "tastes like…", aroma, odour, flavour
Depends on: nose, mouth (body parts), food and drink, sensory experiences (backlog — partially)
Reason: Chemical senses (smell and taste) are among the most immediate sensory experiences children describe and are frequently tied to food, memory, and emotion; the Sensory Experiences category covers broad sensory adjectives but does not give the olfactory and gustatory vocabulary its own depth.
Existing coverage: STEM_entries.md (senses covered as biology; smell/taste adjectives as a descriptive register not dedicated)

---

## [MISSING] — Collections and Collecting
Sequence: middle
Suggested by: 1 model (deepseek)
Examples: collect, sticker, card, set, series, sort, organise, trade, duplicate, complete, album, "I have all of them", "I'm missing one", display, swap
Depends on: hobbies and interests (backlog), categories and grouping (backlog), ownership and sharing (backlog), numbers beyond 10 (backlog)
Reason: Collecting is a primary hobby for 6–10 year olds and generates specific vocabulary around sets, completeness, trading, and organisation that no other category addresses — even Hobbies and Interests, which names collecting as a hobby but does not supply the vocabulary of the practice.
Existing coverage: —

---

## [MISSING] — Sibling Relationships and Dynamics
Sequence: middle
Suggested by: 1 model (deepseek)
Examples: older brother, younger sister, bossing around, sharing a room, tattletale, "it's not fair", middle child, only child, twins, annoying, play together, "they always get to…", "she started it"
Depends on: family roles (people_roles_entries.md), feeling (angry/sad/happy), logic (rule, fair), ownership and sharing (backlog)
Reason: Sibling dynamics are among the richest sources of social language for school-age children; complaints, negotiations, and loyalties with brothers and sisters generate daily conversation that goes well beyond the basic family-member definitions already in the corpus.
Existing coverage: people_roles_entries.md (brother, sister defined as roles; sibling relationship dynamics not addressed)

---

## [MISSING] — Degrees of Truth
Sequence: middle
Suggested by: 1 model (gemini)
Examples: true, false, half-true, sort of, mostly, not exactly, "kind of but not really", exaggerate, approximately, "that's not quite right", "it depends", roughly, close enough
Depends on: logic (truth, fact/opinion), communication acts and language (backlog), uncertainty and guessing (backlog)
Reason: Children encounter statements that are approximately but not exactly true and need language to qualify accuracy; this occupies the space between binary true/false logic and full persuasion/debate — the vocabulary of nuanced everyday factual negotiation.
Existing coverage: logic_entries.md (truth/fact/opinion as binary; graduated or partial accuracy not present)

---

## [MISSING] — Technology and Digital Media
Sequence: late
Suggested by: 4 models (gpt, deepseek, mistral, sakana)
Examples: phone, tablet, computer, TV, remote, game, video, app, button, screen, battery, email, message, "swipe", "tap"
Depends on: time (day/week), logic (rule), feeling (happy/sad), button, light
Reason: Modern children interact with screens daily and may write emails or messages; the model needs everyday media vocabulary and scripts to engage authentically with children's actual lived experience.
Existing coverage: —

---

## [MISSING] — Environmental Care and Stewardship
Sequence: late
Suggested by: 2 models (gpt, sakana)
Examples: recycle, trash/litter, pollution, conserve water, protect animals, plant a tree, save energy, clean up, "take care of the earth"
Depends on: water, river, sea, tree, field, logic (cause/effect), time (future)
Reason: Environmental responsibility language is a high-reuse anchor for explaining cause/effect ("if we litter, animals get hurt") and for school and community norms; builds on nature entries already in the corpus.
Existing coverage: —

---

## [MISSING] — Fractions and Sharing Quantities
Sequence: late
Suggested by: 1 model (gpt)
Examples: half, quarter, third, equal parts, share evenly, "cut in half", "one out of three", "divide into…"
Depends on: logic (part/whole, same/different, all/some/none), number (0-10), addition/subtraction
Reason: Fractions naturally arise in sharing, cooking, and classroom math talk; connects part/whole logic to daily conversation in a way that whole-number entries cannot; standard elementary math topic.
Existing coverage: —

---

## [MISSING] — Perspective-Taking and Theory of Mind
Sequence: late
Suggested by: 1 model (gpt)
Examples: think, know, believe, guess, misunderstand, "I thought…", "they felt…", "she wanted…", "he didn't know that…"
Depends on: logic (truth, fact/opinion, possible/impossible), feeling (happy/sad/angry), time (past)
Reason: School-age benchmarks describe increasing theory-of-mind ability — reasoning about what others think and feel — as a key development for complex social inference and narrative comprehension; not addressable through existing logic or emotion entries alone.
Existing coverage: —

---

## [MISSING] — Humor and Figurative Language
Sequence: late
Suggested by: 1 model (gpt)
Examples: joke, tease, sarcasm, idiom, exaggeration, pun, "it's raining cats and dogs", "break a leg", riddle, "just kidding"
Depends on: logic (fact/opinion, truth), feeling (happy/angry), time (present)
Reason: School-age benchmarks explicitly include recognising and using sarcasm and other nonliteral meanings as conversational competence grows; essential for peer interaction and understanding indirect speech.
Existing coverage: —

---

## [MISSING] — Inclusion, Bullying, and Kindness
Sequence: late
Suggested by: 1 model (gpt)
Examples: include, exclude, bully, stand up for someone, respect, fairness, compassion, "leave them out", "that's not kind", bystander, "be an upstander"
Depends on: logic (rule, problem/solution), feeling (sad/scared/angry), time (future)
Reason: Social rules and protection from bullying are explicitly present in early civic and responsibility standards; children need language to describe, report, and respond to exclusion and unkindness at school.
Existing coverage: —

---

## [MISSING] — Online Safety and Privacy
Sequence: late
Suggested by: 1 model (gpt)
Examples: private/public, password, personal information, stranger online, report/block, "don't share that", screen time, "ask a grown-up"
Depends on: logic (rule, necessary, possible/impossible), feeling (scared), home
Reason: Modern communication skills standards increasingly include digital safety contexts; safety-oriented boundary and refusal strategies extend online as children begin using devices independently — distinct from the general Technology category.
Existing coverage: —

---

## [MISSING] — Civic Responsibility and Community Rules
Sequence: late
Suggested by: 1 model (gpt)
Examples: rights, responsibilities, authority, law, community rules, vote, classroom jobs, "following rules", "what's allowed", citizen
Depends on: logic (rule, order, goal), home, road, time (day/week)
Reason: Social studies frameworks explicitly teach that children and adults follow rules across home, school, and community; becomes everyday talk about civic participation and rule-following behaviour in the late elementary years.
Existing coverage: —

---

## [MISSING] — Learning, Memory, and Metacognition
Sequence: late
Suggested by: 1 model (deepseek)
Examples: learn, remember, forget, practice, try again, make a mistake, figure out, know, guess, "I don't understand", "I need to practise", "I forgot"
Depends on: logic (problem/solution, goal, change, possible/impossible), time (past/future)
Reason: Metacognition emerges in elementary years and is needed for school success and self-regulation; this is distinct from Communication Acts — it covers the child's internal cognitive processes, not speech acts directed at others.
Existing coverage: —

---

## [MISSING] — Future Planning and Goals
Sequence: late
Suggested by: 1 model (sakana)
Examples: grow up, want to be, learn more, try, dream, plan, "when I'm older", "I'm going to…", goal, "someday I will…"
Depends on: school, professions, feeling (happy/excited), time (future)
Reason: Older children start thinking about what they want to do or be; future-oriented language is important for aspirational conversation, goal-setting talk, and discussing the world beyond the present.
Existing coverage: —

---

## [MISSING] — Story Roles and Plot Elements
Sequence: late
Suggested by: 1 model (sakana)
Examples: hero, villain, sidekick, problem in the story, solution, twist, moral, conflict, climax, character, setting, "the lesson is…", "the bad guy"
Depends on: storytelling and narrative structure (backlog), imagination and pretend play (backlog), emotions, logic concepts (cause/effect, problem/solution)
Reason: Storytelling and Narrative Structure covers sequence words (first/then/finally/beginning-middle-end); this covers the characters and plot vocabulary children use when discussing books, films, and games — a distinct and heavily used register.
Existing coverage: —

---

## [MISSING] — Social-Emotional Learning Competencies
Sequence: late
Suggested by: 1 model (gpt)
Examples: self-management, social awareness, empathy, responsible decision-making, "how would you feel if…", self-regulation, "that was a good choice", impulse control
Depends on: feeling (happy/sad/angry), logic (rule, decision, consequence), time (future)
Reason: Widely used SEL frameworks organise children's social functioning into core competencies that strongly predict real-world conversational needs; integrates self, others, relationships, and decision-making into a unified register not yet covered elsewhere.
Existing coverage: —

---

## [MISSING] — Secrets, Surprises, and Keeping Promises
Sequence: late
Suggested by: 1 model (deepseek)
Examples: secret, surprise, promise, keep a secret, break a promise, tell the truth, trust, "I promised I wouldn't tell", surprise party, "cross my heart", "pinky promise", safe secret vs. unsafe secret
Depends on: logic (truth, rule), communication acts and language (backlog), feeling (excited/sad/guilty), boundaries and consent (backlog)
Reason: These social-communicative concepts involve complex moral and emotional reasoning; understanding the difference between a healthy surprise and an unsafe secret is a specific child-protection literacy goal; children use this vocabulary constantly in social settings.
Existing coverage: —

---

## [MISSING] — Praise, Criticism, and Feedback
Sequence: late
Suggested by: 1 model (deepseek)
Examples: well done, good job, try again, that's not right, you can do better, "I like how you…", constructive, improve, feedback, encourage, "what could be different?", praise, critique, "I'm proud of you"
Depends on: learning, memory, and metacognition (backlog), feeling (proud/embarrassed/encouraged), logic (cause/effect, goal)
Reason: School-age children constantly give and receive evaluation from teachers, peers, and family; handling praise and criticism gracefully and using feedback productively are social and academic skills that generate specific vocabulary not addressed elsewhere.
Existing coverage: —

---

## [COVERED] — Movement and Physical Action
Sequence: early
Suggested by: 3 models (gemini, grok, mistral)
Examples: run, jump, climb, kick, throw, catch, swim, dance, hop, crawl, bounce, fall, spin, roll
Depends on: body (leg, arm, foot, hand), ball, hill, tree
Reason: Elementary-age life is highly kinetic; describing play requires verbs that connect the body to objects and environments; necessary for any sports, playground, or PE conversation.
Existing coverage: `verbs_entries.md` now covers many core movement verbs (`walk`, `run`, `jump`, `climb`, `throw`, `catch`, `swim`, `crawl`, `slide`, `roll`, `hop`), and `movement_and_physical_action_entries.md` now anchors `movement`, `exercise`, `balance`, `stretch`, `kick`, `bounce`, `spin`, and `dance`.

---

## [COVERED] — Directions and Navigation
Sequence: early
Suggested by: 2 models (gpt, deepseek)
Examples: left, right, up, down, forward, backward, through, around, across, next to, turn, map, address, route, "go straight", "turn left"
Depends on: space (on/in/under/over/near/far/between), road, bridge, home
Reason: Needed for giving and following directions, playground games, and describing layouts; elementary social studies introduces map concepts that children use to describe places and routes.
Existing coverage: `space_entries.md` covers core positional and path words such as `on`, `in`, `under`, `near`, `between`, `through`, `around`, and `across`. `directions_and_navigation_entries.md` now adds `left`, `right`, `up`, `down`, `forward`, `backward`, `turn`, `go straight`, `map`, `route`, and `address`.

---

## [COVERED] — Meals and Mealtime Talk
Sequence: early
Suggested by: 1 model (gpt)
Examples: breakfast, lunch, dinner, snack, hungry/full, "pass the…", "may I have…", mealtime conversation, table manners, "all done"
Depends on: apple, banana, bread, milk, water, bowl, plate, spoon, time (morning/afternoon/evening), feeling (hungry/thirsty)
Reason: Food items are already known but children also need the routine structure of meals and "how and when we eat" talk; mealtime is a primary site of family conversation and daily narrative.
Existing coverage: `foods_and_drinks_entries.md`, `foods_fruits_entries.md`, and `foods_vegetables_entries.md` cover food items. `meals_and_mealtime_talk_entries.md` now adds `meal`, `breakfast`, `lunch`, `dinner`, `snack`, `hungry`, `full`, `pass something`, and `all done`.

---

## [COVERED] — Sensory Experiences
Sequence: early
Suggested by: 1 model (gemini)
Examples: loud, quiet, soft, hard, sticky, stinky, sweet, sour, rough, smooth, bright, dark, hot, cold, scratchy, noisy, silent, bang, squeak, roar, chirp, melody, whisper
Depends on: ear, skin, nose, mouth, honey, stone, bread, animals (for animal sounds)
Reason: Adjectives describing sensory input are essential for the descriptive language used in elementary storytelling and conversation; connects the five senses to concrete objects the model already knows. Sound vocabulary (named sound types) expanded on suggestion from gemma — roar/chirp/squeak connect to animal entries; bang/noise/melody fill a gap in auditory description.
Existing coverage: `STEM_entries.md` covers the five senses as body/science concepts. `sensory_experiences_entries.md` now adds descriptive sensory language and named sensory events such as `sound`, `loud`, `quiet`, `noisy`, `silent`, `bright`, `dim`, `sticky`, `sweet`, `sour`, `bang`, `squeak`, `roar`, `chirp`, and `melody`.

---

## [PARTIAL] — Health and Wellness
Sequence: middle
Suggested by: 6 models (gpt, deepseek, gemini, grok, mistral, sakana)
Examples: fever, cough, sore throat, stomachache, headache, cut, bruise, bandage, rest, medicine, healthy food, exercise, hygiene, germs, "I feel sick"
Depends on: body parts (head, belly, mouth, nose, skin, bone), food (water, soup), feeling (tired/sad), time (past/present)
Reason: Kids frequently talk about minor injuries and why they stayed home from school; requires a "system" view of the body that connects parts to functions to wellness — the highest-consensus gap across all models after family, school, and routines.
Existing coverage: `health_and_wellness_entries.md` now anchors `health`, `wellness`, `fever`, `cough`, `sore throat`, `headache`, `stomachache`, `cut`, `bruise`, `bandage`, `medicine`, and `germ`. `body_parts_entries.md` still owns body-part vocabulary, and further health habits and symptom coverage can expand later.

---

## [PARTIAL] — Emotions Beyond Basic States
Sequence: middle
Suggested by: 5 models (gpt, deepseek, gemini, grok, mistral)
Examples: lonely, disappointed, nervous, relieved, embarrassed, frustrated, jealous, worried, mixed emotions, "proud and nervous at the same time", emotion triggers
Depends on: feeling (happy/sad/tired), logic (cause/effect, fact/opinion), face, time (past/present)
Reason: School-age communication includes using language to explore mixed and complex emotions; developmental benchmarks emphasise causal storytelling and explaining feelings/events — a register emotions_entries.md covers partially but does not complete.
Existing coverage: `emotions_entries.md` now includes `frustration`, `loneliness`, `excitement`, `confusion`, `boredom`, `nervousness`, `jealousy`, `embarrassment`, `curiosity`, `disappointment`, and `relief` alongside the earlier core emotion anchors. `worried` and mixed-emotion phrasing are still open for later work.

---

## [PARTIAL] — Measurement and Comparison
Sequence: middle
Suggested by: 5 models (gpt, deepseek, gemini, grok, mistral)
Examples: bigger/smaller, taller/shorter, heavier/lighter, faster/slower, hotter/colder, more/less, half full, length, weight, temperature, volume, estimate, measure
Depends on: size, number (0-10), counting, addition/subtraction, shape, logic (same/different, all/some/none), space
Reason: Children compare toys, snacks, heights, and speeds constantly; core elementary math includes measuring and representing data; high-leverage connector for describing choices, observations, and comparisons in daily talk and school tasks.
Existing coverage: `measurement_and_comparison_entries.md` now anchors `measurement`, `comparison`, `bigger`, `smaller`, `taller`, `shorter`, `heavier`, `lighter`, `length`, `height`, `weight`, `capacity`, `distance`, and `estimate`. `mathematical_concepts_entries.md` still owns early number/shape language and `STEM_entries.md` still owns broad physical-property vocabulary.

---

## [PARTIAL] — Natural Life Cycles and Processes
Sequence: middle
Suggested by: 5 models (gpt, deepseek, gemini, grok, mistral)
Examples: water cycle, plant growth, day/night pattern, seasons changing, caterpillar to butterfly, hatch, bloom, melt, freeze, seed → sprout → tree, life cycle
Depends on: sun, moon, rain, snow, river, tree, butterfly, frog, bird, time (season/day/night), logic (cause/effect)
Reason: Everyday child conversation includes "why" questions about nature; school-age communication benchmarks emphasise inferential language and causal sequencing around observable, repeating change in the natural world.
Existing coverage: `natural_life_cycles_and_processes_entries.md` now anchors `life cycle`, `plant growth`, `hatching`, `metamorphosis`, `pollination`, `hibernation`, `decomposition`, `water cycle`, `day and night pattern`, and `season change`. The plant, animal, weather, and STEM files still own the underlying object and science anchors.

---

## [PARTIAL] — Construction and Material Transformations
Sequence: middle
Suggested by: 3 models (gemini, deepseek, mistral)
Examples: melt, freeze, boil, dissolve, break, fix, build, bend, stretch, tear, repair, fold, glue, cut, "it melted", "I fixed it"
Depends on: ice, water, wood, stone, fire, hammer, screw, brick, paper, stick, logic (cause/effect, change, possible/impossible)
Reason: Children are active makers who need to describe the transition of materials from one state to another; explains everyday changes like butter melting, paper tearing, or a broken toy being fixed.
Existing coverage: `construction_and_material_transformations_entries.md` now anchors `construction`, `repair`, `glue something`, `fold something`, `tear something`, `flatten something`, `mold something`, `shred something`, and `crush something`. `STEM_entries.md` still owns the more general science-state verbs such as `melt`, `freeze`, `boil`, `break`, and `fix`.

---

## [PARTIAL] — Cooking and Food Preparation
Sequence: middle
Suggested by: 2 models (deepseek, grok)
Examples: mix, stir, pour, measure, peel, cut, bake, boil, fry, taste, recipe, ingredients, "first you…then you…"
Depends on: spoon, bowl, pot, cup, water, milk, egg, sugar, fire/heat, time (morning/evening)
Reason: Cooking ties together measurement, sequence (first/then/last), material change (liquid to solid), and safety; children help in the kitchen and talk about meals being made.
Existing coverage: `cooking_and_food_preparation_entries.md` now anchors `cooking`, `food preparation`, `recipe`, `ingredient`, `chop food`, `peel food`, `stir food`, `whisk`, `bake`, `simmer`, `season food`, and `knead dough`. `tools_and_kitchenware_entries.md` still owns kitchen tools and the food files still own ingredients as foods.

---

## [PARTIAL] — Community Places and Services
Sequence: middle
Suggested by: 2 models (gpt, grok)
Examples: store, hospital, post office, police station, fire station, park, library, clinic, playground, "where do we go when…?"
Depends on: road, bridge, car, bus, home, logic (rule), time (day/week)
Reason: Children reference community places to explain where events happened and to talk about help, safety, and daily errands; anchors the broader social world beyond home and school.
Existing coverage: `community_places_and_services_entries.md` now anchors `community place`, `service`, `library`, `hospital`, `grocery store`, `fire station`, `police station`, `post office`, `museum`, `restaurant`, `bakery`, and `bus stop`. `places_and_landforms_entries.md` still owns general place vocabulary and `professions_entries.md` still owns role vocabulary.

---

## [PARTIAL] — Opinions, Persuasion, and Simple Debate
Sequence: late
Suggested by: 1 model (gpt)
Examples: I think, I agree/disagree, convince, reasons, evidence, "in my opinion", "I believe", "because…", "the best one is…"
Depends on: logic (fact/opinion, cause/effect, goal), feeling (happy/angry), time (future)
Reason: School-age benchmarks note using language to persuade and advance opinions; children increasingly voice and defend preferences; builds directly on fact/opinion entries in logic_entries.md.
Existing coverage: `opinions_persuasion_and_simple_debate_entries.md` now anchors `opinion`, `I think`, `in my opinion`, `agree`, `disagree`, `persuasion`, `convince`, `reason in an argument`, `evidence`, and `debate`. `logic_entries.md` still owns the more abstract fact/truth and reasoning layer.

---

## [PARTIAL] — Numbers Beyond 10 and Large-Number Talk
Sequence: late
Suggested by: 1 model (gpt)
Examples: numbers to 100 and 1000, place value, "a lot", "hundreds", rounding, "about twenty", "more than fifty"
Depends on: number (0-10), counting, addition/subtraction, logic (more/less)
Reason: Time, money, measurement, and school stories quickly exceed 0–10; extending number talk is essential for believable elementary conversation across most other categories.
Existing coverage: `numbers_beyond_10_and_large_number_talk_entries.md` now anchors `eleven`, `twelve`, `thirteen`, `twenty`, `one hundred`, `one thousand`, `a lot`, `about twenty`, and `more than fifty`. `mathematical_concepts_entries.md` still owns the 0-10 bridge and core operation vocabulary.

---

## [PARTIAL] — Machines and Simple Mechanisms
Sequence: late
Suggested by: 1 model (deepseek)
Examples: pull, push, turn, spin, roll, slide, lift, drop, bounce, lever, wheel, gear, ramp, "how does it work?"
Depends on: wheel, lever, rope, hook, screw, hammer, block, ball
Reason: Physics for children — playground swings, doors, bikes; teaches force and motion in everyday contexts; builds on forces section of STEM entries.
Existing coverage: `machines_and_simple_mechanisms_entries.md` now anchors `machine`, `simple machine`, `ramp`, `wheel`, `axle`, `gear`, `pulley`, `roll`, and `slide`. `STEM_entries.md` still owns the broad force-and-motion concepts such as `push`, `pull`, and `move`.

---

## [PARTIAL] — Growth and Life Stages (Human)
Sequence: late
Suggested by: 1 model (grok)
Examples: baby, toddler, child, grown-up, getting bigger, learning new skills, "I used to…", "when I was little", adult, elder
Depends on: time (past/future), body, family relationships
Reason: Helps children understand their own growth and how family members change over time; supports longer narratives about personal history and future aspirations.
Existing coverage: `growth_and_life_stages_human_entries.md` now anchors `life stage`, `baby`, `toddler`, `child`, `teenager`, `adult`, `grown-up`, `grow up`, and `when I was little`. `people_roles_entries.md` still owns the broad person/family-role vocabulary.

---

## [COVERED] — Family Roles and Kinship
Sequence: early
Suggested by: 6 models (gpt, deepseek, gemini, grok, mistral, sakana)
Examples: mother, father, brother, sister, grandparent, aunt, uncle, cousin, guardian, family
Depends on: home, feeling
Reason: Family members form the foundation of every child's daily conversations about who lives together, helps with tasks, and shares feelings; primary social world and earliest conversational reference point.
Existing coverage: people_roles_entries.md (father, mother, brother, sister, family, husband, wife, neighbour confirmed defined)
> ⚠️ **Coverage flag (gemma):** Only the first 40 lines of people_roles_entries.md have been verified. Extended family (aunt, uncle, cousin, grandparent) appears in the category examples but has not been confirmed present in the file. Verify before treating as fully COVERED.

---

## [COVERED] — Home Rooms and Household Spaces
Sequence: early
Suggested by: 1 model (gpt)
Examples: kitchen, bathroom, bedroom, living room, hallway, garage, garden
Depends on: home, door, window, bed, lamp, table, chair
Reason: Children frequently narrate events by location inside the home, anchoring spatial language and daily routine stories.
Existing coverage: home_rooms_entries.md (5 entries with "room" as anchor)

---

## [COVERED] — Professions and Community Helpers
Sequence: middle
Suggested by: 6 models (gpt, deepseek, gemini, grok, mistral, sakana)
Examples: doctor, nurse, firefighter, police officer, mail carrier, cashier, teacher, builder, baker, farmer, sailor, carpenter
Depends on: car, farm, tools, places (road, farm), logic (goal), feeling (scared/hurt)
Reason: Children ask about what adults do and see community helpers in their neighbourhood every week; health and safety learning depends on knowing which helpers exist and how to communicate with them.
Existing coverage: professions_entries.md (21 entries covering the core set)

---

## [COVERED] — Time, Schedules, and Calendar
Sequence: middle
Suggested by: 3 models (gpt, deepseek, grok)
Examples: clock, o'clock, minutes, a.m./p.m., early/late, schedule, Monday–Sunday, January–December, yesterday/today/tomorrow, weekend
Depends on: time (past/present/future, day/week/month/year/season, morning/afternoon/evening/night), number (0-10)
Reason: Elementary math expectations include telling time and reading a calendar; children use this daily for routines, planning, and scheduling talk.
Existing coverage: time_entries.md (temporal anchors and calendar vocabulary covered)

---

## [COVERED] — Weather and Seasons
Sequence: middle
Suggested by: 3 models (deepseek, gemini, sakana)
Examples: sunny, cloudy, rainy, snowy, windy, temperature, forecast, summer, winter, spring, autumn, "what's the weather like?"
Depends on: sun, rain, snow, wind, ice, frost, time (season)
Reason: Children plan clothing and activities around weather; common everyday topic connecting to clothes, activities, and feelings; also explains why nature changes across the year.
Existing coverage: weather_and_celestial_entries.md (exists; flagged as not yet cleaned in CORPUS_STATUS.md — content present but may need formatting pass)

---

## [COVERED] — Transport and Travel
Sequence: middle
Suggested by: 1 model (sakana)
Examples: car, bus, bike, walk, trip, train, boat, plane, "how do you get to…?", journey, passenger
Depends on: places, objects, daily routines
Reason: Children describe how they get to school or go on trips; transport vocabulary supports practical life conversations and location narratives.
Existing coverage: vehicles_transport_entries.md (10 entries)

---

## Summary

Total categories: 88
  MISSING:  65
  PARTIAL:  17
  COVERED:   6

Categories by sequence:
  early:   34
  middle:  41
  late:    13

---

### Top 12 by model consensus (suggested by most models)

*Note: ties at 5 and 6 models expand the list beyond 10.*

| Rank | Category | Models | Status |
|------|----------|--------|--------|
| 1 | Daily Routines and Self-Care | 6 | MISSING |
| 1 | School Life and Learning | 6 | PARTIAL |
| 1 | Family Roles and Kinship | 6 | COVERED |
| 1 | Health and Wellness | 6 | PARTIAL |
| 1 | Professions and Community Helpers | 6 | COVERED |
| 6 | Manners, Politeness, and Social Etiquette | 5 | MISSING |
| 6 | Safety, Rules, and Emergency Awareness | 5 | MISSING |
| 6 | Play, Games, and Sports | 5 | MISSING |
| 6 | Communication Acts and Language | 5 | MISSING |
| 6 | Emotions Beyond Basic States | 5 | PARTIAL |
| 6 | Measurement and Comparison | 5 | PARTIAL |
| 6 | Natural Life Cycles and Processes | 5 | PARTIAL |

**Highest-priority MISSING entries (6 models, not covered at all):**
Daily Routines and Self-Care

**Highest-priority MISSING entries (5 models):**
Manners/Etiquette · Safety/Rules · Play/Games · Communication Acts

---

### Unique to a single model (review for relevance)

These were suggested by one source only. Flag for editorial review before scheduling.

**gpt only (14):**
Greetings and Social Salutations · Personal Identity and Self-Description ·
Meals and Mealtime Talk · Data, Charts, and Graphs ·
Conflict Resolution and Relationship Repair · Boundaries and Consent ·
Perspective-Taking and Theory of Mind · Humor and Figurative Language ·
Inclusion, Bullying, and Kindness · Online Safety and Privacy ·
Civic Responsibility and Community Rules · Fractions and Sharing Quantities ·
Social-Emotional Learning Competencies · Opinions, Persuasion, and Simple Debate

**deepseek only (12):**
Wants, Needs, and Preferences · Sleep and Rest ·
Machines and Simple Mechanisms · Learning, Memory, and Metacognition ·
Lost and Found / Misplacing Objects · Waiting and Patience ·
Accidents and Mistakes · Smells and Tastes · Collections and Collecting ·
Sibling Relationships and Dynamics ·
Secrets, Surprises, and Keeping Promises · Praise, Criticism, and Feedback

**gemini only (4):**
Sensory Experiences · Containers and Capacity ·
Body States and Internal Cues · Degrees of Truth

**grok only (1):**
Growth and Life Stages (Human)

**sakana only (2):**
Future Planning and Goals · Transport and Travel *(covered by existing wiki file)*

**LFM only (1):**
Seasonal Activities

**gemma only (6):**
Clothing and Apparel · States of Being and Condition · Material Composition ·
Simple Physics: Energy and Power · Animal Habitats and Homes · Levels of Intensity and Gradation

**qwen only (5):**
Animal Care and Pet Keeping · Food Groups and Nutrition · Musical Instruments ·
Shadow and Light Phenomena · Garden and Planting Basics

**sakana only (4):**
Safety Signs and Symbols · Classroom Objects and School Tools ·
Group Roles and Participation · Story Roles and Plot Elements

**gpt only (7):**
Location and Direction in Action · Agreement and Disagreement · Uncertainty and Guessing ·
Evidence and Justification · Categories and Grouping · Exceptions and Qualifications ·
Intentions and Plans in Action
