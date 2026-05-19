# Plano: Observabilidade estruturada do módulo de modelagem 3D

## Contexto

O pipeline de modelagem 3D falha silenciosamente em vários pontos. O caso recente: o usuário pediu "uma bola", o Fusion gerou um retângulo 40×20mm, e foram necessárias horas de debug para descobrir que o `planner_service` caía em fallback heurístico porque o modelo default no Postgres era um modelo de teste fake (`test/audit-cost-*` sem `provider_model_id` válido). O `fallback_reason` ficava persistido no `ModelingPlan` mas nunca era surfaceado ao usuário, e a falha do LLM era logada como `warning` sem stack trace.

**Objetivo:** instrumentação estruturada ponta-a-ponta (UI → backend → MCP → Fusion/Blender) com correlation ID, structured logging JSON, persistência em tabela dedicada, e surfacing imediato de falhas críticas via SSE + UI. Escopo limitado ao módulo de modelagem 3D nesta iteração.

## Decisões já alinhadas com o usuário

- **Escopo:** médio (instrumentação estruturada com trace_id propagado + JSON logging só no módulo modeling + nova tabela `modeling_trace_events`).
- **Consumo:** trace ponta-a-ponta UI+backend+infra + logs do backend estruturados.
- **Conteúdo LLM (prompt/resposta):** atrás de flag `TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE=false` por default.

## Arquitetura

### Identificadores e propagação

- `trace_id` em formato **ULID** (sortable, debuggable) gerado em `chat_orchestrator.propose_plan` quando intent 3D é detectado.
- Propagado via **contextvars** no backend (Python `contextvars.ContextVar`) — todo `logger.info/error` no módulo modeling captura automaticamente.
- SSE: incluído em metadata dos eventos `modeling_plan` e novo `modeling_trace_event`.
- MCP → Fusion/Blender: campos reservados `_trace_id` e `_parent_event_id` no envelope JSON-RPC (fora do contract de tool args). Addin retorna `trace_events: []` array que o backend drena via `ModelingTracer.record()` ao receber resposta.
- Frontend: envia `trace_id` em todos os POSTs para `/api/modeling/traces/events`.

### Novo contrato e armazenamento

**`ModelingTraceEvent`** em `backend/app/core/contracts.py`:
```
id: str (ULID)
trace_id: str (ULID)
plan_id: str | None
session_id: str | None
project_id: str | None
event_type: str             # dotted: "planner.fallback_used", "executor.step_started", "ui.modal_opened"
source: Literal["ui", "backend", "mcp", "fusion", "blender"]
level: Literal["debug", "info", "warn", "error"]
message: str | None
payload: dict[str, Any]     # capped a 50KB, com flag `_truncated: bool`
duration_ms: int | None
sequence: int               # monotônico dentro do trace para dedupe SSE vs GET
schema_version: int = 1
created_at: datetime
```

**Tabela Postgres** `modeling_trace_events` adicionada em `postgres_store.py::_ensure_schema` (não via Alembic — segue o padrão do repo):
```sql
CREATE TABLE modeling_trace_events (
  id TEXT PRIMARY KEY,
  trace_id TEXT NOT NULL,
  plan_id TEXT,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_mte_trace_id ON modeling_trace_events(trace_id, created_at);
CREATE INDEX idx_mte_plan_id ON modeling_trace_events(plan_id);
```

**DevStore JSON:** ring buffer dos últimos N=50 traces (lista única em memória, capped). Filtros via Python (sem JSONB operators).

**AuditEvent (contracts.py:194-203):** adicionar campo opcional `trace_id: str | None = None`. Eventos âncora (`modeling.plan_created`, `modeling.chat.plan_proposed`, `modeling.chat.execution_completed`) passam a setá-lo para navegação bidirecional trace↔audit. Sem mudança no schema da tabela `audit_events` (já é JSONB).

### Tracer e logging estruturado

**Novo módulo** `backend/app/modeling/observability.py`:

- `ModelingTracer` injetável (via FastAPI dependency), expõe:
  - `start_trace(session_id, project_id, plan_id=None) -> str` (retorna trace_id, seta contextvar)
  - `record(event_type, source, level, message=None, payload=None, duration_ms=None)` (síncrono + assíncrono)
  - `record_span(event_type, ...)` context manager para operações cronometradas
  - Batch interno: buffer in-memory, flush ao final de cada span ou a cada 25 eventos.
- `TraceContextFilter` para `logging`: injeta `trace_id` no `LogRecord` lendo da contextvar.
- `JsonFormatter` aplicado SÓ aos loggers do namespace `app.modeling.*` (não polui logs do resto do app).
- `_truncate_payload(payload, limit_bytes=50_000)` helper que marca `_truncated: True` em caso de corte.

### Pontos de instrumentação obrigatórios

| Arquivo | Linha aprox. | Evento(s) emitidos |
|---|---|---|
| `chat_orchestrator.py:154` (`propose_plan`) | start | `trace.started` (info, source=backend) |
| `planner_service.py:149` (`_resolve_planner_model`) | sucesso | `planner.model_resolved` (info, payload: model_id, provider_model_id, default flag) |
| `planner_service.py:167-168` (None retornado) | falha | **`planner.model_unavailable` (error)** payload: candidatos considerados + razão de rejeição de cada um — evento mais valioso para o bug original |
| `planner_service.py:113-121` (LLM call) | span | `planner.llm_request` → `planner.llm_response` ou `planner.llm_error` (com `exc_info=True`) |
| `planner_service.py:122-124, 145-147` | warn→error | promover `logger.warning` → `logger.error(..., exc_info=True)` + emitir `planner.fallback_used` (error, payload: fallback_reason completo) |
| `executor.py:86-181` (`execute_plan`) | span por step | `executor.step_started` → `executor.step_ok` ou `executor.step_error` |
| `mcp_client.py:188` (stdio falha) | warn→error | `mcp.transport_error` |
| `mcp_client.execute_step` | span | `mcp.dispatch` → `mcp.response` |
| `attachment_analyzer.py:189, 319` | falha silenciosa | `attachment.analysis_failed` (warn) |
| `policy.py` (decisões de printability/segurança) | sempre | `policy.decision` (info se ok, warn se mutar plano, error se rejeitar) |
| `chat_state.py` (transições) | toda transição | `state.transition` (debug) — facilita diagnosticar "PLAN_PROPOSED disparou mas guard X bloqueou" |
| `snapshot_service.py` (write/restore) | falha | `snapshot.write_failed` ou `snapshot.restore_failed` (error) |
| `fusion_mcp_scripts.py:278, 418` | falha addin | `fusion.tool_error` (error) — chega via `trace_events: []` do addin |
| Frontend (cliente) | UI actions | `ui.modal_opened`, `ui.plan_approved`, `ui.step_retried`, `ui.diagnostics_export` |

### Hierarquia de exceções LLM (gateway)

Criar em `backend/app/llm/exceptions.py` (ou local equivalente):
- `LLMProviderError` (base)
- `LLMTimeoutError` (retryable → level=warn)
- `LLMInvalidResponseError` (level=error)
- `LLMAuthError` (level=error, raiz do bug original)

Refatorar `except Exception` em `planner_service.py:122-124, 145-147` para distinguir tipo e emitir `event_type` específico (`planner.llm_timeout` vs `planner.llm_provider_error` vs `planner.llm_auth_error`).

### Endpoints

- **GET** `/api/modeling/plans/{plan_id}/trace` → `list[ModelingTraceEvent]` ordenado por `sequence`. Suporta `?level=warn,error` e `?source=backend,fusion`.
- **POST** `/api/modeling/traces/events` → aceita lote de eventos UI. Rate-limit: 60 req/min por session_id. Rejeita eventos com `trace_id` desconhecido ou trace cujo TTL expirou. Força `source="ui"` server-side.
- **GET** `/api/modeling/plans/{plan_id}/diagnostics` (consolidação opcional) — combina trace + tool_calls + plan metadata em um JSON exportável.

### SSE (chat streaming)

- Evento `modeling_plan` enriquecido: adicionar `trace_id`, `planner_source`, `fallback_reason` no payload.
- **Novo evento `modeling_trace_event`**: emitido em **tempo real** APENAS para `level in (warn, error)` (evita flood de happy path). Modal usa GET histórico no open, e mescla com eventos SSE subsequentes via `sequence` para dedupe.

### Configuração

Em `backend/app/core/config.py`:
- `modeling_observability_enabled: bool = True` (env: `TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED`)
- `modeling_debug_llm_trace: bool = False` (env: `TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE`) — gating do conteúdo de prompt/resposta no payload de `planner.llm_request/response`.
- `modeling_trace_retention_days_info: int = 30` e `modeling_trace_retention_days_error: int = 180` (retention job futuro, fora desta iteração — apenas reservar config).

### Frontend

- **Novo hook** `useModeling3dTrace(planId, traceId)` em `apps/web/src/features/modeling-3d/hooks/` consumindo `/plans/{id}/trace` + ouvindo `modeling_trace_event` via stream do chat.
- **Cliente** `recordClientTrace(traceId, eventType, payload)` postando em `/traces/events`, com debounce e cap de 50 eventos por minuto local.
- Instrumentar: `ModelingDiagnosticsModal` open/close, `ModelingPlanCard` aprovação, retry de step.
- **Nova seção "Trace"** em `ModelingDiagnosticsModal.tsx`: timeline cronológica (ícone por source, cor por level, payload colapsável), filtros por source/level, `trace_id` copiável no topo.
- **Badge no `ModelingPlanCard`**: quando `planner_source === "heuristic"`, mostrar pill vermelha "fallback" com `fallback_reason` em tooltip + link "ver trace" que abre o modal.

## Arquivos críticos a modificar

### Backend
- `backend/app/core/contracts.py` — adicionar `ModelingTraceEvent`, `trace_id` opcional em `AuditEvent`.
- `backend/app/core/config.py` — flags de observability.
- `backend/app/modeling/observability.py` — **novo módulo**, `ModelingTracer`, filters, formatter, contextvars.
- `backend/app/modeling/planner_service.py` — instrumentação + promoção de log level + tratamento de exceções tipadas.
- `backend/app/modeling/executor.py` — span por step.
- `backend/app/modeling/mcp_client.py` — span de boundary + propagar `_trace_id` no wire.
- `backend/app/modeling/fusion_mcp_scripts.py` — drenar `trace_events: []` do addin.
- `backend/app/modeling/chat_orchestrator.py` — `start_trace` em `propose_plan`, anexar `trace_id` em audit events âncora.
- `backend/app/modeling/policy.py`, `attachment_analyzer.py`, `chat_state.py`, `snapshot_service.py` — pontos adicionais de instrumentação.
- `backend/app/llm/exceptions.py` — **novo arquivo**, hierarquia de exceções LLM.
- `backend/app/storage/postgres_store.py` — `_ensure_schema` cria tabela + CRUD `list_trace_events`, `record_trace_events_bulk`. Reusar padrão `_bulk_insert` em `postgres_store.py:569`.
- `backend/app/storage/dev_store.py` — equivalente JSON com ring buffer.
- `backend/app/api/routes/modeling.py` — endpoints GET/trace, POST/traces/events, GET/diagnostics.
- `backend/app/api/routes/chat.py:1141, 1457` — enriquecer `modeling_plan` SSE + emitir `modeling_trace_event`.

### Frontend
- `apps/web/src/features/modeling-3d/hooks/useModeling3dTrace.ts` — **novo**.
- `apps/web/src/features/modeling-3d/hooks/index.ts` — export.
- `apps/web/src/features/modeling-3d/api.ts` (ou equivalente) — `recordClientTrace`, `fetchTrace`.
- `apps/web/src/features/modeling-3d/components/ModelingDiagnosticsModal.tsx` — nova seção Trace.
- `apps/web/src/features/modeling-3d/components/ModelingPlanCard.tsx` — badge fallback + link "ver trace".

### Addin (Fusion)
- `apps/fusion-addin/TruthsForge.py` — aceitar `_trace_id` no envelope, retornar `trace_events: []` na resposta.

### Testes
- `backend/tests/modeling/test_observability.py` — **novo**. Cobrir: trace_id propagação, batching, payload truncation, retention config, exception hierarchy mapping.
- `backend/tests/modeling/test_planner_service.py` — atualizar para verificar `planner.model_unavailable` e `planner.fallback_used` eventos emitidos.

## Reuso (não duplicar)

- `_sse()` em `chat.py:1141` — usar para novo `modeling_trace_event`.
- `_bulk_insert()` em `postgres_store.py:569` — reusar para batch de trace events.
- `AuditEvent` + `record_audit_event()` — manter como está; só estender com `trace_id` opcional.
- `_ensure_schema` em `postgres_store.py:237` — adicionar tabela aqui, não criar migração separada.
- `ModelingDiagnosticsModal.tsx` + `useModeling3dDiagnostics` — estender, não substituir.
- Padrão `formatDurationMs`, `formatTimestamp` em `apps/web/src/features/modeling-3d/format.ts` — reusar na timeline.

## Verificação end-to-end

1. **Caminho do bug original** (com dev-store ainda contaminado ou simulação):
   - Mandar "uma bola" no chat 3D.
   - Esperado: card `ModelingPlanCard` mostra badge vermelha "fallback" com tooltip "Planner LLM falhou: ...".
   - Abrir diagnostics modal → seção Trace mostra: `ui.modal_opened` → `trace.started` → `planner.model_resolved` (warn, model_id=...) ou `planner.model_unavailable` (error com candidatos) → `planner.llm_request` → `planner.llm_auth_error` (error com exc_info) → `planner.fallback_used`.
   - `docker logs truths-forge-backend --tail 100` mostra linhas JSON com mesmo `trace_id` correlacionado.

2. **Caminho feliz** (config corrigida + API key válida):
   - Esperado: badge "fallback" ausente, trace mostra `planner.llm_response` (info), executor steps todos `step_ok`. Sem flood de SSE no happy path (apenas final `done`).

3. **Flag de debug LLM**:
   - Setar `TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE=true`, restart backend.
   - Repetir teste — payload de `planner.llm_request` agora contém prompt completo; `planner.llm_response` contém JSON bruto.
   - Desativar — payload volta a só metadata (model_id, tokens, latência).

4. **Propagação Fusion**:
   - Forçar erro no addin (script test que retorna erro).
   - Esperado: response inclui `trace_events: [{event_type: "fusion.tool_error", ...}]` que aparece na timeline com `source=fusion`.

5. **Volume e limites**:
   - Plano com 20 steps + falhas → verificar batch flush, sem N+1 inserts no log do Postgres (`docker exec ... pg_stat_statements`).
   - Trace com payload de 100KB → verificar `_truncated: true`.

6. **Testes automatizados**:
   - `docker compose ... exec backend python -m pytest backend/tests/modeling/test_observability.py -v`
   - `pnpm --filter @truths-forge/web test:unit` (cobertura do hook + componente).
   - `scripts/quality.ps1` para garantir lint/typecheck.

## Aproveitamento da stack containerizada

A aplicação roda 100% em containers via `infra/docker-compose.yml` + `infra/docker-compose.dev.yml`. O design abaixo explora isso ao invés de duplicar infra.

### Logging via stdout + docker logging driver
- `JsonFormatter` em `app.modeling.*` escreve **direto no stdout** do container `truths-forge-backend`. Sem arquivos de log, sem rotação manual.
- Consumo nativo: `docker logs truths-forge-backend --since 10m --follow | jq 'select(.trace_id=="<ulid>")'`.
- Já há `volumes: - ..:/workspace` (compose dev linha 32), então scripts de host podem fazer `docker logs ... > .local/logs/trace-<id>.json` para snapshots de debug sem mudança na infra.

### Perfil opcional de visualização (compose dev)
- Adicionar **serviço opcional `trace-viewer`** em `infra/docker-compose.dev.yml` sob um `profiles: [observability]`. Padrão off; ativável via `docker compose --profile observability up`.
- Opção minimalista (recomendada nesta iteração): `dozzle` (imagem `amir20/dozzle:latest`, ~20MB) na porta `8082` — UI web pra `docker logs` com filtro por container, busca por substring (`trace_id=<ulid>`) e download. Zero config, zero estado.
- Não introduzir Loki/Grafana/Tempo agora — overkill para o volume previsto e contraria a regra "Não introduzir dependências pesadas sem necessidade clara" (AGENTS.md). Reservar para iteração futura se métrica agregada virar necessidade.

### Persistência: reutilizar volume Postgres já mapeado
- Tabela `modeling_trace_events` herda automaticamente do volume `../.local/postgres:/var/lib/postgresql/data` (compose linha 15). Sem mudança em volumes.
- Backup/inspeção via comando já documentado em `docs/local-dev.md`: `docker exec truths-forge-postgres psql -U forge -d truths_forge_ai -c "SELECT ... FROM modeling_trace_events WHERE trace_id='...'"`.
- Para casos de "export de bundle de diagnóstico", o endpoint `GET /plans/{id}/diagnostics` retorna o JSON — `curl` direto no container basta, sem precisar de exporter dedicado.

### Propagação MCP cruzando boundary container↔host
- O Fusion 360 roda no **host Windows** (não em container), comunicando via MCP em `host.docker.internal:27182` (compose linha 25). O wire JSON-RPC já atravessa essa fronteira — adicionar `_trace_id` no envelope é gratuito.
- O Blender runner roda dentro do container backend (se configurado via `TRUTHS_FORGE_BLENDER_EXECUTABLE`). Para Blender: subprocess herda contextvar via env var injetada (`TRUTHS_FORGE_TRACE_ID`) no `subprocess.Popen(env=...)`.

### Healthcheck do endpoint de trace
- Estender o healthcheck do backend (compose linhas 41-49) para incluir um GET no novo endpoint de listagem de traces, garantindo que o módulo subiu corretamente. Opcional, mas barato.

### Isolamento de testes (resolve a causa raiz da contaminação)
- Adicionar **serviço `postgres-test`** em um arquivo `infra/docker-compose.test.yml` separado (não em dev), com volume **tmpfs** (zero persistência). Conftest do pytest aponta `TRUTHS_FORGE_DATABASE_URL` para esse serviço quando `pytest` roda.
- Isso resolve estruturalmente o bug que originou esta investigação (27 modelos `test/*` na tabela `model_configs`).
- Comando: `docker compose -f infra/docker-compose.test.yml run --rm backend-test pytest`.
- Esta peça é **fora do escopo principal** mas referenciada como tarefa adjacente já registrada (chip "Isolar testes do Postgres de dev" do turno anterior).

### Flags via env do compose
- `TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED` e `TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE` adicionados em `docker-compose.dev.yml` no bloco `environment:` (linhas 12-27), default `true` e `false` respectivamente.
- Toggle sem rebuild: edita compose → `docker compose ... restart backend`. Documentar em `docs/local-dev.md`.

### Smoke test ponta-a-ponta usando os containers
- Script `scripts/smoke-modeling-trace.ps1`:
  1. `docker compose ... up -d` (garante stack)
  2. `curl POST /api/chat/stream` com prompt "uma esfera"
  3. Aguarda SSE `modeling_plan` → captura `trace_id`
  4. `docker exec ... psql ... -c "SELECT event_type, level FROM modeling_trace_events WHERE trace_id='...'"`
  5. Asserta que existe ao menos um evento com `level='info'` e nenhum `planner.model_unavailable` no caminho feliz.
- Roda no CI local antes de PR. Não substitui pytest, é validação de integração rápida.

## Fora de escopo desta iteração

- Retention job (scheduler que deleta trace events velhos) — apenas reservar config.
- Observabilidade fora do módulo modeling (chat geral, RAG, agentes).
- Exporter OpenTelemetry / integração com observability vendor externo.
- Painel de "fallback rate" agregado / alerting — fica para uma iteração posterior com base nos dados coletados.
- Migração de logs do backend inteiro para JSON — só `app.modeling.*` nesta iteração.
