# CLAUDE.md

@AGENTS.md

## Claude Code

Use este arquivo apenas como adaptador para Claude Code. As regras principais do repositório vivem em `AGENTS.md`.

## Regras específicas

- Antes de implementar mudanças grandes, apresente um plano curto e confirme o escopo contra a spec relevante.
- Ao trabalhar em monorepo, leia os arquivos de contexto do diretório tocado antes de editar.
- Se a tarefa vier de outro agente, leia `specs/repo-foundation/handoff.md` e preserve decisões já validadas.
- Prefira commits/patches pequenos e revise o diff antes de concluir.
- Não duplique regras de arquitetura aqui; atualize `AGENTS.md` quando a regra for comum a Codex, Devin e humanos.
- Caso ainda existam conflitos ou dúvidas de como desenvolver, pergunte ao dono do prompt antes de gerar código.
