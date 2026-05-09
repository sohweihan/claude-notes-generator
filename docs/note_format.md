# Note Format

## Detailed Notes

Frontmatter:

```yaml
---
status: complete
module: {module_name}
lecture: {lecture_label}
source_pdf: {pdf_filename}
source_sha256: {source_sha256}
source_modified_utc: {source_modified_utc}
page_count: {page_count}
note_type: detailed
generated_by: claude
---
```

Body requirements:
- exact heading pattern `## Slide N: Title`
- one slide section for every page
- rendered asset image embed for every slide
- explanatory teaching prose, not transcript fragments or slide paraphrase
- important ideas should include their practical meaning, decision relevance, or real-world implication when relevant
- formulas must explain variables, intuition, use, and practical meaning when relevant
- formula-heavy slides should include a compact worked numerical example using simple concrete numbers (e.g., 2 assets) that demonstrates the calculation end-to-end; use a consistent setup throughout the lecture so successive examples chain together
- charts and tables must explain what conclusion the student should draw and why it matters
- question and scenario slides must not remain bare prompts in the notes
- if a question is resolved on the current slide or in the next 1-3 slides, give either a short answer now or a brief signpost such as `Developed in the next 2 slides`
- when later slides provide the answer, explicitly close the loop and explain the thought process step by step
- when useful, identify the key clue, the inference that follows, and a tempting wrong answer or trap

## Summaries

Frontmatter:

```yaml
---
status: complete
module: {module_name}
lecture: {lecture_label}
source_pdf: {pdf_filename}
source_sha256: {source_sha256}
source_modified_utc: {source_modified_utc}
page_count: {page_count}
note_type: summary
generated_by: claude
---
```

Required sections (use these exact heading strings — do not substitute alternatives like `## Core Themes` or `## Summary`):
- `## Overview` — 2-4 sentences describing what the lecture covers and why it matters
- `## Key Concepts` — concise explanations of the main ideas
- `## Important Terms` — 8-12 terms with one-line definitions
- `## Key Takeaways` — 5-8 bullet points; the most important things to remember
- `## Review Questions` — at least 5 questions, each with an inline answer

Rules:
- every concept and important term should link to a detailed-note heading when possible
- review questions must be on a single line in the format: `N. Question text — **Answer:** Answer text`
- do not restate the whole lecture slide by slide

## Audit Metadata

Do not hand-author audit metadata unless necessary. Prefer updating it through `python record_audit.py`.

Expected audit fields:

```yaml
audit_status: preliminary_clear | audited | flagged | repaired
last_audited_utc: 2026-04-29T12:00:00Z
last_audit_mode: auto | light | strict
last_audit_action: preliminary | flag-only | repair
last_audited_against_sha256: <PDF hash>
```

## Obsidian Rendering Rules

These rules apply to all note content written for Obsidian (KaTeX math renderer, CommonMark markdown).

**Math blocks (`$...$` display math)**
- Always leave a blank line before and after every `$...$` block.
- Always leave a blank line between two consecutive `$...$` blocks.
- Violating either rule causes Obsidian to silently fail rendering from that point onwards in the note.

**Inline math fractions**
- Use `\frac` inside inline `$...$` math, not `\dfrac`.
- `\dfrac` forces display size even in inline context, producing oversized fractions.

**Percent sign in math**
- Always write `\%` inside any math environment (`$...$` or `$...$`).
- An unescaped `%` is a KaTeX comment character; everything after it on the same line is silently dropped.

**Lists and tables**
- Always leave a blank line before a list (`-`) or table (`|`) when the preceding line is ordinary prose.
- Omitting the blank line causes Obsidian to parse the block as continuation text, not a list or table.

**Callouts with internal blank lines**
- Inside an Obsidian callout (`> [!type] Title`), represent blank lines as `>` on an otherwise-empty line.
- A truly empty line closes the callout block.

## Paper Notes

Paper notes cover research papers, working papers, and any non-lecture PDFs. They live alongside module lectures (in a module's `Notes/` subfolder) or in a standalone `Research Papers/` collection at the vault root.

**Source PDFs** go in a `_papers/` directory — either `Research Papers/_papers/` or `{Module}/_papers/`.

**Frontmatter:**

```yaml
---
status: complete
note_type: paper
collection: {collection_name}
paper_label: {pdf_stem}
source_pdf: {pdf_filename}
source_sha256: {source_sha256}
source_modified_utc: {source_modified_utc}
page_count: {page_count}
generated_by: claude
---
```

**Note filename** is derived from the paper's actual title (extracted from PDF metadata or the largest text on page 1), not the source filename. If title extraction fails, the PDF stem is used as fallback.

**Required sections** (use these exact heading strings):
- `## Citation` — full citation: authors, year, title, journal/venue, DOI if available
- `## Abstract` — the paper's own abstract or a faithful one-paragraph paraphrase
- `## Motivation` — the research question and why it matters; what gap it fills
- `## Methodology` — data, empirical strategy, model, or theoretical framework used
- `## Key Findings` — main results; include key numbers, magnitudes, and statistical qualifications where they matter
- `## Implications` — practical takeaways, limitations, and how the findings connect to other work in the vault
- `## Critical Evaluation` — see below

**`## Critical Evaluation` format:**

This section is a structured professional assessment. It should cover four points in order:

1. **Contribution** — what this paper adds over prior work; whether the contribution is incremental or substantial
2. **Robustness** — quality of the evidence: sample size, out-of-sample testing, multiple-comparison concerns, robustness checks, data-mining risk
3. **Replication feasibility** *(include only when the paper tests an implementable strategy or quantitative model)* — data requirements and availability; estimated implementation complexity; transaction cost sensitivity; capacity constraints; whether the strategy has been shown to hold out-of-sample or in live trading
4. **Verdict** — a concise bottom-line assessment: whether the findings are credible and, where applicable, whether the strategy is worth attempting to implement given the evidence presented

The Replication feasibility point is conditional: skip it for purely theoretical or non-implementable papers. For empirical papers that test tradeable signals, factor exposures, or portfolio construction methods, this is the most important point in the section.

Write the evaluation as a professional practitioner would — evidence-based, specific about what the paper actually shows, and honest about gaps.

**Body rules:**
- Each section must have substantive content — not just a restatement of the heading
- For quantitative papers: `## Key Findings` should include at least one worked numerical result or key statistic
- `## Implications` should cross-link to relevant lecture notes in the vault where the same concept appears
- Embed page images for figures and tables that are important to the argument (same `assets/` convention as lecture notes)

**Paper summary** uses the same 5-section format as lecture summaries (`## Overview`, `## Key Concepts`, `## Important Terms`, `## Key Takeaways`, `## Review Questions`) but the `## Overview` should name the paper and state the central contribution in 2-3 sentences.

**Reading List** (`{collection}/Reading List.md`) serves the same role as `Module TOC.md` for a lecture module: a scannable roadmap of what papers are in the collection, their topic, and why they are included.

## Module TOC

Purpose:
- act as a study roadmap for the module, not just a file index

Required elements:
- module title
- quick links to `Concept Index`, `Detailed Notes`, and `Summaries`
- one entry per lecture in module order
- for completed lectures: a short `Focus` line, 2-3 concrete `Learning outcomes`, and links to the lecture's detailed notes and summary
- for incomplete lectures: a clear pending marker rather than fake content

Style rules:
- optimise for scanability over dense tables
- learning outcomes should tell the student what they should be able to explain, distinguish, derive, interpret, or apply after the lecture
- avoid generic lines like "understand the lecture" or redundant file-registry prose