# Especificação: Pipeline de Arquivos e RAG (com dados sensíveis)

**Pasta da spec**: `specs/030-files-rag-pipeline/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Consolidar o pipeline de arquivos/documentos/bases + recuperação RAG e a classificação de dados sensíveis. **Migra e supersede** o legado `rag-sensitive-data` (arquivada em `specs/_legacy/rag-sensitive-data/`).

> Onda 3 do refactor SDD. Cobre upload → parsing → chunking → indexação → bases → recuperação, com escopo por projeto/agente e classificação sensível (decisão ADR-010, ainda não implementada).

## Cenários de usuário e testes

### História 1 — Ingerir e indexar um arquivo (Prioridade: P1) 🎯 MVP

O operador adiciona um arquivo à biblioteca; opcionalmente indexa (extração → chunks → vetores no Qdrant).

**Teste independente**: subir um arquivo e indexá-lo; verificar chunks vinculados e busca retornando o conteúdo.

**Cenários de aceitação**:

1. **Dado** um arquivo, **Quando** entra no sistema, **Então** é registrado na biblioteca (`files/library.py`).
2. **Dado** opção de indexar, **Quando** acionada, **Então** o sistema extrai texto/metadados, cria chunks e envia ao índice vetorial (`files/processor.py`, `rag/indexing.py`, `rag/vector_store.py`).

### História 2 — Recuperar contexto por escopo (Prioridade: P1)

A recuperação respeita projeto ativo, agente, bases ativas e limites da base.

**Cenários de aceitação**:

1. **Dado** uma base ativa no escopo, **Quando** o chat monta contexto, **Então** o sistema busca apenas no escopo permitido e registra evento auditável de acesso a documentos.

### História 3 — Classificação de conteúdo sensível (Prioridade: P1)

Conteúdo sensível é classificado (manual + heurística) e rastreável antes de virar contexto para provedores externos.

**Cenários de aceitação**:

1. **Dado** conteúdo marcado/detectado como sensível, **Quando** for usado em prompt, **Então** o sistema registra a classificação e o uso é rastreável na auditoria (ADR-010).

### Casos de borda

- Tipos suportados: PDF, DOCX, Markdown, TXT, CSV, HTML e imagem (OCR opcional).
- Documento fora do escopo do projeto não entra no contexto.

## Requisitos

### Requisitos funcionais

- **RF-001**: QUANDO um arquivo for processado, O SISTEMA DEVE diferenciar upload, parsing, chunking, indexação, vinculação a bases e recuperação. _(migrado de rag-sensitive-data)_
- **RF-002**: QUANDO conteúdo sensível for detectado ou marcado, O SISTEMA DEVE registrar a classificação sensível.
- **RF-003**: QUANDO documentos indexados forem usados em prompt para OpenAI/Anthropic/Google, O SISTEMA PODE enviá-los conforme bases ativas e escopo permitido.
- **RF-004**: QUANDO o RAG montar contexto, O SISTEMA DEVE respeitar projeto/agente/bases ativos e limites da base.
- **RF-005**: QUANDO uma busca acessar documentos, O SISTEMA DEVE registrar evento auditável.

### Requisitos não funcionais

- **RNF-001**: Embeddings locais e índice Qdrant via interface `VectorStore` (ADR-004), permitindo troca futura.
- **RNF-002**: Indexação longa DEVE expor status e suportar retry (workers — ver `040-import-workers-queues`).

## Critérios de sucesso

- **CS-001**: Toda recuperação respeita o escopo (projeto/agente/base) — validado por teste.
- **CS-002**: Todo acesso a documento em contexto gera evento de auditoria.

## Premissas

- Fora do escopo imediato: fluxo automático ChatGPT → bases revisadas; backup local (migrado de rag-sensitive-data).

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `backend/app/files/library.py`, `files/processor.py`, `backend/app/rag/embeddings.py`, `rag/indexing.py`, `rag/vector_store.py`, `backend/app/api/routes/files.py`, `documents.py`, `knowledge.py`
- Docs: `docs/knowledge-bases.md`, `docs/decisions.md` (ADR-004, ADR-010), `docs/application-map.md`
- Testes: `backend/tests/test_rag_ingestion.py`, `test_platform_files.py`
- Legado migrado: `specs/_legacy/rag-sensitive-data/`
- Specs relacionadas: `specs/010-chat-orchestration/`, `specs/040-import-workers-queues/`, `specs/060-cost-audit-governance/`

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: Classificação sensível **não implementada** (`specs/000-repo-foundation/tasks.md` item aberto). Direção: marcação manual + heurística + flag de auditoria. Esforço: M.
- **DT-002**: Embeddings locais simples (sentence-transformers ou hash determinístico). Direção: melhorar qualidade/consistência; busca híbrida (vetorial + filtros + boost + fallback). Esforço: M.
- **DT-003**: Fila de indexação em memória (`rag/indexing.py`, `workers/index_queue.py`) — migrar para Valkey/Redis com volume. Esforço: M. (cruza com `040-import-workers-queues`.)

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Conteúdo do legado migrado; dívida documentada
