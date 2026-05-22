---
name: speckit-plan
description: Use quando traduzir uma spec aprovada em plano técnico (plan.md) aderente ao código atual do repositório.
---

## Objetivo

Produzir `specs/NNN-slug/plan.md` a partir de `.specify/templates/plan-template.md`, descrevendo o "como" sem trocar a stack.

## Passos

1. Instancie o plano:
   - Windows: `.specify/scripts/powershell/setup-plan.ps1 -FeatureDir NNN-slug`
   - bash: `.specify/scripts/bash/setup-plan.sh NNN-slug`
2. Preencha contexto técnico, estrutura com **caminhos reais** (`backend/app/...`, `apps/web/src/...`), estratégia/ondas, sequenciamento, validação e riscos.
3. Preencha o **Constitution Check** (gate): marque conformidade com P1–P9 ou justifique em "Rastreamento de complexidade". Não avance para `tasks` com o gate reprovado.
4. Crie `research.md`, `data-model.md` ou `contracts/` somente quando agregarem (use os templates).

## Saída

`plan.md` com Constitution Check aprovado; opcionalmente `research/data-model/contracts`.

## Não faça

- não pular o Constitution Check;
- não trocar de stack sem ADR e aprovação (P2);
- não duplicar o "o quê" da spec.
