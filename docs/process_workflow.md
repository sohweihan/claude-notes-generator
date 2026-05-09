# Process Workflow

Use this workflow for `process lecture`, `process module`, and `process the inbox` / `/process-next`.

## Scope

- `process lecture` is the default generation path.
- `process module` is for controlled batch work inside one module.
- `process the inbox` is only a convenience command for "next pending lecture".

## Steps

1. Run `python extract.py` with the narrowest possible scope.
2. Parse the JSON after `__EXTRACT_RESULT__`.
3. Work only on returned `work_items`.
4. For each work item:
   - read `digest_path` first
   - read `manifest_path` second
   - inspect slide assets only when `needs_visual_review` is true, the digest says `has_formula` / `has_table` / `has_chart`, or the extracted text is ambiguous
5. Generate only the files flagged as needed.
6. Write drafts to `detailed_partial_path` and `summary_partial_path` first.
7. Run the preliminary audit before promoting any partial file to its final path.
8. Rename the partial file to its final path only after the preliminary audit clears.
9. Update `Module TOC.md` when a lecture becomes complete or when its roadmap entry is stale.
10. Record the preliminary audit with `python record_audit.py`.

## Preliminary Audit

This is mandatory inside `process ...`, but it is lighter than a full `audit ...`.

Check:
- every slide is covered
- no obvious contradiction with the manifest or inspected assets
- formulas, matrices, charts, and tables were checked against assets when needed
- no malformed OCR fragments were copied through blindly
- math rendering rules are satisfied: blank lines before/after every `$...$` block, blank lines between consecutive blocks, `\frac` not `\dfrac` in inline math, `\%` not `%` inside any math environment, blank line before lists and tables when preceded by prose
- summary links point to real detailed-note headings
- dense slides are not explained at a surface level
- important concepts include practical meaning or decision relevance where warranted
- question and scenario slides are not left as bare prompts
- if a question is resolved on the current slide or within the next 1-3 slides, the notes either answer it now or give a short local signpost
- later slides close the loop and explain the reasoning path clearly

Do not:
- perform a full strict review of every slide by default
- search broadly across the vault
- convert `process ...` into a separate second-pass audit session
- leave `Module TOC.md` as a thin file-list if the lecture summary now supports a clearer roadmap entry
- scan far ahead to resolve question slides unless the lecture structure clearly requires it
- state a confident answer early when the local slide sequence has not established it yet

## Audit Recording

After a successful preliminary audit, run:

```bash
python record_audit.py --module "<Module Name>" --lecture "<Lecture Label>" --status preliminary_clear --mode light --action preliminary
```

Add one or more `--note` arguments only when there is something operationally useful to log.

## Extractor Output Reference

`extract.py` prints a JSON payload after `__EXTRACT_RESULT__`.

Top-level fields:
- `scope`
- `intake_issues`
- `work_items`

Important work item fields:
- `detailed_notes_path`
- `detailed_partial_path`
- `summary_notes_path`
- `summary_partial_path`
- `module_toc_path`
- `root_toc_path`
- `concept_index_path`
- `manifest_path`
- `digest_path`
- `source_sha256`
- `source_modified_utc`
- `detailed_status`
- `summary_status`
- `needs_detailed`
- `needs_summary`
- `needs_manifest`
- `needs_digest`
- `needs_module_toc`
- `needs_root_toc`
- `needs_concept_index`

The workflow is resumable. If a note exists but is incomplete, the extractor returns it for repair instead of skipping it.