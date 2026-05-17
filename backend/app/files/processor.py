from __future__ import annotations

import csv
import io
import zipfile
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from textwrap import shorten
from xml.etree import ElementTree

from app.core.config import settings
from app.files.library import is_zip_storage_path, parse_zip_storage_path

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import pytesseract
    from PIL import Image
except ImportError:
    pytesseract = None
    Image = None

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


@dataclass(frozen=True)
class TextExtraction:
    text: str
    mode: str
    warnings: list[str] = field(default_factory=list)


class VisibleHtmlTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.hidden_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self.hidden_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self.hidden_depth > 0:
            self.hidden_depth -= 1

    def handle_data(self, data: str) -> None:
        if self.hidden_depth == 0 and data.strip():
            self.parts.append(data.strip())


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


def _limit_text(content: str, max_chars: int | None) -> str:
    if max_chars is None:
        return content.strip()
    return content[:max_chars].strip()


def _decode_text(raw: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def _read_storage_bytes(
    storage_path: str | None, allowed_root: Path, max_bytes: int | None = None
) -> bytes:
    if not storage_path:
        return b""

    root = allowed_root.resolve()
    if is_zip_storage_path(storage_path):
        try:
            archive_path, entry_name = parse_zip_storage_path(storage_path)
        except ValueError:
            return b""
        archive_path = archive_path.resolve()
        if not archive_path.is_relative_to(root) or not archive_path.is_file():
            return b""
        try:
            with zipfile.ZipFile(archive_path) as archive:
                with archive.open(entry_name) as handle:
                    return handle.read(max_bytes) if max_bytes is not None else handle.read()
        except (KeyError, OSError, zipfile.BadZipFile):
            return b""

    path = Path(storage_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        return b""
    with path.open("rb") as handle:
        return handle.read(max_bytes) if max_bytes is not None else handle.read()


def _plain_text(raw: bytes, max_chars: int | None) -> str:
    return _limit_text(_decode_text(raw), max_chars)


def _csv_text(raw: bytes, max_chars: int | None) -> str:
    decoded = _decode_text(raw)
    rows: list[str] = []
    total_chars = 0
    for row in csv.reader(io.StringIO(decoded)):
        line = " | ".join(cell.strip() for cell in row if cell.strip()).strip()
        if line:
            rows.append(line)
            total_chars += len(line)
        if max_chars is not None and total_chars >= max_chars:
            break
    return _limit_text("\n".join(rows), max_chars)


def _html_text(raw: bytes, max_chars: int | None) -> str:
    parser = VisibleHtmlTextParser()
    parser.feed(_decode_text(raw))
    return _limit_text("\n".join(parser.parts), max_chars)


def _docx_text(raw: bytes, max_chars: int | None) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            document_xml = archive.read("word/document.xml")
    except (KeyError, zipfile.BadZipFile):
        return ""

    try:
        root = ElementTree.fromstring(document_xml)
    except ElementTree.ParseError:
        return ""

    paragraphs: list[str] = []
    total_chars = 0
    for paragraph in root.iter():
        if paragraph.tag.rsplit("}", 1)[-1] != "p":
            continue
        parts = [
            node.text.strip()
            for node in paragraph.iter()
            if node.tag.rsplit("}", 1)[-1] == "t" and node.text and node.text.strip()
        ]
        if parts:
            paragraph_text = " ".join(parts)
            paragraphs.append(paragraph_text)
            total_chars += len(paragraph_text)
        if max_chars is not None and total_chars >= max_chars:
            break
    return _limit_text("\n".join(paragraphs), max_chars)


def _pdf_text(raw: bytes, max_chars: int | None) -> TextExtraction:
    if PdfReader is None:
        return TextExtraction(text="", mode="pdf_unavailable", warnings=["pypdf_missing"])
    try:
        reader = PdfReader(io.BytesIO(raw))
    except Exception as exc:
        return TextExtraction(text="", mode="pdf_failed", warnings=[str(exc)[:120]])

    pages: list[str] = []
    total_chars = 0
    for page in reader.pages:
        try:
            page_text = page.extract_text() or ""
        except Exception:
            page_text = ""
        if page_text.strip():
            pages.append(page_text.strip())
            total_chars += len(page_text)
        if max_chars is not None and total_chars >= max_chars:
            break
    text = _limit_text("\n\n".join(pages), max_chars)
    if text:
        return TextExtraction(text=text, mode="pdf")
    return TextExtraction(text="", mode="pdf_scanned_or_empty", warnings=["pdf_text_empty"])


def _image_ocr_text(raw: bytes, max_chars: int | None) -> TextExtraction:
    if pytesseract is None or Image is None:
        return TextExtraction(text="", mode="ocr_unavailable", warnings=["ocr_dependency_missing"])
    try:
        with Image.open(io.BytesIO(raw)) as image:
            text = pytesseract.image_to_string(image, lang=settings.rag_ocr_languages)
    except Exception as exc:
        return TextExtraction(text="", mode="ocr_failed", warnings=[str(exc)[:120]])
    return TextExtraction(text=_limit_text(text, max_chars), mode="ocr")


def extract_text_content(
    storage_path: str | None,
    allowed_root: Path,
    source_type: str,
    max_chars: int | None = None,
) -> TextExtraction:
    try:
        raw = _read_storage_bytes(
            storage_path,
            allowed_root,
            None if max_chars is None else max(max_chars * 8, 1024 * 1024),
        )
    except OSError:
        return TextExtraction(text="", mode="empty")
    if not raw:
        return TextExtraction(text="", mode="empty")

    normalized_source_type = source_type.lower()
    if normalized_source_type in {"markdown", "txt", "unknown"}:
        return TextExtraction(text=_plain_text(raw, max_chars), mode="text")
    if normalized_source_type == "csv":
        return TextExtraction(text=_csv_text(raw, max_chars), mode="csv")
    if normalized_source_type == "html":
        return TextExtraction(text=_html_text(raw, max_chars), mode="html")
    if normalized_source_type == "docx":
        text = _docx_text(raw, max_chars)
        warnings = [] if text else ["docx_text_empty"]
        return TextExtraction(text=text, mode="docx", warnings=warnings)
    if normalized_source_type == "pdf":
        return _pdf_text(raw, max_chars)
    if normalized_source_type == "image":
        return _image_ocr_text(raw, max_chars)
    return TextExtraction(text=_plain_text(raw, max_chars), mode="text")


def read_text_content(
    storage_path: str | None, allowed_root: Path, max_chars: int | None = None
) -> str:
    try:
        raw = _read_storage_bytes(
            storage_path,
            allowed_root,
            None if max_chars is None else max_chars * 4,
        )
    except OSError:
        return ""
    return _plain_text(raw, max_chars)


def read_text_preview(storage_path: str | None, allowed_root: Path, max_chars: int = 1800) -> str:
    return read_text_content(storage_path, allowed_root, max_chars=max_chars)
