# Desenvolvimento Local

## Observabilidade do módulo de modelagem 3D

O backend emite logs JSON estruturados e persiste eventos de trace em `modeling_trace_events` para todo o fluxo de modelagem 3D (planner → executor → MCP → Fusion/Blender). Ver o plano em `C:\Users\Jonatan\.claude\plans\para-que-seja-mais-immutable-puffin.md`.

### Flags

- `TRUTHS_FORGE_MODELING_OBSERVABILITY_ENABLED` (default `true`) — habilita persistência e logging estruturado. Desligar reduz I/O.
- `TRUTHS_FORGE_MODELING_DEBUG_LLM_TRACE` (default `false`) — quando `true`, eventos `planner.llm_request`/`response` incluem prompt completo e resposta bruta. Ativar só para debug.

### Visualizar logs com filtro por trace_id

```powershell
docker logs truths-forge-backend --since 10m | jq 'select(.trace_id == "<trace_id>")'
```

### UI opt-in: dozzle (perfil observability)

```powershell
docker compose --env-file infra\.env -f infra\docker-compose.yml -f infra\docker-compose.dev.yml --profile observability up -d dozzle
# UI em http://127.0.0.1:8082 — busca por trace_id no campo de filtro.
```

### Smoke test rápido

```powershell
pwsh scripts/smoke-modeling-trace.ps1
```

### Endpoints

- `GET /api/3d/plans/{plan_id}/trace?level=warn,error&source=backend,fusion` — eventos de trace de um plano.
- `GET /api/3d/traces/{trace_id}` — eventos por trace_id (vindo do SSE `modeling_plan` ou de logs).
- `POST /api/3d/traces/events` — registra evento UI, força `source="ui"` no backend, trunca payloads grandes, atribui `sequence` server-side e aplica rate-limit 60/min por IP + `trace_id`.
- `GET /api/3d/plans/{plan_id}/diagnostics` — bundle consolidado (plano + tool calls + trace + printability).

O endpoint de evento UI usa `get_max_trace_sequence(trace_id)` na store para calcular o próximo `sequence` sem carregar a timeline inteira. `PostgresStore` faz `MAX((payload->>'sequence')::int)` e `DevStore` calcula o máximo sobre o ring buffer JSON. Os buckets do rate-limit são limpos quando ficam obsoletos para evitar crescimento ilimitado por `trace_id` único.

## Preflight

Execute:

```powershell
.\scripts\check-env.ps1
```

No ambiente Windows local, Docker Desktop e Git sao obrigatorios para o fluxo containerizado. `npm`/`pnpm`, Rust/Cargo e ADB so precisam estar no PATH quando for rodar host mode, empacotar desktop ou sincronizar Android fora dos containers.

Em ambientes sem Docker, como execucoes automatizadas do Devin, o backend tambem roda em host mode com Python 3.11+ e o frontend com pnpm:

```bash
pip install -e "backend[dev]"
pnpm install --frozen-lockfile
```

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

Se a porta `8080` ja estiver ocupada, ajuste `PGADMIN_PORT` em `infra/.env` para uma porta livre, por exemplo `PGADMIN_PORT=18080`, e rode `dev.ps1` novamente.

- Postgres porta direta: `127.0.0.1:5432`
- Qdrant porta direta: `127.0.0.1:6333`
- Valkey porta direta: `127.0.0.1:6379`

## Modos de storage

O modo recomendado para uso real local e o stack completo em containers:

```powershell
$env:TRUTHS_FORGE_STORAGE_BACKEND="postgres"
```

Use esse modo quando quiser validar persistencia como producao local. Se o Postgres nao
conectar, o backend deve falhar em vez de mascarar o problema.

Para desenvolvimento leve sem Docker, deixe o default:

```powershell
$env:TRUTHS_FORGE_STORAGE_BACKEND="auto"
```

Nesse modo o backend tenta Postgres e cai para o dev store JSON quando o banco nao esta
disponivel. O fallback JSON serve para testes, demos e trabalho rapido; nao e formato de
producao, backup ou sincronizacao mobile.

Para testes isolados, use:

```powershell
$env:TRUTHS_FORGE_STORAGE_BACKEND="json"
```

O RAG real continua esperando Qdrant. Sem Qdrant, algumas buscas podem operar como scaffold
ou retornar vazio.

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

Para testar o Fusion 360 real, abra o Fusion, habilite **Fusion MCP Server** e
confirme a porta exibida pelo aplicativo:

```text
http://127.0.0.1:27182/mcp
```

O backend usa esse endpoint por padrão via `TRUTHS_FORGE_FUSION_MCP_URL`. No
Docker de desenvolvimento, o compose aponta para `http://host.docker.internal:27182/mcp`
para alcançar o Fusion aberto no Windows. Se a porta mudar no aplicativo,
ajuste a variável:

```powershell
$env:TRUTHS_FORGE_FUSION_MCP_URL="http://127.0.0.1:27182/mcp"
```

Mesmo usando o MCP oficial do Fusion, o backend continua bloqueando script livre
de LLM: ele só traduz tools `fusion.*` allowlistadas para scripts determinísticos
do próprio backend. O add-in legado em `apps/fusion-addin/` permanece como
fallback por discovery file/socket local.

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

Em host mode sem Docker:

```bash
pushd backend
python -m pytest -q
popd
pnpm --filter @truths-forge/web test:unit
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

Equivalente em host mode sem Docker:

```bash
python -m ruff format --check backend/app backend/tests
python -m ruff check backend/app backend/tests
pushd backend && python -m pytest -q && popd
pnpm --filter @truths-forge/web format:check
pnpm --filter @truths-forge/web lint
pnpm --filter @truths-forge/web test:unit
pnpm --filter @truths-forge/web typecheck
pnpm --filter @truths-forge/web build
pnpm --filter @truths-forge/docs build
```

## Modo host opcional

O modo host continua possivel para debugging pontual, mas nao e o fluxo recomendado. Use apenas se quiser rodar `uvicorn` ou `pnpm dev:web` diretamente no Windows.
