---
name: speckit-taskstoissues
description: Use quando converter tasks.md de uma spec em issues do GitHub (opcional; só se o repo usar Issues). Cria conteúdo externo — confirme com o dono antes.
---

## Objetivo

Espelhar as tarefas de `specs/NNN-slug/tasks.md` em issues do GitHub, preservando rastreabilidade.

## Passos

1. **Confirme com o dono do produto** antes de criar issues (ação externa, difícil de reverter em massa).
2. Leia `tasks.md`; para cada tarefa relevante crie uma issue via `gh issue create`, preservando ID, `[Pri]`, `[exec]` e o caminho de arquivo na descrição.
3. Inclua link para `specs/NNN-slug/spec.md` e para a constituição; aplique labels por prioridade quando existirem.

## Saída

Issues criadas e referenciadas a partir da spec.

## Não faça

- não criar issues sem confirmação do dono;
- não duplicar issues já existentes para a mesma tarefa.
