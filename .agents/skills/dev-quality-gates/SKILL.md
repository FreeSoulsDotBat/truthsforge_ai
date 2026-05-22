---
name: dev-quality-gates
description: Use antes de concluir mudanças relevantes, preparar PRs ou validar se backend e frontend continuam saudáveis.
---

## Objetivo

Aplicar os gates reais do repositório.

## Fonte principal

- `scripts/quality.ps1`
- `docs/local-dev.md`
- `specs/000-repo-foundation/plan.md`

## Procedimento

1. Identificar quais áreas foram alteradas.
2. Rodar os checks equivalentes do backend quando backend for impactado:
    - `python -m ruff format --check backend/app backend/tests`
    - `python -m ruff check backend/app backend/tests`
    - `pushd backend && python -m pytest -q && popd`
3. Rodar os checks equivalentes do frontend quando web for impactado:
    - `pnpm --filter @truths-forge/web format:check`
    - `pnpm --filter @truths-forge/web lint`
    - `pnpm --filter @truths-forge/web test:unit`
    - `pnpm --filter @truths-forge/web typecheck`
4. Rodar `pnpm --filter @truths-forge/docs build` quando documentação Docusaurus ou `docs/` forem impactados.
5. Confirmar se documentação e spec foram atualizadas quando contratos mudaram.
6. Registrar o que foi validado no resumo final.

## Não faça

- não declare tarefa concluída sem mencionar validação;
- não omita falhas de qualidade;
- não introduza atalhos diferentes de `scripts/quality.ps1` sem justificar.
