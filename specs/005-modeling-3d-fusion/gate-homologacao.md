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

## Gate 2 — Fase 6: Sheet metal (chapa dobrada)

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
