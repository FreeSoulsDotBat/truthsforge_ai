# plan.md — Geração de tipos do frontend (ADR-016)

## Constitution Check

- **P1 (local-first)**: a geração roda offline contra o backend local/empacotado. OK.
- **P2 (stack inalterada)**: a toolchain de tipos é **aditiva** (dev-dep `openapi-typescript`); não troca React/Vite/TS nem FastAPI. OK.
- **P4 (docs+specs juntos)**: esta spec + ADR-016 cobrem a decisão; atualizar `090` DT-003 quando concluído. OK.
- **P9 (PT-BR)**: artefatos em PT-BR; nomes de ferramentas em inglês. OK.
- Sem violação. Frente liberada para detalhamento.

## Abordagem técnica

1. **Schema**: script que importa `app.main:app` e exporta `app.openapi()` para `apps/web/src/types/openapi.json` (substitui o snapshot manual defasado).
2. **Tipos**: `openapi-typescript` gera `apps/web/src/types/openapi.gen.ts`; `api.ts` passa a derivar/re-exportar desses tipos (ou é substituído).
3. **Call sites**: ajustar `lib/api.ts` e as features para os tipos gerados; corrigir os drifts conhecidos (Document, Prompt.agent_id, Agent, ...).
4. **Gate**: comando `pnpm gen:types` + check de CI que regenera e roda `git diff --exit-code` (falha em drift).
5. **3D**: gerar os tipos `Modeling*` após o contrato `spec-005-v4` estabilizar, ou isolá-los para evitar churn.

## Riscos / trade-offs

- `openapi-typescript` produz tipos verbosos → mitigar com aliases finos.
- A regeneração exige o backend importável no CI (já há venv/deps).
- Contrato 3D em movimento → sequenciar após estabilização.

## Sequência (PRs pequenos)

- **PR1**: script de schema + `openapi.json` regenerado (sem trocar `api.ts`).
- **PR2**: geração de tipos + `api.ts` derivado dos gerados (modelos não-3D).
- **PR3**: migração de call sites + correção dos drifts; gate de CI.
- **PR4**: tipos 3D (após `spec-005-v4`).
