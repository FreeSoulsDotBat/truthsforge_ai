"""Catálogo de tools MCP derivado da allowlist de fonte única (``tool_registry``).

Fase 1 usa um ``inputSchema`` permissivo por tool — os schemas ricos (args,
unidades, exemplos) entram com o asset ``tool_schemas.py`` (fidelity) na Fase
2/4. A allowlist exposta é ``FUSION_TOOLS`` (já exclui ``fusion.run_script``
— RF-023) filtrada pelos handlers executáveis do script (paridade list/call).
"""

from __future__ import annotations

import mcp.types as mtypes

from app.modeling import tool_registry
from app.modeling.fusion_adapter import FUSION_TOOLS

# Schema permissivo: aceita qualquer objeto de argumentos. Mantém a validação
# de tipo básica do SDK sem rejeitar chamadas legítimas enquanto os schemas
# por tool não existem.
_PERMISSIVE_INPUT_SCHEMA: dict = {"type": "object", "additionalProperties": True}


def executable_fusion_tools() -> tuple[str, ...]:
    """Interseção registry × handlers do script (paridade list/call real),
    SEM tools destrutivas/high-risk.

    ``FUSION_TOOLS`` pode conter tools registradas sem handler executável
    (ex.: ``fusion.relate_bodies``, UNRELEASED — o resolver F7 a expande
    ANTES do dispatch). Expor essas tools no ``tools/list`` fazia clientes
    externos receberem ``fusion.autodesk_mcp_error`` ao invocá-las, além de
    penalizar a saúde do adapter.

    A exclusão de destrutivas/high-risk é específica do servidor MCP
    standalone (única superfície que consome esta função): ele NÃO tem
    humano no circuito, e a constituição exige aprovação humana para ações
    destrutivas — o gate vive na camada orchestrator/service do backend.
    Anunciar ``fusion.delete_body``/``fusion.rollback_timeline`` aqui
    permitiria a qualquer cliente com o Bearer token executar destrutivo
    sem gate. ``execute_fusion_tool`` aplica a mesma recusa na execução
    (defesa em profundidade).
    """

    from app.modeling.fusion_mcp_scripts import FUSION_SCRIPT_TOOLS

    script_tools = set(FUSION_SCRIPT_TOOLS)
    return tuple(
        name
        for name in FUSION_TOOLS
        if name in script_tools
        and not tool_registry.is_destructive(name)
        and not tool_registry.is_high_risk(name)
    )


def build_fusion_tools() -> list[mtypes.Tool]:
    # Fonte: a allowlist executável do adapter (derivada do tool_registry, já
    # com ``fusion.run_script`` excluído — RF-023) filtrada pelos handlers
    # reais do script, garantindo paridade list/call.
    tools: list[mtypes.Tool] = []
    for name in sorted(executable_fusion_tools()):
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
