# handoff.md

## Estado

Refatoração v2 (chat-first integral + título obrigatório) em curso. **Onda 4
em PR** na branch `refactor/3d-frontend-chat-cards`.

| Onda | Status | Commit(s) |
|---|---|---|
| 0 — Specs/docs/ADRs | mergeado (PR #19) | `bf9395a` |
| 1 — Backend foundations | mergeado (PR #19) | `0546ff8` → `371eb0e` |
| 2 — Backend chat-first orchestration | mergeado (PR #20) | `f5269b7` → `c3cb10c` |
| 3 — Frontend feature module 3D | mergeado (PR #21, #22, #24) | `a94a273` + fixes |
| 4.1+4.2 — `ModelingPlanCard` + `ModelingEditCard` + `useModelingPlanActions` | em PR | `cf42144` |
| 4 integration — wire approve/reject/retry/revise no App.tsx | em PR | `ffb6f73` |
| 4.3 — Auto-analyze de anexos em chats 3D | em PR | `92218dd` |
| 5 — Título obrigatório do chat (frontend) | não iniciada | — |
| 6 — QA / docs finais | não iniciada | — |

Verificação ao fim da Onda 4:
- `pytest tests/ --ignore=tests/test_postgres_store.py` = **243 verdes**
  (backend regredido vs Onda 2 só em count porque Onda 3 trouxe 2 testes
  novos do orchestrator chat-first sync).
- `pnpm test:unit` = **60 verdes** em 11 arquivos (16 novos da Onda 4
  para PlanCard + EditCard).
- `pnpm typecheck` limpo.
- `alembic history` linear `001 → 002 → 003 → 004`.

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

1. Abrir PR de `refactor/3d-frontend-chat-cards` para `master` (Onda 4).
2. Ao mergear, agendar o flip `TRUTHS_FORGE_REQUIRE_CHAT_TITLE=true` para
   logo após a Onda 5 (frontend) garantir que o modal de título obrigatório
   está plugado antes do primeiro envio.
3. Iniciar **Onda 5 — Título obrigatório do chat (frontend)**:
   - Modal "Dê um título para esse chat" antes da primeira mensagem.
   - `ChatStreamRequest.title` agora opcional no contrato; o cliente
     React deve passar a sempre enviar `title` quando criar sessão.
   - Tratar 422 `{error: "chat_title_required"}` com mensagem clara.
4. Onda 6 (QA + docs finais) só começa quando 5 estiver mergeada.

### Pendências carryover para 5/6

- **SSE handler dedicado para execução**: backend ainda não emite
  `modeling_execution_*` events no stream; quando emitir, substituir a
  atualização otimista do `applyPlanToSession` por reação aos eventos.
- **Wire orchestrator chat-first ao stream handler do backend**: hoje
  `POST /api/chat/stream` ainda cria plano via tool legada
  `3d.generate_plan` (Onda 3 manteve compat). As 5 tools dedicadas
  (`3d.propose_plan`, `3d.propose_edit_plan`, etc.) existem no
  `ModelingChatOrchestrator` mas o stream handler precisa ser ligado a
  elas. Sub-fase pendente para a Onda 6 ou um PR dedicado entre 5 e 6.

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
