# Backend migrations (Alembic)

ADR-013 adota Alembic como ferramenta canônica de migrações. As migrações vivem
em `backend/migrations/versions/` e são numeradas para alinhar com as ondas da
refatoração 3D chat-first:

| Versão | Onda | Conteúdo |
|---|---|---|
| `001_initial_baseline` | 1.4 | Espelha o estado atual produzido por `PostgresStore.init_schema()`. Idempotente (todas as DDLs usam `CREATE … IF NOT EXISTS`). |
| `002_chats_title_not_null` | 2 | `chats.title NOT NULL` + backfill `"Sem título - YYYY-MM-DD"` (ADR-014). |
| `003_chats_modeling_fields` | 2 | Índices funcionais sobre `payload JSONB` (`payload->>'is_modeling_3d'`, `payload->>'modeling_stage'`, `payload->>'modeling_plan_id'`). **Não cria colunas** — os campos vivem dentro do `payload` (ADR-004). |
| `004_modeling_plans_kind` | 1.4 | Índices em `payload->>'kind'` e `payload->>'parent_plan_id'` para queries de planos `primary` vs `edit`. **Revisão `head` atual.** |
| `005_drop_legacy_modes` | pós-Onda-3 | **Planejada / não implementada.** Drop opcional dos campos `mode` e `approval_required` no payload do plano. Quando criada, encadear `down_revision` a partir de `004`. |

## Convivência com `init_schema()`

Durante as Ondas 1–3, `PostgresStore.init_schema()` continua sendo invocado no
boot do backend. Como cada DDL é idempotente, rodar `alembic upgrade head` em
seguida (ou antes) não causa conflito.

A migração final (Onda 6) vai mover toda a lógica de schema para Alembic e
remover `init_schema()`.

## Como rodar

```powershell
# do diretório backend/
alembic upgrade head
```

Para apontar para um banco específico sem mexer em variáveis de ambiente:

```powershell
alembic -x url=postgresql://user:pass@host:5432/dbname upgrade head
```

## Como adicionar uma nova revisão

```powershell
alembic revision -m "<descricao>"
```

A numeração manual nesta refator (1.4, 2, etc.) significa que você deve
**renomear** o arquivo gerado para refletir a versão correta antes de
commit. Isso pode ser substituído por timestamps quando a Onda 6 fechar o
script Alembic como única fonte de schema.
