# File Locations

Before following the rewrite instructions below,
note the following file locations:

Input files:
  /media/aomukai/SSD External/Ninereeds/training_data/phase 1 to 5/phase_1_01.md
  through
  /media/aomukai/SSD External/Ninereeds/training_data/phase 1 to 5/phase_1_99.md

Output directory:
  /media/aomukai/SSD External/Ninereeds/training_data/phase 1 to 5/rewritten/

Output naming convention:
  Input phase_1_01.md → Output rewritten/phase_1_01.md
  Input phase_1_02.md → Output rewritten/phase_1_02.md
  (same filename, different directory)

Process the files in batches of 10.
Start with phase_1_01.md through phase_1_10.md.
After completing each batch, confirm how many files
were written and list their names.
Then wait for instruction before continuing
to the next batch.
Create the output directory if it does not exist.

# Rewrite Instruction: Phase 1 → User/Assistant Format

## Your task

Rewrite the Phase 1 training data into [user]/[assistant] format.

## Input format

The source file contains blocks like this:

This is the sun.
The sun is round.
The sun is bright.
The sun is hot.
The sun is yellow in the sky.
The sun is a hot bright ball in the sky.

Each concept appears in four consecutive blocks, each approaching 
the concept from a different angle:
- block 1: properties (what it is, what it looks like)
- block 2: location (where it is in space)
- block 3: process (what it does over time)
- block 4: function (what it gives or does for the world)

## Output format

Convert each block into a [user]/[assistant] pair.

The [user] line is a short question that matches the angle of the block:
- block 1 (properties): "what is X?" or "what does X look like?"
- block 2 (location): "where is X?" or "where can you find X?"
- block 3 (process): "what does X do?" or "how does X change?"
- block 4 (function): "what does X give?" or "what does X do for 
  the world?"

The [assistant] block is the original text, unchanged.

## Example input

This is the sun.
The sun is round.
The sun is bright.
The sun is hot.
The sun is yellow in the sky.
The sun is a hot bright ball in the sky.
This is the sun.
The sun is in the sky.
The sun is above the ground.
The sun is over the trees.
The sun moves across the sky.
The sun is a bright light in the sky.
This is the sun.
The sun rises in the morning.
The sun climbs higher at noon.
The sun moves lower in the afternoon.
The sun sets in the evening.
The sun is a ball of heat that rises and sets.
This is the sun.
The sun gives light to the ground.
The sun warms the road.
The sun dries a wet rock.
The sun makes a shadow on the grass.
The sun is a warm light above the ground.

## Example output

[user]what is the sun?
[assistant]This is the sun.
The sun is round.
The sun is bright.
The sun is hot.
The sun is yellow in the sky.
The sun is a hot bright ball in the sky.

[user]where is the sun?
[assistant]This is the sun.
The sun is in the sky.
The sun is above the ground.
The sun is over the trees.
The sun moves across the sky.
The sun is a bright light in the sky.

[user]what does the sun do?
[assistant]This is the sun.
The sun rises in the morning.
The sun climbs higher at noon.
The sun moves lower in the afternoon.
The sun sets in the evening.
The sun is a ball of heat that rises and sets.

[user]what does the sun give?
[assistant]This is the sun.
The sun gives light to the ground.
The sun warms the road.
The sun dries a wet rock.
The sun makes a shadow on the grass.
The sun is a warm light above the ground.

## Rules

- Do not change any [assistant] text. Copy it exactly.
- Do not add, remove, or reorder blocks.
- Vary the question phrasing slightly across concepts so not every 
  block 1 says "what is X?" — use "what does X look like?" or 
  "describe X" occasionally.
- Keep questions short. Maximum 8 words.
- Do not add any explanation, commentary, or headers.
- Output only the converted [user]/[assistant] pairs.

## Processing instruction

This file is large. Process it in sections.
After each concept group (four blocks = one concept), output the 
result and stop.
Wait for confirmation before continuing to the next concept.
This prevents drift and keeps output quality consistent.