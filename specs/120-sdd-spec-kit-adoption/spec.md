# Especificação: Adoção do GitHub Spec Kit (governança SDD)

**Pasta da spec**: `specs/120-sdd-spec-kit-adoption/` | **Criada em**: 2026-05-22 | **Status**: Em andamento (Ondas 0–10 + retro-fit concluídos; Fase 2 iniciada)

**Entrada**: Registrar, como artefato SDD próprio, o refactor que trouxe o padrão **GitHub Spec Kit** ao repositório. A constituição (P4) exige que toda frente que exceda ajuste pontual tenha spec própria — esta é a meta-spec dessa frente.

> Esta spec é a fonte rastreável do próprio processo SDD. O plano operacional original ficou em `~/.claude/plans/` (externo); aqui ele vira artefato versionado.

## Cenários de usuário e testes

### História 1 — LLMs guiadas sem conversa histórica (Prioridade: P1) 🎯 MVP

Qualquer agente (Codex, Claude Code, Devin) ou humano entende como trabalhar a partir da constituição + templates + skills, sem depender de transcrições.

**Teste independente**: abrir `.specify/memory/constitution.md` + `.claude/skills/speckit-*` e conseguir iniciar uma feature pelo fluxo SDD.

**Cenários de aceitação**:

1. **Dado** um agente novo, **Quando** lê a constituição e o `specs/README.md`, **Então** sabe a numeração `NNN-`, os invariantes e as fases (specify→plan→tasks→implement).

### História 2 — Cobertura de specs por domínio (Prioridade: P1)

Todo bounded context de código tem uma spec `NNN-` dedicada.

**Cenários de aceitação**:

1. **Dado** um bounded context (chat, gateway, files/RAG, import/workers, agents/tools, cost/audit, storage, prompts/projetos, frontend, mobile/desktop, 3D, artifacts), **Quando** se procura sua spec, **Então** existe uma em `specs/NNN-<slug>/`.

### História 3 — Rastreabilidade da dívida (Prioridade: P2)

A dívida de código é documentada (DT-xxx) por domínio para execução futura, sem reescrita nesta frente.

### Casos de borda

- Specs absorvidas por um domínio novo ficam congeladas em `specs/_legacy/` (sem referência ativa a slug antigo).

## Requisitos

### Requisitos funcionais

- **RF-001**: O SISTEMA DEVE oferecer invariantes em `.specify/memory/constitution.md` e as fases SDD como skills em `.claude/skills/speckit-*`.
- **RF-002**: QUANDO uma frente exceder ajuste pontual, O SISTEMA DEVE ter (ou criar via `speckit-specify`) uma spec `specs/NNN-<slug>/`.
- **RF-003**: O SISTEMA DEVE manter specs absorvidas em `specs/_legacy/` (congeladas), sem nenhuma referência ativa a slug antigo fora de `_legacy/`.
- **RF-004**: QUANDO contrato, comportamento ou fluxo mudar, O SISTEMA DEVE atualizar `docs/` e `specs/` juntos (P4).
- **RF-005**: Toda spec DEVE citar `.specify/memory/constitution.md` em **Fontes** e todo `plan.md` DEVE passar pelo Constitution Check.

### Requisitos não funcionais

- **RNF-001**: A adoção é **aditiva** — não troca a stack (P2) nem apaga `docs/`/`.agents/skills/`.
- **RNF-002**: Artefatos SDD em PT-BR; nomes/comandos do Spec Kit em inglês (P9).

## Critérios de sucesso

- **CS-001**: Zero referências a slug antigo na árvore ativa (fora de `_legacy/`).
- **CS-002**: Todos os bounded contexts de código têm spec `NNN-`.
- **CS-003**: Toda spec nova cita a constituição em Fontes.

## Premissas

- A execução da dívida (Fase 2) acontece em PRs próprios, validados pelo gate (Docker).

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Estrutura: `.specify/templates/`, `.specify/scripts/`, `.claude/skills/speckit-*`
- Catálogo: `specs/README.md`; specs `000`–`130`; arquivo `specs/_legacy/`
- Docs: `docs/decisions.md` (ADR-008 governança SDD, ADR-015 storage, ADR-016 tipos OpenAPI)
- Entrega: PR #32 (`refactor/sdd-architecture` → `master`)

## Dívida de código documentada *(cross-cutting; não pertence a um único domínio)*

Dívidas transversais descobertas na exploração/vistoria, sem dono em uma spec de domínio:

- **DT-001**: `backend/app/core/contracts.py` (**1348 linhas**) concentra modelos Pydantic de todos os domínios num único arquivo. Direção: separar por bounded context (chat, files, agents, modeling, …). Esforço: L.
- **DT-002**: Lacunas de teste — rotas backend simples sem teste (`api/routes/agents.py`, `prompts.py`, `models.py`, `projects.py`); cobertura do frontend ~22%; fallback JSON→Postgres sem teste e2e (cruza com `070`). Direção: testes por rota/feature + paridade de stores. Esforço: M.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Dívida cross-cutting documentada (não executada aqui)
