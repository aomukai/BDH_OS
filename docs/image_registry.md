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

Concurrent model review uses the leased registry queue described in
`docs/image_review_queue.md`. The queue owns work state and results; exported filename
and result JSONL files are portable projections, not competing ledgers.
