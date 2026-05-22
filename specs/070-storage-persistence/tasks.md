# Tarefas: Persistência e Abstração de Storage

**Entrada**: `specs/070-storage-persistence/spec.md` + `plan.md` + `research.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` da camada de storage
- [x] T002 [P0] [claude-code] Registrar dívida DT-001..003
- [x] T003 [P0] [claude-code] Redigir proposta de ADR-015 em `research.md` (não ratificada)

## Fase 2 — Decisão e implementação (futuro; não executar nesta frente)

- [x] T010 [P1] [human] Ratificar ADR-015 em `docs/decisions.md` (2026-05-22)
- [ ] T011 [P1] [any] Extrair `Protocol Store` a partir da superfície atual (sem mudar implementações) (DT-002)
- [x] T012 [P1] [claude-code] Teste de paridade Postgres × DevStore em `backend/tests/test_store_parity.py` (validado: ruff + pytest no container) (DT-003)
- [ ] T013 [P2] [any] Fatiar storage em repositórios por domínio, um por vez (DT-001)

## Notas

- T011+ só após T010 (ADR ratificado). Storage é transversal — refatorar com testes de paridade antes de fatiar.
