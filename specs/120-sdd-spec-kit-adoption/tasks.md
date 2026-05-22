# Tarefas: Adoção do GitHub Spec Kit

**Entrada**: `specs/120-sdd-spec-kit-adoption/spec.md` + `plan.md`.

## Fase 1 — Estrutura e cobertura (concluída)

- [x] T001 [P0] [claude-code] Onda 0: `.specify/` (constituição, 7 templates, scripts ps/bash) + `.claude/skills/speckit-*` (9 fases) + ponteiros aditivos
- [x] T002 [P0] [claude-code] Ondas O1–O10: specs `010`–`100` por domínio; 4 migradas para `specs/_legacy/`
- [x] T003 [P0] [claude-code] Retro-fit: renomear `000`/`005`/`110` e atualizar todas as referências
- [x] T004 [P0] [claude-code] Auditoria de referências: zero slug antigo fora de `_legacy/` (inclusive sem barra final)
- [x] T005 [P1] [human] Ratificar ADR-015 (storage) e ADR-016 (tipos OpenAPI) em `docs/decisions.md`
- [x] T006 [P1] [claude-code] Fase 2 fase-1: teste de paridade de storage (`backend/tests/test_store_parity.py`), validado no container
- [x] T007 [P1] [claude-code] Descoberta: apontar `README.md`, `docs/application-map.md` e skill `repo-map` para a constituição/Spec Kit

## Fase 2 — Execução da dívida (futuro; PRs próprios, validados pelo gate)

- [ ] T010 [P1] [any] Extrair `Protocol Store` (spec `070`, T011)
- [ ] T011 [P2] [any] Fatiar storage em repositórios por domínio (spec `070`, T013)
- [ ] T012 [P2] [any] Decompor `App.tsx`/`lib/api.ts` por feature (spec `090`)
- [ ] T013 [P2] [any] Adotar `openapi-typescript` (ADR-016; spec `090`)
- [ ] T014 [P2] [any] Separar `backend/app/core/contracts.py` por bounded context (DT-001 cross-cutting)
- [ ] T015 [P2] [any] Cobrir lacunas de teste: rotas backend simples + frontend + fallback e2e (DT-002 cross-cutting)

## Notas

- Fase 2 muda código de produção: exige o gate (Docker) e deve subir a stack a partir do worktree para validar a branch correta.
