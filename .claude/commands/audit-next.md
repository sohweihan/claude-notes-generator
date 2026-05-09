---
description: Audit the next completed lecture that still needs review or repair
argument-hint: --module "CS101 - Computer Networks" --mode auto --action repair
---
Follow @docs/audit_workflow.md and @docs/note_format.md.

Treat the arguments below as the exact scope tail for the validation and audit request:

`$ARGUMENTS`

If no `--mode` is provided, default to `auto`.

Your task:
1. Run `python validate.py $ARGUMENTS` first.
2. From the returned lectures, choose only the first completed lecture that most clearly needs audit attention.
3. Use this priority order when selecting that lecture:
   - `status: issues`
   - `status: review`
   - `audit_status` missing, `preliminary_clear`, or `flagged`
   - otherwise, the first completed lecture in scope not yet audited or repaired against the current source PDF
4. Skip lectures that are still pending generation; those belong to `process` workflows.
5. Audit only the selected lecture.
6. Read the lecture digest first, then the full manifest, then slide assets as required by the selected review mode.
7. If the action is `repair`, correct only the selected lecture's notes.
8. Record the audit outcome with `python record_audit.py`.
9. Report which lecture was selected, why it was selected, what changed, and whether more audit candidates remain in scope.