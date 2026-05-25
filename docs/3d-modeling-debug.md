# Debug do módulo de Modelagem 3D

Receituário de terminal para diagnosticar o fluxo de modelagem 3D (chat → planner
→ plano → execução no Fusion/Blender) **sem precisar abrir o código**. Todos os
comandos assumem a stack de dev no ar (`.\scripts\dev.ps1`) e usam PowerShell 7+.

Nomes e portas usados abaixo:

| Recurso | Valor padrão |
| --- | --- |
| Backend (API) | `http://127.0.0.1:8000` (OpenAPI em `/docs`) |
| Endpoints 3D | `http://127.0.0.1:8000/api/3d/*` |
| Container backend | `truths-forge-backend` |
| Container Postgres | `truths-forge-postgres` (user `forge`, db `truths_forge_ai`) |
| Fusion MCP Server | `http://127.0.0.1:27182/mcp` (Docker: `host.docker.internal:27182`) |
| Servidor MCP standalone | `http://127.0.0.1:8787/mcp` (Fase 1) |

> Atalho: na maioria dos casos `Invoke-RestMethod` já devolve objetos prontos
> para `Select-Object` / `Where-Object` / `Format-Table`. Onde a leitura no
> banco é mais direta, use `docker exec ... psql`.

## Logs no terminal

O backend emite os eventos de modelagem como **logs JSON estruturados** no stdout
(logger `app.modeling.observability`), cada linha com `event_type`, `trace_id`,
`plan_id`, `tool_name`, `error_code` e `trace_payload`. É o jeito mais rápido de
ver o que aconteceu numa execução.

```powershell
# Seguir o backend ao vivo (tudo)
docker logs -f truths-forge-backend

# Só os eventos de trace de modelagem (planner / executor / loop)
docker logs --tail 500 truths-forge-backend | Select-String "modeling.trace"

# Filtrar por tipo: erros de etapa, loop de auto-correção, fallback do planner
docker logs -f truths-forge-backend |
  Select-String "executor.step_error|agent_loop|planner.fallback_used"

# Tudo de UM plano (ou de um trace_id) específico
docker logs --tail 4000 truths-forge-backend | Select-String "m3d_plan_xxxxxxxx"
docker logs --tail 4000 truths-forge-backend | Select-String "mt_019e..."
```

**Via `docker compose`** (precisa dos 2 arquivos + env — ver §5):

```powershell
docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml logs -f backend
```

**Outros serviços:**

```powershell
docker logs -f truths-forge-qdrant       # ex.: progresso do recovery
docker logs --tail 80 truths-forge-postgres
docker logs --tail 80 truths-forge-web
```

**Dozzle** — visualizador web de logs (opcional; filtra os containers `truths-forge-*`):

```powershell
docker compose --env-file infra/.env -f infra/docker-compose.yml -f infra/docker-compose.dev.yml --profile observability up -d dozzle
# abra http://127.0.0.1:8082
```

Para incluir prompt/resposta do LLM no log, ligue `TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE=true` (§5) e reinicie o backend.

## 1. Saúde e conexões

```powershell
# Backend vivo?
Invoke-RestMethod http://127.0.0.1:8000/health

# Flags efetivas DENTRO do container (decide mock vs real, loop, transporte)
docker exec truths-forge-backend printenv |
  Select-String 'MODELING_|FUSION_MCP|MCP_TRANSPORT|^OPENAI_API_KEY='
```

No **modal de Diagnóstico 3D** (cabeçalho do chat 3D), a seção *Adapters* mostra o
transporte de cada adapter: `fusion` deve aparecer **`conectado` / `http`** quando
o Fusion MCP Server está ligado. Se aparecer **`mock`**, o backend não está
alcançando o Fusion — confira `TRUTHS_FORGE_FUSION_MCP_URL` e se o add-in/Server
está ativo no Fusion.

## 2. Modelo do planner (o que decide LLM × heurístico)

Se o card do plano vier com a tag **`PLANNER: FALLBACK`** (em vez de `PLANNER: IA`),
o planner caiu no heurístico. A causa quase sempre é o **modelo default** apontar
para um `provider_model_id` inexistente (ex.: `audit-cost-model`, resíduo de teste).

```powershell
$base = "http://127.0.0.1:8000/api/models"

# Quais modelos OpenAI de chat existem e qual é o default?
Invoke-RestMethod $base |
  Where-Object { $_.provider -eq 'openai' -and $_.capabilities -contains 'chat' } |
  Select-Object id, provider_model_id, default, enabled | Format-Table -Auto
```

O planner resolve **o modelo `default`** (entre os OpenAI + `chat` + `enabled`).
Se o default estiver errado, **recoroe o modelo bom** — o `upsert` garante "default
único", então salvar um com `default=true` zera os demais:

```powershell
$m = (Invoke-RestMethod $base) | Where-Object id -eq 'openai/default-chat'
$m.default = $true
# (opcional) fixar um provider_model_id real:  $m.provider_model_id = 'gpt-4o-mini'
Invoke-RestMethod $base -Method Post -ContentType 'application/json' `
  -Body ($m | ConvertTo-Json -Depth 12)
```

> A API **não tem DELETE** de modelo. Registros de teste poluídos (`test/...`) só
> podem ser desabilitados (`enabled=false`) por `upsert` ou removidos via SQL /
> script de purga. Ver [test-data-cleanup] na memória do projeto.

## 3. Planos e etapas (achar o que o LLM gerou)

```powershell
$api = "http://127.0.0.1:8000/api/3d"

# Últimos planos
Invoke-RestMethod "$api/plans" | Select-Object -First 8 `
  id, status, planner_source, @{n='steps';e={$_.steps.Count}} | Format-Table -Auto

# Dump das etapas de UM plano: tool + args de entrada + resumo da saída
$p = Invoke-RestMethod "$api/plans/<PLAN_ID>"
$p.steps | ForEach-Object {
  "{0}. {1} [{2}]" -f $_.seq, $_.tool_name, $_.status
  "    in : " + ($_.input_json  | ConvertTo-Json -Compress -Depth 8)
  "    out: " + ($_.output_json | ConvertTo-Json -Compress -Depth 8)
}
```

É assim que se pega bug de geometria: olhe os `input_json` (qual `sketch`,
`operation`, `distance_mm`) e o `output_json` (ex.: `query_geometry` com
`dimensions_mm: [0,0,0]` ⇒ corpo vazio/apagado).

## 4. Tool calls, trace e diagnóstico

```powershell
# Tool calls + trace + printability num único bundle
Invoke-RestMethod "$api/plans/<PLAN_ID>/diagnostics" |
  Select-Object @{n='tool_calls';e={$_.tool_calls.Count}},
                @{n='trace_events';e={$_.trace_events.Count}}

# Só os eventos de trace do plano
Invoke-RestMethod "$api/plans/<PLAN_ID>/trace"

# Por trace_id (pega eventos do planner que ainda não têm plan_id)
Invoke-RestMethod "$api/traces/<TRACE_ID>"
```

Lendo a tabela direto (útil quando o filtro por plano vem vazio):

```powershell
docker exec truths-forge-postgres psql -U forge -d truths_forge_ai -c `
"SELECT payload->>'event_type' AS event, COALESCE(plan_id,'<null>') AS plan, created_at
 FROM modeling_trace_events ORDER BY created_at DESC LIMIT 20;"

# Total de eventos / eventos de um plano específico
docker exec truths-forge-postgres psql -U forge -d truths_forge_ai -c `
"SELECT count(*) FROM modeling_trace_events WHERE plan_id='<PLAN_ID>';"
```

### Trace aparece vazio?

1. **Flag desligada** — `record()` vira no-op se
   `TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED` for falso. Confira no container
   (seção 1). Default é `true`.
2. **Eventos com `plan_id` nulo** — spans do planner gravados antes do
   `bind_plan()` não casam no filtro por plano; busque por `trace_id` ou direto na
   tabela.
3. **Execução sem trace** — se houver tool calls mas **nenhum** evento
   `executor.*`/`agent_loop.*`, o caminho de execução não abriu/propagou o trace
   (bug conhecido — ver Gotchas).

## 5. Ligar/desligar flags

Edite `infra/.env` (ou exporte no shell antes de subir a stack) e **reinicie o
backend**:

```dotenv
TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED=true
TRUTHS_FORGE_MODELING_AGENTIC_LOOP_ENABLED=true   # loop de auto-correção (Fase 2)
TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE=true        # inclui prompt/resposta no trace
TRUTHS_FORGE_MCP_TRANSPORT=mcp_http               # roteia fusion.* pelo servidor standalone
```

```powershell
docker compose -f infra/docker-compose.dev.yml restart backend
```

## 6. Smoke da observabilidade

```powershell
pwsh scripts/smoke-modeling-trace.ps1
# valida: /health, POST /api/3d/traces/events, leitura por trace_id e persistência
# na tabela modeling_trace_events. Não exercita o LLM real.
```

## 7. Servidor MCP standalone (Fase 1)

```powershell
cd backend
.\.venv\Scripts\python.exe -m app.modeling.mcp_standalone   # sobe em 127.0.0.1:8787/mcp
# Token gerado em .local/modeling/mcp_server_token (header Authorization: Bearer <token>)
```

Conecte um cliente MCP externo (ex.: `npx @modelcontextprotocol/inspector`) em
`http://127.0.0.1:8787/mcp` com o Bearer; `tools/list` deve trazer as `fusion.*`
**sem** `fusion.run_script` (RF-023). Sem o token ⇒ **401**.

## 8. Gate de qualidade

```powershell
pwsh scripts/quality.ps1        # backend ruff+pytest, web format/lint/test/typecheck/build
```

## Gotchas já diagnosticados

- **`PLANNER: FALLBACK` por modelo poluído** — um `test/audit-cost-*` com
  `default=true` (resíduo de testes sem isolamento) destrona o `openai/default-chat`
  e o planner chama um `provider_model_id` inexistente → 400 → heurístico.
  Correção na seção 2.
- **Trace por plano vazio mesmo com a flag ligada** — (a) spans do planner saem com
  `plan_id` nulo (gravados antes do `bind_plan`) e (b) o caminho de
  aprovação/execução não abre trace, então a execução não gera eventos. Enquanto não
  corrigido, diagnostique por `trace_id` ou direto na tabela (seção 4).
- **`fusion.extrude_profile` extruda sempre `profiles.item(0)`** — não há seleção de
  perfil. Em sketch com mais de um perfil (ex.: retângulo + círculo coplanares), o
  `new_body` já produz o furo e um `cut` posterior reextruda **o mesmo perfil** (a
  placa inteira), apagando o corpo. Para furos: use sketches separados (corpo →
  sketch na face → `cut`) ou um único perfil líquido.
