---
description: Repair safe mechanical issues within one module without broad content rewrites
argument-hint: --module "CS101 - Computer Networks"
---
Follow @docs/fix_workflow.md and @docs/note_format.md.

Treat the arguments below as the exact scope tail for the fix request:

`$ARGUMENTS`

Your task:
1. Run `python validate.py` for the scoped module first.
2. Fix only safe mechanical issues such as missing manifests, missing digests, TOCs, concept indexes, path mismatches, or stale partial artifacts.
3. Do not perform broad content rewrites unless the user explicitly escalates to an audit repair.
4. Re-run validation for the same scope.
5. Report what was fixed and any remaining content issues that should be audited separately.
