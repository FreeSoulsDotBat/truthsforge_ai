# Tarefas: Importação e Workers/Filas

**Entrada**: `specs/040-import-workers-queues/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` de importação + workers
- [x] T002 [P0] [claude-code] Registrar dívida DT-001..002

## Fase 2 — Dívida de código (futuro; não executar nesta frente)

- [ ] T010 [P2] [any] Migrar `workers/import_queue.py` e `index_queue.py` para fila externa (Valkey/Redis) preservando status/retry (DT-001)
- [ ] T011 [P2] [human] Avaliar/escrever spec do fluxo automático ChatGPT → bases revisadas (DT-002)

## Notas

- Fase 2 só inicia após decisão do dono.
