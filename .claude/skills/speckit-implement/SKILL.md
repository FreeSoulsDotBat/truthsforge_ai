---
name: speckit-implement
description: Use quando executar as tarefas de uma spec (specs/NNN-slug/tasks.md), respeitando aprovação humana e os gates de qualidade.
---

## Objetivo

Implementar as tarefas em ordem, preservando os princípios da constituição e o checklist de entrega.

## Passos

1. Siga `tasks.md` na ordem de dependência; respeite os checkpoints por fase/história.
2. **Aprovação humana (P6):** adições podem autoexecutar quando a policy permitir; **alterações e deleções exigem aprovação** antes de executar.
3. Atualize `docs/` e a própria spec quando contrato/comportamento/fluxo mudar (P4).
4. Rode os gates: `scripts/quality.ps1` (backend ruff+pytest; web format/lint/test/typecheck/build) para as áreas tocadas.
5. Aplique `docs/delivery-checklist.md` e `.github/pull_request_template.md`; atualize `handoff.md` ao passar a frente.
6. Antes de commitar/alterar a plataforma, confirme com o dono o **nome da branch** e a **mensagem de commit semântica** (P9).

## Saída

Mudança implementada, validada e rastreável (spec/task/PR/handoff).

## Não faça

- não reescrever código fora do escopo das tarefas;
- não pular gates de qualidade;
- não commitar/empurrar sem o dono pedir.
