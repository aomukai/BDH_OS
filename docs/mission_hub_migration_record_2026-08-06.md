# Mission Hub migration record — 2026-08-06

## Preserved evidence

The original sources were not modified. Copied evidence is stored outside the repository under `~/.local/share/ninereeds/mission-hub/evidence` with portable manifests, immutable content-addressed blobs, and lossless JSON record imports.

| Source | Snapshot SHA-256 | Files | Imported JSON records | Byte preservation |
|---|---|---:|---:|---|
| Workstation control ledger | `946f9d60ab0356472f8505d92adb1b10f2e49c199d1b97fdb3def5b05cbbda9c` | 2,427 | 2,421 | copied and content-hashed |
| Workstation MSM state | `9b0598a0c8ab1c6097112d191c52c07e8ba47741f492b226cb4433a76ac74987` | 5 | 3 | copied and content-hashed |
| Workstation campaign/log evidence (complete JSON/JSONL/Markdown/log capture) | `3e376250adbd03e7a05fed41d92aa7c05aa7a6441a53988e3dbfa969c366cdf2` | 641 | 258 | copied and content-hashed |
| Workstation Lab messages | `c8b5f847c7b00203273866eb380d4263c46c5f17197acbc00414c5f0a862da00` | 112 | 111 | copied and content-hashed |
| Trainbox control ledger | `9eeba7597d15b435713a603d1bf6814b3cdf25fd74ad689c5c3203c30cced9c1` | 1,861 | 1,855 | copied on trainbox, transferred, verified, imported |
| Trainbox checkpoint index | `400f3a0780fe604034d9b67de096c14b3b286bd41dfd11874defe5823d56af30` | 179 | 114 | JSON/Markdown imported; weight files metadata-indexed only |

An earlier campaign snapshot omitted JSONL/log files. It remains preserved as evidence but is superseded for migration purposes by the complete `3e376…` snapshot.

### Reconciliation source snapshots

Before source-control cleanup, both dirty working trees were captured outside the repository under `~/.local/share/ninereeds/mission-hub/evidence/reconciliation-2026-08-06`.

| Snapshot | SHA-256 | Purpose |
|---|---|---|
| Repository refs bundle | `e43caad29400d3ad11a5383586641ea759e7efe0ca1ffb1b0b7a080a27c6fcb0` | Complete reachable Git refs before reconciliation |
| Workstation tracked patch | `bcbf6031d627607e23ad5865c9a1943c8817b05b6d62d042d3065d646c0da070` | Binary/full-index preservation of all tracked workstation changes |
| Workstation source worktree | `550f9f403e395e55ad17814b0bb5eebe2385f1c7a30926fcd9ea33cdcc509d4a` | Physical source snapshot excluding data/runtime roots |
| Trainbox tracked patch | `2c5dd54b1432da37899ee462cc2f05672e002e229d6ff35bb24d6244261d1022` | Binary/full-index preservation of all tracked trainbox changes |
| Trainbox untracked source | `cb5023cf94ba08c44a6685013d6cf22d74bd433118f2c687cb52555884dba129` | Physical preservation of trainbox-only untracked paths |

The trainbox had 21 modified and 22 untracked source entries. A post-capture checksum comparison found every source file present there identical to the corresponding workstation working-tree file. The workstation tree is therefore the canonical superset; no trainbox file overwrote it. The trainbox branch commit remains reachable in the refs bundle and through `origin/trainbox/runtime`.

### Training-library reconciliation

The workstation and trainbox libraries each contain 244,388 regular files. Their path layouts differ: the trainbox retains 57,042 files below the old `pre_c16` prefix, while the workstation has reorganized those materials into the current top-level library. A path-independent SHA-256 multiset comparison of every file produced the same digest on both machines: `62f0a546f4979d484fa639429e5c4703510941ae636c6fbae6e7ef09cf394be5`. Therefore the trainbox contains no unique file content requiring recovery; it is a redundant legacy layout, not a second authority.

No library bytes were deleted during reconciliation. The workstation still holds all 244,388 files at the canonical editable location. The old trainbox copy remains untouched until a later, explicit storage-cleanup decision.

## Campaign freeze

Legacy campaign `play-word-evolution-0501-2000-v1` (campaign 33) is stored in Mission Hub as `legacy_stopped`. Its legacy status was `waiting`. The migration metadata names `plan-campaign-play-word-evolution-0501-2000-v1-b0068` as the stale boundary and sets `resumption_allowed=false`.

Decision `decision-legacy-freeze-play-word-evolution-0501-2000-v1` is executed and linked to evidence source `evidence-3e376250adbd03e7`. This is a safety/migration decision only; it does not close, rewrite, or resume the old files.

## Deployment evidence

All builds remain candidates. None is active and no service was installed or started.

The first trainbox candidate `dep-e12eb6df7cc4f77f` was rejected because its environment facts were collected on the workstation. The correction requires target-host attestation. The trainbox Cortex runtime is now explicitly recorded as:

- invoked interpreter: `/home/aomukai/.venvs/ninereeds-cortex/bin/python`;
- resolved interpreter: uv CPython 3.13.12;
- external site path: `/home/aomukai/.unsloth/studio/unsloth_studio/lib/python3.13/site-packages`;
- Torch 2.10.0+cu130;
- Transformers 5.2.0;
- jsonschema 4.26.0;
- safetensors 0.8.0.

The interpreter binary hash and complete attestation are stored in the replacement deployment manifest when registered.

Current corrected candidates:

| Role | Deployment | Release | Source SHA-256 | Environment SHA-256 | Archive SHA-256 | Files | Active? |
|---|---|---|---|---|---|---:|---|
| Mission Hub | `dep-4058606d5a187fdb` | `release-03f86f0f9bab-a33aba33dc60` | `03f86f0f9bab83c9557b4ef6bd71714b396fcf895be8bf1345311db0dfa89605` | `a33aba33dc60230e226eb19e544fef8deba294f44bdf6e311b96a08fe21739cf` | `665b21ff69a4113aa1d58a26cc0f366a1f10cb5e3b10139c2c2ebc6f1ef1b802` | 73 | no; dirty candidate |
| Trainbox agent | `dep-50bf8c67e69ae000` | `release-acd641fdd5dc-a2724fbf9a9a` | `acd641fdd5dc076bf974fcba89e0cb9413b5af90b3fc3aeaeda3c05d3084eb7a` | `a2724fbf9a9aa9f208cea30249d5304c02b44f26b2de2fa30892544b4911ee59` | `4123c1df57bdef0e0dd0130c67bed36de94a7c468e30a0d154e3011d54eff242` | 77 | no; dirty candidate |

Earlier candidates `dep-10ffd6ec4e2f9e99`, `dep-d3257022f8714f3c`, `dep-e12eb6df7cc4f77f`, and `dep-24537d91f3e9ffbe` are rejected with durable reasons. Candidate archives live outside the repository under `~/.local/share/ninereeds/mission-hub/releases/candidates`.

The exact trainbox candidate archive was transferred to an isolated, non-current release directory and passed:

- agent `ping` with deployment/config hash agreement and SHA-256 verification of all 77 allowlisted release files;
- one manually constructed, hash-validated `system.healthcheck` envelope;
- target observation of both RTX 3060 GPUs idle with 1 MiB reported usage each;
- result-envelope generation without echoing the lease token.

This was a stateless candidate-package test. It did not activate the deployment, create/complete an authoritative Mission Hub job, install a forced SSH key, or enable any service, so the durable commissioning-healthcheck gate correctly remains unmet.

## Remaining preservation gate

The checkpoint tree currently has metadata hashes, not content hashes. Before any lineage can be resumed or protected in the new artifact registry, the selected parent, current candidate, evaluation suite, and corpus shards must be content-hashed on the trainbox and registered with exact locations and manifests.
