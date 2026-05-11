# Desenvolvimento Local

## Preflight

Execute:

```powershell
.\scripts\check-env.ps1
```

No momento do bootstrap, foram detectados Docker e Git. `npm`, Rust/Cargo e ADB precisam estar no PATH antes de empacotar frontend/desktop/mobile.

## Modo recomendado: tudo em containers

```powershell
.\scripts\dev.ps1
```

Servicos:

- Web: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- Documentacao Docusaurus: `http://127.0.0.1:3000`
- pgAdmin/Postgres: `http://localhost:8080`
- Redis Commander/Valkey: `http://127.0.0.1:8081`
- Qdrant dashboard: `http://127.0.0.1:6333/dashboard`
- Postgres porta direta: `127.0.0.1:5432`
- Qdrant porta direta: `127.0.0.1:6333`
- Valkey porta direta: `127.0.0.1:6379`

Se o pgAdmin recusar o login apos alteracoes em `infra/.env`, ou se o servidor Postgres nao aparecer no painel esquerdo, rode `.\scripts\reset-pgadmin.ps1`.

## Deep Research

O atalho `Pesquisa OpenAI` usa `openai/deep-research`, configurado por padrao como `o4-mini-deep-research`. Ele roda no backend com Responses API, `web_search_preview`, `background=true` e limite de chamadas ajustavel no composer do chat.

Para testar com provedor real, configure a API key da OpenAI no app ou em `backend/.env`. O frontend nunca chama a OpenAI diretamente.

## Modelagem 3D local

O modulo `3D` usa MCP local com fallback mock. Para testar o Blender real fora do container, configure:

```powershell
$env:TRUTHS_FORGE_BLENDER_EXECUTABLE="C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"
```

O backend executa apenas ferramentas Blender allowlistadas em background e salva `.blend`/`.stl` em `.local/modeling`, registrando os artefatos em `Arquivos`.

Comando manual equivalente:

```powershell
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml up --build -d
```

Para logs:

```powershell
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml logs -f backend web docs
```

## Testes

```powershell
.\scripts\test-container.ps1
```

## Qualidade e pre-commit

O projeto tem uma rotina unica de qualidade para backend e frontend:

```powershell
.\scripts\quality.ps1
```

Ela roda no Docker:

- Backend: `ruff format --check`, `ruff check` e `pytest`.
- Frontend: `prettier --check`, `eslint`, `vitest run` e `tsc --noEmit`.

Para aplicar fixes automaticos de format/lint:

```powershell
.\scripts\quality.ps1 -Fix
```

Para preparar o Git hook local:

```powershell
.\scripts\install-git-hooks.ps1
```

Isso configura `core.hooksPath=.githooks`; o hook `.githooks/pre-commit` chama `scripts/quality.ps1` antes de cada commit.

Ou manualmente:

```powershell
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T backend python -m pytest
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T backend python -m ruff format --check app tests
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T backend python -m ruff check app tests
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T web pnpm --filter @truths-forge/web format:check
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T web pnpm --filter @truths-forge/web lint
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T web pnpm --filter @truths-forge/web test:unit
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T web pnpm --filter @truths-forge/web typecheck
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T web pnpm build:web
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml exec -T docs pnpm build:docs
```

## Modo host opcional

O modo host continua possivel para debugging pontual, mas nao e o fluxo recomendado. Use apenas se quiser rodar `uvicorn` ou `pnpm dev:web` diretamente no Windows.
