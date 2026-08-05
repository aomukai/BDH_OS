# Training library contract

## Canonical location

`/home/aomukai/Ninereeds/training_data` on the Mission Hub workstation is Ninereeds' canonical, living training-material library. It remains directly accessible to the operator and may be expanded or reorganized over time.

The library is not obsolete, generated build output, an immutable artifact, or part of an application source release. Git ignores its contents so that normal authoring does not produce tens of thousands of repository changes. Role-release manifests also exclude it. These exclusions affect transport and version-control ownership only; they do not remove or relocate files.

## Data flow

1. The operator creates or curates material in `training_data/`.
2. Mission Hub catalogs the library and records the exact selected paths and content hashes for a corpus build.
3. A deterministic corpus job produces one or more immutable, content-hashed training shards in the Mission Hub artifact store.
4. Mission Hub registers the shard metadata and lineage.
5. Only shards explicitly referenced by an approved job are copied to the trainbox artifact cache.
6. The trainbox verifies hashes before execution and treats its copy as a disposable cache, never as the canonical library.

This design preserves convenient human access while making every training run reproducible. Editing a library file cannot silently change the input of an already-created job because that job names an immutable shard hash.

## Reconciliation rule

The pre-rebuild Git index contains 244,365 `training_data` paths and the trainbox holds a historical full copy. During reconciliation those paths are removed from source control without deleting working-tree bytes. The workstation directory remains canonical; the trainbox copy is retained as legacy evidence until its content has been compared and any unique material has been recovered.
