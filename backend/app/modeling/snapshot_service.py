"""Snapshot/restore service extracted from the v1 :class:`ModelingService`.

ADR-013 splits the modeling backend into focused services. This module owns
the snapshot lifecycle: creating a snapshot of the canonical workspace,
restoring one back (with an automatic safety snapshot beforehand) and
writing the manifest under ``.local/modeling/snapshots/<id>/``.

The :class:`ModelingService` (now a thin facade) exposes the same public
methods (``create_snapshot`` / ``restore_snapshot``) and delegates here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.contracts import (
    AuditEvent,
    ModelingSnapshot,
    ModelingSnapshotCreate,
    ModelingSnapshotFile,
    ModelingSnapshotRestore,
    ModelingSnapshotRestoreResult,
    now_utc,
)
from app.modeling.workspace import (
    copy_into_snapshot,
    is_inside,
    restore_from_snapshot,
    safe_segment,
    sha256_file,
    snapshots_root,
    workspace_dir,
)


class ModelingSnapshotService:
    """Owns ``modeling_snapshots`` lifecycle on top of the store and filesystem."""

    def __init__(self, store: Any) -> None:
        self.store = store

    # ------------------------------------------------------------------
    # create
    # ------------------------------------------------------------------

    def create(self, payload: ModelingSnapshotCreate) -> ModelingSnapshot:
        """Create a snapshot for ``(project_id, plan_id)`` from the workspace."""

        settings.ensure_local_dirs()
        snapshot = ModelingSnapshot(
            project_id=payload.project_id,
            plan_id=payload.plan_id,
            step_id=payload.step_id,
            parent_snapshot_id=payload.parent_snapshot_id,
            label=payload.label,
            reason=payload.reason,
        )
        workspace = workspace_dir(payload.project_id, payload.plan_id)
        snapshot_dir = snapshots_root() / safe_segment(snapshot.id, "snapshot")
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        files_dir = snapshot_dir / "files"

        snapshot_files: list[ModelingSnapshotFile] = []
        if workspace.is_dir():
            copied = copy_into_snapshot(workspace, files_dir)
            for path in copied:
                relative = path.relative_to(files_dir).as_posix()
                snapshot_files.append(
                    ModelingSnapshotFile(
                        relative_path=relative,
                        sha256=sha256_file(path),
                        size_bytes=path.stat().st_size,
                    )
                )

        manifest = {
            "id": snapshot.id,
            "project_id": payload.project_id,
            "plan_id": payload.plan_id,
            "step_id": payload.step_id,
            "parent_snapshot_id": payload.parent_snapshot_id,
            "label": payload.label,
            "reason": payload.reason,
            "workspace_path": str(workspace),
            "storage_path": str(snapshot_dir),
            "created_at": snapshot.created_at.isoformat(),
            "files": [item.model_dump() for item in snapshot_files],
        }
        manifest_path = snapshot_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        snapshot = snapshot.model_copy(
            update={
                "workspace_path": str(workspace),
                "storage_path": str(snapshot_dir),
                "files": snapshot_files,
                "manifest": manifest,
            }
        )
        self.store.upsert_modeling_snapshot(snapshot)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.snapshot_created",
                metadata={
                    "snapshot_id": snapshot.id,
                    "plan_id": payload.plan_id,
                    "step_id": payload.step_id,
                    "parent_snapshot_id": payload.parent_snapshot_id,
                    "file_count": len(snapshot_files),
                },
            ),
        )
        return snapshot

    # ------------------------------------------------------------------
    # restore
    # ------------------------------------------------------------------

    def restore(
        self,
        snapshot_id: str,
        payload: ModelingSnapshotRestore | None = None,
    ) -> ModelingSnapshotRestoreResult:
        """Restore ``snapshot_id`` onto its canonical workspace.

        Unless ``payload.force`` is ``True`` an automatic snapshot of the
        current state is created first so that "undoing the undo" is just
        another restore.
        """

        if not hasattr(self.store, "get_modeling_snapshot"):
            raise RuntimeError("Backend store não implementa get_modeling_snapshot.")
        request = payload or ModelingSnapshotRestore()
        snapshot = self.store.get_modeling_snapshot(snapshot_id)
        if snapshot is None:
            raise KeyError(snapshot_id)
        if not snapshot.storage_path or not snapshot.workspace_path:
            raise ValueError(
                "Snapshot sem storage_path/workspace_path; "
                "não há conteúdo persistido para restaurar."
            )

        storage = Path(snapshot.storage_path)
        workspace = Path(snapshot.workspace_path)
        modeling_root = settings.modeling_dir
        if not is_inside(storage, modeling_root) or not is_inside(workspace, modeling_root):
            raise ValueError("Snapshot fora do diretório de modelagem; restauração bloqueada.")

        auto_snapshot: ModelingSnapshot | None = None
        if not request.force and workspace.is_dir() and any(workspace.iterdir()):
            auto_snapshot = self.create(
                ModelingSnapshotCreate(
                    project_id=snapshot.project_id,
                    plan_id=snapshot.plan_id,
                    parent_snapshot_id=snapshot.id,
                    label=f"auto: pré-restore de {snapshot.id}",
                    reason=(
                        request.reason or f"Backup automático antes de restaurar {snapshot.id}."
                    ),
                )
            )

        files_dir = storage / "files"
        if not files_dir.is_dir():
            raise ValueError(
                "Conteúdo do snapshot ausente (diretório files/ não existe); "
                "restauração abortada para não reportar sucesso silencioso."
            )
        restored_paths = restore_from_snapshot(files_dir, workspace)
        expected = len(snapshot.files or [])
        if expected and len(restored_paths) != expected:
            raise ValueError(
                "Restauração incompleta: snapshot declarava "
                f"{expected} arquivo(s) mas {len(restored_paths)} foram restaurados."
            )
        timestamp = now_utc()
        updated = snapshot.model_copy(update={"restored_at": timestamp})
        self.store.upsert_modeling_snapshot(updated)
        self.store.add_audit_event(
            AuditEvent(
                event_type="modeling.snapshot_restored",
                metadata={
                    "snapshot_id": updated.id,
                    "plan_id": updated.plan_id,
                    "step_id": updated.step_id,
                    "file_count": len(restored_paths),
                    "reason": request.reason,
                    "force": request.force,
                    "auto_snapshot_id": auto_snapshot.id if auto_snapshot else None,
                },
            ),
        )
        return ModelingSnapshotRestoreResult(
            snapshot=updated,
            auto_snapshot=auto_snapshot,
            restored_file_count=len(restored_paths),
        )


__all__ = ["ModelingSnapshotService"]
