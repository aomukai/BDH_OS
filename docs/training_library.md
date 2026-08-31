# Training library contract

## Canonical location

`/home/aomukai/Ninereeds/training_data` on the Mission Hub workstation is Ninereeds' canonical, living training-material library. It remains directly accessible to the operator and may be expanded or reorganized over time.

The library is not generated build output or an immutable artifact. Git ignores
its contents so that normal authoring does not produce tens of thousands of
repository changes, with one deliberate exception:
`training_data/v8_curriculum/` is version-controlled and is the sole valid
lesson curriculum. Older lesson trees, campaign lesson payloads, generated
renders, and handoff copies are not curriculum sources. Role-release manifests
still exclude the operator library unless a release explicitly declares a
content-hashed training artifact.

## Data flow

1. The operator creates or curates lesson material in
   `training_data/v8_curriculum/`; other operator-library material may live
   elsewhere under `training_data/`.
2. Mission Hub catalogs the library and records the exact selected paths and content hashes for a corpus build.
3. A deterministic corpus job produces one or more immutable, content-hashed training shards in the Mission Hub artifact store.
4. Mission Hub registers the shard metadata and lineage.
5. Only shards explicitly referenced by an approved job are copied to the trainbox artifact cache.
6. The trainbox verifies hashes before execution and treats its copy as a disposable cache, never as the canonical library.

This design preserves convenient human access while making every training run reproducible. Editing a library file cannot silently change the input of an already-created job because that job names an immutable shard hash.

## Reconciliation result

The pre-rebuild Git index contained 244,365 `training_data` paths and the trainbox held a historical full copy. Reconciliation removed those paths from source control without deleting the workstation bytes. The two physical libraries were then compared as complete content multisets: all 244,388 files matched the same aggregate digest. The redundant trainbox copy was removed after verification; the workstation directory remains canonical. See `physical_cleanup_2026-08-06.md` for the preservation and cleanup record.

## Current lesson authority

The v8 curriculum contains 200 ordered language lessons under `language/`, an
education scope under `education/`, and local build/validation tools under
`tools/`. Validate it with:

```bash
python3 training_data/v8_curriculum/tools/validate_vocab_blocks.py
```

Code that selects lesson inputs must fail closed if asked to read another
curriculum location.
