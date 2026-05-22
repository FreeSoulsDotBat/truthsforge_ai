# Tarefas: [NOME DA FEATURE]

**Entrada**: artefatos de `specs/[NNN-slug]/` (plan.md obrigatório; spec.md para histórias; research/data-model/contracts se existirem).

## Formato: `[ID] [P?] [Hx] [Pri] [exec] Descrição`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência).
- **[Hx]**: a qual história a tarefa pertence (H1, H2…), para rastreabilidade.
- **[Pri]**: prioridade no roadmap — `[P0]` bloqueante / `[P1]` MVP / `[P2]` não-bloqueante.
- **[exec]**: executor sugerido — `[any|codex|claude-code|devin|human]` (`[human]` exige decisão/aprovação).
- Inclua o **caminho de arquivo exato** na descrição.
- Cada item deve virar commit/PR pequeno sempre que possível; ao passar de um agente a outro, atualizar `handoff.md`.

## Fase 1 — Setup (infra compartilhada)

- [ ] T001 [P0] [any] [descrição] em `caminho/arquivo`

## Fase 2 — Fundação (pré-requisitos bloqueantes)

**⚠️ Nenhuma história começa antes desta fase concluir.**

- [ ] T002 [P] [P0] [any] [descrição] em `caminho/arquivo`

**Checkpoint**: fundação pronta — histórias podem começar.

## Fase 3 — História 1 (Prioridade: P1) 🎯 MVP

**Objetivo**: [o que a história entrega] · **Teste independente**: [como validar]

- [ ] T003 [P] [H1] [P1] [any] [descrição] em `caminho/arquivo`
- [ ] T004 [H1] [P1] [any] [descrição] em `caminho/arquivo` (depende de T003)

**Checkpoint**: História 1 funcional e testável isoladamente.

## Fase 4 — História 2 (Prioridade: P2)

- [ ] T005 [P] [H2] [P2] [any] [descrição] em `caminho/arquivo`

## Fase N — Polimento e transversais

- [ ] TXXX [P] [P2] [any] Atualizar `docs/` e specs afetadas
- [ ] TXXX [P2] [any] Rodar validação de `quality.ps1` e checklist de entrega

## Dependências e ordem de execução

- Setup → Fundação (bloqueia tudo) → Histórias (P1 → P2 → P3) → Polimento.
- Dentro de cada história: dados/modelos antes de serviços; serviços antes de endpoints; implementação antes de integração.

## Paralelismo

- Tarefas `[P]` em arquivos distintos podem rodar juntas.
- Histórias diferentes podem ser tocadas em paralelo após a Fundação.

## Notas

- `[P]` = arquivos diferentes, sem dependência. Evite: tarefas vagas, conflito no mesmo arquivo, dependências cruzadas que quebram a independência das histórias.
- Em refactor SDD, tarefas de **dívida de código** apenas DOCUMENTAM o débito (spec/ADR), não reescrevem o código.
