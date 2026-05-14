---
name: rag-knowledge-bases
description: Use ao trabalhar com arquivos, importações, documentos, knowledge bases, chunking, embeddings, Qdrant e recuperação de contexto.
---

## Objetivo

Tratar RAG como pipeline completo, não como simples upload de arquivo.

## Sempre consultar primeiro

- `docs/application-map.md`
- `docs/architecture.md`
- `docs/knowledge-bases.md`
- `docs/implementation-plan.md`
- `docs/mvp-readiness.md`
- `specs/repo-foundation/spec.md`

## Regras

- Diferencie claramente:
    - biblioteca de arquivos;
    - documentos parseados;
    - bases de conhecimento;
    - indexação vetorial;
    - recuperação em prompt.
- Bases são a unidade principal de contexto indexado.
- Projetos e agentes referenciam bases; eles não substituem bases.
- Conteúdo sensível não deve seguir automaticamente para provedores externos.
- Se o trabalho tocar OCR, parsing ou filas, explicite fallback e observabilidade.

## Resultado esperado

Entregar desenho e implementação com caminho rastreável:

arquivo → parsing → chunking → indexação → base ativa → recuperação.
