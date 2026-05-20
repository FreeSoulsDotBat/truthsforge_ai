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

### Onda 4 — Frontend: cards de plano e fluxo de aprovação (em PR)

Branch: `refactor/3d-frontend-chat-cards`. Commits:
`cf42144` (4.1+4.2 ModelingPlanCard + ModelingEditCard + hook
`useModelingPlanActions`), `ffb6f73` (integração no App.tsx via
`modelingPlanActions` prop + state sync), `92218dd` (4.3 auto-analyze
de anexos em chats 3D).

Verificação ao fim da Onda 4:
`pnpm test:unit` = **60 verdes** em 11 arquivos (16 novos para
PlanCard + EditCard), `pnpm typecheck` limpo,
`pytest tests/ --ignore=tests/test_postgres_store.py` = **243 verdes**.

- [x] [P1] [any] Implementar `ModelingPlanCard` com prosa, etapas, badges de risco, banner high-risk, botões "Aprovar"/"Rejeitar" e campo de motivo obrigatório na rejeição (em `features/modeling-3d/components/`).
- [x] [P1] [any] Implementar `ModelingEditCard` compacto para mini-planos auto-aprovados (`kind=edit`).
- [x] [P1] [any] Upload de anexos (imagens + STL/OBJ/STEP/3MF/BLEND) em chats 3D dispara `analyze_attachment` em background após o stream e injeta o `context_text` como nota local assistant.
- [x] [P1] [any] Hook `useModelingPlanActions` encapsula approve+execute, reject, retry e revise sobre `modeling3dApi`; mantém estado `busy/error/lastPlan/lastExecution`.
- [x] [P1] [any] Indicação visual de `executing` no card (spinner + cópia clara) e blocos para `completed`, `failed` e `rejected`.
- [x] [P1] [any] Tratamento de erro com "Tentar novamente" e "Revisar plano" inline em estado `failed`.
- [ ] [P1] [Onda 5/6] SSE handler dedicado para `modeling_execution_progress`/`completion`/`failure` — esperando o orchestrator backend emitir os eventos no stream. Até lá, o card é atualizado pela resposta direta de `approve+execute` via `applyPlanToSession` no App.tsx.

### Onda 5 — Título obrigatório do chat (frontend) — concluída localmente

Backend já está totalmente preparado desde Onda 2 (rotas, validação 422,
remoção de auto-titulação OpenAI, migração 002 com backfill). A Onda 5
entregou o frontend, o flip da feature flag e um ajuste de persistência
para rascunhos `Novo chat` já criados antes do primeiro envio.

**Sub-etapas concretas** (ver `handoff.md` para guia step-by-step):

- [x] [P1] [any] **5.1** Criar `apps/web/src/features/chat/components/ChatTitleRequiredDialog.tsx`: modal acessível (`role="dialog"`), input com `min_length=1`, autofocus, ESC cancela, Enter confirma. Confirma desabilita com título vazio/whitespace ou em `DEFAULT_CHAT_TITLES`. Copy explicando economia de tokens.
- [x] [P1] [any] **5.1.test** `ChatTitleRequiredDialog.test.tsx` (Vitest + Testing Library): open/close, validation, ESC, Enter, busy state.
- [x] [P1] [any] **5.2** Criar `apps/web/src/features/chat/hooks/useChatTitleGate.ts` que decide quando `needsTitle === true` (sessão nova, título vazio, ou em DEFAULT_CHAT_TITLES) e expõe `openTitleDialog`.
- [x] [P1] [any] **5.3** Wire no `App.tsx`: antes de `streamChat`, checar `gate.needsTitle`; se sim, abrir modal, aguardar `onConfirm`, atualizar `session.title` localmente, e passar `title` no payload. Em `onError` do streamChat, abrir o mesmo modal quando reason `chat_title_required`.
- [x] [P1] [any] **5.4** Em `apps/web/src/lib/api.ts`, garantir que o `streamChat.onError` é chamado com `reason: "chat_title_required"` quando o backend devolve HTTP 422 com esse `detail.error`.
- [x] [P1] [any] **5.5** Flag flip: `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true` em `infra/docker-compose.dev.yml` e `infra/.env.example`.
- [x] [P1] [any] **5.6** Smoke test manual: criar chat novo → modal aparece → confirma → mensagem sobe sem 422. Chats antigos (com título da migração 002) continuam funcionando sem modal.
- [x] [P1] [any] **5.7** Atualizar `docs/application-map.md` (fluxo de criação de chat com título obrigatório) e `README.md` (remover qualquer menção a auto-titulação).
- [x] [P1] [any] **5.8** Atualizar `specs/modeling-3d-fusion/tasks.md` (este arquivo) e `handoff.md` marcando Onda 5 como concluída localmente.

**Contratos backend já implementados (não precisam mexer):**

- `ChatStreamRequest.title: str | None = None` (Onda 2.9)
- `POST /api/chat/stream` retorna `HTTP 422` com `detail={"error": "chat_title_required", "message": "..."}` quando flag ativa e título inválido (Onda 2.9)
- Migração `002_chats_title_not_null` backfill `Sem título - YYYY-MM-DD` (Onda 2.2)
- Auto-titulação OpenAI removida (helpers + gateway method + provider) (Onda 2.10)
- Testes backend: `test_chat_title_required.py` (Onda 2.9 + Onda 5, 8 testes)

### Onda 6 — QA, docs finais e handoff

- [x] [P1] [any] Corrigir fallback heurístico Fusion para variar perfil e medidas pelo prompt (`add_rectangle` para bases/placas, `add_circle` para cilindros/discos) sem sair da allowlist.
- [x] [P1] [any] PR #27 review: deduplicar `FUSION_HINTS`/`BLENDER_HINTS` após `_normalize_prompt` (NFKD + strip diacríticos). Manter só forma canônica + asserção defensiva no import + 3 testes de regressão em `test_planner_llm.py`.
- [x] [P1] [codex] Hardening PR #28 da observabilidade 3D: snapshots de payload em `record_span`, eviction de buffers sem I/O sob `_buffers_lock`, cleanup do rate-limit de eventos UI e `get_max_trace_sequence` em `DevStore`/`PostgresStore` para evitar listagem completa de traces.
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

### Onda 8 — Expansão do adapter Fusion (MVP de operações)

Spec completa: `specs/modeling-3d-fusion/adapter-tools-mvp.md`. Cada onda
abaixo é um PR. Pré-requisito comum: atualizar o system prompt do planner
para exigir geometria explícita antes de extrude/revolve (vai junto com A).

- [x] [P0] [any] Aprovar a spec `adapter-tools-mvp.md` com o dono do produto.
- [x] [P1] [any] **Onda A**: `add_polygon`, `add_line`, `add_arc`, `revolve_profile` + fix do prompt do planner (create_sketch é vazio; proibir geometria em `notes`). Destrava esferas e polígonos. Branch `feat/fusion-revolve-polygon`. Inclui quick fixes de schema drift. Falta validação manual com Fusion real.
- [x] [P1] [any] **Onda C**: `fillet_edges`, `chamfer_edges`, `shell_body`, `hole` + selectors semânticos de edge/face (all/top/bottom/vertical/horizontal; open_faces top/bottom/none). Honra hints órfãos `fillet`/`chamfer`. Branch `feat/fusion-features-onda-c`. `hole` é MVP pragmático (cut na face superior, não holeFeatures). Falta validação manual com Fusion real — selectors e hole são os pontos mais prováveis de iterar.
- [x] [P2] [any] **Onda B**: primitivas diretas `add_box`, `add_cylinder`, `add_sphere`, `add_cone` (paramétricas via sketch+feature interno, não TemporaryBRep). Branch `feat/fusion-primitives-onda-b`. Falta validação manual com Fusion real.
- [x] [P2] [any] **Onda D**: `pattern_rectangular`, `pattern_circular`, `mirror_feature`, `combine_bodies` (combine = high_risk, aprovação obrigatória). Branch `feat/fusion-onda-def`. Patterns operam sobre bodies (não features) via `_find_body`.
- [x] [P3] [any] **Onda E**: `loft_profiles`, `sweep_profile`, `add_construction_plane` (offset), `add_spline`. Branch `feat/fusion-onda-def`.
- [x] [P3] [any] **Onda F**: `move_body` (translação), `scale_body` (uniforme), `delete_body` (delete = destructive, aprovação obrigatória). Branch `feat/fusion-onda-def`. Falta validação manual de todas as ondas D-F com Fusion real (APIs de pattern/loft/sweep/move variam por versão).
- [x] [P1] [any] Quick fixes de schema drift (independem das ondas): `add_circle` aceitar alias `circle_diameter_mm`/`radius_mm`/`center_mm`; `extrude_profile` mapear `operation` desconhecida para `new_body` com warning no message. (entregue junto da Onda A)

### Onda 9 — Cobertura dos gaps pós-MVP

Spec completa: `specs/modeling-3d-fusion/adapter-gaps-roadmap.md`. Fases
priorizadas por valor/custo. Aguardando priorização do dono do produto.

- [x] [P0] [any] **G1.1** — parametrização de distâncias de feature: helper `_param_value_input` (createByString quando arg é nome de parâmetro existente → vínculo; createByReal quando número). Aplicado em extrude/fillet/chamfer/shell. Branch `feat/fusion-gaps-g1-g2-g5`. (revolve angle e primitivas ficam para quando G1.2 amarrar sketch dims; hole depth bakeado por causa da negação.)
- [x] [P1] [any] **G5** — fallback `createInput2`/`createInput` por versão em chamfer e move (APIs deprecadas). Branch `feat/fusion-gaps-g1-g2-g5`. Validação real contínua conforme testes do usuário.
- [x] [P1] [any] **G2.1** — selectors finos: arestas `longest`/`shortest`; faces `planar`/`cylindrical`/`largest`/`+x..-z` (orientação da normal), além de top/bottom. Branch `feat/fusion-gaps-g1-g2-g5`. (posição `near=[x,y,z]` fica para G2.2 junto com query_geometry.)
- [ ] [P1] [any] **G2.2** — tool read-only `fusion.query_geometry` (lista faces/arestas/bodies com id estável) + fluxo query→select no prompt.
- [ ] [P2] [any] **G1.2** — dimensões de sketch amarradas a parâmetros (add_rectangle/add_circle primeiro).
- [ ] [P2] [any] **G2.3** — referência estável a features (`result_name` + `feature_ref` em pattern/mirror). Resolve drift de identidade.
- [ ] [P2] [any] **G3** — gaps de features sob demanda: hole v2 (counterbore/countersink/tapped), ellipse/slot, draft, rib, thicken, split_body, fillet variável, chamfer 2-distâncias, plano por ângulo/3-pontos, rotação em move_body, texto.
- [ ] [P3] [any] **G4** (epic) — assemblies/componentes/joints/materiais. Decidir escopo com o dono antes de specar em detalhe.
