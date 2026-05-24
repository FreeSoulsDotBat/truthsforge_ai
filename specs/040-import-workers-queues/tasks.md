# Tarefas: Importação e Workers/Filas

**Entrada**: `specs/040-import-workers-queues/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` de importação + workers
- [x] T002 [P0] [claude-code] Registrar dívida DT-001..002

## Fase 2 — Dívida de código (futuro; não executar nesta frente)

- [ ] T010 [P2] [any] `RedisJobQueue` (Valkey/Redis) já implementado e testado (`workers/job_queue.py`, status/retry preservados, selecionável via `TRUTHS_FORGE_QUEUE_BACKEND`); **falta** torná-lo default (hoje `memory`) e validar em volume (DT-001)
- [ ] T011 [P2] [human] Avaliar/escrever spec do fluxo automático ChatGPT → bases revisadas (DT-002)

## Notas

- Fase 2 só inicia após decisão do dono.
