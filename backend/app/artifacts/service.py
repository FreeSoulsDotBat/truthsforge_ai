from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ArtifactDescriptor:
    title: str
    artifact_type: str
    export_formats: tuple[str, ...] = ("markdown", "html", "pdf", "docx", "pptx", "json")
