# Plano de implementação: Agentes, Tools, Sandbox e Memória

**Pasta da spec**: `specs/050-agents-tools-runtime/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Consolida o legado `agents-tools` e registra dívida (DT-001..003).

## Resumo

Catálogo/runtime de tools (`tools/*`) com policy/segurança (`security/*`); JUDITE/agentes orquestram (`judite/`, `agents/`). Sandbox real, memória durável e workflows LangGraph são decisões aprovadas, ainda não implementadas.

## Contexto técnico

- **Storage**: Postgres (policies/memória/auditoria); diretório isolado por projeto no filesystem.
- **Tipo de projeto**: backend FastAPI · **Testes**: pytest.

## Constitution Check

- [x] P6 Autonomia com aprovação humana (núcleo desta spec).
- [x] P3 Preservar arquitetura (doc-only).
- [x] P9 Qualidade/PT-BR.

Sem violações.

## Estrutura

```text
backend/app/tools/      # catalog, runtime
backend/app/security/   # permissions, secrets
backend/app/judite/     # orchestrator
backend/app/agents/     # graph
backend/app/api/routes/ # tools.py, agents.py
```

## Estratégia / Ondas

1. Esta onda: consolidar spec + migrar legado + dívida.
2. Futuro: sandbox real; memória durável; LangGraph com checkpoints.

## Validação

- Doc-only: cross-links resolvem; legado em `_legacy/`. Futuro: `scripts/quality.ps1` + testes de policy/sandbox/rollback.

## Riscos e trade-offs

- Sandbox real é superfície de segurança — exige least privilege, timeout, limites e rollback (P6).

## Rastreamento de complexidade

Sem violações.
