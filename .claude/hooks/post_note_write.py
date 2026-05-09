#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import sys
from pathlib import Path


def read_input() -> dict[str, object]:
    try:
        return json.load(sys.stdin)
    except json.JSONDecodeError:
        return {}


def validate_note_file(file_path: Path) -> list[str]:
    if not file_path.exists():
        return []
    if file_path.suffix.lower() != ".md":
        return []

    normalized = str(file_path).replace("\\", "/")
    is_detailed = "/Detailed Notes/" in normalized and not normalized.endswith(".partial.md")
    is_summary = "/Summaries/" in normalized and not normalized.endswith(".partial.md")
    if not (is_detailed or is_summary):
        return []

    text = file_path.read_text(encoding="utf-8")
    issues: list[str] = []
    if not text.startswith("---\n"):
        issues.append("notes should start with YAML frontmatter")
        return issues
    if "status: complete" not in text:
        issues.append("final note is missing `status: complete`")
    if is_detailed and "note_type: detailed" not in text:
        issues.append("detailed note is missing `note_type: detailed`")
    if is_summary and "note_type: summary" not in text:
        issues.append("summary note is missing `note_type: summary`")
    if is_detailed and re.search(r"!\[\[[^\]]+\.pdf#page=\d+\]\]", text):
        issues.append("detailed notes must embed rendered slide images, not PDF page embeds")
    return issues


def main() -> None:
    payload = read_input()
    tool_input = payload.get("tool_input", {})
    file_path = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(file_path, str):
        sys.exit(0)

    issues = validate_note_file(Path(file_path))
    if issues:
        for issue in issues:
            print(f"• {issue}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
