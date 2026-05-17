# spec.md

## Título

Artifacts, canvas e exportações

## Status

Decisões de produto aprovadas; implementação futura.

## Objetivo

Entregar artifacts/canvas com exportações em Markdown, código, JSON, HTML, Mermaid, PDF, DOCX e PPTX com mesma prioridade.

## Requisitos funcionais

- QUANDO o usuário criar um artifact, O SISTEMA DEVE versionar e rastrear sua origem.
- QUANDO o usuário exportar conteúdo, O SISTEMA DEVE suportar Markdown, código, JSON, HTML, Mermaid, PDF, DOCX e PPTX.
- QUANDO uma exportação criar ou alterar arquivo local, O SISTEMA DEVE auditar a operação e permitir rollback quando aplicável.

## Fontes

- `docs/implementation-plan.md`
- `docs/mvp-readiness.md`
- `specs/repo-foundation/spec.md`
