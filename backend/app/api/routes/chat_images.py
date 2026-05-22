"""Persistence of images generated inside chat answers.

Extracted from the ``chat.py`` monolith (architecture-map finding "monólitos
de borda"). Handles the data-URI and remote-URL images an LLM may embed in a
markdown answer: it downloads/decodes them, stores them as platform files
(deduped + indexed) and rewrites the markdown to point at the stored copies.
"""

from __future__ import annotations

import base64
import hashlib
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.contracts import PlatformFile, PlatformFileCreate
from app.files.library import counted_filename, find_duplicate
from app.rag.indexing import ensure_document_for_platform_file
from app.workers.index_queue import enqueue_platform_file_index

DATA_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\(data:(image/[-+.\w]+);base64,([A-Za-z0-9+/=\s]+)\)")
REMOTE_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\((https?://[^)\s]+)\)")
IMAGE_EXTENSIONS = {
    "image/gif": ".gif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/svg+xml": ".svg",
    "image/webp": ".webp",
}
GENERATED_IMAGE_MAX_BYTES = 50 * 1024 * 1024


def _create_generated_image_file(
    *,
    raw: bytes,
    content_type: str,
    store,
    session_id: str,
    message_id: str,
    project_id: str,
    folder_id: str | None,
    index: int,
    existing_files: list[PlatformFile],
    existing_names: set[str],
    source_url: str | None = None,
) -> PlatformFile:
    normalized_content_type = content_type.split(";")[0].strip().lower() or "image/png"
    checksum = hashlib.sha256(raw).hexdigest()
    extension = IMAGE_EXTENSIONS.get(normalized_content_type, ".png")
    filename = counted_filename(
        f"imagem-gerada-{message_id[:8]}-{index}{extension}", existing_names
    )
    existing_names.add(filename)
    target_dir = settings.files_dir / "generated" / session_id
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / filename
    target_path.write_bytes(raw)

    duplicate = find_duplicate(
        existing_files,
        filename=filename,
        size_bytes=len(raw),
        checksum_sha256=checksum,
    )
    metadata: dict[str, Any] = {
        "session_id": session_id,
        "project_id": project_id,
        "folder_id": folder_id,
        "message_id": message_id,
        "generated_from": "chat.image",
    }
    if source_url:
        metadata["source_url"] = source_url

    platform_file = store.create_platform_file(
        PlatformFileCreate(
            filename=filename,
            original_filename=filename,
            content_type=normalized_content_type,
            size_bytes=len(raw),
            storage_path=str(target_path),
            checksum_sha256=checksum,
            duplicate_of_id=duplicate.id if duplicate else None,
            source="generated",
            tags=["generated", "image"],
            metadata=metadata,
        )
    )
    ensure_document_for_platform_file(
        store,
        platform_file,
        project_id=project_id,
        folder_id=folder_id,
        tags=["generated", "image"],
        metadata={
            "session_id": session_id,
            "message_id": message_id,
            "generated_from": "chat.image",
        },
        force_status_pending=True,
    )
    enqueue_platform_file_index(platform_file.id)
    existing_files.append(platform_file)
    return platform_file


async def _download_remote_generated_image(url: str) -> tuple[bytes, str] | None:
    try:
        async with httpx.AsyncClient(timeout=120, follow_redirects=True) as client:
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").split(";")[0].lower()
                if not content_type.startswith("image/"):
                    return None

                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > GENERATED_IMAGE_MAX_BYTES:
                        return None
                    chunks.append(chunk)
    except httpx.HTTPError:
        return None
    return b"".join(chunks), content_type


async def save_generated_images_from_markdown(
    content: str,
    store,
    *,
    session_id: str,
    message_id: str,
    project_id: str,
    folder_id: str | None,
) -> tuple[str, list[PlatformFile]]:
    data_matches = list(DATA_IMAGE_PATTERN.finditer(content))
    remote_matches = list(REMOTE_IMAGE_PATTERN.finditer(content))
    if not data_matches and not remote_matches:
        return content, []

    settings.ensure_local_dirs()
    generated_files: list[PlatformFile] = []
    existing_files = store.list_platform_files()
    existing_names = {
        platform_file.filename for platform_file in existing_files if platform_file.filename
    }
    updated_content = content

    for match in data_matches:
        content_type = match.group(1)
        try:
            raw = base64.b64decode(match.group(2), validate=False)
        except ValueError:
            continue
        platform_file = _create_generated_image_file(
            raw=raw,
            content_type=content_type,
            store=store,
            session_id=session_id,
            message_id=message_id,
            project_id=project_id,
            folder_id=folder_id,
            index=len(generated_files) + 1,
            existing_files=existing_files,
            existing_names=existing_names,
        )
        generated_files.append(platform_file)
        stored_url = f"{settings.public_base_url.rstrip('/')}/api/files/{platform_file.id}/content"
        updated_content = updated_content.replace(
            match.group(0), f"![Imagem gerada]({stored_url})", 1
        )

    local_file_prefix = f"{settings.public_base_url.rstrip('/')}/api/files/"
    for match in remote_matches:
        source_url = match.group(1)
        if source_url.startswith(local_file_prefix):
            continue
        downloaded = await _download_remote_generated_image(source_url)
        if downloaded is None:
            continue
        raw, content_type = downloaded
        platform_file = _create_generated_image_file(
            raw=raw,
            content_type=content_type,
            store=store,
            session_id=session_id,
            message_id=message_id,
            project_id=project_id,
            folder_id=folder_id,
            index=len(generated_files) + 1,
            existing_files=existing_files,
            existing_names=existing_names,
            source_url=source_url,
        )
        generated_files.append(platform_file)
        stored_url = f"{settings.public_base_url.rstrip('/')}/api/files/{platform_file.id}/content"
        updated_content = updated_content.replace(
            match.group(0), f"![Imagem gerada]({stored_url})", 1
        )

    return updated_content, generated_files


__all__ = [
    "DATA_IMAGE_PATTERN",
    "GENERATED_IMAGE_MAX_BYTES",
    "IMAGE_EXTENSIONS",
    "REMOTE_IMAGE_PATTERN",
    "save_generated_images_from_markdown",
]
