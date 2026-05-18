# tasks.md

## v1 — chat + painel híbrido (histórico)

- [x] [P1] [devin] Adicionar contexto `modeling_3d` ao contrato de chat com validação contra modos concorrentes.
- [x] [P1] [devin] Criar plano MCP 3D a partir de `POST /api/chat/stream` e persistir metadata na mensagem da JUDITE.
- [x] [P1] [devin] Renderizar card de plano 3D dentro do chat.
- [x] [P1] [devin] Mover a criação primária para o chat e deixar a aba 3D como configuração/diagnóstico/continuidade.
- [x] [P1] [devin] Diferenciar mock, adapter ausente, execução real e erro na UI de adapters MCP.
- [x] [P1] [devin] Criar contrato detalhado do Fusion bridge.
- [x] [P1] [devin] Implementar versionamento de exports como artifacts.
- [x] [P1] [devin] Expandir printability mínima com recomendações acionáveis.
- [x] [P1] [devin] Ampliar planner Fusion para tools seguras de design/sketch/export.
- [x] [P1] [devin] Corrigir exclusividade MCP 3D vs multiagente e persistência de título no chat.
- [x] [P1] [devin] Tornar o fluxo 3D do chat fluido, com autoexecução para adições/alterações normais allowlistadas.
- [x] [P1] [devin] Remover snapshot automático do planner/card no fluxo fluido.

Tasks pendentes da v1 são absorvidas pela Onda 6 da v2:

- [ ] [P1] [any] Validar Blender real como caminho obrigatório quando configurado (→ Onda 6).
- [ ] [P1] [any] Testar prompt no chat, plano fluido, autoexecução e export com Blender/Fusion reais (→ Onda 6).
- [ ] [P1] [any] Testar aprovação de etapa destrutiva/high-risk e rollback manual por snapshot (→ Onda 6, novo fluxo de aprovação inline).

## v2 — chat-first integral + título obrigatório

### Onda 0 — Specs, ADRs e docs (concluída, commit `bf9395a`)

- [x] [P0] [any] Atualizar `specs/modeling-3d-fusion/spec.md` com novo fluxo chat-first integral.
- [x] [P0] [any] Atualizar `specs/modeling-3d-fusion/plan.md` com 6 ondas.
- [x] [P0] [any] Atualizar `specs/modeling-3d-fusion/tasks.md` (este arquivo).
- [x] [P0] [any] Atualizar `specs/modeling-3d-fusion/handoff.md`.
- [x] [P0] [any] Adicionar ADR-013 em `docs/decisions.md`: 3D chat-first sem painel; aprovação inline; fluxo único.
- [x] [P0] [any] Adicionar ADR-014 em `docs/decisions.md`: título de chat obrigatório; remoção da auto-titulação OpenAI.
- [x] [P0] [any] Atualizar `docs/3d-mcp-modeling.md` com state machine, novas tools e remoção do painel.
- [x] [P0] [any] Atualizar `docs/architecture.md` removendo referência ao módulo modeling como dashboard.
- [x] [P0] [any] Atualizar `docs/application-map.md` removendo painel 3D do painel direito.
- [x] [P0] [any] Revisar `docs/delivery-checklist.md` para refletir novo fluxo.

### Onda 1 — Backend: fundação refatorada (concluída)

Branch: `refactor/3d-backend-foundations`. Commits: `0546ff8` (1.1), `821b66a` (1.2), `89b1b21` (1.3), `0e1e78e` (1.4). 60 testes verdes em `tests/test_tool_registry.py + test_modeling_services_split.py + test_modeling_routes.py + test_planner_llm.py + test_alembic_migrations.py`.

- [x] [P1] [any] Criar `backend/app/modeling/tool_registry.py` como única fonte da allowlist (1.1).
- [x] [P1] [any] Migrar `planner.py`, `policy.py` e adapters para derivarem de `TOOL_REGISTRY` (1.1).
- [x] [P1] [any] Split do `ModelingService` em `planner_service.py`, `executor.py`, `snapshot_service.py`, `artifacts.py`, `printability.py`; `service.py` vira facade (1.3). `discovery.py` fica para a Onda 2 quando a state machine de chat 3D nascer.
- [x] [P1] [any] Adicionar `kind` (`primary`/`edit`) + `parent_plan_id` em `ModelingPlan` e `ModelingPlanCreate` (1.2).
- [x] [P1] [any] Adoção do Alembic confirmada com o dono. Migrações `001_initial_baseline` (espelha estado atual idempotente) e `004_modeling_plans_kind` (índices `idx_modeling_plans_kind` e `idx_modeling_plans_parent`) criadas (1.4). Migrações `002` e `003` ficam para a Onda 2.
- [x] [P1] [any] Atualizar `backend/tests/test_modeling_routes.py` e `test_planner_llm.py` para os novos serviços.
- [x] [P1] [any] Criar `backend/tests/test_tool_registry.py` (18), `test_modeling_services_split.py` (7) e `test_alembic_migrations.py` (4).

### Onda 2 — Backend: orquestração chat-first (concluída)

Branch: `refactor/3d-backend-chat-first`. Commits:
`f5269b7` (2.1+2.2), `0734f8d` (2.3), `46e718a` (2.4+2.5),
`24b3822` (2.6), `a181f32` (2.11), `b6998e9` (2.10), `aa4abd4` (2.9),
`f42f7eb` (2.7). 241 testes verdes em
`pytest tests/ --ignore=tests/test_postgres_store.py`.

- [x] [P1] [any] Adicionar campos `title NOT NULL`, `is_modeling_3d`, `modeling_software_preference`, `modeling_stage`, `modeling_plan_id` em `chats` (migrações `002` e `003` + campos em `ChatSession` / `ChatSessionCreate`).
- [x] [P1] [any] Implementar state machine `discovery → planning → approved → executing → editing` no domain do chat (pure functions em `chat_state.py` + orchestrator em `chat_orchestrator.py`).
- [x] [P1] [any] Substituir tool `3d.generate_plan` por `3d.ask_clarification`, `3d.propose_plan`, `3d.propose_edit_plan`, `3d.request_high_risk_approval`, `3d.analyze_attachment` (mapeadas para métodos do `ModelingChatOrchestrator`).
- [x] [P1] [any] Criar `backend/app/modeling/prompts/discovery_system.md` + helper `discovery_system_prompt()` com lru_cache.
- [x] [P1] [any] Implementar `ModelingAttachmentAnalyzer` (vision stub para imagens, Blender headless para mesh/blend, metadata-only para CAD STEP).
- [x] [P1] [any] Criar `POST /api/chat/sessions/{chat_id}/attachments/analyze`.
- [x] [P1] [any] Implementar mini-planos auto-aprovados em `editing`; reaprovação inline para high-risk (`ModelingChatOrchestrator.propose_edit_plan` retorna `EditPlanOutcome.requires_approval`).
- [x] [P1] [any] Remover `POST /api/3d/plans` e `POST /api/3d/steps/{id}/approve` + ajustar testes que dependiam delas.
- [x] [P1] [any] Validar `chat.title` obrigatório em `POST /api/chat/stream` (HTTP 422 quando ausente/default) via feature flag `settings.require_chat_title` (off por padrão para não quebrar frontend legado antes da Onda 5).
- [x] [P1] [any] Migração `002` com backfill `Sem título - YYYY-MM-DD` para chats existentes (idempotente, cobre títulos vazios e structurally missing).
- [x] [P1] [any] Remover serviço/endpoint de auto-titulação OpenAI (helpers `_openai_title_model` / `_maybe_generate_openai_title`, `gateway.generate_title` e implementação em `OpenAIProvider`).
- [x] [P1] [any] Criar `test_chat_modeling_state_machine.py` (18), `test_chat_orchestrator.py` (17), `test_discovery_system_prompt.py` (5), `test_attachment_analyzer.py` (22), `test_chat_attachment_analyze_endpoint.py` (5), `test_chat_title_required.py` (6).

### Onda 3 — Frontend: feature module 3D (em PR)

- [x] [P1] [devin] Criar `apps/web/src/features/modeling-3d/` com estrutura `api/`, `hooks/`, `components/`, `settings/`, `types.ts` e `store.ts`.
- [x] [P1] [devin] Migrar leituras/diagnóstico 3D de `apps/web/src/lib/api.ts` para o módulo, mantendo criação/execução de planos no chat-first backend.
- [x] [P1] [devin] Implementar `useModeling3dChat`, `useAttachmentAnalysis`, `useModeling3dDiagnostics`.
- [x] [P1] [devin] Remover `ModelingDashboard` e `ModelingStepCard` de `dashboard-sections.tsx`.
- [x] [P1] [devin] Remover view `"modeling"` de `App.tsx`.
- [x] [P1] [devin] Mover flags 3D para `features/modeling-3d/store.ts` e substituir flag global por `nextChatIs3D` não-persistente.
- [x] [P1] [devin] Atualizar `apps/web/src/types/api.ts` com `is_modeling_3d`, `modeling_stage`, `kind`, `parent_plan_id` e análise de anexos.
- [x] [P1] [devin] Implementar `ChatModeling3DBadge` em sidebar e header.
- [x] [P1] [devin] Implementar `EnableModeling3DDialog` no menu rápido.
- [x] [P1] [devin] Seção 3D em Configurações gerais para preferência de software do próximo chat MCP.
- [x] [P1] [devin] Remover seletor frontend de modo 3D; o chat envia sempre o fluxo fluido `safe_auto`.
- [x] [P1] [devin] `ModelingDiagnosticsModal` acessível pelo cabeçalho do chat 3D.

### Onda 4 — Frontend: cards de plano e fluxo de aprovação

- [ ] [P1] [any] Implementar `ModelingPlanCard` com prosa, etapas, badges de risco, banner high-risk, botões "Aprovar"/"Rejeitar" e campo opcional de motivo.
- [ ] [P1] [any] Implementar `ModelingEditCard` compacto.
- [ ] [P1] [any] Upload de anexos (imagens + STL/OBJ/STEP/3MF/BLEND) dispara `analyze_attachment`.
- [ ] [P1] [any] SSE handler para eventos de execução (progress, completion, error).
- [ ] [P1] [any] Indicação visual de `executing` no card.
- [ ] [P1] [any] Tratamento de erro com "tentar novamente" e "revisar plano".

### Onda 5 — Título obrigatório do chat

- [ ] [P1] [any] Frontend bloqueia input quando `chat.title` vazio; modal pede título no primeiro acesso.
- [ ] [P1] [any] Backend retorna 422 quando `chat.title` ausente em `POST /api/chat/stream`.
- [ ] [P1] [any] Remover serviço/endpoint de auto-titulação OpenAI; atualizar docs.
- [ ] [P1] [any] Confirmar migração `002_chats_title_not_null` aplicada.
- [ ] [P1] [any] Criar `test_chat_title_validation.py`.

### Onda 6 — QA, docs finais e handoff

- [ ] [P1] [any] Rodar `scripts/quality.ps1` para backend e frontend tocados.
- [ ] [P1] [any] E2E manual com Blender real: descoberta → plano → aprovação → execução → edição.
- [ ] [P1] [any] E2E manual com Fusion conectado: mesmo fluxo com `software_preference="fusion"`.
- [ ] [P1] [any] E2E manual de high-risk em edição: card retorna para aprovação inline.
- [ ] [P1] [any] E2E manual de anexos: imagem (vision) e STL (Blender headless) entram como contexto.
- [ ] [P1] [any] E2E manual de modal de chat separado em chat com histórico.
- [ ] [P1] [any] E2E manual de bloqueio de título obrigatório (front e back).
- [ ] [P1] [any] Atualizar `docs/3d-mcp-modeling.md` com diagramas finais.
- [ ] [P1] [any] Atualizar `docs/delivery-checklist.md` com checklist da refator.
- [ ] [P1] [any] Marcar tasks v2 concluídas e atualizar `handoff.md`.
