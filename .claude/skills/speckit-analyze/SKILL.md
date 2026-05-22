---
name: speckit-analyze
description: Use quando checar consistência entre spec, plan e tasks de uma feature (cobertura, contradições, cross-links). Read-only.
---

## Objetivo

Validar a coerência dos artefatos de `specs/NNN-slug/` antes de implementar.

## Passos

1. Verifique cobertura: todo requisito funcional (`RF-###`) tem ao menos uma tarefa correspondente em `tasks.md`.
2. Verifique contradições entre `spec.md` ↔ `plan.md` ↔ `tasks.md`.
3. Verifique cross-links: todos os caminhos citados em **Fontes** e nas tarefas existem no repo.
4. Verifique aderência à constituição (Constitution Check do plano consistente com os princípios).
5. Reporte gaps e inconsistências — **não corrija sozinho**; proponha ajustes ao dono.

## Saída

Relatório de cobertura/inconsistências e recomendação (seguir para `implement` ou voltar a `specify`/`plan`).

## Não faça

- não editar artefatos nesta fase;
- não aprovar implementação com requisitos sem tarefa.
