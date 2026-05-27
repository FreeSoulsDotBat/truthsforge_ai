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
            "expected_dimensions_mm": ArgSpec(
                "Bbox esperado [x,y,z] do corpo após o passo (read-back/verificação): "
                "se a geometria real divergir, o loop auto-corrige (ex.: um cut que "
                "consome a peça vira bbox ~0). Num furo, use o bbox externo da peça.",
                type="array",
                unit="mm",
                required=False,
                example=[60, 40, 4],
            ),
            "as_surface": ArgSpec(
                "Produz SurfaceBody (NURBS) em vez de Body sólido — Fase 5. "
                "Default false (sólido). Combine com thicken_surface depois para "
                "voltar a sólido com espessura controlada.",
                type="boolean",
                unit=None,
                required=False,
                example=False,
            ),
        },
    ),
    "fusion.revolve_profile": ToolSchema(
        summary="Revolve um perfil de sketch em torno de um eixo.",
        args={
            "sketch": ArgSpec(
                "Sketch cujo perfil será revolvido.",
                type="string",
                unit=None,
                example="Perfil",
            ),
            "axis": ArgSpec(
                "Eixo de revolução: x | y | z.",
                type="string",
                unit=None,
                required=False,
                example="y",
            ),
            "angle_deg": ArgSpec(
                "Ângulo da revolução em graus (default 360 = corpo completo). "
                "Aceita nome de userParameter para vínculo paramétrico.",
                unit="deg",
                required=False,
                example=360,
            ),
            "operation": ArgSpec(
                "new_body | join | cut | intersect.",
                type="string",
                unit=None,
                required=False,
                example="new_body",
            ),
            "as_surface": ArgSpec(
                "Produz SurfaceBody em vez de Body sólido — Fase 5. Default false. "
                "Em modo surface, o meio-perfil NÃO precisa cruzar o eixo.",
                type="boolean",
                unit=None,
                required=False,
                example=False,
            ),
        },
    ),
    "fusion.sweep_profile": ToolSchema(
        summary="Varre um perfil de sketch ao longo de um caminho (path sketch).",
        args={
            "profile": ArgSpec(
                "Sketch do perfil (corte transversal).",
                type="string",
                unit=None,
                example="Perfil",
            ),
            "path": ArgSpec(
                "Sketch do caminho de varredura.",
                type="string",
                unit=None,
                example="Caminho",
            ),
            "operation": ArgSpec(
                "new_body | join | cut.",
                type="string",
                unit=None,
                required=False,
                example="new_body",
            ),
            "as_surface": ArgSpec(
                "Produz SurfaceBody em vez de Body sólido — Fase 5. Default false.",
                type="boolean",
                unit=None,
                required=False,
                example=False,
            ),
        },
    ),
    "fusion.thicken_surface": ToolSchema(
        summary="Espessa SurfaceBody(ies) gerando Body sólido — ponte surface→solid (Fase 5).",
        args={
            "surface_refs": ArgSpec(
                "Lista de nomes (ou índices) de SurfaceBodies a espessar. "
                "Aliases: surfaces, body_refs, bodies. Para uma só superfície "
                "pode passar string direta.",
                type="array",
                unit=None,
                example=["Stitched"],
            ),
            "thickness_mm": ArgSpec(
                "Espessura da parede em milímetros. Aceita nome de userParameter "
                "para vínculo paramétrico (G1.1).",
                example=1.5,
            ),
            "is_symmetric": ArgSpec(
                "Quando true, espessa nos dois lados da superfície (default false).",
                type="boolean",
                unit=None,
                required=False,
                example=False,
            ),
            "operation": ArgSpec(
                "new_body | join | cut | intersect (default new_body).",
                type="string",
                unit=None,
                required=False,
                example="new_body",
            ),
            "chain": ArgSpec(
                "Selecionar faces conectadas tangencialmente em cadeia (default true).",
                type="boolean",
                unit=None,
                required=False,
                example=True,
            ),
            "name": ArgSpec(
                "Nome do Body sólido resultante.",
                type="string",
                unit=None,
                required=False,
                example="Casca",
            ),
        },
    ),
    "fusion.stitch_surfaces": ToolSchema(
        summary="Costura 2+ SurfaceBodies por arestas livres adjacentes (Fase 5).",
        args={
            "surface_refs": ArgSpec(
                "Lista de nomes (ou índices) de SurfaceBodies a costurar (>= 2). "
                "Aliases: surfaces, body_refs, bodies.",
                type="array",
                unit=None,
                example=["Casca", "TampaFrente", "TampaTras"],
            ),
            "tolerance_mm": ArgSpec(
                "Tolerância da costura entre arestas livres (default 0.01 mm).",
                required=False,
                example=0.05,
            ),
            "operation": ArgSpec(
                "new_body | join (default new_body).",
                type="string",
                unit=None,
                required=False,
                example="new_body",
            ),
            "name": ArgSpec(
                "Nome do body resultante (pode ser SurfaceBody ou sólido, "
                "depende se a costura fechou volume — checar is_surface no output).",
                type="string",
                unit=None,
                required=False,
                example="Carenagem",
            ),
        },
    ),
    "fusion.create_surface_patch": ToolSchema(
        summary="Cria SurfaceBody preenchendo um boundary fechado — Fase 5.",
        args={
            "sketch": ArgSpec(
                "Sketch cujo primeiro profile fechado vira o boundary. "
                "Alternativa exclusiva a edge_ids.",
                type="string",
                unit=None,
                required=False,
                example="TampaFrente",
            ),
            "edge_ids": ArgSpec(
                "Lista de índices de arestas (de query_geometry) que formam um "
                "boundary fechado em um body existente. Use com body_ref. "
                "Alternativa exclusiva a sketch.",
                type="array",
                unit=None,
                required=False,
                example=[3, 5, 7, 9],
            ),
            "body_ref": ArgSpec(
                "Nome do body cujas arestas serão usadas (requerido com edge_ids).",
                type="string",
                unit=None,
                required=False,
                example="Casca",
            ),
            "operation": ArgSpec(
                "new_body | join (default new_body).",
                type="string",
                unit=None,
                required=False,
                example="new_body",
            ),
            "name": ArgSpec(
                "Nome do SurfaceBody resultante.",
                type="string",
                unit=None,
                required=False,
                example="TampaPatch",
            ),
        },
    ),
    "fusion.loft_profiles": ToolSchema(
        summary="Loft entre 2+ perfis de sketch ordenados.",
        args={
            "profiles": ArgSpec(
                "Lista de sketches ordenados (cada um com profile único).",
                type="array",
                unit=None,
                example=["Secao1", "Secao2", "Secao3"],
            ),
            "operation": ArgSpec(
                "new_body | join | cut.",
                type="string",
                unit=None,
                required=False,
                example="new_body",
            ),
            "as_surface": ArgSpec(
                "Produz SurfaceBody em vez de Body sólido — Fase 5. Default false. "
                "Em modo surface, aceita perfis abertos (curvas).",
                type="boolean",
                unit=None,
                required=False,
                example=False,
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
            "edge_selector": ArgSpec(
                "Quais arestas arredondar. Valores VÁLIDOS: all | top | bottom | "
                "vertical | horizontal. NÃO invente nomes semânticos "
                "(ex.: 'outer_edges_of_body') — eles não casam com aresta nenhuma. "
                "Alternativa precisa: edge_ids=[i,j] com índices de query_geometry.",
                type="string",
                unit=None,
                required=False,
                example="all",
            ),
        },
    ),
    "fusion.chamfer_edges": ToolSchema(
        summary="Chanfra arestas selecionadas com uma distância.",
        args={
            "distance_mm": ArgSpec("Distância do chanfro em milímetros.", example=1.0),
            "edge_selector": ArgSpec(
                "Quais arestas chanfrar. Valores VÁLIDOS: all | top | bottom | "
                "vertical | horizontal (sem nomes semânticos). "
                "Alternativa: edge_ids=[i,j] de query_geometry.",
                type="string",
                unit=None,
                required=False,
                example="all",
            ),
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
