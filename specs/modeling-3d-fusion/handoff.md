# handoff.md

## Estado

Refatoração v2 (chat-first integral + título obrigatório) em curso na branch
`refactor/3d-backend-foundations`.

| Onda | Status | Commit |
|---|---|---|
| 0 — Specs/docs/ADRs | concluída | `bf9395a` |
| 1.1 — Allowlist unificada (`tool_registry`) | concluída | `0546ff8` |
| 1.2 — Campo `kind`/`parent_plan_id` em `ModelingPlan` | concluída | `821b66a` |
| 1.3 — Split do `ModelingService` em 5 serviços | concluída | `89b1b21` |
| 1.4 — Alembic + migrações `001`/`004` | concluída | `0e1e78e` |
| 1.5 — Validação final | em curso (testes verdes; falta esse commit) | — |
| 2 — Backend orquestração chat-first | não iniciada | — |
| 3 — Frontend feature module 3D | não iniciada | — |
| 4 — Frontend cards/aprovação | não iniciada | — |
| 5 — Título obrigatório do chat | não iniciada | — |
| 6 — QA / docs finais | não iniciada | — |

Verificação backend ao fim da Onda 1: `pytest tests/` (excluindo
`tests/test_postgres_store.py` que requer `psycopg-binary`) = 166 testes
verdes localmente.

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

1. Abrir PR de `refactor/3d-backend-foundations` para `master` (Ondas 0+1)
   quando o dono aprovar.
2. Iniciar **Onda 2 — Backend chat-first orchestration**:
   - Migrações Alembic `002_chats_title_not_null` e `003_chats_modeling_fields`.
   - Campos do chat (`title NOT NULL`, `is_modeling_3d`,
     `modeling_software_preference`, `modeling_stage`, `modeling_plan_id`).
   - State machine no domain do chat.
   - Tools dedicadas (`3d.ask_clarification`, `3d.propose_plan`,
     `3d.propose_edit_plan`, `3d.request_high_risk_approval`,
     `3d.analyze_attachment`) substituindo `3d.generate_plan`.
   - System prompt `backend/app/modeling/prompts/discovery_system.md`.
   - `ModelingAttachmentAnalyzer` (vision + Blender headless).
   - Validação backend de `chat.title` em `POST /api/chat/stream`.
   - Backfill de título para chats existentes.
   - Remoção de `POST /api/3d/plans` e `POST /api/3d/steps/{id}/approve`.
3. Onda 3 só começa depois que Onda 2 estiver em main, para evitar
   conflitos no `App.tsx` (3.156 linhas) e em
   `dashboard-sections.tsx` (2.623 linhas).

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
