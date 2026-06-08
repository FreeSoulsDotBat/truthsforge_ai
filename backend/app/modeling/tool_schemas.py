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
            "expected_is_closed": ArgSpec(
                "Quando true, espera-se que a costura feche o volume "
                "(precondição típica antes do thicken_surface). Se ficar aberta, "
                "o loop auto-corrige (aumentar tolerance ou inserir patch).",
                type="boolean",
                unit=None,
                required=False,
                example=True,
            ),
            "expected_surface_area_mm2": ArgSpec(
                "Área total esperada do(s) body(ies) resultante(s) em mm² "
                "(read-back/verificação). Tolerância padrão ±5 mm².",
                unit="mm²",
                required=False,
                example=15000.0,
            ),
        },
    ),
    "fusion.trim_surface": ToolSchema(
        summary="Apara SurfaceBody com ferramenta de corte (sketch/face/surface) — Fase 5.",
        args={
            "surface_ref": ArgSpec(
                "SurfaceBody alvo. Aliases: surface, body_ref, body.",
                type="string",
                unit=None,
                example="Casca",
            ),
            "trim_tool_ref": ArgSpec(
                "Ferramenta de corte (sketch ou body). Aliases: trim_tool, "
                "tool_ref, trimming_tool.",
                type="string",
                unit=None,
                example="CurvaCorte",
            ),
            "keep": ArgSpec(
                "Critério da célula a manter: 'largest' (default, maior área) ou outro.",
                type="string",
                unit=None,
                required=False,
                example="largest",
            ),
            "name": ArgSpec(
                "Nome do SurfaceBody resultante.",
                type="string",
                unit=None,
                required=False,
                example="CascaApanhada",
            ),
        },
    ),
    "fusion.extend_surface": ToolSchema(
        summary="Estende SurfaceBody ao longo de arestas livres — Fase 5.",
        args={
            "edge_ids": ArgSpec(
                "Lista de índices de arestas LIVRES do body. Use "
                "query_geometry com selector 'free_edges' antes para "
                "descobrir os índices.",
                type="array",
                unit=None,
                example=[3, 5],
            ),
            "body_ref": ArgSpec(
                "Nome do body cujas arestas serão estendidas.",
                type="string",
                unit=None,
                example="Casca",
            ),
            "distance_mm": ArgSpec(
                "Distância da extensão em mm. Aceita userParameter (G1.1).",
                example=10.0,
            ),
            "extend_type": ArgSpec(
                "natural | perpendicular | tangent (default natural).",
                type="string",
                unit=None,
                required=False,
                example="natural",
            ),
        },
    ),
    "fusion.offset_surface": ToolSchema(
        summary="Cria SurfaceBody paralela a face(s)/superfície(s) — Fase 5.",
        args={
            "face_ids": ArgSpec(
                "Lista de índices de faces (de query_geometry) a fazer offset. "
                "Exclusivo com surface_refs.",
                type="array",
                unit=None,
                required=False,
                example=[0, 1, 2],
            ),
            "surface_refs": ArgSpec(
                "Lista de nomes de SurfaceBodies a fazer offset (inteiros). "
                "Aliases: surfaces. Exclusivo com face_ids.",
                type="array",
                unit=None,
                required=False,
                example=["Casca"],
            ),
            "body_ref": ArgSpec(
                "Body cujas faces serão usadas (requerido com face_ids).",
                type="string",
                unit=None,
                required=False,
                example="Casca",
            ),
            "distance_mm": ArgSpec(
                "Distância do offset em mm (positivo = exterior). Aceita userParameter (G1.1).",
                example=2.0,
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
                example="CascaOffset",
            ),
        },
    ),
    "fusion.unstitch_surface": ToolSchema(
        summary="Quebra body/SurfaceBody em superfícies individuais por face — Fase 5.",
        args={
            "face_ids": ArgSpec(
                "Lista de índices de faces a desunir. Vazio = todas as faces "
                "do body (unstitch completo).",
                type="array",
                unit=None,
                required=False,
                example=[3, 4],
            ),
            "surface_ref": ArgSpec(
                "Body cujas faces serão desunidas. Aliases: body_ref, body, body_name.",
                type="string",
                unit=None,
                example="Carenagem",
            ),
            "is_chain_selection": ArgSpec(
                "Selecionar faces conectadas tangencialmente (default false). Alias: chain.",
                type="boolean",
                unit=None,
                required=False,
                example=False,
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
            "expected_surface_area_mm2": ArgSpec(
                "Área esperada do patch em mm² (read-back/verificação opcional).",
                unit="mm²",
                required=False,
                example=2400.0,
            ),
        },
    ),
    "fusion.thread": ToolSchema(
        summary=(
            "Rosca MODELADA (geometria real) numa face cilíndrica de um corpo "
            "— externa (parafuso/eixo) ou interna (furo). F3."
        ),
        args={
            "body_ref": ArgSpec(
                "Corpo cuja face cilíndrica recebe a rosca.",
                type="string",
                unit=None,
                required=False,
                example="Screw_Shank",
            ),
            "diameter_mm": ArgSpec(
                "Diâmetro nominal (mm) — usado p/ escolher a designação métrica "
                "mais próxima quando 'designation' não vier.",
                required=False,
                example=6.0,
            ),
            "designation": ArgSpec(
                "Designação da rosca (ex.: 'M6x1'). Tem precedência sobre diameter_mm.",
                type="string",
                unit=None,
                required=False,
                example="M6x1",
            ),
            "is_internal": ArgSpec(
                "true = rosca interna (furo); false = externa (eixo). Default false.",
                type="boolean",
                unit=None,
                required=False,
                example=False,
            ),
            "length_mm": ArgSpec(
                "Comprimento da rosca (mm). Vazio = comprimento total da face.",
                required=False,
                example=18.0,
            ),
            "face_token": ArgSpec(
                "entityToken (F1) da face cilíndrica a roscar. Preferido a "
                "selector quando há ambiguidade.",
                type="string",
                unit=None,
                required=False,
                example="abc123==",
            ),
        },
    ),
    "fusion.make_component": ToolSchema(
        summary=(
            "Transforma um corpo em componente (occurrence) — base para montagens e juntas. F3."
        ),
        args={
            "body_ref": ArgSpec(
                "Corpo a virar componente.",
                type="string",
                unit=None,
                required=False,
                example="Leaf_A",
            ),
            "name": ArgSpec(
                "Nome do componente.",
                type="string",
                unit=None,
                required=False,
                example="Hinge_A",
            ),
        },
    ),
    "fusion.joint": ToolSchema(
        summary=(
            "Cria uma junta entre dois corpos/componentes: revolute (dobradiça), "
            "rigid (fixa), slider (linear) ou cylindrical. F3."
        ),
        args={
            "joint_type": ArgSpec(
                "revolute | rigid | slider | cylindrical (default revolute).",
                type="string",
                unit=None,
                required=False,
                example="revolute",
            ),
            "body_one": ArgSpec(
                "Primeiro corpo/componente da junta.",
                type="string",
                unit=None,
                required=False,
                example="Hinge_A",
            ),
            "body_two": ArgSpec(
                "Segundo corpo/componente da junta.",
                type="string",
                unit=None,
                required=False,
                example="Hinge_B",
            ),
            "face_token_one": ArgSpec(
                "entityToken (F1) da face da junta no corpo 1 (preferido).",
                type="string",
                unit=None,
                required=False,
                example="tokA==",
            ),
            "face_token_two": ArgSpec(
                "entityToken (F1) da face da junta no corpo 2 (preferido).",
                type="string",
                unit=None,
                required=False,
                example="tokB==",
            ),
            "face_selector_one": ArgSpec(
                "Selector da face no corpo 1 quando sem token (ex.: cylindrical).",
                type="string",
                unit=None,
                required=False,
                example="cylindrical",
            ),
            "face_selector_two": ArgSpec(
                "Selector da face no corpo 2 quando sem token.",
                type="string",
                unit=None,
                required=False,
                example="cylindrical",
            ),
            "axis": ArgSpec(
                "Eixo do movimento (x|y|z) para revolute/slider/cylindrical.",
                type="string",
                unit=None,
                required=False,
                example="z",
            ),
        },
    ),
    "fusion.place_body": ToolSchema(
        summary=(
            "F7 — posiciona um corpo por REFERÊNCIA declarativa (sem coordenada "
            "crua): ancora uma face do corpo numa face de destino, FLUSH (faces "
            "coplanares encostadas). O resolver expande em make_component + junta "
            "rígida que sobrevive a recompute. Para eixo coaxial use align_axis."
        ),
        args={
            "body": ArgSpec(
                "Corpo a posicionar (nome ou stable_id).",
                type="string",
                unit=None,
                example="Tampa",
            ),
            "anchor": ArgSpec(
                "Face DO corpo que encosta — por ROLE {body,role:'bottom_planar'} "
                "ou predicado {body,face:{type,radius_mm}}. Não copie token.",
                type="object",
                unit=None,
                example={"body": "Tampa", "role": "bottom_planar"},
            ),
            "target": ArgSpec(
                "Face de DESTINO — por ROLE/predicado (o backend acha a face real).",
                type="object",
                unit=None,
                example={"body": "Caixa", "role": "top_planar"},
            ),
        },
    ),
    "fusion.align_axis": ToolSchema(
        summary=(
            "F7 — alinha o eixo de um corpo a uma FACE cilíndrica de destino "
            "(furo/pino); o resolver expande numa junta revolute/cilíndrica. "
            "Use para o eixo de uma dobradiça."
        ),
        args={
            "body": ArgSpec(
                "Corpo cujo eixo será alinhado.",
                type="string",
                unit=None,
                example="Tampa",
            ),
            "target": ArgSpec(
                "Face cilíndrica de destino por PREDICADO {body,face:{type:"
                "'cylindrical',radius_mm:R}} — o backend acha o furo/pino real.",
                type="object",
                unit=None,
                example={"body": "Caixa", "face": {"type": "cylindrical", "radius_mm": 2.5}},
            ),
            "body_axis": ArgSpec(
                "Eixo do corpo a alinhar (x|y|z). Default z.",
                type="string",
                unit=None,
                required=False,
                example="x",
            ),
        },
    ),
    "fusion.distribute_along": ToolSchema(
        summary=(
            "F7 — distribui N primitivas (ex.: knuckles de dobradiça) ao longo de "
            "uma ARESTA, com espaçamento/encaixe e alternância opcional entre dois "
            "corpos-pai (combine-DENTRO de cada parte imprimível)."
        ),
        args={
            "edge": ArgSpec(
                "Aresta-guia — edge_token (F1) ao longo do qual distribuir.",
                type="string",
                unit=None,
                example="@token('E_HINGE') ou 'E_HINGE'",
            ),
            "count": ArgSpec(
                "Quantidade de nós a distribuir.",
                type="number",
                unit=None,
                example=5,
            ),
            "prototype": ArgSpec(
                "Primitiva a replicar: {primitive:'cylinder', diameter_mm, height_mm, name}.",
                type="object",
                unit=None,
                example={
                    "primitive": "cylinder",
                    "diameter_mm": 5,
                    "height_mm": 8,
                    "name": "Knuckle",
                },
            ),
            "spacing_mm": ArgSpec(
                "Passo entre nós (mm); a fileira é centrada na aresta. Sem isto, "
                "use fit p/ preencher uniformemente.",
                required=False,
                example=10.0,
            ),
            "fit": ArgSpec(
                "true = distribui uniformemente incluindo as pontas da aresta.",
                type="boolean",
                unit=None,
                required=False,
                example=True,
            ),
            "alternate": ArgSpec(
                "[CorpoA, CorpoB] — alterna os nós entre dois pais; cada grupo "
                "funde (combine-DENTRO) com seu corpo.",
                type="array",
                unit=None,
                required=False,
                example=["Caixa", "Tampa"],
            ),
        },
    ),
    "fusion.knuckle_hinge": ToolSchema(
        summary=(
            "MACRO: dobradiça de nós (knuckles) que abre em torno de um pino "
            "vertical — duas abas + coluna de knuckles alternados + pino. F3."
        ),
        args={
            "leaf_length_mm": ArgSpec(
                "Altura total da dobradiça / coluna de knuckles (mm).",
                required=False,
                example=40.0,
            ),
            "leaf_width_mm": ArgSpec(
                "Largura de cada aba a partir do pino (mm).",
                required=False,
                example=20.0,
            ),
            "thickness_mm": ArgSpec(
                "Espessura das abas (mm).",
                required=False,
                example=4.0,
            ),
            "knuckle_count": ArgSpec(
                "Número de knuckles (>=3, alternados entre as abas).",
                type="integer",
                unit=None,
                required=False,
                example=5,
            ),
            "knuckle_diameter_mm": ArgSpec(
                "Diâmetro dos knuckles (mm). Default ~2.5x a espessura.",
                required=False,
                example=10.0,
            ),
            "pin_diameter_mm": ArgSpec(
                "Diâmetro do pino (mm). Default ~0.45x o knuckle.",
                required=False,
                example=4.0,
            ),
            "joint": ArgSpec(
                "revolute cria a junta cinemática que faz a dobradiça abrir — "
                "MAS isso move as abas para COMPONENTES (<name>_A/<name>_B), e "
                "elas deixam de ser corpos do root: você NÃO consegue mais "
                "combiná-las com a caixa/tampa. Use joint só para montagem "
                "cinemática (peça que abre na tela). Para uma peça IMPRESSA "
                "(juntar a dobradiça à caixa/tampa via combine_bodies), OMITA "
                "joint — aí as abas ficam como corpos combináveis.",
                type="string",
                unit=None,
                required=False,
                example="revolute",
            ),
            "name": ArgSpec(
                "Prefixo dos corpos gerados. Produz os corpos <name>_Leaf_A, "
                "<name>_Leaf_B e <name>_Pin (ex.: name='Hinge' → 'Hinge_Leaf_A', "
                "'Hinge_Leaf_B', 'Hinge_Pin'). Referencie ESSES nomes em passos "
                "seguintes (combine/move) — não invente 'HingeLeaf'/'Hinge_Pin'.",
                type="string",
                unit=None,
                required=False,
                example="Hinge",
            ),
        },
    ),
    "fusion.metric_screw": ToolSchema(
        summary=(
            "MACRO: parafuso métrico = haste + cabeça + rosca modelada. "
            "designation 'M6' dá o diâmetro nominal. F3."
        ),
        args={
            "designation": ArgSpec(
                "Designação métrica (ex.: 'M6'). Define o diâmetro nominal.",
                type="string",
                unit=None,
                required=False,
                example="M6",
            ),
            "length_mm": ArgSpec(
                "Comprimento da haste (mm). Default ~4x o nominal.",
                required=False,
                example=24.0,
            ),
            "head_diameter_mm": ArgSpec(
                "Diâmetro da cabeça (mm). Default ~1.6x o nominal.",
                required=False,
                example=10.0,
            ),
            "head_height_mm": ArgSpec(
                "Altura da cabeça (mm). Default ~0.9x o nominal.",
                required=False,
                example=5.0,
            ),
            "threaded": ArgSpec(
                "false desativa a rosca modelada (só a geometria). Default true.",
                type="boolean",
                unit=None,
                required=False,
                example=True,
            ),
            "head_type": ArgSpec(
                "Tipo de cabeça: 'hex' (sextavada, default — cara de parafuso) "
                "ou 'cylinder'/'socket' (cilíndrica). Em hex, head_diameter_mm é "
                "o entre-faces (boca da chave).",
                type="string",
                unit=None,
                required=False,
                example="hex",
            ),
            "name": ArgSpec(
                "Prefixo dos corpos gerados.",
                type="string",
                unit=None,
                required=False,
                example="Screw",
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
        summary=(
            "Lê o estado real do modelo (read-back): por body dimensions_mm/"
            "is_solid/is_closed/surface_area_mm2/stable_id; por face "
            "face_token (ESTÁVEL)/type/area_mm2/radius_mm/normal_axis/center_mm; "
            "por edge edge_token (ESTÁVEL)/length_mm/is_circular/radius_mm/"
            "adjacent_face_tokens. Use os *_token para mirar faces/arestas em "
            "passos seguintes (sobrevivem a recompute, ao contrário do índice)."
        ),
        args={
            "include_tokens": ArgSpec(
                "Inclui entityToken de face/edge + adjacências (default true). "
                "false reduz o payload quando só precisa de contagens/dims.",
                type="boolean",
                unit=None,
                required=False,
                example=True,
            ),
            "limit": ArgSpec(
                "Máximo de faces/edges por body no retorno (default 60).",
                type="integer",
                unit=None,
                required=False,
                example=60,
            ),
        },
    ),
    "fusion.capture_viewport": ToolSchema(
        summary=(
            "Renderiza o viewport ativo do Fusion e devolve a imagem (base64) "
            "para verificação VISUAL do modelo. Read-only. Interno do loop "
            "(render→visão→replaneja); o planner não gasta passo com ela."
        ),
        args={
            "view": ArgSpec(
                "Orientação: iso|front|back|top|bottom|left|right (default iso), "
                "com fit automático.",
                type="string",
                unit=None,
                required=False,
                example="iso",
            ),
            "width_px": ArgSpec(
                "Largura da imagem em px (default 1024).",
                type="integer",
                unit=None,
                required=False,
                example=1024,
            ),
            "height_px": ArgSpec(
                "Altura da imagem em px (default 768).",
                type="integer",
                unit=None,
                required=False,
                example=768,
            ),
        },
    ),
}


def tool_schema(tool_name: str) -> ToolSchema | None:
    return TOOL_SCHEMAS.get(tool_name)


def render_tool_schema(tool_name: str) -> str:
    """Renderiza uma linha-bloco legível pela LLM para uma tool."""
    # Tools depreciadas (fora de PLANNER_TOOLSET) não podem ser renderizadas:
    # senão um corretor/editor de passo poderia reintroduzi-las via schema órfão.
    # Alinha render_tool_schema com tool_registry.DEPRECATED_PLANNER_TOOLS.
    if tool_name in tool_registry.DEPRECATED_PLANNER_TOOLS:
        return f"- {tool_name}: (tool depreciada — indisponível)"
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
