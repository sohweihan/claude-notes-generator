#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from extract import (
    analyze_detailed_note,
    analyze_paper_note,
    analyze_summary_note,
    canonical_pdf_filename,
    count_pdf_pages,
    extract_audit_fields,
    extract_sequence_number,
    file_modified_utc,
    file_sha256,
    find_vault_root,
    matches_lecture_filter,
    matches_module_filter,
    module_code_from_name,
    paper_label_from_stem,
    parse_filename,
    parse_frontmatter,
    resolve_note_path,
    scan_inboxes,
    scan_papers,
    write_json_payload,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate vault note structure and surface teaching-content flags.")
    parser.add_argument("--module", help="Restrict validation to one module name or module code.")
    parser.add_argument("--lecture", help="Restrict validation to one lecture label, number, or combined target string.")
    parser.add_argument("--report-path", help="Optional path to also write the JSON payload.")
    parser.add_argument(
        "--no-teaching-audit",
        action="store_true",
        help="Skip heuristic teaching-content flags and only report mechanical issues.",
    )
    return parser.parse_args(argv)


def strip_frontmatter(text: str) -> str:
    text = text.lstrip("\ufeff")
    if not text.startswith("---\n"):
        return text
    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return text
    return text[end_idx + 5 :]


def validate_links(markdown_path: Path, allowed_missing_stems: set[str]) -> list[str]:
    text = markdown_path.read_text(encoding="utf-8")
    text = strip_frontmatter(text)
    issues: list[str] = []

    for target in re.findall(r"!?\[\[([^\[\]]+?)\]\]", text):
        cleaned = target.split("|", 1)[0].split("#", 1)[0].strip()
        if cleaned.endswith(".pdf"):
            continue

        base_path = (markdown_path.parent / cleaned).resolve()
        candidates = [
            base_path,
            base_path.with_suffix(".md"),
            (markdown_path.parent / "assets" / cleaned).resolve(),
            (markdown_path.parent.parent / cleaned).resolve(),
            (markdown_path.parent.parent / cleaned).resolve().with_suffix(".md"),
        ]
        if Path(cleaned).stem in allowed_missing_stems:
            continue
        if not any(candidate.exists() for candidate in candidates):
            issues.append(f"broken wiki link target: {cleaned}")

    return issues


def note_label_from_path(note_path: Path, suffix: str) -> str:
    marker = f" - {suffix}"
    stem = note_path.stem
    return stem[: -len(marker)] if stem.endswith(marker) else stem


def iter_module_folders(vault_root: Path) -> list[Path]:
    module_folders: list[Path] = []
    for child in sorted(vault_root.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name == "__pycache__":
            continue
        if any((child / folder_name).exists() for folder_name in ("_inbox", "Detailed Notes", "Summaries")):
            module_folders.append(child)
    return module_folders


def expected_manifest_path(module_folder: Path, source_pdf: str | None) -> Path | None:
    if not source_pdf:
        return None
    prefix = re.sub(r"[^\w]", "_", Path(source_pdf).stem)
    return module_folder / "Detailed Notes" / "assets" / f"{prefix}_slide_manifest.json"


def expected_digest_path(module_folder: Path, source_pdf: str | None) -> Path | None:
    if not source_pdf:
        return None
    prefix = re.sub(r"[^\w]", "_", Path(source_pdf).stem)
    return module_folder / "Detailed Notes" / "assets" / f"{prefix}_lecture_digest.json"


def discover_lectures(vault_root: Path, inbox_files: list[Path]) -> list[dict[str, object]]:
    records: dict[tuple[str, str], dict[str, object]] = {}

    def get_record(module_folder: Path, lecture_label: str) -> dict[str, object]:
        key = (module_folder.name, lecture_label)
        record = records.get(key)
        if record is None:
            record = {
                "module_folder": module_folder,
                "module_name": module_folder.name,
                "lecture_label": lecture_label,
                "candidate_labels": [lecture_label],
                "pdf_path": None,
                "source_pdf": None,
                "detailed_path": None,
                "summary_path": None,
            }
            records[key] = record
        return record

    for inbox_file in inbox_files:
        module_folder = inbox_file.parent.parent
        _, lecture_label, candidate_labels = parse_filename(inbox_file.name)
        record = get_record(module_folder, lecture_label)
        record["candidate_labels"] = candidate_labels
        record["pdf_path"] = inbox_file
        record["source_pdf"] = inbox_file.name

    for module_folder in iter_module_folders(vault_root):
        detailed_folder = module_folder / "Detailed Notes"
        summaries_folder = module_folder / "Summaries"

        for detailed_path in sorted(detailed_folder.glob("* - Detailed Notes.md")):
            metadata = parse_frontmatter(detailed_path.read_text(encoding="utf-8"))
            source_pdf = metadata.get("source_pdf")
            lecture_label = metadata.get("lecture") or note_label_from_path(detailed_path, "Detailed Notes")
            if source_pdf:
                _, parsed_label, parsed_candidates = parse_filename(source_pdf)
                lecture_label = parsed_label
                candidate_labels = parsed_candidates
            else:
                seq = extract_sequence_number(lecture_label)
                if seq is not None:
                    lecture_label = canonical_lecture_label(seq)
                candidate_labels = [lecture_label]

            record = get_record(module_folder, lecture_label)
            record["candidate_labels"] = candidate_labels
            record["detailed_path"] = detailed_path
            if source_pdf and not record.get("source_pdf"):
                record["source_pdf"] = source_pdf

        for summary_path in sorted(summaries_folder.glob("* - Summary.md")):
            metadata = parse_frontmatter(summary_path.read_text(encoding="utf-8"))
            source_pdf = metadata.get("source_pdf")
            lecture_label = metadata.get("lecture") or note_label_from_path(summary_path, "Summary")
            if source_pdf:
                _, parsed_label, parsed_candidates = parse_filename(source_pdf)
                lecture_label = parsed_label
                candidate_labels = parsed_candidates
            else:
                seq = extract_sequence_number(lecture_label)
                if seq is not None:
                    lecture_label = canonical_lecture_label(seq)
                candidate_labels = [lecture_label]

            record = get_record(module_folder, lecture_label)
            record["candidate_labels"] = candidate_labels
            record["summary_path"] = summary_path
            if source_pdf and not record.get("source_pdf"):
                record["source_pdf"] = source_pdf

    lectures = list(records.values())
    for record in lectures:
        module_folder = record["module_folder"]
        candidate_labels = record["candidate_labels"]
        detailed_folder = module_folder / "Detailed Notes"
        summaries_folder = module_folder / "Summaries"

        if record["detailed_path"] is None:
            detailed_path, _ = resolve_note_path(detailed_folder, candidate_labels, "Detailed Notes")
            record["detailed_path"] = detailed_path
        if record["summary_path"] is None:
            summary_path, _ = resolve_note_path(summaries_folder, candidate_labels, "Summary")
            record["summary_path"] = summary_path

    return sorted(
        lectures,
        key=lambda record: (
            str(record["module_name"]).lower(),
            extract_sequence_number(str(record["lecture_label"])) or 10**9,
            str(record["lecture_label"]).lower(),
        ),
    )


def discover_papers(vault_root: Path, paper_files: list[Path]) -> list[dict[str, object]]:
    records: dict[tuple[str, str], dict[str, object]] = {}

    for paper_path in paper_files:
        collection_folder = paper_path.parent.parent
        paper_label = paper_label_from_stem(paper_path.stem)
        key = (collection_folder.name, paper_label)
        records[key] = {
            "source_type": "paper",
            "collection_folder": collection_folder,
            "collection_name": collection_folder.name,
            "paper_label": paper_label,
            "pdf_path": paper_path,
            "source_pdf": paper_path.name,
            "notes_path": None,
            "summary_path": None,
        }

    for child in sorted(vault_root.iterdir()):
        if not child.is_dir() or child.name.startswith(".") or child.name == "__pycache__":
            continue
        notes_folder = child / "Notes"
        summaries_folder = child / "Summaries"

        if notes_folder.exists():
            for notes_path in sorted(notes_folder.glob("* - Notes.md")):
                metadata = parse_frontmatter(notes_path.read_text(encoding="utf-8"))
                if metadata.get("note_type") != "paper":
                    continue
                paper_label = metadata.get("paper_label") or note_label_from_path(notes_path, "Notes")
                key = (child.name, paper_label)
                record = records.setdefault(
                    key,
                    {
                        "source_type": "paper",
                        "collection_folder": child,
                        "collection_name": child.name,
                        "paper_label": paper_label,
                        "pdf_path": None,
                        "source_pdf": metadata.get("source_pdf"),
                        "notes_path": None,
                        "summary_path": None,
                    },
                )
                record["notes_path"] = notes_path

        if summaries_folder.exists():
            for summary_path in sorted(summaries_folder.glob("* - Summary.md")):
                metadata = parse_frontmatter(summary_path.read_text(encoding="utf-8"))
                if metadata.get("note_type") not in ("paper", "summary"):
                    continue
                paper_label = metadata.get("paper_label") or metadata.get("lecture") or note_label_from_path(summary_path, "Summary")
                key = (child.name, paper_label)
                record = records.get(key)
                if record is not None and record.get("source_type") == "paper":
                    record["summary_path"] = summary_path

    papers = list(records.values())
    for record in papers:
        collection_folder = record["collection_folder"]
        paper_label = record["paper_label"]
        if record["notes_path"] is None:
            record["notes_path"] = collection_folder / "Notes" / f"{paper_label} - Notes.md"
        if record["summary_path"] is None:
            record["summary_path"] = collection_folder / "Summaries" / f"{paper_label} - Summary.md"

    return sorted(papers, key=lambda r: (str(r["collection_name"]).lower(), str(r["paper_label"]).lower()))


def extract_slide_sections(detailed_text: str) -> dict[int, str]:
    sections: dict[int, str] = {}
    matches = list(re.finditer(r"^## Slide (\d+): .+", detailed_text, flags=re.MULTILINE))
    for idx, match in enumerate(matches):
        start = match.end()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(detailed_text)
        section = detailed_text[start:end]
        section = re.sub(r"!\[\[.*?\]\]", "", section)
        section = section.replace("---", "")
        sections[int(match.group(1))] = re.sub(r"\s+", " ", section).strip()
    return sections


def audit_teaching_content(detailed_path: Path, manifest_path: Path | None) -> list[str]:
    if not detailed_path.exists() or manifest_path is None or not manifest_path.exists():
        return []

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    detailed_text = detailed_path.read_text(encoding="utf-8")
    sections = extract_slide_sections(detailed_text)
    flags: list[str] = []

    for slide in manifest.get("slides", []):
        if not isinstance(slide, dict):
            continue

        page_num = slide.get("page")
        if not isinstance(page_num, int):
            continue

        source_text = str(slide.get("text", ""))
        section = sections.get(page_num, "")
        section_len = len(section)
        word_count = int(slide.get("word_count", 0) or 0)
        needs_visual_review = bool(slide.get("needs_visual_review"))
        formula_like = bool(re.search(r"[=<>±∑σμβα]", source_text))

        is_section_divider = word_count <= 10
        if needs_visual_review and not is_section_divider and section_len < 120:
            flags.append(f"slide {page_num}: visually dense or sparse source text, but the explanation is short")
        elif formula_like and section_len < 160:
            flags.append(f"slide {page_num}: formula-bearing slide may need stronger variable-by-variable explanation")
        elif word_count >= 80 and section_len < 100:
            flags.append(f"slide {page_num}: text-dense slide may be underexplained in the detailed note")

        if len(flags) >= 8:
            break

    return flags


def build_validate_report(
    lectures: list[dict[str, object]],
    intake_issues: list[dict[str, object]],
    *,
    module_filter: str | None,
    lecture_filter: str | None,
    include_teaching_audit: bool,
) -> dict[str, object]:
    summary = {
        "ok": 0,
        "pending": 0,
        "issues": 0,
        "review": 0,
    }

    for lecture in lectures:
        status = str(lecture["status"])
        if status in summary:
            summary[status] += 1

    return {
        "scope": {
            "module": module_filter,
            "lecture": lecture_filter,
        },
        "teaching_audit_enabled": include_teaching_audit,
        "intake_issues": intake_issues,
        "summary": summary,
        "lectures": lectures,
    }


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    vault_root = find_vault_root()
    inbox_files, intake_issues = scan_inboxes(
        vault_root,
        apply_renames=False,
        module_filter=args.module,
        lecture_filter=args.lecture,
    )
    inbox_files = [
        file_path
        for file_path in inbox_files
        if matches_module_filter(file_path.parent.parent.name, args.module)
        and file_matches_scope(file_path, args.module, args.lecture)
    ]
    intake_issues = [
        issue
        for issue in intake_issues
        if matches_module_filter(str(issue.get("module_name", "")), args.module)
    ]

    lectures_report: list[dict[str, object]] = []
    for lecture in discover_lectures(vault_root, inbox_files):
        module_folder = lecture["module_folder"]
        module_name = str(lecture["module_name"])
        lecture_label = str(lecture["lecture_label"])

        if not matches_module_filter(module_name, args.module):
            continue
        if not matches_lecture_filter(module_name, lecture_label, args.lecture):
            continue

        module_code = module_code_from_name(module_name)
        detailed_path = Path(lecture["detailed_path"])
        summary_path = Path(lecture["summary_path"])
        pdf_source = lecture["pdf_path"]
        source_pdf = lecture["source_pdf"]

        if isinstance(pdf_source, Path):
            sequence_num = extract_sequence_number(pdf_source.stem)
            expected_pdf = canonical_pdf_filename(module_code, sequence_num) if sequence_num is not None else pdf_source.name
            page_count = count_pdf_pages(pdf_source)
            pdf_sha256 = file_sha256(pdf_source)
            pdf_modified_utc = file_modified_utc(pdf_source)
        else:
            expected_pdf = str(source_pdf) if source_pdf else None
            page_count = None
            pdf_sha256 = None
            pdf_modified_utc = None

        inferred_page_count = page_count
        if inferred_page_count is None:
            for note_path in (detailed_path, summary_path):
                if note_path.exists():
                    metadata = parse_frontmatter(note_path.read_text(encoding="utf-8"))
                    raw_page_count = metadata.get("page_count", "")
                    if raw_page_count.isdigit():
                        inferred_page_count = int(raw_page_count)
                        break

        detailed_status, detailed_reason = analyze_detailed_note(
            detailed_path,
            inferred_page_count,
            module_name=module_name,
            lecture_label=lecture_label,
            pdf_filename=expected_pdf,
            source_sha256=pdf_sha256,
            source_modified_utc=pdf_modified_utc,
        )
        summary_status, summary_reason = analyze_summary_note(
            summary_path,
            module_name=module_name,
            lecture_label=lecture_label,
            pdf_filename=expected_pdf,
            source_sha256=pdf_sha256,
            source_modified_utc=pdf_modified_utc,
            page_count=inferred_page_count,
        )

        mechanical_issues: list[str] = []
        pending: list[str] = []

        if pdf_source is None:
            mechanical_issues.append("source PDF missing from _inbox")

        if detailed_status == "missing":
            pending.append("detailed note not generated yet")
        elif detailed_status != "complete":
            mechanical_issues.append(f"detailed note: {detailed_reason}")

        if summary_status == "missing":
            pending.append("summary note not generated yet")
        elif summary_status != "complete":
            mechanical_issues.append(f"summary note: {summary_reason}")

        for md_path in [detailed_path, summary_path]:
            if md_path.exists():
                metadata = parse_frontmatter(md_path.read_text(encoding="utf-8"))
                if metadata.get("status") != "complete":
                    mechanical_issues.append(f"{md_path.name}: missing complete status in frontmatter")
                allowed_missing_stems = set()
                if detailed_status == "missing":
                    allowed_missing_stems.add(detailed_path.stem)
                if summary_status == "missing":
                    allowed_missing_stems.add(summary_path.stem)
                mechanical_issues.extend(
                    f"{md_path.name}: {issue}" for issue in validate_links(md_path, allowed_missing_stems)
                )

        manifest_path = expected_manifest_path(module_folder, expected_pdf)
        digest_path = expected_digest_path(module_folder, expected_pdf)
        if detailed_path.exists() and manifest_path is not None and not manifest_path.exists():
            mechanical_issues.append(f"missing slide manifest: {manifest_path.name}")
        if detailed_path.exists() and digest_path is not None and not digest_path.exists():
            mechanical_issues.append(f"missing lecture digest: {digest_path.name}")

        module_toc = module_folder / "Module TOC.md"
        if not module_toc.exists():
            mechanical_issues.append("missing Module TOC.md")
        else:
            toc_text = module_toc.read_text(encoding="utf-8")
            if "Concept Index" not in toc_text:
                mechanical_issues.append("module TOC missing concept index link")

        concept_index = module_folder / "Concept Index.md"
        if not concept_index.exists():
            mechanical_issues.append("missing Concept Index.md")

        teaching_content_flags = []
        teaching_audit_status = "skipped"
        if not args.no_teaching_audit and detailed_status == "complete":
            teaching_content_flags = audit_teaching_content(detailed_path, manifest_path)
            teaching_audit_status = "flagged" if teaching_content_flags else "clear"
        elif args.no_teaching_audit:
            teaching_audit_status = "disabled"

        if mechanical_issues:
            status = "issues"
        elif pending:
            status = "pending"
        elif teaching_content_flags:
            status = "review"
        else:
            status = "ok"

        lectures_report.append(
            {
                "module": module_name,
                "lecture": lecture_label,
                "source_pdf": expected_pdf,
                "detailed_path": str(detailed_path),
                "summary_path": str(summary_path),
                "manifest_path": str(manifest_path) if manifest_path is not None else None,
                "digest_path": str(digest_path) if digest_path is not None else None,
                "status": status,
                "pending": pending,
                "mechanical_issues": mechanical_issues,
                "issues": mechanical_issues,
                "teaching_content_flags": teaching_content_flags,
                "teaching_audit_status": teaching_audit_status,
                "detailed_audit": extract_audit_fields(parse_frontmatter(detailed_path.read_text(encoding="utf-8")))
                if detailed_path.exists()
                else extract_audit_fields({}),
                "summary_audit": extract_audit_fields(parse_frontmatter(summary_path.read_text(encoding="utf-8")))
                if summary_path.exists()
                else extract_audit_fields({}),
            }
        )

    paper_files, _ = scan_papers(vault_root, apply_renames=False, collection_filter=args.module)
    papers_report: list[dict[str, object]] = []

    for paper in discover_papers(vault_root, paper_files):
        collection_name = str(paper["collection_name"])
        paper_label = str(paper["paper_label"])

        if args.module and not matches_module_filter(collection_name, args.module):
            continue
        if args.lecture and paper_label.lower() not in (args.lecture or "").lower() and (args.lecture or "").lower() not in paper_label.lower():
            continue

        collection_folder = paper["collection_folder"]
        pdf_source = paper["pdf_path"]
        notes_path = Path(paper["notes_path"])
        summary_path = Path(paper["summary_path"])

        if isinstance(pdf_source, Path):
            page_count = count_pdf_pages(pdf_source)
            pdf_sha256 = file_sha256(pdf_source)
            pdf_modified_utc = file_modified_utc(pdf_source)
        else:
            page_count = None
            pdf_sha256 = None
            pdf_modified_utc = None

        notes_status, notes_reason = analyze_paper_note(
            notes_path,
            collection_name=collection_name,
            paper_label=paper_label,
            source_sha256=pdf_sha256,
            source_modified_utc=pdf_modified_utc,
        )
        summary_status, summary_reason = analyze_summary_note(
            summary_path,
            module_name=collection_name,
            lecture_label=paper_label,
            source_sha256=pdf_sha256,
            source_modified_utc=pdf_modified_utc,
            page_count=page_count,
        )

        mechanical_issues: list[str] = []
        pending: list[str] = []

        if pdf_source is None:
            mechanical_issues.append("source PDF missing from _papers")
        if notes_status == "missing":
            pending.append("paper notes not generated yet")
        elif notes_status != "complete":
            mechanical_issues.append(f"paper notes: {notes_reason}")
        if summary_status == "missing":
            pending.append("paper summary not generated yet")
        elif summary_status != "complete":
            mechanical_issues.append(f"paper summary: {summary_reason}")

        for md_path in [notes_path, summary_path]:
            if md_path.exists():
                metadata = parse_frontmatter(md_path.read_text(encoding="utf-8"))
                if metadata.get("status") != "complete":
                    mechanical_issues.append(f"{md_path.name}: missing complete status in frontmatter")
                allowed_missing_stems: set[str] = set()
                if notes_status == "missing":
                    allowed_missing_stems.add(notes_path.stem)
                if summary_status == "missing":
                    allowed_missing_stems.add(summary_path.stem)
                mechanical_issues.extend(
                    f"{md_path.name}: {issue}" for issue in validate_links(md_path, allowed_missing_stems)
                )

        reading_list = collection_folder / "Reading List.md"
        if not reading_list.exists():
            mechanical_issues.append("missing Reading List.md")

        status = "issues" if mechanical_issues else ("pending" if pending else "ok")

        papers_report.append(
            {
                "source_type": "paper",
                "collection": collection_name,
                "paper_label": paper_label,
                "source_pdf": paper.get("source_pdf"),
                "notes_path": str(notes_path),
                "summary_path": str(summary_path),
                "status": status,
                "pending": pending,
                "mechanical_issues": mechanical_issues,
                "issues": mechanical_issues,
                "notes_audit": extract_audit_fields(parse_frontmatter(notes_path.read_text(encoding="utf-8")))
                if notes_path.exists()
                else extract_audit_fields({}),
                "summary_audit": extract_audit_fields(parse_frontmatter(summary_path.read_text(encoding="utf-8")))
                if summary_path.exists()
                else extract_audit_fields({}),
            }
        )

    payload = build_validate_report(
        lectures_report + papers_report,
        intake_issues,
        module_filter=args.module,
        lecture_filter=args.lecture,
        include_teaching_audit=not args.no_teaching_audit,
    )
    write_json_payload(payload, args.report_path)
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def file_matches_scope(file_path: Path, module_filter: str | None, lecture_filter: str | None) -> bool:
    module_name = file_path.parent.parent.name
    _, lecture_label, _ = parse_filename(file_path.name)
    return matches_module_filter(module_name, module_filter) and matches_lecture_filter(
        module_name,
        lecture_label,
        lecture_filter,
    )


if __name__ == "__main__":
    main()
