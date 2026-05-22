# Especificação: Custo, Auditoria e Observabilidade

**Pasta da spec**: `specs/060-cost-audit-governance/` | **Criada em**: 2026-05-22 | **Status**: Rascunho

**Entrada**: Consolidar Cost Governor, auditoria e os golden paths/eventos auditáveis. **Migra e supersede** o legado `observability-quality` (arquivada em `specs/_legacy/observability-quality/`).

> Onda 6 do refactor SDD. Documenta governança de custo e auditoria transversais; registra dívida (schema/retentção de auditoria, golden paths).

## Cenários de usuário e testes

### História 1 — Governança de custo (Prioridade: P1) 🎯 MVP

O sistema estima custo (preflight), bloqueia quando a política exige e registra o gasto.

**Teste independente**: enviar com orçamento estourado → bloqueio + auditoria `chat.blocked`.

**Cenários de aceitação**:

1. **Dado** uma política de custo, **Quando** há envio, **Então** o sistema estima custo (`cost_governor/service.py`) e bloqueia se exceder, expondo uso em `api/routes/cost.py`.

### História 2 — Eventos auditáveis obrigatórios (Prioridade: P1)

Fluxos críticos geram eventos auditáveis (`audit/service.py`, `api/routes/audit.py`).

**Cenários de aceitação**:

1. **Dado** uma chamada LLM/tool/acesso a documento/export/delete/pairing/indexação, **Quando** ocorre, **Então** o sistema registra evento auditável.

### História 3 — Golden paths (Prioridade: P2)

Mudanças relevantes são validadas por golden paths visuais/e2e.

### Casos de borda

- Falha de indexação deve ser auditável (cruza com `040-import-workers-queues`).

## Requisitos

### Requisitos funcionais

- **RF-001**: QUANDO houver envio, O SISTEMA DEVE estimar custo e aplicar a política mensal (`cost_governor/service.py`).
- **RF-002**: O SISTEMA DEVE registrar eventos auditáveis de: chamadas LLM, custo/uso, tool calls, acesso a documentos, export/delete, pareamento mobile e falhas de indexação. _(migrado)_
- **RF-003**: O SISTEMA DEVE expor uso/custo via `api/routes/cost.py` e eventos via `api/routes/audit.py`.
- **RF-004**: O SISTEMA DEVE manter golden paths obrigatórios: chat, RAG com base, upload/indexação, agente restrito, 3D e mobile. _(migrado)_

### Requisitos não funcionais

- **RNF-001**: Auditoria é local e mínima por chamada (P9; `docs/infra-observability.md`).
- **RNF-002**: Schema de auditoria DEVE convergir para um formato padronizado com retenção definida.

## Critérios de sucesso

- **CS-001**: Todo evento da lista obrigatória aparece na auditoria.
- **CS-002**: Nenhuma mudança relevante entra sem o golden path correspondente avaliado.

## Premissas

- Cost Governor inicial já existe; golden paths são parcialmente manuais.

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `backend/app/cost_governor/service.py`, `backend/app/audit/service.py`; `backend/app/api/routes/cost.py`, `audit.py`
- Docs: `docs/infra-observability.md`, `docs/delivery-checklist.md`, `docs/decisions.md` (ADR-008)
- Testes: `backend/tests/test_runtime_routes.py`
- Legado migrado: `specs/_legacy/observability-quality/`
- Specs relacionadas: `specs/010-chat-orchestration/`, `specs/050-agents-tools-runtime/`, `specs/040-import-workers-queues/`

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: Schema de auditoria não padronizado; retenção não consolidada (`specs/000-repo-foundation/tasks.md`). Direção: schema único + política de retenção (1 ano) + índices. Esforço: M.
- **DT-002**: Mapeamento de lacunas de auditoria por evento obrigatório pendente. Direção: matriz evento→código→teste. Esforço: S.
- **DT-003**: Golden paths (chat/RAG/upload/agente restrito/3D/mobile) não automatizados. Direção: e2e por golden path. Esforço: L.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Conteúdo do legado migrado; dívida documentada
