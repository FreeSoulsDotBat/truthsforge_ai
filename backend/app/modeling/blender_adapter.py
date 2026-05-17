from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.contracts import ModelingErrorEnvelope, ModelingPlanStep
from app.modeling.tool_registry import BLENDER_TOOLS as _REGISTRY_BLENDER_TOOLS
from app.modeling.workspace import safe_segment, workspace_dir

# ``BLENDER_TOOLS`` is derived from :mod:`app.modeling.tool_registry`
# (ADR-013) and intentionally **excludes** ``blender.run_script`` — the
# adapter must never receive a free-script step, even if the registry
# describes it for audit/policy purposes. The legacy export below is kept
# so callers that import ``BLENDER_TOOLS`` from this module keep working.
BLENDER_TOOLS = [name for name in _REGISTRY_BLENDER_TOOLS if name != "blender.run_script"]


def _tail(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return value[-limit:]


@dataclass(frozen=True)
class BlenderAdapterStatus:
    connected: bool
    transport: str
    status: str
    detail: str
    executable: str | None = None


class BlenderAdapter:
    """Executes a small allowlisted Blender tool surface via background Python.

    This is intentionally not a generic "run arbitrary Python in Blender" bridge.
    The LLM/planner can only select tool names that the runner implements.
    """

    tools = BLENDER_TOOLS

    def __init__(
        self,
        executable: str | None = None,
        timeout_seconds: int | None = None,
    ) -> None:
        self._configured_executable = (
            executable if executable is not None else settings.blender_executable
        )
        self.timeout_seconds = timeout_seconds or settings.modeling_subprocess_timeout_seconds

    def status(self) -> BlenderAdapterStatus:
        executable = self._resolve_executable()
        if not executable:
            detail = (
                "Blender não encontrado. Defina TRUTHS_FORGE_BLENDER_EXECUTABLE "
                "ou adicione o comando blender ao PATH para ativar execução real."
            )
            return BlenderAdapterStatus(
                connected=False,
                transport="mock",
                status="adapter_mock",
                detail=detail,
            )
        return BlenderAdapterStatus(
            connected=True,
            transport="stdio",
            status="available",
            detail="Blender encontrado; execução real usa subprocesso local em background.",
            executable=str(executable),
        )

    def is_available(self) -> bool:
        return self.status().connected

    def execute(
        self,
        step: ModelingPlanStep,
        *,
        plan_id: str | None = None,
        project_id: str | None = None,
    ) -> dict[str, Any]:
        executable = self._resolve_executable()
        if executable is None:
            raise RuntimeError("Blender executable is not configured.")
        if step.tool_name not in self.tools:
            raise ValueError(f"Ferramenta Blender não permitida: {step.tool_name}")

        workspace = workspace_dir(project_id, plan_id)
        workspace.mkdir(parents=True, exist_ok=True)
        exports_dir = workspace / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        runner_path = Path(__file__).with_name("blender_runner.py")
        slot = f"{step.seq:02d}-{safe_segment(step.tool_name, 'step')}"
        result_path = workspace / f"{slot}.result.json"
        job_path = workspace / f"{step.seq:02d}-{safe_segment(step.id, 'job')}.job.json"
        blend_path = workspace / "workspace.blend"
        job = {
            "tool_name": step.tool_name,
            "input_json": step.input_json,
            "workspace_dir": str(workspace),
            "exports_dir": str(exports_dir),
            "blend_path": str(blend_path),
            "result_path": str(result_path),
        }
        job_path.write_text(json.dumps(job, ensure_ascii=False, indent=2), encoding="utf-8")

        command = [
            str(executable),
            "--background",
            "--python",
            str(runner_path),
            "--",
            str(job_path),
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(workspace),
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            envelope = ModelingErrorEnvelope(
                error_code="blender.timeout",
                message="Execução do Blender excedeu o timeout configurado.",
                retryable=True,
                safe_to_retry_after_snapshot_restore=True,
                host_details={
                    "software": step.software.value,
                    "workspace_dir": str(workspace),
                    "timeout_seconds": self.timeout_seconds,
                    "error": str(exc),
                },
            )
            return self._envelope_output(step, envelope, workspace=workspace)

        result = self._read_result(result_path)
        ok = bool(result.get("ok")) and completed.returncode == 0
        artifact_paths = [
            str(Path(path))
            for path in result.get("artifact_paths", [])
            if isinstance(path, str) and path
        ]
        if not ok:
            envelope = ModelingErrorEnvelope(
                error_code=str(result.get("error_code") or "blender.runner_failed"),
                message=str(result.get("message") or "Blender retornou erro na etapa."),
                retryable=bool(result.get("retryable", False)),
                safe_to_retry_after_snapshot_restore=bool(
                    result.get("safe_to_retry_after_snapshot_restore", True)
                ),
                host_details={
                    "software": step.software.value,
                    "workspace_dir": str(workspace),
                    "returncode": completed.returncode,
                    "stdout_tail": _tail(completed.stdout or ""),
                    "stderr_tail": _tail(completed.stderr or ""),
                },
            )
            return self._envelope_output(
                step,
                envelope,
                workspace=workspace,
                extra={
                    "input": step.input_json,
                    "blend_path": result.get("blend_path") or str(blend_path),
                    "artifact_paths": artifact_paths,
                    "result": result,
                },
            )
        return {
            "ok": True,
            "mcp_server": "blender_mcp",
            "transport": "stdio",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "message": result.get("message") or "Etapa Blender executada.",
            "input": step.input_json,
            "workspace_dir": str(workspace),
            "blend_path": result.get("blend_path") or str(blend_path),
            "artifact_paths": artifact_paths,
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout or ""),
            "stderr_tail": _tail(completed.stderr or ""),
            "result": result,
        }

    @staticmethod
    def _envelope_output(
        step: ModelingPlanStep,
        envelope: ModelingErrorEnvelope,
        *,
        workspace: Path,
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        base: dict[str, Any] = {
            "ok": False,
            "mcp_server": "blender_mcp",
            "transport": "stdio",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "input": step.input_json,
            "workspace_dir": str(workspace),
        }
        if extra:
            base.update(extra)
        return {**base, **envelope.model_dump(), "message": envelope.message}

    def _resolve_executable(self) -> Path | None:
        configured = (self._configured_executable or "").strip()
        if configured:
            path = Path(configured)
            if path.is_file():
                return path
            found = shutil.which(configured)
            return Path(found) if found else None
        found = shutil.which("blender") or shutil.which("blender.exe")
        return Path(found) if found else None

    @staticmethod
    def _read_result(result_path: Path) -> dict[str, Any]:
        if not result_path.is_file():
            return {
                "ok": False,
                "message": "Blender não escreveu arquivo de resultado.",
            }
        try:
            raw = json.loads(result_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return {
                "ok": False,
                "message": "Resultado do Blender não pôde ser lido.",
                "error": str(exc),
            }
        return raw if isinstance(raw, dict) else {"ok": False, "result": raw}
