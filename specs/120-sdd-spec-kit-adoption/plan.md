# Plano de implementação: Adoção do GitHub Spec Kit

**Pasta da spec**: `specs/120-sdd-spec-kit-adoption/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Registra a estratégia já executada (Ondas 0–10 + retro-fit) e o que resta (Fase 2).

## Resumo

Adoção **manual aditiva** do Spec Kit: `.specify/` (constituição + templates + scripts), fases SDD como skills em `.claude/skills/speckit-*`, numeração `NNN-` em todas as specs, specs absorvidas arquivadas em `specs/_legacy/`. Cada bounded context ganhou spec; a dívida de código foi documentada (DT) por domínio, não executada.

## Contexto técnico

- **Tipo**: refactor de processo/documentação (doc-only nesta frente).
- **Validação**: gate `scripts/quality.ps1` (Docker) para fatias de código (Fase 2).

## Constitution Check

- [x] P2 Stack invariável — adoção não troca stack.
- [x] P3 Preservar arquitetura — aditivo; nada apagado (`docs/`/`.agents/skills/` mantidos).
- [x] P4 Spec/Doc rastreável — esta meta-spec fecha o requisito de "frente grande tem spec".
- [x] P9 Qualidade/PT-BR.

Sem violações.

## Estratégia / Ondas (executadas)

- **O0** Foundation: `.specify/` + `.claude/skills/speckit-*` + ponteiros aditivos.
- **O1–O10**: specs `010`–`100` por domínio (4 migradas para `_legacy/`).
- **Retro-fit**: renomear `000`/`005`/`110`; atualizar todas as referências.
- **Ratificações**: ADR-015 (storage), ADR-016 (tipos OpenAPI).
- **Fase 2 (início)**: teste de paridade de storage (validado).

## Sequenciamento

Foundation → núcleo (chat/gateway) → demais domínios → transversais (storage) → frontend/shells → retro-fit → ratificações → Fase 2 (faseada, PRs próprios).

## Validação

- Doc-only: `git diff --check`; **zero** refs a slug antigo fora de `_legacy/` (auditado, inclusive sem barra final).
- Fatias de código (Fase 2): `scripts/quality.ps1` verde no container.

## Riscos e trade-offs

- `core.autocrlf=true` gera warnings LF→CRLF cosméticos.
- Containers dev montam o repo principal, não este worktree — validar código de produção exige subir a stack do worktree.

## Rastreamento de complexidade

Sem violações.
