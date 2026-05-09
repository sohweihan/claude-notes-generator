---
description: Generate or repair one lecture with a built-in preliminary audit
argument-hint: --module "CS101 - Computer Networks" --lecture "Lecture 01"
---
Follow @docs/process_workflow.md and @docs/note_format.md.

Treat the arguments below as the exact scope tail for `extract.py`:

`$ARGUMENTS`

Your task:
1. Run `python extract.py $ARGUMENTS`.
2. Process only the matching work item.
3. Generate or repair only the assets and notes marked as needed.
4. Before finalizing, run the preliminary audit defined in the workflow doc.
5. Record the audit result with `python record_audit.py`.
6. Report created, updated, skipped files and whether the scoped lecture still needs follow-up.
