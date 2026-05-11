from __future__ import annotations

import asyncio
import zipfile
from uuid import uuid4

from app.api.routes.chat import save_generated_images_from_markdown
from app.core.config import settings
from app.core.contracts import Document, DocumentCreate, PlatformFile, PlatformFileCreate
from app.files.library import (
    counted_filename,
    register_zip_entries_as_platform_files,
    zip_storage_path,
)
from app.files.processor import read_text_content


class FakeFileStore:
    def __init__(self, files: list[PlatformFile] | None = None) -> None:
        self.files = files or []
        self.documents: list[Document] = []

    def list_platform_files(self) -> list[PlatformFile]:
        return self.files

    def create_platform_file(self, payload: PlatformFileCreate) -> PlatformFile:
        platform_file = PlatformFile(
            **{
                **payload.model_dump(),
                "original_filename": payload.original_filename or payload.filename,
            }
        )
        self.files.append(platform_file)
        return platform_file

    def list_documents(self) -> list[Document]:
        return self.documents

    def create_document(self, payload: DocumentCreate) -> Document:
        document = Document(**payload.model_dump())
        self.documents.append(document)
        return document

    def update_document(self, document: Document) -> Document:
        self.documents = [
            document if existing.id == document.id else existing for existing in self.documents
        ]
        if not any(existing.id == document.id for existing in self.documents):
            self.documents.append(document)
        return document


def test_counted_filename_adds_copy_counter() -> None:
    assert counted_filename("imagem.png", {"imagem.png", "imagem (1).png"}) == "imagem (2).png"


def test_register_zip_entries_covers_chatgpt_export_assets() -> None:
    settings.ensure_local_dirs()
    archive_path = settings.cache_dir / f"chatgpt-export-{uuid4().hex}.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("conversations-000.json", "[]")
        archive.writestr("shared_conversations.json", "[]")
        archive.writestr("images/foto.png", b"fake-image")

    archive_file = PlatformFile(
        filename="chatgpt-export.zip",
        original_filename="chatgpt-export.zip",
        content_type="application/zip",
        size_bytes=archive_path.stat().st_size,
        storage_path=str(archive_path),
        source="chatgpt_import",
        tags=["chatgpt-export"],
    )
    store = FakeFileStore([archive_file])

    created_files = register_zip_entries_as_platform_files(
        archive_path=archive_path,
        archive_file=archive_file,
        store=store,
        job_id="import_test",
    )

    assert len(created_files) == 1
    assert {file.original_filename for file in store.files} >= {"images/foto.png"}
    assert "conversations-000.json" not in {file.original_filename for file in store.files}
    assert "shared_conversations.json" not in {file.original_filename for file in store.files}
    image = next(file for file in store.files if file.original_filename == "images/foto.png")
    assert image.content_type == "image/png"
    assert "image" in image.tags
    assert image.storage_path.startswith("zip://")


def test_generated_chat_image_is_registered_as_platform_file() -> None:
    store = FakeFileStore()
    content = "![resultado](data:image/png;base64,aGVsbG8=)"

    updated_content, generated_files = asyncio.run(
        save_generated_images_from_markdown(
            content,
            store,
            session_id="chat_test",
            message_id="msg_test",
            project_id="project_general",
            folder_id=None,
        )
    )

    assert len(generated_files) == 1
    assert generated_files[0].source == "generated"
    assert generated_files[0].content_type == "image/png"
    assert "/api/files/" in updated_content


def test_zip_text_entries_can_be_read_without_extraction() -> None:
    settings.ensure_local_dirs()
    archive_path = settings.cache_dir / f"text-export-{uuid4().hex}.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("notes/contexto.md", "# Olá\n\nTexto de base.")

    content = read_text_content(
        zip_storage_path(archive_path, "notes/contexto.md"),
        settings.data_dir,
    )

    assert "Texto de base" in content
