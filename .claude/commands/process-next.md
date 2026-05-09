---
description: Process the next pending lecture in the inbox with preliminary audit
---
Follow @docs/process_workflow.md and @docs/note_format.md.

Your task:
1. Run `python extract.py`.
2. If there is a matching work item, process only the first returned lecture.
3. Generate or repair only the artifacts marked as needed.
4. Run the preliminary audit before promoting any `.partial.md` file to its final path.
5. Record the preliminary audit with `python record_audit.py`.
6. Report created, updated, skipped files and whether more pending work remains.
