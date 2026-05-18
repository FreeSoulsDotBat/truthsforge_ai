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

### Onda 2 — Backend: orquestração chat-first

- [ ] [P1] [any] Adicionar campos `title NOT NULL`, `is_modeling_3d`, `modeling_software_preference`, `modeling_stage`, `modeling_plan_id` em `chats` (migrações `002` e `003`).
- [ ] [P1] [any] Implementar state machine `discovery → planning → approved → executing → editing` no domain do chat.
- [ ] [P1] [any] Substituir tool `3d.generate_plan` por `3d.ask_clarification`, `3d.propose_plan`, `3d.propose_edit_plan`, `3d.request_high_risk_approval`, `3d.analyze_attachment`.
- [ ] [P1] [any] Criar `backend/app/modeling/prompts/discovery_system.md`.
- [ ] [P1] [any] Implementar `ModelingAttachmentAnalyzer` (vision + Blender headless com análise profunda).
- [ ] [P1] [any] Criar `POST /api/chat/{id}/attachments/analyze`.
- [ ] [P1] [any] Implementar mini-planos auto-aprovados em `editing`; reaprovação inline para high-risk.
- [ ] [P1] [any] Remover `POST /api/3d/plans` e `POST /api/3d/steps/{id}/approve`.
- [ ] [P1] [any] Validar `chat.title` obrigatório em `POST /api/chat/stream` (422 quando ausente).
- [ ] [P1] [any] Migração `002` com backfill `Sem título - YYYY-MM-DD` para chats existentes.
- [ ] [P1] [any] Remover serviço/endpoint de auto-titulação OpenAI.
- [ ] [P1] [any] Criar `test_chat_modeling_state_machine.py`, `test_attachment_analyzer.py`, `test_mini_plan_auto_approval.py`, `test_chat_title_required.py`.

### Onda 3 — Frontend: feature module 3D

- [ ] [P1] [any] Criar `apps/web/src/features/modeling-3d/` com estrutura `api/`, `hooks/`, `components/`, `settings/`, `types.ts`.
- [ ] [P1] [any] Migrar funções 3D de `apps/web/src/lib/api.ts` para o módulo.
- [ ] [P1] [any] Implementar `useModeling3dChat`, `useAttachmentAnalysis`, `useModeling3dDiagnostics`.
- [ ] [P1] [any] Remover `ModelingDashboard` e `ModelingStepCard` de `dashboard-sections.tsx`.
- [ ] [P1] [any] Remover view `"modeling"` de `App.tsx`.
- [ ] [P1] [any] Mover flags 3D para `features/modeling-3d/store.ts` e substituir flag global por `nextChatIs3D` não-persistente.
- [ ] [P1] [any] Atualizar `apps/web/src/types/api.ts` com `is_modeling_3d`, `modeling_stage` etc.
- [ ] [P1] [any] Implementar `ChatModeling3DBadge` em sidebar e header.
- [ ] [P1] [any] Implementar `EnableModeling3DDialog` no menu rápido (modal para criar chat 3D separado).
- [ ] [P1] [any] Seção 3D em Configurações gerais (Blender path, Fusion URL, status de adapters).
- [ ] [P1] [any] `ModelingDiagnosticsModal` acessível pelo cabeçalho do chat 3D.

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
