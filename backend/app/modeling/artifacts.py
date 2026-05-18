"""Artifact registration extracted from the v1 :class:`ModelingService`.

When a step output reports ``artifact_paths`` we promote each path that
lives inside ``settings.data_dir`` to:

* a :class:`PlatformFile` (so the file shows up in the "Arquivos" library
  with provenance metadata), and
* a :class:`ModelingModelVersion` (the versioned export entity used by the
  diagnostics UI and downstream consumers).

The output dict gets ``platform_file_ids`` / ``model_version_ids`` so the
executor can include them in the persisted ``ModelingToolCall``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.contracts import (
    ModelingModelVersion,
    ModelingPlan,
    ModelingPlanStep,
    PlatformFile,
    PlatformFileCreate,
)
from app.files.library import content_type_for_name, safe_filename
from app.modeling.workspace import sha256_file


ARTIFACT_CONTENT_TYPES: dict[str, str] = {
    ".3mf": "model/3mf",
    ".blend": "application/x-blender",
    ".obj": "model/obj",
    ".stl": "model/stl",
}


class ModelingArtifactService:
    """Promote step outputs into PlatformFile + ModelVersion records."""

    def __init__(self, store: Any) -> None:
        self.store = store

    def register_outputs(
        self,
        output: dict[str, Any],
        *,
        plan: ModelingPlan,
        step: ModelingPlanStep,
    ) -> dict[str, Any]:
        """Augment ``output`` with ``platform_file_ids`` / ``model_version_ids``.

        Returns the output unchanged when there is nothing to register
        (no ``artifact_paths``, store lacks the persistence methods, or
        every path is outside ``settings.data_dir``).
        """

        artifact_paths = [
            Path(raw_path).resolve()
            for raw_path in output.get("artifact_paths", [])
            if isinstance(raw_path, str) and raw_path
        ]
        if not artifact_paths or not hasattr(self.store, "create_platform_file"):
            return output

        created_or_existing: list[PlatformFile] = []
        existing_files = (
            self.store.list_platform_files() if hasattr(self.store, "list_platform_files") else []
        )
        existing_by_storage_path = {item.storage_path: item for item in existing_files}
        for path in artifact_paths:
            if not _is_path_inside_data_dir(path) or not path.is_file():
                continue
            storage_path = str(path)
            existing = existing_by_storage_path.get(storage_path)
            if existing:
                created_or_existing.append(existing)
                continue
            platform_file = self.store.create_platform_file(
                PlatformFileCreate(
                    filename=safe_filename(path.name),
                    original_filename=safe_filename(path.name),
                    content_type=_artifact_content_type(path),
                    size_bytes=path.stat().st_size,
                    storage_path=storage_path,
                    checksum_sha256=sha256_file(path),
                    source="generated",
                    tags=["3d", "modeling", step.software.value],
                    metadata={
                        "artifact_kind": "3d_model",
                        "project_id": plan.project_id,
                        "conversation_id": plan.conversation_id,
                        "plan_id": plan.id,
                        "step_id": step.id,
                        "software": step.software.value,
                        "tool_name": step.tool_name,
                    },
                )
            )
            existing_by_storage_path[storage_path] = platform_file
            created_or_existing.append(platform_file)

        if not created_or_existing:
            return output
        model_version_ids = self._register_model_versions(
            created_or_existing,
            output=output,
            plan=plan,
            step=step,
        )
        return {
            **output,
            "platform_file_ids": [platform_file.id for platform_file in created_or_existing],
            "model_version_ids": model_version_ids,
        }

    def _register_model_versions(
        self,
        files: list[PlatformFile],
        *,
        output: dict[str, Any],
        plan: ModelingPlan,
        step: ModelingPlanStep,
    ) -> list[str]:
        if not hasattr(self.store, "add_modeling_model_version"):
            return []
        existing_versions = (
            self.store.list_modeling_model_versions(project_id=plan.project_id)
            if hasattr(self.store, "list_modeling_model_versions")
            else []
        )
        existing_by_source = {
            version.source_file_id: version
            for version in existing_versions
            if version.source_file_id
        }
        version_ids: list[str] = []
        for platform_file in files:
            existing = existing_by_source.get(platform_file.id)
            if existing:
                version_ids.append(existing.id)
                continue
            version = ModelingModelVersion(
                project_id=plan.project_id,
                plan_id=plan.id,
                step_id=step.id,
                software=step.software,
                source_file_id=platform_file.id,
                file_ids=[platform_file.id],
                export_format=Path(platform_file.filename).suffix.lower().lstrip(".") or None,
                label=f"{step.software.value} export {platform_file.filename}",
                notes=str(output.get("message") or ""),
                metadata={
                    "conversation_id": plan.conversation_id,
                    "tool_name": step.tool_name,
                    "artifact_path": platform_file.storage_path,
                    "checksum_sha256": platform_file.checksum_sha256,
                },
            )
            self.store.add_modeling_model_version(version)
            version_ids.append(version.id)
        return version_ids


def _is_path_inside_data_dir(path: Path) -> bool:
    return path.is_relative_to(settings.data_dir.resolve())


def _artifact_content_type(path: Path) -> str:
    return ARTIFACT_CONTENT_TYPES.get(
        path.suffix.lower(),
        content_type_for_name(path.name) or "application/octet-stream",
    )


__all__ = [
    "ARTIFACT_CONTENT_TYPES",
    "ModelingArtifactService",
]
