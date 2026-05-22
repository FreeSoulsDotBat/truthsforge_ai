# Especificação: Importação (ChatGPT) e Workers/Filas

**Pasta da spec**: `specs/040-import-workers-queues/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Cobrir importação de histórico do ChatGPT e a infraestrutura de filas/workers (indexação e importação), hoje sem spec dedicada.

> Onda 4 do refactor SDD. Documenta importação e os workers em memória; registra a dívida de migração para fila externa (Valkey).

## Cenários de usuário e testes

### História 1 — Importar histórico do ChatGPT (Prioridade: P1) 🎯 MVP

O operador importa um export do ChatGPT; o sistema processa em background como job.

**Teste independente**: submeter um export e acompanhar o job até concluir, com conversas disponíveis.

**Cenários de aceitação**:

1. **Dado** um arquivo de export, **Quando** importado, **Então** o sistema cria um job e processa as conversas (`importers/chatgpt.py`, `chatgpt_jobs.py`).
2. **Dado** indexação opcional, **Quando** habilitada, **Então** o conteúdo importado entra na fila de indexação.

### História 2 — Jobs longos com status e retry (Prioridade: P1)

Importação/indexação rodam como jobs com status observável e retries.

**Cenários de aceitação**:

1. **Dado** um job longo, **Quando** executa, **Então** o sistema expõe status e re-tenta em falha transitória (`workers/import_queue.py`, `index_queue.py`, `tasks.py`).

### Casos de borda

- Fluxo automático assistido ChatGPT → bases revisadas está **fora** do MVP (ADR-010).

## Requisitos

### Requisitos funcionais

- **RF-001**: QUANDO um export do ChatGPT for submetido, O SISTEMA DEVE criar um job e processá-lo em background (`backend/app/importers/chatgpt_jobs.py`).
- **RF-002**: QUANDO um job estiver em execução, O SISTEMA DEVE expor status e suportar retry (`backend/app/workers/`).
- **RF-003**: QUANDO o operador optar por indexar a importação, O SISTEMA DEVE enfileirar a indexação (`workers/index_queue.py`).
- **RF-004**: O SISTEMA DEVE registrar falhas de indexação como evento auditável (cruza com `060-cost-audit-governance`).

### Requisitos não funcionais

- **RNF-001**: Valkey/Redis é a infraestrutura local preparada para fila/cache; workers atuais rodam em memória (ADR-004; `docs/architecture.md`).

## Critérios de sucesso

- **CS-001**: Importações longas não bloqueiam a UI (processamento assíncrono).
- **CS-002**: Falhas de indexação são observáveis (status + auditoria).

## Premissas

- A fila em memória é aceitável no MVP; migração para Valkey ocorre com volume real.

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `backend/app/importers/chatgpt.py`, `chatgpt_jobs.py`; `backend/app/workers/import_queue.py`, `index_queue.py`, `tasks.py`; `backend/app/api/routes/imports.py`
- Docs: `docs/chatgpt-import.md`, `docs/decisions.md` (ADR-004, ADR-010), `docs/architecture.md`, `docs/infra-observability.md`
- Testes: `backend/tests/test_chatgpt_import.py`
- Specs relacionadas: `specs/030-files-rag-pipeline/`, `specs/060-cost-audit-governance/`

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: Workers em memória (`workers/import_queue.py`, `index_queue.py`) vs Valkey/Redis preparado e não usado. Direção: persistir filas em fila externa quando o volume crescer (OCR/indexação). Esforço: M.
- **DT-002**: Sem fluxo automático assistido ChatGPT → bases revisadas (decisão: fora do MVP). Direção: futura spec própria se priorizado. Esforço: L.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Dívida documentada (não executada)
