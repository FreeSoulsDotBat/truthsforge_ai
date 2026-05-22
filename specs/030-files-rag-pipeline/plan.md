# Plano de implementação: Pipeline de Arquivos e RAG

**Pasta da spec**: `specs/030-files-rag-pipeline/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Consolida o legado `rag-sensitive-data` e registra dívida (DT-001..003).

## Resumo

Pipeline: biblioteca (`files/library.py`) → parsing/OCR (`files/processor.py`) → chunking/indexação (`rag/indexing.py`, `rag/vector_store.py`) → bases (`routes/knowledge.py`, `documents.py`) → recuperação por escopo. Classificação sensível decidida (ADR-010), pendente de implementação.

## Contexto técnico

- **Storage**: Postgres (documentos/bases/metadados), Qdrant (vetores), filesystem (`.local/files`).
- **Tipo de projeto**: backend FastAPI · **Testes**: pytest.

## Constitution Check

- [x] P5 Postgres-prod / JSON dev-only.
- [x] P7 RAG com escopo e sensíveis rastreáveis (núcleo desta spec).
- [x] P3 Preservar arquitetura (doc-only).

Sem violações.

## Estrutura

```text
backend/app/files/     # library, processor
backend/app/rag/       # embeddings, indexing, vector_store
backend/app/api/routes # files.py, documents.py, knowledge.py
```

## Estratégia / Ondas

1. Esta onda: consolidar spec + migrar legado + dívida.
2. Futuro: implementar classificação sensível; melhorar embeddings/busca híbrida; fila externa.

## Validação

- Doc-only: cross-links resolvem; legado movido para `_legacy/`.
- Futuro: `scripts/quality.ps1` + `test_rag_ingestion.py`/`test_platform_files.py`.

## Riscos e trade-offs

- Classificação sensível afeta o que vai a provedores externos — exige auditoria desde o início (P7).

## Rastreamento de complexidade

Sem violações.
