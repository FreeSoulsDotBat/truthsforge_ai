# Especificação: Persistência e Abstração de Storage

**Pasta da spec**: `specs/070-storage-persistence/` | **Criada em**: 2026-05-22 | **Status**: Aprovada (ADR-015 ratificado)

**Entrada**: Cobrir a camada de storage (Postgres + fallback JSON) — dívida prioritária do backend. A abstração agora tem decisão registrada (ADR-015).

> Onda 7 do refactor SDD. Documenta o contrato de storage e a dívida de duplicação massiva; registra **ADR-015** (interface de storage), **ratificado** em `docs/decisions.md`; ver `research.md`. Implementação faseada pendente do gate (Docker).

## Cenários de usuário e testes

### História 1 — Persistência transacional confiável (Prioridade: P1) 🎯 MVP

Todos os domínios persistem estado via uma camada de storage; Postgres em uso real, JSON só dev/test.

**Teste independente**: rodar a suíte de store contra Postgres; rodar contra dev-store; comportamento equivalente.

**Cenários de aceitação**:

1. **Dado** Postgres disponível, **Quando** um domínio persiste/recupera, **Então** usa `PostgresStore` (`storage/postgres_store.py`).
2. **Dado** Postgres indisponível em dev/test, **Quando** o factory escolhe o store, **Então** usa o dev-store JSON (`storage/store.py`, `dev_store.py`).

### História 2 — Paridade entre stores (Prioridade: P1)

Os dois stores expõem a mesma superfície de métodos; mudanças devem manter paridade.

### Casos de borda

- JSON nunca é destino de produção nem caminho de sync (ADR-004, P5).
- Payloads JSONB aceitos no MVP; rotas quentes a normalizar com volume.

## Requisitos

### Requisitos funcionais

- **RF-001**: O SISTEMA DEVE prover uma camada de storage única consumida pelos domínios via `get_store()` (`backend/app/storage/store.py`).
- **RF-002**: QUANDO Postgres estiver disponível, O SISTEMA DEVE usá-lo como store transacional; SENÃO, em dev/test, DEVE cair no dev-store JSON.
- **RF-003**: `PostgresStore` e o dev-store DEVEM expor a mesma superfície de métodos (paridade).
- **RF-004**: QUANDO um método de storage mudar de assinatura, ambos os stores DEVEM ser atualizados juntos (até a abstração existir).

### Requisitos não funcionais

- **RNF-001**: Postgres é produção; JSON só dev/test (ADR-004, P5).
- **RNF-002**: Rotas quentes (mensagens, chunks/documentos, auditoria, permissões, tool calls, retenção) DEVEM ser normalizáveis quando houver volume.

## Critérios de sucesso

- **CS-001**: A suíte de store passa contra Postgres e dev-store com o mesmo contrato.
- **CS-002**: Não há divergência silenciosa entre os dois stores (garantida por testes de paridade — futuro).

## Premissas

- A abstração (Protocol/repositórios) é alvo de ADR-015 (proposta), pendente de aprovação.

## Fontes

- Constituição: `.specify/memory/constitution.md`
- Código: `backend/app/storage/store.py`, `postgres_store.py`, `dev_store.py`, `__init__.py`
- Docs: `docs/decisions.md` (ADR-004), `docs/architecture.md`
- Testes: `backend/tests/test_postgres_store.py`, `test_alembic_migrations.py`
- Proposta: `./research.md` (ADR-015)
- Specs relacionadas: todas as ondas (storage é transversal)

## Dívida de código documentada *(não executar nesta frente)*

- **DT-001**: `postgres_store.py` (1752 linhas) e `dev_store.py` (1638 linhas) duplicam ~46 métodos sem `Protocol`/`ABC` — toda mudança exige editar dois lugares (risco de divergência). Direção: ADR-015 (interface `Store` + repositórios por domínio). Esforço: L.
- **DT-002**: `storage/store.py` (31 linhas) é um factory com fallback manual, sem interface explícita. Direção: tipar via `Protocol`. Esforço: S.
- **DT-003**: Fallback Postgres→JSON não tem teste end-to-end. Direção: testes de paridade rodando a mesma suíte nos dois stores. Esforço: M.

## Verificação de qualidade da spec

- [x] Requisitos testáveis (EARS) com Fontes válidas
- [x] Constituição referenciada
- [x] Dívida documentada; ADR-015 proposto (não ratificado)
