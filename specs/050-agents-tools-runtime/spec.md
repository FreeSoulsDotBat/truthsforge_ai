# Especificação: Agentes, Tools, Sandbox e Memória

**Pasta da spec**: `specs/050-agents-tools-runtime/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Consolidar JUDITE/agentes, catálogo e runtime de tools, policy/segurança e memória operacional. **Migra e supersede** `specs/agents-tools/` (arquivada em `specs/_legacy/agents-tools/`).

> Onda 5 do refactor SDD. Documenta o contrato de agentes/tools e a dívida (sandbox real, memória durável, workflows LangGraph) — decisões ADR-005/009.

## Cenários de usuário e testes

### História 1 — Policy de tools por agente (Prioridade: P1) 🎯 MVP

Tools são executadas conforme policy (`allow`/`ask`/`deny`); adições podem autoexecutar, alterações/deleções exigem aprovação.

**Teste independente**: chamar uma tool de leitura segura (autoexecuta) e uma tool mutável (exige aprovação).

**Cenários de aceitação**:

1. **Dado** uma tool de leitura segura permitida, **Quando** chamada, **Então** o sistema executa sem aprovação.
2. **Dado** uma ação de alteração/deleção, **Quando** solicitada, **Então** o sistema exige aprovação humana antes de executar (ADR-009).

### História 2 — Orquestração multi-etapa (JUDITE) (Prioridade: P1)

JUDITE coordena workflows multi-etapa, delega contexto a especialistas e registra checkpoints.

**Cenários de aceitação**:

1. **Dado** uma tarefa multi-etapa, **Quando** iniciada, **Então** JUDITE delega contexto e registra checkpoints (`judite/orchestrator.py`, `agents/graph.py`).

### História 3 — Execução segura de tools (Prioridade: P1)

Tools de escrita/execução rodam em diretório isolado por projeto, com timeout/limites, auditoria e rollback.

### Casos de borda

- `python.run`/`filesystem.write` hoje retornam erro seguro até o sandbox real existir.
- Rede é permitida no sandbox do MVP.

## Requisitos

### Requisitos funcionais

- **RF-001**: QUANDO um agente solicitar tool sensível, O SISTEMA DEVE aplicar a policy por agente/domínio/tool (`security/permissions.py`, `tools/catalog.py`).
- **RF-002**: QUANDO a ação for adição permitida pela policy, O SISTEMA PODE executar sem aprovação. _(migrado)_
- **RF-003**: QUANDO a ação alterar/deletar estado, arquivos, artifacts ou recursos, O SISTEMA DEVE exigir aprovação humana antes de executar. _(migrado)_
- **RF-004**: QUANDO uma tool de escrita/execução rodar, O SISTEMA DEVE usar diretório isolado por projeto, com auditoria e rollback obrigatório quando aplicável (`tools/runtime.py`). _(migrado)_
- **RF-005**: QUANDO uma tarefa exigir múltiplas etapas, JUDITE DEVE coordenar o workflow e registrar checkpoints. _(migrado)_
- **RF-006**: QUANDO JUDITE/agentes aprenderem contexto útil, O SISTEMA DEVE persistir memória durável (preferências, decisões, histórico resumido, contexto por projeto). _(migrado)_

### Requisitos não funcionais

- **RNF-001**: Rede permitida no sandbox do MVP; timeouts iniciais 60s (curto) / 5min (jobs longos); limites 100MB por artifact / 500MB por workspace, ajustáveis. _(migrado)_
- **RNF-002**: Policies rastreáveis por agente, domínio e tool.

## Critérios de sucesso

- **CS-001**: Nenhuma alteração/deleção executa sem aprovação humana.
- **CS-002**: Toda tool call mutável gera auditoria e tem rollback quando aplicável.

## Premissas

- Fora do escopo imediato: marketplace externo de tools (migrado).

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `backend/app/tools/catalog.py`, `tools/runtime.py`; `backend/app/security/permissions.py`, `secrets.py`; `backend/app/judite/orchestrator.py`, `backend/app/agents/graph.py`; `backend/app/api/routes/tools.py`, `agents.py`
- Docs: `docs/decisions.md` (ADR-005, ADR-009), `docs/implementation-plan.md`, `AGENTS.md`
- Testes: `backend/tests/test_agent_orchestration.py`, `test_tool_registry.py`
- Legado migrado: `specs/_legacy/agents-tools/`
- Specs relacionadas: `specs/010-chat-orchestration/`, `specs/060-cost-audit-governance/`

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: Sandbox real ausente — `python.run`/`filesystem.write` retornam erro seguro (`backend/app/tools/runtime.py`; `docs/architecture.md`). Direção: sandbox por projeto com rede/timeout/limites/rollback. Esforço: L.
- **DT-002**: Memória durável de JUDITE/agentes não implementada. Direção: persistência de memória ampla (ADR-009). Esforço: L.
- **DT-003**: Workflows LangGraph com checkpoints humanos pendentes (ADR-005). Esforço: L.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Conteúdo do legado migrado; dívida documentada
