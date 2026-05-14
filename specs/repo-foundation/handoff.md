# handoff.md

## Objetivo

Registrar continuidade de trabalho entre humanos, Codex, Claude Code e Devin.

Este arquivo não substitui `tasks.md`, issues ou PRs. Ele existe para evitar perda de contexto quando uma frente de trabalho muda de executor.

## Registro atual

### Estado

- Última frente trabalhada: criação do baseline SDD multiagente.
- Executor anterior: Devin.
- Executor recomendado para continuação: qualquer agente compatível após leitura de `AGENTS.md`, `spec.md`, `plan.md` e `tasks.md`.
- Branch/PR relacionado: PR #12.
- Spec relacionada: `specs/repo-foundation/spec.md`.
- Task relacionada: `Foundation SDD`.

### Decisões tomadas

- `AGENTS.md` é o contrato comum para Codex, Claude Code, Devin e humanos.
- `CLAUDE.md` é apenas adaptador mínimo para Claude Code.
- `specs/repo-foundation/` é o baseline do produto; specs futuras devem usar `specs/<slug>/`.
- Skills ficam em `.agents/skills/` e começam como instruction-only.
- O baseline SDD foi ajustado ao estado atual já documentado: upload/parsing/OCR, workers, geração de imagem e Fusion bridge existem em níveis iniciais e não devem voltar a ser tratados como inexistentes.

### Arquivos tocados

- `AGENTS.md`
- `CLAUDE.md`
- `.agents/skills/**`
- `specs/**`
- `README.md`
- `docs/application-map.md`

### Validação executada

- `git diff --check`
- `python -m ruff check backend/app backend/tests`
- `pnpm --filter @truths-forge/web typecheck`
- `pnpm --filter @truths-forge/docs build`
- CI do PR #12: GitGuardian e Devin Review verdes no primeiro envio.

### Pendências

-

### Riscos conhecidos

- O SDD pode ficar duplicado em relação a `docs/` se futuras mudanças copiarem conteúdo completo em vez de referenciar docs.
- Tasks marcadas como concluídas no baseline dependem do estado documentado atual; se o código divergir, o código vence.

### Próximo passo recomendado

-

## Regras

- Atualize este arquivo quando uma tarefa ficar incompleta ou for transferida para outro agente.
- Não registre segredos, tokens, chaves ou dados pessoais sensíveis.
- Não use este arquivo para decisões arquiteturais permanentes; decisões permanentes devem virar docs, ADR ou spec.
- Se o handoff contradisser código, docs ou spec, trate o handoff como contexto temporário e valide antes de agir.
