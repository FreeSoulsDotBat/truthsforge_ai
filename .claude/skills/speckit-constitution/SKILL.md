---
name: speckit-constitution
description: Use quando criar ou emendar os princípios não-negociáveis do projeto em .specify/memory/constitution.md. Não use para escrever specs de feature.
---

## Objetivo

Manter `.specify/memory/constitution.md` como a camada curta dos invariantes do repositório, derivada de `AGENTS.md` + `docs/decisions.md` (ADRs). A constituição governa todas as fases do SDD.

## Passos

1. Leia `.specify/memory/constitution.md`, `AGENTS.md` e `docs/decisions.md`.
2. Para uma nova regra invariável, **registre o ADR em `docs/decisions.md` primeiro**; a constituição apenas referencia (não copia o rationale).
3. Atualize o princípio com: nome, regra em 1-2 linhas e `_Fonte: ADR-xxx / AGENTS.md_`.
4. Versione (MAJOR = remoção/redefinição incompatível; MINOR = novo princípio/seção; PATCH = redação) e atualize as datas de ratificação/emenda.
5. Mudança de stack (P2) ou de guardrails de segurança (P6) **exige aprovação explícita do dono do produto** — nunca implícita.

## Saída

Constituição atualizada, com versão e nota de emenda; ADR correspondente em `docs/decisions.md` quando aplicável.

## Não faça

- não copiar ADRs inteiros para dentro da constituição;
- não alterar stack/segurança sem ADR e aprovação;
- não transformar a constituição em manual de "como trabalhar" (isso vive em `AGENTS.md`).
