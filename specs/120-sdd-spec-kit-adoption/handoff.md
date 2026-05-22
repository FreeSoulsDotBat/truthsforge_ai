# handoff.md

Continuidade entre agentes para `120-sdd-spec-kit-adoption`.

## Estado atual

- Adoção do Spec Kit registrada como spec própria (fecha P4). Estrutura, cobertura por domínio e retro-fit concluídos; ADR-015/016 ratificados; Fase 2 iniciada (paridade de storage).
- Entrega em PR #32 (`refactor/sdd-architecture` → `master`).
- Ponto de entrada para qualquer agente: `.specify/memory/constitution.md` → `specs/README.md` (catálogo) → skill `repo-map`.

## Pendências

- Fase 2 (código): Protocol Store (070), repos, App.tsx/api.ts (090), openapi-typescript (090), separar contracts.py (DT-001), testes (DT-002). Exigem gate e stack apontada ao worktree.

## Cuidados de ambiente

- `core.autocrlf=true`: warnings LF→CRLF cosméticos.
- Containers dev montam o repo principal, não este worktree.
