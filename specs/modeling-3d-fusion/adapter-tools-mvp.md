# Spec — Expansão do adapter Fusion para MVP de modelagem completa

> **Status:** proposta, aguardando aprovação do dono do produto.
> **Autor:** Claude Code (sessão Onda 7+), 2026-05-20.
> **Relacionado:** ADR-013 (3D chat-first), `tool_registry.py`, `fusion_mcp_scripts.py`,
> `observability-plan.md`, `handoff.md` (Onda 7).

## 1. Contexto

A observabilidade da Onda 7 expôs, via traces reais, que o adapter Fusion só
sabe **"desenhar retângulo/círculo plano + extrudar"**. Pedidos comuns falham
porque faltam operações de modelagem de nível médio. Evidências (traces):

- **Bola de futebol** (`mt_019e432d6116...`): `create_sketch` cria sketch
  vazio; o LLM descreve "draw a regular pentagon" no campo `notes` (ignorado);
  `extrude_profile` falha com `fusion.no_profile`. Não há `revolve`,
  `add_polygon` nem `add_sphere`. Resultado: 0 bodies.
- **Porta-figurinhas** (`mt_019e3e66...`): precisava de grade de bolsos (resolvido
  com `add_rectangle` grid) **e** de ocar a caixa (`shell`, inexistente) — paredes
  ficaram impossíveis.
- **Hints órfãos**: `planner.py` lista `fillet`, `chamfer`, `rosca` como
  palavras-chave Fusion, mas não há tools correspondentes — o LLM é induzido a
  pedir algo que o adapter não executa.

**Objetivo:** definir o conjunto de tools que torna o adapter capaz de produzir
~90% dos modelos imprimíveis comuns, com contrato de args estável, categoria de
risco correta e cobertura de teste.

## 2. Capacidades atuais (baseline — 11 tools)

| Tool | Categoria | Observação |
|---|---|---|
| `fusion.open_design` | additive | cria documento |
| `fusion.create_sketch` | additive | cria sketch **vazio** num plano |
| `fusion.add_rectangle` | additive | retângulo único + modo grade (cols/rows) |
| `fusion.add_circle` | additive | círculo |
| `fusion.extrude_profile` | mutative | new_body/join/cut/intersect |
| `fusion.set_parameter` | mutative | user parameters (bulk + implícito) |
| `fusion.validate_dimensions` | read_only | inspeção de bbox/volume |
| `fusion.validate_printability` | read_only | checagens de impressão |
| `fusion.export_step/stl/3mf` | additive | exports |

## 3. Gap — tools propostas

Categorias seguem `ToolCategory` em `tool_registry.py`
(`additive`/`mutative`/`destructive`/`high_risk`/`read_only`). Risco mapeia
para `approval_required` via policy.

### Onda A — sketch primitives + revolve (destrava a maioria das formas)

| Tool | Categoria | Args (contrato) | Fusion API |
|---|---|---|---|
| `fusion.add_polygon` | additive | `sketch`, `sides:int>=3`, `diameter_mm` ou `radius_mm`, `center_mm=[x,y]`, `inscribed:bool=true` | `sketchCurves.sketchLines` (constrói N lados) ou `addScribedPolygon` |
| `fusion.add_line` | additive | `sketch`, `points_mm=[[x,y],...]` (>=2), `closed:bool` | `sketchCurves.sketchLines.addByTwoPoints` em loop |
| `fusion.add_arc` | additive | `sketch`, `center_mm`, `start_mm`, `sweep_deg` | `sketchArcs.addByCenterStartSweep` |
| `fusion.revolve_profile` | mutative | `sketch`, `axis:"x"\|"y"\|"z"\|line_ref`, `angle_deg=360`, `operation` | `revolveFeatures` |

`add_polygon` sozinho destrava pentágonos/hexágonos. `revolve_profile` com um
meio-círculo destrava **esferas, cones, vasos, qualquer sólido de revolução**.

### Onda B — primitivas diretas (1 step em vez de sketch+extrude)

| Tool | Categoria | Args | Fusion API |
|---|---|---|---|
| `fusion.add_box` | additive | `width_mm`, `depth_mm`, `height_mm`, `center_mm=[0,0,0]` | TemporaryBRepManager ou sketch+extrude interno |
| `fusion.add_cylinder` | additive | `diameter_mm`, `height_mm`, `center_mm` | idem |
| `fusion.add_sphere` | additive | `diameter_mm`, `center_mm` | TemporaryBRepManager.createSphere |
| `fusion.add_cone` | additive | `base_diameter_mm`, `top_diameter_mm=0`, `height_mm` | revolve interno |

Decisão de design: implementar primitivas via **sketch+feature interno** (não
TemporaryBRep) quando possível, para que apareçam na timeline paramétrica e
sejam editáveis. `add_sphere` provavelmente precisa de revolve de semicírculo.

### Onda C — features de modificação (essenciais p/ peças funcionais)

| Tool | Categoria | Args | Fusion API |
|---|---|---|---|
| `fusion.fillet_edges` | mutative | `radius_mm`, `edge_selector:"all"\|"top"\|"bottom"\|tokens` | `filletFeatures` |
| `fusion.chamfer_edges` | mutative | `distance_mm`, `edge_selector` | `chamferFeatures` |
| `fusion.shell_body` | mutative | `thickness_mm`, `open_faces:"top"\|tokens`, `body_ref` | `shellFeatures` |
| `fusion.hole` | mutative | `diameter_mm`, `depth_mm`, `position_mm`, `face_ref`, `type:"simple"\|"counterbore"\|"countersink"` | `holeFeatures` |

`shell_body` resolve caixas/recipientes (porta-figurinhas). `fillet`/`chamfer`
honram os hints já existentes no planner.

### Onda D — replicação e combinação

| Tool | Categoria | Args | Fusion API |
|---|---|---|---|
| `fusion.pattern_rectangular` | mutative | `feature_ref`, `count_x`, `spacing_x_mm`, `count_y`, `spacing_y_mm` | `rectangularPatternFeatures` |
| `fusion.pattern_circular` | mutative | `feature_ref`, `count`, `axis`, `total_angle_deg=360` | `circularPatternFeatures` |
| `fusion.mirror_feature` | mutative | `feature_ref`, `plane:"xy"\|"yz"\|"xz"` | `mirrorFeatures` |
| `fusion.combine_bodies` | high_risk | `target_ref`, `tool_refs[]`, `operation:"join"\|"cut"\|"intersect"` | `combineFeatures` |

`combine_bodies` é `high_risk` porque pode destruir topologia de bodies
existentes (exige aprovação humana, conforme AGENTS.md).

### Onda E — sweeps avançados + construção (completa o leque)

| Tool | Categoria | Args | Fusion API |
|---|---|---|---|
| `fusion.loft_profiles` | mutative | `profiles[]` (sketch refs ordenados), `operation` | `loftFeatures` |
| `fusion.sweep_profile` | mutative | `profile`, `path`, `operation` | `sweepFeatures` |
| `fusion.add_construction_plane` | additive | `type:"offset"\|"angle"\|"midplane"`, `base`, `value` | `constructionPlanes` |
| `fusion.add_spline` | additive | `sketch`, `points_mm[]` | `sketchFittedSplines` |

### Onda F — modificação direta de bodies

| Tool | Categoria | Args | Fusion API |
|---|---|---|---|
| `fusion.move_body` | mutative | `body_ref`, `translation_mm=[x,y,z]`, `rotation_deg` | `moveFeatures` |
| `fusion.scale_body` | mutative | `body_ref`, `factor` ou `factors=[x,y,z]` | `scaleFeatures` |
| `fusion.delete_body` | destructive | `body_ref` | `removeFeatures` (aprovação obrigatória) |

## 4. Mudanças transversais (cross-cutting)

Cada tool nova exige tocar 4 lugares — checklist por tool:

1. **`fusion_mcp_scripts.py`**
   - adicionar à tupla `FUSION_SCRIPT_TOOLS`
   - implementar `_<tool>()` no template (cuidado: f-string, escapar `{{}}`)
   - registrar em `_dispatch`
   - **reusar `_eval_param`/`_eval_pair`** para todos os args dimensionais
     (suporte a expressões paramétricas já existe — fix #10)
2. **`tool_registry.py`** — adicionar `ToolDescriptor` com categoria correta
3. **`planner.py`** — incluir no `EXECUTION_PLAN_SCHEMA`/toolset exposto ao LLM
   e descrever no system prompt
4. **`planner` system prompt** — **mudança crítica**: explicitar que
   `create_sketch` cria sketch **vazio** e que o LLM DEVE chamar uma tool de
   geometria (`add_rectangle`/`add_circle`/`add_polygon`/`add_line`) **antes**
   de `extrude_profile`/`revolve_profile`; proibir geometria no campo `notes`.
5. **Testes**
   - `test_fusion_script_template_compiles_for_every_tool` já cobre validade
     sintática (cresce automático ao adicionar à tupla)
   - teste de contrato por tool: args canônicos + aliases + expressões
   - teste de policy: categoria → `approval_required` correto

### Resolução de referências (`*_ref`)

Várias tools novas referenciam features/bodies/edges existentes
(`feature_ref`, `body_ref`, `edge_selector`). Hoje sketches são resolvidos por
nome (`_find_sketch`). Proposta: estender o padrão com:

- `body_ref` por nome (`Body1`) ou índice (`0`); helper `_find_body`
- `feature_ref` por nome da timeline; helper `_find_feature`
- `edge_selector` semântico (`"all"`, `"top"`, `"vertical"`) em vez de tokens
  opacos — o LLM não tem como saber edge tokens do Fusion. Esta é a decisão de
  design mais importante da Onda C: **selectors semânticos** resolvidos
  server-side por heurística geométrica (ex: "top" = arestas no maior Z).

## 5. Ordem de implementação recomendada

Por impacto/custo (cada onda é um PR):

1. **Onda A** (polygon, line, arc, revolve) — destrava esferas e polígonos;
   resolve a bola de futebol. **Maior ROI.**
2. **Onda C** (fillet, chamfer, shell, hole) — peças funcionais reais;
   honra hints órfãos do planner.
3. **Onda B** (primitivas diretas) — conveniência, reduz steps.
4. **Onda D** (pattern, mirror, combine) — replicação.
5. **Onda E/F** — avançado, sob demanda.

**Pré-requisito de todas:** a mudança #4 (planner prompt) deve ir junto com a
Onda A, senão o LLM continua pondo geometria em `notes`.

## 6. Estratégia de teste

- **Unit (sem Fusion):** `test_fusion_script_template_compiles_for_every_tool`
  garante que cada novo template é Python válido. Testes de contrato verificam
  parsing de args/aliases/expressões sem chamar a API.
- **Integração (com Fusion real):** smoke manual por onda — um prompt
  representativo (ex: "uma esfera de 50mm", "uma caixa ocada 60x40x30 parede 2mm")
  → verificar bodies no Fusion + export OK. Registrar trace_id no handoff.
- **Regressão:** suíte completa `pytest tests/` deve continuar verde.

## 7. Fora de escopo (não-MVP)

- Assemblies, joints, componentes múltiplos.
- Sheet metal, surfaces NURBS complexas, T-Spline/sculpt.
- Simulação (FEA), CAM/usinagem, generative design.
- Renderização e aparências/materiais visuais.
- Edição destrutiva de timeline (rollback de features individuais além de
  snapshot — o snapshot atual já cobre o rollback de plano inteiro).

## 8. Riscos e trade-offs

- **Selectors de edge/face são o ponto mais frágil.** Sem selectors semânticos
  robustos, fillet/chamfer/shell viram tentativa-e-erro. Mitigação: começar com
  selectors grossos (`"all"`, `"top"`, `"bottom"`) e refinar.
- **Primitivas diretas vs. paramétricas.** TemporaryBRep é mais simples mas gera
  body não-editável; sketch+feature é editável mas mais código. Decisão: preferir
  paramétrico.
- **Crescimento do prompt do planner.** Mais tools = prompt maior = mais tokens
  por request. Aceitável; monitorar via `planner.llm_request` no trace.
- **`high_risk`/`destructive`** (combine, delete) exigem aprovação humana inline
  — não quebrar o contrato de auto-execução do fluxo fluido (AGENTS.md).
