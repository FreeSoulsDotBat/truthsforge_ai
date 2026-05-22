# Plano de implementação: Custo, Auditoria e Observabilidade

**Pasta da spec**: `specs/060-cost-audit-governance/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Consolida o legado `observability-quality` e registra dívida (DT-001..003).

## Resumo

Cost Governor (`cost_governor/service.py`) faz preflight/registro de custo; auditoria (`audit/service.py`) registra eventos críticos. Golden paths e schema/retentção de auditoria são alvos de evolução.

## Contexto técnico

- **Storage**: Postgres (eventos de auditoria, políticas de custo).
- **Tipo de projeto**: backend FastAPI (transversal) · **Testes**: pytest + e2e (futuro).

## Constitution Check

- [x] P9 Qualidade obrigatória (gates + checklist) — núcleo transversal.
- [x] P6/P7 auditoria de tools e acesso a documentos.
- [x] P3 Preservar arquitetura (doc-only).

Sem violações.

## Estrutura

```text
backend/app/cost_governor/  # service.py
backend/app/audit/          # service.py
backend/app/api/routes/     # cost.py, audit.py
```

## Estratégia / Ondas

1. Esta onda: consolidar spec + migrar legado + dívida.
2. Futuro: padronizar schema de auditoria + retenção; matriz de lacunas; e2e dos golden paths.

## Validação

- Doc-only: cross-links resolvem; legado em `_legacy/`. Futuro: `scripts/quality.ps1` + e2e por golden path.

## Riscos e trade-offs

- Padronizar schema de auditoria pode exigir migração de eventos existentes.

## Rastreamento de complexidade

Sem violações.
