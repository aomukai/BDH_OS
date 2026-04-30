# Cross-Corpus Introduced Vocabulary Ledger

This file is the canonical ledger for vocabulary introduced across the active Ninereeds training corpus.

It exists to support low-noise curriculum backfill planning and final training-activation audit work.

---

## Purpose

Track which words and compact concept labels are introduced in later corpus layers before they are safely grounded in the curriculum foundation.

Use this ledger to:

- compare Phase 1–6 coverage against later layers
- identify true prerequisite blockers
- route missing high-leverage items into bounded backfill batches
- avoid giant raw uncovered-word dumps
- keep `training_data/phases/dependency_graph.json` aligned with real curriculum prerequisites

---

## Scope

This ledger should eventually cover all active content layers:

- `training_data/phases/` — Phase 1 through Phase 6
- `training_data/wiki/wiki_1/` through `training_data/wiki/wiki_4/`
- `training_data/triplet_stories/tier_1/` through `training_data/triplet_stories/tier_4/`
- `training_data/reasoning/` including:
  - `00_bridge_word_to_symbol.md`
  - `01_bridge_symbol_to_word.md`
  - Sprint 0 through Sprint 4 files
  - `epistemic_uncertainty_stories.md`

Reference-only material under `archive/` is out of scope unless an active document still depends on it.

---

## Low-noise policy

Do not treat every unseen token as equally important.

Prioritize items that are:

1. repeated across many files or layers
2. prerequisite-shaped for later comprehension
3. central to reasoning, explanation, or instruction-following
4. needed by the new reasoning curriculum

Deprioritize items that are:

- one-off decorative tails
- proper-name residue
- formatting artifacts
- inflectional variants that add no new conceptual burden

Compact word families are preferred over noisy raw token lists when the underlying concept is the real issue.

---

## Canonical ledger fields

Use one row per vocabulary item or compact concept family.

| item | type | earliest_non_curriculum_layer | seen_in | phase_1_6_status | priority | recommended_landing_zone | notes |
|------|------|-------------------------------|---------|------------------|----------|--------------------------|-------|

Field notes:

- `item`: the word, phrase, or compact concept family label
- `type`: `word`, `phrase`, `concept_family`, or `operator`
- `earliest_non_curriculum_layer`: first later-layer source where the item clearly matters
- `seen_in`: compact summary of major layers/files using it
- `phase_1_6_status`: `covered`, `partially covered`, `missing`, or `needs verification`
- `priority`: `critical`, `high`, `medium`, `low`, or `tail`
- `recommended_landing_zone`: where to backfill if needed, such as `phase_5`, `phase_6`, `wiki level 1`, or `no backfill needed`
- `notes`: why the item matters, and whether it is a true blocker or just a tail

---

## Seed categories to watch closely

These are especially likely to matter for the new reasoning track:

- number words and operator language
- equation-reading language
- meta-language about words, symbols, meaning, and patterns
- reasoning connectives like `because`, `if`, `then`, `so`
- epistemic language like `know`, `not sure`, `guess`, `check`, `fact`, `true`, `real`, `reason`, `certain`, `uncertain`
- comparison and contradiction language
- instruction and explanation scaffolding words

---

## Working sections

### A. Critical blockers

Populate this section first with items that clearly block comprehension of later layers.

| item | type | earliest_non_curriculum_layer | seen_in | phase_1_6_status | priority | recommended_landing_zone | notes |
|------|------|-------------------------------|---------|------------------|----------|--------------------------|-------|

### B. High-leverage reasoning/support vocabulary

Items that are not total blockers but strongly improve understanding of reasoning, bridge, wiki, or story material.

| item | type | earliest_non_curriculum_layer | seen_in | phase_1_6_status | priority | recommended_landing_zone | notes |
|------|------|-------------------------------|---------|------------------|----------|--------------------------|-------|
| certainly | word | wiki | wiki (1 file) | missing | high | phase_6 | epistemic marker |
| evidence | word | wiki | wiki (5 files) | missing | high | phase_6 | reasoning |
| false | word | wiki | wiki (2 files), reasoning (4 files) | missing | critical | phase_5 | reasoning |
| justification | word | wiki | wiki (4 files) | missing | high | phase_6 | reasoning |
| maybe | word | wiki | wiki (7 files), stories (1 file) | missing | high | phase_6 | epistemic marker |
| possibly | word | wiki | wiki (1 file) | missing | high | phase_6 | epistemic marker |
| probably | word | wiki | wiki (2 files), stories (1 file) | missing | high | phase_6 | epistemic marker |
| proof | word | wiki | wiki (3 files) | missing | high | phase_6 | reasoning |
| uncertain | word | wiki | wiki (3 files) | missing | high | phase_6 | epistemic marker |

### C. Tail / defer candidates

Items that appear uncovered but should usually stay out of the first bounded backfill batches unless later analysis shows they are more central than expected.

| item | type | earliest_non_curriculum_layer | seen_in | phase_1_6_status | priority | recommended_landing_zone | notes |
|------|------|-------------------------------|---------|------------------|----------|--------------------------|-------|

---

## Status

- Created: 2026-04-30
- Current status: first pass complete for high-leverage reasoning/epistemic vocabulary
- Next step: continue populating with other seed categories, then derive the first bounded Phase 1–6 backfill batch
\n\n### training_data/phases/concept_index.md\n\n- `above`\n- `across`\n- `adds`\n- `after`\n- `air`\n- `alligator`\n- `and`\n- `animal`\n- `animals`\n- `ant`\n- `anthill`\n- `ants`\n- `apple`\n- `are`\n- `area`\n- `arm`\n- `arms`\n- `around`\n- `away`\n- `back`\n- `backbone`\n- `bag`\n- `baked`\n- `baking`\n- `ball`\n- `banana`\n- `band`\n- `bank`\n- `bar`\n- `barrier`\n- `base`\n- `basketball`\n- `bat`\n- `bdh`\n- `beach`\n- `beam`\n- `bean`\n- `bed`\n- `bedsheet`\n- `bee`\n- `beehive`\n- `bees`\n- `belly`\n- `belt`\n- `bending`\n- `bends`\n- `berry`\n- `between`\n- `bike`\n- `bird`\n- `birdhouse`\n- `birds`\n- `biting`\n- `blade`\n- `block`\n- `blocks`\n- `blooming`\n- `blue`\n- `blueberry`\n- `board`\n- `boat`\n- `body`\n- `boiling`\n- `bone`\n- `bones`\n- `book`\n- `books`\n- `bookshelf`\n- `bottle`\n- `bottom`\n- `bowl`\n- `box`\n- `branch`\n- `bread`\n- `breadcrumb`\n- `break`\n- `breathing`\n- `brick`\n- `bridge`\n- `brightness`\n- `brings`\n- `broccoli`\n- `broom`\n- `brown`\n- `bucket`\n- `buds`\n- `building`\n- `builds`\n- `bulb`\n- `bunches`\n- `bunny`\n- `burning`\n- `bus`\n- `bushes`\n- `butterfly`\n- `button`\n- `cabbage`\n- `cage`\n- `cake`\n- `can`\n- `car`\n- `cargo`\n- `carries`\n- `carrot`\n- `carrying`\n- `cars`\n- `cart`\n- `carved`\n- `cat`\n- `catch`\n- `catches`\n- `catching`\n- `cauliflower`\n- `caves`\n- `cereal`\n- `chair`\n- `cheese`\n- `chest`\n- `chewing`\n- `chicken`\n- `chirps`\n- `circular`\n- `clam`\n- `clean`\n- `clear`\n- `clicks`\n- `close`\n- `closes`\n- `cloth`\n- `clothing`\n- `cloud`\n- `clover`\n- `cloves`\n- `coat`\n- `cold`\n- `collarbone`\n- `collect`\n- `color`\n- `coloring`\n- `comfort`\n- `concept`\n- `connects`\n- `container`\n- `controls`\n- `cooked`\n- `cookie`\n- `cooking`\n- `cools`\n- `coral`\n- `corn`\n- `cornfield`\n- `corpus`\n- `cover`\n- `covered`\n- `covering`\n- `covers`\n- `cow`\n- `crack`\n- `crawls`\n- `crayon`\n- `cricket`\n- `crops`\n- `crossing`\n- `crunch`\n- `crunchy`\n- `cup`\n- `cupboard`\n- `cupcake`\n- `curved`\n- `cutting`\n- `dark`\n- `day`\n- `decoration`\n- `deep`\n- `definition`\n- `desert`\n- `device`\n- `digging`\n- `digit`\n- `dish`\n- `dishes`\n- `dives`\n- `dog`\n- `doghouse`\n- `doll`\n- `dollhouse`\n- `dolls`\n- `dolphin`\n- `done`\n- `door`\n- `doorbell`\n- `doorknob`\n- `doorstep`\n- `down`\n- `dragonfly`\n- `drawing`\n- `drink`\n- `drinking`\n- `driving`\n- `drop`\n- `drops`\n- `dry`\n- `duck`\n- `dust`\n- `dustpan`\n- `each`\n- `eagle`\n- `ear`\n- `earlobe`\n- `ears`\n- `earth`\n- `eat`\n- `eaten`\n- `eating`\n- `eats`\n- `edge`\n- `egg`\n- `eggs`\n- `eggshell`\n- `end`\n- `ends`\n- `enter`\n- `eye`\n- `eyelid`\n- `eyes`\n- `fall`\n- `falls`\n- `farm`\n- `farmers`\n- `farmhouse`\n- `farmyard`\n- `fast`\n- `fastener`\n- `feathers`\n- `fed`\n- `feeding`\n- `feeds`\n- `feeling`\n- `felt`\n- `field`\n- `fields`\n- `file`\n- `files`\n- `fills`\n- `fin`\n- `find`\n- `fine`\n- `finger`\n- `fingertip`\n- `fire`\n- `firefly`\n- `fish`\n- `fishpond`\n- `flake`\n- `flat`\n- `flies`\n- `floats`\n- `flood`\n- `floors`\n- `flour`\n- `flow`\n- `flower`\n- `flowers`\n- `flows`\n- `fly`\n- `flying`\n- `food`\n- `foot`\n- `for`\n- `forehead`\n- `forest`\n- `forms`\n- `found`\n- `fresh`\n- `frog`\n- `from`\n- `front`\n- `frost`\n- `frozen`\n- `fruit`\n- `furniture`\n- `furry`\n- `gaps`\n- `garden`\n- `garlic`\n- `give`\n- `gives`\n- `glass`\n- `glove`\n- `gobbles`\n- `goods`\n- `goose`\n- `grains`\n- `grape`\n- `grapes`\n- `grass`\n- `grasshopper`\n- `green`\n- `gripping`\n- `ground`\n- `grow`\n- `growing`\n- `grown`\n- `grows`\n- `guide`\n- `guides`\n- `gust`\n- `hair`\n- `hammer`\n- `hamster`\n- `hand`\n- `handle`\n- `handsaw`\n- `hanging`\n- `hard`\n- `has`\n- `hat`\n- `hatband`\n- `hawk`\n- `head`\n- `heads`\n- `heap`\n- `hearing`\n- `heat`\n- `heavy`\n- `help`\n- `helps`\n- `high`\n- `highest`\n- `hill`\n- `hilltop`\n- `hiss`\n- `hisses`\n- `hitting`\n- `hold`\n- `holding`\n- `holds`\n- `hole`\n- `holes`\n- `home`\n- `honey`\n- `hook`\n- `hoop`\n- `hoots`\n- `hops`\n- `horse`\n- `house`\n- `hovers`\n- `how`\n- `hunts`\n- `husks`\n- `ice`\n- `index`\n- `insect`\n- `insects`\n- `inside`\n- `into`\n- `jar`\n- `jaw`\n- `jawbone`\n- `jellyfish`\n- `join`\n- `joining`\n- `joint`\n- `juice`\n- `jumps`\n- `jungle`\n- `keep`\n- `keeping`\n- `keeps`\n- `kept`\n- `key`\n- `knee`\n- `kneecap`\n- `lace`\n- `ladybug`\n- `lamp`\n- `lampshade`\n- `land`\n- `lands`\n- `large`\n- `layers`\n- `lays`\n- `leaf`\n- `leaps`\n- `leave`\n- `leaves`\n- `ledge`\n- `left`\n- `leg`\n- `legs`\n- `lettuce`\n- `lever`\n- `lifting`\n- `light`\n- `lights`\n- `line`\n- `lines`\n- `lips`\n- `liquid`\n- `liquids`\n- `live`\n- `lives`\n- `living`\n- `lizard`\n- `loads`\n- `locking`\n- `long`\n- `loud`\n- `low`\n- `lower`\n- `made`\n- `makes`\n- `making`\n- `many`\n- `mark`\n- `marks`\n- `material`\n- `meadow`\n- `metal`\n- `milk`\n- `milkshake`\n- `moist`\n- `moon`\n- `moonlight`\n- `motor`\n- `motorboat`\n- `mountain`\n- `mountains`\n- `mouse`\n- `mouth`\n- `move`\n- `moved`\n- `movement`\n- `moves`\n- `moving`\n- `much`\n- `nail`\n- `nails`\n- `near`\n- `neck`\n- `needs`\n- `nest`\n- `nests`\n- `night`\n- `nocturnal`\n- `nose`\n- `nuts`\n- `oars`\n- `object`\n- `ocean`\n- `octopus`\n- `often`\n- `oil`\n- `one`\n- `onion`\n- `open`\n- `opening`\n- `opens`\n- `orange`\n- `orchard`\n- `organize`\n- `outer`\n- `outside`\n- `over`\n- `owl`\n- `oyster`\n- `pages`\n- `pale`\n- `pan`\n- `pants`\n- `paper`\n- `part`\n- `patch`\n- `path`\n- `paths`\n- `pea`\n- `pearl`\n- `pecks`\n- `peel`\n- `peeling`\n- `people`\n- `phase`\n- `phases`\n- `piece`\n- `pieces`\n- `pile`\n- `pin`\n- `pinwheel`\n- `place`\n- `placed`\n- `placing`\n- `plane`\n- `plant`\n- `plants`\n- `plate`\n- `play`\n- `playing`\n- `pod`\n- `pointing`\n- `poking`\n- `police`\n- `pond`\n- `pools`\n- `popcorn`\n- `pot`\n- `potato`\n- `pour`\n- `pouring`\n- `powder`\n- `powered`\n- `pressing`\n- `pretend`\n- `prey`\n- `protect`\n- `protection`\n- `protects`\n- `puddles`\n- `puffed`\n- `pulling`\n- `pulls`\n- `pumpkin`\n- `pushes`\n- `quack`\n- `rain`\n- `raincoat`\n- `raindrop`\n- `rainfall`\n- `rat`\n- `raw`\n- `ray`\n- `reading`\n- `recommended`\n- `red`\n- `reefs`\n- `removing`\n- `rest`\n- `resting`\n- `rests`\n- `rice`\n- `riding`\n- `rim`\n- `ring`\n- `rise`\n- `rises`\n- `river`\n- `riverbank`\n- `riverbed`\n- `road`\n- `roads`\n- `rock`\n- `rolling`\n- `room`\n- `root`\n- `rope`\n- `round`\n- `rowboat`\n- `runs`\n- `sailboat`\n- `sailing`\n- `salt`\n- `sand`\n- `sandbox`\n- `sandy`\n- `saw`\n- `scarf`\n- `screw`\n- `screwdriver`\n- `screws`\n- `scurries`\n- `sea`\n- `seashore`\n- `seaweed`\n- `seed`\n- `seeds`\n- `seeing`\n- `seen`\n- `seesaw`\n- `sensing`\n- `sequence`\n- `serving`\n- `set`\n- `shade`\n- `shakes`\n- `shape`\n- `shapes`\n- `shark`\n- `sheep`\n- `sheet`\n- `shelf`\n- `shell`\n- `shelled`\n- `shelter`\n- `shelters`\n- `shinbone`\n- `shines`\n- `ship`\n- `ships`\n- `shirt`\n- `shoe`\n- `shoelace`\n- `shooting`\n- `short`\n- `shoulder`\n- `shovel`\n- `show`\n- `side`\n- `sight`\n- `signal`\n- `sipping`\n- `sits`\n- `sitting`\n- `size`\n- `skin`\n- `sky`\n- `sled`\n- `sleep`\n- `sleeping`\n- `slick`\n- `sliding`\n- `slow`\n- `slowly`\n- `smal`\n- `small`\n- `smelling`\n- `smooth`\n- `snack`\n- `snail`\n- `snake`\n- `snow`\n- `snowball`\n- `snowdrift`\n- `snowflake`\n- `soaks`\n- `soars`\n- `sock`\n- `soft`\n- `softball`\n- `soil`\n- `solid`\n- `someone`\n- `sound`\n- `soup`\n- `space`\n- `speaking`\n- `spider`\n- `spiderweb`\n- `spinach`\n- `spins`\n- `spoon`\n- `spots`\n- `spreading`\n- `squeaks`\n- `squirrel`\n- `stalk`\n- `stand`\n- `standing`\n- `star`\n- `starfish`\n- `starlight`\n- `stars`\n- `steam`\n- `steamboat`\n- `step`\n- `stick`\n- `stickball`\n- `stirring`\n- `stone`\n- `storage`\n- `store`\n- `stores`\n- `storing`\n- `storm`\n- `strands`\n- `strap`\n- `strawberry`\n- `stream`\n- `strength`\n- `strong`\n- `structure`\n- `sun`\n- `sunlight`\n- `support`\n- `supports`\n- `surfaces`\n- `sweatshirt`\n- `sweeping`\n- `sweet`\n- `sweetening`\n- `swept`\n- `swims`\n- `table`\n- `tadpole`\n- `tall`\n- `teeth`\n- `tells`\n- `tentacles`\n- `that`\n- `the`\n- `thick`\n- `thin`\n- `thing`\n- `things`\n- `thinking`\n- `throwing`\n- `thrown`\n- `thumb`\n- `thumbnail`\n- `thunder`\n- `tiny`\n- `tip`\n- `too`\n- `tool`\n- `tooth`\n- `top`\n- `total`\n- `touch`\n- `touches`\n- `touching`\n- `toy`\n- `train`\n- `training`\n- `travel`\n- `traveling`\n- `treat`\n- `tree`\n- `trees`\n- `treetop`\n- `trims`\n- `truck`\n- `tugboat`\n- `tunnels`\n- `turkey`\n- `turning`\n- `turtle`\n- `tying`\n- `under`\n- `upper`\n- `upright`\n- `used`\n- `valley`\n- `vegetable`\n- `vehicle`\n- `very`\n- `view`\n- `vines`\n- `vineyard`\n- `wagon`\n- `walk`\n- `walking`\n- `walks`\n- `walls`\n- `warm`\n- `warms`\n- `warmth`\n- `warning`\n- `washing`\n- `water`\n- `waterfall`\n- `watermelon`\n- `wave`\n- `waves`\n- `weather`\n- `web`\n- `webs`\n- `wet`\n- `wets`\n- `whale`\n- `what`\n- `wheat`\n- `wheel`\n- `wheelbarrow`\n- `where`\n- `white`\n- `wide`\n- `wind`\n- `window`\n- `windowsill`\n- `wine`\n- `winged`\n- `wiped`\n- `with`\n- `wood`\n- `wooded`\n- `woodland`\n- `wool`\n- `work`\n- `world`\n- `worm`\n- `worn`\n- `writing`\n- `yard`\n- `young`\n\n\n### training_data/phases/concept_vocab_bank.md\n\n- `absorb`\n- `absorbs`\n- `access`\n- `added`\n- `adjusts`\n- `afternoon`\n- `again`\n- `against`\n- `age`\n- `alerts`\n- `allows`\n- `along`\n- `anchor`\n- `ankle`\n- `another`\n- `appearing`\n- `appears`\n- `arranged`\n- `ash`\n- `assistant`\n- `attach`\n- `attention`\n- `axle`\n- `baa`\n- `backward`\n- `bake`\n- `bakes`\n- `balance`\n- `balanced`\n- `banks`\n- `barks`\n- `barn`\n- `basket`\n- `bathroom`\n- `beak`\n- `bear`\n- `become`\n- `becomes`\n- `bedroom`\n- `before`\n- `begins`\n- `bell`\n- `below`\n- `bend`\n- `beneath`\n- `beside`\n- `big`\n- `bigger`\n- `birch`\n- `bite`\n- `bites`\n- `bits`\n- `bitten`\n- `blades`\n- `blank`\n- `blanket`\n- `blink`\n- `blinks`\n- `blooms`\n- `both`\n- `bounce`\n- `bounces`\n- `bound`\n- `boundary`\n- `brain`\n- `branches`\n- `breaking`\n- `breaks`\n- `breathe`\n- `breathes`\n- `bricks`\n- `bright`\n- `brighter`\n- `brim`\n- `bring`\n- `bristles`\n- `broken`\n- `bruised`\n- `brush`\n- `brushed`\n- `buckle`\n- `bug`\n- `build`\n- `buildings`\n- `built`\n- `bunch`\n- `burn`\n- `burns`\n- `bush`\n- `busy`\n- `cab`\n- `cactus`\n- `calls`\n- `calm`\n- `cardboard`\n- `carried`\n- `carton`\n- `carving`\n- `castle`\n- `caught`\n- `cave`\n- `cells`\n- `center`\n- `change`\n- `changed`\n- `changes`\n- `chatter`\n- `checks`\n- `chew`\n- `chewed`\n- `chews`\n- `chicks`\n- `chin`\n- `chirp`\n- `circle`\n- `claws`\n- `clay`\n- `cleaned`\n- `cleaning`\n- `cleans`\n- `cleared`\n- `click`\n- `cliff`\n- `climbed`\n- `climbs`\n- `closed`\n- `closet`\n- `clothes`\n- `clouds`\n- `clove`\n- `coast`\n- `coastal`\n- `coiled`\n- `collecting`\n- `collects`\n- `colorful`\n- `colors`\n- `come`\n- `comes`\n- `comfortable`\n- `concepts`\n- `contracts`\n- `cook`\n- `cooks`\n- `cool`\n- `cord`\n- `corner`\n- `counter`\n- `countryside`\n- `court`\n- `cracked`\n- `cracks`\n- `crawl`\n- `creature`\n- `croaks`\n- `crocodile`\n- `crosses`\n- `crumb`\n- `crumble`\n- `crushed`\n- `crust`\n- `crystals`\n- `cups`\n- `curb`\n- `curtain`\n- `cut`\n- `cuts`\n- `daisy`\n- `darker`\n- `darkness`\n- `dawn`\n- `daylight`\n- `debris`\n- `decorated`\n- `decorates`\n- `deeper`\n- `deer`\n- `delivers`\n- `dense`\n- `dependencies`\n- `dependency`\n- `desk`\n- `detail`\n- `detects`\n- `die`\n- `dies`\n- `different`\n- `dig`\n- `digs`\n- `dim`\n- `dimmer`\n- `dims`\n- `direction`\n- `directs`\n- `dirt`\n- `dirty`\n- `disappears`\n- `displays`\n- `distances`\n- `distant`\n- `dive`\n- `dock`\n- `doors`\n- `doorway`\n- `downhill`\n- `downward`\n- `draw`\n- `drawer`\n- `drawings`\n- `draws`\n- `dressed`\n- `dries`\n- `drifts`\n- `drinks`\n- `drip`\n- `driven`\n- `drives`\n- `drunk`\n- `dug`\n- `during`\n- `earring`\n- `edges`\n- `eight`\n- `emptied`\n- `empty`\n- `engine`\n- `engines`\n- `enters`\n- `entrance`\n- `entry`\n- `erode`\n- `erodes`\n- `evening`\n- `everything`\n- `explores`\n- `exposed`\n- `fabric`\n- `face`\n- `faces`\n- `fades`\n- `faint`\n- `falling`\n- `far`\n- `fastened`\n- `faster`\n- `feather`\n- `feathered`\n- `feel`\n- `feels`\n- `feet`\n- `fence`\n- `fibers`\n- `fill`\n- `filled`\n- `finds`\n- `fingers`\n- `finished`\n- `fins`\n- `firm`\n- `first`\n- `fit`\n- `fits`\n- `fixed`\n- `flags`\n- `flakes`\n- `flaps`\n- `flashes`\n- `flex`\n- `flexible`\n- `float`\n- `floor`\n- `flowing`\n- `force`\n- `forth`\n- `forward`\n- `four`\n- `fox`\n- `frame`\n- `fray`\n- `freeze`\n- `friction`\n- `fridge`\n- `full`\n- `game`\n- `games`\n- `gathers`\n- `gets`\n- `gills`\n- `glow`\n- `gobble`\n- `goes`\n- `grasp`\n- `grip`\n- `groove`\n- `groups`\n- `handles`\n- `hanger`\n- `hangs`\n- `happens`\n- `happy`\n- `harbor`\n- `have`\n- `held`\n- `hidden`\n- `hide`\n- `hides`\n- `hits`\n- `hive`\n- `hollow`\n- `hoot`\n- `hot`\n- `hover`\n- `hungry`\n- `husk`\n- `inserted`\n- `insertions`\n- `introducedby`\n- `items`\n- `juicy`\n- `jump`\n- `kitchen`\n- `knife`\n- `ladder`\n- `lake`\n- `layer`\n- `lifts`\n- `like`\n- `lion`\n- `looks`\n- `make`\n- `mammal`\n- `maple`\n- `mast`\n- `monkeys`\n- `more`\n- `moth`\n- `nature`\n- `needing`\n- `new`\n- `ninereeds`\n- `none`\n- `nothing`\n- `number`\n- `nut`\n- `oak`\n- `off`\n- `outline`\n- `paddy`\n- `parts`\n- `person`\n- `pet`\n- `picked`\n- `pig`\n- `pine`\n- `quickly`\n- `reaches`\n- `reef`\n- `reptile`\n- `review`\n- `roof`\n- `rooms`\n- `rose`\n- `sad`\n- `satisfy`\n- `sees`\n- `shine`\n- `shore`\n- `shows`\n- `silk`\n- `sink`\n- `sleeps`\n- `sleepy`\n- `square`\n- `stands`\n- `starts`\n- `stays`\n- `stops`\n- `stove`\n- `summarysentences`\n- `sunflower`\n- `surface`\n- `swim`\n- `taken`\n- `taller`\n- `tell`\n- `tentacle`\n- `there`\n- `these`\n- `thirsty`\n- `this`\n- `three`\n- `tired`\n- `triangle`\n- `unknown`\n- `vocabulary`\n- `wild`\n- `words`\n- `wordsintroduced`\n\n\n### training_data/phases/missing_curriculum_terms.md\n\n- `about`\n- `abstract`\n- `abstractoperatorsentries`\n- `action`\n- `add`\n- `adding`\n- `adjective`\n- `agents`\n- `all`\n- `alternative`\n- `analysis`\n- `answer`\n- `any`\n- `appeared`\n- `applies`\n- `approach`\n- `assume`\n- `assumed`\n- `assumes`\n- `backfill`\n- `batch`\n- `because`\n- `benefits`\n- `bridging`\n- `but`\n- `buy`\n- `candidates`\n- `category`\n- `cent`\n- `centrality`\n- `check`\n- `cognitive`\n- `coin`\n- `command`\n- `communication`\n- `communicationactsandlanguageentries`\n- `compound`\n- `comprehension`\n- `conceptindex`\n- `concrete`\n- `consider`\n- `constraints`\n- `contrast`\n- `could`\n- `count`\n- `countless`\n- `coverage`\n- `create`\n- `created`\n- `creates`\n- `creating`\n- `critical`\n- `cross`\n- `cumulative`\n- `current`\n- `curriculum`\n- `date`\n- `defer`\n- `defining`\n- `depend`\n- `dependencyledger`\n- `depends`\n- `disruptive`\n- `distinct`\n- `distinguish`\n- `docs`\n- `document`\n- `does`\n- `don`\n- `drilling`\n- `earlier`\n- `early`\n- `economic`\n- `encounters`\n- `ensure`\n- `entries`\n- `epistemic`\n- `evidence`\n- `evidenceandjustificationentries`\n- `examples`\n- `exist`\n- `expands`\n- `explains`\n- `explicitly`\n- `extension`\n- `fact`\n- `fifth`\n- `follow`\n- `form`\n- `format`\n- `foundational`\n- `fourth`\n- `frequency`\n- `frequently`\n- `gap`\n- `general`\n- `grounding`\n- `grounds`\n- `group`\n- `happened`\n- `hasn`\n- `heavily`\n- `idea`\n- `identified`\n- `identifies`\n- `imaginary`\n- `imaginationandpretendplayentries`\n- `immediate`\n- `impact`\n- `implementation`\n- `implicitly`\n- `important`\n- `initial`\n- `instead`\n- `language`\n- `late`\n- `learning`\n- `learningmemoryandmetacognitionentries`\n- `less`\n- `letter`\n- `letters`\n- `level`\n- `life`\n- `linguistic`\n- `log`\n- `logic`\n- `logicentries`\n- `loops`\n- `may`\n- `meaning`\n- `means`\n- `medium`\n- `meta`\n- `metacognition`\n- `mind`\n- `missing`\n- `model`\n- `money`\n- `moneytradeandshoppingentries`\n- `most`\n- `nearly`\n- `needed`\n- `never`\n- `not`\n- `noun`\n- `nouns`\n- `objects`\n- `only`\n- `opinion`\n- `opinionspersuasionandsimpledebateentries`\n- `per`\n- `phrases`\n- `physical`\n- `placement`\n- `places`\n- `planned`\n- `practical`\n- `preferred`\n- `price`\n- `primarily`\n- `priorities`\n- `prioritizes`\n- `pronouns`\n- `properly`\n- `purpose`\n- `question`\n- `rankedgaplist`\n- `real`\n- `reality`\n- `really`\n- `recommendation`\n- `recommends`\n- `referenced`\n- `referencing`\n- `related`\n- `relies`\n- `repetition`\n- `resolution`\n- `response`\n- `robust`\n- `rules`\n- `same`\n- `say`\n- `scaffold`\n- `scaffolding`\n- `scenarios`\n- `second`\n- `see`\n- `sell`\n- `sentence`\n- `seventh`\n- `shopping`\n- `sixth`\n- `solution`\n- `some`\n- `something`\n- `speech`\n- `standard`\n- `statement`\n- `status`\n- `story`\n- `storytelling`\n- `storytellingandnarrativestructureentries`\n- `strategy`\n- `strictly`\n- `suffice`\n- `summary`\n- `talk`\n- `teach`\n- `teaches`\n- `teaching`\n- `term`\n- `terms`\n- `than`\n- `them`\n- `think`\n- `third`\n- `thought`\n- `throughout`\n- `tier`\n- `tools`\n- `touched`\n- `tracks`\n- `trainingsequence`\n- `treating`\n- `true`\n- `truth`\n- `txt`\n- `understanding`\n- `unit`\n- `universally`\n- `unless`\n- `until`\n- `update`\n- `usage`\n- `use`\n- `useful`\n- `user`\n- `uses`\n- `using`\n- `validate`\n- `value`\n- `vehicles`\n- `verb`\n- `vocab`\n- `when`\n- `whole`\n- `wiki`\n- `without`\n- `word`\n- `would`\n- `yet`\n- `your`\n\n\n### training_data/phases/phase_1/01_phase_1_eval_report.md\n\n- `always`\n- `appear`\n- `checking`\n- `compared`\n- `comparison`\n- `contains`\n- `corresponding`\n- `direct`\n- `edit`\n- `establish`\n- `eval`\n- `exactly`\n- `filtered`\n- `final`\n- `fix`\n- `flagged`\n- `generated`\n- `grammatically`\n- `integrity`\n- `introductory`\n- `last`\n- `list`\n- `lowercased`\n- `malformed`\n- `markup`\n- `match`\n- `mirrored`\n- `patched`\n- `possessive`\n- `preceded`\n- `preceding`\n- `prefixed`\n- `prior`\n- `regex`\n- `replacement`\n- `report`\n- `result`\n- `rewritten`\n- `sentences`\n- `source`\n- `statistics`\n- `string`\n- `stripped`\n- `subsequent`\n- `text`\n- `their`\n- `tokens`\n- `treated`\n- `variable`\n- `via`\n- `violation`\n- `violations`\n- `was`\n\n\n### training_data/phases/phase_1/phase_1_001.md\n\n- `shadow`\n\n\n### training_data/phases/phase_1/phase_1_002.md\n\n- `houses`\n- `sunset`\n\n\n### training_data/phases/phase_1/phase_1_004.md\n\n- `apart`\n- `looking`\n\n\n### training_data/phases/phase_1/phase_1_005.md\n\n- `washes`\n\n\n### training_data/phases/phase_1/phase_1_006.md\n\n- `piles`\n\n\n### training_data/phases/phase_1/phase_1_007.md\n\n- `weak`\n\n\n### training_data/phases/phase_1/phase_1_010.md\n\n- `fireplace`\n- `flame`\n- `upward`\n\n\n### training_data/phases/phase_1/phase_1_011.md\n\n- `guards`\n- `roams`\n\n\n### training_data/phases/phase_1/phase_1_012.md\n\n- `leap`\n- `meows`\n\n\n### training_data/phases/phase_1/phase_1_013.md\n\n- `sings`\n- `twig`\n\n\n### training_data/phases/phase_1/phase_1_014.md\n\n- `scales`\n\n\n### training_data/phases/phase_1/phase_1_016.md\n\n- `hooves`\n- `mane`\n- `rider`\n- `run`\n\n\n### training_data/phases/phase_1/phase_1_019.md\n\n- `trail`\n\n\n### training_data/phases/phase_1/phase_1_020.md\n\n- `hop`\n\n\n### training_data/phases/phase_1/phase_1_022.md\n\n- `scoop`\n- `scooping`\n- `scoops`\n- `stirs`\n\n\n### training_data/phases/phase_1/phase_1_025.md\n\n- `seat`\n\n\n### training_data/phases/phase_1/phase_1_027.md\n\n- `lock`\n\n\n### training_data/phases/phase_1/phase_1_031.md\n\n- `ripen`\n- `rot`\n\n\n### training_data/phases/phase_1/phase_1_033.md\n\n- `rack`\n\n\n### training_data/phases/phase_1/phase_1_034.md\n\n- `mixes`\n\n\n### training_data/phases/phase_1/phase_1_035.md\n\n- `oval`\n\n\n### training_data/phases/phase_1/phase_1_036.md\n\n- `slices`\n\n\n### training_data/phases/phase_1/phase_1_037.md\n\n- `harden`\n- `sandwich`\n\n\n### training_data/phases/phase_1/phase_1_038.md\n\n- `evaporate`\n- `hands`\n- `rivers`\n\n\n### training_data/phases/phase_1/phase_1_039.md\n\n- `dough`\n- `soften`\n\n\n### training_data/phases/phase_1/phase_1_041.md\n\n- `laces`\n- `sole`\n\n\n### training_data/phases/phase_1/phase_1_042.md\n\n- `heel`\n- `stretchy`\n\n\n### training_data/phases/phase_1/phase_1_043.md\n\n- `shades`\n\n\n### training_data/phases/phase_1/phase_1_045.md\n\n- `put`\n\n\n### training_data/phases/phase_1/phase_1_046.md\n\n- `pockets`\n\n\n### training_data/phases/phase_1/phase_1_048.md\n\n- `wrap`\n\n\n### training_data/phases/phase_1/phase_1_049.md\n\n- `tighten`\n\n\n### training_data/phases/phase_1/phase_1_051.md\n\n- `strike`\n- `swing`\n\n\n### training_data/phases/phase_1/phase_1_052.md\n\n- `loop`\n- `ties`\n\n\n### training_data/phases/phase_1/phase_1_054.md\n\n- `pocket`\n\n\n### training_data/phases/phase_1/phase_1_055.md\n\n- `well`\n\n\n### training_data/phases/phase_1/phase_1_057.md\n\n- `sweep`\n- `sweeps`\n\n\n### training_data/phases/phase_1/phase_1_059.md\n\n- `releases`\n\n\n### training_data/phases/phase_1/phase_1_060.md\n\n- `lift`\n- `load`\n- `pushed`\n\n\n### training_data/phases/phase_1/phase_1_063.md\n\n- `platform`\n- `station`\n- `stations`\n\n\n### training_data/phases/phase_1/phase_1_064.md\n\n- `handlebars`\n- `pedaling`\n- `pedals`\n- `ridden`\n\n\n### training_data/phases/phase_1/phase_1_065.md\n\n- `runway`\n\n\n### training_data/phases/phase_1/phase_1_066.md\n\n- `passengers`\n- `routes`\n- `wheels`\n\n\n### training_data/phases/phase_1/phase_1_067.md\n\n- `runners`\n- `slide`\n\n\n### training_data/phases/phase_1/phase_1_068.md\n\n- `transport`\n\n\n### training_data/phases/phase_1/phase_1_070.md\n\n- `hull`\n- `port`\n- `ports`\n- `vessel`\n\n\n### training_data/phases/phase_1/phase_1_071.md\n\n- `knocked`\n- `tower`\n\n\n### training_data/phases/phase_1/phase_1_072.md\n\n- `kicked`\n\n\n### training_data/phases/phase_1/phase_1_074.md\n\n- `information`\n- `pictures`\n\n\n### training_data/phases/phase_1/phase_1_075.md\n\n- `laid`\n- `lying`\n\n\n### training_data/phases/phase_1/phase_1_076.md\n\n- `shorter`\n\n\n### training_data/phases/phase_1/phase_1_077.md\n\n- `tear`\n\n\n### training_data/phases/phase_1/phase_1_079.md\n\n- `pokes`\n\n\n### training_data/phases/phase_1/phase_1_080.md\n\n- `others`\n- `rectangular`\n- `separate`\n\n\n### training_data/phases/phase_1/phase_1_082.md\n\n- `toes`\n\n\n### training_data/phases/phase_1/phase_1_083.md\n\n- `outward`\n- `pupil`\n- `takes`\n\n\n### training_data/phases/phase_1/phase_1_084.md\n\n- `hear`\n- `hears`\n- `listening`\n- `noise`\n- `responds`\n- `sends`\n\n\n### training_data/phases/phase_1/phase_1_085.md\n\n- `odors`\n- `scents`\n- `smells`\n\n\n### training_data/phases/phase_1/phase_1_086.md\n\n- `sounds`\n- `tongue`\n\n\n### training_data/phases/phase_1/phase_1_087.md\n\n- `gums`\n\n\n### training_data/phases/phase_1/phase_1_088.md\n\n- `muscles`\n- `organs`\n- `stretch`\n\n\n### training_data/phases/phase_1/phase_1_089.md\n\n- `styled`\n\n\n### training_data/phases/phase_1/phase_1_091.md\n\n- `lived`\n- `town`\n\n\n### training_data/phases/phase_1/phase_1_092.md\n\n- `raises`\n\n\n### training_data/phases/phase_1/phase_1_093.md\n\n- `oxygen`\n- `thicker`\n\n\n### training_data/phases/phase_1/phase_1_094.md\n\n- `wilt`\n\n\n### training_data/phases/phase_1/phase_1_097.md\n\n- `raised`\n- `remains`\n- `sides`\n- `spans`\n- `traffic`\n\n\n### training_data/phases/phase_1/phase_1_099.md\n\n- `ripples`\n- `thaw`\n\n\n### training_data/phases/phase_1/phase_1_100.md\n\n- `sheds`\n\n\n### training_data/phases/phase_1/phase_1_103.md\n\n- `beyond`\n- `boats`\n- `crashes`\n- `who`\n\n\n### training_data/phases/phase_1/phase_1_104.md\n\n- `longer`\n- `year`\n\n\n### training_data/phases/phase_1/phase_1_105.md\n\n- `ability`\n- `easy`\n- `safety`\n- `they`\n\n\n### training_data/phases/phase_1/phase_1_106.md\n\n- `lightning`\n- `rumbles`\n- `strikes`\n- `wakes`\n- `warns`\n\n\n### training_data/phases/phase_1/phase_1_108.md\n\n- `muscle`\n\n\n### training_data/phases/phase_1/phase_1_109.md\n\n- `joints`\n- `nearby`\n- `pushing`\n\n\n### training_data/phases/phase_1/phase_1_110.md\n\n- `firmly`\n- `grips`\n- `slipping`\n\n\n### training_data/phases/phase_1/phase_1_111.md\n\n- `climbing`\n- `fold`\n- `hip`\n- `kneeling`\n- `stepping`\n\n\n### training_data/phases/phase_1/phase_1_114.md\n\n- `contents`\n\n\n### training_data/phases/phase_1/phase_1_115.md\n\n- `getting`\n- `jam`\n- `twisting`\n- `twists`\n\n\n### training_data/phases/phase_1/phase_1_116.md\n\n- `spilling`\n\n\n### training_data/phases/phase_1/phase_1_117.md\n\n- `mixed`\n- `spoonful`\n\n\n### training_data/phases/phase_1/phase_1_118.md\n\n- `floating`\n- `meat`\n- `steams`\n- `stirred`\n- `tipped`\n- `vegetables`\n\n\n### training_data/phases/phase_1/phase_1_119.md\n\n- `powdery`\n- `puffs`\n- `thickens`\n\n\n### training_data/phases/phase_1/phase_1_120.md\n\n- `easily`\n- `mix`\n- `sticking`\n\n\n### training_data/phases/phase_1/phase_1_121.md\n\n- `disturbed`\n- `dull`\n- `grey`\n- `must`\n- `settles`\n\n\n### training_data/phases/phase_1/phase_1_122.md\n\n- `spiral`\n- `turned`\n\n\n### training_data/phases/phase_1/phase_1_123.md\n\n- `numbers`\n- `repair`\n- `sac`\n- `traps`\n- `waits`\n\n\n### training_data/phases/phase_1/phase_1_124.md\n\n- `black`\n- `fuzzy`\n- `nectar`\n- `pairs`\n- `pollen`\n- `striped`\n- `stripes`\n\n\n### training_data/phases/phase_1/phase_1_125.md\n\n- `going`\n- `let`\n- `old`\n- `picks`\n- `six`\n- `waist`\n- `works`\n\n\n### training_data/phases/phase_1/phase_1_126.md\n\n- `dried`\n- `farms`\n- `meal`\n- `rows`\n- `season`\n- `summer`\n- `sunny`\n\n\n### training_data/phases/phase_1/phase_1_127.md\n\n- `dunes`\n- `mixing`\n- `settle`\n\n\n### training_data/phases/phase_1/phase_1_128.md\n\n- `burned`\n- `called`\n- `grain`\n- `logs`\n- `planks`\n- `shed`\n- `split`\n- `swells`\n\n\n### training_data/phases/phase_1/phase_1_129.md\n\n- `dangerous`\n- `slippery`\n- `winter`\n\n\n### training_data/phases/phase_1/phase_1_130.md\n\n- `homes`\n- `watch`\n\n\n### training_data/phases/phase_2/phase_2_01.md\n\n- `packed`\n- `roll`\n- `rolls`\n- `wall`\n\n\n### training_data/phases/phase_2/phase_2_02.md\n\n- `melts`\n\n\n### training_data/phases/phase_2/phase_2_03.md\n\n- `higher`\n- `shifts`\n- `spread`\n\n\n### training_data/phases/phase_2/phase_2_04.md\n\n- `joins`\n- `other`\n- `out`\n- `puddle`\n- `splash`\n- `through`\n\n\n### training_data/phases/phase_2/phase_2_05.md\n\n- `heavier`\n- `roofs`\n- `steady`\n- `stop`\n\n\n### training_data/phases/phase_2/phase_2_06.md\n\n- `mist`\n- `pool`\n- `rocks`\n\n\n### training_data/phases/phase_2/phase_2_07.md\n\n- `loses`\n- `next`\n- `stones`\n\n\n### training_data/phases/phase_2/phase_2_08.md\n\n- `sediment`\n- `stony`\n\n\n### training_data/phases/phase_2/phase_2_10.md\n\n- `reflects`\n- `shadows`\n\n\n### training_data/phases/phase_2/phase_2_12.md\n\n- `sticky`\n- `stretched`\n- `stretches`\n\n\n### training_data/phases/phase_2/phase_2_13.md\n\n- `larger`\n- `safe`\n- `wax`\n- `yellow`\n\n\n### training_data/phases/phase_2/phase_2_14.md\n\n- `pole`\n- `provides`\n\n\n### training_data/phases/phase_2/phase_2_15.md\n\n- `mound`\n- `rebuilt`\n\n\n### training_data/phases/phase_2/phase_2_16.md\n\n- `weedy`\n\n\n### training_data/phases/phase_2/phase_2_17.md\n\n- `repaired`\n- `wear`\n\n\n### training_data/phases/phase_2/phase_2_18.md\n\n- `signals`\n- `wings`\n\n\n### training_data/phases/phase_2/phase_2_19.md\n\n- `mounted`\n\n\n### training_data/phases/phase_2/phase_2_20.md\n\n- `pressed`\n- `ringing`\n- `sounding`\n- `visitor`\n\n\n### training_data/phases/phase_2/phase_2_22.md\n\n- `height`\n- `latch`\n- `turn`\n\n\n### training_data/phases/phase_2/phase_2_23.md\n\n- `narrow`\n\n\n### training_data/phases/phase_2/phase_2_24.md\n\n- `organizes`\n- `shelved`\n- `shelves`\n\n\n### training_data/phases/phase_2/phase_2_25.md\n\n- `lies`\n- `mattress`\n- `smoothed`\n- `washed`\n- `wrinkle`\n- `wrinkled`\n\n\n### training_data/phases/phase_2/phase_2_26.md\n\n- `fade`\n- `glare`\n- `reduces`\n- `replaced`\n- `softens`\n- `time`\n\n\n### training_data/phases/phase_2/phase_2_27.md\n\n- `loaf`\n- `rough`\n- `scatters`\n- `smaller`\n- `sticks`\n- `texture`\n\n\n### training_data/phases/phase_2/phase_2_28.md\n\n- `fragile`\n- `separates`\n\n\n### training_data/phases/phase_2/phase_2_29.md\n\n- `melt`\n- `poured`\n- `restaurant`\n- `straw`\n- `thinner`\n\n\n### training_data/phases/phase_2/phase_2_30.md\n\n- `frosted`\n- `frosting`\n- `oven`\n- `taste`\n- `wrapper`\n\n\n### training_data/phases/phase_2/phase_2_31.md\n\n- `fluffy`\n- `heats`\n- `irregular`\n- `kernel`\n- `popped`\n- `popping`\n- `pops`\n- `salted`\n- `served`\n- `theater`\n\n\n### training_data/phases/phase_2/phase_2_32.md\n\n- `knot`\n- `pulled`\n- `secures`\n- `threaded`\n- `tie`\n- `tied`\n- `tight`\n- `undone`\n- `untied`\n\n\n### training_data/phases/phase_2/phase_2_34.md\n\n- `sleeves`\n- `stay`\n- `waterproof`\n\n\n### training_data/phases/phase_2/phase_2_35.md\n\n- `loosen`\n- `removed`\n- `strip`\n- `wraps`\n\n\n### training_data/phases/phase_2/phase_2_36.md\n\n- `materials`\n- `transports`\n- `two`\n- `wheeled`\n\n\n### training_data/phases/phase_2/phase_2_37.md\n\n- `loosens`\n- `removes`\n- `slip`\n- `tightens`\n- `toolbox`\n\n\n### training_data/phases/phase_2/phase_2_38.md\n\n- `lifted`\n\n\n### training_data/phases/phase_2/phase_2_39.md\n\n- `sharp`\n- `toothed`\n- `workbench`\n- `workshop`\n\n\n### training_data/phases/phase_2/phase_2_40.md\n\n- `seats`\n\n\n### training_data/phases/phase_2/phase_2_41.md\n\n- `sail`\n\n\n### training_data/phases/phase_2/phase_2_42.md\n\n- `powerful`\n- `pull`\n- `release`\n- `toward`\n\n\n### training_data/phases/phase_2/phase_2_43.md\n\n- `speed`\n\n\n### training_data/phases/phase_2/phase_2_44.md\n\n- `its`\n- `paddle`\n- `power`\n- `smokestack`\n- `travels`\n- `turns`\n\n\n### training_data/phases/phase_2/phase_2_45.md\n\n- `opened`\n- `rearranged`\n\n\n### training_data/phases/phase_2/phase_2_46.md\n\n- `gym`\n- `passes`\n- `points`\n- `rubber`\n- `scores`\n- `spin`\n\n\n### training_data/phases/phase_2/phase_2_47.md\n\n- `hit`\n- `leather`\n- `pitched`\n- `players`\n- `thread`\n\n\n### training_data/phases/phase_2/phase_2_48.md\n\n- `street`\n\n\n### training_data/phases/phase_2/phase_2_49.md\n\n- `plastic`\n- `playground`\n- `shallow`\n- `shaped`\n\n\n### training_data/phases/phase_2/phase_2_50.md\n\n- `lowers`\n- `motion`\n- `park`\n- `pivot`\n- `point`\n- `tilts`\n\n\n### training_data/phases/phase_2/phase_2_51.md\n\n- `speeds`\n- `spinning`\n\n\n### training_data/phases/phase_2/phase_2_52.md\n\n- `heal`\n- `jewelry`\n- `pierced`\n- `pinched`\n- `slightly`\n- `wearing`\n\n\n### training_data/phases/phase_2/phase_2_53.md\n\n- `position`\n- `returns`\n- `shin`\n- `slides`\n- `straightens`\n- `thigh`\n\n\n### training_data/phases/phase_2/phase_2_54.md\n\n- `eyebrow`\n- `spreads`\n- `tears`\n\n\n### training_data/phases/phase_2/phase_2_55.md\n\n- `pad`\n- `press`\n- `presses`\n- `pressure`\n- `senses`\n- `tap`\n\n\n### training_data/phases/phase_2/phase_2_56.md\n\n- `pick`\n\n\n### training_data/phases/phase_2/phase_2_57.md\n\n- `hips`\n- `row`\n- `spinal`\n- `twist`\n\n\n### training_data/phases/phase_2/phase_2_58.md\n\n- `shift`\n\n\n### training_data/phases/phase_2/phase_2_59.md\n\n- `sweat`\n\n\n### training_data/phases/phase_2/phase_2_60.md\n\n- `just`\n- `weight`\n\n\n### training_data/phases/phase_2/phase_2_61.md\n\n- `injured`\n- `shoulders`\n\n\n### training_data/phases/phase_2/phase_2_62.md\n\n- `middle`\n- `painted`\n\n\n### training_data/phases/phase_2/phase_2_63.md\n\n- `get`\n- `muddy`\n\n\n### training_data/phases/phase_2/phase_2_64.md\n\n- `sways`\n- `trunk`\n\n\n### training_data/phases/phase_2/phase_2_65.md\n\n- `meets`\n- `receives`\n- `tide`\n- `tides`\n- `uneven`\n\n\n### training_data/phases/phase_2/phase_2_66.md\n\n- `farming`\n- `harvested`\n- `produces`\n- `ripens`\n- `stalks`\n- `supplies`\n\n\n### training_data/phases/phase_2/phase_2_67.md\n\n- `landscape`\n- `overlooks`\n- `remain`\n- `slopes`\n- `stable`\n- `windy`\n\n\n### training_data/phases/phase_2/phase_2_68.md\n\n- `habitat`\n- `lose`\n- `quiet`\n- `seasons`\n- `shaded`\n\n\n### training_data/phases/phase_3/phase_3_01.md\n\n- `spill`\n- `spills`\n- `tips`\n\n\n### training_data/phases/phase_3/phase_3_05.md\n\n- `coats`\n- `shiny`\n\n\n### training_data/phases/phase_3/phase_3_06.md\n\n- `boil`\n- `boils`\n- `bubbles`\n- `fan`\n- `lid`\n\n\n### training_data/phases/phase_3/phase_3_07.md\n\n- `drips`\n- `golden`\n- `pours`\n- `sealed`\n- `stored`\n- `tilt`\n\n\n### training_data/phases/phase_3/phase_3_09.md\n\n- `amount`\n\n\n### training_data/phases/phase_3/phase_3_10.md\n\n- `burst`\n- `push`\n- `sudden`\n\n\n### training_data/phases/phase_3/phase_3_12.md\n\n- `lets`\n- `sit`\n\n\n### training_data/phases/phase_3/phase_3_13.md\n\n- `crystal`\n\n\n### training_data/phases/phase_3/phase_3_14.md\n\n- `echoes`\n- `flash`\n- `follows`\n- `quick`\n- `windows`\n\n\n### training_data/phases/phase_3/phase_3_15.md\n\n- `straight`\n\n\n### training_data/phases/phase_3/phase_3_17.md\n\n- `shrinks`\n\n\n### training_data/phases/phase_3/phase_3_18.md\n\n- `drain`\n- `gray`\n\n\n### training_data/phases/phase_3/phase_3_19.md\n\n- `slope`\n\n\n### training_data/phases/phase_3/phase_3_20.md\n\n- `ditch`\n- `lane`\n- `limit`\n- `look`\n- `outermost`\n- `wears`\n\n\n### training_data/phases/phase_3/phase_3_21.md\n\n- `roots`\n\n\n### training_data/phases/phase_3/phase_3_22.md\n\n- `sloped`\n\n\n### training_data/phases/phase_3/phase_3_23.md\n\n- `chip`\n- `chips`\n\n\n### training_data/phases/phase_3/phase_3_24.md\n\n- `bud`\n- `extends`\n- `shake`\n- `stills`\n\n\n### training_data/phases/phase_3/phase_3_25.md\n\n- `behind`\n- `palm`\n- `redden`\n- `reddens`\n- `wrist`\n\n\n### training_data/phases/phase_3/phase_3_26.md\n\n- `section`\n\n\n### training_data/phases/phase_3/phase_3_27.md\n\n- `splinter`\n- `stacks`\n\n\n### training_data/phases/phase_3/phase_3_28.md\n\n- `noon`\n\n\n### training_data/phases/phase_3/phase_3_29.md\n\n- `harder`\n\n\n### training_data/phases/phase_3/phase_3_31.md\n\n- `fur`\n\n\n### training_data/phases/phase_3/phase_3_32.md\n\n- `stronger`\n\n\n### training_data/phases/phase_3/phase_3_33.md\n\n- `sets`\n\n\n### training_data/phases/phase_3/phase_3_34.md\n\n- `hills`\n- `mass`\n\n\n### training_data/phases/phase_3/phase_3_35.md\n\n- `morning`\n\n\n### training_data/phases/phase_3/phase_3_36.md\n\n- `wider`\n\n\n### training_data/phases/phase_3/phase_3_37.md\n\n- `provide`\n- `stacked`\n- `you`\n\n\n### training_data/phases/phase_3/phase_3_40.md\n\n- `take`\n- `temperature`\n- `tomato`\n- `tulip`\n- `wolf`\n\n\n### training_data/phases/phase_4/phase_4_01.md\n\n- `smoke`\n\n\n### training_data/phases/phase_4/phase_4_02.md\n\n- `together`\n\n\n### training_data/phases/phase_4/phase_4_14.md\n\n- `way`\n\n\n### training_data/phases/phase_4/phase_4_15.md\n\n- `while`\n\n\n### training_data/phases/phase_4/phase_4_23.md\n\n- `squeak`\n\n\n### training_data/phases/phase_4/phase_4_24.md\n\n- `scurry`\n\n\n### training_data/phases/phase_4/phase_4_27.md\n\n- `hunt`\n- `soar`\n\n\n### training_data/phases/phase_4/phase_4_30.md\n\n- `wing`\n\n\n### training_data/phases/phase_4/phase_4_37.md\n\n- `spray`\n- `tail`\n\n\n### training_data/phases/phase_4/phase_4_62.md\n\n- `peeled`\n\n\n### training_data/phases/phase_4/phase_4_66.md\n\n- `slice`\n- `sliced`\n- `vine`\n\n\n### training_data/phases/phase_5/phase_5_27.md\n\n- `mud`\n- `onto`\n\n\n### training_data/phases/phase_5/phase_5_33.md\n\n- `leans`\n\n\n### training_data/phases/phase_5/phase_5_39.md\n\n- `slows`\n- `spot`\n- `still`\n\n\n### training_data/phases/phase_6/README.md\n\n- `actual`\n- `choosing`\n- `connective`\n- `controlled`\n- `corpora`\n- `currently`\n- `definitions`\n- `directory`\n- `documenting`\n- `dragon`\n- `elsewhere`\n- `experimental`\n- `families`\n- `free`\n- `handling`\n- `hoc`\n- `isolated`\n- `manifests`\n- `minimal`\n- `missingcurriculumterms`\n- `once`\n- `pass`\n- `post`\n- `prepare`\n- `rather`\n- `repetitive`\n- `repo`\n- `reusable`\n- `spec`\n- `staying`\n- `stories`\n- `storydialogueprogression`\n- `style`\n- `targets`\n- `weekend`\n- `working`\n\n\n### training_data/phases/phase_6/phase_6_01.md\n\n- `read`\n\n\n### training_data/phases/phase_6/phase_6_02.md\n\n- `meanings`\n- `speaks`\n\n\n### training_data/phases/phase_6/phase_6_03.md\n\n- `having`\n- `knowing`\n- `learns`\n- `mean`\n- `thoughts`\n- `understands`\n\n\n### training_data/phases/phase_6/phase_6_05.md\n\n- `asking`\n- `explaining`\n- `repeating`\n- `saying`\n- `telling`\n\n\n### training_data/phases/phase_6/phase_6_06.md\n\n- `puts`\n- `reach`\n- `start`\n- `then`\n- `wants`\n\n\n### training_data/phases/phase_6/phase_6_manifest.md\n\n- `actions`\n- `anchors`\n- `ask`\n- `asks`\n- `audit`\n- `basic`\n- `canonical`\n- `causal`\n- `child`\n- `connect`\n- `details`\n- `draft`\n- `drafted`\n- `drift`\n- `eventually`\n- `explain`\n- `family`\n- `finalized`\n- `finish`\n- `five`\n- `focus`\n- `following`\n- `foundation`\n- `frames`\n- `generation`\n- `goal`\n- `goals`\n- `grid`\n- `interaction`\n- `know`\n- `knowledge`\n- `knows`\n- `leakage`\n- `learn`\n- `logical`\n- `manifest`\n- `name`\n- `order`\n- `ordered`\n- `pattern`\n- `patterns`\n- `plan`\n- `planning`\n- `prerequisite`\n- `progression`\n- `proposed`\n- `rained`\n- `reads`\n- `reason`\n- `reasoning`\n- `record`\n- `repeat`\n- `repeats`\n- `required`\n- `should`\n- `states`\n- `steps`\n- `student`\n- `target`\n- `task`\n- `teacher`\n- `thinks`\n- `understand`\n- `verbs`\n- `verification`\n- `writes`\n\n\n### training_data/phases/phase_6/phase_6_spec.md\n\n- `acceptable`\n- `answers`\n- `approves`\n- `candidate`\n- `cli`\n- `comparing`\n- `compliance`\n- `contract`\n- `control`\n- `core`\n- `decide`\n- `decision`\n- `define`\n- `deliverables`\n- `design`\n- `discipline`\n- `divergence`\n- `doc`\n- `established`\n- `exact`\n- `existing`\n- `exists`\n- `expectations`\n- `fair`\n- `finalize`\n- `flourish`\n- `gemini`\n- `gradual`\n- `happen`\n- `human`\n- `introduction`\n- `jumping`\n- `leak`\n- `listing`\n- `major`\n- `possible`\n- `preserving`\n- `problem`\n- `prose`\n- `random`\n- `relaxed`\n- `repeated`\n- `simple`\n- `specific`\n- `strongly`\n- `substitutions`\n- `sync`\n- `unconstrained`\n- `unnecessary`\n- `whether`\n- `wording`\n\n\n### training_data/phases/phase_6/story_dialogue_progression.md\n\n- `allow`\n- `allowed`\n- `already`\n- `ambiguity`\n- `avoid`\n- `avoids`\n- `bare`\n- `brittle`\n- `causing`\n- `collapse`\n- `collapsing`\n- `compressed`\n- `content`\n- `context`\n- `default`\n- `definitional`\n- `dialogue`\n- `directly`\n- `discourse`\n- `drafting`\n- `elliptical`\n- `every`\n- `example`\n- `exchange`\n- `exchanges`\n- `explicit`\n- `extremely`\n- `fully`\n- `grounded`\n- `highly`\n- `indirect`\n- `intended`\n- `introduce`\n- `introduced`\n- `introducing`\n- `kind`\n- `later`\n- `mapping`\n- `matters`\n- `narrated`\n- `need`\n- `note`\n- `overuse`\n- `own`\n- `prefer`\n- `preserves`\n- `primary`\n- `principle`\n- `prompts`\n- `proposition`\n- `quotation`\n- `quoted`\n- `quotes`\n- `recoverable`\n- `referent`\n- `rely`\n- `replies`\n- `role`\n- `rule`\n- `sake`\n- `says`\n- `semantic`\n- `sparse`\n- `speaker`\n- `stack`\n- `stage`\n- `staged`\n- `storylayerrules`\n- `structurally`\n- `tags`\n- `taught`\n- `those`\n- `trainingdata`\n- `trainingpipeline`\n- `visible`\n- `why`\n\n\n### training_data/reasoning/00_bridge_word_to_symbol.md\n\n- `extracted`\n- `greater`\n\n\n### training_data/reasoning/01_bridge_symbol_to_word.md\n\n- `companion`\n- `equation`\n- `numerals`\n- `readings`\n\n\n### training_data/reasoning/addition_1_digit_facts.md\n\n- `combining`\n\n\n### training_data/reasoning/basic_contradiction_checks.md\n\n- `nighttime`\n\n\n### training_data/reasoning/conditional_if_then.md\n\n- `breast`\n- `therefore`\n\n\n### training_data/reasoning/conservation_of_quantity.md\n\n- `conservation`\n- `rearrange`\n- `rearranging`\n\n\n### training_data/reasoning/contradiction_check_advanced.md\n\n- `paradox`\n\n\n### training_data/reasoning/division_fair_sharing.md\n\n- `distribute`\n- `divided`\n\n\n### training_data/reasoning/epistemic_uncertainty_stories.md\n\n- `collaboration`\n- `communal`\n- `consulting`\n- `cosmos`\n- `formation`\n- `guessed`\n- `judges`\n- `kenji`\n- `kilograms`\n- `lena`\n- `mentioning`\n- `modeled`\n- `nobody`\n- `overstating`\n- `papered`\n- `prevented`\n- `recognizes`\n- `resolves`\n- `resource`\n- `shameful`\n- `sora`\n- `spoke`\n- `stated`\n- `tasted`\n- `uphill`\n\n\n### training_data/reasoning/greater_than_less_than.md\n\n- `kittens`\n- `puppies`\n- `represents`\n\n\n### training_data/reasoning/inverse_operations_check.md\n\n- `calculation`\n- `dividing`\n- `inverse`\n- `multiplied`\n- `received`\n- `subtracted`\n\n\n### training_data/reasoning/mathematical_problems_seed_corpus.md\n\n- `altogether`\n- `decreases`\n- `planted`\n- `removals`\n- `sending`\n- `sprouted`\n- `sum`\n- `television`\n- `traveled`\n\n\n### training_data/reasoning/multiplication_repeated_addition.md\n\n- `marbles`\n\n\n### training_data/reasoning/number_mechanics_successor.md\n\n- `successor`\n\n\n### training_data/reasoning/ordinal_sequencing.md\n\n- `ordinal`\n\n\n### training_data/reasoning/reasoning_corpus.md\n\n- `algorithmic`\n- `bounded`\n- `byte`\n- `collisions`\n- `convergence`\n- `decomposing`\n- `digits`\n- `distributional`\n- `drill`\n- `expressions`\n- `hallucination`\n- `hazard`\n- `inconsistencies`\n- `numeric`\n- `presented`\n- `quad`\n- `reanchors`\n- `regrouping`\n- `reset`\n- `scale`\n- `stabilize`\n- `substrate`\n- `sums`\n- `totals`\n- `triple`\n- `utility`\n- `vetting`\n\n\n### training_data/reasoning/representation_translation_reinforcement.md\n\n- `translation`\n\n\n### training_data/reasoning/rollout_plan.md\n\n- `adapted`\n- `adhere`\n- `adjunct`\n- `adjuncts`\n- `aligning`\n- `articulate`\n- `artificial`\n- `basiccontradictionchecks`\n- `calibration`\n- `categorical`\n- `collaborative`\n- `complements`\n- `conditionalifthen`\n- `conservationofquantity`\n- `consistently`\n- `contradictioncheckadvanced`\n- `costly`\n- `decouples`\n- `density`\n- `divisionfairsharing`\n- `drills`\n- `epistemicuncertaintystories`\n- `equality`\n- `equals`\n- `establishes`\n- `executable`\n- `greaterthanlessthan`\n- `hazards`\n- `inclusionexclusion`\n- `inconsistency`\n- `increased`\n- `inspiration`\n- `interpretations`\n- `invariants`\n- `inverseoperationscheck`\n- `legacy`\n- `linear`\n- `lookup`\n- `magnitude`\n- `mathematicalproblemsseedcorpus`\n- `multiplicationrepeatedaddition`\n- `narrowly`\n- `non`\n- `numbermechanicssuccessor`\n- `ordinalsequencing`\n- `persistence`\n- `progressively`\n- `representation`\n- `representations`\n- `representationtranslationreinforcement`\n- `retrieval`\n- `reversibility`\n- `rigorous`\n- `samevsdifferentbase`\n- `sequential`\n- `sprint`\n- `sprints`\n- `stateful`\n- `subtract`\n- `symbolicsubstitution`\n- `terminology`\n- `transformation`\n- `translated`\n- `translating`\n- `usefully`\n- `variables`\n- `verbal`\n- `zeroandidentityfacts`\n\n\n### training_data/reasoning/subtraction_1_digit_stories.md\n\n- `decreased`\n- `minus`\n\n\n### training_data/reasoning/symbolic_substitution.md\n\n- `substitution`\n\n\n### training_data/reasoning/zero_and_identity_facts.md\n\n- `subtracting`\n\n\n### training_data/triplet_stories/character_registry.md\n\n- `acorn`\n- `ada`\n- `alice`\n- `amy`\n- `apologizes`\n- `argues`\n- `arlo`\n- `ava`\n- `bea`\n- `beth`\n- `biking`\n- `billy`\n- `boyd`\n- `buckles`\n- `cade`\n- `caleb`\n- `casually`\n- `celebrates`\n- `chloe`\n- `clara`\n- `cocoa`\n- `cody`\n- `cole`\n- `cousins`\n- `dean`\n- `delivery`\n- `dragons`\n- `drew`\n- `eli`\n- `ella`\n- `eric`\n- `ethan`\n- `eve`\n- `exercises`\n- `faye`\n- `fern`\n- `fetch`\n- `finn`\n- `forgives`\n- `gabe`\n- `gia`\n- `grace`\n- `grandfather`\n- `grandmother`\n- `grant`\n- `greg`\n- `gus`\n- `gwen`\n- `hank`\n- `hazel`\n- `henry`\n- `herself`\n- `him`\n- `hugh`\n- `hugo`\n- `hugs`\n- `iris`\n- `isaac`\n- `ivy`\n- `jace`\n- `jack`\n- `jade`\n- `jake`\n- `jett`\n- `joel`\n- `jude`\n- `june`\n- `kai`\n- `kate`\n- `kay`\n- `kent`\n- `kicks`\n- `lamb`\n- `lark`\n- `lee`\n- `lemonade`\n- `liam`\n- `lily`\n- `logan`\n- `lucy`\n- `luke`\n- `mae`\n- `mason`\n- `meg`\n- `mia`\n- `mila`\n- `miles`\n- `miller`\n- `mrs`\n- `nash`\n- `nate`\n- `ned`\n- `nell`\n- `nina`\n- `noah`\n- `nora`\n- `olive`\n- `oliver`\n- `opal`\n- `owen`\n- `paints`\n- `paul`\n- `pete`\n- `phil`\n- `phoebe`\n- `pinecones`\n- `policy`\n- `porch`\n- `quinn`\n- `reed`\n- `registry`\n- `reid`\n- `rename`\n- `reviewqueue`\n- `rosa`\n- `ross`\n- `ruby`\n- `ruth`\n- `ryan`\n- `sara`\n- `scott`\n- `scrapes`\n- `seeks`\n- `seth`\n- `silently`\n- `skye`\n- `snowman`\n- `soccer`\n- `son`\n- `sophie`\n- `spells`\n- `tara`\n- `tate`\n- `tess`\n- `theo`\n- `throws`\n- `toby`\n- `todd`\n- `tom`\n- `troy`\n- `unlocks`\n- `vera`\n- `wes`\n- `willa`\n- `wilson`\n- `wobbly`\n- `wren`\n- `wyatt`\n- `zara`\n- `zoe`\n\n\n### training_data/triplet_stories/review_notes.md\n\n- `absolutely`\n- `aligned`\n- `alignment`\n- `animalsandnature`\n- `aphorisms`\n- `attributes`\n- `bodyandhealth`\n- `calibrated`\n- `casing`\n- `christmas`\n- `closest`\n- `compartment`\n- `components`\n- `consistency`\n- `denser`\n- `desired`\n- `explanatory`\n- `exposition`\n- `favor`\n- `foodandmeals`\n- `generality`\n- `generalization`\n- `generalized`\n- `generic`\n- `graphite`\n- `homeanddailylife`\n- `inherited`\n- `lengths`\n- `mechanical`\n- `mismatch`\n- `normalize`\n- `obviously`\n- `overusing`\n- `peopleandrelationships`\n- `playandgames`\n- `reader`\n- `realism`\n- `redundant`\n- `restatement`\n- `rollout`\n- `scenic`\n- `schoolandlearning`\n- `shorten`\n- `slogans`\n- `templates`\n- `toolsandmaking`\n- `unnatural`\n- `usable`\n- `vehiclesandtravel`\n- `verdict`\n- `visibility`\n- `weatherandseasons`\n- `workable`\n- `writerly`\n\n\n### training_data/triplet_stories/rewrite_prompt.md\n\n- `guardrails`\n- `skeleton`\n- `unfinished`\n- `unrelated`\n\n\n### training_data/triplet_stories/story_tier_specs.md\n\n- `ambiguous`\n- `approaching`\n- `archaic`\n- `atmosphere`\n- `clearest`\n- `contrastive`\n- `ellipsis`\n- `endings`\n- `enforce`\n- `excessive`\n- `filler`\n- `flowery`\n- `fuller`\n- `global`\n- `headings`\n- `integrated`\n- `inversion`\n- `literary`\n- `maintain`\n- `markdown`\n- `metaphors`\n- `mini`\n- `moralizing`\n- `morals`\n- `narration`\n- `obscures`\n- `obvious`\n- `paragraph`\n- `paragraphing`\n- `participant`\n- `pasted`\n- `paused`\n- `poetic`\n- `prettiness`\n- `psychological`\n- `reinforce`\n- `relying`\n- `retrofit`\n- `reused`\n- `scenes`\n- `simplicity`\n- `specs`\n- `summarizing`\n- `tagged`\n- `themes`\n- `topical`\n- `vary`\n- `visibly`\n\n\n### training_data/triplet_stories/tier_1/animals_and_nature.md\n\n- `flop`\n- `munch`\n- `pats`\n- `peeking`\n- `petal`\n- `wanders`\n\n\n### training_data/triplet_stories/tier_1/body_and_health.md\n\n- `cracker`\n- `cushion`\n- `indeed`\n- `kiss`\n- `poorly`\n- `seashell`\n- `suds`\n- `twinkles`\n- `velvet`\n- `workout`\n\n\n### training_data/triplet_stories/tier_1/food_and_meals.md\n\n- `mmm`\n- `pluck`\n- `reveals`\n- `sizzle`\n\n\n### training_data/triplet_stories/tier_1/home_and_daily_life.md\n\n- `comfy`\n- `dangle`\n\n\n### training_data/triplet_stories/tier_1/people_and_relationships.md\n\n- `bundle`\n- `chalkboard`\n- `envelopes`\n- `ribbon`\n- `tripped`\n- `vroom`\n- `whimpers`\n\n\n### training_data/triplet_stories/tier_1/play_and_games.md\n\n- `pound`\n\n\n### training_data/triplet_stories/tier_1/school_and_learning.md\n\n- `zips`\n\n\n### training_data/triplet_stories/tier_1/tools_and_making.md\n\n- `pierces`\n- `rotation`\n- `sloshes`\n- `swirls`\n\n\n### training_data/triplet_stories/tier_1/vehicles_and_travel.md\n\n- `approaches`\n- `beams`\n- `cheering`\n- `clack`\n- `flatbed`\n- `massive`\n- `masts`\n- `oar`\n- `stroll`\n- `underfoot`\n- `whistles`\n- `zooming`\n\n\n### training_data/triplet_stories/tier_1/weather_and_seasons.md\n\n- `howls`\n- `moody`\n- `swirling`\n- `wiggle`\n\n\n### training_data/triplet_stories/tier_2/animals_and_nature.md\n\n- `buzzing`\n- `clucks`\n- `delicate`\n- `fleece`\n- `floppy`\n- `handed`\n- `honks`\n- `marching`\n- `milked`\n- `moos`\n- `purrs`\n- `saves`\n- `talons`\n- `tufts`\n- `weaves`\n- `whiskers`\n\n\n### training_data/triplet_stories/tier_2/body_and_health.md\n\n- `croaking`\n- `foam`\n- `holder`\n- `jog`\n- `mint`\n- `mitt`\n- `scrubbing`\n- `sniff`\n- `wiggly`\n- `wrinkles`\n\n\n### training_data/triplet_stories/tier_2/food_and_meals.md\n\n- `crumbles`\n- `jeans`\n- `ladles`\n- `lip`\n- `snip`\n- `spoonfuls`\n- `stool`\n- `thumbs`\n- `twirl`\n- `wicker`\n\n\n### training_data/triplet_stories/tier_2/home_and_daily_life.md\n\n- `flips`\n\n\n### training_data/triplet_stories/tier_2/people_and_relationships.md\n\n- `pat`\n\n\n### training_data/triplet_stories/tier_2/play_and_games.md\n\n- `crown`\n- `handrails`\n- `royal`\n- `yells`\n\n\n### training_data/triplet_stories/tier_2/school_and_learning.md\n\n- `squeezed`\n\n\n### training_data/triplet_stories/tier_2/tools_and_making.md\n\n- `lumps`\n- `newspaper`\n- `sawhorses`\n- `sawing`\n- `snipping`\n- `wiggling`\n\n\n### training_data/triplet_stories/tier_2/vehicles_and_travel.md\n\n- `creaks`\n- `creek`\n- `ducklings`\n- `grazing`\n- `hum`\n- `lint`\n- `mossy`\n- `package`\n- `parked`\n- `plop`\n- `tickets`\n- `tractor`\n- `winds`\n\n\n### training_data/triplet_stories/tier_2/weather_and_seasons.md\n\n- `booms`\n- `diamonds`\n- `flicker`\n- `icy`\n- `jewels`\n- `rounder`\n- `shorts`\n\n\n### training_data/triplet_stories/tier_3/animals_and_nature.md\n\n- `bale`\n- `bossy`\n- `chatters`\n- `crouches`\n- `curls`\n- `dashes`\n- `dew`\n- `escape`\n- `escapes`\n- `flicks`\n- `flopping`\n- `flutters`\n- `gnat`\n- `landed`\n- `march`\n- `nesting`\n- `nibble`\n- `paddles`\n- `pebbles`\n- `rooster`\n- `scratches`\n- `shoo`\n- `snorts`\n- `stuffs`\n- `sway`\n- `swishes`\n- `swoops`\n- `uncurls`\n- `waddles`\n- `woolly`\n\n\n### training_data/triplet_stories/tier_3/body_and_health.md\n\n- `buried`\n- `crease`\n- `creases`\n- `fairy`\n- `fingernails`\n- `fluids`\n- `offers`\n- `ouch`\n- `print`\n- `relaxes`\n- `smooths`\n- `sneezing`\n- `stuffed`\n- `tickles`\n- `yawns`\n\n\n### training_data/triplet_stories/tier_3/food_and_meals.md\n\n- `creamy`\n- `cutter`\n- `elbows`\n- `glows`\n- `pinches`\n- `plucks`\n- `polishes`\n- `ripest`\n- `scrambles`\n- `squirts`\n- `squishes`\n- `stains`\n- `waxy`\n\n\n### training_data/triplet_stories/tier_3/home_and_daily_life.md\n\n- `beeping`\n- `empties`\n- `rip`\n- `tub`\n\n\n### training_data/triplet_stories/tier_3/play_and_games.md\n\n- `aimed`\n- `cheers`\n- `outfit`\n- `peeks`\n- `pump`\n- `slowing`\n- `teacup`\n- `treetops`\n- `west`\n\n\n### training_data/triplet_stories/tier_3/review_notes.md\n\n- `counterparts`\n- `employs`\n- `understandable`\n\n\n### training_data/triplet_stories/tier_3/tools_and_making.md\n\n- `aims`\n- `anyway`\n- `burner`\n- `celery`\n- `clockwise`\n- `curves`\n- `glues`\n- `halfway`\n- `imagines`\n- `moat`\n- `myself`\n- `pinecone`\n- `poster`\n- `ripped`\n- `rocket`\n- `rush`\n- `soaking`\n- `stroke`\n- `swishing`\n- `tallest`\n- `tapes`\n- `tire`\n\n\n### training_data/triplet_stories/tier_3/vehicles_and_travel.md\n\n- `aisle`\n- `armrest`\n- `bobs`\n- `clipboard`\n- `creak`\n- `dots`\n- `frees`\n- `hiking`\n- `horn`\n- `intersection`\n- `jammed`\n- `lighthouse`\n- `parking`\n- `patches`\n- `prints`\n- `races`\n- `scattered`\n- `screech`\n- `seagulls`\n- `snugly`\n- `sprays`\n- `suitcases`\n- `tangled`\n- `ticket`\n- `traces`\n- `trails`\n- `tugs`\n- `unbuckles`\n- `unties`\n\n\n### training_data/triplet_stories/tier_3/weather_and_seasons.md\n\n- `roaring`\n\n\n### training_data/triplet_stories/tier_4/animals_and_nature.md\n\n- `adjust`\n- `binoculars`\n- `buzzes`\n- `coop`\n- `creeps`\n- `cutest`\n- `dip`\n- `flippers`\n- `gulps`\n- `inches`\n- `kneels`\n- `lambs`\n- `lick`\n- `lots`\n- `nibbles`\n- `nudges`\n- `pads`\n- `paw`\n- `paws`\n- `pounces`\n- `ripple`\n- `sneaky`\n- `sniffing`\n- `softly`\n- `spotted`\n- `springtime`\n- `sprinkles`\n- `sunshine`\n- `swallows`\n- `swam`\n- `tangles`\n- `tennis`\n- `territory`\n- `trough`\n- `tuck`\n- `twitches`\n- `twitching`\n- `wag`\n- `wags`\n- `whoo`\n- `wiggles`\n\n\n### training_data/triplet_stories/tier_4/body_and_health.md\n\n- `faucet`\n- `glimpse`\n- `gulp`\n- `hooting`\n- `infection`\n- `itch`\n- `jacks`\n- `lilies`\n- `minty`\n- `palms`\n- `perfume`\n- `restful`\n- `rustling`\n- `scent`\n- `sniffs`\n- `snuggles`\n- `spits`\n- `stings`\n- `stuffy`\n- `swallowing`\n- `tender`\n- `ticking`\n- `tissues`\n- `toothbrush`\n- `toothpaste`\n- `whenever`\n- `worrying`\n\n\n### training_data/triplet_stories/tier_4/food_and_meals.md\n\n- `bubbling`\n- `bubbly`\n- `burnt`\n- `bursts`\n- `buttered`\n- `crispier`\n- `crispy`\n- `cubes`\n- `drizzles`\n- `energized`\n- `feathery`\n- `folds`\n- `grilled`\n- `gritty`\n- `hers`\n- `homemade`\n- `leftover`\n- `licks`\n- `method`\n- `mustache`\n- `poke`\n- `sandwiches`\n- `silky`\n- `sized`\n- `slicer`\n- `slimy`\n- `soak`\n- `soy`\n- `spatula`\n- `stringy`\n- `sweeter`\n- `swirl`\n- `tangy`\n- `thoroughly`\n- `treats`\n- `twirls`\n- `unclean`\n- `wavy`\n- `wedges`\n- `yeast`\n\n\n### training_data/triplet_stories/tier_4/home_and_daily_life.md\n\n- `bubble`\n- `cozy`\n- `crib`\n- `dirtiest`\n- `draped`\n- `driveway`\n- `flickers`\n- `glad`\n- `goodnight`\n- `hose`\n- `leaning`\n- `napkin`\n- `nipple`\n- `pajama`\n- `pantry`\n- `peaceful`\n- `refreshing`\n- `rinses`\n- `rinsing`\n- `rub`\n- `scraping`\n- `scrubs`\n- `soapy`\n- `sponge`\n- `tonight`\n- `wipes`\n- `wobbles`\n\n\n### training_data/triplet_stories/tier_4/people_and_relationships.md\n\n- `arrange`\n- `artwork`\n- `balloons`\n- `belonged`\n- `bent`\n- `brand`\n- `carpet`\n- `delivered`\n- `diagram`\n- `diaper`\n- `downstairs`\n- `flip`\n- `fort`\n- `hopefully`\n- `hugged`\n- `invitations`\n- `laughter`\n- `meow`\n- `nods`\n- `noises`\n- `noisier`\n- `offered`\n- `prizes`\n- `saturday`\n- `searched`\n- `searching`\n- `shy`\n- `slept`\n- `squeezes`\n- `streamers`\n- `teddy`\n- `tiptoes`\n- `wins`\n- `woke`\n\n\n### training_data/triplet_stories/tier_4/play_and_games.md\n\n- `aside`\n- `chaser`\n- `claps`\n- `coach`\n- `creaking`\n- `dances`\n- `defenders`\n- `dice`\n- `drags`\n- `dribbles`\n- `dumps`\n- `faked`\n- `fakes`\n- `fancy`\n- `flown`\n- `footsteps`\n- `goalie`\n- `loading`\n- `net`\n- `oiled`\n- `oldest`\n- `playroom`\n- `pumps`\n- `scoring`\n- `seeker`\n- `slowed`\n- `snug`\n- `sooner`\n- `sorts`\n- `spool`\n- `squares`\n- `swinging`\n- `toe`\n- `tosses`\n- `tucked`\n- `unwinds`\n- `youngest`\n- `zooms`\n\n\n### training_data/triplet_stories/tier_4/review_notes.md\n\n- `contribute`\n- `encyclopedia`\n- `logically`\n\n\n### training_data/triplet_stories/tier_4/school_and_learning.md\n\n- `accidentally`\n- `bead`\n- `chapter`\n- `clears`\n- `completes`\n- `continues`\n- `dips`\n- `flattens`\n- `friday`\n- `himself`\n- `interested`\n- `minute`\n- `notebook`\n- `positions`\n- `rings`\n- `rubs`\n- `rug`\n- `slams`\n- `slips`\n- `squeaky`\n- `successfully`\n- `thinly`\n- `unscrews`\n- `upside`\n- `whispers`\n- `wobble`\n\n\n### training_data/triplet_stories/tier_4/tools_and_making.md\n\n- `adheres`\n- `amazing`\n- `backyard`\n- `became`\n- `blew`\n- `boards`\n- `broth`\n- `cans`\n- `chose`\n- `cobwebs`\n- `crooked`\n- `dipped`\n- `dispenser`\n- `dot`\n- `drained`\n- `entire`\n- `entryway`\n- `fallen`\n- `fulcrum`\n- `glued`\n- `hammered`\n- `hardens`\n- `hung`\n- `installed`\n- `invention`\n- `invisible`\n- `kart`\n- `magical`\n- `mural`\n- `ooze`\n- `outlines`\n- `patio`\n- `piercing`\n- `pitcher`\n- `posts`\n- `puppy`\n- `rinsed`\n- `sawdust`\n- `scrubbed`\n- `seam`\n- `showed`\n- `sip`\n- `skyscraper`\n- `slid`\n- `spaghetti`\n- `sparkled`\n- `spout`\n- `stood`\n- `tasty`\n- `threw`\n- `tidier`\n- `tightened`\n- `tines`\n- `treehouse`\n- `twisted`\n- `unpacked`\n- `watered`\n- `wobbled`\n\n\n### training_data/triplet_stories/tier_4/vehicles_and_travel.md\n\n- `airplane`\n- `airport`\n- `amazed`\n- `announces`\n- `attendant`\n- `blur`\n- `brought`\n- `cabin`\n- `conductor`\n- `confident`\n- `crinkly`\n- `cruise`\n- `deck`\n- `destination`\n- `dolly`\n- `dotted`\n- `driftwood`\n- `dump`\n- `exploring`\n- `fastens`\n- `fastest`\n- `foil`\n- `galaxy`\n- `greasy`\n- `grins`\n- `highway`\n- `hiker`\n- `hums`\n- `intersections`\n- `lap`\n- `loves`\n- `movie`\n- `octagonal`\n- `patchwork`\n- `pedal`\n- `pretends`\n- `quickest`\n- `quilt`\n- `radio`\n- `railing`\n- `rake`\n- `reels`\n- `rumbling`\n- `rushes`\n- `scavenger`\n- `scenery`\n- `seashells`\n- `seasick`\n- `shady`\n- `shouts`\n- `sidewalk`\n- `sledding`\n- `spaceship`\n- `sparkling`\n- `stopped`\n- `treasure`\n- `tug`\n- `tumbles`\n- `turbulence`\n- `whistle`\n- `whoosh`\n- `winding`\n- `wonderful`\n- `wonders`\n- `zags`\n- `zig`\n\n\n### training_data/triplet_stories/tier_4/weather_and_seasons.md\n\n- `adjusted`\n- `braver`\n- `chilly`\n- `crunches`\n- `crunching`\n- `disappeared`\n- `drizzle`\n- `drumming`\n- `flashlights`\n- `footprints`\n- `freezing`\n- `jumped`\n- `patter`\n- `pitter`\n- `shoos`\n- `smiley`\n- `soggy`\n- `sparkle`\n- `sparkles`\n- `sparkly`\n- `splashes`\n- `thud`\n- `tighter`\n- `unzips`\n- `zip`\n\n\n### training_data/wiki/00_ideas.md\n\n- `able`\n- `absent`\n- `afraid`\n- `amenable`\n- `animalsmammals`\n- `anne`\n- `appearanceandhiddenstate`\n- `apples`\n- `arc`\n- `arcs`\n- `balloon`\n- `bark`\n- `began`\n- `believes`\n- `bob`\n- `bowls`\n- `buys`\n- `came`\n- `carry`\n- `chick`\n- `clauses`\n- `clusters`\n- `cocoon`\n- `conceptually`\n- `containing`\n- `correct`\n- `correction`\n- `countable`\n- `cube`\n- `delayed`\n- `demand`\n- `demanding`\n- `developing`\n- `discrete`\n- `distinction`\n- `division`\n- `doesn`\n- `double`\n- `embody`\n- `equally`\n- `ever`\n- `everyone`\n- `exhaustive`\n- `exposure`\n- `failing`\n- `failure`\n- `fallback`\n- `familiar`\n- `flesh`\n- `forced`\n- `forcing`\n- `formats`\n- `given`\n- `gradually`\n- `grouped`\n- `had`\n- `hardest`\n- `her`\n- `however`\n- `ideas`\n- `identify`\n- `implied`\n- `increase`\n- `leaks`\n- `led`\n- `lists`\n- `mat`\n- `mathematical`\n- `mathematicalconcepts`\n- `mathematicalproblems`\n- `measures`\n- `met`\n- `metaphor`\n- `methods`\n- `mommysaysmachine`\n- `multi`\n- `multiplication`\n- `naturallifecycles`\n- `nemotron`\n- `nine`\n- `observed`\n- `occurs`\n- `ones`\n- `opposite`\n- `otherwise`\n- `outcome`\n- `perception`\n- `persistent`\n- `personalidentity`\n- `perspectivetakingandtheoryofmind`\n- `petrol`\n- `phased`\n- `pipe`\n- `plenty`\n- `principles`\n- `progressive`\n- `proper`\n- `propose`\n- `psychology`\n- `pure`\n- `quantity`\n- `rabbit`\n- `reacts`\n- `reliably`\n- `replacing`\n- `restated`\n- `reuses`\n- `reverse`\n- `revisited`\n- `rushed`\n- `sally`\n- `sat`\n- `schema`\n- `seems`\n- `selection`\n- `semantically`\n- `setup`\n- `seven`\n- `several`\n- `shop`\n- `shrink`\n- `shrinking`\n- `simplest`\n- `simultaneously`\n- `situation`\n- `solve`\n- `spending`\n- `strict`\n- `subordinate`\n- `succeed`\n- `syntax`\n- `tests`\n- `though`\n- `took`\n- `tracking`\n- `trains`\n- `triplets`\n- `trying`\n- `typically`\n- `unchanged`\n- `unfolds`\n- `validates`\n- `variety`\n- `waited`\n- `walked`\n- `weighted`\n- `winning`\n- `witness`\n- `yolk`\n\n\n### training_data/wiki/dependency_ledger.md\n\n- `agricultural`\n- `alias`\n- `amphibian`\n- `appearance`\n- `aquatic`\n- `auditing`\n- `avian`\n- `binding`\n- `biology`\n- `botany`\n- `checked`\n- `chemistry`\n- `cluster`\n- `combined`\n- `combustion`\n- `comparatives`\n- `conscious`\n- `cookware`\n- `dimension`\n- `duty`\n- `echoed`\n- `epistemics`\n- `features`\n- `garment`\n- `garments`\n- `geographic`\n- `geography`\n- `geometry`\n- `implicit`\n- `issue`\n- `landform`\n- `lighting`\n- `limbs`\n- `listed`\n- `manipulation`\n- `marked`\n- `mathconcepts`\n- `mealsandtablemannersentries`\n- `mereology`\n- `modal`\n- `modality`\n- `moneyandbasiceconomicsentries`\n- `necessity`\n- `normalizing`\n- `normative`\n- `numerical`\n- `operations`\n- `phenomenon`\n- `positive`\n- `precipitation`\n- `previously`\n- `product`\n- `proximity`\n- `quantifiers`\n- `references`\n- `refers`\n- `regret`\n- `relations`\n- `relative`\n- `require`\n- `satellite`\n- `satiation`\n- `serve`\n- `since`\n- `skill`\n- `spectrum`\n- `spelling`\n- `staple`\n- `sufficiently`\n- `sweetener`\n- `sweets`\n- `tableware`\n- `transportation`\n- `underpin`\n- `utensil`\n- `various`\n\n\n### training_data/wiki/level1_finish_and_level2_start_plan.md\n\n- `abstraction`\n- `acting`\n- `active`\n- `additions`\n- `adjacent`\n- `ahead`\n- `also`\n- `alternate`\n- `alternating`\n- `anatomy`\n- `appearanceandhiddenstateentries`\n- `areas`\n- `audited`\n- `audits`\n- `automatically`\n- `available`\n- `awake`\n- `backlog`\n- `been`\n- `begin`\n- `being`\n- `belong`\n- `belongs`\n- `benefit`\n- `better`\n- `biological`\n- `bloat`\n- `branching`\n- `broad`\n- `broader`\n- `cadence`\n- `cause`\n- `chain`\n- `chains`\n- `characters`\n- `checkpoint`\n- `clarity`\n- `cleanliness`\n- `cleanly`\n- `cleanup`\n- `coherent`\n- `common`\n- `compact`\n- `compete`\n- `complexity`\n- `consistent`\n- `contrasts`\n- `correctly`\n- `criteria`\n- `deferred`\n- `depth`\n- `describe`\n- `descriptive`\n- `detailed`\n- `detected`\n- `did`\n- `disappear`\n- `distinctions`\n- `documented`\n- `domain`\n- `drifting`\n- `duplicate`\n- `effect`\n- `enough`\n- `etc`\n- `evaluation`\n- `event`\n- `expand`\n- `expanding`\n- `expansions`\n- `explanation`\n- `fail`\n- `finishing`\n- `focuses`\n- `followed`\n- `former`\n- `gate`\n- `gates`\n- `genuinely`\n- `good`\n- `habit`\n- `here`\n- `history`\n- `hotspots`\n- `implement`\n- `implemented`\n- `including`\n- `intentional`\n- `interleaving`\n- `inventory`\n- `issues`\n- `justify`\n- `learned`\n- `letting`\n- `levels`\n- `likely`\n- `links`\n- `logged`\n- `machine`\n- `main`\n- `map`\n- `mathematicalproblemsentries`\n- `measurement`\n- `measurementandcomparison`\n- `memory`\n- `mild`\n- `mommy`\n- `mostly`\n- `multiple`\n- `named`\n- `narrative`\n- `narrower`\n- `natural`\n- `naturally`\n- `obstacle`\n- `occurrence`\n- `optional`\n- `ordering`\n- `outcomes`\n- `output`\n- `overall`\n- `overlap`\n- `overly`\n- `owner`\n- `owns`\n- `poor`\n- `pragmatic`\n- `prevents`\n- `probably`\n- `process`\n- `pronoun`\n- `qualities`\n- `questions`\n- `queue`\n- `realistic`\n- `reclassified`\n- `recognize`\n- `reinforcement`\n- `reinforces`\n- `relation`\n- `resolved`\n- `results`\n- `reveal`\n- `rewrite`\n- `richer`\n- `risk`\n- `scene`\n- `scope`\n- `scoped`\n- `scripts`\n- `self`\n- `sense`\n- `sensoryexperiences`\n- `setting`\n- `skip`\n- `smell`\n- `solved`\n- `solving`\n- `spatial`\n- `specialist`\n- `specifically`\n- `splits`\n- `standalone`\n- `state`\n- `stem`\n- `storytierspecs`\n- `strategic`\n- `structures`\n- `subcases`\n- `substructure`\n- `temporal`\n- `textbook`\n- `tiering`\n- `tissue`\n- `todo`\n- `track`\n- `transition`\n- `tripletstories`\n- `truly`\n- `ungrounded`\n- `unique`\n- `variation`\n- `voice`\n- `width`\n- `wikicategorybacklog`\n- `write`\n\n\n### training_data/wiki/ranked_gap_list.md\n\n- `accessible`\n- `actually`\n- `adequately`\n- `affected`\n- `based`\n- `blocking`\n- `cascading`\n- `categoriesandgrouping`\n- `causes`\n- `clarified`\n- `clearer`\n- `conclusion`\n- `confirm`\n- `confusing`\n- `contextually`\n- `continuing`\n- `correctness`\n- `dailyroutines`\n- `deciding`\n- `deduplicate`\n- `depended`\n- `dependent`\n- `dimensions`\n- `discovered`\n- `documentation`\n- `duplicates`\n- `either`\n- `expresses`\n- `filling`\n- `finalization`\n- `findings`\n- `fixes`\n- `hardware`\n- `homeobjects`\n- `housekeeping`\n- `immediately`\n- `improving`\n- `inconsistent`\n- `instability`\n- `instances`\n- `iteration`\n- `materialcomposition`\n- `miss`\n- `organ`\n- `overlaps`\n- `parent`\n- `peripheral`\n- `potential`\n- `potentially`\n- `prerequisites`\n- `prioritize`\n- `problematic`\n- `produce`\n- `propagating`\n- `ranked`\n- `ranking`\n- `rationale`\n- `recommend`\n- `recommendations`\n- `reconciliation`\n- `removal`\n- `remove`\n- `resolutions`\n- `resolve`\n- `resolving`\n- `reviewed`\n- `risky`\n- `scored`\n- `secondary`\n- `sleepandrest`\n- `strengthening`\n- `sufficient`\n- `technically`\n- `tense`\n- `tiers`\n- `unclear`\n- `universal`\n- `urgency`\n- `usages`\n\n\n### training_data/wiki/story_layer_rules.md\n\n- `alternation`\n- `appended`\n- `appropriate`\n- `assigns`\n- `assurance`\n- `boy`\n- `causation`\n- `certainty`\n- `characteristics`\n- `characterregistry`\n- `checklist`\n- `claiming`\n- `clearly`\n- `compression`\n- `condescension`\n- `conditionals`\n- `contextual`\n- `continue`\n- `convention`\n- `crawled`\n- `delay`\n- `element`\n- `encyclopedic`\n- `ending`\n- `evaluating`\n- `exotic`\n- `finalizing`\n- `flew`\n- `framing`\n- `friendly`\n- `helpful`\n- `idioms`\n- `increases`\n- `inserting`\n- `instruction`\n- `involves`\n- `limited`\n- `matches`\n- `mechanically`\n- `modes`\n- `normal`\n- `openings`\n- `paragraphs`\n- `philosophy`\n- `plainly`\n- `pursue`\n- `range`\n- `readable`\n- `realistically`\n- `reasonable`\n- `replace`\n- `reversal`\n- `reviewing`\n- `rubric`\n- `settling`\n- `simplify`\n- `slang`\n- `slight`\n- `slogan`\n- `sparing`\n- `speculation`\n- `storytripletcandidates`\n- `stuck`\n- `surprised`\n- `surprising`\n- `technical`\n- `template`\n- `temporality`\n- `timmy`\n- `tone`\n- `trim`\n- `truthful`\n- `unfamiliar`\n- `unreliable`\n- `urgent`\n- `varied`\n- `weakly`\n- `went`\n- `workflow`\n\n\n### training_data/wiki/story_triplet_candidates.md\n\n- `batches`\n- `bath`\n- `behaviors`\n- `berries`\n- `blow`\n- `blows`\n- `brief`\n- `brushing`\n- `cares`\n- `centered`\n- `chase`\n- `chases`\n- `chasing`\n- `coherence`\n- `conditions`\n- `consists`\n- `cries`\n- `cry`\n- `doing`\n- `drive`\n- `drying`\n- `exercising`\n- `external`\n- `fitting`\n- `forgiven`\n- `gifts`\n- `gluing`\n- `hang`\n- `hay`\n- `helping`\n- `hint`\n- `hug`\n- `hypotheticals`\n- `inviting`\n- `kicking`\n- `kite`\n- `love`\n- `mornings`\n- `negation`\n- `neighbor`\n- `notation`\n- `observe`\n- `occur`\n- `our`\n- `outdoor`\n- `packing`\n- `pain`\n- `painting`\n- `picking`\n- `plays`\n- `plus`\n- `polite`\n- `quietly`\n- `race`\n- `relational`\n- `ride`\n- `running`\n- `sails`\n- `select`\n- `snowballs`\n- `snowflakes`\n- `soap`\n- `spawn`\n- `spell`\n- `splashing`\n- `stacking`\n- `staging`\n- `study`\n- `studying`\n- `tape`\n- `thematically`\n- `towel`\n- `truthfulness`\n- `twigs`\n- `variants`\n- `version`\n- `visits`\n- `wrapping`\n\n\n### training_data/wiki/uncovered_words_routing.md\n\n- `anchored`\n- `choose`\n- `commands`\n- `currency`\n- `domains`\n- `existence`\n- `focusing`\n- `functional`\n- `lack`\n- `ledger`\n- `link`\n- `operator`\n- `pending`\n- `procedural`\n- `routing`\n- `serves`\n- `structural`\n- `subunit`\n- `synonym`\n- `systemic`\n- `triplet`\n- `uncovered`\n\n\n### training_data/wiki/wiki_1/STEM_entries.md\n\n- `anymore`\n- `babies`\n- `bumps`\n- `curve`\n- `death`\n- `gases`\n- `gravel`\n- `hardly`\n- `jug`\n- `polished`\n- `rising`\n- `sinking`\n- `sinks`\n- `solids`\n- `voices`\n- `wire`\n\n\n### training_data/wiki/wiki_1/abstract_operators_entries.md\n\n- `bendable`\n\n\n### training_data/wiki/wiki_1/accidents_and_mistakes_entries.md\n\n- `accidental`\n- `anyone`\n- `beads`\n- `error`\n- `knocking`\n\n\n### training_data/wiki/wiki_1/agreement_and_disagreement_entries.md\n\n- `accept`\n- `cruel`\n- `offer`\n- `refuse`\n\n\n### training_data/wiki/wiki_1/animal_care_and_pet_keeping_entries.md\n\n- `groom`\n- `indoor`\n- `knots`\n- `pee`\n- `poop`\n- `smelly`\n- `vets`\n\n\n### training_data/wiki/wiki_1/animal_habitats_and_homes_entries.md\n\n- `burrows`\n- `hiding`\n- `ledges`\n- `protected`\n- `sheltered`\n- `trap`\n\n\n### training_data/wiki/wiki_1/animals_birds_entries.md\n\n- `chickens`\n- `clucking`\n- `crow`\n- `crows`\n- `ducks`\n- `geese`\n- `hens`\n- `honking`\n- `hooked`\n- `owls`\n- `parrot`\n- `parrots`\n- `peck`\n- `penguins`\n- `quacking`\n- `raven`\n- `ravens`\n- `robin`\n- `robins`\n- `roosters`\n- `sparrow`\n- `sparrows`\n- `swan`\n- `swans`\n- `waddle`\n- `webbed`\n- `worms`\n\n\n### training_data/wiki/wiki_1/animals_fish_entries.md\n\n- `blend`\n- `clams`\n- `crab`\n- `crabs`\n- `creatures`\n- `lakes`\n- `losing`\n- `octopuses`\n- `ponds`\n- `pulse`\n- `salmon`\n- `sharks`\n- `sideways`\n- `sting`\n- `swimmers`\n\n\n### training_data/wiki/wiki_1/animals_insects_arthropods_entries.md\n\n- `arthropod`\n- `arthropods`\n- `beetle`\n- `beetles`\n- `chirping`\n- `crickets`\n- `dragonflies`\n- `earthworms`\n- `feelers`\n- `fireflies`\n- `fliers`\n- `grasshoppers`\n- `grassy`\n- `jointed`\n- `ladybugs`\n- `moths`\n- `mounds`\n- `spiders`\n\n\n### training_data/wiki/wiki_1/animals_mammals_entries.md\n\n- `affection`\n- `antlers`\n- `ape`\n- `apes`\n- `beard`\n- `bears`\n- `birth`\n- `blankets`\n- `bleat`\n- `bleating`\n- `blooded`\n- `booming`\n- `breath`\n- `bunnies`\n- `bushy`\n- `cheeks`\n- `chimp`\n- `chimpanzees`\n- `chimps`\n- `circles`\n- `cities`\n- `clever`\n- `clicking`\n- `closely`\n- `corners`\n- `cows`\n- `dash`\n- `ditches`\n- `dolphins`\n- `expressive`\n- `females`\n- `fences`\n- `fingerprint`\n- `flatter`\n- `flocks`\n- `foxes`\n- `giant`\n- `goat`\n- `goats`\n- `gorillas`\n- `graceful`\n- `grasslands`\n- `graze`\n- `hamsters`\n- `hopping`\n- `horns`\n- `horses`\n- `howl`\n- `howling`\n- `humans`\n- `hunter`\n- `hunters`\n- `hunting`\n- `independent`\n- `largest`\n- `licking`\n- `lions`\n- `loyal`\n- `mainly`\n- `male`\n- `meadows`\n- `mice`\n- `monkey`\n- `months`\n- `moo`\n- `neigh`\n- `orangutans`\n- `owners`\n- `packs`\n- `parents`\n- `pigs`\n- `purring`\n- `quieter`\n- `rabbits`\n- `reddish`\n- `rocky`\n- `scraps`\n- `shear`\n- `sizes`\n- `slim`\n- `smart`\n- `snout`\n- `stables`\n- `steep`\n- `stripe`\n- `stuff`\n- `sturdy`\n- `tails`\n- `thousands`\n- `thump`\n- `tiger`\n- `tigers`\n- `tough`\n- `trained`\n- `underwater`\n- `wagging`\n- `whales`\n- `whistling`\n- `wolves`\n\n\n### training_data/wiki/wiki_1/animals_reptiles_amphibians_entries.md\n\n- `alligators`\n- `amphibians`\n- `bumpier`\n- `crocodiles`\n- `drier`\n- `lizards`\n- `scaly`\n- `snakes`\n- `toad`\n- `toads`\n- `tortoise`\n\n\n### training_data/wiki/wiki_1/art_and_creative_expression_entries.md\n\n- `beauty`\n- `copying`\n- `crayons`\n- `decorating`\n- `erasing`\n- `folding`\n- `hearable`\n- `original`\n- `pencils`\n- `pens`\n- `project`\n- `wetter`\n\n\n### training_data/wiki/wiki_1/body_parts_entries.md\n\n- `blush`\n- `cheek`\n- `earrings`\n- `eyelids`\n- `fingertips`\n- `hairs`\n- `knock`\n- `knuckle`\n- `knuckles`\n- `lungs`\n- `puff`\n- `rib`\n- `ribs`\n- `sensitive`\n- `straighten`\n- `waving`\n\n\n### training_data/wiki/wiki_1/body_states_and_internal_cues_entries.md\n\n- `ache`\n- `aching`\n- `distracting`\n- `heartbeat`\n- `movements`\n- `quicker`\n- `reacting`\n- `scratch`\n- `shivering`\n- `unsteady`\n\n\n### training_data/wiki/wiki_1/boundaries_and_consent_entries.md\n\n- `affects`\n- `crowded`\n- `discomfort`\n- `freely`\n- `hurtful`\n- `remind`\n- `silence`\n- `unwanted`\n\n\n### training_data/wiki/wiki_1/categories_and_grouping_entries.md\n\n- `classifying`\n- `sorting`\n\n\n### training_data/wiki/wiki_1/chores_and_home_responsibilities_entries.md\n\n- `carpets`\n- `garbage`\n- `laundry`\n- `mop`\n- `mopping`\n- `supposed`\n- `tidying`\n- `towels`\n- `vacuuming`\n- `wiping`\n\n\n### training_data/wiki/wiki_1/civic_responsibility_and_community_rules_entries.md\n\n- `citizens`\n- `classrooms`\n- `communities`\n- `fairly`\n- `forbidden`\n- `luck`\n- `marking`\n- `privilege`\n- `privileges`\n- `students`\n- `voting`\n- `wishes`\n\n\n### training_data/wiki/wiki_1/classroom_objects_and_school_tools_entries.md\n\n- `attached`\n- `bold`\n- `erased`\n- `erasers`\n- `neatly`\n- `posters`\n- `rulers`\n- `sharpeners`\n- `sharpening`\n- `tube`\n- `whiteboards`\n\n\n### training_data/wiki/wiki_1/clothing_and_apparel_entries.md\n\n- `backpacks`\n- `bags`\n- `belts`\n- `boots`\n- `buttons`\n- `collars`\n- `dresses`\n- `elbow`\n- `fasteners`\n- `hats`\n- `jackets`\n- `mitten`\n- `mittens`\n- `reaching`\n- `scarves`\n- `shirts`\n- `skirt`\n- `skirts`\n- `sleeve`\n- `slider`\n- `snaps`\n- `straps`\n- `styles`\n- `zippers`\n\n\n### training_data/wiki/wiki_1/collections_and_collecting_entries.md\n\n- `binder`\n- `collected`\n- `copy`\n- `extra`\n- `gathered`\n- `matching`\n- `neat`\n- `organization`\n- `organizing`\n- `page`\n- `papers`\n- `scatter`\n- `shells`\n- `similar`\n- `swapping`\n- `theme`\n- `traded`\n\n\n### training_data/wiki/wiki_1/colors_entries.md\n\n- `blood`\n- `butterflies`\n- `chocolate`\n- `crowns`\n- `darkest`\n- `gold`\n- `ink`\n- `lightest`\n- `pink`\n- `pumpkins`\n- `silver`\n- `spoons`\n- `warn`\n\n\n### training_data/wiki/wiki_1/communication_acts_and_language_entries.md\n\n- `louder`\n- `whispering`\n\n\n### training_data/wiki/wiki_1/community_places_and_services_entries.md\n\n- `bun`\n- `checkups`\n- `firefighters`\n- `neighborhood`\n- `packages`\n- `pharmacies`\n- `stamps`\n\n\n### training_data/wiki/wiki_1/conflict_resolution_and_relationship_repair_entries.md\n\n- `acceptance`\n- `blaming`\n- `caused`\n- `failed`\n- `fault`\n- `fighting`\n- `forgiveness`\n- `forgiving`\n- `refusing`\n- `tension`\n\n\n### training_data/wiki/wiki_1/construction_and_material_transformations_entries.md\n\n- `assemble`\n- `assembling`\n- `bundles`\n- `crumbs`\n- `crushing`\n- `damaged`\n- `fasten`\n- `flattening`\n- `knotting`\n- `lump`\n- `molding`\n- `playdough`\n- `shredding`\n- `untie`\n\n\n### training_data/wiki/wiki_1/containers_and_capacity_entries.md\n\n- `baskets`\n- `cabinets`\n- `desks`\n- `drawers`\n- `dressers`\n- `jars`\n- `keys`\n- `mess`\n- `sorted`\n\n\n### training_data/wiki/wiki_1/cooking_and_food_preparation_entries.md\n\n- `batter`\n- `blended`\n- `carrots`\n- `chopping`\n- `combine`\n- `cookies`\n- `cream`\n- `flavors`\n- `frying`\n- `gently`\n- `herbs`\n- `kneading`\n- `loose`\n- `onions`\n- `orderly`\n- `pasta`\n- `potatoes`\n- `preparing`\n- `salad`\n- `sauce`\n- `seasoning`\n- `simmering`\n- `smoother`\n- `soups`\n- `spices`\n- `stew`\n- `toast`\n- `whisking`\n\n\n### training_data/wiki/wiki_1/daily_routines_and_self_care_entries.md\n\n- `lining`\n- `waking`\n- `weekday`\n\n\n### training_data/wiki/wiki_1/data_charts_and_graphs_entries.md\n\n- `bars`\n- `biggest`\n- `boxes`\n- `glance`\n- `greatest`\n- `lined`\n- `smallest`\n- `surveys`\n- `votes`\n\n\n### training_data/wiki/wiki_1/degrees_of_truth_entries.md\n\n- `bugs`\n- `completely`\n- `confuse`\n- `correcting`\n- `got`\n- `huge`\n- `perfect`\n\n\n### training_data/wiki/wiki_1/directions_and_navigation_entries.md\n\n- `maps`\n\n\n### training_data/wiki/wiki_1/emotions_entries.md\n\n- `achievements`\n- `amazement`\n- `awkward`\n- `brave`\n- `bravery`\n- `calmly`\n- `cancelled`\n- `capable`\n- `cruelty`\n- `dependable`\n- `despite`\n- `difficulty`\n- `disgust`\n- `eager`\n- `embarrassing`\n- `foolish`\n- `frustrating`\n- `fullness`\n- `giver`\n- `growling`\n- `grumpy`\n- `harshly`\n- `hate`\n- `honesty`\n- `hoped`\n- `interesting`\n- `prize`\n- `rebuild`\n- `receiver`\n- `relieve`\n- `restless`\n- `reward`\n- `satisfaction`\n- `satisfied`\n- `satisfies`\n- `shaky`\n- `startling`\n- `steadier`\n- `stomach`\n- `thankfulness`\n- `tripping`\n- `unease`\n- `uneasy`\n- `unexpected`\n- `unhappiness`\n- `unlooked`\n- `vital`\n- `wanting`\n- `wishing`\n\n\n### training_data/wiki/wiki_1/environmental_care_and_stewardship_entries.md\n\n- `affect`\n- `alive`\n- `beaches`\n- `bins`\n- `bottles`\n- `chemicals`\n- `cleaner`\n- `conserving`\n- `ecosystems`\n- `harm`\n- `harmful`\n- `healthier`\n- `parks`\n- `protecting`\n- `recyclables`\n- `recycled`\n- `reduce`\n- `scare`\n- `streets`\n- `survive`\n- `taps`\n- `unplugging`\n- `waste`\n- `wasted`\n- `wrappers`\n- `yards`\n\n\n### training_data/wiki/wiki_1/evidence_and_justification_entries.md\n\n- `broke`\n- `claim`\n- `explained`\n- `grew`\n- `invites`\n- `listener`\n- `noticed`\n\n\n### training_data/wiki/wiki_1/exceptions_and_qualifications_entries.md\n\n- `exception`\n- `lazy`\n- `narrows`\n- `penguin`\n- `weaker`\n\n\n### training_data/wiki/wiki_1/food_groups_and_nutrition_entries.md\n\n- `amounts`\n- `candy`\n- `oats`\n- `vitamins`\n- `yogurt`\n\n\n### training_data/wiki/wiki_1/foods_and_drinks_entries.md\n\n- `boiled`\n- `buttery`\n- `cupcakes`\n- `film`\n- `fried`\n- `icing`\n- `kernels`\n- `milkshakes`\n- `noodles`\n- `pop`\n- `toasted`\n- `vanilla`\n\n\n### training_data/wiki/wiki_1/foods_fruits_entries.md\n\n- `almond`\n- `almonds`\n- `bananas`\n- `beans`\n- `blueberries`\n- `cakes`\n- `cherries`\n- `cherry`\n- `chestnut`\n- `chestnuts`\n- `chunks`\n- `citrus`\n- `crisp`\n- `days`\n- `dessert`\n- `desserts`\n- `earthy`\n- `especially`\n- `flavor`\n- `gather`\n- `grainy`\n- `handful`\n- `insides`\n- `lemon`\n- `lemons`\n- `lime`\n- `limes`\n- `mango`\n- `melon`\n- `melons`\n- `muffins`\n- `oranges`\n- `pancakes`\n- `peach`\n- `peaches`\n- `peanut`\n- `peanuts`\n- `pear`\n- `pears`\n- `pies`\n- `pineapple`\n- `pineapples`\n- `pit`\n- `plantain`\n- `plantains`\n- `plum`\n- `plums`\n- `popular`\n- `purple`\n- `raisins`\n- `rind`\n- `rinds`\n- `ripe`\n- `roast`\n- `roasted`\n- `salsa`\n- `segments`\n- `softer`\n- `spiky`\n- `squeeze`\n- `starchy`\n- `stems`\n- `stiff`\n- `strawberries`\n- `tart`\n- `tea`\n- `underground`\n- `walnut`\n- `walnuts`\n- `watermelons`\n\n\n### training_data/wiki/wiki_1/foods_vegetables_entries.md\n\n- `bulbs`\n- `curly`\n- `kale`\n- `leafy`\n- `mash`\n- `mashed`\n- `parsnip`\n- `parsnips`\n- `peas`\n- `salads`\n- `stews`\n- `tomatoes`\n- `underneath`\n\n\n### training_data/wiki/wiki_1/fractions_and_sharing_quantities_entries.md\n\n- `chosen`\n- `halves`\n- `pizza`\n- `teams`\n- `thirds`\n\n\n### training_data/wiki/wiki_1/friends_and_peer_interactions_entries.md\n\n- `apologizing`\n- `arguing`\n- `cheer`\n- `cooperate`\n\n\n### training_data/wiki/wiki_1/future_planning_and_goals_entries.md\n\n- `artist`\n- `closer`\n- `effort`\n- `hopes`\n- `ignore`\n- `pilot`\n- `practicing`\n- `wish`\n\n\n### training_data/wiki/wiki_1/garden_and_planting_basics_entries.md\n\n- `beds`\n- `crop`\n- `lightly`\n- `sprouts`\n- `ugly`\n- `watering`\n- `windowsills`\n- `worked`\n\n\n### training_data/wiki/wiki_1/greetings_and_social_salutations_entries.md\n\n- `arrives`\n- `casual`\n- `cheerful`\n- `guest`\n\n\n### training_data/wiki/wiki_1/group_roles_and_participation_entries.md\n\n- `captains`\n- `clap`\n- `leaders`\n- `listens`\n- `opponent`\n- `performers`\n- `steadily`\n- `volunteering`\n- `watches`\n- `willingness`\n\n\n### training_data/wiki/wiki_1/growth_and_life_stages_human_entries.md\n\n- `achievement`\n- `adulthood`\n- `elderly`\n- `gaining`\n- `lifetime`\n- `milestone`\n- `milestones`\n- `reached`\n- `teenage`\n- `teenagers`\n- `toddlers`\n- `ups`\n\n\n### training_data/wiki/wiki_1/health_and_wellness_entries.md\n\n- `allergic`\n- `bleed`\n- `bother`\n- `bothered`\n- `bothers`\n- `bruises`\n- `bumpy`\n- `coughs`\n- `curl`\n- `heals`\n- `irritates`\n- `pill`\n- `rashes`\n- `scrape`\n\n\n### training_data/wiki/wiki_1/hobbies_and_interests_entries.md\n\n- `assigned`\n- `comics`\n- `dislikes`\n- `enjoying`\n- `enjoys`\n\n\n### training_data/wiki/wiki_1/holidays_and_celebrations_entries.md\n\n- `candles`\n- `celebrate`\n- `decorations`\n- `gathering`\n- `gatherings`\n- `joy`\n- `meaningful`\n- `moments`\n- `notice`\n- `parties`\n- `presents`\n- `songs`\n- `traditions`\n- `usual`\n- `wick`\n\n\n### training_data/wiki/wiki_1/home_objects_entries_part1.md\n\n- `bookshelves`\n- `brooms`\n- `buckets`\n- `cabinet`\n- `cheap`\n- `footboards`\n- `headboards`\n- `king`\n- `labeled`\n- `queen`\n- `suction`\n- `taped`\n- `tile`\n- `twin`\n- `vacuum`\n\n\n### training_data/wiki/wiki_1/home_objects_entries_part2.md\n\n- `cupboards`\n- `fixture`\n- `hinges`\n- `locks`\n\n\n### training_data/wiki/wiki_1/home_objects_entries_part3.md\n\n- `brighten`\n\n\n### training_data/wiki/wiki_1/home_rooms_entries.md\n\n- `bathrooms`\n- `bedrooms`\n- `chairs`\n- `dining`\n- `guests`\n- `kitchens`\n- `relax`\n- `sofa`\n- `toilet`\n- `welcomed`\n\n\n### training_data/wiki/wiki_1/humor_and_figurative_language_entries.md\n\n- `alike`\n- `clues`\n- `extreme`\n- `funny`\n- `gentle`\n- `heard`\n- `jokes`\n- `laugh`\n- `plain`\n- `playful`\n- `puns`\n- `riddles`\n- `serious`\n- `silly`\n- `teasing`\n- `told`\n- `trick`\n- `tricky`\n\n\n### training_data/wiki/wiki_1/imagination_and_pretend_play_entries.md\n\n- `adventures`\n- `cape`\n- `challenging`\n- `costumes`\n- `exciting`\n- `forests`\n- `great`\n- `imagine`\n- `imagined`\n- `invented`\n- `planets`\n- `powers`\n- `superheroes`\n- `unusual`\n- `wand`\n\n\n### training_data/wiki/wiki_1/inclusion_bullying_and_kindness_entries.md\n\n- `bystanders`\n- `excluding`\n- `honorable`\n- `meanness`\n- `suffering`\n- `uncaring`\n- `upstanders`\n\n\n### training_data/wiki/wiki_1/intentions_and_plans_in_action_entries.md\n\n- `suggest`\n- `upcoming`\n\n\n### training_data/wiki/wiki_1/learning_memory_and_metacognition_entries.md\n\n- `attempt`\n- `confused`\n- `figuring`\n- `gain`\n- `honest`\n- `mastered`\n- `remembered`\n- `reminders`\n- `satisfying`\n\n\n### training_data/wiki/wiki_1/location_and_direction_in_action_entries.md\n\n- `bench`\n\n\n### training_data/wiki/wiki_1/logic_entries.md\n\n- `absence`\n- `achieve`\n- `advantage`\n- `balls`\n- `chaos`\n- `city`\n- `clash`\n- `connection`\n- `contradiction`\n- `contradictions`\n- `country`\n- `damage`\n- `decides`\n- `difficult`\n- `disorder`\n- `doubt`\n- `driver`\n- `dropping`\n- `effects`\n- `expected`\n- `fails`\n- `fairer`\n- `falsehood`\n- `falsehoods`\n- `fell`\n- `firmer`\n- `freezes`\n- `impossibility`\n- `included`\n- `itself`\n- `laws`\n- `leads`\n- `locked`\n- `looked`\n- `memories`\n- `messy`\n- `motivation`\n- `option`\n- `options`\n- `owning`\n- `possibility`\n- `possibly`\n- `rains`\n- `reaction`\n- `reactions`\n- `safer`\n- `separating`\n- `settled`\n- `solutions`\n- `struggle`\n- `testing`\n- `towns`\n- `traveler`\n- `unfair`\n- `unhelpful`\n- `unkind`\n- `wondering`\n- `zero`\n\n\n### training_data/wiki/wiki_1/lost_and_found_misplacing_objects_entries.md\n\n- `gotten`\n\n\n### training_data/wiki/wiki_1/machines_and_simple_mechanisms_entries.md\n\n- `axe`\n- `axles`\n- `barrels`\n- `carts`\n- `clocks`\n- `cranes`\n- `gears`\n- `pulleys`\n- `ramps`\n- `rod`\n- `stairs`\n- `systems`\n- `wedge`\n- `wells`\n- `wrapped`\n\n\n### training_data/wiki/wiki_1/manners_politeness_and_social_etiquette_entries.md\n\n- `answering`\n- `appreciated`\n- `bumping`\n- `chance`\n- `fixing`\n- `gladly`\n- `gratitude`\n- `harshness`\n- `hurting`\n- `ignoring`\n- `interrupting`\n- `interruptions`\n- `kinder`\n- `listen`\n- `passing`\n- `permission`\n- `prevent`\n- `raising`\n- `receiving`\n- `reply`\n- `request`\n- `respected`\n- `rude`\n- `rudeness`\n- `sharply`\n- `shouting`\n- `smoothly`\n- `speak`\n- `trouble`\n\n\n### training_data/wiki/wiki_1/material_composition_entries.md\n\n- `curtains`\n- `fabrics`\n- `folded`\n- `joined`\n- `metals`\n- `sheets`\n- `springy`\n- `tables`\n- `tires`\n\n\n### training_data/wiki/wiki_1/mathematical_concepts_entries.md\n\n- `drawn`\n- `rectangle`\n- `rectangles`\n- `rooftops`\n- `tiles`\n- `triangles`\n\n\n### training_data/wiki/wiki_1/measurement_and_comparison_entries.md\n\n- `runner`\n- `sameness`\n- `thermometer`\n- `weigh`\n\n\n### training_data/wiki/wiki_1/money_trade_and_shopping_entries.md\n\n- `asked`\n- `bill`\n- `bills`\n- `bought`\n- `cents`\n- `chooses`\n- `coins`\n- `costs`\n- `countries`\n- `customer`\n- `customers`\n- `dimes`\n- `dollars`\n- `earned`\n- `finishes`\n- `market`\n- `marketplace`\n- `nickels`\n- `outdoors`\n- `owned`\n- `paid`\n- `paying`\n- `payment`\n- `payments`\n- `pays`\n- `pennies`\n- `prices`\n- `purchase`\n- `quarters`\n- `receipt`\n- `receipts`\n- `sale`\n- `seller`\n- `sellers`\n- `selling`\n- `sells`\n- `shopkeeper`\n- `shopkeepers`\n- `shops`\n- `spent`\n- `ten`\n- `workers`\n\n\n### training_data/wiki/wiki_1/movement_and_physical_action_entries.md\n\n- `backs`\n- `dancing`\n- `dropped`\n- `lively`\n- `patterned`\n- `stretching`\n\n\n### training_data/wiki/wiki_1/musical_instruments_entries.md\n\n- `beat`\n- `beaters`\n- `beginners`\n- `blowing`\n- `blown`\n- `bow`\n- `cymbals`\n- `drums`\n- `guitars`\n- `performance`\n- `pianos`\n- `pitches`\n- `plucking`\n- `rhythm`\n- `shaken`\n- `shakers`\n- `shaking`\n- `strings`\n- `struck`\n- `strumming`\n- `timing`\n- `trumpets`\n- `valves`\n- `vibrate`\n- `vibrates`\n- `violins`\n\n\n### training_data/wiki/wiki_1/natural_life_cycles_and_processes_entries.md\n\n- `differences`\n- `hunted`\n- `lay`\n- `laying`\n- `migration`\n- `period`\n- `populations`\n- `predator`\n- `predators`\n- `regular`\n- `seas`\n- `south`\n- `times`\n- `weeks`\n\n\n### training_data/wiki/wiki_1/numbers_beyond_10_and_large_number_talk_entries.md\n\n- `eighteen`\n- `eighty`\n- `estimating`\n- `fifteen`\n- `forty`\n- `fourteen`\n- `million`\n- `nineteen`\n- `ninety`\n- `seventeen`\n- `seventy`\n- `sixteen`\n- `sixty`\n- `tens`\n- `thirty`\n\n\n### training_data/wiki/wiki_1/online_safety_and_privacy_entries.md\n\n- `account`\n- `code`\n- `comments`\n- `contact`\n- `internet`\n- `passwords`\n- `peace`\n- `reporting`\n- `seem`\n- `strangers`\n- `whom`\n\n\n### training_data/wiki/wiki_1/opinions_persuasion_and_simple_debate_entries.md\n\n- `agreeing`\n- `convinced`\n- `convincing`\n- `disagreeing`\n- `politely`\n- `proven`\n\n\n### training_data/wiki/wiki_1/ownership_and_sharing_entries.md\n\n- `borrowed`\n- `grabbing`\n- `returned`\n- `returning`\n\n\n### training_data/wiki/wiki_1/people_roles_entries.md\n\n- `bodies`\n- `boyfriend`\n- `boyfriends`\n- `boys`\n- `enemies`\n- `enemy`\n- `fathers`\n- `female`\n- `fight`\n- `girl`\n- `girlfriend`\n- `girlfriends`\n- `girls`\n- `guidance`\n- `man`\n- `married`\n- `mothers`\n- `partners`\n- `relatives`\n- `romantic`\n- `spouse`\n- `woman`\n\n\n### training_data/wiki/wiki_1/personal_identity_and_self_description_entries.md\n\n- `apartment`\n- `born`\n- `introductions`\n- `talks`\n- `tokyo`\n- `visiting`\n\n\n### training_data/wiki/wiki_1/perspective_taking_and_theory_of_mind_entries.md\n\n- `acted`\n- `ignored`\n- `misses`\n- `seemed`\n\n\n### training_data/wiki/wiki_1/places_and_landforms_entries.md\n\n- `ago`\n- `apartments`\n- `benches`\n- `border`\n- `borders`\n- `buses`\n- `clearing`\n- `cliffs`\n- `courtyard`\n- `courtyards`\n- `deserts`\n- `docks`\n- `farmhouses`\n- `few`\n- `formed`\n- `frogs`\n- `gentler`\n- `island`\n- `islands`\n- `marketplaces`\n- `orchards`\n- `passage`\n- `peak`\n- `playgrounds`\n- `reeds`\n- `rougher`\n- `ruin`\n- `ruins`\n- `sold`\n- `streams`\n- `swamp`\n- `swamps`\n- `textures`\n- `tunnel`\n- `turtles`\n- `unload`\n- `valleys`\n- `village`\n- `villages`\n- `wagons`\n- `warehouses`\n- `weights`\n- `wildflowers`\n\n\n### training_data/wiki/wiki_1/plants_and_nature_entries.md\n\n- `acorns`\n- `beautiful`\n- `cap`\n- `cones`\n- `cornfields`\n- `daisies`\n- `damp`\n- `dead`\n- `fungus`\n- `gardens`\n- `jungles`\n- `lawn`\n- `mushroom`\n- `mushrooms`\n- `mycelium`\n- `needles`\n- `oaks`\n- `peels`\n- `petals`\n- `pines`\n- `poisonous`\n- `pretty`\n- `rays`\n- `roses`\n- `sap`\n- `squirrels`\n- `storybooks`\n- `strips`\n- `sunflowers`\n- `syrup`\n- `thorns`\n- `toadstool`\n- `toadstools`\n- `visit`\n- `woods`\n- `woody`\n\n\n### training_data/wiki/wiki_1/play_games_and_sports_entries.md\n\n- `challenge`\n- `competition`\n- `contest`\n- `disappointing`\n- `played`\n- `player`\n- `pretending`\n- `skipping`\n- `spoil`\n- `teamwork`\n\n\n### training_data/wiki/wiki_1/praise_criticism_and_feedback_entries.md\n\n- `blame`\n- `coaches`\n- `complaint`\n- `courage`\n- `discourage`\n- `encouragement`\n- `gestures`\n- `improvement`\n- `notices`\n- `pleased`\n- `teammates`\n- `weakness`\n\n\n### training_data/wiki/wiki_1/professions_entries.md\n\n- `advice`\n- `axes`\n- `bakers`\n- `barns`\n- `builders`\n- `butcher`\n- `butchers`\n- `carpenters`\n- `clinics`\n- `crime`\n- `discover`\n- `doctors`\n- `drivers`\n- `fisher`\n- `fishers`\n- `fishing`\n- `flock`\n- `gardener`\n- `gardeners`\n- `heated`\n- `hospitals`\n- `ill`\n- `indoors`\n- `librarian`\n- `librarians`\n- `looms`\n- `medical`\n- `nets`\n- `nurses`\n- `nursing`\n- `officers`\n- `painter`\n- `painters`\n- `patients`\n- `potter`\n- `potters`\n- `practices`\n- `prepares`\n- `profession`\n- `readers`\n- `repairs`\n- `rods`\n- `ropes`\n- `rugs`\n- `sailors`\n- `saws`\n- `scientist`\n- `scientists`\n- `sew`\n- `sewing`\n- `shepherd`\n- `shepherds`\n- `steer`\n- `tailor`\n- `tailors`\n- `threads`\n- `treatment`\n- `watching`\n- `weaver`\n- `weavers`\n- `weaving`\n- `weeds`\n- `woodcutter`\n- `woodcutters`\n- `wooden`\n\n\n### training_data/wiki/wiki_1/safety_rules_and_emergency_awareness_entries.md\n\n- `calling`\n- `careless`\n- `crash`\n- `helmets`\n- `injury`\n- `protective`\n- `scooter`\n- `seatbelts`\n- `skates`\n- `watchful`\n\n\n### training_data/wiki/wiki_1/safety_signs_and_symbols_entries.md\n\n- `alert`\n- `arriving`\n- `arrows`\n- `bandages`\n- `bin`\n- `cleaners`\n- `crossings`\n- `electric`\n- `forming`\n- `kit`\n- `theaters`\n- `walkers`\n- `zone`\n\n\n### training_data/wiki/wiki_1/school_life_and_learning_entries.md\n\n- `caps`\n- `charge`\n- `colored`\n- `lunchtime`\n- `magazines`\n- `meeting`\n- `notebooks`\n- `publication`\n- `spine`\n- `tops`\n\n\n### training_data/wiki/wiki_1/seasonal_activities_entries.md\n\n- `cooler`\n- `figures`\n- `sleds`\n- `warmer`\n\n\n### training_data/wiki/wiki_1/secrets_surprises_and_keeping_promises_entries.md\n\n- `celebrated`\n- `forgetting`\n- `gave`\n- `hooking`\n- `prepared`\n- `remembering`\n- `trapped`\n\n\n### training_data/wiki/wiki_1/sensory_experiences_entries.md\n\n- `barking`\n- `clings`\n- `crashing`\n- `slamming`\n\n\n### training_data/wiki/wiki_1/shadow_and_light_phenomena_entries.md\n\n- `background`\n- `blocked`\n- `bouncing`\n- `coals`\n- `depending`\n- `glowing`\n- `image`\n- `mirrors`\n- `reflections`\n- `shining`\n- `silhouettes`\n- `squint`\n\n\n### training_data/wiki/wiki_1/sibling_relationships_and_dynamics_entries.md\n\n- `bossed`\n- `closeness`\n- `grabs`\n- `pushy`\n- `reported`\n- `siblings`\n- `suggesting`\n\n\n### training_data/wiki/wiki_1/simple_physics_energy_and_power_entries.md\n\n- `batteries`\n- `chargers`\n- `fires`\n- `gas`\n- `gasoline`\n- `lamps`\n- `outlet`\n- `panels`\n- `plugs`\n- `schools`\n- `stoves`\n- `wires`\n\n\n### training_data/wiki/wiki_1/sleep_and_rest_entries.md\n\n- `comfortably`\n- `couch`\n- `lasting`\n- `lullabies`\n- `naps`\n- `nightmares`\n- `pillows`\n- `pleasant`\n- `recover`\n- `scary`\n- `sickness`\n- `song`\n- `strange`\n- `sung`\n- `unsettled`\n- `upsetting`\n\n\n### training_data/wiki/wiki_1/smells_and_tastes_entries.md\n\n- `bland`\n- `boring`\n- `enjoyment`\n- `greens`\n- `informal`\n- `medicines`\n- `newly`\n- `pleasing`\n- `rotten`\n- `sauces`\n- `tasting`\n\n\n### training_data/wiki/wiki_1/social_emotional_learning_competencies_entries.md\n\n- `aware`\n- `calmer`\n- `controlling`\n- `kindly`\n- `noticing`\n- `pause`\n- `responding`\n- `socially`\n- `stopping`\n- `tempted`\n- `thoughtful`\n\n\n### training_data/wiki/wiki_1/space_entries.md\n\n- `arrive`\n- `atop`\n- `basement`\n- `lean`\n- `slanted`\n- `surrounded`\n- `towards`\n\n\n### training_data/wiki/wiki_1/states_of_being_and_condition_entries.md\n\n- `shut`\n- `unpleasant`\n\n\n### training_data/wiki/wiki_1/story_roles_and_plot_elements_entries.md\n\n- `comic`\n- `determined`\n- `fables`\n- `heroes`\n- `worse`\n\n\n### training_data/wiki/wiki_1/storytelling_and_narrative_structure_entries.md\n\n- `describes`\n- `listeners`\n- `storyteller`\n- `tale`\n\n\n### training_data/wiki/wiki_1/technology_and_digital_media_entries.md\n\n- `apps`\n- `camera`\n- `captures`\n- `computers`\n- `keyboards`\n- `news`\n- `phones`\n- `photos`\n- `printed`\n- `program`\n- `sent`\n- `shown`\n- `spoken`\n- `swiping`\n- `tablets`\n- `tapping`\n- `tvs`\n- `usernames`\n- `videos`\n- `watched`\n- `website`\n\n\n### training_data/wiki/wiki_1/time_entries.md\n\n- `begun`\n- `horizon`\n- `nearest`\n- `rarely`\n- `recent`\n- `uncommon`\n\n\n### training_data/wiki/wiki_1/tools_and_kitchenware_entries.md\n\n- `brushes`\n- `ceramic`\n- `fork`\n- `forks`\n- `hammers`\n- `hooks`\n- `knives`\n- `levers`\n- `pans`\n- `plates`\n- `pointed`\n- `pots`\n- `prongs`\n- `pry`\n- `rounded`\n- `skillet`\n- `skillets`\n- `sloping`\n- `swung`\n\n\n### training_data/wiki/wiki_1/topology_parts_entries.md\n\n- `sips`\n\n\n### training_data/wiki/wiki_1/uncertainty_and_guessing_entries.md\n\n- `cautious`\n- `certainly`\n- `definitely`\n- `guaranteed`\n- `searches`\n- `tentative`\n- `uncertain`\n- `unsure`\n\n\n### training_data/wiki/wiki_1/vehicles_transport_entries.md\n\n- `bicycle`\n- `bicycles`\n- `farther`\n- `helicopter`\n- `motorboats`\n- `planes`\n- `rails`\n- `rides`\n- `rotating`\n- `rudder`\n- `sailboats`\n- `tricycle`\n- `tricycles`\n- `trucks`\n\n\n### training_data/wiki/wiki_1/verbs_entries.md\n\n- `airplanes`\n- `aloud`\n- `amused`\n- `badly`\n- `bats`\n- `brakes`\n- `canvas`\n- `crawling`\n- `crying`\n- `curious`\n- `deal`\n- `deeply`\n- `destroy`\n- `destroyed`\n- `distractions`\n- `eagles`\n- `earning`\n- `enjoy`\n- `eyebrows`\n- `finding`\n- `flap`\n- `flapping`\n- `focused`\n- `frown`\n- `glide`\n- `glides`\n- `gliding`\n- `grab`\n- `hawks`\n- `heating`\n- `helicopters`\n- `hours`\n- `ignores`\n- `knees`\n- `ladders`\n- `laughing`\n- `laughs`\n- `loudly`\n- `needle`\n- `nod`\n- `ruined`\n- `sandcastle`\n- `send`\n- `separated`\n- `shovels`\n- `shrug`\n- `simply`\n- `smile`\n- `soaring`\n- `softness`\n- `stare`\n- `staring`\n- `steers`\n- `swallow`\n- `torn`\n- `towers`\n- `uncomfortable`\n- `uncover`\n- `undo`\n- `unhappy`\n- `weave`\n- `wipe`\n\n\n### training_data/wiki/wiki_1/waiting_and_patience_entries.md\n\n- `answered`\n- `coming`\n- `happening`\n- `organized`\n- `rushing`\n\n\n### training_data/wiki/wiki_1/wants_needs_and_preferences_entries.md\n\n- `enjoyable`\n- `favorites`\n- `harsh`\n- `liked`\n- `liking`\n- `negative`\n- `preferring`\n\n\n### training_data/wiki/wiki_1/weather_and_celestial_entries.md\n\n- `boom`\n- `breeze`\n- `climate`\n- `colours`\n- `floods`\n- `fog`\n- `hour`\n- `jupiter`\n- `kites`\n- `mars`\n- `nights`\n- `planet`\n- `raincoats`\n- `raindrops`\n- `reflect`\n- `rumble`\n- `shoots`\n- `snowmen`\n- `storms`\n- `umbrellas`\n- `venus`\n- `violet`\n\n\n### training_data/wiki/wiki_2/README.md\n\n- `scaffolds`\n\n\n### training_data/wiki/wiki_2/communication_acts_and_language_level2.md\n\n- `assistance`\n- `avoiding`\n- `disappearing`\n- `hebbian`\n- `hints`\n- `realizes`\n- `subcategorization`\n- `suggests`\n- `tried`\n- `unlike`\n\n\n### training_data/wiki/wiki_2/community_places_and_services_level2.md\n\n- `announcement`\n- `assistants`\n- `bakeries`\n- `behave`\n- `checkout`\n- `concentrate`\n- `department`\n- `flashing`\n- `fuss`\n- `labels`\n- `libraries`\n- `menu`\n- `occasions`\n- `overnight`\n- `pastries`\n- `patiently`\n- `procedure`\n- `programs`\n- `remained`\n- `reminding`\n- `rescue`\n- `rescues`\n- `scanning`\n- `scans`\n- `seated`\n- `server`\n- `shoppers`\n- `shots`\n- `sirens`\n- `staff`\n- `surgery`\n- `visitors`\n- `wandering`\n- `welcoming`\n- `worker`\n\n\n### training_data/wiki/wiki_2/conflict_resolution_and_relationship_repair_level2.md\n\n- `apologies`\n- `blames`\n- `bumped`\n- `excuses`\n- `fake`\n- `grudge`\n- `incidentally`\n- `limits`\n- `readiness`\n- `rebuilding`\n- `rebuilds`\n- `weapon`\n- `wrongdoing`\n\n\n### training_data/wiki/wiki_2/emotions_level2.md\n\n- `accomplished`\n- `annoyed`\n- `anticipation`\n- `bothering`\n- `calming`\n- `canceled`\n- `complicated`\n- `counselor`\n- `criticize`\n- `defeat`\n- `droop`\n- `envy`\n- `fluttery`\n- `grateful`\n- `grief`\n- `hearts`\n- `heaviness`\n- `helped`\n- `hopeful`\n- `lasts`\n- `loss`\n- `loved`\n- `petting`\n- `practiced`\n- `realize`\n- `scares`\n- `slowness`\n- `slumped`\n- `stomp`\n- `strengths`\n- `succeeded`\n- `temporary`\n- `theirs`\n- `traceability`\n- `unfairness`\n- `unstick`\n- `worst`\n\n\n### training_data/wiki/wiki_2/evidence_and_justification_level2.md\n\n- `baths`\n- `colloquial`\n- `confidence`\n- `demonstrative`\n- `durian`\n- `expandnow`\n- `figured`\n- `heater`\n- `justified`\n- `misleading`\n- `north`\n- `observation`\n- `opener`\n- `refrigerator`\n- `reliable`\n- `remembers`\n- `rolled`\n- `shook`\n- `smartest`\n- `smiled`\n- `strongest`\n- `syntactic`\n- `thinkers`\n- `twice`\n- `variant`\n\n\n### training_data/wiki/wiki_2/friends_and_peer_interactions_level2.md\n\n- `cruelly`\n- `disagreed`\n- `gesture`\n- `hall`\n- `insult`\n- `interrupt`\n- `invited`\n- `maintenance`\n- `mood`\n- `necessarily`\n- `pie`\n- `playdates`\n- `thanks`\n- `unfairly`\n\n\n### training_data/wiki/wiki_2/health_and_wellness_level2.md\n\n- `allergies`\n- `ate`\n- `bleeding`\n- `bless`\n- `calms`\n- `caregiver`\n- `coughing`\n- `crackers`\n- `crampy`\n- `diarrhea`\n- `digest`\n- `diseases`\n- `dripping`\n- `droplets`\n- `dusty`\n- `flavoring`\n- `gesundheit`\n- `harmless`\n- `headaches`\n- `healing`\n- `isn`\n- `jelly`\n- `lotion`\n- `microscope`\n- `ointment`\n- `overlapping`\n- `painful`\n- `peek`\n- `pepper`\n- `petroleum`\n- `pinch`\n- `popsicles`\n- `pounding`\n- `preventive`\n- `puffy`\n- `reflexes`\n- `rinse`\n- `scab`\n- `scraped`\n- `scrub`\n- `seconds`\n- `shot`\n- `sneezes`\n- `specialized`\n- `squeezing`\n- `stethoscope`\n- `stitches`\n- `stomachaches`\n- `stressed`\n- `swelling`\n- `throats`\n- `tickle`\n- `tickled`\n- `unwell`\n- `vaccine`\n- `won`\n- `yelling`\n\n\n### training_data/wiki/wiki_2/perspective_taking_and_theory_of_mind_level2.md\n\n- `arrived`\n- `believed`\n- `ben`\n- `dad`\n- `daughter`\n- `desire`\n- `emma`\n- `entryrevieweddraftwritten`\n- `grandpa`\n- `his`\n- `imagining`\n- `incomplete`\n- `kid`\n- `knew`\n- `label`\n- `leo`\n- `maya`\n- `mental`\n- `misunderstands`\n- `misunderstood`\n- `mom`\n- `sam`\n- `spoiled`\n- `takeaways`\n\n\n### training_data/wiki/wiki_2/play_games_and_sports_level2.md\n\n- `admitting`\n- `becoming`\n- `bragging`\n- `celebrating`\n- `coordination`\n- `damages`\n- `directing`\n- `disagreements`\n- `discussed`\n- `encourages`\n- `ended`\n- `governed`\n- `impressive`\n- `insulting`\n- `loser`\n- `mocking`\n- `quitting`\n- `replaying`\n- `restart`\n- `rounds`\n- `shortcut`\n- `sportsmanship`\n- `storming`\n- `winner`\n\n\n### training_data/wiki/wiki_2/school_life_and_learning_level2.md\n\n- `arrival`\n- `arrivals`\n- `assemblies`\n- `assembly`\n- `assessments`\n- `attendance`\n- `auditorium`\n- `brains`\n- `breaths`\n- `buddy`\n- `cafeteria`\n- `coping`\n- `cubby`\n- `disagrees`\n- `distract`\n- `earns`\n- `edits`\n- `engaging`\n- `forgets`\n- `honestly`\n- `importance`\n- `mention`\n- `mentioned`\n- `newness`\n- `nicely`\n- `participates`\n- `puzzles`\n- `respectfully`\n- `reviews`\n- `snapshot`\n- `struggles`\n- `struggling`\n- `transitioning`\n- `transitions`\n- `tutoring`\n- `typical`\n- `unpack`\n\n\n### training_data/wiki/wiki_2/storytelling_and_narrative_structure_level2.md\n\n- `closure`\n- `existed`\n- `pacing`\n- `saved`\n- `storytellers`\n- `suddenlys`\n\n\n### training_data/wiki/wiki_2/technology_and_digital_media_level2.md\n\n- `aches`\n- `actors`\n- `agrees`\n- `assignments`\n- `cartoons`\n- `considerations`\n- `downloading`\n- `educational`\n- `footrest`\n- `involving`\n- `minds`\n- `newer`\n- `posture`\n- `purchases`\n- `recordings`\n- `researching`\n- `respects`\n- `schoolwork`\n- `spends`\n- `typing`\n- `updated`\n- `users`\n- `weird`\n\n\n### training_data/wiki/wiki_3/emotions_level3.md\n\n- `achieved`\n- `evaluate`\n\n\n### training_data/wiki/wiki_3/evidence_and_justification_level3.md\n\n- `cohesive`\n- `possibilities`\n- `smiles`\n\n\n### training_data/wiki/wiki_3/perspective_taking_level3.md\n\n- `reminds`\n\n\n### training_data/wiki/wiki_4/emotions_level4.md\n\n- `brake`\n- `challenges`\n- `compass`\n- `crossed`\n- `decrease`\n- `incorporating`\n- `instantly`\n- `mad`\n- `maintaining`\n- `opposites`\n- `overwhelmed`\n- `overwhelming`\n- `purposes`\n- `rate`\n- `react`\n- `secure`\n- `sharper`\n- `stormy`\n- `thrive`\n- `values`\n- `versions`\n\n\n### training_data/wiki/wiki_4/evidence_and_justification_level4.md\n\n- `accurately`\n- `angles`\n- `bolt`\n- `breed`\n- `clue`\n- `conclude`\n- `contain`\n- `detective`\n- `ensures`\n- `excellent`\n- `flight`\n- `footprint`\n- `justifications`\n- `meowing`\n- `mystery`\n- `objective`\n- `orbits`\n- `ourselves`\n- `perfectly`\n- `provided`\n- `providing`\n- `retriever`\n- `ruling`\n- `shatter`\n- `similarly`\n- `smiling`\n- `solves`\n- `trusting`\n\n\n### training_data/wiki/wiki_4/perspective_taking_level4.md\n\n- `baseball`\n- `desires`\n- `east`\n- `expectation`\n- `happily`\n- `imaginations`\n- `inner`\n- `lens`\n- `missed`\n- `observer`\n- `perceived`\n- `spoils`\n- `updating`\n- `views`\n- `worlds`\n- `zoom`\n\n\n### training_data/wiki/wiki_category_backlog.md\n\n- `absolute`\n- `abstractions`\n- `academic`\n- `accepted`\n- `accident`\n- `accuracy`\n- `accurate`\n- `activities`\n- `activity`\n- `acts`\n- `addition`\n- `additional`\n- `address`\n- `addressable`\n- `addressed`\n- `addresses`\n- `adjectives`\n- `adult`\n- `adults`\n- `advance`\n- `adventure`\n- `affirming`\n- `afterward`\n- `aged`\n- `agree`\n- `aid`\n- `alarm`\n- `album`\n- `allowance`\n- `allowances`\n- `almost`\n- `alone`\n- `alongside`\n- `among`\n- `anchoring`\n- `angry`\n- `annoying`\n- `anything`\n- `anywhere`\n- `apologise`\n- `apology`\n- `apparel`\n- `appropriately`\n- `approximately`\n- `argument`\n- `arguments`\n- `arise`\n- `arithmetic`\n- `aroma`\n- `art`\n- `asleep`\n- `aspirational`\n- `aspirations`\n- `assignment`\n- `audience`\n- `auditory`\n- `aunt`\n- `authentic`\n- `authentically`\n- `authenticity`\n- `authority`\n- `autumn`\n- `awareness`\n- `baby`\n- `backing`\n- `bad`\n- `baker`\n- `bands`\n- `bang`\n- `barely`\n- `basics`\n- `battery`\n- `beating`\n- `beats`\n- `bedtime`\n- `behaviour`\n- `behavioural`\n- `behaviours`\n- `believable`\n- `believe`\n- `belonging`\n- `benchmarks`\n- `best`\n- `bikes`\n- `binary`\n- `birthday`\n- `birthdays`\n- `bit`\n- `bitter`\n- `bloom`\n- `boot`\n- `bored`\n- `boredom`\n- `borrow`\n- `borrowing`\n- `bossing`\n- `breakdown`\n- `breakfast`\n- `bridges`\n- `brother`\n- `brothers`\n- `builder`\n- `bully`\n- `bullying`\n- `bump`\n- `burrow`\n- `butter`\n- `buying`\n- `bystander`\n- `calculator`\n- `calendar`\n- `call`\n- `candle`\n- `cannot`\n- `capacity`\n- `captain`\n- `carbohydrate`\n- `card`\n- `cards`\n- `care`\n- `career`\n- `careful`\n- `caring`\n- `carpenter`\n- `carrier`\n- `case`\n- `cashier`\n- `categories`\n- `categorise`\n- `caterpillar`\n- `cats`\n- `causally`\n- `caution`\n- `celebration`\n- `celebrations`\n- `celestial`\n- `central`\n- `certain`\n- `changing`\n- `character`\n- `chart`\n- `charts`\n- `chatgpt`\n- `chemical`\n- `childhood`\n- `children`\n- `choice`\n- `choices`\n- `chop`\n- `chore`\n- `chores`\n- `citizen`\n- `civic`\n- `claims`\n- `clarify`\n- `clarifying`\n- `class`\n- `classification`\n- `classify`\n- `classmates`\n- `climax`\n- `climb`\n- `clock`\n- `closing`\n- `cloudy`\n- `colder`\n- `collage`\n- `collar`\n- `collection`\n- `collections`\n- `colour`\n- `comb`\n- `commonly`\n- `communicate`\n- `communicative`\n- `compare`\n- `comparisons`\n- `compassion`\n- `competence`\n- `competencies`\n- `complaints`\n- `completeness`\n- `complex`\n- `composition`\n- `compost`\n- `conceptideasgemini`\n- `conceptideaslfm`\n- `conceptideasnemotron`\n- `conceptual`\n- `condition`\n- `confusion`\n- `connected`\n- `connecting`\n- `connector`\n- `consensus`\n- `consent`\n- `consequence`\n- `consequences`\n- `conserve`\n- `constant`\n- `constantly`\n- `construction`\n- `constructive`\n- `containers`\n- `contesting`\n- `contexts`\n- `conversation`\n- `conversational`\n- `conversations`\n- `convince`\n- `cooperation`\n- `corpusstatus`\n- `cost`\n- `cotton`\n- `counted`\n- `counting`\n- `cousin`\n- `craft`\n- `crafts`\n- `creative`\n- `creativity`\n- `criticism`\n- `critique`\n- `crosswalk`\n- `crowd`\n- `crush`\n- `cues`\n- `cultural`\n- `curiosity`\n- `cycle`\n- `cycles`\n- `daily`\n- `dairy`\n- `dance`\n- `danger`\n- `data`\n- `debate`\n- `december`\n- `decided`\n- `decomposition`\n- `decorate`\n- `dedicated`\n- `deepseek`\n- `defend`\n- `defined`\n- `degree`\n- `degrees`\n- `delicious`\n- `den`\n- `denim`\n- `describing`\n- `description`\n- `descriptions`\n- `development`\n- `developmental`\n- `devices`\n- `didn`\n- `difference`\n- `differently`\n- `digital`\n- `dime`\n- `dinner`\n- `directed`\n- `directions`\n- `disagree`\n- `disappointed`\n- `disappointment`\n- `discuss`\n- `discussing`\n- `discussion`\n- `dislike`\n- `display`\n- `dissolve`\n- `distance`\n- `divide`\n- `dizzy`\n- `doctor`\n- `dogs`\n- `dollar`\n- `dream`\n- `dreams`\n- `dress`\n- `dressing`\n- `drum`\n- `duties`\n- `dynamics`\n- `earliest`\n- `earn`\n- `editorial`\n- `education`\n- `effective`\n- `elder`\n- `electricity`\n- `elementary`\n- `elements`\n- `eleven`\n- `email`\n- `emails`\n- `embarrassed`\n- `embedded`\n- `emergencies`\n- `emergency`\n- `emerges`\n- `emotion`\n- `emotional`\n- `emotionally`\n- `empathy`\n- `emphasise`\n- `enabling`\n- `encounter`\n- `encourage`\n- `encouraged`\n- `engage`\n- `environment`\n- `environmental`\n- `environments`\n- `equal`\n- `equipment`\n- `erase`\n- `eraser`\n- `errands`\n- `essential`\n- `estimate`\n- `ethics`\n- `etiquette`\n- `even`\n- `evenly`\n- `events`\n- `everyday`\n- `everywhere`\n- `exaggerate`\n- `exaggeration`\n- `exceed`\n- `except`\n- `exceptions`\n- `excited`\n- `excitement`\n- `exclude`\n- `excluded`\n- `exclusion`\n- `excuse`\n- `exercise`\n- `exit`\n- `expanded`\n- `expect`\n- `expects`\n- `experience`\n- `experiences`\n- `explanations`\n- `explore`\n- `express`\n- `expressing`\n- `expression`\n- `extend`\n- `extended`\n- `extending`\n- `facing`\n- `facts`\n- `factual`\n- `fairness`\n- `false`\n- `farmer`\n- `fat`\n- `father`\n- `favorite`\n- `favourite`\n- `favourites`\n- `feature`\n- `feed`\n- `feelings`\n- `festival`\n- `fewer`\n- `fibre`\n- `fifty`\n- `fights`\n- `figurative`\n- `figure`\n- `films`\n- `firefighter`\n- `flag`\n- `flashlight`\n- `flatten`\n- `flavour`\n- `flute`\n- `folder`\n- `follower`\n- `foods`\n- `forces`\n- `forecast`\n- `forget`\n- `forgot`\n- `formal`\n- `formatting`\n- `fraction`\n- `fractions`\n- `frameworks`\n- `frequent`\n- `friendships`\n- `fruits`\n- `frustrated`\n- `fry`\n- `fuel`\n- `fun`\n- `function`\n- `functioning`\n- `functions`\n- `fundamental`\n- `further`\n- `future`\n- `garage`\n- `gardening`\n- `gear`\n- `gemma`\n- `generalise`\n- `generate`\n- `generates`\n- `generating`\n- `genuine`\n- `germinate`\n- `germs`\n- `gift`\n- `giving`\n- `glasses`\n- `gloves`\n- `glue`\n- `gone`\n- `goodbye`\n- `gpt`\n- `gracefully`\n- `gradation`\n- `grades`\n- `grammar`\n- `grandparent`\n- `graph`\n- `graphs`\n- `greetings`\n- `grok`\n- `grooming`\n- `grouping`\n- `guardian`\n- `guessing`\n- `guilty`\n- `guitar`\n- `gustatory`\n- `guy`\n- `habitats`\n- `habits`\n- `half`\n- `hallmarks`\n- `hallway`\n- `harvest`\n- `hatch`\n- `hatching`\n- `healthy`\n- `heart`\n- `hedges`\n- `hedging`\n- `heights`\n- `hello`\n- `helmet`\n- `helper`\n- `helpers`\n- `hero`\n- `hibernation`\n- `highlight`\n- `hobbies`\n- `hobby`\n- `holiday`\n- `holidays`\n- `hope`\n- `hotter`\n- `household`\n- `humor`\n- `hundred`\n- `hundreds`\n- `hunger`\n- `hurry`\n- `hurt`\n- `hurts`\n- `husband`\n- `hutch`\n- `hygiene`\n- `identical`\n- `identity`\n- `idiom`\n- `illness`\n- `imaginative`\n- `imperative`\n- `impossible`\n- `improve`\n- `impulse`\n- `include`\n- `includes`\n- `increasing`\n- `increasingly`\n- `independence`\n- `independently`\n- `inference`\n- `inferential`\n- `ingredient`\n- `ingredients`\n- `injuries`\n- `input`\n- `instance`\n- `instructions`\n- `instrument`\n- `instruments`\n- `integrates`\n- `intensity`\n- `intent`\n- `intention`\n- `intentions`\n- `interact`\n- `interactions`\n- `interest`\n- `interests`\n- `internal`\n- `interrupted`\n- `introduces`\n- `invent`\n- `involve`\n- `involved`\n- `itchy`\n- `jacket`\n- `january`\n- `jealous`\n- `jealousy`\n- `job`\n- `jobs`\n- `joke`\n- `journey`\n- `judge`\n- `junk`\n- `kennel`\n- `kick`\n- `kidding`\n- `kids`\n- `kinetic`\n- `kinship`\n- `kitchenware`\n- `knead`\n- `known`\n- `lacks`\n- `landforms`\n- `law`\n- `layouts`\n- `lead`\n- `leader`\n- `leash`\n- `least`\n- `leaving`\n- `length`\n- `lessons`\n- `leverage`\n- `lfm`\n- `lie`\n- `lighter`\n- `likes`\n- `linked`\n- `liquidai`\n- `literacy`\n- `litter`\n- `little`\n- `local`\n- `location`\n- `locations`\n- `loneliness`\n- `lonely`\n- `lost`\n- `lot`\n- `loyalties`\n- `lullaby`\n- `lunch`\n- `machines`\n- `magic`\n- `mail`\n- `makers`\n- `mammals`\n- `manage`\n- `management`\n- `managing`\n- `marker`\n- `markers`\n- `math`\n- `matter`\n- `maybe`\n- `mealtime`\n- `meant`\n- `measure`\n- `measuring`\n- `mechanics`\n- `mechanisms`\n- `media`\n- `meet`\n- `melody`\n- `melted`\n- `melting`\n- `member`\n- `members`\n- `messages`\n- `metamorphosis`\n- `micro`\n- `might`\n- `mine`\n- `mineral`\n- `minor`\n- `minutes`\n- `mirror`\n- `misplace`\n- `misplacing`\n- `mistake`\n- `mistral`\n- `misunderstand`\n- `mode`\n- `models`\n- `modern`\n- `modifiers`\n- `mold`\n- `moment`\n- `monday`\n- `month`\n- `moral`\n- `mother`\n- `music`\n- `musical`\n- `names`\n- `naming`\n- `nap`\n- `narrate`\n- `narratives`\n- `navigation`\n- `necessary`\n- `negotiate`\n- `negotiating`\n- `negotiation`\n- `negotiations`\n- `neighbour`\n- `neighbourhood`\n- `neither`\n- `nervous`\n- `nice`\n- `nickel`\n- `nightmare`\n- `noisy`\n- `nonliteral`\n- `nor`\n- `norms`\n- `nuance`\n- `nuanced`\n- `nurse`\n- `nutrition`\n- `nutritional`\n- `nylon`\n- `observable`\n- `observations`\n- `occupies`\n- `occurred`\n- `odour`\n- `officer`\n- `older`\n- `olds`\n- `olfactory`\n- `oops`\n- `opaque`\n- `openers`\n- `operate`\n- `operation`\n- `operators`\n- `opinions`\n- `ordinary`\n- `organisation`\n- `organise`\n- `oriented`\n- `orphan`\n- `overflow`\n- `pack`\n- `paint`\n- `pair`\n- `pajamas`\n- `parade`\n- `parsed`\n- `partial`\n- `partially`\n- `participate`\n- `participation`\n- `partner`\n- `party`\n- `passenger`\n- `password`\n- `patience`\n- `patient`\n- `pay`\n- `pedestrian`\n- `peers`\n- `penny`\n- `percussion`\n- `perhaps`\n- `personal`\n- `perspective`\n- `persuade`\n- `persuasion`\n- `pets`\n- `phenomena`\n- `phrase`\n- `phrasing`\n- `piano`\n- `picnic`\n- `picnics`\n- `pictograph`\n- `picture`\n- `pillow`\n- `pinky`\n- `plans`\n- `planting`\n- `playtime`\n- `please`\n- `plug`\n- `poison`\n- `politeness`\n- `pollination`\n- `pollution`\n- `polyester`\n- `positional`\n- `practice`\n- `practise`\n- `predict`\n- `predictable`\n- `preference`\n- `preferences`\n- `preparation`\n- `primitive`\n- `privacy`\n- `private`\n- `problems`\n- `processes`\n- `produced`\n- `productively`\n- `progress`\n- `projects`\n- `promise`\n- `promised`\n- `promises`\n- `prompt`\n- `proof`\n- `properties`\n- `property`\n- `protein`\n- `proud`\n- `public`\n- `pulley`\n- `pun`\n- `puzzle`\n- `qualification`\n- `qualifications`\n- `qualify`\n- `quantities`\n- `quarter`\n- `queues`\n- `quite`\n- `qwen`\n- `railway`\n- `rainbow`\n- `rainbows`\n- `raining`\n- `rainy`\n- `raise`\n- `ramp`\n- `rank`\n- `receive`\n- `recipe`\n- `recognising`\n- `recorder`\n- `recount`\n- `recycle`\n- `recycling`\n- `reference`\n- `reflection`\n- `reflective`\n- `refusal`\n- `register`\n- `registers`\n- `regularly`\n- `regulation`\n- `regulatory`\n- `relationship`\n- `relationships`\n- `relevance`\n- `relevant`\n- `relief`\n- `relieved`\n- `remaining`\n- `remember`\n- `remote`\n- `repairing`\n- `representing`\n- `reptiles`\n- `requests`\n- `requires`\n- `requiring`\n- `resistance`\n- `respect`\n- `respectful`\n- `respond`\n- `responsibilities`\n- `responsibility`\n- `responsible`\n- `retell`\n- `retrace`\n- `return`\n- `reuse`\n- `revolves`\n- `rhythms`\n- `richest`\n- `riddle`\n- `right`\n- `rights`\n- `rigid`\n- `roar`\n- `robotically`\n- `roughly`\n- `rounding`\n- `route`\n- `routine`\n- `routines`\n- `ruler`\n- `safely`\n- `safest`\n- `said`\n- `sailor`\n- `sakana`\n- `salient`\n- `salty`\n- `salutations`\n- `sarcasm`\n- `save`\n- `saving`\n- `scared`\n- `schedule`\n- `schedules`\n- `scheduling`\n- `science`\n- `scissors`\n- `scratchy`\n- `screens`\n- `search`\n- `seasonal`\n- `seatbelt`\n- `secret`\n- `secrets`\n- `seeking`\n- `sel`\n- `sensations`\n- `sequenced`\n- `sequences`\n- `sequencing`\n- `series`\n- `services`\n- `settings`\n- `shall`\n- `share`\n- `shared`\n- `shares`\n- `sharpener`\n- `she`\n- `shiver`\n- `shoes`\n- `shout`\n- `shower`\n- `shred`\n- `sibling`\n- `sick`\n- `sidekick`\n- `sign`\n- `signs`\n- `silent`\n- `silhouette`\n- `simmer`\n- `sing`\n- `singing`\n- `single`\n- `sister`\n- `sisters`\n- `site`\n- `situations`\n- `skills`\n- `sledging`\n- `slower`\n- `snacks`\n- `snap`\n- `snowy`\n- `socks`\n- `solar`\n- `someday`\n- `sometimes`\n- `somewhere`\n- `soon`\n- `sorry`\n- `sort`\n- `sota`\n- `sour`\n- `spaces`\n- `spanning`\n- `special`\n- `species`\n- `spend`\n- `spicy`\n- `sports`\n- `spring`\n- `sprout`\n- `standards`\n- `stapler`\n- `started`\n- `starting`\n- `statements`\n- `static`\n- `stewardship`\n- `sticker`\n- `stickers`\n- `stinky`\n- `stir`\n- `stranger`\n- `strategies`\n- `structured`\n- `studies`\n- `sub`\n- `subjects`\n- `subtraction`\n- `success`\n- `such`\n- `sugar`\n- `suggested`\n- `suggestion`\n- `suggestions`\n- `sunday`\n- `superhero`\n- `supply`\n- `sure`\n- `surprise`\n- `surprises`\n- `survey`\n- `swap`\n- `sweater`\n- `swimming`\n- `swings`\n- `switch`\n- `symbol`\n- `symbolic`\n- `symbols`\n- `symptom`\n- `system`\n- `taker`\n- `taking`\n- `talking`\n- `tally`\n- `tank`\n- `tasks`\n- `tastes`\n- `tattletale`\n- `taxonomy`\n- `teachers`\n- `tearing`\n- `tease`\n- `teenager`\n- `textile`\n- `thank`\n- `themselves`\n- `theory`\n- `thirst`\n- `thirteen`\n- `thousand`\n- `throw`\n- `tidy`\n- `tightly`\n- `timekeeper`\n- `tiredness`\n- `toddler`\n- `tomorrow`\n- `topic`\n- `topics`\n- `topology`\n- `toys`\n- `trade`\n- `trading`\n- `tradition`\n- `transformations`\n- `transparent`\n- `trash`\n- `tray`\n- `tries`\n- `triggers`\n- `trip`\n- `trips`\n- `trumpet`\n- `trust`\n- `trusted`\n- `tummy`\n- `twelve`\n- `twenty`\n- `twins`\n- `types`\n- `umbrella`\n- `uncertainty`\n- `uncle`\n- `underlying`\n- `unified`\n- `unintended`\n- `units`\n- `unkindness`\n- `unlock`\n- `unsafe`\n- `upset`\n- `upstander`\n- `usually`\n- `utterances`\n- `valid`\n- `velcro`\n- `verified`\n- `verify`\n- `vet`\n- `villain`\n- `violin`\n- `visual`\n- `vitamin`\n- `volume`\n- `volunteer`\n- `vote`\n- `wait`\n- `waiting`\n- `wake`\n- `want`\n- `wanted`\n- `warren`\n- `wash`\n- `wasn`\n- `ways`\n- `weed`\n- `week`\n- `welcome`\n- `welfare`\n- `were`\n- `which`\n- `whisk`\n- `whisper`\n- `whiteboard`\n- `whose`\n- `widely`\n- `wife`\n- `will`\n- `within`\n- `wonder`\n- `workplace`\n- `worried`\n- `wouldn`\n- `woven`\n- `wrong`\n- `xylophone`\n- `yawn`\n- `years`\n- `yes`\n- `yesterday`\n- `younger`\n- `yours`\n- `yucky`\n- `yummy`\n- `zipper`\n\n\n### training_data/wiki/wiki_entry_expansion_index.md\n\n- `abstractoperators`\n- `boundariesandconsent`\n- `communicationactsandlanguage`\n- `currentmaxlevel`\n- `decisions`\n- `detection`\n- `escalated`\n- `escalation`\n- `growthandlifestageshuman`\n- `heuristic`\n- `imaginationandpretendplay`\n- `indexed`\n- `manual`\n- `moneytradeandshopping`\n- `naturallifecyclesandprocesses`\n- `onlinesafetyandprivacy`\n- `plantsandnature`\n- `represented`\n- `safetyrulesandemergencyawareness`\n- `safetysignsandsymbols`\n- `schoollifeandlearning`\n- `selected`\n- `simplephysicsenergy`\n- `socialemotionallearningcompetencies`\n- `storyroles`\n- `uncertaintyandguessing`\n- `waitingandpatience`\n- `wantsneeds`\n- `weatherandcelestial`\n- `wikiexpansionindex`\n\n\n### training_data/wiki/wiki_expansion_index.md\n\n- `accidents`\n- `accidentsandmistakesentries`\n- `advanced`\n- `agreement`\n- `agreementanddisagreement`\n- `agreementanddisagreemententries`\n- `allergy`\n- `anger`\n- `animalcareandpetkeepingentries`\n- `animalhabitatsandhomesentries`\n- `animalsbirdsentries`\n- `animalsfishentries`\n- `animalsinsectsarthropodsentries`\n- `animalsmammalsentries`\n- `animalsreptilesamphibiansentries`\n- `apologize`\n- `app`\n- `approved`\n- `argue`\n- `artandcreativeexpressionentries`\n- `article`\n- `backpack`\n- `bakery`\n- `bandage`\n- `beginning`\n- `beliefs`\n- `bodyparts`\n- `bodypartsentries`\n- `bodystates`\n- `bodystatesandinternalcues`\n- `bodystatesandinternalcuesentries`\n- `boundaries`\n- `boundariesandconsententries`\n- `bruise`\n- `calmness`\n- `categoriesandgroupingentries`\n- `ceiling`\n- `cheat`\n- `checkup`\n- `choresandhomeresponsibilitiesentries`\n- `civicresponsibility`\n- `civicresponsibilityandcommunityrulesentries`\n- `classmate`\n- `classroom`\n- `classroomobjectsandschooltoolsentries`\n- `clinic`\n- `clothingandapparelentries`\n- `collectionsandcollectingentries`\n- `colorsentries`\n- `community`\n- `communityplacesandservicesentries`\n- `complete`\n- `completed`\n- `completion`\n- `compromise`\n- `computer`\n- `conditional`\n- `confirmed`\n- `conflict`\n- `conflictresolutionandrelationshiprepairentries`\n- `connectives`\n- `constructionandmaterialtransformationsentries`\n- `containersandcapacityentries`\n- `cookingandfoodpreparationentries`\n- `cough`\n- `counts`\n- `creation`\n- `csv`\n- `dailyroutinesandselfcareentries`\n- `datachartsandgraphsentries`\n- `degreesoftruthentries`\n- `directionsandnavigationentries`\n- `disagreement`\n- `else`\n- `embarrassment`\n- `emotions`\n- `emotionsentries`\n- `energy`\n- `entity`\n- `environmentalcareandstewardshipentries`\n- `exceptionsandqualificationsentries`\n- `expansion`\n- `fear`\n- `feedback`\n- `fever`\n- `finally`\n- `foodgroupsandnutritionentries`\n- `foodsanddrinks`\n- `foodsanddrinksentries`\n- `foodsfruitsentries`\n- `foodsvegetablesentries`\n- `forever`\n- `forgive`\n- `fractionsandsharingquantitiesentries`\n- `friend`\n- `friends`\n- `friendsandpeerinteractions`\n- `friendsandpeerinteractionsentries`\n- `friendship`\n- `frustration`\n- `futureplanningandgoalsentries`\n- `gardenandplantingbasicsentries`\n- `germ`\n- `grade`\n- `greeting`\n- `greetingsandsocialsalutationsentries`\n- `grocery`\n- `grouprolesandparticipation`\n- `grouprolesandparticipationentries`\n- `growth`\n- `growthandlifestageshumanentries`\n- `growthlifestages`\n- `guess`\n- `guilt`\n- `happiness`\n- `headache`\n- `health`\n- `healthandwellness`\n- `healthandwellnessentries`\n- `hobbiesandinterestsentries`\n- `holidaysandcelebrationsentries`\n- `homerooms`\n- `homeroomsentries`\n- `homework`\n- `hospital`\n- `humorandfigurativelanguageentries`\n- `imagination`\n- `inclusion`\n- `inclusionbullyingandkindnessentries`\n- `intentionsandplansinactionentries`\n- `invite`\n- `judgment`\n- `justification`\n- `keyboard`\n- `kindness`\n- `kinds`\n- `learningmemoryandmetacognition`\n- `lesson`\n- `levelsofintensityandgradationentries`\n- `library`\n- `locationanddirectioninactionentries`\n- `lostandfoundmisplacingobjectsentries`\n- `lunchbox`\n- `machinesandsimplemechanismsentries`\n- `magazine`\n- `mandatory`\n- `manners`\n- `mannerspolitenessandsocialetiquetteentries`\n- `materialcompositionentries`\n- `mathematicalconceptsentries`\n- `max`\n- `meals`\n- `mealsandmealtimetalkentries`\n- `meanwhile`\n- `measurementandcomparisonentries`\n- `medicine`\n- `message`\n- `metadata`\n- `mistakes`\n- `misunderstandings`\n- `moneytrade`\n- `movementandphysicalactionentries`\n- `museum`\n- `musicalinstrumentsentries`\n- `narrator`\n- `naturallifecyclesandprocessesentries`\n- `neighbors`\n- `nervousness`\n- `now`\n- `office`\n- `okay`\n- `online`\n- `onlinesafetyandprivacyentries`\n- `ownership`\n- `ownershipandsharingentries`\n- `panic`\n- `passed`\n- `past`\n- `peer`\n- `pen`\n- `pencil`\n- `peopleroles`\n- `peoplerolesentries`\n- `permanent`\n- `personalidentityandselfdescriptionentries`\n- `perspectives`\n- `perspectivetakingandtheoryofmindentries`\n- `pharmacy`\n- `phone`\n- `photo`\n- `physics`\n- `placesandlandforms`\n- `placesandlandformsentries`\n- `plantsandnatureentries`\n- `playdate`\n- `playgames`\n- `playgamesandsports`\n- `playgamesandsportsentries`\n- `plot`\n- `praise`\n- `praisecriticismandfeedbackentries`\n- `present`\n- `pride`\n- `principal`\n- `professions`\n- `professionsentries`\n- `proves`\n- `proving`\n- `provisional`\n- `putting`\n- `quality`\n- `rash`\n- `ready`\n- `reasons`\n- `recess`\n- `recheck`\n- `rechecked`\n- `rechecking`\n- `retained`\n- `revise`\n- `roles`\n- `rollup`\n- `runny`\n- `sadness`\n- `safetyrules`\n- `safetyrulesandemergencyawarenessentries`\n- `safetysignsandsymbolsentries`\n- `school`\n- `schoollife`\n- `schoollifeandlearningentries`\n- `score`\n- `screen`\n- `seasonalactivitiesentries`\n- `secretssurprisesandkeepingpromisesentries`\n- `sections`\n- `seek`\n- `sensory`\n- `sensoryexperiencesentries`\n- `service`\n- `shadowandlightphenomenaentries`\n- `shame`\n- `sharing`\n- `siblingrelationshipsanddynamicsentries`\n- `simplephysicsenergyandpowerentries`\n- `sleepandrestentries`\n- `smellsandtastesentries`\n- `sneeze`\n- `social`\n- `socialemotionallearningcompetenciesentries`\n- `sore`\n- `sources`\n- `spaceentries`\n- `sport`\n- `stages`\n- `statesofbeingandconditionentries`\n- `stayed`\n- `stementries`\n- `stomachache`\n- `storyrolesandplotelementsentries`\n- `subject`\n- `suddenly`\n- `supporting`\n- `swipe`\n- `tablet`\n- `tag`\n- `tbd`\n- `team`\n- `teammate`\n- `technology`\n- `technologyanddigitalmediaentries`\n- `test`\n- `throat`\n- `timeentries`\n- `today`\n- `toolsandkitchenwareentries`\n- `topologypartsentries`\n- `try`\n- `uncertaintyandguessingentries`\n- `upon`\n- `username`\n- `vehiclestransport`\n- `vehiclestransportentries`\n- `verbsentries`\n- `verifying`\n- `video`\n- `waitingandpatienceentries`\n- `wantsneedsandpreferencesentries`\n- `weatherandcelestialentries`\n- `wellness`\n- `wikientryexpansionindex`\n- `win`\n- `worry`\n- `worth`\n- `written`\n- `yourself`\n\n\n### training_data/wiki/wiki_level2_expansion_assessment.md\n\n- `act`\n- `articles`\n- `assessment`\n- `auto`\n- `automatic`\n- `bearing`\n- `behavior`\n- `belief`\n- `carefully`\n- `cases`\n- `cheating`\n- `clarification`\n- `classic`\n- `conflicts`\n- `connectors`\n- `deepen`\n- `downstream`\n- `easier`\n- `expandable`\n- `fidelity`\n- `framework`\n- `fundamentally`\n- `gains`\n- `generative`\n- `handled`\n- `hedge`\n- `infrastructure`\n- `inventories`\n- `invitation`\n- `misunderstanding`\n- `modifier`\n- `partly`\n- `passive`\n- `plausible`\n- `prevention`\n- `production`\n- `prove`\n- `records`\n- `recurring`\n- `repeatedly`\n- `representative`\n- `resulting`\n- `rich`\n- `scenario`\n- `script`\n- `showing`\n- `situational`\n- `stabilized`\n- `subset`\n- `symptoms`\n- `valuable`\n- `variations`\n- `viewpoint`\n- `warnings`\n| able | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| absence | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| absent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| absolute | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| abstraction | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| abstractions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| academic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| accept | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| acceptance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| accepted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| accident | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| accidental | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| accidents | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| accomplished | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| account | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| accuracy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| accurate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| accurately | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ache | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| aches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| achieve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| achieved | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| achievement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| achievements | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| aching | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| acorns | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| act | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| acted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| acting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| action-linked | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| active | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| activities | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| activity | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| actors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| acts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| actually | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| addition | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| additional | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| additions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| address | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| addressable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| addressed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| addresses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| adequately | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| adjectives | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| admitting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| adult | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| adult-sounding | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| adulthood | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| adults | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| advance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| advanced | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| advantage | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| adventure | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| adventures | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| advice | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| affect | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| affected | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| affection | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| affects | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| affirming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| afraid | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| afterward | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| aged | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ago | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| agree | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| agreeing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| agreement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| agrees | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| agricultural | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ahead | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| aid | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| airplanes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| alarm | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| album | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| alert | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| alias | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| alike | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| alive | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| allergic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| allergies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| allergy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| alligators | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| allowance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| allowances | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| almond | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| almonds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| almost | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| alone | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| alongside | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| aloud | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| already-written | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| also | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| alternate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| alternating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| alternation | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| am | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| amazement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| among | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| amounts | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| amphibian | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| amphibians | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| amused | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| anatomy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| anchor-gap | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| anchored | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| anchoring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| anger | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| angles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| angry | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| announcement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| annoyed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| annoying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| answered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| answering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| anticipation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| antlers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| anymore | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| anyone | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| anything | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| anywhere | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| apartment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apartments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ape | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apologies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apologise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apologize | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apologizing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apology | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| app | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apparel | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| appearance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| appended | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apples | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| appreciated | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| appropriate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| appropriately | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| approved | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| approximately | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| apps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| aquatic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| arc | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| arcs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| areas | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| argue | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| arguing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| argument | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| arguments | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| arise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| arithmetic | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| aroma | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| arrival | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| arrivals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| arrive | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| arrived | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| arrives | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| arriving | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| arrows | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| art | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| arthropod | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| arthropods | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| article | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| article-body | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| articles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| artist | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| as-is | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| asked | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| asleep | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| aspirational | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| aspirations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assemble | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assemblies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assembling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assembly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assessment | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| assessments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assigned | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assignment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assignments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assigns | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assistance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| assistants | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| atop | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| attached | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| attempt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| attendance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| audience | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| audited | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| auditing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| auditorium | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| auditory | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| audits | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| aunt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| authentic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| authentically | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| authenticity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| authority | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| auto-create | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| automatic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| automatically | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| autumn | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| available | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| avian | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| avoiding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| awake | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| aware | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| awareness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| awkward | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| axe | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| axes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| axles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| babies | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| baby | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| background | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| backing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| backlog | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| backpack | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| backpacks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| backs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bad | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| badly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bags | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| baker | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bakeries | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bakers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bakery | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| balloon | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| balls | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| bananas | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| bandage | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bandages | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bands | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bang | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| barely | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bark | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| barking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| barns | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| barrels | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bars | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| baseball | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| based | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| basement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| basics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| baskets | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| batches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bath | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bathrooms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| baths | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bats | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| batter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| batteries | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| battery | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| beaches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| beads | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| beans | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| beard | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bears | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| beat | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| beaters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| beating | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| beats | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| beautiful | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| beauty | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| becoming | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bedrooms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| beds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bedtime | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| been | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| beetle | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| beetles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| began | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| begin | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| beginners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| beginning | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| beginning-middle-end | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| begun | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| behave | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| behavior | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| behaviors | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| behaviour | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| behavioural | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| behaviours | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| being | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| belief | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| beliefs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| believable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| believe | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| believed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| believes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bell-shaped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| belong | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| belonging | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| belongs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| belts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ben | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bench | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| benches | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| benchmarks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bendable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| benefit | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| berries | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| best | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| better | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| bicycle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bicycles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| biggest | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bikes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bill | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bills | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bin | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| binary | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| binder | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| binding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| biological | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| biology | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| birth | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| birthday | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| birthdays | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bit | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bitter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blame | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| blames | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| blaming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bland | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| blankets | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bleat | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bleating | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bleed | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| bleeding | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blend | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| blended | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bless | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bloat | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| blocked | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blocking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blood | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bloom | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blow | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blowing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blown | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blows | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| blueberries | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| blush | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bob | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bodies | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| body-helping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| body-part | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| body-parts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| body-state | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| body-states | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| boiled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bold | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bolt | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bookshelves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| boom | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| booming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| boot | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| boots | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| border | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| borders | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bored | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| boredom | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| boring | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| born | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| borrow | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| borrowed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| borrowing | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| bossed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bossing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| botany | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bother | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bothered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bothering | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bothers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bottles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bought | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| bouncing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| boundaries | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| boundary-setting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bow | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bowls | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| box-like | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| boxes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| boy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| boyfriend | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| boyfriends | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| boys | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bragging | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| brains | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| brake | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| brakes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| branching | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| brave | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bravery | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| breakdown | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| breakfast | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| breath | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| breaths | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| breed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| breeze | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bridge-and-modifier | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bridges | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| brief | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| brighten | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| broad | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| broader | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| broke | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| brooms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| brother | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| brothers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bruise | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bruises | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| brushes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| brushing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| buckets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| buddy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bugs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| builder | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| builders | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bulbs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bully | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bullying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bump | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bumped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bumpier | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bumping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bumps | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bumpy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bun | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bundles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bunnies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| burrow | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| burrows | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| buses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bushy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| butcher | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| butchers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| butter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| butterflies | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| buttery | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| buttons | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| buying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| buys | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| bystander | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| bystanders | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cabinet | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cabinets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cadence | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cafeteria | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cakes | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| calculator | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| calendar | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| call | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| calling | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| calmer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| calming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| calmly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| calmness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| calms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| came | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| camera | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| canceled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cancelled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| candle | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| candles | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| candy | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| cannot | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| canvas | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cap | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| capable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| capacity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cape | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| caps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| captain | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| captains | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| captures | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| carbohydrate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| card | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cards | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| care | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| career | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| careful | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| carefully | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| caregiver | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| careless | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cares | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| caring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| carpenter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| carpenters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| carpets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| carrier | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| carrots | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| carry | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| cartoons | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| carts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cascading | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| case | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cases | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cashier | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| casual | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| catch-all | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| categories | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| categorise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| caterpillar | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cats | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| causally | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| causation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cause | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cause-and-effect | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cause-effect | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| caused | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| causes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| caution | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cautious | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ceiling | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| celebrate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| celebrated | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| celebrating | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| celebration | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| celebrations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| celestial | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| centered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| central | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cents | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ceramic | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| certain | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| certainty | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| chain | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| chains | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chairs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| challenge | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| challenges | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| challenging | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chance | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| changing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| chaos | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| character | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| characteristics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| characters | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| charge | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chargers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chart | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| charts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chase | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chases | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chasing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chatgpt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cheap | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cheat | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cheating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| checked | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| checklist | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| checkout | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| checkpoint | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| checkup | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| checkups | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cheek | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cheeks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cheer | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cheerful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chemical | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chemicals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chemistry | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cherries | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cherry | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chestnut | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chestnuts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chick | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chickens | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| child-accessible | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| child-caregiver | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| child-directed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| child-facing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| child-friendly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| child-level | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| child-produced | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| child-protection | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| child-readable | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| childhood | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| children | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| chimp | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chimpanzees | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chimps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chirping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chocolate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| choice | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| choices | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| choose | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chooses | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chop | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| chopping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chore | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chores | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chosen | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| chunks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| circles | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cities | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| citizen | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| citizens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| citrus | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| city | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| civic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| claim | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| claiming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| claims | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clams | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clap | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clarification | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clarified | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clarify | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clarifying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clarity | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clash | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| class | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| classic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| classification | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| classify | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| classifying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| classmate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| classmates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| classroom | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| classrooms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clauses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cleaner | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cleaners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cleanliness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cleanly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cleanup | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clearer | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| clearing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clearly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clever | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clicking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cliffs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| climate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| climax | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| climb | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clinic | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clinics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| clock | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| clocks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| closely | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| closeness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| closer | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| closing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| closure | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cloth-covered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cloudy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clucking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clue | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clues | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cluster | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| clusters | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| co-occur | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| co-occurrence | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| coaches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| coals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cocoon | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| code | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| coherence | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| coherent | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cohesive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| coins | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| colder | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| collage | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| collar | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| collars | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| collected | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| collection | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| collections | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| colloquial | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| colored | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| colour | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| colours | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| comb | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| combine | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| combined | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| combustion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| comfortably | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| comic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| comics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| coming | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| commands | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| comments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| common | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| commonly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| communicate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| communities | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| community | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| community-places | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| compact | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| compact-file | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| comparatives | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| compare | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| comparisons | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| compass | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| compassion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| compete | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| competence | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| competencies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| competition | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| complaint | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| complaints | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| complete | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| completed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| completely | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| completeness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| completion | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| complex | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| complexity | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| complicated | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| composition | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| compost | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| comprehension-critical | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| compression | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| compromise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| computer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| computers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| concentrate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| concept-language | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| concept-only | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conceptual | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conceptually | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conclude | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conclusion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| condescension | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| condition | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| conditional | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| conditionals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conditions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cones | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| confidence | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| confirm | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| confirmed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conflict | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conflict-repair | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conflicts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| confuse | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| confused | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| confusing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| confusion | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| connected | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| connecting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| connection | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| connective-tissue | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| connectives | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| connector | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| connectors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| consensus | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| consent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| consequence | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| consequences | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conserve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conserving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| considerations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| consistent | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| consists | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| constant | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| constantly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| construction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| constructive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| contact | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| contain | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| container-specific | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| containers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| containing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| contest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| contesting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| contexts | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| contextual | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| contextually | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| continue | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| continuing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| contradiction | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| contradictions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| contrasts | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| controlling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| convention | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| conversation | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| conversational | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| conversations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| convince | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| convinced | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| convincing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cookies | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| cookware | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cooler | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cooperate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cooperation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| coordination | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| coping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| copy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| copying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| corners | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| cornfields | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| corpus-wide | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| correct | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| correcting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| correction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| correctly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| correctness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cost | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| costs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| costumes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cotton | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| couch | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cough | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| coughing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| coughs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| counselor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| countable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| counted | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| counting | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| countries | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| country | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| counts | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| courage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| courtyard | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| courtyards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cousin | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cows | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crab | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crabs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crackers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| craft | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crafts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crampy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cranes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crash | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crashing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crawled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crawling | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crayons | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cream | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cream-colored | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| creation | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| creation-pass | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| creative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| creativity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| creatures | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crickets | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cries | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crime | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crisp | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| criteria | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| criticism | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| criticize | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| critique | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crocodiles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crop | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cross-reference | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crossed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crossings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crosswalk | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crow | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crowd | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crowded | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| crowns | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crows | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| cruel | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cruelly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cruelty | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| crumbs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crush | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crushing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cry | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| crying | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| csv | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cubby | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cube | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cues | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cultural | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cupboards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cupcakes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| curiosity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| curious | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| curl | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| curly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| currency | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| curriculum-only | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| curtains | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| curve | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| customer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| customers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cycle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cycles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| cymbals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dad | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| daily | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| daily-life | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dairy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| daisies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| damage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| damaged | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| damages | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| damp | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dance | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dancing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| danger | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| darkest | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dash | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| data | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| daughter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| days | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| dead | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| deal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| death | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| debate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| december | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| decided | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| decides | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| deciding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| decision-making | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| decisions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| decomposition | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| decorate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| decorating | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| decorations | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| decrease | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dedicated | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| deduplicate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| deep-dive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| deepen | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| deeply | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| deepseek | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| defeat | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| defend | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| deferred | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| defined | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| definitely | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| degree | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| degrees | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| delay | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| delayed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| delicious | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| demand | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| demanding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| demonstrative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| den | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| denim | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| department | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dependable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| depended | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dependency-heavy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dependent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| depending | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| depth | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| describe | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| describes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| describing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| description | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| descriptions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| descriptive | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| deserts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| desire-reporting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| desires | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| desks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| despite | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dessert | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| desserts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| destroy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| destroyed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| detailed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| detected | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| detection | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| detective | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| determined | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| developing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| development | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| developmental | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| devices | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| diarrhea | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| did | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| didn | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| difference | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| differences | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| differently | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| difficult | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| difficulty | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| digest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| digital | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dime | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dimension | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dimensions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dimes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dining | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dinner | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| directed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| directing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| directions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| disagree | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| disagreed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disagreeing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disagreement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disagreements | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disagrees | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disappear | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| disappearing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disappointed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| disappointing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disappointment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| discomfort | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| discourage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| discover | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| discovered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| discrete | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| discuss | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| discussed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| discussing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| discussion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| diseases | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disgust | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dislike | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dislikes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| disorder | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| display | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dissolve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| distance | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| distinction | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| distinctions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| distract | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| distracting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| distractions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ditches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| divide | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| division | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| dizzy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| docks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| doctor | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| doctors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| documentation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| documented | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| doesn | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dogs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| doing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| dollar | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dollars | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| dolphins | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| domain | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| domain-specific | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| domains | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| double | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| doubt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| downloading | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| downstream | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dragonflies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| drawers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| drawn | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dream | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dreams | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dress | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dressers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dresses | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dressing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| drier | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| drifting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dripping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| drive | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| driver | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| drivers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| droop | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| droplets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dropped | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| dropping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| drum | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| drums | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| drying | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| ducks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| duplicate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| duplicates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| durian | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dusty | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| duties | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| duty | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| dynamics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| eager | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| eagles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| earliest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| early-anchor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| earn | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| earned | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| earning | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| earns | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| earrings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| earthworms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| earthy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| easier | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| east | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| echoed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ecosystems | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| editorial | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| edits | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| education | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| educational | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| effect | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| effective | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| effects | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| effort | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| eighteen | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| eighty | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| either | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| elbow | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| elder | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| elderly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| electric | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| electricity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| element | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| elementary | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| elementary-age | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| elements | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| eleven | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| else | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| email | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emails | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| embarrassed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| embarrassing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| embarrassment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| embedded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| embody | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emergencies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emergency | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emerges | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emma | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| emotion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emotion-reporting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emotional | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emotionally | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emotions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| empathy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| emphasise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| enabling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| encounter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| encourage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| encouraged | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| encouragement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| encourages | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| encyclopedic | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| ending | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| enemies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| enemy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| energy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| engage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| engaging | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| enjoy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| enjoyable | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| enjoying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| enjoyment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| enjoys | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| enough | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| ensures | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| entity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| entry-by-entry | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| entry-level | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| environment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| environmental | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| environments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| envy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| epistemics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| equal | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| equally | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| equipment | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| erase | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| erased | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| eraser | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| erasers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| erasing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| errands | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| error | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| escalated | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| escalation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| especially | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| essential | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| estimate | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| estimating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| etc | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| ethics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| etiquette | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| evaluate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| evaluating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| evaluation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| even | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| evenly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| event | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| events | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| ever | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| everyday | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| everyone | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| everywhere | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| evidence-based | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exaggerate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exaggeration | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| example-bearing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| example-before-definition | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exceed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| excellent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| except | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exception | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| exceptions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| excited | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| excitement | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| exciting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| exclude | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| excluded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| excluding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exclusion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| excuse | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| excuses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exercise | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| exercising | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exhaustive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exist | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| existed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| existence | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| exit | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| exotic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expand | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| expand-now | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expandable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expanded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expanding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expansion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expansions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expect | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| expectation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expected | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| expects | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| experience | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| experiences | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| explained | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| explanation | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| explanations | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| explore | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| exposure | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| express | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| expresses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expressing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expression | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| expressive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| extend | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| extended | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| extending | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| external | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| extra | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| extreme | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| eyebrows | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| eyelids | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fables | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fabrics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| facing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| facts | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| factual | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fail | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| failed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| failing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fails | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| failure | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| fairer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fairly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| fairness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fake | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fallback | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| false-belief | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| falsehood | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| falsehoods | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| familiar | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| family-member | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| family-role | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| farmer | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| farmhouses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| farther | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fasten | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fasteners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fat | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| father | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fathers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fault | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| favorite | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| favorites | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| favourite | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| favourites | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fear | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| feature | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| features | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| feed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| feedback | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| feelers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| feelings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fell | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| female | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| females | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fences | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| festival | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fever | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| few | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fewer | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| fibre | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fidelity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fifteen | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| fifty | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| fifty-one | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fight | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fighting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fights | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| figurative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| figure | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| figured | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| figures | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| figuring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| file-by-file | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| file-level | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| filling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| film | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| films | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| finalization | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| finalizing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| finally | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| finding | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| findings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fingerprint | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fingertips | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| finishes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| finishing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| firefighter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| firefighters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fireflies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fires | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| firmer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fisher | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fishers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fishing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fitting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fixes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fixing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fixture | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flag | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flap | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flapping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flashing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flashlight | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flatten | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| flattening | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flatter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| flavor | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| flavoring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flavors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flavour | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flesh | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flew | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fliers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flight | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| flock | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flocks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| floods | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| flute | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fluttery | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| focused | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| focuses | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| focusing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fog | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| folded | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| folder | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| folding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| followed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| follower | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| food-side | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| foods | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| foolish | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| footboards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| footprint | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| footrest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| forbidden | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| force-and-motion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| forced | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| forces | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| forcing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forecast | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| forests | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forever | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forget | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forgets | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forgetting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forgive | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forgiven | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| forgiveness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| forgiving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| forgot | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fork | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| formal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| formats | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| formatting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| formed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| former | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| forming | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| forty | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fourteen | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| foxes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fraction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fractions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| framework | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| frameworks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| framing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| free | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| freely | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| freezes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| frequent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fried | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| friend | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| friendly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| friends | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| friendship | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| friendships | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| frogs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| front-load | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| frown | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fruits | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| frustrated | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| frustrating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| frustration | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fry | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| frying | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| fuel | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fullness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fun | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| function | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| functional | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| functioning | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| functions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fundamental | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fundamentally | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fungus | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| funny | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| further | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| fuss | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| future | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| future-facing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| future-oriented | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gain | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gaining | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gains | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gap-filling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| garage | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| garbage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gardener | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gardeners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gardening | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gardens | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| garment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| garments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gas | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gases | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gasoline | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| gates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gather | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gathered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gathering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gatherings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gave | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| gear | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gears | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| geese | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gemma | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| general-purpose | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| generalise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| generate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| generates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| generating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| generative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gentle | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gentler | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gently | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| genuine | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| genuinely | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| geographic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| geography | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| geometry | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| germ | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| germinate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| germs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gesture | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gestures | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gesundheit | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| giant | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gift | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gifts | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| girl | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| girlfriend | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| girlfriends | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| girls | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| given | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| giver | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| giving | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| gladly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| glance | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| glasses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| glide | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| glides | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gliding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gloves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| glowing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| glue | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gluing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| goal-directed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| goal-setting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| goat | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| goats | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gold | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| golden-yellow | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gone | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| good | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| good-vs-weak | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| goodbye | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gorillas | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| got | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gotten | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gpt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grab | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| grabbing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grabs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| graceful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gracefully | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| gradation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grade | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| grades | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gradually | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grainy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grammar | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grandpa | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grandparent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| graph | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| graphs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grasshoppers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grasslands | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grassy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| grateful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gratitude | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gravel | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| graze | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| great | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| greatest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| greens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| greeting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| greetings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grew | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| grief | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grocery | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| grok | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| groom | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grooming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grouped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grouping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| growling | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| grown-up | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| grown-ups | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| growth | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grudge | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| grumpy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guaranteed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guardian | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guess | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| guessing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| guest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guests | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guidance | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| guilt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guilty | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guitar | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guitars | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| gustatory | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| guy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| habit | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| habitats | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| habits | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| had | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| hairs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| half | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| half-true | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hall | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hallmarks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hallway | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| halves | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| hammers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hamsters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| handful | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| handled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hang | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| happening | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| happily | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| happiness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hard-day | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hardest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hardly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hardware | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| harm | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| harmful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| harmless | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| harsh | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| harshly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| harshness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| harvest | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hatch | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hatching | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hats | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hawks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hay | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| he | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| headache | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| headaches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| headboards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| healing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| heals | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| health | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| health-education | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| healthier | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| healthy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hearable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| heard | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| heart | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| heartbeat | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hearts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| heated | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| heater | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| heating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| heaviness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hebbian | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hedge | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hedges | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hedging | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| heights | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| helicopter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| helicopters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hello | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| helmet | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| helmets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| help-seeking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| helped | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| helper | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| helpers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| helpful | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| helping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| hens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| her | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| herbs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| here | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| hero | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| heroes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| heuristic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hi | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hibernation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hidden-cause | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hidden-state | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hiding | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| high-energy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| high-impact | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| high-leverage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| high-priority | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| high-reuse | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| high-signal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| high-value | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| highest-consensus | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| highest-priority | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| highest-value | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| highlight | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hinges | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hint | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hints | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| his | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| history | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hobbies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hobby | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| holiday | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| holidays | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| home-object | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| home-objects | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| homework | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| honest | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| honestly | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| honesty | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| honking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| honorable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hooked | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hooking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hooks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hope | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hoped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hopeful | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hopes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hopping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| horizon | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| horns | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| horses | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hospital | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hospitals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hotspots | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hotter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hour | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hours | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| household | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| housekeeping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| however | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| howl | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| howling | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hug | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| huge | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| humans | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| humor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hundred | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| hundreds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hunger | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hunted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hunter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hunters | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hunting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hurry | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hurt | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| hurtful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hurting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hurts | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| husband | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hutch | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hygiene | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| hypotheticals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| i | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| icing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ideas | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| identical | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| identify | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| identity | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| idiom | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| idioms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ignore | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ignored | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ignores | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ignoring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ill | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| illness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| image | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| imagination | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| imaginations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| imaginative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| imagine | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| imagined | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| imagining | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| immediately | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| imperative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| implement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| implemented | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| implicit | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| implied | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| importance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| impossibility | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| impossible | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| impressive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| improve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| improvement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| improving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| impulse | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| in-app | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| incidentally | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| include | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| included | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| includes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| including | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| inclusion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| incomplete | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| inconsistent | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| incorporating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| increase | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| increases | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| increasing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| increasingly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| independence | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| independent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| independently | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| indexed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| indoor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| indoors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| inference | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| inferential | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| informal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| infrastructure | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ingredient | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ingredients | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| injuries | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| injury | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ink | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| inner | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| input | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| inserting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| insides | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| instability | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| instance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| instances | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| instantly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| instruction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| instructions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| instrument | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| instruments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| insult | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| insulting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| integrates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| intensity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| intent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| intention | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| intentional | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| intentions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| interact | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| interactions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| interest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| interesting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| interests | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| interleaving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| internal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| internal-state | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| internet | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| interrupt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| interrupted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| interrupting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| interruptions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| introduces | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| introductions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| invent | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| invented | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| inventories | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| inventory | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| invitation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| invite | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| invited | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| invites | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| inviting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| involve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| involved | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| involves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| involving | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| irritates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| island | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| islands | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| isn | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| issue | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| issues | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| itchy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| iteration | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| itself | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| jacket | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| jackets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| january | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| jars | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| jealous | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| jealousy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| jelly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| job | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| jobs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| joined | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| jointed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| joke | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| jokes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| journey | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| joy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| judge | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| judgment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| jug | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| jungles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| junk | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| jupiter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| justifications | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| justified | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| justify | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kale | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kennel | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kernels | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| keyboard | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| keyboards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| keys | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| kick | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| kicking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| kid | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kidding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kids | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| kinder | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kindly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| kindness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kinds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| kinetic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| king | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kinship | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kit | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| kitchens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kitchenware | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kite | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| kites | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| knead | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| kneading | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| knees | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| knew | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| knives | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| knock | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| knocking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| knots | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| knotting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| known | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| knuckle | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| knuckles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| label | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| labeled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| labels | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lack | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lacks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ladders | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ladybugs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lakes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lamps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| landform | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| landforms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| large-number | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| largest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lasting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lasts | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| late-pragmatic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| laugh | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| laughing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| laughs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| laundry | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| law | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lawn | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| laws | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lay | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| laying | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| layouts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lazy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lead | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| leader | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| leaders | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| leads | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| leafy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| leaks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lean | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| learned | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| leash | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| least | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| leaving | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| led | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| ledger | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ledges | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lemon | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lemons | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| length | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| leo | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lesson | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| lessons | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| letting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| level- | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| levels | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| levers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lfm | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| librarian | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| librarians | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| libraries | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| library | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| licking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lie | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| life-process | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| life-stages | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lifetime | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lighter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lightest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lighting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lightly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| liked | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| likely | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| likes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| liking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| limbs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lime | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| limes | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| limited | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| limits | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lined | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lining | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| link | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| linked | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| links | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| liquidai | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| listed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| listen | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| listener | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| listeners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| listens | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lists | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| literacy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| litter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| little | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lively | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lizards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ll | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| local | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| location | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| locations | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| locked | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| locks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| logged | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| loneliness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lonely | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| long-term | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| looked | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| looking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| looms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| loose | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| loser | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| losing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| loss | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lost | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| lot | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lotion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| louder | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| loudly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| love | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| loved | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| low-energy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| low-priority | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| low-risk | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| loyal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| loyalties | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| luck | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lullabies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lullaby | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lump | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lunch | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lunchbox | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| lunchtime | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| lungs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| m | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| machine | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| machine-friendly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| machines | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mad | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| made-up | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| magazine | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| magazines | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| magic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mail | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| main | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mainly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| maintaining | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| maintenance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| make-believe | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| makers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| male | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mammals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| man | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| manage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| managing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mandatory | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| mango | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| manipulation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| manners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| manual | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| map | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| maps | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| marked | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| marker | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| markers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| market | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| marketplace | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| marketplaces | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| marking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| married | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mars | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mash | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mashed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mastered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mat | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| matches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| matching | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| material-science | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| math | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| mathematical | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| matter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| max | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| maya | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| me | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| meadows | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| meals | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mealtime | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| meaningful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| meanness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| meant | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| meanwhile | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| measure | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| measurement | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| measurement-adjacent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| measurement-and-data | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| measures | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| measuring | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| mechanically | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mechanics | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| mechanisms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| media | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| medical | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| medicine | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| medicines | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| meet | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| meeting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| melody | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| melon | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| melons | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| melted | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| melting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| member | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| members | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| memories | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| memory | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mental | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mention | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mentioned | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| menu | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| meowing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mereology | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mess | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| message | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| messages | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| messy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| met | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| meta-concept | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| meta-layer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| metadata-only | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| metals | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| metamorphosis | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| metaphor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| methods | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mice | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| micro-structure | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| microscope | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| middle-childhood | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| might | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| migration | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mild | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| milestone | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| milestones | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| milkshakes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| million | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| minds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mine | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mineral | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| minor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| minutes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| mirror | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mirrors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| misleading | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| misplace | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| misplacing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| miss | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| missed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| misses | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mistake | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mistakes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mistral | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| misunderstand | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| misunderstanding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| misunderstandings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| misunderstands | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| misunderstood | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mitten | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mittens | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mix-up | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mixed-emotion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mixed-up | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mocking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| modal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| modality | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mode | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| models | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| modern | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| modes | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| modifier | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| modifiers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mold | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| molding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mom | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| moment | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| moment-to-moment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| moments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mommy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| monday | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| monkey | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| month | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| months | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| moo | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mood | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mop | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mopping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| moral | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mornings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mostly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mother | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| mothers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| moths | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| motivation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| motorboats | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mounds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| movements | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| muffins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| multi-character | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| multi-part | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| multi-step | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| multiple | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| multiplication | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| museum | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mushroom | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mushrooms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| music | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| musical | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| my | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| mycelium | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| mystery | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| name-calling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| named | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| names | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| naming | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| nap | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| naps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| narrate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| narrative | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| narratives | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| narrator | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| narrower | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| narrows | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| natural | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| naturally | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| navigation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nearest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| neat | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| neatly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| necessarily | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| necessary | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| necessity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| needle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| needles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| negation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| negation-heavy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| negative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| negotiate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| negotiating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| negotiation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| negotiations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| neigh | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| neighbor | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| neighborhood | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| neighbors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| neighbour | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| neighbourhood | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| neither | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| nemotron | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nervous | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| nervousness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| newer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| newly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| newness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| news | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| next-step | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nice | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| nicely | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| nickel | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nickels | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nightmare | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nightmares | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nights | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nine | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| nineteen | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| ninety | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nod | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| noisy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| nonliteral | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| noodles | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| nor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| normal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| normalizing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| normative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| norms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| north | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| notation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| notebooks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| notice | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| noticed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| notices | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| noticing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| noun-based | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| noun-to-pronoun | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| now | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| nuance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nuanced | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| numerical | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| nurse | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| nurses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nursing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nutrition | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nutritional | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| nylon | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| o | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| oaks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| oats | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| object-state | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| objective | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| observable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| observation | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| observations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| observe | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| observed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| observer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| obstacle | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| occasions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| occupies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| occur | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| occurred | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| occurs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| octopuses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| odour | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| offer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| office | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| officer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| officers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ointment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| okay | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| older | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| olds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| olfactory | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| one-time | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ones | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| onions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| online | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| online-safety | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| oops | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| opaque | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| open-ended | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| open-house | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| opener | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| openers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| openings | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| operate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| operation | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| operations | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| operator | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| operators | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| opinions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| opponent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| opposite | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| opposites | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| option | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| optional | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| options | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| oranges | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| orangutans | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| orbits | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| orchards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ordering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| orderly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ordinary | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| organ | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| organisation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| organise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| organization | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| organized | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| organizing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| oriented | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| original | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| orphan-check | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| otherwise | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| our | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| ourselves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| outcome | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| outcomes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| outdoor | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| outdoors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| outlet | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| output | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| over-long | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| overall | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| overflow | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| overlap | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| overlapping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| overlaps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| overly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| overnight | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| overwhelmed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| overwhelming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| owls | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| owned | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| owner | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| owners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ownership | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| owning | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| owns | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| p | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pacing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pack | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| packages | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| packing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| packs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| page | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| paid | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pain | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| painful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| paint | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| painter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| painters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| painting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pair | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| pajamas | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pancakes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| panels | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| panic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pans | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| papers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| parade | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| paragraphs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| parent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| parents | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| parks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| parrot | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| parrots | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| parsed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| parsnip | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| parsnips | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| part-whole | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| partial | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| partially | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| participate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| participates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| participation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| parties | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| partly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| partner | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| partners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| party | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| passage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| passed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| passenger | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| passing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| passive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| password | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| passwords | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| past | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pasta | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pastries | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| patience | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| patient | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| patiently | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| patients | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pattern-drilling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| patterned | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pause | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pay | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| paying | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| payment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| payments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pays | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pe | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peace | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peach | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peaches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peak | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peanut | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peanuts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pear | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pears | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| peas | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peck | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pedestrian | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pee | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peek | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| peels | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| peer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peer-interaction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pen | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pencil | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pencils | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| pending | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| penguin | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| penguins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pennies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| penny | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| people-role | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| people-roles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pepper | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| per-file | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| perceived | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| perception | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| percussion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| perfect | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| perfectly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| performance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| performers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| perhaps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| period | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| peripheral | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| permanent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| permission | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| permission-seeking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| persistent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| person-role | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| personal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| perspective | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| perspective-taking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| perspectives | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| persuade | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| persuasion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| petals | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| petrol | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| petroleum | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pets | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| petting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pharmacies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pharmacy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| phased | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| phenomena | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| phenomenon | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| philosophy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| phone | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| phones | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| photo | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| photos | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| phrase | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| phrasing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| physical-property | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| physics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| piano | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pianos | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| picking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| picnic | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| picnics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pictograph | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| picture | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| picture-like | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pie | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pigs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pill | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pillow | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pillows | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pilot | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pinch | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pineapple | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pineapples | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pines | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pink | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pinky | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pipe | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pit | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pitches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pizza | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| plain | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| plainly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| planes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| planet | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| planets | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| plans | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| plantain | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| plantains | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| planting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| plates | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| plausible | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| play-games | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| playdate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| playdates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| playdough | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| played | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| player | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| playful | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| playgrounds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| plays | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| playtime | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pleasant | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| please | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pleased | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pleasing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| plenty | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| plot | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| plucking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| plug | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| plugs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| plum | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| plums | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| plus | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| pointed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| poison | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| poisonous | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| polished | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| polite | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| politely | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| politeness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pollination | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pollution | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| polyester | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ponds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| poop | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| poor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pop | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| popsicles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| popular | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| populations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| positional | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| positive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| possibilities | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| possibility | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| posters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| posture | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| potatoes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| potential | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| potentially | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pots | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| potter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| potters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pounding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| powers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| practical-language | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| practice | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| practiced | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| practices | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| practicing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| practise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pragmatic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| praise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| precipitation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| predator | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| predators | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| predict | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| predictable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| preference | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| preferences | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| preferring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| preparation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| prepared | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| prepares | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| preparing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| prerequisites | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| present | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| presents | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pretend-certainty | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pretend-play | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pretending | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| pretty | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| prevent | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| prevention | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| preventive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| prevents | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| previously | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| prices | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pride | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| primitive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| principal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| principles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| printed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| prioritize | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| privacy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| private | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| privilege | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| privileges | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| prize | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| problem-solving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| problematic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| problems | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| procedural | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| procedure | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| process | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| processes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| produce | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| product | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| production | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| productively | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| profession | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| professions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| program | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| programs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| progress | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| progressive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| project | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| projects | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| promise | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| promised | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| promises | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| prompt | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| prongs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pronoun | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| propagating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| proper | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| properties | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| property | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| propose | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| protected | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| protecting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| protective | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| protein | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| proud | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| prove | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| proven | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| proves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| provided | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| providing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| proving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| provisional | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| proximity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pry | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| psychology | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| public | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| publication | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| puddle-jumping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| puff | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| puffy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pulley | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pulleys | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pulse | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pumpkins | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| pun | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| puns | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| purchase | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| purchases | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pure | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| purple | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| purposes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| purring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pursue | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| pushy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| putting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| puzzle | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| puzzles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| q | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| quacking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| qualification | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| qualifications | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| qualify | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| qualities | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quality | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| quality-assurance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quality-passed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quantifiers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quantities | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quantity | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| quarter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quarters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| queen | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| questions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| queue | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| queues | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| quicker | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quiet-looking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quieter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| quietly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| quite | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| quitting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| qwen | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rabbit | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rabbits | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| race | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rails | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| railway | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rainbow | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rainbows | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| raincoats | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| raindrops | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| raining | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| rains | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rainy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| raise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| raising | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| raisins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ramp | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ramps | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| range | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rank | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ranked | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ranking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rarely | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rash | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rashes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rationale | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| raven | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ravens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rays | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| re | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| reached | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reaching | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| react | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reacting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reaction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reactions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reacts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| readable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| readers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| readiness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ready | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| real-world | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| realistic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| realistically | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| realize | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| realizes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| reasonable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reasoning-corpus | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reasons | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rebuild | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rebuilding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rebuilds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| receipt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| receipts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| receive | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| receiver | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| receiving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recess | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| recheck | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rechecked | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rechecking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recipe | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| reclassified | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recognising | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recognize | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| recommend | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recommendations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reconciliation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recorder | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recordings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| records | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recount | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recover | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rectangle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rectangles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recurring | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| recyclables | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recycle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recycled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| recycling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reddish-orange | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reduce | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| reeds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| reference | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| referenced | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| references | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| refers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reflect | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reflection | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| reflections | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reflective | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reflexes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| refrigerator | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| refusal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| refuse | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| refusing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| register | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| registers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| regret | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| regular | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| regularly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| regulation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| regulatory | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reinforcement | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| reinforces | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| related | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| relation | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| relational | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relationship | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relationships | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| relative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relatives | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relax | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| relevance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relevant | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reliable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reliably | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relief | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relieve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| relieved | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| remained | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| remaining | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| remember | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| remembered | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| remembering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| remembers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| remind | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reminders | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reminding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reminds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| remote | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| removal | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| remove | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| repairing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| repairs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| repeatedly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| replace | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| replacing | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| replaying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reply | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reported | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reporting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| representative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| represented | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| representing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reptiles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| request | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| requests | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| require | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| requires | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| requiring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rescue | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rescues | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| researching | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| resistance | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| resolutions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| resolve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| resolved | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| resolving | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| respect | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| respected | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| respectful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| respectfully | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| respects | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| respond | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| responding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| responsibilities | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| responsibility | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| responsible | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| restart | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| restated | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| restless | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| resulting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| results | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| retained | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| retell | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| retrace | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| retriever | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| return | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| returned | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| returning | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reuses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reveal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reversal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reverse | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| reviewed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| reviewing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reviews | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| revise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| revisited | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| revolves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| reward | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rewrite-stage | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rhythm | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rhythms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rib | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ribs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rich | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| richer | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| richest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| riddle | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| riddles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ride | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rides | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| right | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| rights | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rigid | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| rind | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rinds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rinse | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| ripe | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rising | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| risk | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| risky | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| roar | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| roast | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| roasted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| robin | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| robins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| robotically | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rocky | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rod | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rods | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| roles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rolled | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| rollup | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| romantic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rooftops | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| roosters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ropes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| roses | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rotating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rotten | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rougher | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| roughly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rounded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rounding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rounds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| route | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| routine | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| routines | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| routing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rubric | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rudder | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rude | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rudeness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rugs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ruin | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ruined | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ruins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rule-following | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rule-governed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ruler | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| rulers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ruling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rumble | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| runner | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| running | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| runny | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rushed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| rushing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sadness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| safely | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| safer | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| safest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| safety-oriented | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| safety-relevant | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| safety-rules | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| said | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| sailboats | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sailor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sailors | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sails | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sakana | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| salad | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| salads | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sale | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| salient | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sally | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sally-anne | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| salmon | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| salsa | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| salty | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| salutations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sam | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| same-size | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sameness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sandcastle | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sap | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sarcasm | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sat | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| satellite | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| satiation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| satisfaction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| satisfied | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| satisfies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| satisfying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sauce | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sauces | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| save | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| saved | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| saving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| saws | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scab | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scaffolds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scaly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scanning | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scans | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scare | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scared | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scares | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scarves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scary | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scatter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scenario | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| scenario-driven | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scenario-expanded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scene | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scene-setting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| schedule | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| schedules | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scheduling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| schema | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| school | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| school-age | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| school-behavior | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| school-domain | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| school-life | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| school-object | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| school-overlap | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| schools | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| schoolwork | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| science | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| science-state | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scientist | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scientists | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scissors | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scooter | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scope | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| score | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scored | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scrape | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scraped | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scraps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scratch | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| scratchy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| screen | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| screens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| script | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| script-like | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| script-rich | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scripts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| scrub | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| search | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| searches | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| seas | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| seasonal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| seasoning | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| seatbelt | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| seatbelts | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| seated | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| secondary | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| seconds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| secret | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| secrets | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sections | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| secure | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| seek | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| seem | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| seemed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| seems | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| segments | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sel | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| select | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| selected | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| selection | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-care | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-conscious | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-control | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-correction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-description | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-identity | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-introduction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-knowledge | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-management | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-regulation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| self-report | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| seller | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sellers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| selling | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| sells | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| semantically | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| send | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| sensations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sense | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| sense-verb | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sensitive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sensory | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sent | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| separated | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| separating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sequenced | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sequences | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| sequencing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| series | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| serious | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| serve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| server | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| serves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| service | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| services | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| setting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| settings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| settled | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| settling | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| setup | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| seven | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| seventeen | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| seventy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| several | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sew | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sewing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shaken | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shakers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shaking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shaky | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shall | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shame | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| share | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| shared | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| shares | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sharing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| sharks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sharpener | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sharpeners | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sharpening | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sharper | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sharply | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shatter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| she | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| shear | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sheets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shells | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sheltered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shepherd | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shepherds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shining | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shirts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shiver | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shivering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shoes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| shook | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shoots | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shop | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| shopkeeper | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shopkeepers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shoppers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shops | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| short-form | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| short-term | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shortcut | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shot | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shots | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shout | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shouting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shovels | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shower | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| showing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| shown | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shred | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shredding | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shrink | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shrinking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shrug | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| shut | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sibling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| siblings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sick | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sickness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sidekick | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sideways | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sign | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| signs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| silence | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| silent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| silhouette | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| silhouettes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| silly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| silver | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| similar | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| similarly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| simmer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| simmering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| simple-physics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| simplest | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| simplify | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| simply | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| simultaneously | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| since | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| singing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| single | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| sinking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sinks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sips | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sirens | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sister | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| sisters | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| site | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| situation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| situational | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| situations | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sixteen | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sixty | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sizes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| skates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| skill | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| skillet | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| skillets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| skills | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| skip | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| skipping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| skirt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| skirts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slamming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slang | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slanted | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sledging | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sleds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sleeve | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| slider | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slight | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slim | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slogan | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sloping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slower | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slowness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| slumped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| smallest | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| smart | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| smartest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| smell | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| smelly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| smile | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| smiled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| smiles | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| smiling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| smoother | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| smoothly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| snacks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| snakes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| snap | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| snaps | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| snapshot | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sneeze | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sneezes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| snout | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| snowballs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| snowflakes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| snowmen | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| snowy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| soap | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| soaring | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| social | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| social-communicative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| social-emotional | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| socially | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| socks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sofa | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| softer | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| softness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| solar | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sold | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| solids | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| solutions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| solve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| solved | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| solves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| solving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| someday | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sometimes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| somewhere | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| song | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| songs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| soon | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sore | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sorry | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| sort | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sorted | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sorting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sota | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| soups | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sour | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| source-of-reason | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sources | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| south | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spaces | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| spanning | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sparing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sparrow | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sparrows | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spatial | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spatial-relation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spawn | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| speak | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| special | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| specialist | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| specialized | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| species | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| specifically | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spectrum | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| speculation | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| speech-act | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spell | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| spelling | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| spend | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| spending | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| spends | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| spent | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| spices | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spicy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spiders | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| spiky | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spine | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| splashing | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| splits | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| spoil | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spoiled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spoils | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spoken | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spoons | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sport | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sports | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sportsmanship | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spouse | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| spring | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| springy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sprout | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| sprouts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| square-shaped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| squeeze | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| squeezing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| squint | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| squirrels | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stabilized | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stables | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stacking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| staff | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stages | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| staging | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stairs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stamps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| standalone | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| standards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| staple | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stapler | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| starchy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stare | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| staring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| started | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| starting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| startling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| state | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| state-change | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| state-of-matter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| state-transition | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| statements | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| static | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stayed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| steadier | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| steadily | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| steep | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| steer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| steers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stem | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stems | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stethoscope | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stew | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stewardship | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stews | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sticker | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stickers | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| stiff | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stinky | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stir | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stitches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stomach | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stomachache | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stomachaches | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stomp | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stopping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| storming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| storms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stormy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| story-amenable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| story-block | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| story-roles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| storybooks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| storyteller | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| storytellers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stoves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| straighten | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strange | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stranger | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strangers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| straps | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| strategic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strategies | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strawberries | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| streams | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| streets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strength-of-evidence | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strengthening | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strengths | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stressed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stretching | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| strict | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| strings | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| stripe | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| strips | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| strong-smelling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strongest | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| struck | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| structural | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| structured | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| structures | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| struggle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| struggles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| struggling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| strumming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stuck | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| student-teacher | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| students | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| studies | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| study | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| studying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| stuff | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sturdy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| styles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sub-domain | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| subcases | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| subcategorization | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| subject | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| subjects | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| subordinate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| subset | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| substructure | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| subtraction | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| subunit | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| succeed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| succeeded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| success | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| such | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| suction | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| suddenly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| suddenlys | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| suffering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sufficient | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sufficiently | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sugar | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| suggest | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| suggested | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| suggesting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| suggestion | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| suggestions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| suggests | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sunday | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sunflowers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sung | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| superhero | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| superheroes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| supply | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| supporting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| supposed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| sure | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| surgery | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| surprise | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| surprised | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| surprises | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| surprising | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| surrounded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| survey | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| surveys | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| survive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swallow | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| swamp | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swamps | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swan | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swans | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swap | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swapping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sweater | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sweetener | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| sweets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swelling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swimmers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| swimming | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| swings | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| swipe | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| swiping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| switch | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| swung | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| symbol | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| symbolic | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| symbols | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| symptom | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| symptoms | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| synonym | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| syntactic | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| syntax | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| syrup | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| system | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| systemic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| systems | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tables | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tablet | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tablets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tableware | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tag | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tailor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tailors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tails | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| takeaways | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| taking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tale | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| talking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| talks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tally | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tank | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tape | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| taped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tapping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| taps | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tart | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tasks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tastes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tasting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tattletale | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| taxonomy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tbd | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tea | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| teachers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| team | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| teammate | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| teammates | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| teams | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| teamwork | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tearing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tease | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| teasing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| technical | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| technically | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| technology | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| teenage | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| teenager | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| teenagers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| template | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| temporal | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| temporality | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| temporary | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tempted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ten | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tens | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| tense | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tension | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tentative | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| test | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| testing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tests | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| textbook | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| textile | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| textures | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thank | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| thankfulness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thanks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| theaters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| theirs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thematically | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| theme | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| themselves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| theory | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| theory-of-mind | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thermometer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thinkers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thirds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thirst | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| thirteen | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| thirty | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thorns | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| though | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| thoughtful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thousand | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| thousands | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| thread-like | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| threads | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| thrive | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| throat | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| throats | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| throw | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| thump | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tickle | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tickled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tidy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tidying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tiering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tiers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tiger | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tigers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tightly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tile | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tiles | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| time-of-day | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| timekeeper | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| times | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| timing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| timmy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tiredness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tires | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tissue | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| toad | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| toads | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| toadstool | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| toadstools | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| toast | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| toasted | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| today | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| toddler | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| toddlers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| todo | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| toilet | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tokyo | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| told | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tomatoes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tomorrow | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tone | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| took | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| topic | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| topics | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| topology | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tops | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| torn | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tortoise | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tough | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| towards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| towel | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| towels | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| towers | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| towns | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| toys | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| traceability | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| track | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tracking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| trade | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| traded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trading | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tradition | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| traditions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trained | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| trains | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| transformations | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| transition | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| transitioning | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| transitions | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| transparent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| transportation | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| trap | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| trapped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trash | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| traveler | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tray | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| treatment | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| triangles | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| trick | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tricky | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tricycle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tricycles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tried | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tries | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| triggers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trim | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trip | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| triplet | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| triplets | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tripping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trips | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| trouble | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trucks | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| truly | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| trumpet | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trumpets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trust | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| trusted | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| trusting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| truth-language | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| truthful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| truthfulness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| try | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| trying | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tube | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tummy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| tunnel | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| turn-taker | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| turn-taking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| turtles | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tutoring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tv | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| tvs | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| twelve | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| twenty | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| twenty-five | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| twice | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| twigs | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| twin | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| twins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| twist-based | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| types | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| typical | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| typically | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| typing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ugly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| umbrella | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| umbrellas | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| uncaring | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| uncertainty | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| unchanged | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| uncle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unclear | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| uncomfortable | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| uncommon | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| uncover | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| uncovered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| underground | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| underlying | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| underneath | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| underpin | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| underwater | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| undo | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unease | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| uneasy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unexpected | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unfair | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| unfairly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unfairness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unfamiliar | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unfolds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| ungrounded | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| unhappiness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unhappy | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unhelpful | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| unified | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unintended | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unique | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| units | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| universal | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unkind | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unkindness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unlike | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| unload | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unlock | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| unlooked-for | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unpack | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| unpleasant | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unplugging | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unreliable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unsafe | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unsettled | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unsteady | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unstick | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unsure | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| untie | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unusual | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unwanted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| unwell | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| upcoming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| updated | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| updating | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| upon | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| upset | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| upsetting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| upstander | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| upstanders | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| urgency | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| urgent | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| us | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| usages | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| user | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| username | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| usernames | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| users | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| usual | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| usually | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| utensil | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| utterances | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vaccine | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vacuum | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vacuuming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| valid | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| validates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| valleys | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| valuable | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| values | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| valves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vanilla | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| variant | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| variants | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| variation | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| variations | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| varied | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| variety | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| various | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| ve | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| velcro | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| venus | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| verified | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| verify | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| verifying | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| version | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| versions | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| vet | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| vets | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vibrate | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vibrates | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| video | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| videos | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| viewpoint | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| views | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| village | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| villages | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| villain | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| violet | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| violin | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| violins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| visit | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| visiting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| visitors | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| visits | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| visual | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vital | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vitamin | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vitamins | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| voice | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| voices | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| volume | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| volunteer | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| volunteering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| vote | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| votes | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| voting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| waddle | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wagging | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wagons | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wait | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| waited | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| waiting | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| wake | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| waking | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| walked | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| walkers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| walnut | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| walnuts | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wand | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wandering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| want | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| wanted | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wanting | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| warehouses | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| warm-blooded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| warmer | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| warn | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| warnings | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| warren | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wash | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| wasn | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| waste | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wasted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| watched | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| watches | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| watchful | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| watching | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| watering | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| watermelons | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| waving | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| ways | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| we | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| weaker | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weakly | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weakness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weapon | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weave | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weaver | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weavers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weaving | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| webbed | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| website | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wedge | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weeds | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| week | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| weekday | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weeks | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| weigh | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weighted | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weights | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| weird | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| welcome | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| welcomed | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| welcoming | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| welfare | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| well-being | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| well-covered | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| well-grounded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| well-scoped | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wellness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wells | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| went | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| were | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| wetter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| whales | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| which | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| whisk | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| whisking | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| whisper | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| whispering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| whistling | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| whiteboard | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| whiteboards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| whole-number | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| whom | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| whose | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wick | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| widely | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| width | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wife | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wiki-grounded | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wildflowers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| will | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| willingness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| win | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| windowsills | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| winner | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| winning | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wipe | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wiping | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wire | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| wires | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wish | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wishes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wishing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| within | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| witness | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wolves | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| woman | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| won | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wonder | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wondering | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| woodcutter | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| woodcutters | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wooden | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| woods | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| woody | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| word-by-word | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| worked | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| worker | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| workers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| workflow | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| workplace | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| world-anchor | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| worlds | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| worms | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| worried | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| worry | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| worse | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| worst | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| worth | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wouldn | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| woven | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wrapped | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| wrappers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| wrapping | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| write | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| written | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| wrong | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| wrongdoing | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| x-rays | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| xylophone | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| yards | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| yawn | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| years | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| yelling | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| yes | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4, reasoning | missing | medium | phase_6 |  |
| yesterday | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| yogurt | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| yolk | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| younger | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| yours | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| yourself | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| yucky | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| yummy | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| zero | word | wiki_l1_l4 | wiki_l1_l4, reasoning | missing | medium | phase_6 |  |
| zipper | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| zippers | word | wiki_l1_l4 | wiki_l1_l4 | missing | medium | phase_6 |  |
| zone | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| zoom | word | wiki_l1_l4 | wiki_l1_l4, story_t1_t4 | missing | medium | phase_6 |  |
| absolutely | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| accidentally | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| acorn | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ada | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| add-on | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| adheres | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| adjust | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| adjusted | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| adult-level | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| aimed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| aims | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| airplane | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| airport | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| aisle | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| alice | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| aligned | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| alignment | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| amazed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| amazing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ambiguous | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| amy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| anne | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| announces | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| anyway | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| aphorisms | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| apologizes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| approaches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| approaching | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| archaic | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| argues | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| arlo | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| armrest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| arrange | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| artwork | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| aside | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| atmosphere | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| attendant | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| attributes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ava | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| backyard | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bale | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| balloons | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| bea | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bead | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| beams | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| became | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| beeping | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| belonged | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bent | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| beth | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| biking | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| billy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| binoculars | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| birthday-like | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| blew | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| blur | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| boards | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bobs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| booms | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bossy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| boyd | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| brand | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| braver | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| broth | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| brought | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| bubble | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bubbling | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bubbly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| buckles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bundle | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| burner | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| burnt | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| bursts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| buttered | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| buzzes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| buzzing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cabin | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cade | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| caleb | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| calibrated | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| cans | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| carpet | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| casing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| casually | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| celebrates | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| celery | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| chalkboard | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| chapter | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| chaser | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| chatters | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cheering | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cheers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| chilly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| chloe | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| chose | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| christmas-like | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| claps | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| clara | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| clearest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| clears | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| click-clack | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| clipboard | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| clockwise | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| closest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| clucks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| coach | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cobwebs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cocoa | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cody | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cole | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| comfy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| compartment | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| completes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| components | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| conductor | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| confident | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| consistency | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| continues | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| contrastive | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| contribute | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| coop | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| counterparts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cousins | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cozy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cracker | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| creak | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| creaking | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| creaks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| creamy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crease | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| creases | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| creek | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| creeps | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crib | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crinkly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crispier | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crispy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| croaking | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crooked | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cross-layer | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crouches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crown | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cruise | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crumbles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crunches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| crunching | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cubes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| curls | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| curves | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cushion | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cutest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| cutter | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dances | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dangle | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dashes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dean | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| deck | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| defenders | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| definition-like | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| delicate | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| delivered | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| delivery | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| denser | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| desired | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| destination | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dew | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| diagram | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| diamonds | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| diaper | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dice | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dip | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dipped | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dips | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dirtiest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| disappeared | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dispenser | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dolly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dot | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dots | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dotted | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| downstairs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dr | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dragons | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| drags | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| drained | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| draped | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dress-up | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| drew | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| dribbles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| driftwood | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| driveway | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| drizzle | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| drizzles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| drumming | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ducklings | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dump | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| dumps | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| early-layer | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| elbows | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| eli | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ella | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ellipsis | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| employs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| empties | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| empty-handed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| encyclopedia | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| endings | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| energized | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| enforce | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| entire | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| entryway | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| envelopes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| eric | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| escape | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| escapes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ethan | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| eve | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| excessive | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| exercises | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| explanatory | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| exploring | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| exposition | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fairy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| faked | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fakes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fallen | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fan-shaped | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fancy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fastens | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fastest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| faucet | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| favor | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| faye | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| feathery | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fern | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fetch | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| filler | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fingernails | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| finn | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flashlights | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flatbed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flattens | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fleece | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flicker | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flickers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flicks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flip | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flippers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flips | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flop | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flopping | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| floppy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flowery | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flown | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fluids | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| flutters | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| foam | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| foil | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| folds | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| footprints | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| footsteps | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| forgives | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fort | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| frees | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| freezing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| friday | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fulcrum | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| fuller | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| gabe | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| galaxy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| generality | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| generalization | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| generalized | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| generic | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| gia | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| glad | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| glimpse | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| global | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| glows | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| glued | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| glues | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| gnat | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| go-kart | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| goalie | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| goodnight | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| grace | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| grandfather | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| grandmother | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| grant | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| graphite | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| grazing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| greasy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| greg | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| grilled | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| grins | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| gritty | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| guardrails | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| gulp | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| gulps | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| gus | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| gwen | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| half-buried | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| halfway | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hammered | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| handrails | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hank | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hardens | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hazel | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| headings | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| henry | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| herself | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| high-level | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| highway | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hiker | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hiking | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| him | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| himself | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| holder | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| homemade | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| honks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hooting | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hopefully | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| horn | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hose | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| howls | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hugged | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hugh | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hugo | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hugs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hum | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hums | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| hung | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| icy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| id | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| imagines | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| inches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| indeed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| infection | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| inherited | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| installed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| integrated | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| interested | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| intersection | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| intersections | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| invention | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| inversion | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| invisible | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| invitations | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| iris | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| isaac | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| itch | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ivy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jace | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jack | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jacks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jade | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jake | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jammed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jeans | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jett | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jewels | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| joel | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jog | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jude | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| jumped | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| june | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| kai | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| kate | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| kay | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| kent | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| kicks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| kiss | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| kneels | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| l | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ladles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lamb | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lambs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| landed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lap | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lark | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| later-layer | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| laughter | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| leaning | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lee | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| leftover | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lemonade | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lengths | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| liam | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lick | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| licks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lighthouse | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lilies | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lily | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| linguistic | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lint | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lip | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| literary | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| loading | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| logan | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| logically | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lots | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| loves | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lucy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| luke | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| lumps | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mae | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| magical | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| maintain | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| march | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| marching | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| markdown | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mason | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| massive | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| masts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mechanical | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| medium-sized | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| meg | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| meow | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| metaphors | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| method | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mia | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| mila | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| miles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| milked | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| miller | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mini | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mini-narratives | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mini-scenes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mint | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| minty | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| minute | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| mismatch | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mitt | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mmm | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| moat | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| moody | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| moos | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| moralizing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| morals | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mossy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| movie | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mr | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mrs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ms | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| multi-paragraph | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| munch | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mural | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| mustache | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| myself | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| napkin | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| narration | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nash | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nate | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ned | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nell | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nesting | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| net | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| newspaper | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nibble | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nibbles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nina | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nipple | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| noah | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nods | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| noises | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| noisier | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nora | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| normalize | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| notebook | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| nudges | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| oar | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| obscures | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| obvious | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| obviously | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| octagonal | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| offered | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| offers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| oiled | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| oldest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| olive | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| oliver | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ooze | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| opal | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ouch | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| outfit | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| outlines | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| overusing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| owen | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| package | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paddles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pads | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paints | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pajama | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| palms | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pantry | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paper-thin | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paragraph | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paragraphing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| parked | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| parking | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| participant | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pasted | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pat | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| patches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| patchwork | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| patio | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pats | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paul | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paused | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paw | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| paws | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| peaceful | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pebbles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pedal | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| peeking | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| peeks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| perfume | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| petal | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pete | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| phil | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| phoebe | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pierces | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| piercing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pinches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pinecone | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pinecones | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pitcher | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pitter-patter | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| playroom | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| plop | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pluck | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| plucks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| poetic | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| poke | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| policy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| polishes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| poorly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| porch | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| positions | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| poster | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| posts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pounces | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pound | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| present-tense | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pretends | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| prettiness | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| print | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| prints | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| prizes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| psychological | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pump | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| pumps | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| puppy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| purrs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| quickest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| quilt | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| quinn | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| races | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| radio | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| railing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rake | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| reader | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| realism | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| redundant | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| reed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| reels | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| refreshing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| registry | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| reid | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| reinforce | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| relaxes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| relying | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rename | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| restatement | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| restful | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| retrofit | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| reuse | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| reused | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| reveals | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rewrite | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ribbon | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rings | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rinsed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rinses | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rinsing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rip | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ripest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ripped | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ripple | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| roaring | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rocket | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rollout | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| rooster | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rosa | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ross | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rotation | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rounder | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| royal | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rub | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rubs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ruby | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rug | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rumbling | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rush | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rushes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| rustling | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ruth | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ryan | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sandwiches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sara | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| saturday | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| saves | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sawdust | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sawhorses | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sawing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scattered | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scavenger | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scene-based | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scene-first | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scenery | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scenes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scenic | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scent | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scoring | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scott | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scrambles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scrapes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scraping | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scratches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| screech | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scrubbed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scrubbing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| scrubs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| seagulls | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| seam | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| searched | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| searching | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| seashell | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| seashells | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| seasick | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| seeker | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| seeks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sentence-count | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| seth | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| setting-first | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| shady | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| shoo | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| shoos | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| short-sentence | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| shorten | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| shorts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| shouts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| showed | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| shy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sidewalk | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| silently | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| silky | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| simplicity | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| single-subject | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sip | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sizzle | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| skeleton | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| skye | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| skyscraper | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slams | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sledding | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slept | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slicer | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slid | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slimy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slips | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slogans | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sloshes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slowed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| slowing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| smiley | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| smooths | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sneaky | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sneezing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sniff | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sniffing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sniffs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| snip | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| snipping | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| snorts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| snowman | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| snug | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| snuggles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| snugly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| soak | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| soaking | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| soapy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| soccer | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| softly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| soggy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| son | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sooner | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sophie | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sorts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| soy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spaceship | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spaghetti | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sparkle | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sparkled | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sparkles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sparkling | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sparkly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spatula | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| speaker-tag | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| specs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spells | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spits | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| splashes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sponge | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spool | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spoonfuls | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spotted | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| spout | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sprays | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| springtime | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sprinkles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| squares | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| squeaky | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| squeezed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| squeezes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| squirts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| squishes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stains | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| star-shaped | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stings | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stood | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stool | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stopped | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stored-file | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| story-like | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| story-shape | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| streamers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stringy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stroke | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stroll | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stuffed | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stuffs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| stuffy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| successfully | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| suds | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| suitcases | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| summarizing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sunshine | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| support-word | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swallowing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swallows | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swam | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sway | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| sweeter | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swinging | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swirl | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swirling | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swirls | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swishes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swishing | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| swoops | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tagged | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tallest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| talons | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tangled | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tangles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tangy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tapes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tara | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tasty | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tate | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| teacup | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| teddy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| templates | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tender | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tennis | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| territory | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tess | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| themes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| theo | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| thinly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| thoroughly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| threw | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| throws | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| thud | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| thumbs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ticket | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tickets | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| ticking | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tickles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tidier | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tier-specific | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tightened | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tighter | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tines | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tiptoes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tire | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tissues | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| toby | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| todd | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| toe | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tom | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| tonight | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| toothbrush | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| toothpaste | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| topical | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tosses | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| traces | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tractor | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| trails | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| treasure | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| treats | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| treehouse | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| treetops | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tripped | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| trough | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| troy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tub | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tuck | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tucked | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tufts | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tug | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tugs | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| tumbles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| turbulence | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| twinkles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| twirl | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| twirls | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| twisted | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| twitches | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| twitching | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unbuckles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unclean | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| uncurls | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| underfoot | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| understandable | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unfinished | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unlocks | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unnatural | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unpacked | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unrelated | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unscrews | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unties | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unwinds | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| unzips | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| upside | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| usable | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| vary | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| velvet | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| vera | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| verdict | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| visibility | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| visibly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| vroom | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| waddles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wag | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wags | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wanders | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| watered | word | story_t1_t4 | story_t1_t4, reasoning | missing | medium | phase_6 |  |
| wavy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| waxy | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| weaves | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wedges | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| west | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| whenever | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| whimpers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| whiskers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| whispers | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| whistle | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| whistles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| whoo-whoo | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| whoosh | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wicker | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wiggle | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wiggles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wiggling | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wiggly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| willa | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wilson | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| winding | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| winds | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wins | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wipes | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wobble | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wobbled | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wobbles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wobbly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| woke | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wonderful | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wonders | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| woolly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| workable | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| workout | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| world-knowledge | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| worrying | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wren | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wrinkles | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| writerly | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| wyatt | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| yawns | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| yeast | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| yells | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| youngest | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| zara | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| zig-zags | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| zip | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| zips | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| zoe | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| zooming | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| zooms | word | story_t1_t4 | story_t1_t4 | missing | medium | phase_6 |  |
| adapted | word | reasoning | reasoning | missing | medium | phase_6 |  |
| adhere | word | reasoning | reasoning | missing | medium | phase_6 |  |
| adjunct | word | reasoning | reasoning | missing | medium | phase_6 |  |
| adjuncts | word | reasoning | reasoning | missing | medium | phase_6 |  |
| algorithmic | word | reasoning | reasoning | missing | medium | phase_6 |  |
| aligning | word | reasoning | reasoning | missing | medium | phase_6 |  |
| altogether | word | reasoning | reasoning | missing | medium | phase_6 |  |
| articulate | word | reasoning | reasoning | missing | medium | phase_6 |  |
| artificial | word | reasoning | reasoning | missing | medium | phase_6 |  |
| breast | word | reasoning | reasoning | missing | medium | phase_6 |  |
| bridge-dependent | word | reasoning | reasoning | missing | medium | phase_6 |  |
| bridge-like | word | reasoning | reasoning | missing | medium | phase_6 |  |
| byte | word | reasoning | reasoning | missing | medium | phase_6 |  |
| byte-pattern | word | reasoning | reasoning | missing | medium | phase_6 |  |
| byte-position | word | reasoning | reasoning | missing | medium | phase_6 |  |
| byte-shift | word | reasoning | reasoning | missing | medium | phase_6 |  |
| byte-stream | word | reasoning | reasoning | missing | medium | phase_6 |  |
| calculation | word | reasoning | reasoning | missing | medium | phase_6 |  |
| calibration | word | reasoning | reasoning | missing | medium | phase_6 |  |
| categorical | word | reasoning | reasoning | missing | medium | phase_6 |  |
| collaboration | word | reasoning | reasoning | missing | medium | phase_6 |  |
| collaborative | word | reasoning | reasoning | missing | medium | phase_6 |  |
| collisions | word | reasoning | reasoning | missing | medium | phase_6 |  |
| combining | word | reasoning | reasoning | missing | medium | phase_6 |  |
| communal | word | reasoning | reasoning | missing | medium | phase_6 |  |
| companion | word | reasoning | reasoning | missing | medium | phase_6 |  |
| complements | word | reasoning | reasoning | missing | medium | phase_6 |  |
| conservation | word | reasoning | reasoning | missing | medium | phase_6 |  |
| consistently | word | reasoning | reasoning | missing | medium | phase_6 |  |
| consulting | word | reasoning | reasoning | missing | medium | phase_6 |  |
| convergence | word | reasoning | reasoning | missing | medium | phase_6 |  |
| cosmos | word | reasoning | reasoning | missing | medium | phase_6 |  |
| costly | word | reasoning | reasoning | missing | medium | phase_6 |  |
| decomposing | word | reasoning | reasoning | missing | medium | phase_6 |  |
| decouples | word | reasoning | reasoning | missing | medium | phase_6 |  |
| decreased | word | reasoning | reasoning | missing | medium | phase_6 |  |
| decreases | word | reasoning | reasoning | missing | medium | phase_6 |  |
| digits | word | reasoning | reasoning | missing | medium | phase_6 |  |
| distribute | word | reasoning | reasoning | missing | medium | phase_6 |  |
| distributional | word | reasoning | reasoning | missing | medium | phase_6 |  |
| divided | word | reasoning | reasoning | missing | medium | phase_6 |  |
| dividing | word | reasoning | reasoning | missing | medium | phase_6 |  |
| drill | word | reasoning | reasoning | missing | medium | phase_6 |  |
| drills | word | reasoning | reasoning | missing | medium | phase_6 |  |
| eighty-eight | word | reasoning | reasoning | missing | medium | phase_6 |  |
| equality | word | reasoning | reasoning | missing | medium | phase_6 |  |
| equals | word | reasoning | reasoning | missing | medium | phase_6 |  |
| equation | word | reasoning | reasoning | missing | medium | phase_6 |  |
| establishes | word | reasoning | reasoning | missing | medium | phase_6 |  |
| executable | word | reasoning | reasoning | missing | medium | phase_6 |  |
| expressions | word | reasoning | reasoning | missing | medium | phase_6 |  |
| extracted | word | reasoning | reasoning | missing | medium | phase_6 |  |
| false-certainty | word | reasoning | reasoning | missing | medium | phase_6 |  |
| fifty-seven | word | reasoning | reasoning | missing | medium | phase_6 |  |
| formation | word | reasoning | reasoning | missing | medium | phase_6 |  |
| four-part | word | reasoning | reasoning | missing | medium | phase_6 |  |
| greater | word | reasoning | reasoning | missing | medium | phase_6 |  |
| grounded-story | word | reasoning | reasoning | missing | medium | phase_6 |  |
| guessed | word | reasoning | reasoning | missing | medium | phase_6 |  |
| hallucination | word | reasoning | reasoning | missing | medium | phase_6 |  |
| hazard | word | reasoning | reasoning | missing | medium | phase_6 |  |
| hazards | word | reasoning | reasoning | missing | medium | phase_6 |  |
| high-density | word | reasoning | reasoning | missing | medium | phase_6 |  |
| higher-order | word | reasoning | reasoning | missing | medium | phase_6 |  |
| if-then | word | reasoning | reasoning | missing | medium | phase_6 |  |
| inclusion-exclusion | word | reasoning | reasoning | missing | medium | phase_6 |  |
| inconsistencies | word | reasoning | reasoning | missing | medium | phase_6 |  |
| inconsistency | word | reasoning | reasoning | missing | medium | phase_6 |  |
| increased | word | reasoning | reasoning | missing | medium | phase_6 |  |
| inspiration | word | reasoning | reasoning | missing | medium | phase_6 |  |
| interpretations | word | reasoning | reasoning | missing | medium | phase_6 |  |
| invariants | word | reasoning | reasoning | missing | medium | phase_6 |  |
| inverse | word | reasoning | reasoning | missing | medium | phase_6 |  |
| judges | word | reasoning | reasoning | missing | medium | phase_6 |  |
| kenji | word | reasoning | reasoning | missing | medium | phase_6 |  |
| kilograms | word | reasoning | reasoning | missing | medium | phase_6 |  |
| kittens | word | reasoning | reasoning | missing | medium | phase_6 |  |
| large-scale | word | reasoning | reasoning | missing | medium | phase_6 |  |
| legacy | word | reasoning | reasoning | missing | medium | phase_6 |  |
| lena | word | reasoning | reasoning | missing | medium | phase_6 |  |
| linear | word | reasoning | reasoning | missing | medium | phase_6 |  |
| lookup | word | reasoning | reasoning | missing | medium | phase_6 |  |
| low-value | word | reasoning | reasoning | missing | medium | phase_6 |  |
| magnitude | word | reasoning | reasoning | missing | medium | phase_6 |  |
| management | word | reasoning | reasoning | missing | medium | phase_6 |  |
| marbles | word | reasoning | reasoning | missing | medium | phase_6 |  |
| math-language | word | reasoning | reasoning | missing | medium | phase_6 |  |
| mentioning | word | reasoning | reasoning | missing | medium | phase_6 |  |
| minus | word | reasoning | reasoning | missing | medium | phase_6 |  |
| modeled | word | reasoning | reasoning | missing | medium | phase_6 |  |
| multiplied | word | reasoning | reasoning | missing | medium | phase_6 |  |
| n | word | reasoning | reasoning | missing | medium | phase_6 |  |
| n- | word | reasoning | reasoning | missing | medium | phase_6 |  |
| narrowly | word | reasoning | reasoning | missing | medium | phase_6 |  |
| natural-language | word | reasoning | reasoning | missing | medium | phase_6 |  |
| nighttime | word | reasoning | reasoning | missing | medium | phase_6 |  |
| ninereeds | word | reasoning | reasoning | missing | medium | phase_6 |  |
| ninety-nine | word | reasoning | reasoning | missing | medium | phase_6 |  |
| ninety-two | word | reasoning | reasoning | missing | medium | phase_6 |  |
| nobody | word | reasoning | reasoning | missing | medium | phase_6 |  |
| non-equality | word | reasoning | reasoning | missing | medium | phase_6 |  |
| non-narrative | word | reasoning | reasoning | missing | medium | phase_6 |  |
| not-knowing | word | reasoning | reasoning | missing | medium | phase_6 |  |
| numerals | word | reasoning | reasoning | missing | medium | phase_6 |  |
| numeric | word | reasoning | reasoning | missing | medium | phase_6 |  |
| one-thirty | word | reasoning | reasoning | missing | medium | phase_6 |  |
| ordinal | word | reasoning | reasoning | missing | medium | phase_6 |  |
| overstating | word | reasoning | reasoning | missing | medium | phase_6 |  |
| papered | word | reasoning | reasoning | missing | medium | phase_6 |  |
| paradox | word | reasoning | reasoning | missing | medium | phase_6 |  |
| persistence | word | reasoning | reasoning | missing | medium | phase_6 |  |
| planted | word | reasoning | reasoning | missing | medium | phase_6 |  |
| presented | word | reasoning | reasoning | missing | medium | phase_6 |  |
| prevented | word | reasoning | reasoning | missing | medium | phase_6 |  |
| progressively | word | reasoning | reasoning | missing | medium | phase_6 |  |
| puppies | word | reasoning | reasoning | missing | medium | phase_6 |  |
| quad | word | reasoning | reasoning | missing | medium | phase_6 |  |
| readings | word | reasoning | reasoning | missing | medium | phase_6 |  |
| reanchors | word | reasoning | reasoning | missing | medium | phase_6 |  |
| rearrange | word | reasoning | reasoning | missing | medium | phase_6 |  |
| rearranging | word | reasoning | reasoning | missing | medium | phase_6 |  |
| received | word | reasoning | reasoning | missing | medium | phase_6 |  |
| recognizes | word | reasoning | reasoning | missing | medium | phase_6 |  |
| regrouping | word | reasoning | reasoning | missing | medium | phase_6 |  |
| removals | word | reasoning | reasoning | missing | medium | phase_6 |  |
| representation | word | reasoning | reasoning | missing | medium | phase_6 |  |
| representations | word | reasoning | reasoning | missing | medium | phase_6 |  |
| represents | word | reasoning | reasoning | missing | medium | phase_6 |  |
| reset | word | reasoning | reasoning | missing | medium | phase_6 |  |
| resolves | word | reasoning | reasoning | missing | medium | phase_6 |  |
| resource | word | reasoning | reasoning | missing | medium | phase_6 |  |
| retrieval | word | reasoning | reasoning | missing | medium | phase_6 |  |
| reversibility | word | reasoning | reasoning | missing | medium | phase_6 |  |
| rigorous | word | reasoning | reasoning | missing | medium | phase_6 |  |
| scale | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sending | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sequential | word | reasoning | reasoning | missing | medium | phase_6 |  |
| seventy-five | word | reasoning | reasoning | missing | medium | phase_6 |  |
| shameful | word | reasoning | reasoning | missing | medium | phase_6 |  |
| single-digit | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sora | word | reasoning | reasoning | missing | medium | phase_6 |  |
| spoke | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sprint | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sprint-based | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sprints | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sprouted | word | reasoning | reasoning | missing | medium | phase_6 |  |
| stabilize | word | reasoning | reasoning | missing | medium | phase_6 |  |
| state-checks | word | reasoning | reasoning | missing | medium | phase_6 |  |
| state-consistency | word | reasoning | reasoning | missing | medium | phase_6 |  |
| state-persistence | word | reasoning | reasoning | missing | medium | phase_6 |  |
| stated | word | reasoning | reasoning | missing | medium | phase_6 |  |
| stateful | word | reasoning | reasoning | missing | medium | phase_6 |  |
| story-based | word | reasoning | reasoning | missing | medium | phase_6 |  |
| story-first | word | reasoning | reasoning | missing | medium | phase_6 |  |
| story-mode | word | reasoning | reasoning | missing | medium | phase_6 |  |
| substitution | word | reasoning | reasoning | missing | medium | phase_6 |  |
| substrate | word | reasoning | reasoning | missing | medium | phase_6 |  |
| subtract | word | reasoning | reasoning | missing | medium | phase_6 |  |
| subtracted | word | reasoning | reasoning | missing | medium | phase_6 |  |
| subtracting | word | reasoning | reasoning | missing | medium | phase_6 |  |
| successor | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sum | word | reasoning | reasoning | missing | medium | phase_6 |  |
| sums | word | reasoning | reasoning | missing | medium | phase_6 |  |
| tasted | word | reasoning | reasoning | missing | medium | phase_6 |  |
| television | word | reasoning | reasoning | missing | medium | phase_6 |  |
| terminology | word | reasoning | reasoning | missing | medium | phase_6 |  |
| therefore | word | reasoning | reasoning | missing | medium | phase_6 |  |
| thirty-four | word | reasoning | reasoning | missing | medium | phase_6 |  |
| thirty-three | word | reasoning | reasoning | missing | medium | phase_6 |  |
| three-digit | word | reasoning | reasoning | missing | medium | phase_6 |  |
| totals | word | reasoning | reasoning | missing | medium | phase_6 |  |
| transformation | word | reasoning | reasoning | missing | medium | phase_6 |  |
| translated | word | reasoning | reasoning | missing | medium | phase_6 |  |
| translating | word | reasoning | reasoning | missing | medium | phase_6 |  |
| translation | word | reasoning | reasoning | missing | medium | phase_6 |  |
| traveled | word | reasoning | reasoning | missing | medium | phase_6 |  |
| triple-mode | word | reasoning | reasoning | missing | medium | phase_6 |  |
| truth-vetting | word | reasoning | reasoning | missing | medium | phase_6 |  |
| twenty-one | word | reasoning | reasoning | missing | medium | phase_6 |  |
| twenty-seven | word | reasoning | reasoning | missing | medium | phase_6 |  |
| twenty-three | word | reasoning | reasoning | missing | medium | phase_6 |  |
| twenty-two | word | reasoning | reasoning | missing | medium | phase_6 |  |
| two-digit | word | reasoning | reasoning | missing | medium | phase_6 |  |
| uphill | word | reasoning | reasoning | missing | medium | phase_6 |  |
| usefully | word | reasoning | reasoning | missing | medium | phase_6 |  |
| utility-based | word | reasoning | reasoning | missing | medium | phase_6 |  |
| utility-bounded | word | reasoning | reasoning | missing | medium | phase_6 |  |
| variables | word | reasoning | reasoning | missing | medium | phase_6 |  |
| verbal | word | reasoning | reasoning | missing | medium | phase_6 |  |
