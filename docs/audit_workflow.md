# Audit Workflow

Use this workflow for `audit module`, `audit lecture`, and `audit next`.

## Intent

- `audit lecture` is the preferred path when you suspect a specific formula, matrix, chart, or explanation is wrong.
- `audit module` is for broader scoped review.
- `audit next` is the convenience path for the next completed lecture in scope that still needs audit attention.
- `audit ...` is deeper than the built-in preliminary audit in `process ...`.

## Required First Step

Run `python validate.py` with the narrowest scope first.

Examples:

`auto` is the default review mode when no mode is specified.

```bash
python validate.py --module "CS101 - Computer Networks" --lecture "Lecture 01"
python validate.py --module "CS101 - Computer Networks"
```

## Review Modes

- `auto`
  - default mode
  - read the lecture digest first
  - read the full manifest second
  - inspect slide assets dynamically at the individual-slide level when they are likely to matter
  - inspect a slide asset when any of these are true:
    - `needs_visual_review`
    - `has_formula`
    - `has_table`
    - `has_chart`
    - OCR is sparse, malformed, or ambiguous
    - the slide is a question/scenario slide whose answer depends on visual details
    - the note appears to contradict the slide
  - inspect neighboring slides when needed for local context, usually the previous slide plus the next 1-3 slides
  - escalate toward lecture-wide strictness only when many slides are flagged or the lecture is heavily visual / notation dependent
- `light`
  - read the lecture digest first
  - read the full manifest second
  - inspect only the assets needed to verify correctness
- `strict`
  - inspect every slide asset in scope before approving correctness
  - use this for OCR-sensitive formulas, matrices, notation, charts, and tables

## Actions

- `flag-only`
  - do not rewrite note content
  - report issues clearly with slide references
- `repair`
  - fix only the scoped notes
  - do not spill into other lectures or modules

## Explanation Quality Check

When auditing explanation quality, check not only factual correctness but also whether the notes do the following for material concepts:
- state why the point matters in practice
- connect the idea to decisions, risk, pricing, hedging, modeling, or interpretation when relevant
- surface meaningful caveats, limits, or common mistakes when those are important
- resolve question and scenario slides instead of leaving them as bare prompts when the local slide sequence supports an answer
- keep look-ahead local; by default, use only the current slide and the next 1-3 slides to determine whether the question is answered
- give an interim signpost when the answer is developed shortly afterward, then close the loop in the later explanatory slides
- explain the reasoning path, not just the final label or answer
- identify the key clue, inference, or tempting wrong answer when doing so materially improves learning

Do not force artificial "insights" onto trivial administrative or purely definitional slides.
Do not overstate certainty when the lecture only provides a partial answer or a discussion framework.

## Recording Audits

After the audit:

- if content was clear:

```bash
python record_audit.py --module "<Module Name>" --lecture "<Lecture Label>" --status audited --mode auto --action flag-only
```

- if issues were found without repair:

```bash
python record_audit.py --module "<Module Name>" --lecture "<Lecture Label>" --status flagged --mode strict --action flag-only --note "Formula on slide 17 needs correction"
```

- if the scoped notes were repaired:

```bash
python record_audit.py --module "<Module Name>" --lecture "<Lecture Label>" --status repaired --mode auto --action repair
```