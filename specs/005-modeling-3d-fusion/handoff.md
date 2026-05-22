# handoff.md

> **Para a próxima IA/humano que pegar o trabalho:** leia esse arquivo
> inteiro **antes** de tocar código. As seções abaixo descrevem o que já
> está em produção, o que está em PR aberto, os gaps que ficaram
> explicitamente sem fazer, e como continuar a partir da Onda 6. As
> decisões consolidadas com o dono do produto seguem firmes —
> não reabrir sem aprovação.

## Estado atual

Refatoração v2 (chat-first integral + título obrigatório). **Onda 5
concluída localmente** na branch `codex/3d-chat-title-required`; falta
PR/merge.

### Redesenho do processo 3D (discovery→aprovação→edição) — spec `chat-flow-redesign.md`

Pedido do dono do produto (2026-05-20): (1) agente deve perguntar antes de
planejar; (2) plano não pode executar sem aprovação; (3) edição não pode
quebrar/recriar o modelo. Diagnóstico: a maquinaria chat-first
(`chat_state.py` + `chat_orchestrator.py` + cards no front) já existe, mas a
rota de chat a ignorava e auto-executava em `safe_auto`. Faseado em P1–P4 na
spec. **Decisões do dono:** aprovação sempre (primário e edições), com "modo
fluido" opt-in por chat liberando edições aditivas (P3); discovery pergunta
só quando ambíguo (limiar); follow-up assume edição por default e pergunta se
ambíguo (P3 corrige `open_design` que recria `Untitled`).

- **P1 ENTREGUE** (branch `feat/modeling-3d-approval-gate`): rota
  `chat.py:modeling_events` deixou de auto-executar; força
  `waiting_approval`, emite o card e PARA; sessão → `planning`. Execução só
  via `/approve`+`/execute` (card já ligado). Teste
  `test_chat_stream_proposes_plan_without_executing`. Revisa a ADR-013
  (fluxo fluido vira opt-in na P3).
- **P2 ENTREGUE** (mesma branch): discovery agent (`app/modeling/discovery.py`)
  avalia o pedido antes de planejar e **pergunta só quando ambíguo** (limiar
  de confiança). `ModelingPlannerService.assess_request_async` reusa modelo+
  gateway+tracer; rota `chat.py` faz as perguntas e PARA quando não-pronto
  (chat fica em `discovery`), ou usa `refined_brief` quando pronto. Flags
  `MODELING_DISCOVERY_ENABLED`/`_THRESHOLD`. Testes em
  `test_modeling_discovery.py` + rota.
- **P3 ENTREGUE** (mesma branch): (a) `open_design` reusa o design ativo por
  padrão (corrige "edição quebra/recria o modelo"; force-new via
  `new_document`/`reset`); (b) `/execute` avança o chat para `editing`;
  (c) discovery classifica `intent` edit/new_model/ambiguous (default edit
  quando há modelo) — ambíguo PERGUNTA, edit vira `kind=edit`, new_model força
  doc limpo; (d) **modo fluido** opt-in (`modeling_fluid_mode`): edição
  aditiva sem high-risk auto-executa, default OFF. Testes em
  `test_modeling_discovery.py` + `test_modeling_routes.py`. **Validação real
  pendente:** qualidade do delta de edição (precisa do estado do modelo via
  G2.2) e comportamento de documento do `open_design` — iterar via
  fix-by-trace no Fusion.
- **P4 ENTREGUE** (mesma branch): `PATCH /api/3d/plans/{id}`
  (`ModelingService.edit_plan`) edita o plano enquanto draft/waiting_approval
  — envia a lista completa de etapas (editar/reordenar/remover/adicionar),
  valida tool_name contra a allowlist (422), re-aplica policy e mantém
  waiting_approval; 409 após aprovação. Frontend: `editPlan` no api+hook +
  editor inline no `ModelingPlanCard` (título/tool/risco/JSON, mover, remover,
  adicionar, valida JSON). Testes backend `test_edit_plan_*` + front
  `ModelingPlanCard.test.tsx`.

- **P5 ENTREGUE** (mesma branch): planner de edição ciente do modelo atual.
  `build_edit_context_block` injeta no prompt do planner (quando `kind=edit`)
  o histórico de construção do plano-pai + métricas de corpos extraídas das
  saídas executadas; instrui a gerar só o delta e não recriar a base.
  `_resolve_edit_context` busca o pai por `parent_plan_id`. Testes
  `test_build_edit_context_block_*`. **Limitação:** usa estado CONHECIDO (não
  leitura ao vivo do Fusion); evolução futura é persistir snapshot de
  `query_geometry` após cada execução.

**Redesenho do processo 3D COMPLETO (P1–P5).** Próximo passo principal:
validar tudo no Fusion real via fix-by-trace — em especial P3 (edição/
open_design) e a qualidade dos deltas com o contexto da P5.

| Onda                                                 | Status               | PR                   | Commits-chave                         |
| ---------------------------------------------------- | -------------------- | -------------------- | ------------------------------------- |
| 0 — Specs/docs/ADRs                                  | mergeado             | #19                  | `bf9395a`                             |
| 1 — Backend foundations                              | mergeado             | #19                  | `0546ff8` → `371eb0e`                 |
| 2 — Backend chat-first orchestration                 | mergeado             | #20                  | `f5269b7` → `c3cb10c`                 |
| 3 — Frontend feature module 3D                       | mergeado             | #21 + fixes #22, #24 | `a94a273`                             |
| 4 — Frontend cards + aprovação inline + auto-analyze | mergeado             | #25                  | `cf42144` → `424be99`                 |
| 5 — Título obrigatório do chat (frontend)            | concluída localmente | —                    | branch `codex/3d-chat-title-required` |
| 6 — QA / docs finais + wire orchestrator no stream   | iniciada (hotfix QA) | —                    | —                                     |
| 7 — Observabilidade + 13 fixes do adapter Fusion     | mergeada na master   | #27/#28/#29          | ver seção Onda 7                      |
| 8A — Expansão adapter Fusion (revolve + polygon)     | em PR                | —                    | branch `feat/fusion-revolve-polygon`  |
| 8B — Primitivas diretas (box/cylinder/sphere/cone)   | em PR                | —                    | branch `feat/fusion-primitives-onda-b` |
| 8C — Features (fillet/chamfer/shell/hole)            | em PR                | —                    | branch `feat/fusion-features-onda-c`  |
| 8D-F — Replicação/sweeps/modificação direta          | em PR                | —                    | branch `feat/fusion-onda-def`         |

### Bug de geometria: hole consumia a peça (placa, 4º teste, 20/05) — branch `fix/fusion-param-expression-syntax`

Trace `mt_019e46e06f3b` — **todos os 11 steps OK**, mas o modelo saiu errado:
sobrou só um cilindro Ø10×5mm (validate_printability: `Body1` dims [10,10,5],
volume 392.7mm³ = π·5²·5). A placa 80×60×5 foi consumida. 1º teste do
`fusion.hole` em Fusion REAL.

**Causa raiz (geometria, não schema):** `_hole` cria o sketch SOBRE a face
superior da peça. Ao criar sketch sobre uma face existente, o Fusion inclui o
contorno da face no sketch → desenhar o círculo gera 2 profiles: o disco
central e o ANEL (face menos círculo). `sketch.profiles.item(0)` pegava o
anel; o CUT removeu tudo menos o miolo → restou o plug cilíndrico.

**Fix:** helper `_profile_for_circle(sketch, radius_cm)` escolhe o profile
cuja área bate com π·r² (fallback: menor área, depois item(0)). Aplicado ao
furo principal e ao counterbore. **Limitação latente análoga:**
`_extrude_profile` também usa `profiles.item(0)` — se o LLM criar um sketch
de corte sobre uma face com múltiplos profiles, mesmo risco; não corrigido
agora (o plano usou o tool `hole`). Documentar/observar.

Teste: `test_hole_uses_circle_profile_selector` (compile + presença do helper;
geometria real só valida no Fusion).

### Schema drift convenção `_param` (placa, 3º teste, 20/05) — branch `fix/fusion-param-expression-syntax`

Trace `mt_019e46d6dc46` (3ª iteração da placa). O LLM mudou de novo o plano
(12 steps com `set_parameter` + `create_sketch` + `add_rectangle`/`add_circle`
+ extrude) e expôs 1 drift **sistemático**: ele expressa vínculo paramétrico
com o sufixo **`_param`** carregando o NOME do parâmetro:

- `add_rectangle`: `width_param:"plate_length"`, `height_param:"plate_width"`.
- `extrude_profile`: `distance_param:"plate_thickness"`.
- `add_circle`: `diameter_param:"hole_diameter"`.

**Fix (genérico, no `_dispatch`):** helper `_normalize_param_suffix` mapeia
QUALQUER chave `<base>_param` → `<base>_mm` (só se a `_mm` canônica não veio),
preservando o nome do parâmetro como valor. Os helpers `_eval_param`/
`_param_value_input`/`_param_name_or_none` já resolvem nome de parâmetro como
vínculo (G1.1/G1.2). Resolvido para TODAS as tools dimensionais de uma vez —
mata a classe inteira desse drift. `set_parameter`/`validate_dimensions` não
têm chaves que terminam exatamente em `_param` (`parameters`/`check_parameters`
não casam), então é seguro.

Teste: `test_schema_drift_param_suffix_convention`. Documentado o fluxo
fix-by-trace + scripts SQL de debug em `docs/3d-mcp-modeling.md` (seção
"Debug de schema drift do adapter Fusion").

### Schema drift add_box lista de dimensões (placa, 2º teste, 20/05) — branch `fix/fusion-param-expression-syntax`

Trace `mt_019e46cf2726` (re-teste da placa após o fix de sintaxe de
expressão). Os drifts anteriores sumiram (set_parameter/add_circle OK). O
LLM gerou plano DIFERENTE (7 steps, `add_box` direto) e expôs 1 drift novo
+ 2 falhas em cascata:

- **add_box** (raiz): o LLM manda as 3 medidas numa lista única
  `dimensions_mm:[80,60,5]` (+ chave extra `primitive:"box"` e
  `origin_mm:[0,0,0]` como CANTO), não `width_mm`/`depth_mm`/`height_mm`.
  Step falhava com `... precisam ser positivos`. **Fix:** aceitar
  `dimensions_mm`/`size_mm`/`dimensions`/`size` como lista [w,d,h]; tratar
  `origin_mm` como canto inferior (senão `center_mm` centraliza). Isso também
  alinha a semântica: o LLM põe o furo em `[40,30]` = centro de uma placa
  0..80×0..60 ancorada no canto.
- **extrude_profile cut** (step 5) e **export_stl** (step 7) falharam em
  CASCATA — sem body (add_box falhou), o cut não tinha alvo e o STL achou o
  design vazio. Devem resolver sozinhos com o add_box corrigido; se o cut
  coincidente (5mm através de 5mm) falhar, próximo passo é honrar `through_all`.

Teste: `test_schema_drift_add_box_dimensions_list`.

### Schema drift sintaxe de expressão (placa parametrizada, 20/05) — branch `fix/fusion-param-expression-syntax`

Trace `mt_019e46942241` (prompt "placa 80x60mm espessura 5mm com furo
central de 10mm, tudo parametrizado"). O LLM produziu plano paramétrico de
13 steps mas a maioria falhou no parsing de args com 3 drifts novos — todos
de **sintaxe de expressão paramétrica do Fusion**:

- **set_parameter**: o LLM emite o valor em `value_mm` (ou `value`/`value_cm`/
  `value_deg`) em vez de `expression` (ex: `{name:"plate_width", value_mm:80}`).
  Steps davam `name e expression são obrigatórios`. **Fix:** no caminho
  singular, aceitar `value_mm`/`value`/... como alias de `expression`, com a
  unidade inferida do sufixo do alias.
- **chaves dimensionais sem sufixo**: `add_rectangle` recebia `width`/`height`,
  `add_circle` recebia `radius`/`diameter`, `extrude_profile` recebia
  `distance` (sem `_mm`). **Fix:** normalização no topo de cada função mapeia
  o alias sem sufixo para a chave canônica `_mm` (cobre valor + amarração G1.2).
- **`=` líder (sintaxe da barra de parâmetros do Fusion)**: o LLM manda
  `"=plate_width"`, `"=thickness"`, `"=hole_diameter/2"`. **Fix:** `_eval_param`,
  `_param_value_input` e `_param_name_or_none` removem o `=` líder antes de
  resolver — nome puro vira vínculo paramétrico (G1.1/G1.2), expressão composta
  é bakeada.

Observabilidade funcionou de novo: o 1º trace (`mt_019e469343b9`) caiu por
erro de rede da OpenAI (`Server disconnected`) e fez fallback heurístico
corretamente; o 2º obteve plano LLM e expôs exatamente estes drifts.

Teste: `test_schema_drift_param_expression_syntax`.

### Schema drift G5 (teste real da bola, 20/05) — branch `fix/fusion-schema-drift-arc-line-sketch`

Trace `mt_019e45f8c20e_0bbd73d75b34eacc` (bola via revolve manual) expôs
4 drifts LLM↔adapter (todos no parsing de args, antes da API do Fusion):

- **create_sketch** não aceitava `sketch` como nome → o LLM usava
  `sketch: "profile_sketch"` em todos os steps, o nome virava default
  `TF_Sketch`, e os steps seguintes davam `sketch_not_found` (drift de
  identidade). **Fix mais crítico**: aceitar `sketch` como alias do nome.
- **add_arc** só aceitava `center+start_mm+sweep_deg`; o LLM manda forma
  POLAR (`center+radius_mm+start_angle_deg+end_angle_deg`). Aceita os dois.
- **add_line** só aceitava `points_mm[]`; o LLM manda `start_mm+end_mm`
  para uma linha única. Aceita os dois.
- **revolve_profile** aceitava só `operation`; o LLM manda `result`. Alias.

Também: nudge no prompt do planner para **preferir primitivas diretas**
(`add_sphere`/`add_box`/`add_cylinder`/`add_cone`) em formas básicas, e
aviso de que o meio-perfil do revolve não pode cruzar o eixo (o LLM tinha
feito um semicírculo completo cruzando o eixo — sólido inválido).

Teste: `test_schema_drift_arc_line_sketch_revolve_aliases`.

### Onda 9 — G1.2 (seguro) + hole v2 — branch `feat/fusion-g1.2-sketch-params`

- **G1.2 (parametrização de sketch):** `add_rectangle` (single) e `add_circle`
  agora amarram width/height/diameter/radius ao parâmetro quando o arg é uma
  referência pura a userParameter (helper `_param_name_or_none`). **Padrão
  seguro:** a geometria é desenhada primeiro (bakeada no valor resolvido) e
  a `sketchDimension` é adicionada DEPOIS em `try/except` — se a API falhar
  ou over-constrain, o try/except mantém a geometria bakeada (zero regressão
  no extrude). Resposta marca `[parametrico]` quando o vínculo foi criado.
  Grid de retângulos e primitivas (box/cylinder) seguem bakeados por ora.
- **G3 hole v2:** `fusion.hole` aceita `type=counterbore` +
  `counterbore_diameter_mm`/`counterbore_depth_mm` (recesso cilíndrico para
  cabeça de parafuso, via 2º cut). countersink (cônico) fica para futuro
  (exige revolve/chamfer da borda).
- **Validar com Fusion real:** a API `sketchDimensions.addDiameterDimension/
  addRadialDimension/addDistanceDimension` e o counterbore. Como tudo é
  guarded, o pior caso é "não parametrizou" (não quebra).

### Onda 9 restante (G2.2 + G2.3 + G3 parcial + G4 decisão) — branch `feat/fusion-gaps-onda9-rest`

- **G2.2:** `fusion.query_geometry` (read-only) lista bodies/faces/arestas
  com índice + metadata; fillet/chamfer aceitam `edge_ids`, shell aceita
  `face_ids`. O LLM pode consultar e mirar por índice (preciso) em vez de
  adivinhar selectors.
- **G2.3:** `result_name`/`output_name` nos body-creators (rename pós-criação
  centralizado no `_dispatch` via `_maybe_rename_last_body`) → handle estável
  para pattern/mirror/fillet. Mitiga o drift de identidade.
- **G3 parcial:** `add_ellipse`, `add_slot` (sketch primitives), `split_body`
  (divisão por plano construtivo/offset). Restante do long-tail sob demanda.
- **G1.2 ADIADO** (com critério): mexe em add_rectangle/add_circle que toda
  modelagem composta usa; sketch dimensions não-testadas arriscam
  over-constraint regredindo o extrude. Fazer com Fusion real no loop.
- **G4 BLOQUEADO por decisão:** `g4-assemblies-decision.md` — opções A
  (single-body, recomendada) / B (componentes leves) / C (assemblies
  completo). Muda data model + UI; aguarda o dono.

Total: **50 tools** (era 24 no v1). Validação real das tools novas (G2.2/G3
+ G1.1/G2.1/G5) pendente — observabilidade mostra divergência de API.

### Onda 9 parcial (G1.1 + G2.1 + G5) — branch `feat/fusion-gaps-g1-g2-g5`

Da spec `adapter-gaps-roadmap.md`, entregues as 3 fases de maior alavanca:

- **G1.1 (parametrização real):** helper `_param_value_input(arg, design)`
  — se `arg` é nome de parâmetro existente, usa `createByString` (cria
  VÍNCULO; mudar o param depois atualiza a geometria); senão `createByReal`
  (bakeado). Aplicado em extrude/fillet/chamfer/shell. Resolve a limitação
  conceitual #1 (modelo era não-editável-por-parâmetro) nas distâncias de
  feature. **Pendente G1.2**: amarrar dimensões de SKETCH (rectangle/circle)
  aos params — mais complexo (precisa sketchDimensions).
- **G2.1 (selectors finos):** arestas `longest`/`shortest`; faces
  `planar`/`cylindrical`/`largest`/`+x`..`-z` (por normal). Soma aos
  top/bottom/vertical/horizontal da Onda C. **Pendente**: `near=[x,y,z]`
  (vai com G2.2 query_geometry).
- **G5 (robustez por versão):** `chamferFeatures` e `moveFeatures` agora
  tentam a API antiga (`createInput`) e caem para a nova (`createInput2`
  + `chamferEdgeSets`/`defineAsFreeMove`) via try/except — cobre versões
  diferentes do Fusion sem o usuário precisar reportar.

Teste: `test_g1_g2_g5_scripts_compile`. **Pendente da Onda 9:** G1.2,
G2.2 (`query_geometry` + `near`), G2.3 (feature refs estáveis), G3
(long-tail de features), G4 (assemblies — **precisa decisão de escopo**).

### Schema drift 2 (2o teste da bola, 20/05) — branch `fix/fusion-pattern-shell-aliases`

MARCO: `add_sphere` funcionou, esfera materializou pela 1a vez (8/9 steps
OK, STL exportado). Mas o resultado foi esfera SÓLIDA com 1 dente de
pentágono, não bola de futebol. Trace `mt_019e4623c801` expôs:

- **pattern_circular fez 1x**: o LLM manda `occurrences`/`angle_deg`, o
  tool lia só `count`/`total_angle_deg` → count defaultava 1 (no-op).
  Fix: aceitar `occurrences`/`quantity`/`instances` + `angle_deg`.
- **shell_body**: o LLM manda `faces`/`body_name`, o tool lia
  `open_faces`/`body_ref`. Fix: aceitar `faces` (+ "all"→"none" enclosed)
  e `body_name`. Esfera fechada ainda falha no shell (limitação do Fusion
  para sólido sem face plana — esperado).
- **body_name alias** adicionado nos 10 call sites de `_find_body`.

**Limitação conceitual (não-bug):** o LLM modela "soccer ball" como
pentágono plano + cut + pattern num plano — geometricamente ingênuo. Um
icosaedro truncado real precisa de matemática esférica de posicionamento
de 32 painéis, que o LLM não faz. Nenhum fix de adapter resolve isso;
seria prompt/estratégia de modelagem ou uma tool dedicada de alto nível.

Teste: `test_pattern_shell_accept_llm_aliases`.

### Onda 8D-F — pattern/mirror/combine + loft/sweep/plane/spline + move/scale/delete

Branch `feat/fusion-onda-def` (encadeada sobre C→B→A). 11 tools.
Total agora: **47 tools** (era 24 no v1).

- **D (replicação/combinação):** `pattern_rectangular`,
  `pattern_circular`, `mirror_feature` (mutative; operam sobre bodies
  via `_find_body`), `combine_bodies` (**high_risk** — boolean entre
  bodies existentes, aprovação obrigatória).
- **E (sweeps/construção):** `loft_profiles` (2+ sketches),
  `sweep_profile` (profile + path via `createPath`),
  `add_construction_plane` (offset; additive), `add_spline` (additive).
- **F (modificação direta):** `move_body` (translação via Matrix3D),
  `scale_body` (uniforme em torno da origem), `delete_body`
  (**destructive** — `removeFeatures`, aprovação obrigatória).

**APIs sensíveis a versão a validar com Fusion real** (a observabilidade
mostra divergência): `rectangularPatternFeatures.createInput` (assinatura
+ `PatternDistanceType`), `circularPatternFeatures` quantity/totalAngle,
`createPath` no sweep, `moveFeatures.createInput`/`scaleFeatures.createInput`
(deprecadas em favor de `createInput2` em versões novas).

### Onda 8C — fillet/chamfer/shell/hole + selectors semânticos

Branch `feat/fusion-features-onda-c` (encadeada sobre B → A). 4 tools
`mutative` + 3 helpers de seleção em `fusion_mcp_scripts.py`:

- `_find_body(design, ref)` — body por nome/índice/último.
- `_select_edges(body, selector)` — selectors SEMÂNTICOS
  (`all`/`top`/`bottom`/`vertical`/`horizontal`) resolvidos por heurística
  geométrica de Z (o LLM não conhece edge tokens do Fusion).
- `_select_faces(body, selector)` — `top`/`bottom`/`none` para shell.
- `fusion.fillet_edges` / `fusion.chamfer_edges` — arredonda/chanfra.
- `fusion.shell_body` — oca (open_faces top/bottom/none).
- `fusion.hole` — MVP pragmático: circle + cut-extrude na face superior
  (NÃO usa holeFeatures, que exige point/face refs precisos). Limitação:
  assume face superior planar.

**Pontos frágeis a validar no Fusion real** (a observabilidade vai
mostrar se a API divergir): selectors de aresta em geometria curva,
`chamferFeatures.createInput`+`setToEqualDistance` (varia por versão),
direção do cut em `hole`. Total agora: 36 tools (era 24 no v1).

### Onda 8A — add_polygon/add_line/add_arc/revolve_profile + fix do prompt

Spec: `specs/005-modeling-3d-fusion/adapter-tools-mvp.md`. Branch
`feat/fusion-revolve-polygon`. Entregue:

- **4 tools novas** em `fusion_mcp_scripts.py` (template + dispatch + tupla)
  + registry + planner toolset: `fusion.add_polygon` (N lados),
  `fusion.add_line` (polilinha fechável), `fusion.add_arc`,
  `fusion.revolve_profile` (esferas/cones/vasos). Todas reusam
  `_eval_param`/`_eval_pair` (suporte a expressão paramétrica).
- **Fix do prompt do planner** (causa raiz do `no_profile`): system prompt
  agora explicita que `create_sketch` cria sketch VAZIO e exige uma tool de
  geometria antes de extrude/revolve; proíbe geometria em campos de texto
  (`notes`/`description`); orienta revolve para esfera e polygon para
  pentágono/hexágono.
- **Quick fixes de schema drift**: `add_circle` aceita
  `circle_diameter_mm`/`radius_mm`/`center_mm`; `extrude_profile` mapeia
  `operation` desconhecida (ex: `join_or_new_body`) para `new_body` com
  warning no message em vez de abortar.
- **Testes**: `test_onda_a_tools_are_registered_and_compile`,
  `test_add_circle_accepts_aliases`, atualizado
  `test_planner_toolset_matches_allowlist` (24 → 28 tools).
- **Pendente**: validação manual com Fusion real (esfera por revolve,
  hexágono por polygon). Próximas ondas (B-F) na spec.

Verificação ao fim da Onda 4 (local, Windows):

- `pytest tests/ --ignore=tests/test_postgres_store.py` → **243 verdes**
- `pnpm test:unit` → **60 verdes** em 11 arquivos (16 novos)
- `pnpm typecheck` → limpo
- `alembic history` linear `001 → 002 → 003 → 004`

Verificação da Onda 5 (local, Windows):

- `backend\.venv\Scripts\python.exe -m ruff format --check backend\app\api\routes\chat.py backend\tests\test_chat_title_required.py` → limpo.
- `backend\.venv\Scripts\python.exe -m ruff check backend\app\api\routes\chat.py backend\tests\test_chat_title_required.py` → limpo.
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_chat_title_required.py -q` → **8 verdes**.
- `backend\.venv\Scripts\python.exe -m pytest backend\tests --ignore=backend\tests\test_postgres_store.py --ignore=backend\tests\test_alembic_migrations.py -q` → **239 verdes**.
- `pnpm --filter @truths-forge/web lint` → limpo.
- `pnpm --filter @truths-forge/web typecheck` → limpo.
- `pnpm --filter @truths-forge/web test:unit` → **68 verdes**.
- `pnpm --filter @truths-forge/web exec prettier --check <arquivos tocados>` → limpo.
- `pnpm --filter @truths-forge/docs build` → limpo com warning conhecido de `vscode-languageserver-types`.
- Smoke visual local em `http://127.0.0.1:5173` → modal abriu antes do envio, bloqueou título vazio, aceitou `Smoke título obrigatório` e o backend persistiu a sessão com mensagem sem `chat_title_required`.

Limitações: `pnpm --filter @truths-forge/web format:check` completo ainda
falha por 38 arquivos preexistentes fora do escopo. A suíte backend completa
sem ignores parou na coleta porque o venv atual não tem `alembic`.

---

## Hotfix QA Fusion após Onda 5

Sintoma reportado no Fusion real: com MCP Fusion configurado, qualquer prompt
caía no mesmo fallback retangular (`add_rectangle 40x20` + extrusão 12) e o
plano visual não variava. Causa confirmada em `backend/app/modeling/planner.py`:
`create_heuristic_plan` usava `_default_steps()` fixo para Fusion quando o planner
LLM estava indisponível ou falhava.

Correção aplicada na branch `codex/3d-chat-title-required` (e isolada no
PR companheiro `feat/planner-llm-wip`, PR #27):

- fallback Fusion agora deriva um perfil simples do prompt dentro da allowlist;
- pedidos retangulares/base/chapa/placa usam `fusion.add_rectangle` com dimensões
  extraídas de sequências tipo `80x40x12 mm`;
- pedidos circulares/cilíndricos/disco/pino/eixo/tubo usam `fusion.add_circle`
  e extrusão com `diâmetro`/`altura` quando informados;
- o sketch do fallback passou a enviar `plane_ref="xy"`, alinhado ao executor
  determinístico do Fusion MCP;
- `_normalize_prompt` faz NFKD + strip de diacríticos para unificar matching
  de "paramétrico"/"parametrico", "tolerância"/"tolerancia" etc.

### PR #27 review — dedup de hints após normalização

Reviewer apontou inflate de score em `choose_software`: como
`_normalize_prompt` colapsa acentos, manter ambas as formas ("paramétrico"
e "parametrico") em `FUSION_HINTS` fazia a mesma palavra do prompt contar
duas vezes. Correção aplicada (commit do PR #27):

- Removidas as variantes não-acentuadas redundantes de `FUSION_HINTS`
  (`parametrico`, `tolerancia`, `extrusao`, `peca`) e `BLENDER_HINTS`
  (`organico`). Mantida só a forma canônica com acento; o
  `_normalize_prompt(hint)` no scoring continua fazendo o trabalho.
- Adicionada asserção defensiva `_assert_hints_dedup_after_normalize`
  que roda no import e impede regressão futura silenciosa.
- Testes novos em `test_planner_llm.py`:
  - `test_choose_software_does_not_double_count_normalized_hints`
  - `test_hint_sets_have_no_normalized_collisions`
  - `test_blender_score_with_organic_prompt_is_correct`

Validação local:

- `backend\.venv\Scripts\python.exe -m ruff format --check backend\app\modeling\planner.py backend\tests\test_planner_llm.py` → limpo.
- `backend\.venv\Scripts\python.exe -m ruff check backend\app\modeling\planner.py backend\tests\test_planner_llm.py` → limpo.
- `backend\.venv\Scripts\python.exe -m pytest backend\tests\test_planner_llm.py backend\tests\test_modeling_routes.py backend\tests\test_tool_registry.py -q` → **51 verdes** antes do fix do PR #27, **18 verdes** isolando só test_planner_llm.py após o fix (inclui 3 novos casos do dedup).

Limitação: `pnpm --filter @truths-forge/docs build` foi tentado após a atualização
da doc, mas falhou neste ambiente com `fetch failed`; validação completa da doc
build e smoke manual com Fusion conectado seguem pendentes na Onda 6.

## Onda 7 — Observabilidade do módulo 3D + caça aos schema drifts do adapter Fusion

**Sessão:** 18–19/05/2026, Claude Code. **Branch:** `feat/modeling-3d-observability` (mergeada na `codex/3d-chat-title-required` localmente, sem push). **Plano completo:** `specs/005-modeling-3d-fusion/observability-plan.md` (este repo) — descreve a arquitetura de observabilidade que foi implementada (contracts, tracer, endpoints, frontend, containerização, gaps fora de escopo). Cópia local original em `C:\Users\Jonatan\.claude\plans\para-que-seja-mais-immutable-puffin.md`.

### Contexto que originou a Onda

Bug recorrente "uma bola virou retângulo": qualquer prompt 3D produzia o mesmo paralelepípedo no Fusion. Causa real só descoberta após horas: modelo default no Postgres era `test/audit-cost-*` (lixo de testes não isolados); planner LLM falhava silenciosamente; executor mascarava falhas internas; o LLM gerava planos com schema drifts contra o adapter Fusion.

### O que foi entregue

**1. Módulo de observabilidade estruturada** (fundação)

| Arquivo | Conteúdo |
|---|---|
| `backend/app/core/contracts.py` | `ModelingTraceEvent`, `ModelingTraceSource`, `ModelingTraceLevel`, `trace_id` opcional em `AuditEvent`, caps de payload/buffer |
| `backend/app/core/config.py` | `TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED` (default `true`), `TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE` (default `false` em main, `true` no compose de dev temporariamente), retention reservas |
| `backend/app/llm_gateway/exceptions.py` | Hierarquia tipada: `LLMProviderError`, `LLMAuthError`, `LLMTimeoutError`, `LLMRateLimitError`, `LLMInvalidResponseError` + `classify_provider_exception` |
| `backend/app/modeling/observability.py` | `ModelingTracer` (contextvars + JsonFormatter + span context manager + batch buffer + payload truncate + `ingest_external_events` para drenar trace_events do addin), helpers `current_trace_id`/`current_plan_id`/`generate_trace_id`, singleton `get_tracer` |
| `backend/app/storage/postgres_store.py` | Tabela `modeling_trace_events` + 3 índices, `record_trace_events_bulk`, `list_trace_events` |
| `backend/app/storage/dev_store.py` | Equivalente JSON com ring buffer cap `MODELING_TRACE_DEVSTORE_MAX_EVENTS` |

**2. Instrumentação ponta-a-ponta**

- `planner_service.py`: `planner.model_resolved`, `planner.model_unavailable` (com candidatos rejeitados), `planner.llm_request` span, classificação tipada de exceções, `planner.fallback_used` (level=error), `logger.warning` promovido a `logger.error(exc_info=True)`
- `executor.py`: `_unwrap_inner_fusion_result` desempacota inner `ok:false` do adapter HTTP, `executor.step_started/ok/error/blocked/skipped` por step
- `chat_orchestrator.py`: `start_trace` em propose/approve, audit events com `trace_id`, flush em pontos chave
- `mcp_client.py`: propaga `_trace_id` no envelope JSON-RPC, drena `trace_events: []` da resposta via `ingest_external_events`
- `apps/fusion-addin/TruthsForge.py`: aceita `_trace_id` no `_meta`, retorna `trace_events: []` com `fusion.tool_completed`/`error`
- `chat.py`: `start_trace` no boundary da rota (porque a rota chama `modeling_service` direto, sem passar pelo orchestrator), flush após `to_thread`

**3. Endpoints REST + SSE enrichment**

- `GET /api/3d/plans/{id}/trace` — lista eventos do plano (filtros `?level=` `?source=`)
- `GET /api/3d/traces/{trace_id}` — lista eventos por trace_id direto
- `POST /api/3d/traces/events` — aceita eventos UI do frontend (rate-limit 60/min por IP, source forçado pra `ui`)
- `GET /api/3d/plans/{id}/diagnostics` — bundle consolidado (plan + tool_calls + trace + printability)
- SSE `modeling_plan` enriquecido com `trace_id`, `planner_source`, `fallback_reason` no payload

**4. Frontend**

- Hook `useModeling3dTrace(planId, traceId)` + `useRecordClientTrace` em `apps/web/src/features/modeling-3d/hooks/`
- API client: `planTrace`, `trace`, `recordClientTraceEvent`
- `ModelingDiagnosticsModal.tsx`: nova seção **Trace** com timeline cronológica, filtros por nível, payloads colapsáveis, trace_id copiável
- `ModelingPlanCard.tsx`: badge vermelho **PLANNER: FALLBACK** com tooltip mostrando `fallback_reason`

**5. Containerização (opt-in)**

- `infra/docker-compose.dev.yml`: serviço `dozzle` no profile `observability` (UI de logs em http://127.0.0.1:8082), flags expostas como env vars
- `scripts/smoke-modeling-trace.ps1`: smoke test ponta-a-ponta (POST evento UI → GET trace → query Postgres → check logs)
- `docs/local-dev.md`: seção nova de observabilidade

**6. 13 fixes-by-trace no adapter Fusion** (cada um descoberto via trace, não leitura de código)

| # | Fix | Bug que pegou |
|---|---|---|
| 0 | Executor detecta inner `ok:false` do adapter HTTP | "Tudo verde, Fusion vazio" — 11/16 steps mascarados |
| 1 / 1.1 / 1.2 | `set_parameter` aceita `parameters`/`parameters_mm`/`params`/bulk implícito | Schema drift do LLM |
| 2 / 8 | `create_sketch` honra `sketch_name`/`plane`, fallback gracioso pra plano desconhecido | Cascata `sketch_not_found` |
| 4 | ARGUMENTS via `json.loads` em runtime no script template | `NameError: name 'true'` |
| 5 | Guard de geometria vazia em export_stl/3mf | `InternalValidationError` opaco da SDK |
| 6 / 9 | `add_rectangle` aceita `corner1_mm`/`corner2_mm`, `size_mm`, modo grade `cols+rows+cell_size_mm` | Schema drift |
| 7 | Flush do tracer no fim de `execute_plan` + chat.py após `to_thread` | Modal de diagnóstico vazio quando trace tinha < `batch_size=25` events |
| 10 | `_eval_param` resolve string como `userParameter` lookup ou eval sandboxed | LLM passou expressões paramétricas (`sticker_width_mm + pocket_clearance_total_mm`) |
| (regressão auto-introduzida) | Chaves `{}` literais em comentário do f-string template | Crash em runtime; pego pela própria observabilidade |

**Teste regressão**: `backend/tests/test_modeling_observability.py` — 29 verdes. Inclui `test_fusion_script_template_compiles_for_every_tool` que `ast.parse` o script gerado para cada tool com sample args (previne classe de bug do `{}` literal).

### Estado dos dados no Postgres (configuração inicial necessária)

A sessão limpou via SQL o estado contaminado do Postgres local (foi causa raiz do bug original):

```sql
-- 27 modelos test/* deletados, openai/default-chat virou default
DELETE FROM model_configs WHERE payload->>'id' LIKE 'test/%';
UPDATE model_configs SET payload = jsonb_set(payload, '{default}', 'true'::jsonb)
  WHERE payload->>'id' = 'openai/default-chat';
UPDATE model_configs SET payload = jsonb_set(payload, '{max_output_tokens}', '8192'::jsonb)
  WHERE payload->>'id' = 'openai/default-chat';
```

`provider_model_id` deve estar `gpt-5-mini` ou superior (`gpt-4o` aceito). Sem `provider_model_id` ou com modelo fake, planner cai em fallback heurístico silenciosamente.

### Gaps conhecidos (NÃO TRABALHADOS, candidatos para próxima sessão)

1. **`fusion.create_sketch` em face de body existente** — LLM tenta `plane: "InnerFace_Left"` etc. Hoje cai em XY com warning visível, mas semanticamente errado. Solução real exige face references via Fusion SDK.
2. **Tracking de nomes de sketch entre steps** — O LLM referencia sketches por nome que **ele esperava ter criado** (ex: `lid_outline_sketch`, `box_outline_sketch`, `pocket_rectangles_sketch`), mas o passo `fusion.create_sketch` correspondente nem sempre passa `sketch_name`. Quando o nome falta, o adapter usa default `TF_Sketch (N)` (sequencial). O extrude subsequente busca pelo nome que o LLM "tinha em mente" e falha com `fusion.no_profile` (sketch existe na cena mas com nome diferente). Gap diferente dos outros 13 fixes — não é schema drift de campo, é **drift de identidade**. Soluções possíveis: (a) injetar o `sketch_name` que o LLM passou DEPOIS no `create_sketch` ANTERIOR (lookahead no executor sobre o plano completo); (b) tornar `_find_sketch` heurístico (fuzzy match por substring/Levenshtein); (c) instruir melhor o LLM no system prompt para sempre setar `sketch_name` consistente. Pegado no trace `mt_019e3e77e4ed_a7321f589d29e7a2` da Onda 7, sequence 25 (`fusion.extrude_profile` profile=`lid_outline_sketch` → `fusion.no_profile`).
3. **2 testes pré-existentes falhando em `test_fusion_bridge.py`** — não relacionados a esta sessão, confirmados nos commits anteriores. `_extract_mcp_content_json` não propaga `error_code` do payload interno.
4. **Testes escrevendo no Postgres de dev** — chip "Isolar testes do Postgres de dev" foi spawned como tarefa adjacente (não atacada). Causa raiz da contaminação inicial dos 27 modelos `test/*` que originaram tudo.
5. **Frontend modal não recebe `traceId` via App.tsx** — hook funciona via fallback `planTrace(planId)`. Wire explícito do `trace_id` do SSE seria mais robusto.
6. **`TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE` está hardcoded em `true`** no compose dev — temporário para debug. Reverter para `${...:-false}` quando observability não for mais necessária.
7. **Frontend não rebuildado** — mudanças em `useModeling3dTrace.ts`, `api/index.ts`, `ModelingDiagnosticsModal.tsx`, `ModelingPlanCard.tsx`, `types/api.ts` foram aplicadas mas o serviço `web` está parado. Subir com `docker compose ... up -d web` antes de testar UI.

### Validação ao fim da sessão

- `pytest backend/tests/ -q` → **273 verdes + 2 pré-existentes falhando** (test_fusion_bridge, escopo separado)
- 29 testes novos em `test_modeling_observability.py`
- Smoke manual: `pwsh scripts/smoke-modeling-trace.ps1` → PASS em todos os passos
- Caso "modele um prisma" (50×30×100 mm): primeira execução end-to-end bem-sucedida (8/9 steps OK, body real criado no Fusion, exports OK)
- Caso "porta-figurinhas panini WC 2026": LLM aprendeu paramétrica, expôs schema drift de expressões (resolvido em Fix #10); execução posterior depende dos gaps 1 e 2 acima

### Como continuar

1. **Continuar a caça aos schema drifts do adapter Fusion** (gaps 1 e 2 acima) — mesma metodologia: rodar prompt complexo, ler trace, fixar adapter, repetir.
2. **Consolidar PR** desta branch (16 commits, ~3.5K linhas) — eventualmente push e abrir PR contra `main`.
3. **Spawn de tarefas adjacentes**: isolar testes do Postgres, fixar 2 testes de `test_fusion_bridge` pré-existentes.

### Branch e commits

- Branch: `feat/modeling-3d-observability` (worktree em `D:\projects\truths_forge_ai\.claude\worktrees\admiring-mendeleev-689279`)
- 16 commits semânticos: `8134751` (foundation) até `9473d2b` (Fix #10)
- Main repo (`D:\projects\truths_forge_ai\`) está com merge dessa branch + commit `60f5119` (WIP pré-existente do planner)
- Nenhum push remoto feito ainda

---

## O que a Onda 5 entregou

**Arquivos novos:**

- `apps/web/src/features/chat/components/ChatTitleRequiredDialog.tsx`
- `apps/web/src/features/chat/components/ChatTitleRequiredDialog.test.tsx`
- `apps/web/src/features/chat/hooks/useChatTitleGate.ts`

**Arquivos alterados:**

- `apps/web/src/features/chat/chat-domain.ts` centraliza `DEFAULT_CHAT_TITLES`,
  normalização de título e `chatSessionNeedsTitle`.
- `apps/web/src/App.tsx` abre o modal antes de `streamChat`, atualiza o título
  local da sessão, envia `title` no payload e restaura o draft quando o backend
  devolve `chat_title_required`.
- `apps/web/src/lib/api.ts` transforma HTTP 422 JSON em `onError` com
  `reason: "chat_title_required"` e lança `ChatStreamHttpError` para o caller.
- `backend/app/api/routes/chat.py` persiste `payload.title` em rascunhos já
  criados como `Novo chat` antes do primeiro envio.
- `infra/docker-compose.dev.yml` e `infra/.env.example` ligam
  `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true`.

**Contrato de UI:**

- `ChatTitleRequiredDialog` usa `role="dialog"`, `aria-modal`, autofocus no
  input, ESC para cancelar e Enter para confirmar.
- Confirmar fica bloqueado para vazio/whitespace/`Novo chat`/`New chat` e
  durante `busy`.
- O modal não executa envio por texto livre; ele apenas resolve o título para
  o fluxo do `App.tsx`.

**Pendências imediatas:**

- Rodar o smoke manual da task 5.6.
- Registrar resultados de validação final nesta seção antes de PR/merge.

## O que a Onda 4 entregou (detalhe técnico)

### Sub-etapa 4.1+4.2 — Cards no chat (commit `cf42144`)

**Arquivos novos:**

- `apps/web/src/features/modeling-3d/components/ModelingPlanCard.tsx`
- `apps/web/src/features/modeling-3d/components/ModelingPlanCard.test.tsx` (12 testes)
- `apps/web/src/features/modeling-3d/components/ModelingEditCard.tsx`
- `apps/web/src/features/modeling-3d/components/ModelingEditCard.test.tsx` (4 testes)
- `apps/web/src/features/modeling-3d/hooks/useModelingPlanActions.ts`

**`ModelingPlanCard` — contrato:**

```ts
interface ModelingPlanCardProps {
  plan: ModelingPlan;
  onApprove?: (reason?: string) => Promise<void> | void;
  onReject?: (reason: string) => Promise<void> | void;
  onRetry?: () => Promise<void> | void; // só em status="failed"
  onRevise?: () => Promise<void> | void; // só em status="failed"
  isBusy?: boolean;
}
```

- Renderiza prosa (rationale → prompt fallback), badges (software/status
  localizado em pt-BR/planner_source/kind=edit), banner amarelo quando
  há etapa `risk_level="high"` ou `approval_required=true`, lista de
  etapas com pill colorida de risk_level.
- Botões "Aprovar"/"Rejeitar" aparecem **apenas em**
  `status ∈ {"waiting_approval", "draft"}`.
- Rejeição abre form expansível com motivo obrigatório (`min_length` no
  client, button "Confirmar rejeição" só habilita com texto).
- Estados visuais: `running` (spinner amarelo), `completed` (mensagem
  verde), `failed` (alerta vermelho + botões "Tentar novamente" / "Revisar
  plano"), `rejected` (nota neutra).
- Texto livre **não** dispara nada — reforçado em copy no rodapé.

**`ModelingEditCard` — contrato:**

```ts
interface ModelingEditCardProps {
  plan: ModelingPlan; // sempre kind="edit"
}
```

- Card compacto, sem botões. Renderiza header com ícone+badge "edição",
  resumo (rationale → prompt → fallback "Edição executada no modelo 3D"),
  contagem de etapas executadas e falhas.
- Quando um edit plan está em `waiting_approval` (high-risk reaberto),
  o caller renderiza `ModelingPlanCard` em vez deste.

**`useModelingPlanActions` — contrato:**

```ts
{
  busy: boolean;
  error: string | null;
  lastPlan: ModelingPlan | null;
  lastExecution: ModelingExecutionResult | null;
  approve(planId): Promise<ModelingExecutionResult | null>;
  reject(planId, reason): Promise<ModelingPlan | null>;
  retry(planId): Promise<ModelingExecutionResult | null>;
  revise(planId, reason?): Promise<ModelingPlan | null>;
  reset(): void;
}
```

- `approve` chama `modeling3dApi.approvePlan(id)` seguido de
  `modeling3dApi.executePlan(id)` em sequência. Mantém os dois retornos
  em `lastPlan` / `lastExecution`.
- `reject` e `revise` usam `modeling3dApi.rejectPlan(id, reason)`.
- Todas capturam exceção em `error` sem propagar.

### Sub-etapa 4 integration — wire no App.tsx (commit `ffb6f73`)

**Arquivo modificado:** `apps/web/src/App.tsx`

**`applyPlanToSession(plan, nextStage)`** — helper local que substitui
`metadata.modeling_plan` na mensagem correspondente da sessão e ajusta
`session.modeling_stage` / `session.modeling_plan_id`. Rejeição limpa
`modeling_plan_id` e volta para `discovery`.

**Handlers wire-up:**

- `handleApproveModelingPlan(planId)` → `hook.approve` → `applyPlanToSession(result.plan, "editing")`
- `handleRejectModelingPlan(planId, reason)` → `hook.reject` → `applyPlanToSession(rejected, "discovery")`
- `handleRetryModelingPlan(planId)` → `hook.retry` → `applyPlanToSession(execution.plan, "editing")`
- `handleReviseModelingPlan(planId)` → `hook.revise` → `applyPlanToSession(rejected, "discovery")`

**Prop `modelingPlanActions`** passada ao `MessageBubble` apenas quando
`activeSessionIsModeling3D=true`. Chats normais recebem `undefined` e
o card fica não-interativo (botões somem).

### Sub-etapa 4.3 — Auto-analyze de anexos (commit `92218dd`)

**Onde:** `apps/web/src/App.tsx`, dentro do `try{}` de envio do chat,
imediatamente após o stream completar e antes do `catch`.

**Trigger:** `modeling3dPayload.enabled && uploadedFileIds.length > 0`.

**Comportamento:**

1. `Promise.all` paralelo sobre `uploadedFileIds`.
2. Para cada, `modeling3dApi.analyzeAttachment(chatId, fileId)`.
3. Cada sucesso vira `ChatMessage` assistant local com:
   - `metadata.response_mode = "modeling_3d_attachment_analysis"`
   - `metadata.attachment_analysis = AttachmentAnalysis` completo
   - `content = analysis.context_text` (pronto para LLM ler)
4. Falhas viram nota assistant com `response_mode =
"modeling_3d_attachment_analysis_error"` e texto humano legível —
   nunca quebram o chat.
5. `void Promise.all` não bloqueia o reset dos `attached*` states.

### Sub-etapa 4 — `app-chat.tsx` polishing

- Removeu o `ModelingPlanCard` legacy interno (~45 linhas).
- `MessageBubble` aceita `modelingPlanActions?: ModelingPlanCardActions`.
- Lógica de decisão Plan vs Edit:
  ```tsx
  metadata.modeling_plan.kind === "edit" &&
    metadata.modeling_plan.status !== "waiting_approval"
    ? <ModelingEditCard />
    : <ModelingPlanCard ... callbacks />
  ```
- Teste `app-chat.test.tsx` atualizado: assertions sem `mode` badge,
  status localizado, sem copy "painel 3D" removido.

### Sub-etapa 4 — `modeling3dApi` ganhou `approvePlan` / `rejectPlan` / `executePlan`

**Arquivo:** `apps/web/src/features/modeling-3d/api/index.ts`

```ts
approvePlan(planId, payload = { decision: "approve" }): Promise<ModelingPlan>
rejectPlan(planId, reason: string): Promise<ModelingPlan>
executePlan(planId): Promise<ModelingExecutionResult>
```

Todos usam `apiRequest` com `POST` e mapeiam direto para
`POST /api/3d/plans/{id}/approve` e `POST /api/3d/plans/{id}/execute`
(rotas backend preservadas na Onda 2.11 para uso interno).

---

## Decisões consolidadas com o dono do produto

### Módulo 3D (ADR-013)

- **Fluxo único**: descoberta → plano apresentado no chat → aprovação
  por botões inline → execução → edições com mini-planos. Os três modos
  legados (`plan_only`/`approval_required`/`safe_auto`) são removidos.
- **Aprovação só via botões inline no card**, não no painel. Resposta
  textual livre não aciona execução.
- **Aprovação global do plano cobre todas as etapas**, incluindo
  high-risk (`apply_boolean`, `repair_non_manifold`, `restore_snapshot`,
  `run_script`). Sem reaprovação step-a-step depois.
- **High-risk em edição posterior** abre nova aprovação inline; edição
  comum autoexecuta como mini-plano.
- **Flag `is_modeling_3d` por chat**, persistida e imutável após criação.
  Toggle global vira `nextChatIs3D` (apenas marca a intenção do próximo
  chat).
- **Ativar 3D em chat com histórico**: modal pergunta antes; confirma
  cria novo chat 3D vazio sem copiar mensagens.
- **Anexos com análise profunda**: imagens via vision (gateway LLM,
  stub hoje — ver gap abaixo) e arquivos 3D (`STL`/`OBJ`/`STEP`/`3MF`/
  `BLEND`) via Blender headless — bounding box, mesh stats, simetria,
  features identificáveis, sugestões.
- **Painel 3D removido**. Config de adapters vai para Configurações
  gerais; diagnóstico vira modal acessível pelo cabeçalho do chat 3D.
- **Trigger discovery → planning**: decisão livre do LLM. A tool
  `3d.propose_plan` é o único gatilho formal.

### Título obrigatório (ADR-014, escopo não-3D acoplado)

- **Front e back validam**. Front bloqueia o input (Onda 5 — pendente),
  back retorna 422 quando `chat.title` vazio/default (Onda 2.9, atrás
  da feature flag `TRUTHS_FORGE_REQUIRE_CHAT_TITLE`).
- **Migração backfill** aplica `"Sem título - YYYY-MM-DD"` (derivado
  de `created_at`) a chats existentes sem título (Onda 2.2).
- **Auto-titulação OpenAI removida** completamente (serviço +
  endpoint + provider method) — Onda 2.10.

### Decisões herdadas (v1, ADR-012)

- Blender real e Fusion bridge são obrigatórios para a trilha 3D.
- Fusion tem contrato próprio dentro do bounded context.
- Fusion MCP Server local (porta padrão `27182`) é o caminho preferido;
  bridge legado em `apps/fusion-addin/` permanece como fallback.

---

## Gaps e pendências (LEIA ANTES DE MEXER)

Estes itens **não foram entregues** durante as Ondas 0–4 — não por
descuido, mas por escopo ou dependência. Estão listados aqui para que
outra IA não pense que estão prontos ou que precisam ser refeitos.

### Gap 1 — SSE handler dedicado para execução

**Onde está agora:** `applyPlanToSession` em `App.tsx` atualiza estado
otimisticamente a partir da resposta direta de
`approvePlan + executePlan`.

**O que falta:** backend não emite eventos
`modeling_execution_started`, `modeling_execution_progress`,
`modeling_execution_step_completed`, `modeling_execution_completed`,
`modeling_execution_failed` no stream SSE. Quando esses forem emitidos,
substituir o update otimista por handlers no `streamChat.onEvent` (como
o `"modeling_plan"` já existente em `App.tsx:1247-1269`).

**Para quem implementar:** começar em `backend/app/api/routes/chat.py`
no bloco do `modeling_3d.enabled`, depois adicionar dispatcher
correspondente em `apps/web/src/App.tsx`. Carryover para **Onda 6** ou
sub-fase dedicada entre 5 e 6.

### Gap 2 — Wire do `ModelingChatOrchestrator` ao stream handler

**Onde está agora:** `POST /api/chat/stream` ainda chama
`ModelingService.create_plan_async` inline (compat v1). O
`ModelingChatOrchestrator` existe em
`backend/app/modeling/chat_orchestrator.py` com 5 métodos públicos
(`ask_clarification`, `propose_plan`, `propose_edit_plan`,
`approve_plan`, `reject_plan`, etc.) e está totalmente testado, mas
**não é chamado pelo stream handler ainda**.

**O que falta:** o stream handler precisa:

1. Detectar `chat.is_modeling_3d` no início.
2. Decidir a fase atual via `chat.modeling_stage`.
3. Chamar `orchestrator.propose_plan(chat, payload)` em `discovery`
   (em vez de `service.create_plan_async`).
4. Em `editing`, chamar `orchestrator.propose_edit_plan`.
5. Emitir SSE event `modeling_plan` igual ao fluxo atual.
6. Plumar o `EditPlanOutcome.requires_approval` para o frontend saber
   se pode auto-executar ou exibir reaprovação.

**Para quem implementar:** Carryover para **Onda 6** ou PR dedicado
entre 5 e 6. Pode ser feito junto com o Gap 1 (SSE de execução)
porque os dois mexem na mesma região do código.

### Gap 3 — Vision real para imagens

**Onde está agora:** `ModelingAttachmentAnalyzer._call_vision` retorna
`None` como stub. Frontend exibe summary placeholder + sugestões.

**O que falta:** quando o `LLMGateway` aceitar conteúdo multimodal
(`list[dict[str, Any]]` em vez de `list[dict[str, str]]`), implementar
chamada vision real com a imagem como data URL base64. Local exato:
`backend/app/modeling/attachment_analyzer.py:_call_vision`.

**Para quem implementar:** sub-fase no contexto de uma melhoria do
gateway LLM; não bloqueia nenhuma das ondas restantes.

### Gap 4 — Análise profunda de CAD STEP

**Onde está agora:** `ModelingAttachmentAnalyzer._analyze_cad_metadata`
retorna metadata-only (size_bytes, extension).

**O que falta:** quando o Fusion adapter expor análise headless de
STEP (corpos, features, printability), trocar o stub por chamada real.
Local: `backend/app/modeling/attachment_analyzer.py:_analyze_cad_metadata`.

**Para quem implementar:** sub-fase do bounded context Fusion;
backlog Onda 6+.

### Gap 5 — Telemetria do trigger `propose_plan`

**Decisão:** instrumentar mas não bloquear (handoff Onda 2). Telemetria
deve auditar quando o LLM chama `propose_plan` com descoberta
insuficiente (poucas mensagens em discovery).

**Onde está agora:** não implementado.

**Para quem implementar:** adicionar audit event
`modeling.chat.proposed_plan_without_clarification` no
`ModelingChatOrchestrator.propose_plan` quando
`chat.message_count_in_stage == 1` ou similar. Pode ser feito junto
com o Gap 2 (wire do orchestrator).

### Gap 6 — Modal de título obrigatório no frontend (resolvido na Onda 5)

**Decisão:** ADR-014. Cliente React precisa exigir título antes da
primeira mensagem.

**Onde está agora:** backend já valida com `HTTP 422` quando a feature
flag `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true`. Flag está em
`backend/app/core/config.py`, default `false` para não quebrar o
frontend legado.

**Status:** concluído localmente em `codex/3d-chat-title-required`; falta
PR/merge.

---

## Guia histórico da Onda 5

Este plano fica como registro do que foi implementado. A maior parte do
trabalho da Onda 5 foi frontend; o backend recebeu apenas o ajuste para
persistir o título em rascunhos já criados.

### Contratos backend que o frontend precisa honrar (já implementados)

1. **Campo opcional `title` em `ChatStreamRequest`**:

   ```python
   # backend/app/core/contracts.py
   class ChatStreamRequest(BaseModel):
       message: str
       session_id: str | None = None
       title: str | None = None   # ← novo (Onda 2.9)
       ...
   ```

   O frontend deve incluir esse campo em todo `POST /api/chat/stream`.

2. **422 quando flag ativa**:

   ```python
   # backend/app/api/routes/chat.py
   def _enforce_required_chat_title(payload: ChatStreamRequest) -> None:
       normalized = (payload.title or "").strip().lower()
       if not normalized or normalized in DEFAULT_CHAT_TITLES:
           raise HTTPException(
               status_code=422,
               detail={
                   "error": "chat_title_required",
                   "message": "Esse chat precisa de um título antes...",
               },
           )
   ```

   `DEFAULT_CHAT_TITLES = {"novo chat", "new chat"}` — qualquer um
   desses + vazio → 422.

3. **Feature flag controla**:
   ```python
   # backend/app/core/config.py
   require_chat_title: bool = Field(
       default_factory=lambda: (
           os.getenv("TRUTHS_FORGE_REQUIRE_CHAT_TITLE", "false").lower()
           in {"1", "true", "yes", "on"}
       )
   )
   ```
   Na Onda 5, `infra/.env.example` e `docker-compose.dev.yml` foram
   atualizados para `true`.

### Plano de execução da Onda 5

#### 5.1 — Componente `ChatTitleRequiredDialog`

**Onde:** `apps/web/src/features/chat/components/ChatTitleRequiredDialog.tsx`
(criar pasta `components/` se não existir).

**Props:**

```ts
interface ChatTitleRequiredDialogProps {
  open: boolean;
  initialTitle?: string;
  onConfirm: (title: string) => Promise<void> | void;
  onCancel?: () => void;
  busy?: boolean;
}
```

**Comportamento:**

- Modal acessível (`role="dialog"`, `aria-modal="true"`).
- Input texto com `min_length=1`, autofocus.
- Botão "Confirmar" desabilita enquanto título vazio/whitespace ou
  está em `DEFAULT_CHAT_TITLES` (`"Novo chat"`, `"New chat"`).
- ESC cancela; Enter confirma se válido.
- Copy: "Dê um título para esse chat antes de começar: isso ajuda
  você a encontrá-lo depois e economiza chamadas ao modelo."

**Test file:** `ChatTitleRequiredDialog.test.tsx` cobrindo:

- Modal abre/fecha com prop `open`
- Confirma desabilitado com título vazio/default
- ESC fecha
- Enter confirma quando válido
- `busy=true` desabilita confirm

#### 5.2 — Hook `useChatTitleGate`

**Onde:** `apps/web/src/features/chat/hooks/useChatTitleGate.ts`.

**API sugerida:**

```ts
function useChatTitleGate(activeSession: ChatSession | null) {
  // Retorna { needsTitle: boolean, openTitleDialog, ... }
  // needsTitle === true quando:
  //   - sessão é nova (sem messages.length) OU
  //   - title está em DEFAULT_CHAT_TITLES OU vazio/whitespace
}
```

#### 5.3 — Wire no `App.tsx`

1. Importar `useChatTitleGate` e `ChatTitleRequiredDialog`.
2. Antes de chamar `streamChat`, checar `gate.needsTitle`:
   - Se sim, abrir modal e aguardar `onConfirm`.
   - Depois de confirmar, atualizar `session.title` localmente e
     incluir `title` no payload do `streamChat`.
3. Em `onError` do `streamChat`, detectar
   `error.reason === "chat_title_required"` (ou detail.error) e abrir
   o mesmo modal.
4. No `ChatStreamRequest`, passar `title: activeSession?.title`.

#### 5.4 — Tratar 422 no `streamChat`

**Onde:** `apps/web/src/lib/api.ts`.

Precisa que o `onError` callback do `streamChat` seja chamado com algo
do tipo:

```ts
onError({
  reason: "chat_title_required",
  message: detail.message,
  status: 422,
});
```

#### 5.5 — Flag flip + smoke test

Após 5.1–5.4 mergeado:

1. Adicionar `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true` em
   `infra/docker-compose.dev.yml` e `infra/.env.example`.
2. Rodar manualmente: criar chat novo, tentar enviar mensagem sem
   título → modal abre → confirma → mensagem sobe sem 422.
3. Validar que chats antigos (com título já populado pela migração 002)
   continuam funcionando sem modal.

#### 5.6 — Atualizar docs

- `docs/application-map.md` — descrever o fluxo de criação de chat com
  título obrigatório.
- `README.md` — se mencionar auto-titulação, remover.
- `specs/005-modeling-3d-fusion/tasks.md` — marcar 5.1–5.6 concluídos.
- `handoff.md` (este arquivo) — mover Onda 5 para mergeado e listar
  novos commits.

### Estimativa

- 5.1–5.4: ~400 linhas TSX + testes
- 5.5: 3 linhas em env files + smoke test manual
- 5.6: ~50 linhas docs

Total: pequeno-médio. Compatível com um único PR.

---

## Mapa de contratos de API (frontend ↔ backend)

| Endpoint                                                | Quem chama                                 | Estado                                                                               |
| ------------------------------------------------------- | ------------------------------------------ | ------------------------------------------------------------------------------------ |
| `POST /api/chat/stream`                                 | `streamChat` em `lib/api.ts`               | Aceita `title` opcional (Onda 2.9). Retorna SSE com `modeling_plan` event quando 3D. |
| `POST /api/chat/sessions/{chat_id}/attachments/analyze` | `modeling3dApi.analyzeAttachment`          | Onda 2.7. Retorna `ChatAttachmentAnalyzeResponse`.                                   |
| `GET /api/3d/capabilities`                              | `modeling3dApi.capabilities`               | Diagnóstico, mantido.                                                                |
| `GET /api/3d/plans`                                     | `modeling3dApi.plans`                      | Read-only para diagnóstico.                                                          |
| `POST /api/3d/plans/{id}/approve`                       | `modeling3dApi.approvePlan` / `rejectPlan` | Onda 4. Body `{decision, reason}`.                                                   |
| `POST /api/3d/plans/{id}/execute`                       | `modeling3dApi.executePlan`                | Onda 4. Sem body.                                                                    |
| ~~`POST /api/3d/plans`~~                                | —                                          | **Removido na Onda 2.11**.                                                           |
| ~~`POST /api/3d/steps/{id}/approve`~~                   | —                                          | **Removido na Onda 2.11**.                                                           |

## Mapa de state machine

```
created (title obrigatório quando flag on)
  → discovery
       ↓
   planning ← (rejeição) ←┐
       ↓                  │
   approved               │
       ↓                  │
   executing              │
       ↓                  │
   editing ────────────── ┘ (high-risk em edição)
       │
   completed (archive)
```

Estados representados em `ChatSession.modeling_stage` (enum `ChatModelingStage`).
Transitions implementadas em `backend/app/modeling/chat_state.py`
(funções puras, 18 testes).

## Mapa de eventos de auditoria

Eventos emitidos pelo `ModelingChatOrchestrator` (todos com
`metadata.chat_id`):

- `modeling.chat.discovery_started`
- `modeling.chat.clarification_asked`
- `modeling.chat.plan_proposed`
- `modeling.chat.plan_approved`
- `modeling.chat.plan_rejected`
- `modeling.chat.execution_started`
- `modeling.chat.execution_completed` (ou `_failed`)
- `modeling.chat.edit_auto_executed`
- `modeling.chat.edit_high_risk_requested`
- `modeling.chat.edit_high_risk_approved` / `_rejected`
- `modeling.chat.archived`

Eventos legados (preservados): `modeling.plan_created`,
`modeling.plan_approved`, `modeling.plan_rejected`,
`modeling.plan_executed`, `modeling.snapshot_created`,
`modeling.snapshot_restored`, `modeling.printability_validated`.

---

## Pontos abertos (não-bloqueantes para 5/6)

- **System prompt de descoberta**: 5 tools dedicadas estão expostas via
  `backend/app/modeling/prompts/discovery_system.md`. Falta adicionar
  exemplos few-shot para o trigger `propose_plan`. Backlog Onda 6+.
- **Limites de tamanho/timeout para análise 3D**: proposta inicial é
  50 MB / 15 s, ajustar conforme experimentos com Blender real.

---

## Referências

- Plano de execução original (host-side): `C:\Users\Jonatan\.claude\plans\gostaria-de-planejar-uma-lovely-ember.md`
- Spec viva: `specs/005-modeling-3d-fusion/spec.md`
- Plano técnico: `specs/005-modeling-3d-fusion/plan.md`
- Tasks: `specs/005-modeling-3d-fusion/tasks.md`
- ADRs: `docs/decisions.md` (ADR-012, ADR-013, ADR-014)
- Documentação operacional: `docs/3d-mcp-modeling.md`
- Mapa da aplicação: `docs/application-map.md`
- PRs: #19 (Onda 0+1), #20 (Onda 2), #21+#22+#24 (Onda 3 + fixes),
  #25 (Onda 4)
