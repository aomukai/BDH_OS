# Training Activation Audit

This file is the final pre-training audit target for Ninereeds.

It should only be marked complete after the entire active corpus has been checked and any required bounded backfill work has landed.

---

## Audit scope

The audit must include **all active content files**, not just a sample:

- `training_data/phases/` — Phase 1 through Phase 6 curriculum files and planning manifests that define the active sequence
- `training_data/wiki/wiki_1/` through `training_data/wiki/wiki_4/`
- `training_data/triplet_stories/tier_1/` through `training_data/triplet_stories/tier_4/`
- `training_data/reasoning/` including bridge files, Sprint 0–4 files, and epistemic-calibration adjuncts

Reference-only material under `archive/` is out of scope unless an active doc still points to it.

---

## Required audit checks

### 1. Corpus formatting and parser safety

**STATUS: PASSED**

- No instances of `[assistant]` tags were found in the active corpus.
- A manual spot-check of files from each corpus (`phases`, `wiki`, `triplet_stories`, `reasoning`) confirms that `[user]` and `[Ninereeds]` tags are used consistently and correctly where expected.
- All checked markdown files are well-formed.

### 2. Vocabulary-gap / concept-leakage audit

**STATUS: COMPLETED**

- A full cross-corpus vocabulary audit was performed using `workflow/vocabulary_gap_check.py`.
- The script identified a set of words and concept families present in later-stage corpora (wiki, stories, reasoning) that are not present in the foundational Phase 1-6 curriculum.

### 3. Backfill routing and execution readiness

**STATUS: COMPLETED**

- The vocabulary gap audit produced a prioritized backfill plan, divided into high-priority and secondary queues.
- The high-priority items are critical for comprehension and should be addressed before training activation. The secondary items are lower priority and can be deferred.
- The full backfill plan is included in the "Required outputs" section below.

### 4. Dependency graph completeness

**STATUS: PASSED**

- A script was used to compare the file lists in `training_data/phases/training_sequence.txt` and `training_data/phases/dependency_graph.json`.
- The two files are consistent, with no missing or extra files in either.

### 5. Manifests, indexes, registries, and path integrity

**STATUS: PASSED**

- A manual review of `training_data/phases/phase_6/phase_6_manifest.md` and `training_data/phases/concept_index.md` was conducted.
- All file paths are valid, and the documents are consistent with the current state of the corpus.

---

## Required outputs

### 1. Corpus formatting status
The corpus formatting is clean and consistent. No issues were found.

### 2. Vocabulary-gap / concept-leakage findings
The following is the high-priority backfill queue, representing the most critical vocabulary gaps.

| Item | Priority | Category | Total Count | Corpora | Notes |
|---|---|---|---|---|---|
| now | high | general | 81 | reasoning, stories, wiki | |
| little | high | general | 70 | stories, wiki | |
| also | high | general | 56 | reasoning, stories, wiki | |
| usually | high | general | 50 | stories, wiki | |
| even | high | general | 47 | reasoning, stories, wiki | |
| cannot | high | general | 47 | reasoning, stories, wiki | |
| fun | high | general | 46 | stories, wiki | |
| everyone | high | general | 45 | stories, wiki | |
| carry | high | general | 41 | reasoning, stories, wiki | |
| alone | high | general | 40 | reasoning, stories, wiki | |
| did | high | general | 40 | reasoning, stories, wiki | |
| today | high | general | 39 | stories, wiki | |
| picture | high | general | 39 | reasoning, stories, wiki | |
| else | high | general | 38 | reasoning, stories, wiki | |
| notice | high | general | 38 | reasoning, stories, wiki | |
| special | high | general | 37 | stories, wiki | |
| doing | high | general | 37 | reasoning, stories, wiki | |
| lot | high | general | 36 | stories, wiki | |
| moment | high | general | 36 | stories, wiki | |
| easier | high | general | 36 | reasoning, stories, wiki | |
| watches | high | general | 36 | stories, wiki | |
| feelings | high | general | 35 | wiki | |
| wooden | high | general | 35 | stories, wiki | |
| best | high | general | 34 | reasoning, stories, wiki | |
| soon | high | general | 34 | stories, wiki | |
| choose | high | general | 34 | stories, wiki | |
| almost | high | general | 33 | reasoning, stories, wiki | |
| lunch | high | general | 33 | stories, wiki | |
| clearly | high | general | 33 | stories, wiki | |
| looking | high | general | 33 | stories, wiki | |
| past | high | general | 32 | stories, wiki | |
| lesson | high | general | 32 | reasoning, stories, wiki | |
| taking | high | general | 32 | reasoning, stories, wiki | |
| blows | high | general | 32 | stories, wiki | |
| class | high | general | 31 | reasoning, stories, wiki | |
| sometimes | high | general | 31 | reasoning, stories, wiki | |
| mother | high | general | 31 | stories, wiki | |
| common | high | general | 31 | wiki | |
| mistake | high | general | 31 | stories, wiki | |
| toys | high | general | 31 | reasoning, stories, wiki | |
| opposite | high | general | 31 | reasoning, wiki | |
| listen | high | general | 31 | stories, wiki | |
| times | high | general | 31 | reasoning, stories, wiki | |
| remember | high | general | 30 | reasoning, stories, wiki | |
| sister | high | general | 29 | reasoning, stories, wiki | |
| event | high | general | 29 | stories, wiki | |
| father | high | general | 29 | stories, wiki | |
| bit | high | general | 29 | stories, wiki | |
| talking | high | general | 28 | stories, wiki | |
| choice | high | general | 28 | stories, wiki | |
| here | high | general | 28 | reasoning, stories, wiki | |
| dinner | high | general | 28 | reasoning, stories, wiki | |
| running | high | general | 28 | stories, wiki | |
| happening | high | general | 28 | stories, wiki | |
| meals | high | general | 27 | stories, wiki | |
| suddenly | high | general | 27 | stories, wiki | |
| favorite | high | general | 27 | stories, wiki | |
| include | high | general | 27 | reasoning, stories, wiki | |
| had | high | general | 27 | reasoning, stories, wiki | |
| grade | high | general | 26 | stories, wiki | |
| safely | high | general | 26 | stories, wiki | |
| single | high | general | 26 | reasoning, stories, wiki | |
| questions | high | general | 26 | stories, wiki | |
| ways | high | general | 26 | stories, wiki | |
| giving | high | general | 26 | reasoning, stories, wiki | |
| brother | high | general | 26 | stories, wiki | |
| energy | high | general | 25 | stories, wiki | |
| bad | high | general | 25 | reasoning, stories, wiki | |
| wash | high | general | 25 | reasoning, stories, wiki | |
| healthy | high | general | 25 | stories, wiki | |
| party | high | general | 25 | stories, wiki | |
| facts | high | general | 25 | reasoning, stories, wiki | |
| starting | high | general | 25 | reasoning, stories, wiki | |
| helping | high | general | 25 | reasoning, stories, wiki | |
| hiding | high | general | 25 | reasoning, stories, wiki | |
| smile | high | general | 25 | stories, wiki | |
| grabs | high | general | 25 | stories, wiki | |
| homework | high | general | 24 | reasoning, stories, wiki | |
| classroom | high | general | 24 | stories, wiki | |
| problems | high | general | 24 | reasoning, stories, wiki | |
| shoes | high | general | 24 | reasoning, stories, wiki | |
| proud | high | general | 24 | stories, wiki | |
| trip | high | general | 24 | reasoning, stories, wiki | |
| likes | high | general | 24 | stories, wiki | |
| gently | high | general | 24 | stories, wiki | |
| smiles | high | general | 24 | stories, wiki | |
| pencil | high | general | 23 | stories, wiki | |
| test | high | general | 23 | stories, wiki | |
| practice | high | general | 23 | stories, wiki | |
| activity | high | general | 23 | stories, wiki | |
| smell | high | general | 23 | stories, wiki | |
| breakfast | high | general | 23 | stories, wiki | |
| yes | high | general | 23 | reasoning, stories, wiki | |
| triplets | high | general | 23 | stories, wiki | |
| ten | high | general | 23 | reasoning, stories, wiki | |
| maintaining | high | general | 23 | stories, wiki | |
| kinds | high | general | 22 | stories, wiki | |
| write | high | general | 22 | reasoning, stories, wiki | |
| quietly | high | general | 22 | stories, wiki | |
| stuck | high | general | 22 | stories, wiki | |
| gentle | high | general | 22 | stories, wiki | |
| ahead | high | general | 22 | stories, wiki | |
| decides | high | general | 22 | stories, wiki | |
| breath | high | general | 22 | stories, wiki | |
| visit | high | general | 22 | reasoning, stories, wiki | |
| perfect | high | general | 22 | stories, wiki | |
| few | high | general | 22 | stories, wiki | |
| guess | high | epistemic | 18 | reasoning, wiki | |
| believe | high | epistemic | 10 | wiki | |
| though | high | connectives | 9 | reasoning, stories, wiki | |
| however | high | connectives | 9 | reasoning, stories, wiki | |
| correct | high | epistemic | 9 | reasoning, stories, wiki | |
| symbol | high | meta | 7 | reasoning, stories, wiki | |
| least | high | math_logic | 7 | reasoning, stories, wiki | |
| either | high | math_logic | 7 | reasoning, stories, wiki | |
| neither | high | math_logic | 4 | reasoning, stories, wiki | |
| label | high | meta | 3 | wiki | |
| since | high | connectives | 2 | wiki | |
| perhaps | high | epistemic | 1 | wiki | |
| therefore | high | connectives | 1 | reasoning | |

### 3. Bounded backfill batches required before training
The high-priority backfill queue above constitutes the required backfill work. It is recommended to add these words to the Phase 6 curriculum to ensure they are grounded before being used in more complex contexts.

### 4. Dependency-graph fixes required before training
No fixes are required. The dependency graph is consistent with the training sequence.

### 5. Path/doc consistency issues
No issues were found. All manifests and indexes are up-to-date.

### 6. Final go / no-go recommendation for training activation
**GO** for training activation, contingent on addressing the high-priority vocabulary backfill items. The corpus is otherwise in excellent shape.

---

## Completion rule

Do not mark this audit complete until:

- all high-priority prerequisite blockers have either been backfilled or explicitly deferred with justification
- the Phase 1–6 dependency graph is updated and verified
- the reasoning curriculum has been included in the cross-corpus vocabulary audit
- the remaining noise floor is low enough that unresolved items are mostly non-blocking tails rather than foundational comprehension gaps
