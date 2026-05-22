# CLAUDE.md

@AGENTS.md

## Claude Code

Use este arquivo apenas como adaptador para Claude Code. As regras principais do repositório vivem em `AGENTS.md` e os invariantes em `.specify/memory/constitution.md`.

As fases do SDD (padrão GitHub Spec Kit) estão disponíveis como skills em `.claude/skills/speckit-*`: `speckit-specify`, `speckit-clarify`, `speckit-plan`, `speckit-analyze`, `speckit-tasks`, `speckit-implement` (e `speckit-constitution`, `speckit-checklist`, `speckit-taskstoissues`). Templates em `.specify/templates/`; scripts em `.specify/scripts/`.

## Regras específicas

- Antes de implementar mudanças grandes, apresente um plano curto e confirme o escopo contra a spec relevante.
- Ao trabalhar em monorepo, leia os arquivos de contexto do diretório tocado antes de editar.
- Se a tarefa vier de outro agente, leia `specs/repo-foundation/handoff.md` e preserve decisões já validadas.
- Prefira commits/patches pequenos e revise o diff antes de concluir.
- Não duplique regras de arquitetura aqui; atualize `AGENTS.md` quando a regra for comum a Codex, Devin e humanos.
- Caso ainda existam conflitos ou dúvidas de como desenvolver, pergunte ao dono do prompt antes de gerar código.
