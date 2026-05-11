from __future__ import annotations

import zipfile
from pathlib import Path
from textwrap import shorten

from app.files.library import is_zip_storage_path, parse_zip_storage_path

SUPPORTED_EXTENSIONS = {
    ".pdf": "pdf",
    ".md": "markdown",
    ".markdown": "markdown",
    ".json": "txt",
    ".yaml": "txt",
    ".yml": "txt",
    ".xml": "txt",
    ".log": "txt",
    ".csv": "csv",
    ".txt": "txt",
    ".docx": "docx",
    ".png": "image",
    ".jpg": "image",
    ".jpeg": "image",
    ".webp": "image",
    ".html": "html",
    ".htm": "html",
}


def detect_source_type(path: str) -> str:
    return SUPPORTED_EXTENSIONS.get(Path(path).suffix.lower(), "unknown")


def extension_for_source_type(source_type: str) -> str:
    return {
        "markdown": ".md",
        "txt": ".txt",
        "csv": ".csv",
        "html": ".html",
    }.get(source_type, ".txt")


def chunk_text(content: str, chunk_size: int = 1200, overlap: int = 160) -> list[str]:
    normalized = "\n".join(
        line.rstrip() for line in content.replace("\r\n", "\n").split("\n")
    ).strip()
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        window = normalized[start:end]
        split_at = max(window.rfind("\n\n"), window.rfind(". "), window.rfind("\n"))
        if split_at > chunk_size * 0.45 and end < len(normalized):
            end = start + split_at + 1
            window = normalized[start:end]
        chunks.append(window.strip())
        if end >= len(normalized):
            break
        next_start = end - overlap
        start = next_start if next_start > start else end
    return [chunk for chunk in chunks if chunk]


def summarize_chunk(content: str) -> str:
    return shorten(" ".join(content.split()), width=180, placeholder="...")


def read_text_content(
    storage_path: str | None, allowed_root: Path, max_chars: int | None = None
) -> str:
    if not storage_path:
        return ""

    root = allowed_root.resolve()
    if is_zip_storage_path(storage_path):
        archive_path, entry_name = parse_zip_storage_path(storage_path)
        archive_path = archive_path.resolve()
        if not archive_path.is_relative_to(root) or not archive_path.is_file():
            return ""
        try:
            with zipfile.ZipFile(archive_path) as archive:
                with archive.open(entry_name) as handle:
                    raw = handle.read() if max_chars is None else handle.read(max_chars * 4)
            return raw.decode("utf-8")[:max_chars]
        except (KeyError, UnicodeDecodeError, zipfile.BadZipFile):
            return ""

    path = Path(storage_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return ""

    try:
        with path.open("r", encoding="utf-8") as handle:
            if max_chars is None:
                return handle.read()
            return handle.read(max_chars)
    except UnicodeDecodeError:
        return ""


def read_text_preview(storage_path: str | None, allowed_root: Path, max_chars: int = 1800) -> str:
    return read_text_content(storage_path, allowed_root, max_chars=max_chars)
