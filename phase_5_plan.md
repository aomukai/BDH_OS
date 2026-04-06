## Phase 5 Planning Document: Motivated Action Sequences

### 1) How this phase differs from phases 1–4
- Phases 1–3 are mostly concept-centric (`what X is`, `where X is`, `what X does`), with heavy property/location/function repetition.
- Phase 4/4_ext adds richer event flow, but motivation is still not the organizing backbone.
- This new phase is explicitly **causal and intentional**: `state -> movement -> target -> arrival -> purpose action -> recap`.
- Sentence 1 now carries a hard requirement absent in prior phases: **state + subject together** (`This is a sleepy bird.`).

### 2) What this phase teaches that current corpus under-teaches
- Stable mapping from **internal state to behavior policy**:
  - `hungry -> move to food -> eat`
  - `sleepy/tired -> move to shelter -> sleep/rest`
  - `thirsty -> move to water -> drink`
- Stronger **goal-directed chaining** across all 6 sentences.
- Better handling of **purpose language** (`to sleep`, `to eat`, `to drink`) grounded in prior actions.
- Stronger **consistency pressure**: same subject, same target thread, no concept drift in sentence 6.

### 3) Corpus-grounded building blocks

#### Agents / subjects (prefer already common)
- `bird`, `bunny`, `frog`, `fish`, `duck`, `cat`, `dog`, `mouse`, `squirrel`, `bee`
- Use `rabbit` sparingly at first (close to existing `bunny` but less established in current files).

#### Motivations / internal states (new core set)
- `sleepy`, `hungry`, `thirsty`, `tired`
- Optional later extension: `cold`, `hot` (only if behavior mapping is concrete and consistent).

#### Environments / media (high overlap with corpus)
- `air`, `water`, `grass`, `ground`, `soil`, `field`, `pond`, `tree`, `branch`, `nest`, `hole`, `bush`

#### Movement verbs (already familiar)
- `flies`, `swims`, `jumps`, `hops`, `runs`, `walks`, `crawls`, `climbs`, `moves`

#### Targets / destinations (already grounded)
- `nest`, `pond`, `water`, `carrot`, `leaf`, `hole`, `branch`, `bush`, `flower`

#### Arrival / transition verbs
- `lands`, `stops`, `reaches`, `goes into`, `returns to`

#### Purpose / outcome verbs
- `sleep`, `rest`, `eat`, `drink`, `hide`, `catch`
- Keep object links concrete: `eat the carrot`, `drink the water`, `sleep in the nest`.

#### Sentence-6 recap patterns (no new concepts)
- `The {subject} {move_verb} to the {target} to {purpose_verb}.`
- `To {purpose_verb}, the {subject} {move_verb} to the {target}.`
- Only reuse subject/action/target/purpose already stated in sentences 1–5.

### 4) Vocabulary policy
- Prioritize terms already frequent in phases 1–4 (`bird`, `bunny`, `grass`, `nest`, `water`, `pond`, `fly`, `jump`, `land`, `eat`, `drink`).
- Introduce new tokens only when essential to the phase objective (mainly motivation adjectives).
- Avoid lexical novelty in recap lines; recap should consolidate, not expand.

#### State-contrast rule (critical)
- Treat motivation words as high-contrast triggers, not decoration.
- For each subject, include at least 2-3 stories with different motivations and different targets.
- Keep subject constant while changing motivation, destination, and purpose path.
- Example contrast pair:
  - `hungry bird -> worm -> eat`
  - `sleepy bird -> nest -> sleep`
- Avoid single default routes (for example, do not make every bird story go to `nest` regardless of state).

### 5) Reusable 6-sentence schema (mandatory shape)
1. `This is a {motivation} {subject}.`
2. `The {subject} {movement_in_medium} in/on {environment}.`
3. `The {subject} {movement_to_target} to {target}.`
4. `The {subject} {arrival_verb} in/on/at {target}.`
5. `The {subject} {purpose_action} in/on/at {target_or_object}.`
6. `The {subject} {movement_to_target} to {target} to {purpose_infinitive}.`

### 6) Strict constraints vs slight variation

#### Must stay strict
- Exactly 6 sentences.
- Sentence 1 includes both motivation and subject.
- No pronouns for main subject.
- Concrete, visible, simple language.
- One coherent state-action-goal-outcome chain.
- Sentence 6 introduces no new concepts.
- Motivation in sentence 1 must causally control sentence 3 target and sentence 5 outcome.

#### Can vary slightly
- Prepositions are restricted in v1 to `in`, `on`, `to` for consistency. Expand later if needed.
- Arrival verb choice (`lands`, `stops`, `reaches`, `goes into`).
- Movement verb choice per species (`flies`, `swims`, `hops`, `runs`).
- Purpose verb within mapped state family (`sleep/rest`, `eat`, `drink`, `hide`).

#### Additional consistency rules (v1)
- Keep movement fixed per subject within v1:
  - `bird -> flies`
  - `bunny -> hops`
  - `frog -> jumps`
  - `fish -> swims`
  - `duck -> swims`
- Medium must match movement explicitly:
  - `flies -> air`
  - `swims -> water/pond`
  - `hops/jumps -> grass/ground`
- Sentence 5 uses two consistent forms:
  - object form for consumption: `eats the X`, `drinks the water`
  - location form for rest/sleep: `rests in/on the X`, `sleeps in the X`

### 7) Practical rollout strategy
- Start with 3 motivation families: `hungry`, `sleepy`, `thirsty`.
- Start with highly familiar subjects: `bird`, `bunny`, `frog`, `fish`, `duck`.
- Use one canonical schema for initial batch; avoid stylistic variants early.
- Build a compatibility matrix before drafting:
  - subject x movement
  - subject x valid target
  - motivation x purpose verb
- Add a contrast matrix for each subject:
  - subject x motivation -> unique destination -> unique outcome
  - verify that different motivations do not collapse to the same destination unless intentionally justified
- QA checklist per story:
  - sentence 1 has state+subject
  - same subject throughout
  - target continuity across 3/4/5/6
  - sentence 6 adds nothing new
- QA checklist per subject (cross-story):
  - each motivation maps to a distinct, plausible goal path
  - state is inferable from action sequence alone
  - no "always-goes-to-X" shortcut emerges
- After stable first batch, expand to `tired` and additional subjects, then limited recap variation.

### 8) Practical dataset creation workflow (no code)
1. Define the initial subject set (for example: `bird`, `bunny`, `frog`, `fish`, `duck`).
2. Define the trigger set (`hungry`, `sleepy`, `thirsty`).
3. For each subject, pre-assign one destination/outcome pair per trigger.
4. Sanity-check biological plausibility and corpus vocabulary overlap.
5. Draft stories using the fixed 6-sentence schema only.
6. Run a manual review pass:
   - sentence-level constraints
   - cross-story contrast for each subject
   - recap integrity (sentence 6 introduces nothing new)
7. Freeze batch v1 before adding new states or lexical variants.

### 9) v1.1 Extension Track (basic concept layer)
- After v1 is stable, add one contrast layer at a time:
  - speed contrast: `fast/slow`
  - size contrast: `big/small`
- Keep prepositions restricted in v1.1 (`in`, `on`, `to`).
- Keep movement-medium mapping strict.
- Keep one added contrast dimension per story.
- Use [phase_5_v1_1_extension.md](/home/aomukai/Projects/BDH_OS/phase_5_v1_1_extension.md) as the v1.1 blueprint source.

Core design principle preserved: this phase trains **state -> action -> goal -> outcome**, not static description.
