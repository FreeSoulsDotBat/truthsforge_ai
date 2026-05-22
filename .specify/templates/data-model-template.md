# Modelo de dados: [NOME DA FEATURE]

**Pasta da spec**: `specs/[NNN-slug]/` | **Data**: [DATA]

> Opcional. Use quando a feature envolver entidades persistidas. Reflita o storage real (Postgres principal; Qdrant p/ vetores; fallback JSON apenas dev/test — ver P5 da constituição). Saída da fase 1 do `plan`.

## Entidades

### [Entidade]

- **Representa**: [o quê]
- **Campos**: [nome: tipo — restrição] (marque `JSONB` quando aplicável)
- **Relações**: [com outras entidades]
- **Persistência**: Postgres (`storage/postgres_store.py`) / Qdrant / filesystem
- **Auditoria**: [eventos auditáveis associados, se houver]

## Migrações

- [Impacto em schema; backfill; compatibilidade com chats/dados existentes.]

## Espelho no fallback JSON (dev/test)

- [Como `storage/dev_store.py` representa a mesma entidade — paridade obrigatória.]
