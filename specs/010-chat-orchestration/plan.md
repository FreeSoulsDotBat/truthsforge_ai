# Plano de implementação: Orquestração de Chat (núcleo)

**Pasta da spec**: `specs/010-chat-orchestration/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Esta onda é **doc-only**: descreve o estado atual e registra a dívida. A extração de service layer fica como trabalho futuro (DT-001..003), guiado por esta spec.

## Resumo

O chat é orquestrado por `backend/app/api/routes/chat.py` (2433 linhas), que coordena agentes, contexto/RAG, cost governor, gateway LLM, modos especiais e persistência/auditoria, com bifurcação para 3D (ADR-013) e gate de título (ADR-014).

## Contexto técnico

- **Linguagem/Versão**: Python 3.11
- **Dependências principais**: FastAPI, SSE (StreamingResponse), llm_gateway
- **Storage**: Postgres (sessões/mensagens/auditoria); fallback JSON dev/test
- **Testes**: pytest (`backend/tests/test_chat_*.py`)
- **Tipo de projeto**: backend FastAPI

## Constitution Check

- [x] P3 Preservar arquitetura — onda apenas documenta; sem mudança de comportamento.
- [x] P4 Spec/Doc rastreável — esta spec passa a cobrir o domínio antes sem spec.
- [x] P6 Aprovação humana — bifurcação 3D e modos destrutivos permanecem fora deste núcleo.
- [x] P9 Qualidade/PT-BR — gates inalterados (doc-only).

Sem violações a justificar.

## Estrutura

```text
backend/app/api/routes/chat.py     # núcleo atual (monólito)
backend/app/chat/                  # destino futuro do service layer (hoje só session_cleanup.py)
```

## Estratégia / Ondas

1. Esta onda: spec + registro de dívida (DT-001..003).
2. Futuro (não nesta frente): extrair `chat/orchestrator.py`, `chat/context.py`, `chat/sse.py`, `chat/special_modes.py`; rota fina com `Depends()`. Cada extração nasce de tasks desta spec, com testes de regressão do contrato SSE.

## Validação

- Doc-only: `git diff --check`; cross-links de Fontes resolvem (todos os caminhos existem).
- Quando a extração futura ocorrer: `scripts/quality.ps1` (ruff+pytest) verde e testes `test_chat_*` preservados.

## Riscos e trade-offs

- Risco: extrair o monólito pode alterar o contrato SSE. Mitigação: testes de contrato SSE antes de mover código.

## Rastreamento de complexidade

Sem violações.
