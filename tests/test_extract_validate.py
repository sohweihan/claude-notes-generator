from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import fitz

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from extract import (  # noqa: E402
    analyze_detailed_note,
    analyze_summary_note,
    build_slide_manifest,
    digest_needs_refresh,
    digest_path_for,
    extractor_lock,
    extract_sequence_number,
    manifest_needs_refresh,
    matches_lecture_filter,
    matches_module_filter,
    scan_inboxes,
    source_fingerprint,
)
from record_audit import main as record_audit_main  # noqa: E402
from validate import discover_lectures, validate_links  # noqa: E402


class ExtractValidateTests(unittest.TestCase):
    def make_temp_root(self) -> Path:
        temp_root = Path.cwd() / f"tmp_mqf_test_{uuid.uuid4().hex}"
        temp_root.mkdir(parents=True, exist_ok=False)
        self.addCleanup(lambda: shutil.rmtree(temp_root, ignore_errors=True))
        return temp_root

    def create_pdf(self, pdf_path: Path, text: str) -> None:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text)
        doc.save(pdf_path)
        doc.close()

    def test_extract_sequence_number_handles_words_and_rejects_bare_numbers(self) -> None:
        self.assertEqual(extract_sequence_number("week one"), 1)
        self.assertEqual(extract_sequence_number("Lecture 02 revised"), 2)
        self.assertIsNone(extract_sequence_number("02"))

    def test_scope_matching_supports_module_and_lecture_filters(self) -> None:
        self.assertTrue(matches_module_filter("QF623_Portfolio Management", "QF623"))
        self.assertTrue(matches_module_filter("QF623_Portfolio Management", "portfolio"))
        self.assertTrue(matches_lecture_filter("QF623_Portfolio Management", "Lecture 01", "L01"))
        self.assertTrue(matches_lecture_filter("QF623_Portfolio Management", "Lecture 01", "QF623 Lecture 01"))
        self.assertFalse(matches_lecture_filter("QF623_Portfolio Management", "Lecture 01", "Lecture 02"))

    def test_scan_inboxes_reports_conflicts_without_guessing(self) -> None:
        vault_root = self.make_temp_root()
        (vault_root / "CLAUDE.md").write_text("", encoding="utf-8")
        inbox = vault_root / "QF999_Test Module" / "_inbox"
        inbox.mkdir(parents=True)
        (inbox / "Week 1.pdf").write_bytes(b"%PDF-1.4")
        (inbox / "Lecture 1 revised.pdf").write_bytes(b"%PDF-1.4")

        ready_files, issues = scan_inboxes(vault_root, apply_renames=False)

        self.assertEqual(ready_files, [])
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["status"], "conflict")
        self.assertEqual(issues[0]["target_name"], "QF999_L01.pdf")

    def test_scoped_scan_only_renames_matching_module(self) -> None:
        vault_root = self.make_temp_root()
        (vault_root / "CLAUDE.md").write_text("", encoding="utf-8")
        target_inbox = vault_root / "QF999_Test Module" / "_inbox"
        other_inbox = vault_root / "QF123_Other Module" / "_inbox"
        target_inbox.mkdir(parents=True)
        other_inbox.mkdir(parents=True)
        (target_inbox / "Week 1.pdf").write_bytes(b"%PDF-1.4")
        (other_inbox / "Week 2.pdf").write_bytes(b"%PDF-1.4")

        ready_files, issues = scan_inboxes(
            vault_root,
            apply_renames=True,
            module_filter="QF999",
        )

        self.assertEqual(issues, [])
        self.assertEqual([path.name for path in ready_files], ["QF999_L01.pdf"])
        self.assertTrue((target_inbox / "QF999_L01.pdf").exists())
        self.assertTrue((other_inbox / "Week 2.pdf").exists())

    def test_discover_lectures_includes_note_only_records(self) -> None:
        vault_root = self.make_temp_root()
        (vault_root / "CLAUDE.md").write_text("", encoding="utf-8")
        module_folder = vault_root / "QF999_Test Module"
        detailed_folder = module_folder / "Detailed Notes"
        detailed_folder.mkdir(parents=True)
        note_path = detailed_folder / "Lecture 01 - Detailed Notes.md"
        note_path.write_text(
            "\n".join(
                [
                    "---",
                    "status: complete",
                    "module: QF999_Test Module",
                    "lecture: Lecture 01",
                    "source_pdf: QF999_L01.pdf",
                    "page_count: 2",
                    "note_type: detailed",
                    "---",
                    "",
                    "# Test",
                ]
            ),
            encoding="utf-8",
        )

        lectures = discover_lectures(vault_root, [])

        self.assertEqual(len(lectures), 1)
        self.assertEqual(lectures[0]["lecture_label"], "Lecture 01")
        self.assertEqual(Path(lectures[0]["detailed_path"]), note_path)
        self.assertIsNone(lectures[0]["pdf_path"])

    def test_analyze_detailed_note_can_validate_without_live_source_pdf(self) -> None:
        temp_root = self.make_temp_root()
        note_path = temp_root / "Lecture 01 - Detailed Notes.md"
        note_path.write_text(
            "\n".join(
                [
                    "---",
                    "status: complete",
                    "module: QF999_Test Module",
                    "lecture: Lecture 01",
                    "source_pdf: QF999_L01.pdf",
                    "page_count: 2",
                    "note_type: detailed",
                    "---",
                    "",
                    "## Slide 1: Intro",
                    "",
                    "This slide explains the setup clearly enough for validation to accept it.",
                    "",
                    "## Slide 2: Next",
                    "",
                    "This slide also has enough explanatory content to count as complete.",
                ]
            ),
            encoding="utf-8",
        )

        status, reason = analyze_detailed_note(
            note_path,
            None,
            module_name="QF999_Test Module",
            lecture_label="Lecture 01",
            pdf_filename="QF999_L01.pdf",
        )

        self.assertEqual(status, "complete")
        self.assertEqual(reason, "all slide headings present")

    def test_manifest_includes_source_fingerprint_and_refreshes_on_mismatch(self) -> None:
        temp_root = self.make_temp_root()
        pdf_path = temp_root / "QF999_L01.pdf"
        assets_dir = temp_root / "assets"
        self.create_pdf(pdf_path, "Slide 1 content")
        source_sha256, source_modified_utc = source_fingerprint(pdf_path)

        _, manifest_path, slide_images = build_slide_manifest(
            pdf_path,
            assets_dir,
            "QF999_L01",
            source_sha256=source_sha256,
            source_modified_utc=source_modified_utc,
        )

        self.assertTrue(manifest_path.exists())
        digest_path = digest_path_for(assets_dir, "QF999_L01")
        self.assertTrue(digest_path.exists())
        self.assertEqual(len(slide_images), 1)
        self.assertFalse(
            manifest_needs_refresh(
                manifest_path,
                pdf_path=pdf_path,
                source_sha256=source_sha256,
                source_modified_utc=source_modified_utc,
            )
        )
        self.assertFalse(
            digest_needs_refresh(
                digest_path,
                pdf_path=pdf_path,
                source_sha256=source_sha256,
                source_modified_utc=source_modified_utc,
            )
        )
        self.assertTrue(
            manifest_needs_refresh(
                manifest_path,
                pdf_path=pdf_path,
                source_sha256="BADHASH",
                source_modified_utc=source_modified_utc,
            )
        )
        self.assertTrue(
            digest_needs_refresh(
                digest_path,
                pdf_path=pdf_path,
                source_sha256="BADHASH",
                source_modified_utc=source_modified_utc,
            )
        )

    def test_validate_links_ignores_plain_matrix_notation(self) -> None:
        temp_root = self.make_temp_root()
        summaries_dir = temp_root / "Summaries"
        summaries_dir.mkdir()
        note_path = summaries_dir / "Lecture 03 - Summary.md"
        note_path.write_text(
            "\n".join(
                [
                    "## Important Terms",
                    "- Transition matrix: Π = [[p, 1−p], [1−q, q]]",
                    "- Real link: [[../Detailed Notes/Lecture 03 - Detailed Notes]]",
                ]
            ),
            encoding="utf-8",
        )
        detailed_dir = temp_root / "Detailed Notes"
        detailed_dir.mkdir()
        (detailed_dir / "Lecture 03 - Detailed Notes.md").write_text("# Placeholder", encoding="utf-8")

        issues = validate_links(note_path, set())

        self.assertEqual(issues, [])

    def test_extractor_lock_recovers_stale_lock(self) -> None:
        vault_root = self.make_temp_root()
        (vault_root / "CLAUDE.md").write_text("", encoding="utf-8")
        lock_path = vault_root / ".extract.lock"
        stale_payload = {
            "pid": 999999,
            "created_utc": (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scope": {"module": "QF999"},
        }
        lock_path.write_text(json.dumps(stale_payload), encoding="utf-8")

        with extractor_lock(vault_root, {"module": "QF999"}):
            self.assertTrue(lock_path.exists())

        self.assertFalse(lock_path.exists())

    def test_analyze_summary_note_requires_answered_review_questions_in_section(self) -> None:
        temp_root = self.make_temp_root()
        note_path = temp_root / "Lecture 01 - Summary.md"
        note_path.write_text(
            "\n".join(
                [
                    "---",
                    "status: complete",
                    "module: QF999_Test Module",
                    "lecture: Lecture 01",
                    "source_pdf: QF999_L01.pdf",
                    "page_count: 2",
                    "note_type: summary",
                    "---",
                    "",
                    "# QF999_Test Module - Lecture 01 - Summary",
                    "",
                    "## Overview",
                    "Short overview.",
                    "",
                    "## Key Concepts",
                    "- Concept.",
                    "",
                    "## Important Terms",
                    "- Term.",
                    "",
                    "## Key Takeaways",
                    "- Takeaway.",
                    "",
                    "1. Stray numbered item before review section",
                    "2. Another stray item",
                    "",
                    "## Review Questions",
                    "1. Question only",
                    "2. Another question only",
                ]
            ),
            encoding="utf-8",
        )

        status, reason = analyze_summary_note(
            note_path,
            module_name="QF999_Test Module",
            lecture_label="Lecture 01",
            pdf_filename="QF999_L01.pdf",
            page_count=2,
        )

        self.assertEqual(status, "incomplete")
        self.assertEqual(reason, "fewer than 5 answered review questions found")

    def test_record_audit_updates_frontmatter_and_history(self) -> None:
        vault_root = self.make_temp_root()
        (vault_root / "CLAUDE.md").write_text("", encoding="utf-8")
        module_folder = vault_root / "QF999_Test Module"
        inbox = module_folder / "_inbox"
        detailed_folder = module_folder / "Detailed Notes"
        summaries_folder = module_folder / "Summaries"
        inbox.mkdir(parents=True)
        detailed_folder.mkdir()
        summaries_folder.mkdir()
        pdf_path = inbox / "QF999_L01.pdf"
        self.create_pdf(pdf_path, "Slide 1 content")

        detailed_path = detailed_folder / "Lecture 01 - Detailed Notes.md"
        summary_path = summaries_folder / "Lecture 01 - Summary.md"
        note_frontmatter = [
            "---",
            "status: complete",
            "module: QF999_Test Module",
            "lecture: Lecture 01",
            "source_pdf: QF999_L01.pdf",
            "page_count: 1",
            "note_type: {note_type}",
            "---",
            "",
            "# Placeholder",
        ]
        detailed_path.write_text("\n".join(line.format(note_type="detailed") for line in note_frontmatter), encoding="utf-8")
        summary_path.write_text("\n".join(line.format(note_type="summary") for line in note_frontmatter), encoding="utf-8")

        old_cwd = Path.cwd()
        os.chdir(vault_root)
        try:
            record_audit_main(
                [
                    "--module",
                    "QF999",
                    "--lecture",
                    "Lecture 01",
                    "--status",
                    "audited",
                    "--mode",
                    "light",
                    "--action",
                    "flag-only",
                    "--note",
                    "Scoped lecture audit completed",
                ]
            )
        finally:
            os.chdir(old_cwd)

        detailed_text = detailed_path.read_text(encoding="utf-8")
        summary_text = summary_path.read_text(encoding="utf-8")
        self.assertIn("audit_status: audited", detailed_text)
        self.assertIn("audit_status: audited", summary_text)
        history_path = vault_root / "reports" / "audit_history.jsonl"
        self.assertTrue(history_path.exists())
        history_records = [json.loads(line) for line in history_path.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(history_records), 1)
        self.assertEqual(history_records[0]["status"], "audited")


if __name__ == "__main__":
    unittest.main()
