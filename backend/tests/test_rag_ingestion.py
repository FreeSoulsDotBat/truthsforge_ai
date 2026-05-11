import shutil
from uuid import uuid4

from app.core.config import settings
from app.files.processor import (
    chunk_text,
    detect_source_type,
    extension_for_source_type,
    read_text_preview,
)
from app.rag.embeddings import VECTOR_SIZE, embed_text


def test_document_type_detection_and_extension_mapping() -> None:
    assert detect_source_type("notes.md") == "markdown"
    assert detect_source_type("report.unknown") == "unknown"
    assert extension_for_source_type("markdown") == ".md"
    assert extension_for_source_type("txt") == ".txt"


def test_chunk_text_splits_large_content() -> None:
    content = "A verdade precisa de contexto. " * 140
    chunks = chunk_text(content, chunk_size=400, overlap=40)

    assert len(chunks) > 1
    assert all(chunk.strip() for chunk in chunks)


def test_local_embedding_is_stable_and_normalized() -> None:
    first = embed_text("JUDITE organiza contexto")
    second = embed_text("JUDITE organiza contexto")

    assert first == second
    assert len(first) == VECTOR_SIZE
    assert any(value != 0 for value in first)


def test_text_preview_is_limited_to_storage_root() -> None:
    settings.ensure_local_dirs()
    temp_root = settings.cache_dir / "tests" / f"preview-{uuid4().hex}"
    allowed_root = temp_root / "files"
    try:
        allowed_root.mkdir(parents=True)
        safe_file = allowed_root / "doc.txt"
        unsafe_file = temp_root / "outside.txt"
        safe_file.write_text("abc" * 1000, encoding="utf-8")
        unsafe_file.write_text("fora", encoding="utf-8")

        assert read_text_preview(str(safe_file), allowed_root, max_chars=6) == "abcabc"
        assert read_text_preview(str(unsafe_file), allowed_root) == ""
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
