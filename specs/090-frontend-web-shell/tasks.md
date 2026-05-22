# Tarefas: Frontend Web (shell)

**Entrada**: `specs/090-frontend-web-shell/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` do shell web
- [x] T002 [P0] [claude-code] Registrar dívida DT-001..004 (App.tsx, api.ts, tipos, estado)

## Fase 2 — Dívida de código (futuro; não executar nesta frente)

- [ ] T010 [P2] [any] Decompor `apps/web/src/App.tsx` por feature/hooks, espelhando `features/modeling-3d/` (DT-001)
- [ ] T011 [P2] [any] Dividir `apps/web/src/lib/api.ts` por domínio (DT-002)
- [ ] T012 [P2] [human] Avaliar ADR + adotar geração de tipos do OpenAPI (`openapi-typescript`) (DT-003)
- [ ] T013 [P2] [any] Consolidar estado (React Query por entidade) e remover fetch monolítico (DT-004)

## Notas

- Fase 2 só inicia após decisão do dono; DT-003 exige ADR (mudança de toolchain). Preservar UX dark/densa/mobile-first.
