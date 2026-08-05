# Grounded-story picture books

Status: feasibility demonstrated; production pipeline not yet commissioned.

## Source contracts

The canonical world contract is
`training/corpus_admin/grounded_stories/world_bible.md`. It defines the cast,
places, topology, seasons, and writing rules. The story event specifications
are in `training/corpus_admin/grounded_stories/storylist.txt`.

The corpus has 747 stories in four independently authored language versions,
for 2,988 texts. There is deliberately no source language. A picture-book
compiler must not mark English, German, Japanese, or Chinese as the original
and must not silently translate captions from one of them.

The existing bible fixes personality and world facts but usually does not fix
faces, hair, or clothing. Before production, add a reviewed visual supplement
with:

- front, side, and expression references for every recurring character;
- stable proportions, markings, signature colors, and seasonal outfits;
- exterior and interior reference views for recurring locations;
- object and spatial landmarks from the canonical world bible;
- an immutable revision and an explicit record of every newly chosen detail.

The visual supplement extends the prose bible; it may not contradict it.

## No-source-language visual compilation

Compile each four-language story group into three layers:

1. **Event spine:** facts shared by the story specification and all four
   tellings, such as the rain beginning, the children running to the oak, and
   Biscuit entering the stream.
2. **Parallel narration tracks:** the independently written EN, DE, JP, and ZH
   texts, each retaining its own rhythm, dialogue, and sensory emphasis.
3. **Visual bindings:** shared images for compatible events plus a
   language-specific override only when a visible detail materially differs.

Story 05 demonstrates the distinction. All versions share the same causal
sequence and locations. They differ in phrasing, the number and emphasis of
the first drops, the visual metaphor of the oak as an umbrella in Chinese,
and whether Biscuit sits or lies in the little stream. The first two pages can
use a shared scene. The stream page can either use a posture-neutral image or
provide a Chinese override showing Biscuit lying with his belly in the water.

Page breaks also belong to each narration track. An image may be reused by
several pages or languages; the system must not force four prose traditions
into English paragraph boundaries. Captions and narration remain separate
from pixels, and generated images contain no writing.

This structure gives useful multimodal training pairs: one visual event can be
experienced through four independently authored descriptions, while genuine
language-specific variants teach that close paraphrases need not describe
pixel-identical scenes.

## Character-consistency probe

On 2026-08-01, local `black-forest-labs/FLUX.2-klein-4B` rendered a cast anchor
and two three-page versions of story 05 at 768 x 512. The provisional visual
cast respected the prose bible: Emma and Taro are both eight, and Biscuit is a
medium brown dog. Newly invented hair, facial, and clothing details were
recorded as provisional rather than written into canon.

Two reference topologies were compared:

- **fixed anchor:** every page uses the clean cast sheet;
- **previous-page chain:** each page uses the preceding page.

Emma and Taro stayed strongly recognizable across every page: faces, hair,
Emma's crescent clip, coat colors, boots, apparent age, proportions, and
gouache style survived large changes in pose and setting. The meadow path and
oak also followed the world bible well.

Biscuit exposed the limiting case. One fixed-anchor page created two dogs. The
last chained page created two dogs and redesigned one as shaggy. Chaining also
propagated a large decorative raindrop from one page into the next. The fixed
anchor therefore has the safer default topology; previous pages may be added
as secondary references for scene continuity, but never replace the canonical
character anchor.

Manual pixel review classified the six candidates as three pass, one review,
and two reject. Selecting the good first page from one branch and pages two
and three from the fixed-anchor branch produced a coherent three-page sequence
without further generation. This demonstrates feasibility, not one-shot
reliability.

Measured runtime was 11.8 seconds for the anchor and 13.3 seconds per 768 x 512
page, with 0.968 GiB peak CUDA allocation under sequential CPU offload.

## Continuity validation

Gemma E2B was shown the cast anchor beside each page and asked for character
counts and identity matches. It accepted all six pages and reported one dog in
both two-dog failures. It is not qualified as a picture-book continuity gate.

Continuity acceptance therefore requires:

1. exact cast-count and duplicate checks by a stronger independent visual
   model or a person;
2. character-by-character identity, outfit, markings, and proportion checks;
3. recurring-location landmark checks;
4. detection of chained artifacts and unrequested symbols;
5. scene-content validation against the event spine and the selected language
   binding;
6. pack-wide inspection after all individual pages pass.

The first production validator set should deliberately include missing,
duplicated, merged, recolored, aged, and redesigned characters, plus drifting
locations. A judge is not promoted until it detects those defects against
human labels.

## Recommended production topology

Use a star-shaped reference graph:

```text
canonical character sheets + canonical location sheet
                    |
        +-----------+-----------+
        |           |           |
      page 1      page 2      page 3
        |           |           |
   validate     validate     validate
        +-----------+-----------+
                    |
             pack continuity audit
```

FLUX.2 Klein supports multiple reference images, so production should prefer
separate references for Emma, Taro, Biscuit, and the location when the GPU
profile remains within bounds. The asset schema must be extended from one
`parent_sha256` to an ordered reference list before such outputs become
authoritative; the current single-parent lineage is insufficient.

Probe implementations:

- `meta/scripts/probe_flux_story_consistency.py`;
- `meta/scripts/qualify_gemma_story_continuity.py`.

Authoritative trainbox evidence:

- `/home/aomukai/.local/share/ninereeds/visual/reports/flux_story05_consistency_20260801.json`;
- `/home/aomukai/.local/share/ninereeds/visual/reports/gemma_story05_continuity_20260801.json`.

FLUX.2 Klein officially supports single- and multi-reference editing, with up
to four references for Klein. See the
[BFL FLUX.2 overview](https://docs.bfl.ai/flux_2/flux2_overview),
[official FLUX.2 repository](https://github.com/black-forest-labs/flux2), and
[Diffusers FLUX.2 pipeline documentation](https://huggingface.co/docs/diffusers/api/pipelines/flux2).
