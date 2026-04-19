# Skill: verify_teacher_output

## Purpose

Mandatory safety skill for any teacher-generated student-facing content.

## Use When

Always use this before accepting:

- corrections
- drill prompts
- contrastive pairs
- emergency-exit generated draft data

## Inputs

- candidate artifact
- relevant accepted corpus context
- verifier policy

## Steps

1. Read the candidate text.
2. Check factual correctness.
3. Check ontology consistency.
4. Check contrast safety.
5. Check curriculum level fit.
6. Check dependency fit.
7. Approve, rewrite, or reject.

## Output

Must produce a structured verifier decision with:

- outcome
- reasons
- rewritten form if needed
- warnings

## Hard Rule

If verification fails, the content does not reach the student or accepted training corpus.
