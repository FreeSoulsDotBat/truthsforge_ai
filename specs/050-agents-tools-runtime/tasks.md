# Tarefas: Agentes, Tools, Sandbox e Memória

**Entrada**: `specs/050-agents-tools-runtime/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` consolidando agentes+tools+sandbox+memória
- [x] T002 [P0] [claude-code] Migrar requisitos de `agents-tools` e arquivar em `specs/_legacy/`
- [x] T003 [P0] [claude-code] Registrar dívida DT-001..003

## Fase 2 — Implementação (futuro; herdada do legado + dívida)

- [ ] T010 [P1] [any] Implementar sandbox por projeto p/ `python.run` e `filesystem.write` (rede/timeout/limites/rollback) (DT-001)
- [x] T011 [P1] [any] Implementar aprovação obrigatória p/ alteração/deleção (modelo adição/alteração/deleção) — gate implementado e testado (`tools/runtime.py:94`; `test_runtime_routes.py:98`); execução de tools mutáveis ainda stub (ver T010)
- [x] T012a [P1] [any] Persistir auditoria completa por tool call — FEITA e testada (`tools/runtime.py:152`)
- [ ] T012b [P1] [any] Rollback de tools mutáveis — pendente (bloqueado pelo sandbox, T010)
- [ ] T013 [P1] [any] Especificar e implementar memória durável de JUDITE/agentes (DT-002)
- [ ] T014 [P2] [any] Implementar workflows LangGraph com checkpoints humanos (DT-003)

## Notas

- Fase 2 herda tarefas abertas do legado `agents-tools`; iniciar após decisão do dono.
