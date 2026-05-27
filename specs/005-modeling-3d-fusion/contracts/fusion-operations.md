# Contrato de operações Fusion — mapa `fusion.*` → API do Autodesk Fusion 360

> **Tipo:** contrato/referência (as-built vs. API oficial).
> **Status:** vivo — atualizar a cada onda implementada.
> **Autor:** Claude Code (sessão gate v4), 2026-05-25.
> **Relacionado:** ADR-013 (registry único), ADR-017 (MCP standalone), ADR-019
> (script determinístico backend-owned), `backend/app/modeling/fusion_mcp_scripts.py`,
> `tool_registry.py`, `tool_schemas.py`, `adapter-tools-mvp.md` (proposta original —
> **este documento corrige os mapeamentos de API que mudaram na implementação**),
> `docs/3d-modeling-debug.md` (logs/terminal).

## 1. Como ler este documento

### 1.1 Duas camadas — onde mora a correção

A integração com o Fusion tem **duas camadas**, e confundi-las é a origem do
schema-drift que vínhamos caçando "fix-by-trace":

1. **Protocolo do servidor MCP (porta `27182`, `…/mcp`).** O servidor (Autodesk
   Fusion MCP Server / add-ins equivalentes da comunidade) expõe essencialmente
   **um tool genérico** `fusion_mcp_execute` (+ `fusion_mcp_read`) com payload
   `{"featureType": "...", "object": {...}}`. Nosso adapter
   (`fusion_adapter.py`) **sempre** envia `featureType:"script"` com um script
   Python que **nós geramos** — nunca o script do modelo. Isso é decisão de
   design (**ADR-019**: só geramos script determinístico para tools
   allowlistadas), não algo a "corrigir": garante controle, determinismo e
   auditoria. Handshake usa `protocolVersion: "2025-06-18"` (versão do **MCP**,
   não do servidor).
2. **API do Autodesk Fusion 360** (`adsk.core` / `adsk.fusion`) **dentro** do
   script gerado. **É esta a "documentação deles" que vale para correção.** Cada
   `fusion.*` deste contrato é, no fim, uma sequência de chamadas desta API. Erros
   de assinatura/seleção aqui = peça errada no gate.

> **Implicação prática:** ao implementar uma onda nova, a fonte de verdade é a
> **API Reference do Fusion 360**, não o protocolo MCP. Use os mapeamentos da
> §3 e valide a assinatura exata na referência oficial (§Fontes).

### 1.2 Convenções de unidade (CRÍTICO)

A API interna do Fusion usa **centímetros e radianos**. Nossos args são sempre
**milímetros e graus**. As conversões aplicadas no gerador:

| De (arg) | Para (API) | Fator | Exemplo no código |
|---|---|---|---|
| comprimento `mm` | `cm` | `/ 10.0` | `radius_cm = radius_mm / 10.0` |
| **diâmetro `mm`** | **raio `cm`** | `/ 20.0` | `_profile_for_circle(sketch, diam/20.0)` |
| ângulo `graus` | `rad` | `* math.pi / 180.0` | `angle_rad = angle_deg*math.pi/180` |
| posição `[x,y] mm` | `cm` | `/ 10.0` cada | `Point3D.create(x/10, y/10, …)` |

Todo arg dimensional passa por `_eval_param` / `_eval_pair`, que aceitam número
**ou** expressão paramétrica do Fusion (ex.: `"=thickness"`, `"largura/2"`).

### 1.3 Seleção de perfil e de aresta/face (as duas fontes de drift)

- **Perfil** (`extrude`/`revolve`/`sweep`): `_resolve_profile_selection(sketch, args, design)`
  — `profile_index` (0-based) **ou** `profile_diameter_mm` (casa por área do
  círculo via `_profile_for_circle`, π·r²). **Sem seletor cai em `profiles.item(0)`**
  — origem do bug "o cut consumiu a peça" (retângulo+círculo coplanares).
  `extrude cut` com >1 perfil e sem seletor emite WARN no trace.
- **Aresta** (`fillet`/`chamfer`): `_select_edges(body, selector)` — seletores
  **semânticos** `all | top | bottom | vertical | horizontal | longest | shortest`,
  ou `edge_ids`/`edge_indices` (índices de `query_geometry`). **Não** aceita
  nomes inventados (`"outer_edges_of_body"`).
- **Face** (`shell`/`hole`): `_select_faces(body, selector)` — `top | bottom |
  none | +x | -x | +y | -y | +z | -z | planar | cylindrical | largest`, ou
  `face_ids`.
- ⚠️ **Fragilidade conhecida:** selectors `top/bottom/vertical/horizontal` são
  heurística por **bounding-box em Z**. Corretos para peças alinhadas aos eixos;
  **não confiáveis** para corpos rotacionados/oblíquos. Para precisão use
  `edge_ids`/`face_ids` de `query_geometry`.

### 1.4 Categorias de risco (de `tool_registry.py`)

`read_only` (sempre auto) · `additive` (auto) · `mutative` (auto no fluxo fluido)
· `destructive` (**aprovação obrigatória**) · `high_risk` (**aprovação
obrigatória**). Ver AGENTS.md / ADR.

## 2. Tabela-resumo (todas as ops)

| Tool | Cat. | Classe/feature da API Fusion | Status impl. |
|---|---|---|---|
| `open_design` | additive | `Application.documents` / `activeProduct` | ✅ |
| `create_sketch` | additive | `Component.sketches.add(plane)` | ✅ (sketch **vazio**) |
| `add_rectangle` | additive | `SketchLines.addTwoPointRectangle` | ✅ (+modo grade) |
| `add_circle` | additive | `SketchCircles.addByCenterRadius` | ✅ |
| `add_polygon` | additive | `SketchLines.addByTwoPoints` (N lados) | ✅ (manual, não `addScribedPolygon`) |
| `add_line` | additive | `SketchLines.addByTwoPoints` | ✅ |
| `add_arc` | additive | `SketchArcs.addByCenterStartSweep` | ✅ |
| `add_ellipse` | additive | `SketchEllipses.add` | ✅ |
| `add_slot` | additive | arcos + linhas | ✅ |
| `add_spline` | additive | `SketchFittedSplines.add` | ✅ |
| `extrude_profile` | mutative | `ExtrudeFeatures.createInput` + `setDistanceExtent` | ✅ |
| `revolve_profile` | mutative | `RevolveFeatures.createInput` + `setAngleExtent` | ✅ |
| `sweep_profile` | mutative | `Features.createPath` + `SweepFeatures.createInput` | ✅ (path = `item(0)`) |
| `loft_profiles` | mutative | `LoftFeatures.createInput` + `loftSections` | ✅ |
| `add_box` | additive | sketch+extrude interno | ✅ |
| `add_cylinder` | additive | sketch+extrude interno | ✅ |
| `add_sphere` | additive | **revolve de semicírculo** | ✅ (não `TemporaryBRepManager`) |
| `add_cone` | additive | **revolve de trapézio** | ✅ |
| `fillet_edges` | mutative | `FilletFeatures` + `addConstantRadiusEdgeSet` | ✅ (`createInput` legado) |
| `chamfer_edges` | mutative | `ChamferFeatures` (`createInput`/`createInput2`) | ✅ |
| `shell_body` | mutative | `ShellFeatures.createInput` + `insideThickness` | ✅ |
| `hole` | mutative | **cut-extrude de círculo** | ✅ (não `HoleFeatures`) |
| `pattern_rectangular` | mutative | `RectangularPatternFeatures` | ✅ |
| `pattern_circular` | mutative | `CircularPatternFeatures` | ✅ |
| `mirror_feature` | mutative | `MirrorFeatures.createInput` | ✅ |
| `combine_bodies` | **high_risk** | `CombineFeatures.createInput` | ✅ (aprovação) |
| `move_body` | mutative | `MoveFeatures` (`createInput`/`createInput2`) | ✅ |
| `scale_body` | mutative | `ScaleFeatures.createInput` | ✅ |
| `split_body` | mutative | `SplitBodyFeatures.createInput` | ✅ |
| `delete_body` | **destructive** | `RemoveFeatures` / `deleteMe` | ✅ (aprovação) |
| `add_construction_plane` | additive | `ConstructionPlanes.createInput().setByOffset` | ✅ |
| `set_parameter` | mutative | `Design.userParameters` + `ValueInput.createByString` | ✅ |
| `export_step` | additive | `ExportManager.createSTEPExportOptions` | ✅ |
| `export_stl` | additive | `ExportManager.createSTLExportOptions` | ✅ |
| `export_3mf` | additive | `ExportManager.createC3MFExportOptions` | ✅ |
| `query_geometry` | read_only | `BRepBodies`/`faces`/`edges`/`boundingBox` | ✅ |
| `validate_dimensions` | read_only | `boundingBox` + `physicalProperties` | ✅ |
| `validate_printability` | read_only | checks B-Rep | ✅ |
| `run_script` | high_risk | — | 🚫 **nunca exposto** (ADR-019) |
| `extrude_profile` `as_surface=true` | mutative | `ExtrudeFeatures.createInput` + `input.isSolid=False` | ✅ T5.1a/b |
| `revolve_profile` `as_surface=true` | mutative | `RevolveFeatures.createInput` + `input.isSolid=False` | ✅ T5.1a/b |
| `sweep_profile` `as_surface=true` | mutative | `SweepFeatures.createInput` + `input.isSolid=False` | ✅ T5.1a/b |
| `loft_profiles` `as_surface=true` | mutative | `LoftFeatures.createInput` + `input.isSolid=False` (aceita open profiles) | ✅ T5.1a/b |
| `create_surface_patch` | mutative | `PatchFeatures.createInput(boundary, op)` | ✅ T5.1b |
| `trim_surface` | mutative | `TrimFeatures.createInput(surface, trim_tool)` + cell-to-remove | 🚧 Fase 5 |
| `extend_surface` | mutative | `ExtendFeatures.createInput(edges, distance, extendType)` | 🚧 Fase 5 |
| `offset_surface` | mutative | `OffsetFeatures.createInput(face\|surface, distance, op)` | 🚧 Fase 5 |
| `thicken_surface` | mutative | `ThickenFeatures.createInput(surfaces, thickness, isSymmetric, op)` | 🚧 Fase 5 |
| `stitch_surfaces` | mutative | `StitchFeatures.createInput(surfaces, tolerance, op)` | 🚧 Fase 5 |
| `unstitch_surface` | mutative | `UnstitchFeatures.createInput(faces)` | 🚧 Fase 5 |

## 3. Operações em detalhe

Formato por op: **API Fusion** · **args** (canônicos; aliases entre parênteses)
· **semântica/limitações**.

### 3.1 Sessão & inspeção

- **`fusion.open_design`** — `app.documents.add(DocumentTypes.FusionDesignDocumentType)`
  para documento novo; senão reusa `app.activeProduct`. Args: `new_document`,
  `reset`, `force_new` (bool, default false). Garante design ativo para as demais.
- **`fusion.query_geometry`** (G2.2) — itera `rootComponent.bRepBodies` →
  `body.faces` / `body.edges` / `body.boundingBox` / `physicalProperties`.
  Args: `limit`. Retorna **índices estáveis** de bodies/faces/arestas + bbox/volume
  — é a fonte dos `edge_ids`/`face_ids` precisos.
- **`fusion.validate_dimensions`** — `body.boundingBox` + `body.physicalProperties.volume`.
  Args: `body`. Read-back para o verifier do loop agêntico.
- **`fusion.validate_printability`** — checks no B-Rep (`body.isSolid`, volume,
  parede mínima, overhang). Args: `checks`, `printer_profile`.

### 3.2 Sketch & perfis

- **`fusion.create_sketch`** — `component.sketches.add(plane)`. Args: `plane`
  (`plane_ref`): `xy|yz|xz|top|front|right` (fallback XY com warning), `name`
  (`sketch_name`). ⚠️ **Cria sketch VAZIO** — o planner DEVE chamar uma tool de
  geometria antes de extrude/revolve.
- **`fusion.add_rectangle`** — `sketch.sketchCurves.sketchLines.addTwoPointRectangle(p1,p2)`.
  Args: `sketch`, `width_mm`, `height_mm`, `center_mm`; **modo grade**:
  `cols` (`columns`), `rows`, `cell_size_mm`, `gap_mm`, `grid_origin_mm`.
- **`fusion.add_circle`** — `sketchCircles.addByCenterRadius(center, raio_cm)`.
  Args: `sketch`, `diameter_mm` (`circle_diameter_mm`) **ou** `radius_mm`,
  `center_mm` (`center_x_mm`+`center_y_mm`).
- **`fusion.add_polygon`** — N vértices por trigonometria conectados com
  `sketchLines.addByTwoPoints` (Fusion auto-fecha). Args: `sketch`, `sides`
  (≥3), `diameter_mm` **ou** `radius_mm`, `center_mm`. *Canônico alternativo:*
  `addScribedPolygon` — preferimos manual por controle.
- **`fusion.add_line`** — `sketchLines.addByTwoPoints` em loop. Args: `sketch`,
  `points_mm=[[x,y],…]` (`points`; ou `start_mm`+`end_mm` p/ linha única),
  `closed` (bool).
- **`fusion.add_arc`** — `sketchArcs.addByCenterStartSweep(center, start, sweep_rad)`.
  Args: `sketch`, `center_mm`, `start_mm`, `sweep_deg` (ou `radius_mm` +
  `start_angle_deg` + `end_angle_deg`).
- **`fusion.add_ellipse`** — `sketchEllipses.add(...)`. Args: `sketch`,
  `major_mm` (`width_mm`), `minor_mm` (`height_mm`), `center_mm`.
- **`fusion.add_slot`** — oblongo via 2 arcos + 2 linhas. Args: `sketch`,
  `length_mm`, `width_mm`, `center_mm`.
- **`fusion.add_spline`** — `sketchCurves.sketchFittedSplines.add(ObjectCollection<Point3D>)`.
  Args: `sketch`, `points_mm=[[x,y],…]` (≥2).

### 3.3 Sólidos a partir de perfil

- **`fusion.extrude_profile`** — `ExtrudeFeatures.createInput(profile, op)` +
  `setDistanceExtent(False, ValueInput)`. Args: `sketch`, `distance_mm`
  (`distance`; aceita negativo e expressão), `operation`
  (`new_body|join|cut|intersect`; op inválida → `new_body` com WARN),
  **`profile_index`** / **`profile_diameter_mm`** (seleção de perfil — §1.3).
- **`fusion.revolve_profile`** — `RevolveFeatures.createInput(profile, axis, op)`
  + `setAngleExtent(False, ValueInput angle_rad)`. Args: `sketch`, `axis`
  (`x|y|z`, default `y`), `angle_deg` (default 360), `operation` (`result`),
  `profile_index`/`profile_diameter_mm`.
- **`fusion.sweep_profile`** — `Features.createPath(curva)` +
  `SweepFeatures.createInput(profile, path, op)`. Args: `profile`
  (`profile_sketch`), `path` (`path_sketch`), `operation`. ⚠️ **Limitação:** usa
  só `path.sketchCurves.item(0)` — caminhos multi-curva não encadeiam todas.
- **`fusion.loft_profiles`** — `LoftFeatures.createInput(op)` +
  `loftSections.add(profile)` por seção. Args: `profiles` (`sketches`) — refs de
  sketch **ordenados** (cada um com perfil único), `operation`.

### 3.4 Primitivas diretas (sketch+feature interno, paramétrico/editável)

- **`fusion.add_box`** — sketch XY + extrude. Args: `width_mm`,`depth_mm`,`height_mm`
  (ou `dimensions_mm=[w,d,h]` / `size_mm`), `center_mm` (centraliza) **ou**
  `origin_mm` (canto inferior), `name`.
- **`fusion.add_cylinder`** — sketch círculo + extrude. Args: `diameter_mm`
  (`radius_mm`), `height_mm`, `center_mm`, `name`.
- **`fusion.add_sphere`** — semicírculo + revolve 360°. Args: `diameter_mm`
  (`radius_mm`), `center_mm`, `name`. **Divergência:** não usa
  `TemporaryBRepManager.createSphere` (escolha: corpo editável na timeline).
- **`fusion.add_cone`** — perfil trapezoidal/triangular + revolve. Args:
  `base_diameter_mm` (`base_radius_mm`), `top_diameter_mm` (default 0 = cone
  pontudo), `height_mm`, `name`.

### 3.5 Features de modificação

- **`fusion.fillet_edges`** — `rootComp.features.filletFeatures.createInput()` +
  `inp.addConstantRadiusEdgeSet(edges, ValueInput, isTangentChain=True)` + `add`.
  Args: `radius_mm`, `edge_selector` (§1.3) ou `edge_ids`/`edge_indices`,
  `body_ref` (`body`/`body_name`). **Recomendação:** migrar para o moderno
  `createInput2()` + `inp.edgeSetInputs.addConstantRadiusEdgeSet(...)` (o
  `createInput()` é legado).
- **`fusion.chamfer_edges`** — tenta legado `chamferFeatures.createInput(edges, True)`
  + `setToEqualDistance(d)`; fallback moderno `createInput2()` +
  `chamferEdgeSets.addEqualDistanceChamferEdgeSet(edges, d, True)`. Args:
  `distance_mm`, `edge_selector`/`edge_ids`, `body_ref`. **Recomendação:**
  inverter a ordem (tentar `createInput2` primeiro).
- **`fusion.shell_body`** — `shellFeatures.createInput(ObjectCollection, False)` +
  `inp.insideThickness = ValueInput`. Args: `thickness_mm`, `open_faces`
  (`faces`): `top|bottom|none|+x…` ou `face_ids`, `body_ref`. Nota: `"all"`→
  `"none"` (abrir todas deletaria o corpo → casca fechada).
- **`fusion.hole`** — **cut-extrude** de um círculo na face superior. Args:
  `diameter_mm`, `depth_mm` (vazio = passante/through-all), `position_mm=[x,y]`
  (no plano da face), `body_ref`, `type` (`simple|counterbore`),
  `counterbore_diameter_mm`, `counterbore_depth_mm`. **Divergência:** o canônico
  é `HoleFeatures.createSimpleInput(ValueInput)` (ou `createCounterboreInput`/
  `createCountersinkInput`) + `setPositionByPoint`/`setPositionBySketchPoint` +
  `setDistanceExtent`/`setAllExtent`. **Limitações atuais:** assume **face
  superior planar**; `countersink` não implementado (precisa revolve/chamfer da
  borda). Geometricamente equivalente para impressão, mas **não** é um feature
  "Hole" (sem callout/rosca).

### 3.6 Replicação & boolean

- **`fusion.pattern_rectangular`** — `rectangularPatternFeatures.createInput(
  entidades, eixoX, qtdX, distX, PatternDistanceType.SpacingPatternDistanceType)`
  + direção 2. Args: `body_ref`, `count_x` (`occurrences_x`/`instances_x`),
  `count_y` (idem), `spacing_x_mm`, `spacing_y_mm`, `axis_x`, `axis_y`.
- **`fusion.pattern_circular`** — `circularPatternFeatures.createInput(entidades,
  eixo)` + `.quantity` + `.totalAngle`. Args: `body_ref`, `count`
  (`occurrences`/`quantity`/`instances`), `total_angle_deg` (`angle_deg`, default
  360), `axis`.
- **`fusion.mirror_feature`** — `mirrorFeatures.createInput(entidades, plano)`.
  Args: `body_ref`, `plane` (`xy|yz|xz`).
- **`fusion.combine_bodies`** (high_risk) — `combineFeatures.createInput(
  bodyAlvo, ObjectCollection<bodiesFerramenta>)` + `.operation`. Args:
  `target_ref` (`target`), `tool_refs` (`tools`), `operation`
  (`join|cut|intersect`). **Aprovação humana obrigatória.**

### 3.7 Transformação & corpos

- **`fusion.move_body`** — legado `moveFeatures.createInput(coll, Matrix3D)` /
  moderno `createInput2(coll)` + `defineAsFreeMove(transform)`. Args: `body_ref`,
  `translation_mm=[x,y,z]`.
- **`fusion.scale_body`** — `scaleFeatures.createInput(entidades, ponto,
  ValueInput fator)`. Args: `body_ref`, `factor` (uniforme).
- **`fusion.split_body`** (G3) — `splitBodyFeatures.createInput(body,
  ferramentaDeCorte, isExtended)`. Args: `body_ref`, `plane`, `offset_mm`.
- **`fusion.delete_body`** (destructive) — `removeFeatures.add(body)` /
  `body.deleteMe()`. Args: `body_ref`. **Aprovação obrigatória.**

### 3.8 Construção & parâmetros

- **`fusion.add_construction_plane`** — `constructionPlanes.createInput()` +
  `setByOffset(base, ValueInput offset_cm)`. Args: `offset_mm`, `base`
  (`xy|yz|xz`), `name`. *(Proposta original previa `angle`/`midplane` — não
  implementados; só offset.)*
- **`fusion.set_parameter`** — `design.userParameters`: cria/atualiza com
  `ValueInput.createByString(expr)`; ou ajusta `itemByName(name).expression`.
  Args: **bulk** `parameters` (`parameters_mm`/`params`) **ou** single `name` +
  `expression` (+ `unit`, `comment`).

### 3.9 Exports (`design.exportManager`)

> ⚠️ **Atenção à ordem dos args** (assim na API): STEP = `(filename, geometry)`;
> STL/3MF = `(geometry, filename)`.

- **`fusion.export_step`** — `createSTEPExportOptions(str(path), _root(design))`
  + `exportManager.execute(options)`. Args: `result_name` (`output_name`).
- **`fusion.export_stl`** — `createSTLExportOptions(_root(design), str(path))`.
  Args: `result_name`/`output_name`, `body` (vazio = design todo).
- **`fusion.export_3mf`** — `createC3MFExportOptions(_root(design), str(path))`.
  Args: `result_name`/`output_name`. **Guarda:** exige ≥1 body sólido (senão
  `InternalValidationError` — Fix #5).

### 3.10 Superfícies (NURBS) — pré-implementação (Fase 5)

> **Status:** mapeamento pré-implementação (T5.0). Cada item é um contrato-alvo;
> a implementação real entra com testes mock (T5.1–T5.4) e fecha no gate da
> carenagem (Nível 2). Hoje **0/11 itens** existem em `fusion_mcp_scripts.py`.

#### 3.10.1 Criação de superfície (expansão das tools existentes)

A API Fusion já permite que `extrude`/`revolve`/`sweep`/`loft` produzam
**SurfaceBody** em vez de Body sólido por meio de `input.isSolid = False`
(disponível em `FeatureInput` desde versões antigas). Decisão de design:
**não criar tools novas duplicadas** — adicionar o argumento `as_surface: bool`
(default `false`, backward-compat) nas 4 tools existentes:

- **`fusion.extrude_profile`** com `as_surface=true` —
  `ExtrudeFeatures.createInput(profile, op)` + `input.isSolid = False` antes do
  `setDistanceExtent`. Resultado em `feature.bodies` é `SurfaceBody`. Limitação:
  o perfil pode ser aberto (`openProfiles`) — exige caminho alternativo
  `ExtrudeFeatures.createInput(openProfile, op)` quando `profile.isClosed=False`.
- **`fusion.revolve_profile`** com `as_surface=true` — `input.isSolid = False`.
  Aceita meio-perfil aberto (não precisa cruzar o eixo como no sólido).
- **`fusion.sweep_profile`** com `as_surface=true` — `input.isSolid = False`.
  Combinado com perfil aberto produz uma "lasca" de superfície.
- **`fusion.loft_profiles`** com `as_surface=true` — `input.isSolid = False`.
  Aceita perfis abertos (loft entre curvas); aceita `centerLineOrRails` (eixo
  ou rails) — fora de escopo da T5.1; só perfis empilhados.

Conversão de unidades inalterada (cm/rad internos).

#### 3.10.2 `fusion.create_surface_patch`

**API:** `rootComp.features.patchFeatures.createInput(boundaryEntity, FeatureOperation.NewBodyFeatureOperation)`
→ `patchFeatures.add(input)`.

**Args:**
- `boundary` (obrigatório): aceita `sketch=<nome>` (usa primeiro profile fechado
  do sketch como boundary) **ou** `edge_ids=[...]` (lista de índices de
  `query_geometry`; o adapter monta `ObjectCollection<BRepEdge>`).
- `operation` (`new_body|join`; default `new_body`).
- `name` (`result_name` / `body_name`).

**Semântica:** preenche um boundary fechado com uma superfície NURBS plana ou
não-plana (Fusion decide o melhor fit). Falha se o boundary não for fechado ou
auto-interceptar.

**Erros previstos:** `fusion.invalid_boundary`, `fusion.boundary_not_closed`.

#### 3.10.3 `fusion.trim_surface`

**API:** `rootComp.features.trimFeatures.createInput(surface, trimmingTool)` +
`input.cellsToRemove = ObjectCollection<TrimCell>` → `trimFeatures.add(input)`.

**Args:**
- `surface_ref` (obrigatório): nome de SurfaceBody **ou** `surface_index` da
  saída de `query_geometry`.
- `trim_tool_ref` (obrigatório): sketch curve, face de outra superfície ou body.
- `cells_to_remove` (default: todas exceto a maior): lista de índices de células
  resultantes do trim — gerada pelo Fusion. Estratégia v1: aceitar
  `keep="largest"` (default) e o adapter calcula a célula a manter por área.

**Erros previstos:** `fusion.trim_no_intersection`, `fusion.invalid_trim_tool`.

#### 3.10.4 `fusion.extend_surface`

**API:** `rootComp.features.extendFeatures.createInput(edges, ValueInput distance, SurfaceExtendType)`
→ `extendFeatures.add(input)`.

**Args:**
- `edge_ids` (obrigatório): lista de índices de arestas livres de SurfaceBody.
- `distance_mm` (obrigatório): extensão em mm.
- `extend_type` (`natural|perpendicular|tangent`; default `natural`).

**Semântica:** estende uma superfície ao longo de suas arestas livres.

**Erros previstos:** `fusion.extend_edges_not_free` (aresta interior ao body).

#### 3.10.5 `fusion.offset_surface`

**API:** `rootComp.features.offsetFeatures.createInput(faces, ValueInput distance, FeatureOperation)`
→ `offsetFeatures.add(input)`.

**Args:**
- `face_refs` (obrigatório): `face_ids` ou `surface_refs` (offset de SurfaceBody
  inteiro).
- `distance_mm` (obrigatório).
- `operation` (`new_body|join`; default `new_body`).

**Semântica:** cria nova SurfaceBody paralela à(s) face(s) original(is).

#### 3.10.6 `fusion.thicken_surface`

**API:** `rootComp.features.thickenFeatures.createInput(inputSurfaces, ValueInput thickness, isSymmetric, FeatureOperation, isChainSelection)`
→ `thickenFeatures.add(input)`.

**Args:**
- `surface_refs` (obrigatório): nomes ou índices de SurfaceBody.
- `thickness_mm` (obrigatório).
- `is_symmetric` (default `false`; quando `true`, espessa simétrico nos dois
  lados).
- `operation` (`new_body|join|cut|intersect`; default `new_body`).
- `chain` (default `true`): seleciona faces conectadas tangencialmente.

**Semântica:** **ponte surface → solid**. O resultado é um BRepBody sólido. É o
passo que entrega a carenagem fechada da peça-exemplo do gate.

**Erros previstos:** `fusion.thicken_self_intersection`,
`fusion.thicken_open_surface` (precisa ser fechada para espessar simétrico).

#### 3.10.7 `fusion.stitch_surfaces`

**API:** `rootComp.features.stitchFeatures.createInput(surfaces, ValueInput tolerance, FeatureOperation)`
→ `stitchFeatures.add(input)`.

**Args:**
- `surface_refs` (obrigatório): lista ≥ 2 de SurfaceBody.
- `tolerance_mm` (default `0.01`): tolerância de costura entre arestas livres.
- `operation` (`new_body|join`; default `new_body`).

**Semântica:** costura múltiplas superfícies por arestas livres adjacentes.
**Resultado pode ser sólido** se a costura fechar um volume (Fusion detecta
automaticamente).

**Erros previstos:** `fusion.stitch_gap_too_large` (tolerância insuficiente).

#### 3.10.8 `fusion.unstitch_surface`

**API:** `rootComp.features.unstitchFeatures.createInput(faces)` →
`unstitchFeatures.add(input)`.

**Args:**
- `face_ids` ou `surface_ref` (obrigatório).
- `is_chain_selection` (default `false`).

**Semântica:** quebra um SurfaceBody (ou body sólido) em superfícies individuais
por face — inverso do stitch. Útil para reparar/refazer trecho específico.

#### 3.10.9 Selectors e read-back para superfície

A T5.3 estende dois pontos sem quebrar o atual:

- **`fusion.query_geometry`**: hoje itera `rootComp.bRepBodies`; passa a iterar
  também `rootComp.bRepBodies.itemByName(...).isSolid` para distinguir
  sólido × superfície, **e** a lista paralela de SurfaceBody quando exposta pela
  API. Output ganha `is_solid: bool`, `surface_area_mm2`, `is_closed: bool`
  (`bRepBody.isSolid` é `False` para SurfaceBody).
- **`_select_faces`/`_select_edges`**: já operam em `BRepFace`/`BRepEdge`
  genéricos — SurfaceBody também os expõe. Selector novo: `free_edges` (apenas
  arestas livres da superfície, necessárias para extend/stitch).
- **Verifier do loop**: além de `dimensions_mm`, output passa a expor
  `surface_area_mm2` e `is_closed` quando relevante (criação/edição de
  superfície). `build_dimension_verifier` ganha modo `surface` (comparar área
  esperada × medida e exigir `is_closed=True` antes do thicken).

#### 3.10.10 Fluxo da peça-exemplo do gate (carenagem)

Esboço do plano que o LLM deve produzir para a carenagem Nível 2 (CS-002):

```
1.  set_parameter (largura, comprimento, espessura, raio_topo)
2.  create_sketch plane=xz name=Perfil
3.  add_spline points_mm=[[0,0],[40,30],[80,45],[120,30],[160,0]]
4.  create_sketch plane=xy name=Caminho
5.  add_spline points_mm=[[0,0],[80,50],[160,0]]
6.  sweep_profile profile=Perfil path=Caminho as_surface=true name=Casca
7.  create_surface_patch boundary=edge_ids=[...]  # tampa frente
8.  create_surface_patch boundary=edge_ids=[...]  # tampa trás
9.  stitch_surfaces surface_refs=[Casca,Patch1,Patch2] tolerance_mm=0.05
10. thicken_surface surface_refs=[Stitched] thickness_mm=1.5 is_symmetric=false
11. fillet_edges body=Body1 radius_mm=2 edge_selector=free_edges
12. export_3mf
```

Vai exigir: open profile no sweep, patch via `edge_ids` de `query_geometry`,
costura tolerante e thicken simétrico/assimétrico configurável.

## 4. Divergências intencionais vs. API canônica (consolidado)

Estas **não são bugs** — são escolhas conscientes. Documentadas para que ninguém
as "conserte" sem decisão de produto e para guiar reimplementações:

1. **`hole` = cut-extrude**, não `HoleFeatures`. Sem callout/rosca; só face
   superior planar; sem countersink. *Reimplementar com `HoleFeatures` é a
   evolução natural quando precisarmos de furos paramétricos/roscas.*
2. **`add_sphere`/`add_cone` = revolve**, não `TemporaryBRepManager`. Mantém o
   corpo editável na timeline.
3. **Selectors semânticos por bbox-Z** (`top/bottom/vertical/horizontal`), não
   topológicos. Frágeis fora de peças alinhadas aos eixos → usar `edge_ids`/
   `face_ids` de `query_geometry` quando precisar de precisão.
4. **`sweep` usa só `path.sketchCurves.item(0)`** — caminhos multi-segmento não
   encadeiam por completo.
5. **`fillet`/`chamfer` usam a forma legada** `createInput()` primeiro. Funcionam
   (chamfer tem fallback), mas o Fusion moderno prefere `createInput2()` +
   `edgeSetInputs`/`chamferEdgeSets`. *Recomendação de modernização (baixo risco,
   equivalente) — adiada para após o gate do fillet.*
6. **`add_construction_plane` só faz offset** (não angle/midplane).

## 5. Checklist anti-drift para implementar/reimplementar uma op

Cada op nova/alterada toca **5 lugares** (herdado de `adapter-tools-mvp.md` §4,
ainda válido):

1. **`fusion_mcp_scripts.py`**: adicionar à tupla `FUSION_SCRIPT_TOOLS`;
   implementar `_<tool>()` no template; registrar no dispatch. ⚠️ O template é
   uma **f-string** — **escapar todas as chaves literais** como `{{`/`}}`
   (dicts, sets, `.format`). Reusar `_eval_param`/`_eval_pair` para args
   dimensionais e os helpers de seleção (`_find_sketch`/`_find_body`/
   `_resolve_profile_selection`/`_select_edges`/`_select_faces`).
2. **`tool_registry.py`**: `ToolDescriptor` com a **categoria de risco** correta.
3. **`tool_schemas.py`**: `ToolSchema` com args, unidades e **valores válidos
   enumerados** (foi a ausência disto que esgotou o corretor no `edge_selector` —
   o schema é renderizado para o planner **e** para o corretor do loop).
4. **`planner.py`**: incluir no toolset/`EXECUTION_PLAN_SCHEMA` e descrever no
   system prompt (regras de pré-requisito, ex.: geometria antes de extrude).
5. **Testes**: `test_fusion_script_template_compiles_for_every_tool` cobre
   validade sintática (cresce sozinho); + teste de contrato de args/aliases; +
   teste de policy (categoria → `approval_required`).

**Gate por onda:** validação no **Fusion real** (container/CI é mock). Registrar
`plan_id`/`trace_id` no `handoff.md`. Conferir o trace por `query_geometry`
(dims ≠ 0, volume > 0) — não só visualmente.

## 6. Fontes

- **Autodesk Fusion 360 API — User's Manual & Reference** (fonte canônica das
  assinaturas desta §3):
  - Getting Started / Basic Concepts: <https://help.autodesk.com/cloudhelp/ENU/Fusion-360-API/files/BasicConcepts_UM.htm>
  - API Reference Manual (Object Model: `ExtrudeFeatures`, `RevolveFeatures`,
    `FilletFeatures`/`FilletInput`, `ChamferFeatures`/`ChamferInput`,
    `ShellFeatures`, `HoleFeatures`, `SweepFeatures`, `LoftFeatures`,
    `RectangularPatternFeatures`, `CircularPatternFeatures`, `MirrorFeatures`,
    `CombineFeatures`, `MoveFeatures`, `ScaleFeatures`, `ExportManager`,
    `Sketch`/`SketchCurves`).
- **Ecossistema MCP do Fusion** (camada 1; servidor genérico de execução de
  script, porta 27182): página oficial *Autodesk MCP Servers*
  (<https://www.autodesk.com/solutions/autodesk-ai/autodesk-mcp-servers>) e
  implementações de comunidade equivalentes (ex.: `Joe-Spencer/fusion-mcp-server`,
  `faust-machines/fusion360-mcp-server`).
- Internos: ADR-013/017/019 (`docs/decisions.md`), `adapter-tools-mvp.md`
  (proposta original — mapeamentos de API **substituídos** por este documento
  onde divergem), `fusion_mcp_scripts.py`.
