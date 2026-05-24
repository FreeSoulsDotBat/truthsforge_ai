# Tarefas: Pipeline de Arquivos e RAG

**Entrada**: `specs/030-files-rag-pipeline/spec.md` + `plan.md`.

## Fase 1 — Documentação (esta onda)

- [x] T001 [P0] [claude-code] Criar `spec.md` consolidando arquivos+RAG+sensíveis
- [x] T002 [P0] [claude-code] Migrar requisitos de `rag-sensitive-data` e arquivar em `specs/_legacy/`
- [x] T003 [P0] [claude-code] Registrar dívida DT-001..003

## Fase 2 — Implementação (futuro; herdada do legado + dívida)

- [ ] T010 [P1] [any] Implementar classificação sensível manual + heurística com auditoria (DT-001)
- [ ] T011 [P1] [any] Validar escopo RAG por projeto/agente/base com testes
- [ ] T012 [P1] [any] Auditar documentos usados em prompts externos
- [ ] T013 [P2] [any] Melhorar embeddings e busca híbrida (DT-002)
- [ ] T014 [P2] [any] Tornar a fila de indexação externa o default — `RedisJobQueue` já implementado/testado e usado por `index_queue.py` via `create_job_queue` quando `TRUTHS_FORGE_QUEUE_BACKEND=redis`; default ainda `memory` (DT-003)
- [ ] T015 [P2] [any] Expor filtros de sensibilidade na UI

## Notas

- Fase 2 herda tarefas abertas do legado `rag-sensitive-data`; iniciar após decisão do dono.
