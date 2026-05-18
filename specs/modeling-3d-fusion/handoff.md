# handoff.md

## Estado

Refatoração v2 (chat-first integral + título obrigatório) em curso na branch
`refactor/3d-backend-foundations`.

| Onda | Status | Commit(s) |
|---|---|---|
| 0 — Specs/docs/ADRs | mergeado (PR #19) | `bf9395a` |
| 1.1 — Allowlist unificada (`tool_registry`) | mergeado | `0546ff8` |
| 1.2 — Campo `kind`/`parent_plan_id` em `ModelingPlan` | mergeado | `821b66a` |
| 1.3 — Split do `ModelingService` em 5 serviços | mergeado | `89b1b21` |
| 1.4 — Alembic + migrações `001`/`004` | mergeado | `0e1e78e` |
| 1.5 — Marcar Onda 1 em tasks/handoff | mergeado | `371eb0e` |
| 2.1+2.2 — Campos modeling/state em ChatSession + migrações `002`/`003` | em PR | `f5269b7` |
| 2.3 — State machine `chat_state.py` | em PR | `0734f8d` |
| 2.4+2.5 — `ModelingChatOrchestrator` + `discovery_system.md` | em PR | `46e718a` |
| 2.6 — `ModelingAttachmentAnalyzer` | em PR | `24b3822` |
| 2.11 — Remover `POST /api/3d/plans` + step approval | em PR | `a181f32` |
| 2.10 — Remover auto-titulação OpenAI | em PR | `b6998e9` |
| 2.9 — Gate de título obrigatório (feature flag) | em PR | `aa4abd4` |
| 2.7 — Endpoint `attachments/analyze` | em PR | `f42f7eb` |
| 2.8 — Mini-planos auto-aprovados em editing | coberto pelo orchestrator (`propose_edit_plan`) | — |
| 3 — Frontend feature module 3D | não iniciada | — |
| 4 — Frontend cards/aprovação | não iniciada | — |
| 5 — Título obrigatório do chat (frontend) | não iniciada | — |
| 6 — QA / docs finais | não iniciada | — |

Verificação backend ao fim da Onda 2:
`pytest tests/ --ignore=tests/test_postgres_store.py` = **241 verdes**
localmente. `alembic history` linear `001 → 002 → 003 → 004`.

## Decisões consolidadas com o dono do produto

### Módulo 3D

- **Fluxo único**: descoberta → plano apresentado no chat → aprovação por
  botões inline → execução → edições com mini-planos. Os três modos legados
  (`plan_only`/`approval_required`/`safe_auto`) são removidos.
- **Aprovação só via botões inline no card do chat**, não no painel. Resposta
  textual livre não aciona execução.
- **Aprovação global do plano cobre todas as etapas**, incluindo high-risk
  (`apply_boolean`, `repair_non_manifold`, `restore_snapshot`, `run_script`).
  Sem reaprovação step-a-step depois.
- **High-risk em edição posterior** abre nova aprovação inline; edição
  comum autoexecuta como mini-plano.
- **Flag `is_modeling_3d` por chat**, persistida e imutável após criação.
  Toggle global vira `nextChatIs3D` (apenas marca a intenção do próximo chat).
- **Ativar 3D em chat com histórico**: modal pergunta antes; confirma cria
  novo chat 3D vazio sem copiar mensagens.
- **Anexos com análise profunda**: imagens via vision (gateway LLM) e
  arquivos 3D (`STL`/`OBJ`/`STEP`/`3MF`/`BLEND`) via Blender headless —
  bounding box, mesh stats, simetria, features identificáveis, sugestões.
- **Painel 3D removido**. Config de adapters vai para Configurações gerais;
  diagnóstico vira modal acessível pelo cabeçalho do chat 3D.
- **Trigger discovery → planning**: decisão livre do LLM. A tool
  `3d.propose_plan` é o único gatilho formal.

### Título obrigatório (escopo não-3D acoplado)

- **Front e back validam**. Front bloqueia o input, back retorna 422 sem
  `chat.title`.
- **Migração backfill** aplica `"Sem título - YYYY-MM-DD"` (derivado de
  `created_at`) a chats existentes sem título.
- **Auto-titulação OpenAI removida** completamente (serviço + endpoint).

### Decisões herdadas (v1)

- Blender real e Fusion bridge são obrigatórios para a trilha 3D.
- Fusion tem contrato próprio dentro do bounded context.
- Fusion MCP Server local (porta padrão `27182`) é o caminho preferido;
  bridge legado em `apps/fusion-addin/` permanece como fallback.

## Próximos passos

1. Abrir PR de `refactor/3d-backend-chat-first` para `master` (Onda 2).
2. Ao mergear, flipar `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true` só depois
   que a Onda 5 (React) garantir que o frontend exige título antes de
   enviar a primeira mensagem. Backend já está pronto, mas a flag
   permanece off por default para não quebrar a UI legada.
3. Iniciar **Onda 3 — Frontend feature module 3D**:
   - Criar `apps/web/src/features/modeling-3d/`.
   - Migrar funções 3D de `apps/web/src/lib/api.ts`.
   - Hooks `useModeling3dChat`, `useAttachmentAnalysis`,
     `useModeling3dDiagnostics`.
   - Remover `ModelingDashboard` e `ModelingStepCard` do
     `dashboard-sections.tsx`.
   - Remover view `"modeling"` do `App.tsx`.
   - Mover flags 3D de `app/store.ts` para `features/modeling-3d/store.ts`.
   - Atualizar tipos em `types/api.ts` para refletir
     `is_modeling_3d`, `modeling_stage`, `kind`, `parent_plan_id` etc.
   - `ChatModeling3DBadge`, `EnableModeling3DDialog`,
     `ModelingDiagnosticsModal`, seção 3D em Configurações gerais.
4. Onda 4 (cards + fluxo de aprovação) e Onda 5 (título obrigatório
   no frontend) só começam depois que Onda 3 estiver em main, para
   evitar conflitos no `App.tsx` (3.156 linhas) e em
   `dashboard-sections.tsx` (2.623 linhas).

## Notas para a Onda 3 sobre o frontend

- O contrato de `POST /api/chat/stream` ganhou o campo opcional
  `title: str | None`. O React precisa começar a mandar esse campo a
  partir da Onda 5 — pode antecipar na Onda 3 como preparação.
- O endpoint para análise de anexos é
  `POST /api/chat/sessions/{chat_id}/attachments/analyze` com body
  `{file_id: str}`. Resposta:
  `ChatAttachmentAnalyzeResponse { file_id, filename, kind,
  ok, summary, metrics, suggestions, error, context_text }`.
- Os endpoints `POST /api/3d/plans` e
  `POST /api/3d/steps/{id}/approve` foram removidos. Qualquer chamada
  do frontend atual a essas rotas vai falhar com 405 — precisa
  trocar pelo fluxo do chat orchestrator (que ainda está sendo
  ligado ao stream handler na próxima sub-fase).

## Pontos abertos

- Estrutura final do system prompt de descoberta — definir em Onda 2 com
  exemplos few-shot para o trigger `propose_plan`.
- Limites finos de tamanho/timeout para análise profunda de 3D: proposta
  inicial é 50 MB / 15 s, ajustar conforme experimentos.
- Telemetria para auditar quando o LLM propõe plano com descoberta
  insuficiente — instrumentar mas não bloquear na Onda 2.

## Referências

- Plano de execução: `C:\Users\Jonatan\.claude\plans\gostaria-de-planejar-uma-lovely-ember.md`
- Spec viva: `specs/modeling-3d-fusion/spec.md`
- Plano técnico: `specs/modeling-3d-fusion/plan.md`
- Tasks: `specs/modeling-3d-fusion/tasks.md`
- ADRs: `docs/decisions.md` (ADR-012, ADR-013, ADR-014)
- Documentação operacional: `docs/3d-mcp-modeling.md`
