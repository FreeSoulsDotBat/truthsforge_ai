# Plano de implementação: Persistência e Abstração de Storage

**Pasta da spec**: `specs/070-storage-persistence/` | **Data**: 2026-05-22 | **Spec**: `./spec.md`

> Doc-only. Documenta a camada de storage e registra a dívida prioritária; propõe ADR-015 (`research.md`).

## Resumo

`store.py` (31 linhas) é um factory que escolhe entre `PostgresStore` (1752) e `DevStore` (1638), 100% duplicados e sem interface. A proposta ADR-015 introduz um `Protocol Store` + testes de paridade.

## Contexto técnico

- **Storage**: Postgres (produção), JSON (dev/test) — ADR-004.
- **Tipo de projeto**: backend FastAPI (transversal) · **Testes**: pytest.

## Constitution Check

- [x] P5 Postgres-prod / JSON dev-only (núcleo).
- [x] P2 Stack invariável — proposta não troca stack; só abstrai.
- [x] P3 Preservar arquitetura (doc-only nesta onda).

Sem violações. (Mudança de stack seria violação — explicitamente rejeitada na proposta.)

## Estrutura

```text
backend/app/storage/   # store.py (factory), postgres_store.py, dev_store.py
```

## Estratégia / Ondas

1. Esta onda: spec + dívida + proposta ADR-015 (research.md).
2. Futuro (após aprovação do ADR): Protocol Store → testes de paridade → repositórios por domínio.

## Validação

- Doc-only: cross-links resolvem. Futuro: `test_postgres_store.py` + nova suíte de paridade verde nos dois stores.

## Riscos e trade-offs

- Refatorar storage é alto risco (transversal). Mitigação: Protocol primeiro (sem mudar implementações), testes de paridade antes de fatiar.

## Rastreamento de complexidade

Sem violações.
