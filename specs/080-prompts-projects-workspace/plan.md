# Plano de implementação: Prompts, Projetos e Workspace

**Pasta da spec**: `specs/080-prompts-projects-workspace/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Documenta prompts + projetos e registra dívida (DT-001..002).

## Resumo

Biblioteca de prompts (`prompts/renderer.py`, `routes/prompts.py`) e organização de workspace (`routes/projects.py`) que influencia escopo de contexto/RAG.

## Contexto técnico

- **Storage**: Postgres (prompts/projetos/pastas).
- **Tipo de projeto**: backend FastAPI · **Testes**: pytest.

## Constitution Check

- [x] P4 Spec/Doc rastreável.
- [x] P3 Preservar arquitetura (doc-only).
- [x] P9 Qualidade/PT-BR.

Sem violações.

## Estrutura

```text
backend/app/prompts/     # renderer.py
backend/app/api/routes/  # prompts.py, projects.py
```

## Estratégia / Ondas

1. Esta onda: spec + dívida.
2. Futuro: versionamento de prompts; service layer.

## Validação

- Doc-only: cross-links resolvem. Futuro: `scripts/quality.ps1` + testes de prompts/projetos.

## Riscos e trade-offs

- Versionamento de prompts implica schema novo — coordenar com storage (070).

## Rastreamento de complexidade

Sem violações.
