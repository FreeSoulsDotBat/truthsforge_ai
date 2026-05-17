# handoff.md

## Estado

Refatoração v2 (chat-first integral + título obrigatório) está em curso. A
**Onda 0** (specs/docs/ADRs) está sendo aplicada nesta sessão. Implementação
de código (Ondas 1–6) ainda não começou.

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

1. Finalizar Onda 0 (este checkpoint): atualizar `docs/decisions.md` com
   ADR-013 e ADR-014, `docs/3d-mcp-modeling.md` com state machine e novo
   conjunto de tools, `docs/architecture.md` e `docs/application-map.md` para
   refletir remoção do painel 3D.
2. Confirmar com o dono o nome de branch e mensagem de commit semântico
   antes de iniciar Onda 1.
3. Confirmar com o dono a adoção do Alembic para migrações versionadas.
   Plano B aceito: manter `init_schema()` com `schema_version` interno.
4. Executar Onda 1 (backend: fundação) em PR separado.

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
