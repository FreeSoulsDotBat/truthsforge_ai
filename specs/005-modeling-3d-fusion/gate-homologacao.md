# Roteiro de homologação — gates pendentes (Fusion real)

> Receita de teste para o dono homologar **numa tacada** as fases mock-completas
> que aguardam validação no Fusion real. Ordem por risco: superfícies e sheet
> metal primeiro (tools novas, version-sensitive), depois params/loop.
>
> Comandos de debug detalhados em [`../../docs/3d-modeling-debug.md`](../../docs/3d-modeling-debug.md).
> Estado por fase em [`tasks.md`](./tasks.md).

## Pré-voo (uma vez só)

1. **Subir a stack:** `.\scripts\dev.ps1`
   - Se o Qdrant travar o backend:
     `docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml up -d --no-deps backend web`
2. **Ligar loop + observabilidade + frentes de capacidade** em `infra/.env`:
   ```dotenv
   TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED=true
   TRUTHS_FORGE_MODELING_AGENTIC_LOOP_ENABLED=true
   TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE=true
   TRUTHS_FORGE_MODELING_HIERARCHICAL_PLANNING_ENABLED=true     # F2 (decompõe→observa→replaneja)
   TRUTHS_FORGE_MODELING_LIVE_GEOMETRY_RECONCILIATION_ENABLED=true  # F5 (lê geometria ao vivo na edição)
   TRUTHS_FORGE_MODELING_VISUAL_VERIFICATION_ENABLED=true       # visão (percepção). O REPLAN destrutivo é opt-in à parte:
   # TRUTHS_FORGE_MODELING_VISUAL_AUTOCORRECT_ENABLED=true      # ↑ só p/ reproduzir o loop legado (recria corpos / pode duplicar). Default OFF = seguro.
   TRUTHS_FORGE_MODELING_SPATIAL_RESOLUTION_ENABLED=true        # F7 (posicionamento paramétrico declarativo) — só p/ o Gate F7
   TRUTHS_FORGE_MODELING_PROVENANCE_ENABLED=true                # F8 (proveniência: o que cada passo mudou) — Gate F8.D1
   TRUTHS_FORGE_MODELING_SELF_CRITIQUE_ENABLED=true             # F8 (auto-crítica: faltou/demais/errado/certo) — Gate F8.D1
   TRUTHS_FORGE_MODELING_RELATION_PLACEMENT_ENABLED=true        # F8 (relação genérica relate_bodies) — só p/ o Gate F8.R1
   TRUTHS_FORGE_MODELING_RELATIVE_ENFORCEMENT_ENABLED=true      # F9 (Gate B: recusa coordenada absoluta chutada) — Gate F9
   TRUTHS_FORGE_MODELING_ALIGN_MODES_ENABLED=true               # F9 (align center/coplanar/gap/edge/corner) — Gate F9
   TRUTHS_FORGE_MODELING_SEMANTIC_STATE_ENABLED=true            # F9 (roles/touches/body_label no <model-state>) — Gate F9
   # F6 (sanitizer determinístico) já vem ON por padrão; só desligue p/ depurar planner cru.
   ```
   > As 3 flags de capacidade (loop/hierárquico/reconciliação) só fazem efeito
   > porque estão repassadas no `environment:` do compose — ligar só no `.env`
   > sem isso NÃO chega ao container (bug já visto). NÃO precisa de
   > `MCP_TRANSPORT=mcp_http` (isso é o servidor standalone da Fase 1, adiada);
   > o Fusion real é alcançado pelo add-in (27182) + `FUSION_MCP_URL`.

   Reinicie: `docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml restart backend`
   Confirme: `docker exec truths-forge-backend printenv | Select-String 'MODELING_AGENTIC|MODELING_HIERARCHICAL|MODELING_LIVE_GEOMETRY|MODELING_PLAN_SANITIZER'`
3. **Fusion conectado:** add-in/MCP Server ligado (27182). No chat 3D → modal de
   Diagnóstico → *Adapters*: `fusion` = **`conectado` / `http`** (se vier `mock`,
   o backend não alcança o Fusion).
4. **Planner = IA:** card do plano deve mostrar **`PLANNER: IA`**. Se vier
   `FALLBACK`, recoroe o modelo default (ver §2 do debug doc).
5. **Logs ao vivo (2º terminal):**
   ```powershell
   docker logs -f truths-forge-backend |
     Select-String "executor.step_error|agent_loop|planner.fallback_used|fusion\."
   ```
6. **Curinga pra pegar qualquer plan_id** (a UI só dá o de criação):
   ```powershell
   Invoke-RestMethod "http://127.0.0.1:8000/api/3d/plans" | Select-Object -First 8 `
     id, status, kind, planner_source, @{n='steps';e={$_.steps.Count}} | Format-Table -Auto
   ```

## Como reportar cada gate

1. **plan_id** (criação pela UI; edição pelo curinga acima).
2. **Print** do Fusion (peça certa OU erro).
3. Se falhou, o **dump dos steps** (é o que permite fix-by-trace):
   ```powershell
   $p = Invoke-RestMethod "http://127.0.0.1:8000/api/3d/plans/<PLAN_ID>"
   $p.steps | ForEach-Object {
     "{0}. {1} [{2}]" -f $_.seq, $_.tool_name, $_.status
     "    in : " + ($_.input_json  | ConvertTo-Json -Compress -Depth 8)
     "    out: " + ($_.output_json | ConvertTo-Json -Compress -Depth 8)
   }
   ```
4. **O trace RICO por plan_id** (o que diz POR QUÊ o posicionamento saiu errado —
   qual face foi casada e ONDE ela está). É a forma preferida: um plan_id já mostra
   tudo, sem dump manual.
   ```powershell
   Invoke-RestMethod "http://127.0.0.1:8000/api/3d/plans/<PLAN_ID>/trace" |
     Where-Object event_type -match 'spatial_resolved|relation_resolved|provenance_recorded|verdict|visual' |
     ForEach-Object { $_.event_type; $_.payload | ConvertTo-Json -Compress -Depth 12 }
   ```
   No `spatial_resolved`/`relation_resolved`, o campo **`placement`** traz:
   `concrete` (args reais da junta: `face_token_one/two`, `joint_type`, `axis`),
   **`resolved_faces`** (cada token → `body`/`type`/`center_mm`/`normal` — onde a
   face REALMENTE está) e `bodies` (bboxes). Para relações, `derived` mostra o
   role medido (ex.: `target.role=open_boundary`). Com isso o mis-place se lê
   direto: "ancorou em `center_mm=[55,20,20]` (aro lateral) em vez do centro
   `[30,20,20]`".

---

## Gate 1 — Fase 5: Superfícies NURBS (carenagem) ⭐ maior risco

11 tools que **nunca rodaram no Fusion real** (`PatchFeatures`/`ThickenFeatures`/
`StitchFeatures` são version-sensitive). Maior chance de fix-by-trace.

**Prompt natural** (testa planner + tools):
```
Modele uma carenagem oca: uma casca curva fechada nas duas pontas, com
1,5 mm de parede. Use superfície NURBS e depois espesse em sólido.
```

**Prompt dirigido** (se o natural fizer tudo sólido / não usar superfície):
```
Crie uma superfície por sweep: perfil (spline em XZ pelos pontos
[0,0],[40,30],[80,45],[120,30],[160,0]) varrido ao longo de um caminho
(spline em XY pelos pontos [0,0],[80,50],[160,0]), com as_surface=true.
Depois feche as duas aberturas com create_surface_patch, costure tudo com
stitch_surfaces (expected_is_closed=true) e espesse 1,5 mm com thicken_surface.
```

**Observar no Fusion:**
1. O sweep nasce como **superfície** (não sólido)?
2. As tampas fecham (patches)?
3. O stitch junta tudo (e detecta que fechou volume)?
4. O thicken vira sólido de parede uniforme 1,5 mm?
5. Sem buracos não-intencionais?

**Teste isolado mais simples** (se a carenagem inteira for longe demais — prova
extrude as_surface + thicken sem depender de edge_ids dinâmicos):
```
Desenhe um arco aberto e extrude como superfície (as_surface=true) por
50 mm. Depois espesse essa superfície em 2 mm para virar sólido.
```

---

## Gate 2 — Fase 6: Sheet metal (chapa dobrada) ⛔ REMOVIDO — sheet metal congelado (DT-011)

> **NÃO é mais um passo de homologação.** As 5 tools deste gate
> (`convert_to_sheet_metal`/`flange_edge`/`bend_edge`/`unbend`/`rebend`) foram
> **REMOVIDAS** (commit `877ac23`) porque a API Python do Fusion não expõe sheet
> metal (DT-011; só `flangeFeatures` read-only). Rodar os prompts abaixo falha
> deterministicamente — o planner nem enxerga essas tools. Cabeçalho mantido só
> para histórico; **pule para o Gate 3**. (Forma de chapa p/ impressão = sólido
> comum; forma orgânica = superfície NURBS, Gate 1.)

**Prompt natural:**
```
Crie uma chapa de 100x60 mm com 2 mm de espessura, converta para sheet
metal e adicione uma flange de 25 mm dobrada a 90° em uma das bordas maiores.
```

**Prompt dirigido** (se não converter pra sheet metal):
```
Crie uma caixa 100x60x2 mm chamada Chapa. Converta para sheet metal com
convert_to_sheet_metal. Depois use flange_edge com edge_selector=top,
height_mm=25, angle_deg=90.
```

**Edição — flat pattern** (no mesmo chat, após a flange):
```
Achate essa peça (flat pattern / unbend).
```

**Observar:**
1. A chapa vira corpo **Sheet Metal** no browser do Fusion?
2. A flange nasce a 90° com 25 mm?
3. O unbend desdobra para plana?

---

## Gate 3 — Fase 4: Placa paramétrica + 4 furos + stable_id

Valida o recompute paramétrico (fecha DT-002) e o `stable_id` novo. Revisita do
Bug J' (LLM errava posição dos furos).

**Prompt natural:**
```
Crie uma placa retangular parametrizada: Comprimento=120 mm, Largura=80 mm,
Espessura=6 mm, com 4 furos de 8 mm de diâmetro nos 4 cantos, a 15 mm de
cada borda. Tudo paramétrico.
```

**Observar:**
1. Os **4 furos** saem simétricos e corretos? (era o ponto do Bug J')

**Recompute paramétrico** (fecha DT-002 — faça à mão no Fusion):
- *Modify → Change Parameters* → `Comprimento` 120 → 160.
- Os 4 furos se reposicionam sozinhos (continuam a 15 mm dos cantos)?

**Edição por chat** (testa ref ao corpo):
```
Arredonde as arestas verticais dessa placa com fillet de 4 mm.
```
- O fillet acha o corpo certo e aplica só nas verticais?

---

## Gate 4 — Fase 2: Loop agêntico end-to-end

Prova que o loop corrige sozinho e conclui.

**Prompt (gatilho determinístico):**
```
Crie um cubo de 30 mm e arredonde todas as arestas com fillet de 16 mm.
```
Fillet 16 mm é impossível (> metade da aresta) → Fusion rejeita → o loop deve
**reduzir o raio e concluir**.

**Observar no log (pré-voo §5):**
```
agent_loop.correction_attempt ...
executor.step_ok
```
- O cubo sai arredondado (raio < 16) e o plano conclui como **completed**?

---

## Gate F3 — Mecanismos funcionais (thread/joint/composição) ⭐ maior risco (API blind)

`thread`/`joint` foram escritos contra a API documentada **sem Fusion à mão** —
é onde o teu olho vale mais.

> **Macros LEGADAS (ADR-020).** As macros `knuckle_hinge`/`metric_screw` foram
> **deprecadas do planner** (`DEPRECATED_PLANNER_TOOLS`; handlers só p/
> backward-compat/smoke). O **caminho atual** para o mesmo exemplo da
> caixa+dobradiça é o **motor genérico** (composição de primitivas + features) com
> o **Gate Visual** (render → crítica de visão → replan). Os prompts "dirigido"
> abaixo que citam o macro servem só para **smoke do handler legado**; o gate de
> produto é o **prompt natural** (planner compondo) + o **Gate Visual**.

### F3.1 — Dobradiça de nós que ABRE

**Dirigido** (smoke do macro legado `knuckle_hinge` — fora do caminho do planner):
```
Crie uma dobradiça de nós (knuckle hinge) com 5 nós, abas de 40 mm de
comprimento por 20 mm de largura, 4 mm de espessura, pino de 4 mm, e já
monte a junta revolute para ela abrir.
```
**Natural** (prova o planner compondo a montagem):
```
Modele uma caixa de 60x40x30 mm com uma tampa, ligadas por uma dobradiça de
nós (knuckles) numa borda de 60 mm, de modo que a tampa abra e feche.
```
**Observar:** as abas/tampa giram em torno do pino (junta revolute no browser);
os nós são coaxiais e alternados; o pino atravessa todos.

### F3.2 — Parafuso que ENCAIXA (rosca modelada)

**Dirigido** (smoke do macro legado `metric_screw` + `thread` — fora do planner):
```
Crie um parafuso métrico M6 de 24 mm com rosca modelada.
```
**Encaixe** (prova rosca interna casando a externa — a MESMA designação):
```
Crie um bloco de 30x30x15 mm com um furo central roscado M6 (rosca interna
modelada) e um parafuso M6 de 20 mm que encaixe nessa rosca.
```
**Observar:** a rosca é **geometria real** (helicoidal modelada, não textura
cosmética); o parafuso e o furo têm a mesma designação M6 → encaixam.

### F3.3 — Suporte de monitor paramétrico

```
Crie um suporte de monitor em L paramétrico: base de 120x100 mm, coluna
vertical de 200 mm e uma chapa VESA de 100x100 mm com 4 furos M4 nos cantos.
Deixe altura e largura como parâmetros.
```
**Observar:** os 4 furos M4 simétricos; mude `altura` em *Change Parameters* e a
coluna recomputa.

---

## Gate F4 — Image-to-model (vision real)

**Pré-requisito:** ter um modelo **com capability `vision`** habilitado no
registro (Anthropic/OpenAI). Sem isso, cai em metadata-only (sem análise da
imagem) — confirme no modal de Diagnóstico / `GET /api/models`.

**Fluxo:** anexe uma **foto** de uma peça no chat 3D e mande:
```
Analise essa imagem e modele a peça o mais fiel possível. Antes de gerar,
me diga em texto o que você entendeu da forma e das features.
```
**Observar:** a descrição fala da **forma/features da imagem** (caixa, furos,
nervuras…), não do nome do arquivo; o sólido gerado lembra a foto.

---

## Gate F5 — Edição robusta (geometria ao vivo)

Precisa da flag `LIVE_GEOMETRY_RECONCILIATION_ENABLED=true`. Sequência:
1. **Chat:** `Crie um cilindro de 20 mm de diâmetro e 40 mm de altura.`
2. **À mão no Fusion:** mude o diâmetro para **30 mm** (edite a feature/parâmetro).
3. **Chat (mesma conversa):** `Adicione um furo de 6 mm centralizado no topo.`

**Observar:** o furo sai centrado no topo de **30 mm** (estado atual), não no de
20 mm (snapshot velho). No trace, a reconciliação da edição mostra a geometria
ao vivo (`<model-state>` com o raio real). Comparativo opcional: repita com a
flag OFF e veja a diferença.

---

## Gate F6 — Determinismo (sanitizer)

Roda o mesmo pedido **2×** sem mudar nada — ambos devem fechar igual:
```
Crie uma placa de 120x80x6 mm com 4 furos de 8 mm nos cantos, a 15 mm de
cada borda.
```
**Observar:** os 4 furos saem certos nas 2 execuções (era o Bug J'). Se o LLM
tentar um campo-fantasma (`face:"Placa.top_face"`, `bounding_box.max_x`), o trace
mostra `plan_sanitizer drop_ghost_key`/`drop_geom_ref_value` e o step **não falha**
por causa disso. Sanitizer já vem ON por padrão.

---

## Gate Visual — motor genérico (render → visão → replaneja) ⭐ o destravador

Precisa de `TRUTHS_FORGE_MODELING_VISUAL_VERIFICATION_ENABLED=true` (+ loop ON) e
um modelo com capability `vision` habilitado. Use um caso onde a composição
costuma errar a geometria (ex.: a caixa com dobradiça):
```
Modele uma caixa de 60x40x30 mm com uma tampa ligada por uma dobradiça de nós
(knuckles) na borda de cima de 60 mm, de modo que a tampa abra e feche.
```
**Observar (logs — pré-voo §5, filtre por `visual.`):**
1. Após a execução, aparece um `capture_viewport` (render) e um evento
   `visual.critique` com o veredito.
2. Se a geometria saiu errada (knuckles no lado errado / tampa solta), o veredito
   vem `matches=false` com as divergências e o loop **replaneja uma edição
   corretiva** (novo plano `kind=edit`) — depois re-renderiza e re-critica.
3. O modelo final deve estar **mais próximo da intenção** do que sem a flag.
   Compare com a flag OFF (sem auto-correção visual).

> É o passo que faz a composição genérica (sem macros de produto) se
> auto-corrigir. O dono valida olhando o modelo + os eventos `visual.critique`.

---

## Gate F7 — Posicionamento paramétrico (declarativo → montagem nativa) ⭐ API-blind

Precisa de `TRUTHS_FORGE_MODELING_SPATIAL_RESOLUTION_ENABLED=true` (e, p/ o caso
oficial, o **Gate Visual** ON). O resolver de backend (`spatial_resolver`) já está
mock-verde, mas a **montagem nativa** (`joint`/`make_component`/`combine`) nunca
rodou no Fusion à mão — é onde o teu olho vale. Faça **na ordem** P1 → P2 → P6:
o P1 valida a fundação ANTES de confiar na camada declarativa por cima.

> **P1 + P2 VALIDADOS no Fusion real (2026-06-08, autônomo):** com a conexão MCP
> consertada (`0851c65`), rodei via probe. **P2 PASSOU** — `query_geometry`
> devolve `bbox_min/max_mm` + pontas/direção de aresta corretos (a caixa nasce
> CENTRADA na origem: bbox `[-30,-20,0]→[30,20,20]` p/ 60×40×20; logo
> `@body('X').bbox.max_z`=20, `min_x`=-30 etc.). **P1 PASSOU** (após 2 fixes,
> `be1acd0`/`ff09762`): `make_component` + **combine-DENTRO** (3 corpos → 1
> sólido) + **joint revolute ENTRE componentes** (`createByPlanarFace` no proxy
> da occurrence) = "Junta criada". A fundação de montagem (que gateia o resto do
> F7) está **provada**. Falta só o **P6 visual** (dobradiça que abre via loop) —
> esse precisa do teu olho.
>
> **Gotcha de Fusion travado:** se o adapter mostra `conectado/http` mas toda
> execução dá **timeout** (status leve responde, mas `execute` trava), quase
> sempre há um **modal aberto no Fusion** (ex.: um erro de feature). Vá ao Fusion
> e **feche o diálogo**; aí as tools voltam a rodar.
>
> **Pós-review adversarial (2026-06-08, 14 fixes — commits `d7f1bf6`/`ea1c85d`/
> `0150351`):** endurecido o "NUNCA chuta" (token vazio, @-ref em campo fora do
> whitelist, count/spacing inválidos, ÷0, eixo de corpo, spacing que não cabe →
> todos erro TIPADO). **DECISÃO PENDENTE DO DONO:** a `combine-DENTRO` emite
> `combine_bodies` (categoria **high_risk**); pela constituição a expansão F7 NÃO
> auto-executa high_risk → hoje o P6 da dobradiça **falha tipado**
> `fusion.spatial_expansion_requires_approval` no passo de combine. Decida: (a)
> exibir card de aprovação do sub-passo, ou (b) reclassificar o `combine join`
> gerado pelo resolver como auto-aprovável. Até lá, P6 com `alternate` (knuckles)
> para no combine — esperado, não bug.
>
> **Placement estático DETERMINÍSTICO (2026-06-09, gate `m3d_plan_57e048`):** o
> `place_body` (flush) deixou de emitir componente+junta e passou a um `move_body`
> com **delta MEDIDO** (`target.center − anchor.center` no eixo da normal da face
> ancla) → contato com **folga 0**, corpos separados, sem o LLM calcular
> coordenada (a fonte da folga de 1,5 mm: o planner usava `move_body` absoluto). O
> nudge agora PROÍBE `move_body`/`origin_mm` para posição RELATIVA. A junta segue
> só p/ cinemática (`align_axis`/dobradiça). Sem combine ⇒ sem o gate high_risk
> acima no caminho estático.

### F7.P1 — Fundação de montagem (joint + make_component + combine-DENTRO)

Isola o adapter do LLM via **plano literal** (ver §"Plano literal" abaixo). Cole os
steps e execute:
```powershell
$steps = @{ steps = @(
  @{ title="Caixa";  tool_name="fusion.add_box";       input_json=@{ width_mm=60; depth_mm=40; height_mm=20; name="Caixa" } },
  @{ title="Tampa";  tool_name="fusion.add_box";       input_json=@{ width_mm=60; depth_mm=40; height_mm=3;  name="Tampa"; origin_mm=@(0,0,20) } },
  @{ title="CompC";  tool_name="fusion.make_component"; input_json=@{ body_ref="Caixa"; name="Caixa" } },
  @{ title="CompT";  tool_name="fusion.make_component"; input_json=@{ body_ref="Tampa"; name="Tampa" } },
  @{ title="Junta";  tool_name="fusion.joint";          input_json=@{ joint_type="revolute"; body_one="Tampa"; body_two="Caixa"; face_selector_one="top"; face_selector_two="top"; axis="x" } }
) }
```
**Observar:** os 2 viram **componentes** no browser; a **junta revolute** aparece e
a tampa **gira** em torno do eixo X (arraste no Fusion). **Combine-DENTRO:** num 2º
teste, crie `Caixa` + 2 cilindros, `make_component` da Caixa, mova os cilindros pra
dentro dela e `combine_bodies join` → **1 sólido** dentro do componente (é o que a
dobradiça precisa: nós fundidos na caixa, não entre componentes). Mande o **dump
dos steps** (in/out) se a junta não montar — é fix-by-trace.

### F7.P2 — `query_geometry` enriquecido (números do probe)

Plano literal com 1 caixa conhecida + 1 step `fusion.query_geometry`; depois
inspecione o `output_json` do step de query:
```powershell
# após executar [add_box 60x40x20 'Caixa', query_geometry], dump do último step:
$p = Invoke-RestMethod "http://127.0.0.1:8000/api/3d/plans/<PLAN_ID>"
$p.steps[-1].output_json | ConvertTo-Json -Depth 8
```
**Observar:** por corpo, `bbox_min_mm`≈[0,0,0] e `bbox_max_mm`≈[60,40,20] (não só
`dimensions_mm`); por **aresta reta**, `start_point_mm`/`end_point_mm` nas pontas
certas e `direction` unitário (ex.: [1,0,0] numa aresta X). Arestas circulares vêm
com esses campos `null` (ok — o eixo vem do centro/raio). São os números que o
resolver consome; se vierem errados, o placement erra — manda o dump.

### F7.P6 — Placement declarativo + dobradiça que ABRE (caso oficial)

**Natural** (flag F7 + Gate Visual ON; prova o planner declarando placement):
```
Modele uma caixa de 60x40x30 mm com uma tampa ligada por uma dobradiça de nós
(knuckles) na borda de cima de 60 mm, de modo que a tampa abra e feche. A caixa
deve sair impressa como UMA peça e a tampa como outra.
```
**Observar (logs — pré-voo §5, filtre por `spatial_resolved|visual.`):**
1. No trace aparece `executor.spatial_resolved` com `concrete_tools` (ex.: a
   `place_body`/`distribute_along` vira `make_component`/`combine_bodies`/`joint`).
2. Os **knuckles** caem na **borda certa** (a aberta) e **alternados** caixa/tampa,
   fundidos cada grupo no seu corpo (combine-DENTRO); o **pino**/eixo é coaxial.
3. A tampa **abre e fecha** (junta revolute entre os componentes).
4. Se ainda divergir, o **Gate Visual** replaneja a correção — observe convergir.

**Comparativo:** repita com `SPATIAL_RESOLUTION_ENABLED=false` — o planner volta a
chutar `origin_mm` (deve errar mais o posicionamento). É a evidência do ganho.

> **Regressão (importante):** rode um caso simples **sem** montagem (ex.: o Gate F6
> da placa+4 furos) com a flag F7 **ON** — deve sair **idêntico** ao da flag OFF
> (a resolução é no-op quando não há ref espacial). Se mudar algo, é bug.

---

## Gate F8 — Identidade, proveniência, auto-crítica e relação (ADR-023)

Código entregue mock-verde, atrás de flags próprias (default OFF). Pré-requisito do
**Spike** (task #56) p/ confiar curvas/diff sob edição paramétrica — ver abaixo.

### F8.D1 — Proveniência + auto-crítica geométrica
Ligue `TRUTHS_FORGE_MODELING_PROVENANCE_ENABLED=true` +
`TRUTHS_FORGE_MODELING_SELF_CRITIQUE_ENABLED=true`. O `MODELING_VISUAL_VERIFICATION_
ENABLED` pode ficar **ON ou OFF** (a visão vira entrada `source=semantic` do veredito;
o replan destrutivo é opt-in à parte e fica OFF). O `HIERARCHICAL_PLANNING` também
pode ficar **ON ou OFF**: a auto-crítica agora avalia no nível do TURNO (agrega os
blocos) — com hierárquico ON, veja `orchestrator.turn_verdict`; com OFF, `agent_loop.
verdict`. Rode um build simples, ex.: caixa 60×40×20 ocada + tampa.

**Observar (filtre por `provenance_recorded|agent_loop.verdict`):**
1. `executor.provenance_recorded` por passo mutativo, com `summary` coerente
   (add_box → "criou 1 body"; combine → "consumiu N"; pocket → face "consumed", não
   "deleted").
2. Ao fim, **`agent_loop.verdict`** com `overall` + `findings`. Se aparecer um corpo
   órfão (ex.: `Caixa (1)`), o veredito deve marcá-lo **DEMAIS/excess** — é o bug do
   P6 antigo virando achado determinístico. Sem órfão e contagem certa → `ok`.
   Se `overall != ok`, o chat agora **avisa** (não diz "finalizado" limpo).
   Com o visual ON, veja também `visual.critique` (mode=verdict_input) e achados
   `👁 visão:` (`source=semantic`) no mesmo veredito — sem replan/duplicação.
3. **Regressão:** repita com as duas flags **OFF** — zero `provenance_recorded`/
   `verdict` e geometria **idêntica**.

### F8.R1 — Relação genérica (flush_mate) → montagem nativa
Ligue `TRUTHS_FORGE_MODELING_RELATION_PLACEMENT_ENABLED=true`. O `fusion.relate_bodies`
está **dark no planner** (não validado) — dirija por **plano literal** (fallback
abaixo): primeiro `add_box 'Caixa'` (ocada) + `add_box 'Tampa'`, depois um passo
`tool_name="fusion.relate_bodies"` com `input_json={kind:"flush_mate", moving:"Tampa",
reference:"Caixa"}`.

**Observar (filtre por `relation_resolved`):**
1. `executor.relation_resolved` com `kind=flush_mate` e
   `concrete_tools=["fusion.make_component","fusion.joint"]` (a relação derivou medindo
   a face de baixo da Tampa e a de cima da Caixa — **sem token chutado**).
2. A Tampa **encosta** no topo da Caixa (junta rígida); sem folga nem penetração.
3. Tente `kind:"coaxial_insert"` (pino+furo) → deve virar `fusion.align_axis` (revolute).
4. **Erro tipado:** `relate_bodies` com `reference` inexistente → falha clara
   (`fusion.relation_underivable`), nunca posiciona no escuro.

> **Acoplado ao P6:** o reparo de offset (folga/penetração medida) é só **proposto**
> pelo `geometry_verifier` (não auto-aplicado) até o motor de junta com offset do P6.

### F8.Spike — Identidade sob edição paramétrica (BLOQUEIA curvas) 🔒
Probe (molde `_gate_f7_probe.py`): **(a)** `SketchCurve.attributes` sobrevive a
`extrude`+recompute? **(b)** `entityToken` de face sobrevive a mudar 1 parâmetro de
dimensão (não só re-run)? Resultado define se o diff afirma `deleted` ou marca
`uncertain`, e se curvas entram no escopo. Sem isso, F8 cobre só corpo/face/aresta.

---

## Gate F9 — Posicionamento relativo + estado semântico + enforcement (ADR-024)

Código entregue mock-verde, atrás de **três flags próprias** (default OFF). Gateie
**uma flag por vez** (são independentes). Pré-requisito comum: F0 já corrige o parser
do `ModelState` p/ preservar `is_open_boundary` (sem flag).

> **F5 (toque no script, p/ o dono):** o estado semântico e o `cover_opening` dependem
> de `is_open_boundary` MEDIDO no B-Rep. Hoje `fusion_mcp_scripts._query_geometry` NÃO
> emite o campo (só o mock/teste o seta) → no Fusion real `roles`/`body_label` ficam sem
> a abertura. Enriquecer `_query_geometry` p/ marcar a face de borda de abertura
> (loop de edges com 1 só face adjacente) é o trabalho do Gate F9.P2 abaixo.

### F9.P1 — Modos de alinhamento (`align`)
Ligue `TRUTHS_FORGE_MODELING_ALIGN_MODES_ENABLED=true` (+ `SPATIAL_RESOLUTION` p/ o
`place_body` existir). Rode caixa+tampa dirigindo o `place_body` com `align`:
1. `align:"coplanar"` numa tampa criada deslocada lateralmente → encosta no topo MAS
   **mantém o offset** (não recentra). Compare com `align:"center"` (centra).
2. `align:"gap"` + `gap_mm:2` → tampa fica **2 mm acima** do topo (folga do lado certo).
3. `align:"edge"`/`"corner"` num par de caixas axiais → alinha pela borda/canto.
4. **Erro tipado:** `edge`/`corner` num corpo rotacionado → `fusion.bbox_not_axis_aligned`
   (NUNCA alinha torto); `gap` com faces coincidentes → `fusion.gap_side_undeterminable`.
5. **Regressão:** flag **OFF** → `align` IGNORADO, `place_body` centra como antes.

### F9.P3 — Enforcement de coordenada relativa (Gate B)
Ligue `TRUTHS_FORGE_MODELING_RELATIVE_ENFORCEMENT_ENABLED=true`. Force um `move_body`
de coordenada absoluta (plano literal): crie `Caixa` + `Tampa` e mova a Tampa
1. para DENTRO da Caixa (sobreposição) → **recusa** `fusion.relative_coord_forbidden`;
2. para 80 mm longe de tudo → **recusa** (mesma); o chat instrui a usar `place_body`.
3. Um `move_body` que encosta limpo (folga 0) → **passa**.
4. **Regressão:** flag **OFF** → o `move_body` absoluto passa direto (sem probe).

### F9.P2 — Estado semântico no `<model-state>`
Ligue `TRUTHS_FORGE_MODELING_SEMANTIC_STATE_ENABLED=true` (+ o toque F5 no script p/
`is_open_boundary` real). Rode caixa ocada + tampa e inspecione o `<model-state>`:
1. faces com `papéis=top_planar/bottom_planar/open_boundary`; corpos com
   `papel=container`/`papel=lid` e linhas `encosta em '<corpo>'`.
2. O planner ECOA o role no `place_body` (anchor/target por role, sem token chutado).
3. **Regressão:** flag **OFF** → bloco `<model-state>` idêntico ao atual (sem semântica).

---

## Plano literal via API (fallback — quando nem natural nem dirigido funcionam)

Isola 100% o adapter do planner (tira o LLM da equação). Útil pros casos
version-sensitive. O fluxo (PowerShell):

```powershell
$api = "http://127.0.0.1:8000/api/3d"
# 1. Crie um plano qualquer pela UI (qualquer prompt) e pegue o <PLAN_ID>.
# 2. Substitua os steps pelo plano literal:
$steps = @{ steps = @(
  @{ title="Parâmetros"; tool_name="fusion.set_parameter";
     input_json=@{ parameters=@{ Largura="100 mm"; Espessura="2 mm" } } },
  @{ title="Caixa";      tool_name="fusion.add_box";
     input_json=@{ width_mm=100; depth_mm=60; height_mm=2; name="Chapa" } }
) }
Invoke-RestMethod "$api/plans/<PLAN_ID>" -Method Patch -ContentType 'application/json' `
  -Body ($steps | ConvertTo-Json -Depth 12)
# 3. Aprove e execute:
Invoke-RestMethod "$api/plans/<PLAN_ID>/approve" -Method Post -ContentType 'application/json' -Body '{"decision":"approve"}'
Invoke-RestMethod "$api/plans/<PLAN_ID>/execute" -Method Post
```

> ⚠️ Patches por `edge_ids` (carenagem) dependem dos índices que o sweep gerou —
> esses só se sabe rodando `query_geometry` **depois** do sweep. Para esses casos,
> mande o trace do sweep que **eu monto o plano literal** com os edge_ids certos.

## Ordem recomendada

Gate 1 (superfícies) → Gate 2 (sheet metal) → Gate 3 (placa/params) → Gate 4
(loop). Os Gates 1 e 2 concentram o risco (tools novas) — se algo quebrar, será
ali, e o dump dos steps + trace permite correção fix-by-trace na mesma sessão.

Para o **F7** (posicionamento paramétrico, código entregue mock-verde): **Gate F7
P1** (fundação de montagem — joint/component/combine) → **P2** (números do
`query_geometry`) → **P6** (placement declarativo + dobradiça que abre via loop
visual). O P1 concentra o risco API-blind; valide-o antes de confiar no P6.
