---
name: speckit-tasks
description: Use quando quebrar um plano aprovado em tarefas ordenadas e executáveis (specs/NNN-slug/tasks.md).
---

## Objetivo

Gerar `tasks.md` a partir de `.specify/templates/tasks-template.md`, com tarefas atômicas e rastreáveis.

## Passos

1. Instancie as tarefas:
   - Windows: `.specify/scripts/powershell/setup-tasks.ps1 -FeatureDir NNN-slug`
   - bash: `.specify/scripts/bash/setup-tasks.sh NNN-slug`
2. Derive tarefas das histórias/requisitos do plano, no formato `[ID] [P?] [Hx] [Pri] [exec] Descrição` com **caminho de arquivo exato**.
3. Organize em fases: Setup → Fundação (bloqueante) → histórias (P1→P2→P3) → Polimento. Marque `[P]` o que é paralelizável (arquivos distintos).
4. Cada tarefa deve poder virar commit/PR pequeno.

## Saída

`tasks.md` ordenado, com dependências e oportunidades de paralelismo.

## Não faça

- não criar tarefas vagas ou com conflito no mesmo arquivo;
- não transformar dívida de código em reescrita: dívida vira tarefa de **documentação** (ADR/spec).
