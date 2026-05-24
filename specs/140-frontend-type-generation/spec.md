# Especificação: Geração de tipos do frontend a partir do OpenAPI (ADR-016)

**Pasta da spec**: `specs/140-frontend-type-generation/` | **Criada em**: 2026-05-24 | **Status**: Rascunho

**Entrada**: Resolver a dívida **ADR-016** / `specs/090-frontend-web-shell` DT-003: `apps/web/src/types/api.ts` (740 linhas) é mantido **à mão** e diverge de `backend/app/core/contracts.py`, enquanto `apps/web/src/types/openapi.json` existe mas está defasado e não é usado. Esta spec formaliza a adoção de uma toolchain que gera os tipos do contrato OpenAPI, eliminando o drift.

> Idioma: PT-BR (nomes/comandos em inglês). ADR de referência: **ADR-016** (`docs/decisions.md`).

## Cenários de usuário e testes

### História 1 — Tipos do frontend derivam do contrato do backend (Prioridade: P1)

Como dev, quando o contrato do backend (rotas/Pydantic) muda, os tipos do `apps/web` refletem a mudança sem edição manual, evitando payloads/leituras incorretos.

**Teste independente**: regenerar `openapi.json` a partir do FastAPI e os tipos do `api.ts`; o `typecheck` do web aponta qualquer consumo incompatível.

**Cenários de aceitação**:

1. **Dado** o app FastAPI, **Quando** rodo o script de geração, **Então** `openapi.json` é regenerado a partir de `app.main:app` (não um snapshot manual).
2. **Dado** o `openapi.json` atual, **Quando** rodo a geração de tipos, **Então** os tipos do frontend refletem os modelos atuais (ex.: `Document`, `Prompt.agent_id`, `Agent.permission_policy`).
3. **Dado** um drift introduzido, **Quando** roda o gate de CI, **Então** a divergência entre tipos gerados e committados falha o check.

### História 2 — Migração incremental sem quebrar o app (Prioridade: P2)

A substituição do `api.ts` manual pelos tipos gerados acontece sem regressão de comportamento; `lib/api.ts` e as features consomem os novos tipos.

### Casos de borda

- Tipos 3D em redesign pela frente `spec-005-v4`: gerar os tipos `Modeling*` só após o contrato 3D estabilizar, ou isolá-los, para não gerar contra um contrato em movimento.
- Campos só-leitura/sempre-serializados (BE) vs opcionais no FE — a geração deve refletir `required` do schema.

## Requisitos

### Requisitos funcionais

- **RF-001**: O SISTEMA DEVE gerar `apps/web/src/types/openapi.json` a partir do app FastAPI (`app.main:app`), via script versionado (não snapshot manual).
- **RF-002**: O SISTEMA DEVE gerar os tipos TypeScript do frontend a partir do `openapi.json` (ex.: `openapi-typescript`), substituindo o `api.ts` mantido à mão.
- **RF-003**: O SISTEMA DEVE oferecer um comando (`pnpm`) que regenera schema+tipos e um gate que falha quando os tipos committados divergem do contrato.
- **RF-004**: QUANDO a geração substituir tipos consumidos, O SISTEMA DEVE preservar o comportamento atual, ajustando os call sites no mesmo conjunto de mudanças.

### Requisitos não funcionais

- **RNF-001**: A adoção é **aditiva** (dev-dep de geração); não troca a stack (P2). PRs pequenos e auditáveis.
- **RNF-002**: Local-first; a geração roda offline contra o backend local/empacotado.

## Critérios de sucesso

- **CS-001**: `apps/web/src/types/api.ts` deixa de ser mantido à mão (gerado, ou fino sobre o gerado).
- **CS-002**: Zero divergências conhecidas entre os tipos do frontend e `contracts.py` para os modelos de alto tráfego (chat/config/files/knowledge-bases/cost/agents/prompts/projects).
- **CS-003**: `pnpm --filter @truths-forge/web typecheck` verde após a migração; gate de drift no CI.

## Premissas

- ADR-016 já decidiu a direção (gerar tipos); esta spec cobre o "o quê/por quê" da execução em PR próprio.
- O contrato 3D pode estar em movimento (`spec-005-v4`); a ordem de execução considera isso.

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Decisão: `docs/decisions.md` (ADR-016)
- Dívida de origem: `specs/090-frontend-web-shell/` DT-003
- Código: `apps/web/src/types/api.ts`, `apps/web/src/types/openapi.json`, `apps/web/src/lib/api.ts`, `backend/app/core/contracts.py`, `backend/app/main.py`
- Specs relacionadas: `specs/090-frontend-web-shell/`, `specs/010-chat-orchestration/`

## Drift documentado *(motivação; verificado em 2026-05-24, não executar aqui)*

- **DT-001**: `DocumentRecord` (FE) ≠ `Document` (BE): `index_status` string vs enum; faltam `original_path`/`storage_path`. Esforço: S.
- **DT-002**: `Prompt` (FE) sem `agent_id`; `Agent` (FE) sem `permission_policy`/`graph`/timestamps. Esforço: S.
- **DT-003**: `openapi.json` committado está **defasado** (predata 3D e filtros de `DocumentSearchRequest`). Esforço: S.
- **DT-004**: Tipos 3D (`ChatModeling3DContext.fluid_mode`, `ChatSession.modeling_fluid_mode`) — coordenar com `spec-005-v4`. Esforço: M.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Critérios de sucesso mensuráveis
- [x] Escopo delimitado; dependência do contrato 3D registrada
