---
description: Process pending lectures within one module, one work item at a time
argument-hint: --module "CS101 - Computer Networks"
---
Follow @docs/process_workflow.md and @docs/note_format.md.

Treat the arguments below as the exact scope tail for `extract.py`:

`$ARGUMENTS`

Your task:
1. Run `python extract.py $ARGUMENTS`.
2. Process only the returned work items for that module.
3. Respect the extractor's returned ordering and default max-files behavior unless the user explicitly asked for more.
4. Run the built-in preliminary audit before finalizing each note.
5. Record each audit outcome with `python record_audit.py`.
6. Report what was completed and what remains pending in the module.
