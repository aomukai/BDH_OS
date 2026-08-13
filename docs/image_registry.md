# Ninereeds image registry

The registry separates corpus preparation from training. Large immutable bytes live on the
external corpus drive; the SQLite index lives in `training_data/image_registry` on ext4.
This avoids SQLite locking and durability problems on the external exFAT filesystem.

Default locations:

- index: `training_data/image_registry/registry.sqlite3`
- large store: `/media/aomukai/FILES/Ninereeds/image-corpus`
- portable ledgers: `<large store>/exports/*.jsonl`

The registry preserves source IDs, landing pages, authors, licenses, source checksums,
object boxes, relationships, image-level labels, local content hashes, selections, and
append-only text/review records. `text_search` is an FTS5 index, so source terms and later
human/model captions can be searched without scanning image files.

Initial Open Images workflow:

```bash
python3 -m image_registry import-open-images \
  /media/aomukai/FILES/Ninereeds/image-corpus/sources/open_images_v7/validation
python3 -m image_registry select benchmark-100 --size 100 --seed 3501
python3 -m image_registry download benchmark-100
python3 -m image_registry export benchmark-100 \
  /media/aomukai/FILES/Ninereeds/image-corpus/exports/benchmark-100.jsonl
```

Create the production selection by excluding the permanent benchmark, then use bounded
parallel downloading. The official S3 validation JPEG is normalized and therefore does
not share the metadata MD5 of the original Flickr file; the registry records SHA-256 of
the exact downloaded bytes instead.

```bash
python3 -m image_registry select-production open-images-v7-validation-production-v1 \
  --source open_images_v7 --exclude-selection benchmark-100
python3 -m image_registry download open-images-v7-validation-production-v1 \
  --workers 16 --retries 3
```

Mission Hub's surviving FLUX candidates are imported as a distinct source after all
trainbox-only artifacts have been retrieved through Mission Hub. Their generation prompt,
seed, item ID, exact model revision, and artifact identity remain attached as searchable
provenance. Existing inspection and independent final-review records are also imported.
The importer creates `-accepted` and `-pending` selections; known-unusable images appear
only in the complete provenance selection and are never re-reviewed or admitted.

```bash
python3 -m image_registry import-flux-artifacts \
  /home/aomukai/.local/share/ninereeds/mission-hub/mission-hub.sqlite3 \
  --selection flux-candidates-v1
python3 -m image_registry filter-mechanical \
  open-images-v7-validation-production-v1 open-images-v7-validation-review-ready-v1
python3 -m image_registry filter-mechanical \
  flux-candidates-v1-pending flux-candidates-v1-pending-review-ready-v1
python3 -m image_registry combine visual-corpus-review-v1 \
  open-images-v7-validation-review-ready-v1 flux-candidates-v1-pending-review-ready-v1
```

Mechanical validation and review sheets use the isolated vision-capable environment:

```bash
/home/aomukai/.venvs/ninereeds-cortex/bin/python -m image_registry \
  inspect benchmark-candidates-200
/home/aomukai/.venvs/ninereeds-cortex/bin/python -m image_registry \
  derive benchmark-candidates-200 benchmark-100 --size 100
/home/aomukai/.venvs/ninereeds-cortex/bin/python -m image_registry \
  contact-sheets benchmark-100 \
  /media/aomukai/FILES/Ninereeds/image-corpus/work/benchmark-100-sheets
```

Selections are deterministic and stratified across relationship-rich images, countable
objects, and diverse ordinary scenes. They are candidate pools, not evaluation truth.
Benchmark gold labels must be established by human inspection before model scoring.

Search terms or later reviewed captions with FTS5 syntax:

```bash
python3 -m image_registry search 'Dog AND under'
```

## Sol visual-material tool

Sol can fulfil a bounded teaching-material request directly from assets whose canonical
registry status is `reviewed_usable`. The request supplies ordered exact, semantic-
equivalent, and alternate-realization queries, protected selections to exclude, the
teaching claim, intended partition, and acceptance criteria.

```bash
python3 -m image_registry.material_tool \
  mission_hub/research/examples/visual-material-request-example.json \
  --selection lesson-under-candidates-v1 \
  --output /tmp/lesson-under-candidates-v1.json
```

The command creates a new immutable registry selection and a manifest containing exact
paths and SHA-256 hashes. It never selects `mechanically_valid`, pending, unresolved,
or `reviewed_unusable` assets.

If the registry cannot satisfy the requested quantity, the manifest preserves partial
matches and emits a residual-gap request. That request can propose external acquisition,
a minimal Flux edit, or custom generation in the declared fallback order, but it does
not dispatch any provider. New material must pass review and re-enter the registry
before Sol reruns retrieval.

Concurrent model review uses the leased registry queue described in
`docs/image_review_queue.md`. The queue owns work state and results; exported filename
and result JSONL files are portable projections, not competing ledgers.
