# Review Workflow

Use this workflow for `review workflow`.

Review:
- `CLAUDE.md`
- `README.md`
- `docs/`
- `.claude/commands/`
- `.claude/agents/`
- `.claude/settings.json`
- `extract.py`
- `validate.py`
- `record_audit.py`
- vault folder structure

Focus on:
- redundant commands or overlapping workflows
- token-heavy always-on instructions
- weak separation between generation, repair, audit, and workflow review
- missing guardrails around formulas, OCR, embeds, partial files, and logs
- places where the workflow encourages broad context when a narrow scope would do

Report:
- findings ordered by impact
- open questions or assumptions
- recommended changes with the smallest operational cost first
