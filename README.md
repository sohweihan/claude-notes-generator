# Obsidian + Claude Code Lecture Vault

This repository turns lecture slide PDFs into structured Obsidian notes with Claude Code.

The workflow is designed for:
- high-quality teaching notes
- scoped, repeatable generation and audit flows
- lower token waste through narrow commands, digests, and targeted image review

## How It Works

```text
You add lecture PDFs to module _inbox/
            |
            v
      extract.py scans scope
            |
            +--> normalizes filenames
            +--> builds slide manifest
            +--> builds compact lecture digest
            +--> renders slide assets
            +--> returns resumable work items
            |
            v
Claude Code reads digest first, manifest second, assets only when needed
            |
            +--> writes Detailed Notes / Summary via .partial.md
            +--> runs a preliminary audit before finalizing
            +--> records audit metadata + central audit history
            +--> updates TOCs / concept indexes only when needed
```

## Main Ideas

- `process lecture` is the primary generation command.
- `process module` is for controlled batch work.
- `process the inbox` is only a convenience path for “next pending lecture”.
- `validate` is non-mutating.
- `fix` is mainly for safe mechanical repair.
- `audit` is for content correctness/depth review, optionally with repair.
- `audit next` is the convenience path for the next completed lecture that still needs review or upgrade.
- `review workflow` is for reviewing the vault system itself.

## Requirements

Install Python dependencies:

```bash
pip install pymupdf
```

Install Claude Code:

```bash
npm install -g @anthropic-ai/claude-code
```

Then sign in:

```bash
claude
```

## Vault Layout

```text
Vault/
|-- CLAUDE.md
|-- README.md
|-- extract.py
|-- validate.py
|-- record_audit.py
|-- migrate_pdf_embeds_to_assets.py
|-- docs/
|-- .claude/
|   |-- commands/
|   |-- agents/
|   |-- hooks/
|   `-- settings.json
|
`-- CS101 - Computer Networks/
    |-- _inbox/
    |-- Detailed Notes/
    |   `-- assets/
    |-- Summaries/
    |-- Module TOC.md
    `-- Concept Index.md
```

`_inbox/` is the long-term source registry. Keep the canonical lecture PDFs there after generation so validation and source-fingerprint checks continue to work.

## Source PDF Naming

Canonical naming:

```text
{ModuleCode}_L{NN}.pdf
```

Examples:
- `CS101_L01.pdf`
- `CS101_L07.pdf`

The extractor can normalize common uploader names such as:
- `CS101 Lecture 1.pdf`
- `CS101 Week1.pdf`
- `Intro to Routing week one.pdf`

If two PDFs collapse to the same canonical lecture, the extractor reports a conflict instead of guessing.

## Runtime Files

### `CLAUDE.md`

This is the short runtime contract Claude Code reads automatically. It contains:
- command intent
- non-negotiable vault rules
- digest/manifest/image reading order
- preliminary audit requirement
- audit-tracking rules

### `docs/`

These files hold the longer workflow instructions:
- `docs/process_workflow.md`
- `docs/audit_workflow.md`
- `docs/fix_workflow.md`
- `docs/note_format.md`
- `docs/review_workflow.md`

### `.claude/commands/`

Project slash commands:
- `/process-next`
- `/process-lecture`
- `/process-module`
- `/audit-lecture`
- `/audit-module`
- `/audit-next`
- `/fix-module`
- `/validate-scope`
- `/review-workflow`

### `.claude/agents/`

Project subagents:
- `note-generator`
- `vault-auditor`
- `mechanical-fixer`
- `formula-checker`

### `.claude/settings.json`

Project hooks. The included hook checks note writes for:
- missing final frontmatter markers
- wrong note type
- PDF page embeds inside detailed notes

## Recommended Usage

Open a terminal in the vault root and start Claude Code:

```bash
claude
```

### Best default path

Use a narrow scoped command whenever you know the target:

```text
process lecture: CS101 Lecture 01
```

Or the project slash command:

```text
/process-lecture --module "CS101 - Computer Networks" --lecture "Lecture 01"
```

### Batch within one module

```text
process module: CS101 - Computer Networks
```

Or:

```text
/process-module --module "CS101 - Computer Networks"
```

### Next pending lecture only

```text
process the inbox
```

Or:

```text
/process-next
```

### Validate without changing files

```text
validate the vault
```

Or:

```text
/validate-scope --module "CS101 - Computer Networks" --lecture "Lecture 01"
```

### Next lecture to audit or repair

```text
audit the next lecture
```

Or:

```text
/audit-next --module "CS101 - Computer Networks" --mode auto --action repair
```

Use this when notes already exist and you want Claude to upgrade one lecture at a time without naming it explicitly. Pending lectures should still go through `process` workflows.

### Mechanical repair

```text
fix the vault
```

Or:

```text
/fix-module --module "CS101 - Computer Networks"
```

### Content review and correction

Auto audit (default):

```text
audit lecture: CS101 Lecture 01
asset review: auto
action: flag-only
```

Strict repair audit:

```text
audit lecture: CS101 Lecture 01
asset review: strict
action: repair
```

Or the slash command:

```text
/audit-lecture --module "CS101 - Computer Networks" --lecture "Lecture 01" --mode auto --action repair
```

### Workflow/system review

```text
review workflow
```

Or:

```text
/review-workflow
```

## What `process ...` Does

`process ...` is generation plus a built-in preliminary audit.

For the scoped work item, Claude should:
1. Run `extract.py`.
2. Read `digest_path` first.
3. Read `manifest_path` second.
4. Inspect slide assets only when needed.
5. Write `.partial.md` drafts.
6. Run a preliminary audit before promoting the note.
7. Finalize the note only after the preliminary audit clears.
8. Record the preliminary audit with `record_audit.py`.

The preliminary audit checks:
- every slide is covered
- formulas/charts/tables were checked against assets when needed
- obvious OCR corruption was not copied through
- summary links point to real detailed-note headings
- dense slides are not explained too shallowly

## Validation

Run full validation:

```bash
python validate.py
```

Scoped validation:

```bash
python validate.py --module "CS101 - Computer Networks" --lecture "Lecture 01"
```

Mechanical-only scoped validation:

```bash
python validate.py --module "CS101 - Computer Networks" --lecture "Lecture 01" --no-teaching-audit
```

Validation checks:
- note completeness
- frontmatter consistency
- source PDF presence
- manifests and digests
- wiki links
- TOCs and concept indexes
- heuristic teaching-content flags

## Audit Tracking

Audit metadata is written to notes through:

```bash
python record_audit.py --module "CS101 - Computer Networks" --lecture "Lecture 01" --status audited --mode auto --action flag-only
```

This updates note frontmatter and appends a line to:

```text
reports/audit_history.jsonl
```

Expected frontmatter audit fields:
- `audit_status`
- `last_audited_utc`
- `last_audit_mode` (`auto`, `light`, or `strict`)
- `last_audit_action`
- `last_audited_against_sha256`

## Cross-Module Navigation

The vault supports three levels of navigation:

1. **`TOC.md`** (vault root) — learning map describing each module, its prerequisites, and the strongest cross-module conceptual connections.
2. **`Vault Concept Index.md`** (vault root) — cross-module concept index linking the same idea across different modules under its various names (e.g. error maximiser / bias-variance tradeoff, IC / Spearman IC, Ledoit-Wolf / Ridge regularisation).
3. **Module `Concept Index.md`** (per module) — within-module concept index with cross-module pointers for identical concepts.

When generating or auditing notes, check `Vault Concept Index.md` before writing the Related Notes block to ensure known cross-module overlaps are linked.

## Migration Script

For older detailed notes that still use PDF page embeds:

```bash
python migrate_pdf_embeds_to_assets.py
```

This renders missing PNGs and rewrites embeds to `assets/` images atomically.

## Environment Variables

Optional settings:

```bash
MAX_FILES_PER_RUN=1
RENDER_MODE=all
VISUAL_REVIEW_WORD_THRESHOLD=40
SLIDE_RENDER_ZOOM=1.5
EXTRACT_LOCK_STALE_HOURS=12
```

## Practical Advice

- Prefer `process lecture` over `process the inbox` when you already know the target.
- Prefer `audit lecture` over broad audits when you only care about one suspected issue.
- Use `audit the next lecture` or `/audit-next` when you want one-at-a-time repair of existing notes without specifying the lecture.
- Prefer `auto` when you do not want to think about review depth; it is now the default and adapts slide-by-slide.
- Use `strict` only when you want image-backed verification of every slide in scope.
- Keep the vault root as Claude Code's working directory so the project hooks and slash commands resolve cleanly.

## Troubleshooting
| Problem | Fix |
|---------|-----|
| `ModuleNotFoundError: fitz` | `pip install pymupdf` |
| A lecture PDF is not renamed | Include an explicit lecture marker like `Lecture 3`, `Week 3`, `wk03`, or canonical `L03` |
| Multiple PDFs map to the same lecture | Delete or rename the duplicate source before processing |
| Formula, matrix, or symbol looks wrong in the notes | Run `audit lecture` with `asset review: strict` and `action: repair` |
| Detailed notes still contain PDF embeds | Run `python migrate_pdf_embeds_to_assets.py` |
| A final note is missing frontmatter or uses a PDF page embed | The project hook should flag it after write; fix the note and re-run validation |
| `.extract.lock` blocks a new run | Retry once; stale locks are cleaned automatically when the prior process is gone or older than `EXTRACT_LOCK_STALE_HOURS` |
| Claude Code command files are not visible | Make sure you are running Claude Code from the vault root so `.claude/commands/` is in scope |
| Math formula or content after it stops rendering | Missing blank line before/after a `$...$` display block, or between two consecutive blocks — add blank lines around every `$...$` |
| Part of a formula text is silently hidden | Unescaped `%` inside math acts as a comment — replace with `\%` |
| Inline fraction renders oversized | `\dfrac` forces display size in inline math — replace with `\frac` |
| List or table not rendering (appears as plain text) | Missing blank line before the list (`-`) or table (`\|`) — add one blank line between prose and the list/table |
