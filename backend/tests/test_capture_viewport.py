"""Fundação do loop visual (motor genérico): `fusion.capture_viewport`.

Renderiza o viewport e devolve a imagem (base64) para a LLM de visão criticar a
geometria vs. a intenção. Aqui validamos só o WIRING (sem Fusion); a captura
real é gate do dono. É read-only e INTERNA do loop (não é passo do planner).
"""

from __future__ import annotations

import ast

from app.modeling.fusion_mcp_scripts import (
    FUSION_SCRIPT_TOOLS,
    build_autodesk_fusion_script,
)
from app.modeling.tool_registry import (
    FUSION_TOOLS,
    PLANNER_TOOLSET,
    READ_ONLY_TOOL_NAMES,
    TOOL_REGISTRY,
    ToolCategory,
)
from app.modeling.tool_schemas import TOOL_SCHEMAS

TOOL = "fusion.capture_viewport"


def test_capture_viewport_is_wired_everywhere() -> None:
    assert TOOL in FUSION_SCRIPT_TOOLS
    assert TOOL in FUSION_TOOLS  # adapter conhece
    assert TOOL in TOOL_REGISTRY
    assert TOOL in TOOL_SCHEMAS


def test_capture_viewport_is_read_only_and_internal() -> None:
    # Read-only (não muda o modelo) e FORA do planner (probe do loop, como
    # query_timeline) — o LLM não gasta passo com render.
    assert TOOL_REGISTRY[TOOL].category is ToolCategory.read_only
    assert TOOL in READ_ONLY_TOOL_NAMES
    assert TOOL not in PLANNER_TOOLSET


def test_capture_viewport_script_uses_render_api() -> None:
    script = build_autodesk_fusion_script(
        tool_name=TOOL, arguments={"view": "iso", "width_px": 1024, "height_px": 768}
    )
    ast.parse(script)  # f-string válido
    assert "def _capture_viewport(args):" in script
    assert "saveAsImageFile" in script  # captura real do viewport
    assert "image_base64" in script  # devolve a imagem p/ a visão
    assert "ViewOrientations" in script  # orienta a câmera (iso/front/...)
    assert 'if tool_name == "fusion.capture_viewport":' in script  # dispatch
