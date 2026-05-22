# Skills do repositório

Estas skills dão contexto operacional aos principais bounded contexts do monorepo.

## Fronteira com as skills de fase SDD

- As skills **de domínio** vivem aqui em `.agents/skills/` (ex.: `repo-map`, `backend-fastapi`, `web-react-vite`, `modeling-3d`) e são compartilhadas por Codex, Claude Code, Devin e humanos.
- As skills **de fase do SDD (GitHub Spec Kit)** vivem em `.claude/skills/speckit-*` (constitution, specify, clarify, plan, analyze, tasks, implement, checklist, taskstoissues) e orquestram o fluxo spec → plan → tasks → implement.
- A constituição (`.specify/memory/constitution.md`) e os templates (`.specify/templates/`) são agnósticos de agente; as skills `speckit-*` são a interface nativa do Claude Code para essas fases.

## Regras

- Cada skill cobre um trabalho específico.
- Descrições devem dizer claramente quando a skill deve e não deve ser ativada.
- Prefira instruções a scripts.
- Referencie sempre arquivos versionados do próprio repositório.
- Escreva skills como procedimentos do repositório, não como instruções exclusivas de uma única IA.
- Se uma skill começar a ficar genérica demais, ela deve ser dividida.
