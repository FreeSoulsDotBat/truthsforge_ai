# Plano de implementação: Importação e Workers/Filas

**Pasta da spec**: `specs/040-import-workers-queues/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Documenta importação + workers e registra dívida (DT-001..002).

## Resumo

Importação do ChatGPT (`importers/chatgpt*.py`) roda como job; workers (`workers/*`) processam importação e indexação em memória. Valkey está preparado mas não é o backend de fila atual.

## Contexto técnico

- **Storage**: Postgres (jobs/conversas), Qdrant (índice), filesystem (`.local/imports`).
- **Tipo de projeto**: backend FastAPI · **Testes**: pytest.

## Constitution Check

- [x] P5 Postgres-prod / JSON dev-only.
- [x] P3 Preservar arquitetura (doc-only).
- [x] P9 Qualidade/PT-BR.

Sem violações.

## Estrutura

```text
backend/app/importers/   # chatgpt.py, chatgpt_jobs.py
backend/app/workers/     # import_queue.py, index_queue.py, tasks.py
backend/app/api/routes/  # imports.py
```

## Estratégia / Ondas

1. Esta onda: spec + dívida.
2. Futuro: migrar filas para Valkey/Redis; avaliar fluxo ChatGPT → bases.

## Validação

- Doc-only: cross-links resolvem. Futuro: `scripts/quality.ps1` + `test_chatgpt_import.py`.

## Riscos e trade-offs

- Migrar filas muda semântica de retry/persistência — exige testes de jobs.

## Rastreamento de complexidade

Sem violações.
