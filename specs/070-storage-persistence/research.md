# Pesquisa: Abstração de Storage — proposta de ADR-015

**Pasta da spec**: `specs/070-storage-persistence/` | **Data**: 2026-05-22

> **Proposta, NÃO ratificada.** Ratificar um ADR exige registro em `docs/decisions.md` + aprovação do dono do produto (constituição P2/governança). Este documento apenas instrui a decisão.

## Pergunta em aberto

Como eliminar a duplicação de ~46 métodos entre `postgres_store.py` (1752 linhas) e `dev_store.py` (1638 linhas) sem trocar a stack (P5: Postgres é produção; JSON só dev/test)?

## Proposta de decisão (ADR-015)

- **Decisão proposta**: introduzir uma interface `Store` (via `typing.Protocol`) descrevendo a superfície atual; opcionalmente quebrar em repositórios por domínio (chat, files, agents, cost, audit, modeling). `PostgresStore` e `DevStore` passam a implementar a mesma interface; `store.py` retorna o tipo `Store`.
- **Alternativas consideradas**:
  - Manter duplicação (status quo) — rejeitada: divergência silenciosa contínua.
  - ABC com herança compartilhada — possível, mas Protocol é menos intrusivo e casa com o estilo atual.
  - Trocar storage (ORM único) — rejeitada: viola P2 (stack invariável sem ADR/aprovação).
- **Rationale**: reduz risco de divergência, melhora testabilidade (mock por Protocol) e habilita testes de paridade — sem mudar a stack.

## Plano de migração sugerido (futuro, faseado)

1. Extrair `Protocol Store` a partir da superfície atual (sem mudar implementações).
2. Tipar `get_store()` como `Store`; ajustar consumidores para depender do Protocol.
3. Criar testes de paridade que rodam a mesma suíte contra `PostgresStore` e `DevStore`.
4. (Opcional) Fatiar em repositórios por domínio, um por vez, com testes.

## Impacto na dívida documentada

- Resolve DT-001/DT-002/DT-003 desta spec. Cada fase nasce de uma task e exige aprovação do dono antes de mexer no código (P3/P6).
