from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.core.contracts import ModelingPlanStep

BLENDER_TOOLS = [
    "blender.create_mesh_primitive",
    "blender.apply_bevel",
    "blender.export_stl",
]


def _safe_segment(value: str | None, fallback: str) -> str:
    candidate = re.sub(r"[^a-zA-Z0-9_.-]+", "_", value or "").strip("._")
    return candidate[:96] or fallback


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

        workspace_dir = self._workspace_dir(plan_id=plan_id, project_id=project_id)
        workspace_dir.mkdir(parents=True, exist_ok=True)
        exports_dir = workspace_dir / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        runner_path = Path(__file__).with_name("blender_runner.py")
        result_path = workspace_dir / f"{step.seq:02d}-{_safe_segment(step.tool_name, 'step')}.json"
        job_path = workspace_dir / f"{step.seq:02d}-{_safe_segment(step.id, 'job')}.job.json"
        blend_path = workspace_dir / "workspace.blend"
        job = {
            "tool_name": step.tool_name,
            "input_json": step.input_json,
            "workspace_dir": str(workspace_dir),
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
                cwd=str(workspace_dir),
                capture_output=True,
                check=False,
                shell=False,
                text=True,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            return {
                "ok": False,
                "mcp_server": "blender_mcp",
                "transport": "stdio",
                "tool_name": step.tool_name,
                "software": step.software.value,
                "message": "Execução do Blender excedeu o timeout configurado.",
                "error": str(exc),
                "input": step.input_json,
                "workspace_dir": str(workspace_dir),
            }

        result = self._read_result(result_path)
        ok = bool(result.get("ok")) and completed.returncode == 0
        message = result.get("message") or (
            "Etapa Blender executada." if ok else "Blender retornou erro na etapa."
        )
        artifact_paths = [
            str(Path(path))
            for path in result.get("artifact_paths", [])
            if isinstance(path, str) and path
        ]
        return {
            "ok": ok,
            "mcp_server": "blender_mcp",
            "transport": "stdio",
            "tool_name": step.tool_name,
            "software": step.software.value,
            "message": message,
            "input": step.input_json,
            "workspace_dir": str(workspace_dir),
            "blend_path": result.get("blend_path") or str(blend_path),
            "artifact_paths": artifact_paths,
            "returncode": completed.returncode,
            "stdout_tail": _tail(completed.stdout or ""),
            "stderr_tail": _tail(completed.stderr or ""),
            "result": result,
        }

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

    def _workspace_dir(self, *, plan_id: str | None, project_id: str | None) -> Path:
        return (
            settings.modeling_dir
            / "workspaces"
            / _safe_segment(project_id, "project_general")
            / _safe_segment(plan_id, "ad_hoc")
        )

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
