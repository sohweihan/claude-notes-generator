#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from extract import (
    file_sha256,
    find_vault_root,
    matches_lecture_filter,
    matches_module_filter,
    parse_frontmatter,
    scan_inboxes,
    scan_papers,
)
from validate import discover_lectures, discover_papers


AUDIT_FIELDS = (
    "audit_status",
    "last_audited_utc",
    "last_audit_mode",
    "last_audit_action",
    "last_audited_against_sha256",
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record note audit metadata and append to audit history.")
    parser.add_argument("--module", required=True, help="Module name or code.")
    parser.add_argument("--lecture", required=True, help="Lecture label, number, or combined target.")
    parser.add_argument(
        "--status",
        required=True,
        choices=("preliminary_clear", "audited", "flagged", "repaired"),
        help="Audit outcome to store on the notes.",
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=("auto", "light", "strict"),
        help="Audit review depth: auto, light, or strict.",
    )
    parser.add_argument(
        "--action",
        required=True,
        choices=("preliminary", "flag-only", "repair"),
        help="Audit action performed.",
    )
    parser.add_argument(
        "--scope",
        choices=("both", "detailed", "summary"),
        default="both",
        help="Which note types to update.",
    )
    parser.add_argument("--source-sha256", help="Optional source PDF hash. Computed automatically when omitted.")
    parser.add_argument("--note", action="append", default=[], help="Optional note to append into the audit history.")
    parser.add_argument(
        "--history-path",
        default="reports/audit_history.jsonl",
        help="Relative path to the append-only audit history file.",
    )
    return parser.parse_args(argv)


def update_frontmatter(note_path: Path, updates: dict[str, str]) -> None:
    text = note_path.read_text(encoding="utf-8")
    if text.startswith("---\n"):
        end_idx = text.find("\n---\n", 4)
    else:
        end_idx = -1

    if end_idx == -1:
        header_lines: list[str] = []
        body = text
    else:
        header_lines = text[4:end_idx].splitlines()
        body = text[end_idx + 5 :]

    remaining = dict(updates)
    new_header_lines: list[str] = []
    seen: set[str] = set()

    for raw_line in header_lines:
        if ":" not in raw_line:
            new_header_lines.append(raw_line)
            continue
        key, _ = raw_line.split(":", 1)
        key = key.strip()
        if key in remaining:
            new_header_lines.append(f"{key}: {remaining.pop(key)}")
            seen.add(key)
        else:
            new_header_lines.append(raw_line)
            seen.add(key)

    for key in AUDIT_FIELDS:
        if key in remaining and key not in seen:
            new_header_lines.append(f"{key}: {remaining.pop(key)}")

    for key, value in remaining.items():
        if key not in seen:
            new_header_lines.append(f"{key}: {value}")

    new_text = "---\n" + "\n".join(new_header_lines) + "\n---\n" + body.lstrip("\n")
    note_path.write_text(new_text, encoding="utf-8")


def resolve_target_lecture(vault_root: Path, module_filter: str, lecture_filter: str) -> dict[str, object]:
    inbox_files, _ = scan_inboxes(
        vault_root,
        apply_renames=False,
        module_filter=module_filter,
        lecture_filter=lecture_filter,
    )
    candidates = [
        lecture
        for lecture in discover_lectures(vault_root, inbox_files)
        if matches_module_filter(str(lecture["module_name"]), module_filter)
        and matches_lecture_filter(str(lecture["module_name"]), str(lecture["lecture_label"]), lecture_filter)
    ]

    if not candidates:
        paper_files, _ = scan_papers(vault_root, apply_renames=False, collection_filter=module_filter)
        paper_candidates = []
        for paper in discover_papers(vault_root, paper_files):
            collection_name = str(paper["collection_name"])
            paper_label = str(paper["paper_label"])
            if not matches_module_filter(collection_name, module_filter):
                continue
            if lecture_filter and lecture_filter.lower() not in paper_label.lower() and paper_label.lower() not in lecture_filter.lower():
                continue
            paper_candidates.append({
                "module_name": collection_name,
                "lecture_label": paper_label,
                "detailed_path": paper["notes_path"],
                "summary_path": paper["summary_path"],
                "pdf_path": paper.get("pdf_path"),
                "source_type": "paper",
            })
        candidates = paper_candidates

    if not candidates:
        raise SystemExit(f"No lecture or paper matched module={module_filter!r} lecture={lecture_filter!r}.")
    if len(candidates) > 1:
        raise SystemExit(f"Multiple matches found for module={module_filter!r} lecture={lecture_filter!r}.")
    return candidates[0]


def infer_source_sha256(lecture: dict[str, object], explicit_sha256: str | None) -> str | None:
    if explicit_sha256:
        return explicit_sha256
    pdf_path = lecture.get("pdf_path")
    if isinstance(pdf_path, Path) and pdf_path.exists():
        return file_sha256(pdf_path)
    return None


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    vault_root = find_vault_root()
    lecture = resolve_target_lecture(vault_root, args.module, args.lecture)

    audited_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    source_sha256 = infer_source_sha256(lecture, args.source_sha256)

    note_targets: list[Path] = []
    if args.scope in {"both", "detailed"}:
        detailed_path = Path(lecture["detailed_path"])
        if detailed_path.exists():
            note_targets.append(detailed_path)
    if args.scope in {"both", "summary"}:
        summary_path = Path(lecture["summary_path"])
        if summary_path.exists():
            note_targets.append(summary_path)

    frontmatter_updates = {
        "audit_status": args.status,
        "last_audited_utc": audited_utc,
        "last_audit_mode": args.mode,
        "last_audit_action": args.action,
        "last_audited_against_sha256": source_sha256 or "",
    }

    updated_files: list[str] = []
    for note_path in note_targets:
        metadata = parse_frontmatter(note_path.read_text(encoding="utf-8"))
        if metadata.get("status") != "complete":
            continue
        update_frontmatter(note_path, frontmatter_updates)
        updated_files.append(str(note_path))

    history_path = (vault_root / args.history_path).resolve()
    history_path.parent.mkdir(parents=True, exist_ok=True)
    record = {
        "audited_utc": audited_utc,
        "module": lecture["module_name"],
        "lecture": lecture["lecture_label"],
        "status": args.status,
        "mode": args.mode,
        "action": args.action,
        "source_sha256": source_sha256,
        "updated_files": updated_files,
        "notes": args.note,
    }
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(json.dumps({"updated_files": updated_files, "history_path": str(history_path), "record": record}, indent=2))


if __name__ == "__main__":
    main()
