# plan.md

## Sequência (v2 chat-first integral)

A refatoração segue 6 ondas pequenas, cada uma com PR próprio, testes verdes e
docs atualizadas. Ondas posteriores assumem que as anteriores estão em main.

### Onda 0 — Specs, ADRs e docs (sem código de produção)

- Atualizar `specs/005-modeling-3d-fusion/spec.md`, `plan.md`, `tasks.md`, `handoff.md`.
- Criar ADR-013 (3D chat-first sem painel) e ADR-014 (título obrigatório) em
  `docs/decisions.md`.
- Atualizar `docs/3d-mcp-modeling.md` com state machine, novas tools, fluxo único,
  remoção do painel.
- Atualizar `docs/architecture.md` e `docs/application-map.md` para refletir
  remoção do painel 3D do dashboard.
- Revisar `docs/delivery-checklist.md`.

### Onda 1 — Backend: fundação refatorada

1. Criar `backend/app/modeling/tool_registry.py` como única fonte da allowlist.
2. Migrar `planner.py`, `policy.py` e adapters para derivarem de `TOOL_REGISTRY`.
3. Split do `ModelingService` em `discovery.py`, `planner_service.py`, `executor.py`,
   `snapshot_service.py`, `artifacts.py`. `service.py` vira facade fina.
4. Adicionar campo `kind` (`primary`/`edit`) em `ModelingPlan` contratos.
5. Adotar Alembic (após confirmação do dono) e criar migrações `001_initial_baseline`
   e `004_modeling_plans_kind`. Plano B: `schema_version` inline.
6. Atualizar testes existentes; adicionar `test_tool_registry.py` e
   `test_modeling_services_split.py`.

### Onda 2 — Backend: orquestração chat-first

1. Adicionar campos a `chats`: `title NOT NULL`, `is_modeling_3d`,
   `modeling_software_preference`, `modeling_stage`, `modeling_plan_id`
   (migrações `002` e `003`).
2. Implementar state machine de chat 3D no domain.
3. Substituir tool `3d.generate_plan` por `3d.ask_clarification`,
   `3d.propose_plan`, `3d.propose_edit_plan`, `3d.request_high_risk_approval`,
   `3d.analyze_attachment`.
4. Criar prompt sistema dedicado em `backend/app/modeling/prompts/discovery_system.md`.
5. Implementar `ModelingAttachmentAnalyzer` (vision via gateway LLM + Blender headless).
6. Endpoint `POST /api/chat/{id}/attachments/analyze`.
7. Lógica de mini-planos auto-aprovados em fase `editing`.
8. Remover endpoints `POST /api/3d/plans` e `POST /api/3d/steps/{id}/approve`.
9. Validar `chat.title` obrigatório em `POST /api/chat/stream`.
10. Migração de backfill de título e remoção do serviço/endpoint de auto-titulação.
11. Novos testes: `test_chat_modeling_state_machine.py`, `test_attachment_analyzer.py`,
    `test_mini_plan_auto_approval.py`, `test_chat_title_required.py`.

### Onda 3 — Frontend: feature module 3D

1. Criar `apps/web/src/features/modeling-3d/` com `api/`, `hooks/`, `components/`,
   `settings/`, `types.ts`.
2. Migrar funções 3D de `apps/web/src/lib/api.ts` para o módulo.
3. Criar `useModeling3dChat`, `useAttachmentAnalysis`, `useModeling3dDiagnostics`.
4. Remover `ModelingDashboard` e `ModelingStepCard` de
   `apps/web/src/features/dashboard/dashboard-sections.tsx`.
5. Remover view `"modeling"` de `apps/web/src/App.tsx`.
6. Mover flags 3D de `apps/web/src/app/store.ts` para `features/modeling-3d/store.ts`
   e substituir flag global por `nextChatIs3D` não-persistente.
7. Atualizar tipos em `apps/web/src/types/api.ts`.
8. `ChatModeling3DBadge` na sidebar e header; `EnableModeling3DDialog` no menu rápido;
   seção 3D em Configurações gerais; `ModelingDiagnosticsModal` no header do chat.

### Onda 4 — Frontend: cards de plano e fluxo de aprovação

1. `ModelingPlanCard` com prosa, etapas, badges de risco, banner high-risk e
   botões "Aprovar"/"Rejeitar" (com campo opcional de motivo).
2. `ModelingEditCard` compacto para mini-planos executados.
3. Upload de anexos no chat 3D dispara `analyze_attachment` (imagens + STL/OBJ/STEP/3MF/BLEND).
4. SSE handler para eventos de execução (progress, completion, error).
5. Estado `executing` com indicação visual no card.
6. Tratamento de erro com "tentar novamente" e "revisar plano".

### Onda 5 — Título obrigatório do chat

1. Frontend bloqueia input se `chat.title` vazio; modal pede título no primeiro acesso.
2. Backend retorna 422 quando `chat.title` ausente.
3. Remoção do serviço/endpoint de auto-titulação OpenAI; documentar na ADR-014.
4. Confirmação da migração `002_chats_title_not_null`.
5. Novo teste `test_chat_title_validation.py`.

### Onda 6 — QA, docs finais e handoff

1. `scripts/quality.ps1` para backend e frontend tocados.
2. E2E manual com Blender real (resolve task pendente da v1).
3. E2E manual com Fusion conectado (resolve task pendente da v1).
4. E2E manual de high-risk no fluxo novo (resolve task pendente da v1).
5. Diagramas finais em `docs/3d-mcp-modeling.md`.
6. Atualização de `docs/delivery-checklist.md`.
7. Marcar tasks v2 concluídas; handoff final.

## Validação

- Testes unitários backend e frontend por onda.
- Verificação E2E com Blender real (workflow completo descoberta → plano → execução → edição).
- Verificação E2E com Fusion conectado (mesmo fluxo, software preference).
- Verificação E2E de modal de chat separado (3D em chat com histórico).
- Verificação de bloqueio de título obrigatório (front e back).
- Verificação de análise profunda de arquivos 3D anexados.
- Verificação de mini-planos auto-aprovados e fluxo de high-risk em edição.
