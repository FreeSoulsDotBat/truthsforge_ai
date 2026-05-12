import shutil
import zipfile
from uuid import uuid4

from fastapi.testclient import TestClient

from app.core.config import settings
from app.files.processor import (
    chunk_text,
    detect_source_type,
    extension_for_source_type,
    extract_text_content,
    read_text_preview,
)
from app.main import app
from app.rag.embeddings import VECTOR_SIZE, embed_text, embedding_backend_name, embedding_model_name
from app.rag.vector_store import QdrantVectorStore


def test_document_type_detection_and_extension_mapping() -> None:
    assert detect_source_type("notes.md") == "markdown"
    assert detect_source_type("dados.csv") == "csv"
    assert detect_source_type("pagina.html") == "html"
    assert detect_source_type("relatorio.docx") == "docx"
    assert detect_source_type("scan.pdf") == "pdf"
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
    assert embedding_backend_name() in {"sentence_transformers", "hash_fallback"}
    assert embedding_model_name()


def test_extract_text_content_parses_csv_html_and_docx() -> None:
    settings.ensure_local_dirs()
    temp_root = settings.cache_dir / "tests" / f"extract-{uuid4().hex}"
    try:
        temp_root.mkdir(parents=True)
        csv_file = temp_root / "dados.csv"
        html_file = temp_root / "pagina.html"
        docx_file = temp_root / "relatorio.docx"
        csv_file.write_text("nome,valor\nJUDITE,42\n", encoding="utf-8")
        html_file.write_text(
            (
                "<html><head><style>.x{}</style></head><body>"
                "<h1>Título</h1><script>bad()</script><p>Conteúdo útil</p>"
                "</body></html>"
            ),
            encoding="utf-8",
        )
        with zipfile.ZipFile(docx_file, "w") as archive:
            archive.writestr(
                "word/document.xml",
                (
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    "<w:body><w:p><w:r><w:t>Contrato importante</w:t></w:r></w:p></w:body>"
                    "</w:document>"
                ),
            )

        csv_text = extract_text_content(str(csv_file), temp_root, "csv")
        html_text = extract_text_content(str(html_file), temp_root, "html")
        docx_text = extract_text_content(str(docx_file), temp_root, "docx")

        assert csv_text.mode == "csv"
        assert "nome | valor" in csv_text.text
        assert "JUDITE | 42" in csv_text.text
        assert html_text.mode == "html"
        assert "Título" in html_text.text
        assert "Conteúdo útil" in html_text.text
        assert "bad()" not in html_text.text
        assert docx_text.mode == "docx"
        assert "Contrato importante" in docx_text.text
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)


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


def test_document_search_falls_back_to_metadata_filters_when_vector_store_is_unavailable(
    monkeypatch,
) -> None:
    async def unavailable_search(self, collection, vector, limit=8, payload_filter=None):
        raise RuntimeError("qdrant offline")

    monkeypatch.setattr(QdrantVectorStore, "search", unavailable_search)
    client = TestClient(app)
    created = client.post(
        "/api/documents/text",
        json={
            "title": f"Contrato Alpha {uuid4().hex}",
            "content": "clausula confidencial sobre alpha",
            "source_type": "txt",
            "tags": ["contratos"],
        },
    )
    assert created.status_code == 200

    response = client.post(
        "/api/documents/search",
        json={
            "query": "Contrato Alpha",
            "limit": 5,
            "tags": ["contratos"],
            "source_types": ["txt"],
        },
    )

    assert response.status_code == 200
    results = response.json()
    assert any(result["document_id"] == created.json()["id"] for result in results)
    matched = next(result for result in results if result["document_id"] == created.json()["id"])
    assert matched["metadata"]["match_mode"] == "metadata"
