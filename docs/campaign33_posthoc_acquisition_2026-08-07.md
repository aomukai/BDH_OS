# Campaign 33 post-hoc held-out acquisition review

**Reviewed:** 2026-08-07  
**Assessment campaign:** `campaign-33-posthoc-acquisition-v1`  
**Source campaign:** `campaign-33-play-recovery-recommissioned-v1`  
**Mode:** experimental observation; no training, ranking, or promotion  
**Suite artifact:** `art-d7c9adf31b595671` / SHA-256 `289281a9a7ebaba5882ef5260970180e084c5b5a716065731c13a502c2ff5b88`

## Question and method

The original Campaign 33 suite did not directly test the new curriculum. This
assessment presented 24 manually paraphrased prompts for concepts introduced as
`new_allowlist` material, two from each of the twelve blocks, plus four invariant
protected anchors required for preservation context. Every surviving terminal
checkpoint was compared with the exact common baseline. Branch 1 could not be
tested because its terminal weights do not exist.

The first 24-case suite artifact, `art-ce29566266146719`, was invalid because it
omitted the evaluator's required `protected` group. Branch 2 and Branch 3 each
reached a deterministic `KeyError` only after model execution; Branch 4 was
cancelled before lease. Those failed runs remain preserved. The evaluator now
rejects missing groups before model load, and all results below use the corrected
28-case artifact.

## Results

| Checkpoint | Capability passed | Protected passed | Pathological outputs | Overall passed | Ingress/core/intention drift |
|---|---:|---:|---:|---:|---|
| Common baseline | 0/24 | 0/4 (score `0.125` from partial credit) | 18/28 | 0/28 | reference |
| Branch 2, historical repaired | 1/24 | 0/4 | 14/28 | 1/28 | `0.11423 / 0.02921 / 0.07313` |
| Branch 3, protected last | 1/24 | 3/4 | 8/28 | 4/28 | `0.06374 / 0.01229 / 0.02837` |
| Branch 4, protected first | 1/24 | 0/4 | 19/28 | 1/28 | `0.06012 / 0.01371 / 0.03659` |

All three trained terminals passed the same capability case,
`c33-b10-referring`; the baseline passed none. No other held-out capability case
passed. Branch 3 passed the two unknown-information anchors and the adversarial
instruction-boundary anchor. It did not pass the correction anchor. Branches 2
and 4 passed no protected anchor.

All scans remained finite, with no dead or saturated layer. Held-out loss is
recorded in the artifacts as telemetry and has no interpretive or decision role.

Evaluation artifacts:

- Branch 2: `art-0c6532b8364b9c63` / `b844914696390ebcedc671660b167ecfc386cde53c94e93294709180216b51ac`
- Branch 3: `art-dc4a4e4f892763e1` / `9ae84c73ae5b196373c0b35fbf5d6e2efe7a222466538008b8aa327e5673f70f`
- Branch 4: `art-fdfc00ff97fe41c9` / `befb60af0461f6019f52bbb065665d21eaf5292c7f98781c5b9c6ba4825edc09`

## Conclusions

1. Campaign 33 produced evidence of very narrow held-out acquisition, not broad
   vocabulary acquisition. `referring` transferred to unseen wording in every
   surviving trained branch; 23 of 24 sampled concepts did not meet the strict
   keyword criterion.
2. The protected-last effect survived paraphrasing. Branch 3 retained 3/4
   protected behaviors under unseen wording, while the otherwise clean
   protected-first Branch 4 retained 0/4. This strengthens the conclusion that
   last-position protection affected accessible behavior rather than merely
   memorizing the original evaluation prompts.
3. Branch 3 was also much less pathological than Branch 4 (`8/28` versus
   `19/28`). The ordering effect therefore extended beyond protected keyword
   score to expression stability in this battery.
4. Branch 2's larger representation drift did not correspond to broader
   held-out acquisition or protected behavior. Coarse drift magnitude is not a
   learning-success measure.

These are immediate elicitation results from one small, strict suite. A failed
keyword case can still contain partial or differently phrased understanding, so
the immutable response text remains the primary evidence for later human review.

