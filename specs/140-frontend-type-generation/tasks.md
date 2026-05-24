# Tarefas: Geração de tipos do frontend (ADR-016)

**Entrada**: `specs/140-frontend-type-generation/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md`/`plan.md`/`tasks.md` da frente de geração de tipos (formaliza ADR-016 / `090` DT-003)
- [ ] T002 [P1] [any] Adicionar `specs/140-...` ao catálogo de `specs/README.md` e referenciar a partir de `090` DT-003 (retro-fit; coordenar com PR #43 que edita o catálogo)

## Fase 2 — Execução (futuro; PRs próprios, após decisão do dono)

- [ ] T010 [P1] [any] Script de export do schema: `app.openapi()` → `apps/web/src/types/openapi.json` (regenerável, não manual)
- [ ] T011 [P1] [any] Adotar `openapi-typescript` (dev-dep) + comando `pnpm gen:types`
- [ ] T012 [P1] [any] `api.ts` deriva dos tipos gerados (modelos não-3D); corrigir drifts (Document/DocumentRecord, Prompt.agent_id, Agent.permission_policy/graph)
- [ ] T013 [P1] [any] Migrar call sites (`lib/api.ts` + features) e validar `typecheck` verde
- [ ] T014 [P2] [any] Gate de CI: regenerar e `git diff --exit-code` (falha em drift)
- [ ] T015 [P2] [any] Tipos `Modeling*`/3D após estabilização da frente `spec-005-v4` (inclui `fluid_mode`/`modeling_fluid_mode`)

## Notas

- Fase 2 só inicia após decisão do dono; cada item é PR pequeno e auditável.
- Ao iniciar a Fase 2, atualizar `specs/090-frontend-web-shell/` DT-003 e marcar ADR-016 como "em execução" em `docs/decisions.md`.
