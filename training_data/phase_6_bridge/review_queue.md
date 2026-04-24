# Phase 6 Bridge Review Queue

Canonical one-file-at-a-time quality-pass queue for the Phase 6 bridge batch.

Use this file after the first Phase 6 bridge files exist and before treating the bridge as stable enough to carry later story/wiki work.

Use this together with:
- `training_data/phase_6_bridge/phase_6_bridge_manifest.md`
- `training_data/phase_6_bridge/phase_6_bridge_spec.md`
- `training_data/phase_6_bridge/story_dialogue_progression.md`
- `training_data/wiki/story_layer_rules.md`

## Review contract for each file

For the selected file only:
1. verify dependency order and vocabulary support
2. verify pattern-grid compliance
3. verify the file stays close to the intended bridge/curriculum format
4. verify no unnecessary vocabulary drift or stylistic flourish
5. verify the file really helps Story Tier 1 / Tier 2 grounding
6. rewrite only that one file as needed
7. leave compact review notes

## Canonical queue

1. [x] `phase_6_01.md`
2. [x] `phase_6_02.md`
3. [x] `phase_6_03.md`
4. [x] `phase_6_04.md`
5. [x] `phase_6_05.md`
6. [x] `phase_6_06.md`

If the manifest grows, extend this queue in manifest order.

---

## Review notes (Post-Wiki-Level-2 Quality Pass — 2026-04-24)

### phase_6_01.md — Foundation
- **Vocabulary**: All grounded. Target words (`thing`, `object`, `word`, `sentence`) introduced cleanly. Supporting vocabulary (`ball`, `box`, `table`, `wood`, `stone`, `book`, `paper`, `dog`, `cat`) all from Phase 1-5.
- **Pattern grid**: Compliant. Uses "A X is a thing", "A sentence is a group of words" as specified.
- **Format**: 4 blocks, 6 lines each. No flourish.
- **Story support**: Strong. Grounds meta-language concepts for Story Tier 1 narrated indirect discourse.
- **Result**: PASS — no changes needed.

### phase_6_02.md — Meta-language
- **Vocabulary**: All grounded. Depends correctly on `word`, `sentence` from phase_6_01.md. Target words (`meaning`, `question`, `answer`, `language`) introduced cleanly.
- **Pattern grid**: Compliant. Uses "A word has a meaning", "A question asks for an answer" as specified.
- **Format**: 4 blocks, 6 lines each. No flourish.
- **Story support**: Strong. Enables question-answer patterns needed for Story Tier 1/2.
- **Result**: PASS — no changes needed.

### phase_6_03.md — Thought / Knowledge
- **Vocabulary**: Target words (`thought`, `idea`, `think`, `know`, `learn`, `understand`) introduced cleanly. Depends correctly on `meaning`, `sentence`, `word` from earlier files.
- **Note**: `mind` appears as a supporting concept (not in Phase 1-5) but is required by the manifest pattern "A thought is in the mind." Acceptable as a necessary bridge introduction.
- **Pattern grid**: Compliant. Uses required patterns.
- **Format**: 4 blocks, 6 lines each. No flourish.
- **Story support**: Strong. Grounds cognitive verbs for Story Tier 1/2 narration.
- **Result**: PASS with note — `mind` is an unlisted bridge concept but necessary per manifest.

### phase_6_04.md — Truth / Reasoning
- **Vocabulary**: All grounded. Target words (`true`, `real`, `fact`, `reason`, `because`) introduced cleanly. Depends correctly on `thought`, `sentence` from earlier files.
- **Pattern grid**: Compliant. Uses "A fact is a true thing", "The reason is that...", "because" patterns as specified.
- **Format**: 4 blocks, 6 lines each. No flourish.
- **Story support**: Strong. Enables causal reasoning and truthfulness patterns for Story Tier 2+.
- **Result**: PASS — no changes needed.

### phase_6_05.md — Communication
- **Vocabulary**: All grounded. Target words (`ask`, `explain`, `say`, `repeat`, `tell`) introduced cleanly. Depends correctly on `question`, `meaning`, `word`, `sentence`, `fact` from earlier files.
- **Pattern grid**: Compliant. Uses "The child asks a question", "The teacher explains the meaning", "repeat the sentence" patterns as specified.
- **Format**: 4 blocks, 6 lines each. No flourish.
- **Story support**: Strong. Grounds communication verbs needed for Story Tier 1 narrated discourse and Tier 2 quoted dialogue.
- **Result**: PASS — no changes needed.

### phase_6_06.md — Planning / Sequence
- **Vocabulary**: All grounded. Target words (`plan`, `goal`, `step`, `first`, `next`, `follow`) introduced cleanly. Depends correctly on `thought` from earlier files.
- **Pattern grid**: Compliant. Uses "A plan has steps", "First... next...", "The goal is to finish", "Follow the steps" patterns as specified.
- **Format**: 4 blocks, 6 lines each. No flourish.
- **Story support**: Strong. Grounds sequential and goal-oriented language for multi-step Story Tier 2+ narratives.
- **Result**: PASS — no changes needed.

### Summary

All 6 Phase 6 bridge files pass the post-Wiki-Level-2 quality pass:
- Dependency order verified
- Pattern grid compliance confirmed
- Format adheres to curriculum discipline (4 blocks, 6 lines each)
- No unnecessary vocabulary drift or stylistic flourish
- All files support Story Tier 1/2 grounding as intended

One observation: `mind` in phase_6_03.md is an unlisted but necessary bridge concept per the manifest. No remediation needed since the manifest explicitly requires this pattern.
