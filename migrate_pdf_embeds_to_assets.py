#!/usr/bin/env python3
from __future__ import annotations

import re
from pathlib import Path
from uuid import uuid4

import fitz

from extract import find_vault_root, parse_frontmatter

SLIDE_RENDER_ZOOM = 1.5


def sanitize_prefix(name: str) -> str:
    return re.sub(r"[^\w]", "_", name)


def render_all_slide_images(pdf_path: Path, assets_dir: Path, prefix: str) -> None:
    assets_dir.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(pdf_path))
    try:
        for idx, page in enumerate(doc, start=1):
            image_path = assets_dir / f"{prefix}_slide_{idx:02d}.png"
            if image_path.exists():
                continue
            pix = page.get_pixmap(matrix=fitz.Matrix(SLIDE_RENDER_ZOOM, SLIDE_RENDER_ZOOM))
            pix.save(str(image_path))
    finally:
        doc.close()


def atomic_write_text(destination: Path, text: str) -> None:
    temp_path = destination.with_name(f"{destination.name}.{uuid4().hex}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    temp_path.replace(destination)


def replace_pdf_embeds(note_path: Path, prefix: str) -> bool:
    text = note_path.read_text(encoding="utf-8")

    def repl(match: re.Match[str]) -> str:
        page_num = int(match.group(1))
        return f"![[{prefix}_slide_{page_num:02d}.png]]"

    new_text = re.sub(r"!\[\[[^\]]+\.pdf#page=(\d+)\]\]", repl, text)
    if new_text == text:
        return False

    atomic_write_text(note_path, new_text)
    return True


def main() -> None:
    vault_root = find_vault_root()
    updated = 0

    for note_path in vault_root.rglob("Detailed Notes/*.md"):
        text = note_path.read_text(encoding="utf-8")
        metadata = parse_frontmatter(text)
        source_pdf = metadata.get("source_pdf")
        if not source_pdf:
            continue

        pdf_path = note_path.parent.parent / "_inbox" / source_pdf
        if not pdf_path.exists():
            continue

        prefix = sanitize_prefix(pdf_path.stem)
        assets_dir = note_path.parent / "assets"
        render_all_slide_images(pdf_path, assets_dir, prefix)

        if replace_pdf_embeds(note_path, prefix):
            updated += 1
            print(f"Updated embeds: {note_path}")

    print(f"Migration complete. Updated {updated} note(s).")


if __name__ == "__main__":
    main()
