"""Catálogo de tools MCP derivado da allowlist de fonte única (``tool_registry``).

Fase 1 usa um ``inputSchema`` permissivo por tool — os schemas ricos (args,
unidades, exemplos) entram com o asset ``tool_schemas.py`` (fidelity) na Fase
2/4. A allowlist exposta é exatamente ``FUSION_TOOLS`` (já exclui
``fusion.run_script`` — RF-023).
"""

from __future__ import annotations

import mcp.types as mtypes

from app.modeling import tool_registry
from app.modeling.fusion_adapter import FUSION_TOOLS

# Schema permissivo: aceita qualquer objeto de argumentos. Mantém a validação
# de tipo básica do SDK sem rejeitar chamadas legítimas enquanto os schemas
# por tool não existem.
_PERMISSIVE_INPUT_SCHEMA: dict = {"type": "object", "additionalProperties": True}


def build_fusion_tools() -> list[mtypes.Tool]:
    # Fonte: a allowlist executável do adapter (derivada do tool_registry, já
    # com ``fusion.run_script`` excluído — RF-023). É o mesmo conjunto que o
    # ``execute`` aceita, garantindo paridade list/call.
    tools: list[mtypes.Tool] = []
    for name in sorted(FUSION_TOOLS):
        descriptor = tool_registry.descriptor(name)
        description = (
            descriptor.description
            if descriptor and descriptor.description
            else f"Fusion 360 tool {name}."
        )
        tools.append(
            mtypes.Tool(
                name=name,
                description=description,
                inputSchema=dict(_PERMISSIVE_INPUT_SCHEMA),
            )
        )
    return tools
