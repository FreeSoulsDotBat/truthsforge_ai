from __future__ import annotations

import hashlib
import re
import shutil
from collections.abc import Iterable
from pathlib import Path

from app.core.config import settings


def safe_segment(value: str | None, fallback: str) -> str:
    candidate = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value or "").strip("._")
    return candidate[:96] or fallback


def workspace_dir(project_id: str | None, plan_id: str | None) -> Path:
    return (
        settings.modeling_dir
        / "workspaces"
        / safe_segment(project_id, "project_general")
        / safe_segment(plan_id, "ad_hoc")
    )


def snapshots_root() -> Path:
    return settings.modeling_dir / "snapshots"


def sha256_file(path: Path) -> str:
    checksum = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            checksum.update(chunk)
    return checksum.hexdigest()


SNAPSHOT_EXCLUDED_SUFFIXES = (".job.json", ".result.json")
SNAPSHOT_EXCLUDED_NAMES = {"manifest.json"}


def iter_workspace_files(workspace: Path) -> Iterable[Path]:
    """Yield workspace files that belong in a snapshot.

    Job/result manifests are recreated per execution and are not part of the
    canonical state we want to capture.
    """
    if not workspace.is_dir():
        return
    for path in workspace.rglob("*"):
        if not path.is_file():
            continue
        if path.name in SNAPSHOT_EXCLUDED_NAMES:
            continue
        if any(path.name.endswith(suffix) for suffix in SNAPSHOT_EXCLUDED_SUFFIXES):
            continue
        yield path


def copy_into_snapshot(workspace: Path, snapshot_files_dir: Path) -> list[Path]:
    """Copy workspace contents into the snapshot files directory.

    Returns the list of newly created file paths inside the snapshot dir.
    """
    snapshot_files_dir.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for source in iter_workspace_files(workspace):
        relative = source.relative_to(workspace)
        target = snapshot_files_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        copied.append(target)
    return copied


def restore_from_snapshot(snapshot_files_dir: Path, workspace: Path) -> list[Path]:
    """Mirror the snapshot file tree back into the workspace.

    The restore é um espelhamento real (clear-then-copy): primeiro remove do
    workspace os arquivos elegíveis a snapshot que NÃO constam no snapshot
    (rollback completo — sem deixar arquivos criados após o snapshot), depois
    copia/sobrescreve o conteúdo do snapshot. Arquivos efêmeros do runner em
    uso (``*.job.json``/``*.result.json``/``manifest.json``) ficam intactos.
    """
    if not snapshot_files_dir.is_dir():
        return []
    workspace.mkdir(parents=True, exist_ok=True)

    # Conjunto de paths relativos presentes no snapshot.
    snapshot_relatives = {
        source.relative_to(snapshot_files_dir)
        for source in snapshot_files_dir.rglob("*")
        if source.is_file()
    }

    # Limpa do workspace os arquivos que não pertencem ao snapshot, preservando
    # os arquivos efêmeros do runner (mesma exclusão de iter_workspace_files).
    for existing in iter_workspace_files(workspace):
        if existing.relative_to(workspace) not in snapshot_relatives:
            existing.unlink(missing_ok=True)

    restored: list[Path] = []
    for source in snapshot_files_dir.rglob("*"):
        if not source.is_file():
            continue
        relative = source.relative_to(snapshot_files_dir)
        target = workspace / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        restored.append(target)

    # Remove diretórios que ficaram vazios após a limpeza (best-effort).
    for directory in sorted(
        (p for p in workspace.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    ):
        try:
            next(directory.iterdir())
        except StopIteration:
            directory.rmdir()
        except OSError:
            continue

    return restored


def is_inside(path: Path, root: Path) -> bool:
    try:
        return path.resolve().is_relative_to(root.resolve())
    except (OSError, ValueError):
        return False
