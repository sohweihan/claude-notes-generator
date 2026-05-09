#!/usr/bin/env python3
"""
Slide extractor and workflow manifest generator.

- Finds PDF files in module _inbox/ folders
- Normalizes inbox filenames to a canonical lecture/session format
- Surfaces ambiguous or conflicting uploader filenames instead of guessing
- Creates folder scaffolding
- Extracts slide text into a compact manifest
- Renders slide images for note embeds and visual review
- Returns resumable work items so Claude can continue partial runs
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from collections.abc import Mapping
from contextlib import contextmanager, suppress
from datetime import datetime, timezone
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    print("Error: PyMuPDF not installed.\nRun: pip install pymupdf")
    sys.exit(1)

sys.stdout.reconfigure(encoding="utf-8")

SLIDE_RENDER_ZOOM = float(os.getenv("SLIDE_RENDER_ZOOM", "1.5"))
RENDER_MODE = os.getenv("RENDER_MODE", "all").strip().lower()
VISUAL_REVIEW_WORD_THRESHOLD = int(os.getenv("VISUAL_REVIEW_WORD_THRESHOLD", "40"))
MAX_FILES_PER_RUN = int(os.getenv("MAX_FILES_PER_RUN", "1"))
EXTRACT_LOCK_STALE_HOURS = float(os.getenv("EXTRACT_LOCK_STALE_HOURS", "12"))
NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def module_code_from_name(name: str) -> str:
    match = re.match(r"^([A-Za-z0-9]+)", name.strip())
    return match.group(1) if match else name.strip().replace(" ", "_")


def extract_sequence_number(name: str) -> int | None:
    normalized = re.sub(r"[_\-\s]+", " ", name).strip().lower()
    digit_patterns = [
        r"\bl0*(\d{1,2})\b",
        r"\b(?:lecture|lec|lesson|week|wk|session|sess|class|topic)\s*0*(\d{1,2})\b",
    ]
    for pattern in digit_patterns:
        match = re.search(pattern, normalized)
        if match:
            value = int(match.group(1))
            if 1 <= value <= 99:
                return value

    word_match = re.search(
        r"\b(?:lecture|lec|week|wk|session|sess|class|topic)\s+("
        + "|".join(NUMBER_WORDS)
        + r")\b",
        normalized,
    )
    if word_match:
        return NUMBER_WORDS[word_match.group(1)]

    return None


def canonical_lecture_label(sequence_num: int) -> str:
    return f"Lecture {sequence_num:02d}"


def canonical_pdf_filename(module_code: str, sequence_num: int) -> str:
    return f"{module_code}_L{sequence_num:02d}.pdf"


def find_vault_root() -> Path:
    for candidate in [Path.cwd(), *Path.cwd().parents]:
        if (candidate / "CLAUDE.md").exists():
            return candidate
    return Path.cwd()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate scoped slide-processing work items for the vault.")
    parser.add_argument("--module", help="Restrict processing to one module name or module code.")
    parser.add_argument("--lecture", help="Restrict processing to one lecture label, number, or combined target string.")
    parser.add_argument(
        "--max-files",
        type=int,
        default=MAX_FILES_PER_RUN,
        help="Maximum number of work items to return. Defaults to MAX_FILES_PER_RUN.",
    )
    parser.add_argument("--report-path", help="Optional path to also write the JSON payload.")
    return parser.parse_args(argv)


def normalize_match_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", value)).strip().lower()


def matches_module_filter(module_name: str, module_filter: str | None) -> bool:
    if not module_filter:
        return True

    module_code = module_code_from_name(module_name)
    target_tokens = {
        normalize_match_text(module_name),
        normalize_match_text(module_code),
    }
    filter_text = normalize_match_text(module_filter)
    return any(filter_text == token or filter_text in token for token in target_tokens)


def matches_lecture_filter(module_name: str, lecture_label: str, lecture_filter: str | None) -> bool:
    if not lecture_filter:
        return True

    filter_text = normalize_match_text(lecture_filter)
    target_text = normalize_match_text(f"{module_name} {module_code_from_name(module_name)} {lecture_label}")
    if filter_text and filter_text in target_text:
        return True

    filter_sequence = extract_sequence_number(lecture_filter)
    lecture_sequence = extract_sequence_number(lecture_label)
    return filter_sequence is not None and filter_sequence == lecture_sequence


def file_matches_scope(file_path: Path, module_filter: str | None, lecture_filter: str | None) -> bool:
    module_name = file_path.parent.parent.name
    _, lecture_label, _ = parse_filename(file_path.name)
    return matches_module_filter(module_name, module_filter) and matches_lecture_filter(
        module_name,
        lecture_label,
        lecture_filter,
    )


def filter_intake_issues(
    issues: list[dict[str, object]],
    module_filter: str | None,
    lecture_filter: str | None,
) -> list[dict[str, object]]:
    filtered: list[dict[str, object]] = []
    for issue in issues:
        module_name = str(issue.get("module_name", ""))
        if not matches_module_filter(module_name, module_filter):
            continue

        lecture_label = None
        target_name = issue.get("target_name")
        if isinstance(target_name, str):
            _, lecture_label, _ = parse_filename(target_name)
        else:
            original_file = issue.get("original_file")
            if isinstance(original_file, str):
                _, lecture_label, _ = parse_filename(Path(original_file).name)

        if lecture_filter and lecture_label is not None and not matches_lecture_filter(module_name, lecture_label, lecture_filter):
            continue
        if lecture_filter and lecture_label is None:
            filter_sequence = extract_sequence_number(lecture_filter)
            original_files = issue.get("original_files")
            if filter_sequence is not None and isinstance(original_files, list):
                matched = any(
                    extract_sequence_number(Path(str(path)).stem) == filter_sequence
                    for path in original_files
                )
                if not matched:
                    continue
            elif filter_sequence is not None:
                continue

        filtered.append(issue)
    return filtered


def build_extract_result(
    intake_issues: list[dict[str, object]],
    work_items: list[dict[str, object]],
    *,
    module_filter: str | None,
    lecture_filter: str | None,
    max_files: int,
) -> dict[str, object]:
    return {
        "scope": {
            "module": module_filter,
            "lecture": lecture_filter,
            "max_files": max_files,
        },
        "intake_issues": intake_issues,
        "work_items": work_items,
    }


def write_json_payload(payload: dict[str, object], report_path: str | None) -> None:
    if not report_path:
        return
    destination = Path(report_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_utc_timestamp(value: str) -> datetime | None:
    with suppress(ValueError):
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    return None


def process_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def load_lock_payload(lock_path: Path) -> tuple[dict[str, object] | None, str | None]:
    try:
        raw_text = lock_path.read_text(encoding="utf-8")
    except OSError:
        return None, None

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return None, raw_text

    if isinstance(payload, dict):
        return payload, raw_text
    return None, raw_text


def lock_is_stale(lock_path: Path, payload: Mapping[str, object] | None) -> bool:
    created_utc = None
    pid = None
    if payload is not None:
        raw_created = payload.get("created_utc")
        if isinstance(raw_created, str):
            created_utc = parse_utc_timestamp(raw_created)
        raw_pid = payload.get("pid")
        if isinstance(raw_pid, int):
            pid = raw_pid

    if pid is not None and not process_is_running(pid):
        return True

    age_seconds = datetime.now(timezone.utc).timestamp() - lock_path.stat().st_mtime
    if created_utc is not None:
        age_seconds = max(age_seconds, (datetime.now(timezone.utc) - created_utc).total_seconds())

    if age_seconds >= EXTRACT_LOCK_STALE_HOURS * 3600:
        return True

    return False


@contextmanager
def extractor_lock(vault_root: Path, scope: dict[str, object]):
    lock_path = vault_root / ".extract.lock"
    payload = {
        "pid": os.getpid(),
        "created_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": scope,
    }
    for attempt in range(2):
        try:
            fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            existing_payload, existing_text = load_lock_payload(lock_path)
            if attempt == 0 and lock_is_stale(lock_path, existing_payload):
                with suppress(FileNotFoundError):
                    lock_path.unlink()
                continue
            raise RuntimeError(f"extractor lock already exists at {lock_path}: {existing_text or 'busy'}")
    else:
        raise RuntimeError(f"unable to create extractor lock at {lock_path}")

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)
        yield lock_path
    finally:
        with suppress(FileNotFoundError):
            lock_path.unlink()


def scan_inboxes(
    vault_root: Path,
    apply_renames: bool = True,
    *,
    module_filter: str | None = None,
    lecture_filter: str | None = None,
) -> tuple[list[Path], list[dict[str, object]]]:
    ready_files: list[Path] = []
    issues: list[dict[str, object]] = []

    for inbox in sorted(vault_root.rglob("_inbox")):
        if not inbox.is_dir():
            continue

        module_name = inbox.parent.name
        if not matches_module_filter(module_name, module_filter):
            continue
        module_code = module_code_from_name(module_name)
        grouped: dict[str, list[Path]] = {}

        for file_path in sorted(inbox.iterdir()):
            if file_path.suffix.lower() != ".pdf" or file_path.name.startswith("."):
                continue

            sequence_num = extract_sequence_number(file_path.stem)
            if sequence_num is None:
                issues.append(
                    {
                        "module_name": module_name,
                        "module_code": module_code,
                        "status": "ambiguous",
                        "original_file": str(file_path),
                        "reason": "could not infer lecture number from PDF filename",
                    }
                )
                continue

            target_name = canonical_pdf_filename(module_code, sequence_num)
            _, lecture_label, _ = parse_filename(target_name)
            if not matches_lecture_filter(module_name, lecture_label, lecture_filter):
                continue
            grouped.setdefault(target_name, []).append(file_path)

        for target_name, source_files in sorted(grouped.items()):
            if len(source_files) > 1:
                issues.append(
                    {
                        "module_name": module_name,
                        "module_code": module_code,
                        "status": "conflict",
                        "target_name": target_name,
                        "original_files": [str(path) for path in source_files],
                        "reason": f"multiple PDFs map to {target_name}: {', '.join(path.name for path in source_files)}",
                    }
                )
                continue

            source_path = source_files[0]
            target_path = source_path.with_name(target_name)
            if apply_renames and source_path != target_path:
                source_path.rename(target_path)
                ready_files.append(target_path)
            else:
                ready_files.append(source_path)

    return ready_files, issues


def parse_filename(filename: str) -> tuple[str, str, list[str]]:
    """
    Examples:
    - CS101_L03.pdf -> ("CS101", "Lecture 03", [...])
    - QF623_Week1.pdf -> ("QF623", "Lecture 01", [...])
    - Intro to Carry Week One.pdf -> ("Intro to Carry Week One", "Lecture 01", [...]) before normalization
    """
    stem = Path(filename).stem
    module_code = stem.split("_", 1)[0]
    sequence_num = extract_sequence_number(stem)
    if sequence_num is None:
        lecture_label = "Lecture Unknown"
        return module_code, lecture_label, [lecture_label]

    lecture_label = canonical_lecture_label(sequence_num)
    legacy_labels = [
        lecture_label,
        f"Lecture {sequence_num}",
        f"Week {sequence_num}",
        f"Week {sequence_num:02d}",
    ]

    parts = stem.split("_", 1)
    if len(parts) > 1:
        legacy_label = parts[1].replace("_", " ").strip()
        if legacy_label and legacy_label not in legacy_labels:
            legacy_labels.append(legacy_label)

    deduped_labels: list[str] = []
    for label in legacy_labels:
        if label not in deduped_labels:
            deduped_labels.append(label)

    return module_code, lecture_label, deduped_labels


def lecture_sort_key(file_path: Path) -> tuple[str, int, str]:
    sequence_num = extract_sequence_number(file_path.stem)
    lecture_num = sequence_num if sequence_num is not None else 10**9
    return file_path.parent.parent.name.lower(), lecture_num, file_path.name.lower()


def normalize_text(raw: str) -> str:
    return re.sub(r"\s+", " ", raw).strip()


def digest_path_for(assets_dir: Path, prefix: str) -> Path:
    return assets_dir / f"{prefix}_lecture_digest.json"


def slide_preview(text: str, *, max_words: int = 18) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""
    words = normalized.split()
    if len(words) <= max_words:
        return normalized
    return " ".join(words[:max_words]) + " ..."


def slide_contains_formula(text: str) -> bool:
    return bool(re.search(r"[=<>±∑σμβαπΠλγδμΣ]|\\frac|\\sum|\b[A-Z]{2,}\b", text))


def slide_contains_table(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) < 3:
        return False
    return sum(1 for line in lines if len(re.findall(r"\s{2,}|\t", line)) >= 1) >= 2


def slide_contains_chart(text: str, image_count: int) -> bool:
    chart_terms = (
        "chart",
        "graph",
        "figure",
        "panel",
        "axis",
        "return",
        "volatility",
        "sharpe",
        "drawdown",
        "histogram",
        "scatter",
    )
    normalized = text.lower()
    return image_count > 0 and any(term in normalized for term in chart_terms)


def resolve_note_path(folder: Path, candidate_labels: list[str], suffix: str) -> tuple[Path, bool]:
    preferred = folder / f"{candidate_labels[0]} - {suffix}.md"
    for label in candidate_labels:
        candidate = folder / f"{label} - {suffix}.md"
        if candidate.exists():
            return candidate, True
    return preferred, False


def partial_path_for(note_path: Path) -> Path:
    return note_path.with_name(f"{note_path.stem}.partial{note_path.suffix}")


def read_note_source(note_path: Path) -> tuple[Path | None, str | None]:
    partial_path = partial_path_for(note_path)

    if partial_path.exists():
        try:
            return partial_path, partial_path.read_text(encoding="utf-8")
        except OSError as exc:
            return partial_path, f"__READ_ERROR__:{exc}"

    if note_path.exists():
        try:
            return note_path, note_path.read_text(encoding="utf-8")
        except OSError as exc:
            return note_path, f"__READ_ERROR__:{exc}"

    return None, None


def parse_frontmatter(text: str) -> dict[str, str]:
    text = text.lstrip("\ufeff")
    if not text.startswith("---\n"):
        return {}

    end_idx = text.find("\n---\n", 4)
    if end_idx == -1:
        return {}

    metadata: dict[str, str] = {}
    for raw_line in text[4:end_idx].splitlines():
        if ":" not in raw_line:
            continue
        key, value = raw_line.split(":", 1)
        value = value.strip()
        if len(value) >= 2 and (
            (value.startswith('"') and value.endswith('"'))
            or (value.startswith("'") and value.endswith("'"))
        ):
            value = value[1:-1]
        metadata[key.strip()] = value
    return metadata


def markdown_section(text: str, heading: str) -> str:
    pattern = re.compile(rf"^{re.escape(heading)}\s*$", flags=re.MULTILINE)
    match = pattern.search(text)
    if match is None:
        return ""

    next_heading = re.search(r"^## .+", text[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.end() : end].strip()


def file_sha256(file_path: Path) -> str:
    hasher = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest().upper()


def file_modified_utc(file_path: Path) -> str:
    return datetime.fromtimestamp(file_path.stat().st_mtime, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def source_fingerprint(file_path: Path) -> tuple[str, str]:
    return file_sha256(file_path), file_modified_utc(file_path)


def manifest_needs_refresh(
    manifest_path: Path,
    *,
    pdf_path: Path,
    source_sha256: str,
    source_modified_utc: str,
) -> bool:
    if not manifest_path.exists():
        return True

    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True

    if payload.get("render_mode") != RENDER_MODE:
        return True
    if payload.get("pdf_path") != str(pdf_path):
        return True
    if payload.get("source_sha256") != source_sha256:
        return True
    if payload.get("source_modified_utc") != source_modified_utc:
        return True

    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        return True

    required_keys = {"page", "word_count", "image_count", "needs_visual_review", "image_path", "text"}
    for slide in slides:
        if not isinstance(slide, dict) or not required_keys.issubset(slide):
            return True

    return False


def digest_needs_refresh(
    digest_path: Path,
    *,
    pdf_path: Path,
    source_sha256: str,
    source_modified_utc: str,
) -> bool:
    if not digest_path.exists():
        return True

    try:
        payload = json.loads(digest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True

    if payload.get("pdf_path") != str(pdf_path):
        return True
    if payload.get("source_sha256") != source_sha256:
        return True
    if payload.get("source_modified_utc") != source_modified_utc:
        return True

    slides = payload.get("slides")
    if not isinstance(slides, list) or not slides:
        return True

    required_keys = {
        "page",
        "preview",
        "word_count",
        "image_count",
        "needs_visual_review",
        "has_formula",
        "has_table",
        "has_chart",
        "image_path",
    }
    for slide in slides:
        if not isinstance(slide, dict) or not required_keys.issubset(slide):
            return True

    return False


def prune_legacy_assets(assets_dir: Path, current_prefix: str, sequence_num: int | None) -> list[str]:
    if sequence_num is None or not assets_dir.exists():
        return []

    removed: list[str] = []
    lecture_pattern = re.compile(rf"(?:^|_)(?:week|lecture|l)0*{sequence_num}(?:_|$)")

    for asset_path in assets_dir.iterdir():
        name_lower = asset_path.name.lower()
        if name_lower.startswith(f"{current_prefix.lower()}_slide_"):
            continue
        if "_slide_" not in name_lower:
            continue
        if lecture_pattern.search(asset_path.stem.lower()):
            asset_path.unlink(missing_ok=True)
            removed.append(asset_path.name)

    return removed


def load_manifest_image_paths(manifest_path: Path) -> list[str]:
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    slide_images: list[str] = []
    for slide in payload.get("slides", []):
        image_path = slide.get("image_path") if isinstance(slide, dict) else None
        if image_path:
            slide_images.append(str(image_path))
    return slide_images


def extract_audit_fields(metadata: dict[str, str]) -> dict[str, str | None]:
    return {
        "audit_status": metadata.get("audit_status"),
        "last_audited_utc": metadata.get("last_audited_utc"),
        "last_audit_mode": metadata.get("last_audit_mode"),
        "last_audit_action": metadata.get("last_audit_action"),
        "last_audited_against_sha256": metadata.get("last_audited_against_sha256"),
    }


def analyze_detailed_note(
    note_path: Path,
    page_count: int | None,
    *,
    module_name: str | None = None,
    lecture_label: str | None = None,
    pdf_filename: str | None = None,
    source_sha256: str | None = None,
    source_modified_utc: str | None = None,
) -> tuple[str, str]:
    source_path, text = read_note_source(note_path)
    if source_path is None or text is None:
        return "missing", "file does not exist"
    if text.startswith("__READ_ERROR__:"):
        return "incomplete", text.removeprefix("__READ_ERROR__:")

    metadata = parse_frontmatter(text)
    if source_path.name.endswith(".partial.md"):
        return "incomplete", "partial file exists"
    if metadata.get("status") != "complete":
        return "incomplete", "frontmatter status is missing or not complete"
    if metadata.get("note_type") != "detailed":
        return "incomplete", "frontmatter note_type is missing or not detailed"
    if module_name and metadata.get("module") != module_name:
        return "incomplete", "frontmatter module does not match expected module"
    if lecture_label and metadata.get("lecture") != lecture_label:
        return "incomplete", "frontmatter lecture does not match expected lecture"
    if pdf_filename and metadata.get("source_pdf") != pdf_filename:
        return "incomplete", "frontmatter source_pdf does not match expected PDF"
    if source_sha256 and metadata.get("source_sha256") != source_sha256:
        return "incomplete", "frontmatter source_sha256 does not match expected PDF hash"
    if source_modified_utc and metadata.get("source_modified_utc") != source_modified_utc:
        return "incomplete", "frontmatter source_modified_utc does not match expected PDF timestamp"
    expected_page_count = page_count
    if expected_page_count is None:
        raw_page_count = metadata.get("page_count", "")
        if raw_page_count.isdigit():
            expected_page_count = int(raw_page_count)

    if expected_page_count is not None and metadata.get("page_count") != str(expected_page_count):
        return "incomplete", f"frontmatter page_count does not match expected {expected_page_count}"

    slide_nums = [int(match.group(1)) for match in re.finditer(r"^## Slide (\d+): .+", text, flags=re.MULTILINE)]
    if not slide_nums:
        return "incomplete", "no slide headings found"

    if expected_page_count is not None:
        expected = list(range(1, expected_page_count + 1))
        if slide_nums != expected:
            missing = sorted(set(expected) - set(slide_nums))
            if missing:
                return "incomplete", f"missing slide headings for pages: {missing[:10]}"
            return "incomplete", "slide headings are out of order or duplicated"

    heading_matches = list(re.finditer(r"^## Slide (\d+): .+", text, flags=re.MULTILINE))
    for idx, match in enumerate(heading_matches):
        section_start = match.end()
        section_end = heading_matches[idx + 1].start() if idx + 1 < len(heading_matches) else len(text)
        section = text[section_start:section_end]
        section = re.sub(r"!\[\[.*?\]\]", "", section)
        section = section.replace("---", "")
        section = normalize_text(section)
        if len(section) < 20:
            slide_num = match.group(1)
            return "incomplete", f"slide {slide_num} has little or no explanatory content"

    return "complete", "all slide headings present"


def analyze_summary_note(
    note_path: Path,
    *,
    module_name: str | None = None,
    lecture_label: str | None = None,
    pdf_filename: str | None = None,
    source_sha256: str | None = None,
    source_modified_utc: str | None = None,
    page_count: int | None = None,
) -> tuple[str, str]:
    source_path, text = read_note_source(note_path)
    if source_path is None or text is None:
        return "missing", "file does not exist"
    if text.startswith("__READ_ERROR__:"):
        return "incomplete", text.removeprefix("__READ_ERROR__:")

    metadata = parse_frontmatter(text)
    if source_path.name.endswith(".partial.md"):
        return "incomplete", "partial file exists"
    if metadata.get("status") != "complete":
        return "incomplete", "frontmatter status is missing or not complete"
    if metadata.get("note_type") != "summary":
        return "incomplete", "frontmatter note_type is missing or not summary"
    if module_name and metadata.get("module") != module_name:
        return "incomplete", "frontmatter module does not match expected module"
    if lecture_label and metadata.get("lecture") != lecture_label:
        return "incomplete", "frontmatter lecture does not match expected lecture"
    if pdf_filename and metadata.get("source_pdf") != pdf_filename:
        return "incomplete", "frontmatter source_pdf does not match expected PDF"
    if source_sha256 and metadata.get("source_sha256") != source_sha256:
        return "incomplete", "frontmatter source_sha256 does not match expected PDF hash"
    if source_modified_utc and metadata.get("source_modified_utc") != source_modified_utc:
        return "incomplete", "frontmatter source_modified_utc does not match expected PDF timestamp"
    if page_count is not None and metadata.get("page_count") != str(page_count):
        return "incomplete", f"frontmatter page_count does not match expected {page_count}"

    required_sections = [
        "## Overview",
        "## Key Concepts",
        "## Important Terms",
        "## Key Takeaways",
        "## Review Questions",
    ]
    missing_sections = [section for section in required_sections if section not in text]
    if missing_sections:
        return "incomplete", f"missing sections: {missing_sections}"

    for section in required_sections:
        if not normalize_text(markdown_section(text, section)):
            return "incomplete", f"section is empty: {section}"

    review_section = markdown_section(text, "## Review Questions")
    review_questions = re.findall(r"^\d+\. .+\*\*Answer:\*\* .+", review_section, flags=re.MULTILINE)
    if len(review_questions) < 5:
        return "incomplete", "fewer than 5 answered review questions found"

    return "complete", "all required summary sections present"


def render_slide_image(page, image_path: Path) -> None:
    if image_path.exists():
        return
    pix = page.get_pixmap(matrix=fitz.Matrix(SLIDE_RENDER_ZOOM, SLIDE_RENDER_ZOOM))
    pix.save(str(image_path))


def build_slide_manifest(
    pdf_path: Path,
    assets_dir: Path,
    prefix: str,
    *,
    source_sha256: str,
    source_modified_utc: str,
) -> tuple[int, Path, list[str]]:
    assets_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    slides: list[dict[str, object]] = []
    digest_slides: list[dict[str, object]] = []
    slide_images: list[str] = []

    for page_num, page in enumerate(doc, start=1):
        text = normalize_text(page.get_text("text"))
        word_count = len(re.findall(r"\w+", text))
        image_count = len(page.get_images(full=True))
        needs_visual_review = word_count < VISUAL_REVIEW_WORD_THRESHOLD or (image_count > 0 and word_count < 120)

        image_path = assets_dir / f"{prefix}_slide_{page_num:02d}.png"
        should_render_image = (
            RENDER_MODE == "all"
            or (RENDER_MODE == "selective" and needs_visual_review)
        )
        if should_render_image:
            render_slide_image(page, image_path)
            slide_images.append(str(image_path))

        has_formula = slide_contains_formula(text)
        has_table = slide_contains_table(page.get_text("text"))
        has_chart = slide_contains_chart(text, image_count)

        slides.append(
            {
                "page": page_num,
                "word_count": word_count,
                "image_count": image_count,
                "needs_visual_review": needs_visual_review,
                "image_path": str(image_path) if should_render_image else None,
                "text": text,
            }
        )
        digest_slides.append(
            {
                "page": page_num,
                "preview": slide_preview(text),
                "word_count": word_count,
                "image_count": image_count,
                "needs_visual_review": needs_visual_review,
                "has_formula": has_formula,
                "has_table": has_table,
                "has_chart": has_chart,
                "image_path": str(image_path) if should_render_image else None,
            }
        )
        print(f"  Slide {page_num}/{total} indexed", end="\r")

    doc.close()
    render_suffix = {
        "all": " and rendered all images",
        "selective": " and rendered flagged images",
    }.get(RENDER_MODE, "")
    print(f"  Indexed {total} slides{render_suffix}      ")

    manifest_path = assets_dir / f"{prefix}_slide_manifest.json"
    manifest_payload = {
        "pdf_path": str(pdf_path),
        "source_sha256": source_sha256,
        "source_modified_utc": source_modified_utc,
        "page_count": total,
        "render_mode": RENDER_MODE,
        "slides": slides,
    }
    manifest_path.write_text(json.dumps(manifest_payload, indent=2, ensure_ascii=False), encoding="utf-8")
    digest_payload = {
        "pdf_path": str(pdf_path),
        "source_sha256": source_sha256,
        "source_modified_utc": source_modified_utc,
        "page_count": total,
        "slides": digest_slides,
    }
    digest_path_for(assets_dir, prefix).write_text(
        json.dumps(digest_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return total, manifest_path, slide_images


def count_pdf_pages(pdf_path: Path) -> int:
    doc = fitz.open(str(pdf_path))
    total = len(doc)
    doc.close()
    return total


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    vault_root = find_vault_root()
    scope = {
        "module": args.module,
        "lecture": args.lecture,
        "max_files": args.max_files,
    }

    try:
        with extractor_lock(vault_root, scope):
            files, intake_issues = scan_inboxes(
                vault_root,
                apply_renames=True,
                module_filter=args.module,
                lecture_filter=args.lecture,
            )
            files = sorted(
                [file_path for file_path in files if file_matches_scope(file_path, args.module, args.lecture)],
                key=lecture_sort_key,
            )
            intake_issues = filter_intake_issues(intake_issues, args.module, args.lecture)

            for issue in intake_issues:
                print(f"Intake {issue['status']}: {issue['reason']}")

            if not files:
                if not intake_issues:
                    print("No matching PDF files found in any _inbox/ folder.")
                payload = build_extract_result(
                    intake_issues,
                    [],
                    module_filter=args.module,
                    lecture_filter=args.lecture,
                    max_files=args.max_files,
                )
                write_json_payload(payload, args.report_path)
                print("\n__EXTRACT_RESULT__")
                print(json.dumps(payload, indent=2, ensure_ascii=False))
                return

            results: list[dict[str, object]] = []

            for file_path in files:
                if len(results) >= args.max_files:
                    break

                print(f"\nProcessing: {file_path.name}")
                module_folder = file_path.parent.parent
                module_code, lecture_label, note_labels = parse_filename(file_path.name)

                detailed_folder = module_folder / "Detailed Notes"
                summaries_folder = module_folder / "Summaries"
                assets_dir = detailed_folder / "assets"
                module_toc_path = module_folder / "Module TOC.md"
                root_toc_path = vault_root / "TOC.md"
                concept_index_path = module_folder / "Concept Index.md"

                detailed_notes_path, _ = resolve_note_path(detailed_folder, note_labels, "Detailed Notes")
                summary_notes_path, _ = resolve_note_path(summaries_folder, note_labels, "Summary")
                detailed_partial_path = partial_path_for(detailed_notes_path)
                summary_partial_path = partial_path_for(summary_notes_path)

                pdf_filename = file_path.name
                pdf_path = file_path

                detailed_folder.mkdir(parents=True, exist_ok=True)
                summaries_folder.mkdir(parents=True, exist_ok=True)

                prefix = re.sub(r"[^\w]", "_", pdf_path.stem)
                manifest_path = assets_dir / f"{prefix}_slide_manifest.json"
                digest_path = digest_path_for(assets_dir, prefix)
                slide_images: list[str] = []
                page_count = count_pdf_pages(pdf_path)
                pdf_sha256, pdf_modified_utc = source_fingerprint(pdf_path)
                sequence_num = extract_sequence_number(pdf_path.stem)

                detailed_status, detailed_reason = analyze_detailed_note(
                    detailed_notes_path,
                    page_count,
                    module_name=module_folder.name,
                    lecture_label=lecture_label,
                    pdf_filename=pdf_filename,
                    source_sha256=pdf_sha256,
                    source_modified_utc=pdf_modified_utc,
                )
                summary_status, summary_reason = analyze_summary_note(
                    summary_notes_path,
                    module_name=module_folder.name,
                    lecture_label=lecture_label,
                    pdf_filename=pdf_filename,
                    source_sha256=pdf_sha256,
                    source_modified_utc=pdf_modified_utc,
                    page_count=page_count,
                )

                needs_detailed = detailed_status != "complete"
                needs_summary = summary_status != "complete"
                needs_module_toc = not module_toc_path.exists()
                needs_root_toc = not root_toc_path.exists()
                needs_concept_index = not concept_index_path.exists()
                needs_manifest = manifest_needs_refresh(
                    manifest_path,
                    pdf_path=pdf_path,
                    source_sha256=pdf_sha256,
                    source_modified_utc=pdf_modified_utc,
                )
                needs_digest = digest_needs_refresh(
                    digest_path,
                    pdf_path=pdf_path,
                    source_sha256=pdf_sha256,
                    source_modified_utc=pdf_modified_utc,
                )

                if not any(
                    (
                        needs_detailed,
                        needs_summary,
                        needs_module_toc,
                        needs_root_toc,
                        needs_concept_index,
                        needs_manifest,
                        needs_digest,
                    )
                ):
                    print("  Skipping - notes are complete and TOCs already exist.")
                    continue

                if needs_detailed or needs_manifest or needs_digest:
                    page_count, manifest_path, slide_images = build_slide_manifest(
                        pdf_path,
                        assets_dir,
                        prefix,
                        source_sha256=pdf_sha256,
                        source_modified_utc=pdf_modified_utc,
                    )
                elif RENDER_MODE in {"all", "selective"}:
                    slide_images = load_manifest_image_paths(manifest_path)

                removed_assets = prune_legacy_assets(assets_dir, prefix, sequence_num)
                if removed_assets:
                    print(f"  Removed {len(removed_assets)} stale legacy asset(s)")

                results.append(
                    {
                        "original_file": str(file_path),
                        "pdf_filename": pdf_filename,
                        "module_folder": str(module_folder),
                        "module_name": module_folder.name,
                        "module_code": module_code,
                        "lecture_label": lecture_label,
                        "detailed_folder": str(detailed_folder),
                        "summaries_folder": str(summaries_folder),
                        "source_sha256": pdf_sha256,
                        "source_modified_utc": pdf_modified_utc,
                        "detailed_notes_path": str(detailed_notes_path),
                        "detailed_partial_path": str(detailed_partial_path),
                        "summary_notes_path": str(summary_notes_path),
                        "summary_partial_path": str(summary_partial_path),
                        "module_toc_path": str(module_toc_path),
                        "root_toc_path": str(root_toc_path),
                        "concept_index_path": str(concept_index_path),
                        "page_count": page_count,
                        "manifest_path": str(manifest_path),
                        "digest_path": str(digest_path),
                        "slide_images": slide_images,
                        "detailed_status": detailed_status,
                        "detailed_status_reason": detailed_reason,
                        "summary_status": summary_status,
                        "summary_status_reason": summary_reason,
                        "needs_detailed": needs_detailed,
                        "needs_summary": needs_summary,
                        "needs_manifest": needs_manifest,
                        "needs_digest": needs_digest,
                        "needs_module_toc": needs_module_toc,
                        "needs_root_toc": needs_root_toc,
                        "needs_concept_index": needs_concept_index,
                        "detailed_audit": extract_audit_fields(parse_frontmatter(detailed_notes_path.read_text(encoding="utf-8")))
                        if detailed_notes_path.exists()
                        else extract_audit_fields({}),
                        "summary_audit": extract_audit_fields(parse_frontmatter(summary_notes_path.read_text(encoding="utf-8")))
                        if summary_notes_path.exists()
                        else extract_audit_fields({}),
                    }
                )

            payload = build_extract_result(
                intake_issues,
                results,
                module_filter=args.module,
                lecture_filter=args.lecture,
                max_files=args.max_files,
            )
            write_json_payload(payload, args.report_path)
            print("\n__EXTRACT_RESULT__")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
