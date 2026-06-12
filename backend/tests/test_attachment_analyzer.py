"""Tests for the modeling attachment analyzer (Onda 2.6, ADR-013)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from app.core.contracts import PlatformFile
from app.modeling.attachment_analyzer import (
    DEFAULT_MAX_BYTES,
    AttachmentAnalysis,
    ModelingAttachmentAnalyzer,
    classify_attachment,
)

# ---------------------------------------------------------------------------
# Test doubles
# ---------------------------------------------------------------------------


@dataclass
class _FakeStore:
    files: dict[str, PlatformFile] = field(default_factory=dict)

    def get_platform_file(self, file_id: str) -> PlatformFile | None:
        return self.files.get(file_id)


@dataclass
class _FakeBlender:
    available: bool = True
    last_step: Any = None
    response: dict[str, Any] = field(
        default_factory=lambda: {
            "ok": True,
            "message": "Blender real executou validate_printability.",
            "result": {
                "bounding_box": {"x_mm": 40.0, "y_mm": 20.0, "z_mm": 10.0},
                "risk_score": 0.1,
                "metrics": {"vertex_count": 24, "face_count": 12, "volume_mm3": 8000},
                "recommendations": ["Confirme escala em milímetros."],
            },
        }
    )
    raise_on_execute: bool = False

    def is_available(self) -> bool:
        return self.available

    def execute(self, step: Any, *, plan_id: Any, project_id: Any) -> dict[str, Any]:
        self.last_step = step
        if self.raise_on_execute:
            raise RuntimeError("blender headless boom")
        return self.response


def _make_platform_file(
    tmp_path: Path,
    *,
    filename: str,
    content: bytes = b"",
    content_type: str | None = None,
) -> PlatformFile:
    storage = tmp_path / filename
    storage.write_bytes(content)
    return PlatformFile(
        filename=filename,
        original_filename=filename,
        content_type=content_type,
        size_bytes=len(content),
        storage_path=str(storage),
        source="chat_attachment",
    )


def _analyzer(store: _FakeStore, blender: _FakeBlender) -> ModelingAttachmentAnalyzer:
    return ModelingAttachmentAnalyzer(
        store=store,
        gateway=None,
        blender=blender,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# classify_attachment
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "filename,content_type,expected",
    [
        ("ref.png", None, "image"),
        ("ref.JPG", None, "image"),
        ("plain.txt", "image/png", "image"),
        ("part.stl", None, "mesh"),
        ("part.OBJ", None, "mesh"),
        ("part.3mf", "model/3mf", "mesh"),
        ("scene.blend", None, "blend"),
        ("scene.bin", "application/x-blender", "blend"),
        ("design.step", None, "cad"),
        ("design.stp", None, "cad"),
        ("notes.md", None, "unsupported"),
    ],
)
def test_classify_attachment(filename: str, content_type: str | None, expected: str) -> None:
    pf = PlatformFile(
        filename=filename,
        original_filename=filename,
        content_type=content_type,
        size_bytes=0,
        storage_path=f"/tmp/{filename}",
    )
    assert classify_attachment(pf) == expected


# ---------------------------------------------------------------------------
# analyze() — error paths
# ---------------------------------------------------------------------------


def test_analyze_returns_unsupported_when_file_missing(tmp_path: Path) -> None:
    store = _FakeStore()
    analyzer = _analyzer(store, _FakeBlender())

    result = analyzer.analyze("file_unknown")

    assert result.ok is False
    assert result.kind == "unsupported"
    assert result.error == "platform_file_not_found"


def test_analyze_rejects_files_larger_than_limit(tmp_path: Path) -> None:
    store = _FakeStore()
    pf = _make_platform_file(tmp_path, filename="huge.png", content=b"x" * 100)
    pf = pf.model_copy(update={"size_bytes": DEFAULT_MAX_BYTES + 1})
    store.files[pf.id] = pf
    analyzer = _analyzer(store, _FakeBlender())

    result = analyzer.analyze(pf.id)

    assert result.ok is False
    assert result.error == "attachment_too_large"


def test_analyze_handles_missing_storage_path(tmp_path: Path) -> None:
    store = _FakeStore()
    pf = PlatformFile(
        filename="missing.stl",
        original_filename="missing.stl",
        content_type="model/stl",
        size_bytes=100,
        storage_path=str(tmp_path / "does-not-exist.stl"),
    )
    store.files[pf.id] = pf
    analyzer = _analyzer(store, _FakeBlender())

    result = analyzer.analyze(pf.id)

    assert result.ok is False
    assert result.error == "storage_path_missing"


# ---------------------------------------------------------------------------
# analyze() — image path
# ---------------------------------------------------------------------------


def test_analyze_image_returns_metadata_summary_without_vision(tmp_path: Path) -> None:
    store = _FakeStore()
    pf = _make_platform_file(
        tmp_path, filename="ref.png", content=b"PNGDATA", content_type="image/png"
    )
    store.files[pf.id] = pf
    analyzer = _analyzer(store, _FakeBlender())

    result = analyzer.analyze(pf.id)

    assert result.ok is True
    assert result.kind == "image"
    assert "vision" in result.summary.lower() or "imagem" in result.summary.lower()
    assert result.metrics["size_bytes"] == len(b"PNGDATA")
    assert result.suggestions  # non-empty


# ---------------------------------------------------------------------------
# analyze() — mesh path
# ---------------------------------------------------------------------------


def test_analyze_mesh_calls_blender_with_validate_printability(tmp_path: Path) -> None:
    store = _FakeStore()
    pf = _make_platform_file(
        tmp_path, filename="part.stl", content=b"solid stl", content_type="model/stl"
    )
    store.files[pf.id] = pf
    blender = _FakeBlender()
    analyzer = _analyzer(store, blender)

    result = analyzer.analyze(pf.id)

    assert blender.last_step is not None
    assert blender.last_step.tool_name == "blender.validate_printability"
    assert blender.last_step.input_json["source_path"] == pf.storage_path
    assert result.ok is True
    assert result.kind == "mesh"
    assert result.metrics["bbox_mm"]["x_mm"] == 40.0
    assert result.metrics["vertex_count"] == 24
    assert "Confirme escala" in result.suggestions[0]


def test_analyze_mesh_falls_back_to_metadata_when_blender_unavailable(
    tmp_path: Path,
) -> None:
    store = _FakeStore()
    pf = _make_platform_file(
        tmp_path, filename="part.stl", content=b"solid", content_type="model/stl"
    )
    store.files[pf.id] = pf
    blender = _FakeBlender(available=False)
    analyzer = _analyzer(store, blender)

    result = analyzer.analyze(pf.id)

    assert result.ok is True
    assert result.kind == "mesh"
    assert "Blender" in result.summary
    assert result.metrics["extension"] == "stl"


def test_analyze_mesh_captures_blender_exceptions(tmp_path: Path) -> None:
    store = _FakeStore()
    pf = _make_platform_file(tmp_path, filename="part.stl", content=b"x", content_type="model/stl")
    store.files[pf.id] = pf
    blender = _FakeBlender(raise_on_execute=True)
    analyzer = _analyzer(store, blender)

    result = analyzer.analyze(pf.id)

    # Even when blender blows up the result must be ok=True (metadata
    # fallback path), so the chat flow can keep going.
    assert result.ok is True
    assert result.kind == "mesh"
    assert "Blender" in result.summary


def test_analyze_mesh_marks_failure_when_blender_returns_ok_false(
    tmp_path: Path,
) -> None:
    store = _FakeStore()
    pf = _make_platform_file(tmp_path, filename="part.stl", content=b"x", content_type="model/stl")
    store.files[pf.id] = pf
    blender = _FakeBlender(
        response={
            "ok": False,
            "message": "validate_printability falhou",
            "result": {},
        }
    )
    analyzer = _analyzer(store, blender)

    result = analyzer.analyze(pf.id)

    assert result.ok is False
    assert "falhou" in result.summary or "falha" in result.summary.lower()


# ---------------------------------------------------------------------------
# analyze() — CAD path
# ---------------------------------------------------------------------------


def test_analyze_cad_step_returns_metadata_summary(tmp_path: Path) -> None:
    store = _FakeStore()
    pf = _make_platform_file(
        tmp_path,
        filename="design.step",
        content=b"ISO-10303-21",
        content_type="model/step",
    )
    store.files[pf.id] = pf
    analyzer = _analyzer(store, _FakeBlender())

    result = analyzer.analyze(pf.id)

    assert result.ok is True
    assert result.kind == "cad"
    assert "STEP" in result.summary
    assert result.metrics["extension"] == "step"


# ---------------------------------------------------------------------------
# AttachmentAnalysis.to_context_text
# ---------------------------------------------------------------------------


def test_to_context_text_includes_summary_metrics_and_suggestions() -> None:
    analysis = AttachmentAnalysis(
        file_id="f1",
        filename="part.stl",
        kind="mesh",
        ok=True,
        summary="OK",
        metrics={"size_bytes": 1024, "vertex_count": 100},
        suggestions=["confirme escala"],
    )
    text = analysis.to_context_text()
    assert "part.stl" in text
    assert "mesh" in text
    assert "size_bytes=1024" in text
    assert "confirme escala" in text


def test_to_context_text_reports_error_when_not_ok() -> None:
    analysis = AttachmentAnalysis(
        file_id="f1",
        filename="big.stl",
        kind="mesh",
        ok=False,
        summary="muito grande",
        error="attachment_too_large",
    )
    text = analysis.to_context_text()
    assert "Falha de análise" in text
    assert "attachment_too_large" in text
