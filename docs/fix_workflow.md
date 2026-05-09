# Fix Workflow

Use this workflow for `fix the vault` and `/fix-module`.

## Intent

`fix ...` is primarily for safe mechanical repair, not for broad lecture rewrites.

## Required First Step

Run `python validate.py` first.

## Safe Mechanical Fixes

Allowed:
- missing slide manifests
- missing lecture digests
- missing `Module TOC.md`
- missing `TOC.md` rows
- missing `Concept Index.md`
- stale `.partial.md` situations
- canonical path mismatches
- asset-reference mismatches

Not the default:
- broad rewriting of complete lecture content
- deep teaching-quality review
- strict asset-by-asset formula verification

Escalate those to `audit ...` instead.
