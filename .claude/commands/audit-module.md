---
description: Audit one module for content correctness and teaching depth
argument-hint: --module "CS101 - Computer Networks" --mode auto --action flag-only
---
Follow @docs/audit_workflow.md and @docs/note_format.md.

Treat the arguments below as the exact scope tail for the audit request:

`$ARGUMENTS`

If no `--mode` is provided, default to `auto`.

Your task:
1. Run `python validate.py` with the matching module scope first.
2. Audit only the requested module.
3. Use the selected review mode to decide how many slide assets to inspect.
4. If the action is `repair`, update only the scoped module files.
5. Record each lecture audit outcome with `python record_audit.py`.
6. Report structural, correctness, and depth issues clearly.