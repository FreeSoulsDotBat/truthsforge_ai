from __future__ import annotations

import mimetypes
import re
import zipfile
from pathlib import Path

from app.core.contracts import PlatformFile, PlatformFileCreate

ZIP_STORAGE_PREFIX = "zip://"
ZIP_STORAGE_SEPARATOR = "!"
CHATGPT_CONVERSATION_SHARD_PATTERN = re.compile(r"^conversations-\d+\.json$", re.IGNORECASE)
CHATGPT_INFORMATIONAL_FILES = {
    "chat.html",
    "conversations.json",
    "export_manifest.json",
    "shared_conversations.json",
    "user.json",
    "user_settings.json",
}


def safe_filename(filename: str) -> str:
    cleaned = Path(filename or "arquivo").name.replace("\x00", "").strip()
    return cleaned or "arquivo"


def content_type_for_name(filename: str) -> str | None:
    return mimetypes.guess_type(filename)[0]


def counted_filename(filename: str, existing_names: set[str]) -> str:
    safe_name = safe_filename(filename)
    existing_lower = {name.lower() for name in existing_names}
    if safe_name.lower() not in existing_lower:
        return safe_name

    path = Path(safe_name)
    stem = path.stem or "arquivo"
    suffix = path.suffix
    counter = 1
    while True:
        candidate = f"{stem} ({counter}){suffix}"
        if candidate.lower() not in existing_lower:
            return candidate
        counter += 1


def find_duplicate(
    files: list[PlatformFile],
    *,
    filename: str,
    size_bytes: int,
    checksum_sha256: str | None = None,
    content_crc: int | None = None,
) -> PlatformFile | None:
    normalized_name = safe_filename(filename).lower()
    if checksum_sha256:
        checksum_match = next(
            (
                platform_file
                for platform_file in files
                if platform_file.checksum_sha256 == checksum_sha256 and checksum_sha256
            ),
            None,
        )
        if checksum_match:
            return checksum_match

    def _name_size_match(platform_file: PlatformFile) -> bool:
        if platform_file.size_bytes != size_bytes:
            return False
        names = {
            safe_filename(platform_file.filename).lower(),
            safe_filename(platform_file.original_filename).lower(),
        }
        if not (names & {normalized_name}):
            return False
        # Quando ambos os lados expõem o CRC do conteúdo (entradas ZIP), nome+tamanho
        # iguais não bastam: só é duplicata se o CRC também bater. Evita marcar
        # arquivos distintos com mesmo nome/tamanho como duplicados.
        if content_crc is not None and isinstance(platform_file.metadata, dict):
            existing_crc = platform_file.metadata.get("zip_entry_crc")
            if existing_crc is not None and existing_crc != content_crc:
                return False
        return True

    return next(
        (platform_file for platform_file in files if _name_size_match(platform_file)),
        None,
    )


def zip_storage_path(archive_path: Path, entry_name: str) -> str:
    return f"{ZIP_STORAGE_PREFIX}{archive_path}{ZIP_STORAGE_SEPARATOR}{entry_name}"


def parse_zip_storage_path(storage_path: str) -> tuple[Path, str]:
    if not storage_path.startswith(ZIP_STORAGE_PREFIX):
        raise ValueError("storage_path não aponta para um item ZIP.")
    raw = storage_path.removeprefix(ZIP_STORAGE_PREFIX)
    archive_path, entry_name = raw.split(ZIP_STORAGE_SEPARATOR, 1)
    return Path(archive_path), entry_name


def is_image_file(platform_file: PlatformFile) -> bool:
    if platform_file.content_type and platform_file.content_type.startswith("image/"):
        return True
    return (
        safe_filename(platform_file.filename)
        .lower()
        .endswith((".apng", ".avif", ".gif", ".jpeg", ".jpg", ".png", ".svg", ".webp"))
    )


def is_zip_storage_path(storage_path: str) -> bool:
    return storage_path.startswith(ZIP_STORAGE_PREFIX)


def is_chatgpt_informational_entry(entry_name: str) -> bool:
    base_name = safe_filename(entry_name).lower()
    if base_name in CHATGPT_INFORMATIONAL_FILES:
        return True
    return CHATGPT_CONVERSATION_SHARD_PATTERN.fullmatch(base_name) is not None


def register_zip_entries_as_platform_files(
    *,
    archive_path: Path,
    archive_file: PlatformFile,
    store,
    job_id: str | None = None,
) -> list[PlatformFile]:
    existing_files = store.list_platform_files()
    existing_storage_paths = {platform_file.storage_path for platform_file in existing_files}
    existing_names = {
        platform_file.filename for platform_file in existing_files if platform_file.filename
    }
    archive_metadata = (
        dict(archive_file.metadata) if isinstance(archive_file.metadata, dict) else {}
    )
    archive_project_id = archive_metadata.get("project_id")
    archive_folder_id = archive_metadata.get("folder_id")
    archive_session_id = archive_metadata.get("session_id")
    created_files: list[PlatformFile] = []

    try:
        archive = zipfile.ZipFile(archive_path)
    except zipfile.BadZipFile:
        return []

    with archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            if is_chatgpt_informational_entry(info.filename):
                continue
            storage_path = zip_storage_path(archive_path, info.filename)
            if storage_path in existing_storage_paths:
                continue

            base_name = safe_filename(info.filename)
            filename = counted_filename(base_name, existing_names)
            existing_names.add(filename)
            content_type = content_type_for_name(info.filename)
            tags = ["chatgpt-export-entry"]
            if content_type and content_type.startswith("image/"):
                tags.append("image")
            if base_name.lower().startswith("conversations"):
                tags.append("chatgpt-history")

            duplicate = find_duplicate(
                existing_files,
                filename=base_name,
                size_bytes=info.file_size,
                content_crc=info.CRC,
            )
            payload = PlatformFileCreate(
                filename=filename,
                original_filename=info.filename,
                content_type=content_type,
                size_bytes=info.file_size,
                storage_path=storage_path,
                duplicate_of_id=duplicate.id if duplicate else None,
                source="chatgpt_import",
                tags=tags,
                metadata={
                    "archive_file_id": archive_file.id,
                    "archive_filename": archive_file.filename,
                    "job_id": job_id,
                    "zip_entry": info.filename,
                    "zip_entry_crc": info.CRC,
                    "compressed_size": info.compress_size,
                    "from_archive": True,
                    "project_id": archive_project_id,
                    "folder_id": archive_folder_id,
                    "session_id": archive_session_id,
                },
            )
            created_file = store.create_platform_file(payload)
            existing_files.append(created_file)
            existing_storage_paths.add(storage_path)
            created_files.append(created_file)

    return created_files
