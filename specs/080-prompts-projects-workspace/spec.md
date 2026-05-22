# Especificação: Prompts, Projetos e Workspace

**Pasta da spec**: `specs/080-prompts-projects-workspace/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Cobrir a biblioteca de prompts e a organização de workspace (projetos/pastas), hoje sem spec dedicada.

> Onda 8 do refactor SDD. Documenta prompts + projetos e a dívida (versionamento de prompts).

## Cenários de usuário e testes

### História 1 — Biblioteca de prompts (Prioridade: P1) 🎯 MVP

O operador cria/edita/renderiza prompts reutilizáveis.

**Teste independente**: criar um prompt com variáveis e renderizá-lo.

**Cenários de aceitação**:

1. **Dado** um template de prompt, **Quando** renderizado, **Então** o sistema aplica as variáveis (`prompts/renderer.py`) e persiste o prompt (`api/routes/prompts.py`).

### História 2 — Organização por projetos/pastas (Prioridade: P1)

Projetos e pastas organizam chats/arquivos e influenciam o escopo de contexto/RAG.

**Cenários de aceitação**:

1. **Dado** um chat em um projeto, **Quando** monta contexto, **Então** o projeto influencia o escopo de bases associadas (`api/routes/projects.py`; cruza com `030-files-rag-pipeline`).

### Casos de borda

- Projeto "geral" como default quando não houver projeto explícito.

## Requisitos

### Requisitos funcionais

- **RF-001**: QUANDO o operador criar/editar prompts, O SISTEMA DEVE persisti-los e permitir recuperação (`api/routes/prompts.py`).
- **RF-002**: QUANDO um prompt for renderizado, O SISTEMA DEVE aplicar variáveis/templating (`prompts/renderer.py`).
- **RF-003**: QUANDO o operador organizar projetos/pastas, O SISTEMA DEVE persistir e permitir que influenciem contexto e escopo de RAG.

### Requisitos não funcionais

- **RNF-001**: A UX de workspace permanece densa/dark/mobile-first (frontend — ver `090-frontend-web-shell`).

## Critérios de sucesso

- **CS-001**: Prompts criados são recuperáveis e renderizáveis com variáveis.
- **CS-002**: O escopo de projeto/pasta é respeitado na recuperação de contexto.

## Premissas

- Versionamento de prompts ainda não existe.

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `backend/app/prompts/renderer.py`; `backend/app/api/routes/prompts.py`, `projects.py`
- Docs: `docs/application-map.md`
- Specs relacionadas: `specs/010-chat-orchestration/`, `specs/030-files-rag-pipeline/`, `specs/090-frontend-web-shell/`

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: Prompts sem versionamento. Direção: versionar templates de prompt (histórico/rollback). Esforço: M.
- **DT-002**: Acoplamento direto a `get_store()` nas rotas de prompts/projects (sem service layer). Direção: alinhar ao padrão service layer (ver `010-chat-orchestration` DT). Esforço: S.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Dívida documentada (não executada)
