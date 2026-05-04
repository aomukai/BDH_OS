# Rewrite Instruction: Phase 2 → User/Assistant Format
# With Dependency Ordering

## Your task

Rewrite the Phase 2 training data into [user]/[Ninereeds] format,
AND reorder concepts so that constituent parts always appear before
compounds that depend on them.

---

## The dependency problem

Phase 2 contains compound concepts. A compound concept must not
appear before all its parts have been trained.

Known dependency chains in this file:

snow → snowball → snowflake → snowdrift
rain → drop → raindrop → rainfall
water → fall → waterfall
river → bank → riverbank → riverbed
sun → light → sunlight
moon → moonlight
star → starlight
spider → web → spiderweb

Check each concept before placing it. If its parts were not defined
in Phase 1 or earlier in this file, place the parts first.

---

## Phase 1 established concepts (do not redefine these)

The following 99 concepts were defined in Phase 1.
All their vocabulary is available for use in inserted blocks.

sun, moon, star, cloud, rain, snow, wind, river, stone, fire,
dog, cat, bird, fish, frog, horse, butterfly, turtle, worm,
bunny, bee, ant, spider, duck, owl, eagle, crow, swan, robin,
leaf, tree, flower, seed, grass, root, branch, bark, thorn,
water, ice, wave, fog, mud, sand, rock, hill, mountain, valley,
field, forest, path, road, bridge, pond, shore, sky, ground,
roof, wall, door, window, floor, room, house, barn, fence, gate,
boat, wheel, rope, net, box, bag, bowl, cup, pot, jar, bottle,
knife, spoon, fork, plate, brush, broom, nail, hook, button,
hammer, key, lamp, bell, mirror, book, paper, pencil, coin, ball

Note: if a concept you need is not in this list,
define it as a standalone four-block entry BEFORE using it.

---

## Phase 1 vocabulary bank

These words were introduced and grounded in Phase 1.
You may use them freely in inserted blocks:

round, bright, hot, yellow, pale, white, small, thin, flat,
hard, soft, cold, warm, wet, dry, heavy, light, sharp, smooth,
rough, tall, short, wide, narrow, deep, high, low, still, slow,
fast, dark, clear, thick, hollow, curved, straight, open, closed,
long, full, empty

sky, ground, air, water, land, soil, soil, surface, edge, side,
top, bottom, center, middle, corner, hole, gap, layer, ring, line,
point, spot, mark, shape, shadow, path, trail, stream, pool, bank

rise, fall, move, stay, rest, sit, stand, run, walk, fly, swim,
float, sink, spin, roll, slide, climb, drop, flow, grow, spread,
break, crack, melt, freeze, dry, burn, shine, glow, fade, bend,
push, pull, lift, carry, hold, cover, fill, feed, give, take,
reach, touch, open, close, start, stop, change, return

morning, noon, afternoon, evening, night, day, season, time,
year, week, hour, moment, before, after, during, always, never

above, below, over, under, near, far, beside, between, around,
across, through, into, out, along, toward, away, inside, outside,
behind, in front of

animal, plant, living, body, part, group, kind, type, place,
thing, object, material, food, light, heat, sound, air, liquid,
solid, dust, ash, smoke, foam, mist, drop, grain, piece, bit

---

## If a part concept is NOT in the Phase 1 list above

Insert a minimal four-block definition for it BEFORE
the compound that needs it.

All words in inserted blocks must come from the vocabulary
bank above. Do not introduce new vocabulary in inserted blocks.

Grade 4 reading level or below.
No Latin terms, no encyclopedic language, no jargon.
Maximum sentence length: 12 words.

Flag every insertion clearly:
[INSERTED: concept_name]

---

## Input format

Each concept appears in four consecutive blocks of six lines.
Each block approaches the concept from a different angle:
- block 1: properties (what it is, what it looks like)
- block 2: location (where it is in space)
- block 3: process (what it does over time)
- block 4: function (what it gives or does for the world)

---

## Output format

Convert each block into a [user]/[Ninereeds] pair.

Question types by block angle:
- block 1 (properties): "what is X?" or "what does X look like?"
- block 2 (location): "where is X?" or "where can you find X?"
- block 3 (process): "what does X do?" or "how does X change?"
- block 4 (function): "what does X give?" or
  "what does X do for the world?"

Vary question phrasing across concepts.
Do not use the same question form twice in a row.
Maximum question length: 8 words.

---

## Example output (with dependency insert)

[INSERTED: drop]

[user]what is a drop?
[Ninereeds]This is a drop.
A drop is a small round piece of liquid.
A drop is made of water or another liquid.
A drop is very small and light.
A drop falls when it gets heavy enough.
A drop is a tiny round piece of liquid.

[user]where can you find a drop?
[Ninereeds]This is a drop.
A drop can be on a leaf.
A drop can hang from a branch.
A drop can sit on a surface.
A drop falls from the sky or a tap.
A drop is a small piece of liquid found on surfaces.

[user]what does a drop do?
[Ninereeds]This is a drop.
A drop falls when it is heavy.
A drop hits a surface and spreads.
A drop joins other drops.
A drop becomes part of a puddle.
A drop is a piece of liquid that falls and joins others.

[user]what does a drop give?
[Ninereeds]This is a drop.
A drop wets a surface.
A drop feeds a plant.
A drop fills a small space.
A drop adds to a larger body of water.
A drop is a small piece of liquid that wets and fills.

[user]what is a raindrop?
[Ninereeds]This is a raindrop.
The raindrop is small and clear.
The raindrop is made of water.
The raindrop is round.
The raindrop is wet.
A raindrop is a drop of water.

---

## Rules for existing blocks

- Do not change any [Ninereeds] text. Copy it exactly.
- Do not add, remove, or reorder lines within a block.
- Only reorder concept groups (all four blocks move together).

---

## Quality check before each concept group

1. Are all parts of this concept in the Phase 1 list
   or defined earlier in this file?
2. If not, insert the missing parts first.
3. Does the question match the angle of the block?
4. Is all vocabulary in inserted blocks from the bank?

---

## Processing instruction

Process one concept group at a time.
After each concept group, output the result and stop.
Wait for confirmation before continuing.
Flag all insertions: [INSERTED: concept_name]