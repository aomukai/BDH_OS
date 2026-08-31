# Ninereeds v8 curriculum

This directory is the sole authoritative lesson curriculum in the repository.
Lesson data, generated renders, handoff copies, and campaign payloads elsewhere
must not be used as curriculum input.

## Contents

- `language/L001.md` through `language/L200.md`: the ordered language lessons;
- `education/education.md`: the education and visual-material scope;
- `tools/build_vocab_blocks.py`: the local vocabulary-block builder;
- `tools/validate_vocab_blocks.py`: the strict structural validator.

The tools resolve paths relative to this directory and have no dependency on
an earlier curriculum version.

## Validation

Run from the repository root:

```bash
python3 training_data/v8_curriculum/tools/validate_vocab_blocks.py
```
