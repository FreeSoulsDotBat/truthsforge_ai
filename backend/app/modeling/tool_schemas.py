"""Schemas canônicos de argumentos das tools 3D (Fase 2, T2.3c).

Dá ao planner/LLM uma descrição precisa de **args, unidades (mm) e exemplos**
por tool, reduzindo o schema-drift LLM↔adapter (a maior fonte de fix-by-trace
no v3). A allowlist de fonte única continua sendo ``tool_registry``; este módulo
acrescenta a *forma dos argumentos* para as tools mais usadas — extensível tool
a tool conforme as ondas de cobertura.

Não substitui a validação do adapter; é material de prompt. Tools sem schema
explícito caem no ``descriptor().description`` do registry.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modeling import tool_registry


@dataclass(frozen=True)
class ArgSpec:
    description: str
    type: str = "number"
    unit: str | None = "mm"
    required: bool = True
    example: object | None = None


@dataclass(frozen=True)
class ToolSchema:
    summary: str
    args: dict[str, ArgSpec] = field(default_factory=dict)


# Schemas explícitos das tools centrais (smoke da Fase 1 + features comuns).
TOOL_SCHEMAS: dict[str, ToolSchema] = {
    "fusion.open_design": ToolSchema(
        summary="Abre/garante o documento ativo do Fusion (reusa o atual por padrão).",
        args={
            "new_document": ArgSpec(
                "Cria um documento NOVO/limpo em vez de reusar o ativo.",
                type="boolean",
                unit=None,
                required=False,
                example=False,
            ),
        },
    ),
    "fusion.create_sketch": ToolSchema(
        summary="Cria um sketch vazio num plano base.",
        args={
            "plane": ArgSpec(
                "Plano base do sketch.",
                type="string",
                unit=None,
                example="xy",
            ),
            "name": ArgSpec(
                "Nome do sketch (referenciável por outras tools).",
                type="string",
                unit=None,
                required=False,
                example="Sketch1",
            ),
        },
    ),
    "fusion.add_rectangle": ToolSchema(
        summary="Adiciona um retângulo dimensionado a um sketch.",
        args={
            "sketch": ArgSpec("Nome do sketch alvo.", type="string", unit=None, example="Sketch1"),
            "width_mm": ArgSpec("Largura em milímetros.", example=40.0),
            "height_mm": ArgSpec("Altura em milímetros.", example=20.0),
        },
    ),
    "fusion.add_circle": ToolSchema(
        summary="Adiciona um círculo a um sketch.",
        args={
            "sketch": ArgSpec("Nome do sketch alvo.", type="string", unit=None, example="Sketch1"),
            "diameter_mm": ArgSpec("Diâmetro em milímetros.", example=10.0),
        },
    ),
    "fusion.extrude_profile": ToolSchema(
        summary="Extruda um perfil de sketch num corpo sólido.",
        args={
            "sketch": ArgSpec(
                "Sketch cujo perfil será extrudado.", type="string", unit=None, example="Sketch1"
            ),
            "distance_mm": ArgSpec("Altura da extrusão em milímetros.", example=5.0),
            "operation": ArgSpec(
                "new_body | join | cut | intersect.",
                type="string",
                unit=None,
                required=False,
                example="new_body",
            ),
            "profile_index": ArgSpec(
                "Qual perfil extrudar quando o sketch tem vários (0-based). "
                "Sem isto usa o profiles[0].",
                type="integer",
                unit=None,
                required=False,
                example=0,
            ),
            "profile_diameter_mm": ArgSpec(
                "Em operation=cut, seleciona o perfil do furo pela área do círculo "
                "(diâmetro em mm) — evita cortar a peça inteira.",
                required=False,
                example=10.0,
            ),
        },
    ),
    "fusion.hole": ToolSchema(
        summary="Cria um furo numa face/plano.",
        args={
            "diameter_mm": ArgSpec("Diâmetro do furo em milímetros.", example=6.0),
            "depth_mm": ArgSpec(
                "Profundidade em milímetros (vazio = passante).", required=False, example=10.0
            ),
        },
    ),
    "fusion.fillet_edges": ToolSchema(
        summary="Arredonda arestas selecionadas com um raio.",
        args={
            "radius_mm": ArgSpec("Raio do fillet em milímetros.", example=2.0),
        },
    ),
    "fusion.set_parameter": ToolSchema(
        summary="Define um parâmetro do modelo por expressão.",
        args={
            "name": ArgSpec("Nome do parâmetro.", type="string", unit=None, example="largura"),
            "expression": ArgSpec(
                "Expressão com unidade (sintaxe do Fusion).",
                type="string",
                unit=None,
                example="40 mm",
            ),
        },
    ),
    "fusion.export_stl": ToolSchema(
        summary="Exporta o corpo/design para STL.",
        args={
            "body": ArgSpec(
                "Nome do corpo a exportar (vazio = design todo).",
                type="string",
                unit=None,
                required=False,
                example="Body1",
            ),
        },
    ),
    "fusion.validate_dimensions": ToolSchema(
        summary="Lê as dimensões reais de um corpo (read-back para verificação).",
        args={
            "body": ArgSpec(
                "Nome do corpo a medir.", type="string", unit=None, required=False, example="Body1"
            ),
        },
    ),
    "fusion.query_geometry": ToolSchema(
        summary="Lê bbox/volume/contagens/dimensões do design (read-back).",
        args={},
    ),
}


def tool_schema(tool_name: str) -> ToolSchema | None:
    return TOOL_SCHEMAS.get(tool_name)


def render_tool_schema(tool_name: str) -> str:
    """Renderiza uma linha-bloco legível pela LLM para uma tool."""
    schema = TOOL_SCHEMAS.get(tool_name)
    if schema is None:
        descriptor = tool_registry.descriptor(tool_name)
        summary = descriptor.description if descriptor and descriptor.description else tool_name
        return f"- {tool_name}: {summary}"
    lines = [f"- {tool_name}: {schema.summary}"]
    for arg, spec in schema.args.items():
        unit = f" ({spec.unit})" if spec.unit else ""
        opt = "" if spec.required else " [opcional]"
        example = "" if spec.example is None else f" ex.: {spec.example}"
        lines.append(f"    • {arg}{unit}{opt}: {spec.description}{example}")
    return "\n".join(lines)


def render_tool_schemas(tool_names: list[str]) -> str:
    """Bloco de schemas para os nomes dados (ordem preservada)."""
    return "\n".join(render_tool_schema(name) for name in tool_names)


__all__ = [
    "ArgSpec",
    "ToolSchema",
    "TOOL_SCHEMAS",
    "tool_schema",
    "render_tool_schema",
    "render_tool_schemas",
]
