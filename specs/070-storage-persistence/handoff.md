# handoff.md

Continuidade entre agentes para `070-storage-persistence`.

## Estado atual

- Onda 7 concluída (doc-only): spec/plan/tasks + `research.md` com proposta ADR-015.
- Dívida prioritária registrada: DT-001 (1752+1638 linhas duplicadas sem Protocol), DT-002 (factory sem interface), DT-003 (fallback sem teste e2e).
- **ADR-015 ratificado** em `docs/decisions.md`. Fase 2 fase-1 feita: teste de paridade `backend/tests/test_store_parity.py` (PostgresStore 76 × DevStore 71 métodos públicos; 5 só-Postgres allowlistados como infra), validado com ruff format/check + pytest no container.

## Pendências

- Fase 2 restante: extrair `Protocol Store` (T011) e fatiar repositórios por domínio (T013) — mudam código de produção, exigem o gate (Docker) e PR próprio.
