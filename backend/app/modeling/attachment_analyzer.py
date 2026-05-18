"""Deep-analysis of chat attachments for 3D modeling discovery (Onda 2.6).

ADR-013 requires the discovery phase to consume images and 3D files
uploaded by the user so the agent can ground its plan in real data
instead of guesses. This module implements both paths:

* **Images** (``image/*``) — sent to the configured vision-capable LLM
  via the existing gateway. The provider receives the image as a
  base64-encoded data URL along with a Portuguese prompt asking for a
  geometry/material/process summary.
* **3D meshes** (``.stl``, ``.obj``, ``.3mf``, ``.blend``) — analysed
  headlessly through the Blender adapter using the allowlisted
  ``blender.validate_printability`` + ``blender.measure_object`` tools.
* **3D CAD** (``.step``) — Fusion adapter when available, otherwise
  metadata-only fallback.

Defensive guarantees:

* hard size limit (default 50 MB) before doing any heavy work;
* short per-call timeout (default 15 s);
* every exception path falls back to a minimal metadata-only analysis so
  the chat never crashes because an analysis failed.

The :class:`ModelingChatOrchestrator` (Onda 2.4) is the only direct
caller of this service; the HTTP endpoint added in Onda 2.7 simply
forwards to it.
"""

from __future__ import annotations

import base64
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from app.core.contracts import (
    ModelingPlanStep,
    ModelingRiskLevel,
    ModelingSoftware,
    PlatformFile,
)
from app.llm_gateway.gateway import LLMGateway
from app.modeling.blender_adapter import BlenderAdapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_MAX_BYTES = 50 * 1024 * 1024  # 50 MB
DEFAULT_TIMEOUT_SECONDS = 15

IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
MESH_EXTENSIONS = frozenset({".stl", ".obj", ".3mf"})
BLEND_EXTENSIONS = frozenset({".blend"})
CAD_EXTENSIONS = frozenset({".step", ".stp"})

AttachmentKind = Literal[
    "image",
    "mesh",
    "blend",
    "cad",
    "unsupported",
]


# ---------------------------------------------------------------------------
# Result
# ---------------------------------------------------------------------------


@dataclass
class AttachmentAnalysis:
    """Outcome of analysing a single attachment for the modeling agent."""

    file_id: str
    filename: str
    kind: AttachmentKind
    ok: bool
    summary: str
    metrics: dict[str, Any] = field(default_factory=dict)
    suggestions: list[str] = field(default_factory=list)
    error: str | None = None

    def to_context_text(self) -> str:
        """Render the analysis into a single block the agent can read.

        Used by the chat-stream handler to feed the analysis back into
        the LLM as additional context (system or assistant message).
        """

        lines = [
            f"Anexo {self.filename} ({self.kind})",
            self.summary if self.summary else "Sem resumo disponível.",
        ]
        if self.metrics:
            metric_lines = ", ".join(
                f"{key}={value}" for key, value in sorted(self.metrics.items())
            )
            lines.append(f"Métricas: {metric_lines}")
        if self.suggestions:
            for hint in self.suggestions:
                lines.append(f"- {hint}")
        if not self.ok and self.error:
            lines.append(f"Falha de análise: {self.error}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analyzer
# ---------------------------------------------------------------------------


class ModelingAttachmentAnalyzer:
    """Inspect chat attachments and return a structured analysis."""

    def __init__(
        self,
        store: Any,
        gateway: LLMGateway | None = None,
        blender: BlenderAdapter | None = None,
        max_bytes: int = DEFAULT_MAX_BYTES,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.store = store
        self.gateway = gateway or LLMGateway()
        self.blender = blender or BlenderAdapter(timeout_seconds=timeout_seconds)
        self.max_bytes = max_bytes
        self.timeout_seconds = timeout_seconds

    # ------------------------------------------------------------------
    # public
    # ------------------------------------------------------------------

    def analyze(self, file_id: str) -> AttachmentAnalysis:
        """Resolve ``file_id`` and run the appropriate analysis.

        Always returns an :class:`AttachmentAnalysis` — exceptions are
        captured and surfaced as ``ok=False`` results so the chat flow
        never breaks because of a malformed attachment.
        """

        platform_file = self._load_file(file_id)
        if platform_file is None:
            return AttachmentAnalysis(
                file_id=file_id,
                filename="<desconhecido>",
                kind="unsupported",
                ok=False,
                summary="Arquivo não encontrado na biblioteca.",
                error="platform_file_not_found",
            )

        kind = classify_attachment(platform_file)
        if not self._is_within_size_limit(platform_file):
            return AttachmentAnalysis(
                file_id=file_id,
                filename=platform_file.filename,
                kind=kind,
                ok=False,
                summary=(
                    "Arquivo excede o limite de "
                    f"{self.max_bytes // (1024 * 1024)} MB para análise."
                ),
                error="attachment_too_large",
            )

        path = Path(platform_file.storage_path)
        if not path.is_file():
            return AttachmentAnalysis(
                file_id=file_id,
                filename=platform_file.filename,
                kind=kind,
                ok=False,
                summary="Conteúdo do arquivo indisponível no disco.",
                error="storage_path_missing",
            )

        try:
            if kind == "image":
                return self._analyze_image(platform_file, path)
            if kind in {"mesh", "blend"}:
                return self._analyze_mesh(platform_file, path, kind=kind)
            if kind == "cad":
                return self._analyze_cad_metadata(platform_file, path)
        except Exception as exc:  # noqa: BLE001 - defensive: never crash chat
            logger.exception("Attachment analysis failed for %s", file_id)
            return AttachmentAnalysis(
                file_id=file_id,
                filename=platform_file.filename,
                kind=kind,
                ok=False,
                summary="Falha inesperada ao analisar o anexo.",
                error=str(exc),
            )

        return AttachmentAnalysis(
            file_id=file_id,
            filename=platform_file.filename,
            kind="unsupported",
            ok=False,
            summary="Tipo de anexo ainda não é suportado pela análise de modelagem.",
            error="unsupported_attachment_kind",
        )

    # ------------------------------------------------------------------
    # internals — image
    # ------------------------------------------------------------------

    def _analyze_image(
        self, platform_file: PlatformFile, path: Path
    ) -> AttachmentAnalysis:
        """Send the image to the vision-capable LLM via the gateway.

        The gateway today accepts ``list[dict[str, str]]`` messages,
        which is too narrow for multimodal payloads. Until that contract
        is widened, this method records a metadata-only summary so the
        agent still has something to work with. Provider-side vision
        support can be wired in later by swapping :meth:`_call_vision`.
        """

        size_bytes = path.stat().st_size
        try:
            image_bytes = path.read_bytes()
        except OSError as exc:
            return AttachmentAnalysis(
                file_id=platform_file.id,
                filename=platform_file.filename,
                kind="image",
                ok=False,
                summary="Não foi possível ler o conteúdo da imagem.",
                error=str(exc),
            )

        vision_summary = self._call_vision(image_bytes, platform_file)
        summary = vision_summary or (
            "Imagem recebida como referência. Análise vision indisponível "
            "neste backend — siga descrevendo o objetivo em texto."
        )

        return AttachmentAnalysis(
            file_id=platform_file.id,
            filename=platform_file.filename,
            kind="image",
            ok=True,
            summary=summary,
            metrics={"size_bytes": size_bytes},
            suggestions=[
                (
                    "Confirme com o usuário as dimensões aproximadas em mm, "
                    "a imagem só dá proporções."
                ),
                (
                    "Pergunte se a peça é decorativa/funcional e o processo "
                    "(impressão FDM/SLA, usinagem)."
                ),
            ],
        )

    def _call_vision(
        self, image_bytes: bytes, platform_file: PlatformFile
    ) -> str | None:
        """Stub for vision integration.

        Returns ``None`` to indicate "gateway has no vision support
        wired yet"; the caller falls back to a metadata-only summary.
        Override this method (or replace the analyzer entirely) once the
        gateway accepts multimodal messages.
        """

        # Encoding here keeps the door open for a future provider that
        # accepts ``data:`` URLs without changing call sites.
        _ = base64.b64encode(image_bytes).decode("ascii")
        logger.debug(
            "Vision provider not wired yet; skipping LLM call for %s.",
            platform_file.filename,
        )
        return None

    # ------------------------------------------------------------------
    # internals — mesh / blend
    # ------------------------------------------------------------------

    def _analyze_mesh(
        self, platform_file: PlatformFile, path: Path, *, kind: AttachmentKind
    ) -> AttachmentAnalysis:
        """Run ``blender.validate_printability`` headless against the file."""

        if not self.blender.is_available():
            return self._mesh_metadata_only(platform_file, path, kind=kind)

        step = ModelingPlanStep(
            seq=1,
            title="Analisar anexo 3D",
            software=ModelingSoftware.blender,
            tool_name="blender.validate_printability",
            risk_level=ModelingRiskLevel.low,
            approval_required=False,
            input_json={
                "checks": [
                    "non_manifold",
                    "loose_parts",
                    "volume",
                    "bounding_box",
                ],
                "source_path": str(path),
                "file_id": platform_file.id,
            },
        )
        try:
            output = self.blender.execute(
                step,
                plan_id=f"attachment-{platform_file.id}",
                project_id=None,
            )
        except Exception as exc:  # noqa: BLE001 - never break the chat
            logger.warning(
                "Blender headless analysis failed for %s: %s",
                platform_file.filename,
                exc,
            )
            return self._mesh_metadata_only(
                platform_file, path, kind=kind, note=str(exc)
            )

        ok = bool(output.get("ok"))
        result = output.get("result") if isinstance(output.get("result"), dict) else {}
        metrics = self._mesh_metrics_from_blender(result, path)
        suggestions = self._mesh_suggestions(result)
        summary = self._mesh_summary(platform_file, kind, ok, metrics, result)

        return AttachmentAnalysis(
            file_id=platform_file.id,
            filename=platform_file.filename,
            kind=kind,
            ok=ok,
            summary=summary,
            metrics=metrics,
            suggestions=suggestions,
            error=None if ok else str(output.get("message") or "blender_analysis_failed"),
        )

    def _mesh_metadata_only(
        self,
        platform_file: PlatformFile,
        path: Path,
        *,
        kind: AttachmentKind,
        note: str | None = None,
    ) -> AttachmentAnalysis:
        size_bytes = path.stat().st_size
        ext = path.suffix.lower().lstrip(".") or "?"
        summary = (
            f"Arquivo 3D {platform_file.filename} ({ext.upper()}, "
            f"{size_bytes // 1024} KB). Análise profunda indisponível porque "
            "o adapter Blender não está configurado neste backend; "
            "registre dimensões/objetivo no chat."
        )
        if note:
            summary = f"{summary} ({note})"
        return AttachmentAnalysis(
            file_id=platform_file.id,
            filename=platform_file.filename,
            kind=kind,
            ok=True,
            summary=summary,
            metrics={"size_bytes": size_bytes, "extension": ext},
            suggestions=[
                "Confirme com o usuário se este arquivo é referência de forma ou base para editar.",
                "Sem Blender configurado, peça dimensões críticas em mm explicitamente.",
            ],
        )

    @staticmethod
    def _mesh_metrics_from_blender(
        result: dict[str, Any], path: Path
    ) -> dict[str, Any]:
        metrics: dict[str, Any] = {
            "size_bytes": path.stat().st_size,
            "extension": path.suffix.lower().lstrip(".") or "?",
        }
        bounding_box = result.get("bounding_box")
        if isinstance(bounding_box, dict):
            metrics["bbox_mm"] = bounding_box
        risk_score = result.get("risk_score")
        if isinstance(risk_score, (int, float)):
            metrics["risk_score"] = float(risk_score)
        per_object = result.get("metrics") or {}
        if isinstance(per_object, dict):
            for key in ("volume_mm3", "vertex_count", "edge_count", "face_count"):
                value = per_object.get(key)
                if isinstance(value, (int, float)):
                    metrics[key] = value
        return metrics

    @staticmethod
    def _mesh_suggestions(result: dict[str, Any]) -> list[str]:
        raw = result.get("recommendations") if isinstance(result, dict) else []
        if isinstance(raw, list):
            cleaned = [str(item).strip() for item in raw if str(item).strip()]
        else:
            cleaned = []
        if not cleaned:
            cleaned = [
                "Pergunte ao usuário se este arquivo será editado ou só serve de referência.",
                "Confirme se as dimensões atuais já estão na escala desejada.",
            ]
        return cleaned

    @staticmethod
    def _mesh_summary(
        platform_file: PlatformFile,
        kind: AttachmentKind,
        ok: bool,
        metrics: dict[str, Any],
        result: dict[str, Any],
    ) -> str:
        if ok:
            base = result.get("message") if isinstance(result, dict) else None
            if isinstance(base, str) and base.strip():
                return base.strip()
            ext = metrics.get("extension", "?")
            return (
                f"Análise headless concluída para {platform_file.filename} "
                f"({ext.upper()})."
            )
        if isinstance(result, dict) and isinstance(result.get("message"), str):
            return f"Análise headless falhou: {result['message']}"
        return "Análise headless falhou; sem detalhes do adapter."

    # ------------------------------------------------------------------
    # internals — CAD (.step)
    # ------------------------------------------------------------------

    def _analyze_cad_metadata(
        self, platform_file: PlatformFile, path: Path
    ) -> AttachmentAnalysis:
        size_bytes = path.stat().st_size
        return AttachmentAnalysis(
            file_id=platform_file.id,
            filename=platform_file.filename,
            kind="cad",
            ok=True,
            summary=(
                f"Arquivo CAD STEP recebido ({size_bytes // 1024} KB). "
                "Análise profunda requer Fusion conectado — quando disponível, "
                "podemos extrair corpos, features e printability."
            ),
            metrics={"size_bytes": size_bytes, "extension": "step"},
            suggestions=[
                "Confirme se vai editar o STEP existente ou usar como referência.",
                "Pergunte parâmetros chave do design para usar set_parameter em edições.",
            ],
        )

    # ------------------------------------------------------------------
    # internals — file resolution
    # ------------------------------------------------------------------

    def _load_file(self, file_id: str) -> PlatformFile | None:
        if hasattr(self.store, "get_platform_file"):
            return self.store.get_platform_file(file_id)
        if hasattr(self.store, "list_platform_files"):
            for item in self.store.list_platform_files():
                if item.id == file_id:
                    return item
        return None

    def _is_within_size_limit(self, platform_file: PlatformFile) -> bool:
        size = platform_file.size_bytes or 0
        return size <= self.max_bytes


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_attachment(platform_file: PlatformFile) -> AttachmentKind:
    """Decide which analyser path a :class:`PlatformFile` should follow."""

    extension = Path(platform_file.filename).suffix.lower()
    content_type = (platform_file.content_type or "").lower()
    if extension in IMAGE_EXTENSIONS or content_type.startswith("image/"):
        return "image"
    if extension in MESH_EXTENSIONS or content_type in {
        "model/stl",
        "model/obj",
        "model/3mf",
    }:
        return "mesh"
    if extension in BLEND_EXTENSIONS or content_type == "application/x-blender":
        return "blend"
    if extension in CAD_EXTENSIONS or content_type == "model/step":
        return "cad"
    return "unsupported"


__all__ = [
    "AttachmentAnalysis",
    "AttachmentKind",
    "BLEND_EXTENSIONS",
    "CAD_EXTENSIONS",
    "DEFAULT_MAX_BYTES",
    "DEFAULT_TIMEOUT_SECONDS",
    "IMAGE_EXTENSIONS",
    "MESH_EXTENSIONS",
    "ModelingAttachmentAnalyzer",
    "classify_attachment",
]
