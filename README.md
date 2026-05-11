# Truth's Forge AI

Aplicacao pessoal local-first para chat multi-modelo, JUDITE, agentes, RAG, biblioteca de prompts e artifacts/canvas.

Este repositorio comeca pelo ambiente de desenvolvimento local:

- `backend/`: FastAPI em Python, contratos centrais e APIs iniciais.
- `apps/web/`: React + Vite + TypeScript, UI responsiva mobile-first.
- `apps/desktop/`: scaffold Tauri para empacotar o frontend no Windows.
- `apps/mobile/`: scaffold Capacitor para Android.
- `infra/`: Docker Compose com PostgreSQL/pgvector, Qdrant e Valkey.
- `.local/`: dados locais de desenvolvimento, ignorados pelo Git.

## Estado atual

O bootstrap implementa M0 e a base de M1/M4: endpoints iniciais, streaming SSE, Postgres como storage principal no modo container, Qdrant/Valkey, ingestao RAG inicial de texto/Markdown, UI inicial, biblioteca de arquivos com CRUD e galeria, Cost Governor, auditoria, configuracao cifrada de API keys, documentacao, importacao de historico do ChatGPT, atalho de Deep Research via OpenAI Responses API, resumo oficial de raciocinio como modo opt-in e um primeiro modulo de modelagem 3D via MCP local. O Blender ja tem adapter seguro por subprocesso quando `TRUTHS_FORGE_BLENDER_EXECUTABLE` aponta para o executavel local; sem isso, fica em modo mock/auditavel. As integracoes reais com OpenAI, Anthropic e Google ja ficam atras do `LLMProvider`; sem chaves/model IDs configurados, o backend usa o provider dev para manter o fluxo local funcionando.

## Requisitos locais

- Docker Desktop.
- Git.
- Python/Node/pnpm podem rodar dentro dos containers de desenvolvimento.
- Rust/Cargo para Tauri e Android SDK/ADB para Capacitor so sao necessarios quando for empacotar desktop/mobile fora do container.

## Desenvolvimento em containers

```powershell
.\scripts\dev.ps1
```

Ou manualmente:

```powershell
docker compose --env-file infra\.env.example -f infra\docker-compose.yml -f infra\docker-compose.dev.yml up --build -d
```

URLs:

- Web: http://127.0.0.1:5173
- Backend: http://127.0.0.1:8000
- API docs: http://127.0.0.1:8000/docs
- Project docs: http://127.0.0.1:3000
- Postgres/pgAdmin UI: http://localhost:8080
- Redis/Valkey UI: http://127.0.0.1:8081
- Qdrant UI: http://127.0.0.1:6333/dashboard

Testes:

```powershell
.\scripts\test-container.ps1
```

Qualidade antes de commit:

```powershell
.\scripts\quality.ps1
.\scripts\install-git-hooks.ps1
```

O hook preparado em `.githooks/pre-commit` roda format check, lint e testes unitarios do backend/frontend dentro dos containers.
