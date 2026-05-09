---
description: Audit one lecture for correctness and depth, optionally repairing it
argument-hint: --module "CS101 - Computer Networks" --lecture "Lecture 01" --mode auto --action repair
---
Follow @docs/audit_workflow.md and @docs/note_format.md.

Treat the arguments below as the exact scope tail for the audit request:

`$ARGUMENTS`

If no `--mode` is provided, default to `auto`.

Your task:
1. Run `python validate.py` with the matching module and lecture scope first.
2. Audit only the requested lecture.
3. Read the lecture digest first, then the full manifest, then slide assets as required by the selected review mode.
4. If the action is `repair`, correct only the scoped notes.
5. Record the audit outcome with `python record_audit.py`.
6. Report mechanical issues separately from teaching-content issues.