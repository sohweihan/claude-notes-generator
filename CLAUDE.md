# Vault Runtime Instructions for Claude Code

This vault contains lecture notes generated from slide decks stored in module `_inbox/` folders.

Use project slash commands when possible:
- `/process-lecture`
- `/process-module`
- `/process-next`
- `/audit-lecture`
- `/audit-module`
- `/audit-next`
- `/fix-module`
- `/validate-scope`
- `/review-workflow`

Natural-language requests that mean the same thing should be mapped to those workflows.

## Workflow Routing

- For generation or regeneration:
  - read `docs/process_workflow.md`
  - read `docs/note_format.md`
- For content audits:
  - read `docs/audit_workflow.md`
  - read `docs/note_format.md`
- For safe mechanical repair:
  - read `docs/fix_workflow.md`
- For reviewing the vault system itself:
  - read `docs/review_workflow.md`

## Command Intent

- `process lecture: ...`
  - primary generation path
  - use when the target lecture is known
- `process module: ...`
  - controlled batch generation within one module
- `process the inbox`
  - convenience command only
  - treat it as "process the next pending lecture"
- `validate the vault`
  - non-mutating validation only
- `fix the vault`
  - primarily for safe mechanical repair
  - do not use it as the default content-rewrite workflow
- `audit lecture: ...`
  - primary correctness/depth review path
  - use when formulas, charts, tables, matrices, OCR, or teaching depth are suspect
- `audit module: ...`
  - broader scoped content review
- `audit the next lecture`
  - convenience path for the next completed lecture in scope that still needs audit attention
  - use when you want lecture-by-lecture repair without naming the lecture explicitly
- `review workflow`
  - review the vault system itself, not lecture content

## Non-Negotiable Rules

- `_inbox/` is the long-term source registry.
- Do not move source PDFs out of `_inbox/` unless the user explicitly changes that policy.
- Never reconstruct output filenames by hand; use the exact paths returned by `extract.py`.
- Detailed notes must embed rendered slide images from `Detailed Notes/assets/`, not PDF page embeds.
- Write note drafts to `.partial.md` first and promote them only after they are complete.
- `Module TOC.md` is a study roadmap, not just a link registry. Keep it readable and update it when completed lectures change what the module now covers.
- For each completed lecture in `Module TOC.md`, include a short focus line and concrete learning outcomes that tell the student what they should understand after the lecture.
- Never overwrite a complete existing note unless the user explicitly asked for regeneration or the note is clearly incomplete.
- If a note is marked incomplete, replace it with a complete version rather than trying to preserve partial fragments.

## Extractor and Reading Order

- Always run `python extract.py` first for `process ...` workflows.
- For returned work items, read:
  1. `digest_path`
  2. `manifest_path`
  3. slide assets only when needed
- Inspect slide assets when:
  - `needs_visual_review` is true
  - the digest says `has_formula`, `has_table`, or `has_chart`
  - the extracted text is sparse, malformed, or ambiguous
  - a user requested `asset review: strict`
- Trust the rendered slide asset over malformed OCR when formulas, matrices, symbols, or notation matter.

## Teaching Standard

- Do not stop at describing or paraphrasing the slide.
- For important concepts, include the "so what" when it materially improves understanding:
  - why it matters in practice
  - what decision it informs
  - how it is used in the real world
  - what limitation, caveat, or common mistake the student should remember
- Keep this grounded and concise.
- Do not add generic practitioner commentary or forced "real-world relevance" to every slide.
- Prefer faithful interpretation over embellishment.

## Question-Style Slides

- Do not leave question or scenario slides as bare prompts in the notes.
- First check whether the current slide or the next 1-3 slides resolve the question.
- If the answer is already clear from the current slide or immediate context, state the short answer and explain the reasoning.
- If the answer is developed in the next 1-3 slides, give a brief interim note here:
  - what the question is really testing
  - the short answer or likely direction, if that is already supported
  - a signpost such as "Developed in the next 2 slides"
- When the later slides provide the explanation, explicitly close the loop and lay out the reasoning step by step.
- Focus on teaching the student how to solve this class of question again:
  - which facts matter most
  - what inference follows from them
  - what tempting wrong answer a beginner might choose, when useful
- If the lecture intentionally leaves the question open, say that clearly and provide the decision framework the student should use.
- Do not invent certainty or unsupported answers.
- Do not scan far ahead by default; keep look-ahead local unless the lecture structure clearly requires more.

## Preliminary Audit Requirement

`process ...` must include a built-in preliminary audit before finalizing notes.

The preliminary audit must confirm:
- every slide is covered
- no obvious contradiction with the manifest or inspected assets
- formulas, matrices, charts, and tables were checked against assets when needed
- malformed OCR fragments were not copied blindly
- math rendering rules are satisfied: blank lines before/after every `$...$` block, blank lines between consecutive blocks, `\frac` not `\dfrac` in inline math, `\%` not `%` inside any math environment, blank line before lists and tables when preceded by prose
- summary links point to real detailed-note headings
- dense slides are not explained at a surface level
- important concepts include practical meaning or decision relevance where warranted
- question and scenario slides are not left as bare prompts; they are either answered, locally signposted, or clearly framed as discussion prompts

Keep this lighter than a full `audit ...`.

## Audit Tracking

Use `python record_audit.py` to update note frontmatter and append to `reports/audit_history.jsonl`.

Expected audit states:
- `preliminary_clear`
- `audited`
- `flagged`
- `repaired`

Do not keep long narrative audit histories inside each note.

## Related Notes

- Prefer earlier lectures in the same module first.
- Expand to other module notes when the overlap is direct and specific: a concept is the same mathematical object, formula, or decision framework appearing under a different name in the other module.
  - Examples that always qualify: OLS/beta (QF623 ↔ QF632), PCA/covariance estimation (QF623 ↔ QF632), Information Coefficient (QF623 ↔ QF632), carry/forward basis (QF623 ↔ QF637), error maximiser/bias-variance tradeoff (QF623 ↔ QF632), Ledoit-Wolf shrinkage/Ridge regularisation (QF623 ↔ QF632).
- Check [[Vault Concept Index]] for known cross-module overlaps before writing the Related Notes block.
- Do not search the whole vault deeply by default; targeted lookups only.

## Completion Reporting

After mutating work, report:
- which files were created
- which files were updated
- which files were skipped
- whether more pending work remains in the requested scope
