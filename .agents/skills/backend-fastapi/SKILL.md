---
name: backend-fastapi
description: Use ao alterar backend Python, rotas FastAPI, contratos Pydantic, storage, providers LLM, workers ou políticas de domínio.
---

## Objetivo

Trabalhar no backend sem romper a arquitetura atual do projeto.

## Sempre consultar primeiro

- `backend/pyproject.toml`
- `backend/app/main.py`
- `backend/app/api/router.py`
- `docs/application-map.md`
- `docs/architecture.md`
- `specs/000-repo-foundation/spec.md`

## Regras

- Preserve prefixos de rota e fronteiras de domínio.
- Prefira mudanças orientadas a serviço/rota/teste.
- Atualize `backend/tests` quando contrato ou comportamento mudar.
- Se tocar storage, explicite impacto em modos `postgres`, `auto` e `json`.
- Se tocar providers LLM, preserve a separação entre provider real e provider dev.

## Checklist de entrega

- rotas atualizadas;
- tipos/contratos coerentes;
- testes cobrindo o comportamento;
- docs/spec alinhadas.
