# handoff.md

## Objetivo

Registrar continuidade de trabalho entre humanos, Codex, Claude Code e Devin.

Este arquivo não substitui `tasks.md`, issues ou PRs. Ele existe para evitar perda de contexto quando uma frente de trabalho muda de executor.

## Registro atual

### Estado

- Última frente trabalhada: criação do baseline SDD multiagente.
- Executor anterior: Devin.
- Executor recomendado para continuação: qualquer agente compatível após leitura de `AGENTS.md`, `spec.md`, `plan.md` e `tasks.md`.
- Branch/PR relacionado: branch de implementação SDD a partir de `master`.
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

- Pendente nesta branch até a conclusão da implementação e abertura do PR.

### Pendências

- Rodar validações locais.
- Abrir PR separado.
- Aguardar CI.

### Riscos conhecidos

- O SDD pode ficar duplicado em relação a `docs/` se futuras mudanças copiarem conteúdo completo em vez de referenciar docs.
- Tasks marcadas como concluídas no baseline dependem do estado documentado atual; se o código divergir, o código vence.

### Próximo passo recomendado

- Validar docs/specs e manter o PR focado em governança SDD, sem misturar implementação funcional de features.

## Regras

- Atualize este arquivo quando uma tarefa ficar incompleta ou for transferida para outro agente.
- Não registre segredos, tokens, chaves ou dados pessoais sensíveis.
- Não use este arquivo para decisões arquiteturais permanentes; decisões permanentes devem virar docs, ADR ou spec.
- Se o handoff contradisser código, docs ou spec, trate o handoff como contexto temporário e valide antes de agir.
