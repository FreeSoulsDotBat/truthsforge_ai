# Truth's Forge AI

Aplicacao pessoal local-first para chat multi-modelo, JUDITE, agentes, RAG, biblioteca de prompts, arquivos, importacao do ChatGPT, geracao de imagens e modelagem 3D local.

Este repositorio comeca pelo ambiente de desenvolvimento local:

- `backend/`: FastAPI em Python, contratos centrais, workers locais e APIs do produto.
- `apps/web/`: React + Vite + TypeScript, UI responsiva mobile-first.
- `apps/desktop/`: scaffold Tauri para empacotar o frontend no Windows.
- `apps/mobile/`: scaffold Capacitor para Android.
- `apps/docs/`: documentacao do produto em Docusaurus.
- `apps/fusion-addin/`: add-in Python para Fusion 360 (modelagem 3D supervisionada); nao e pacote pnpm.
- `packages/`: pacotes compartilhados do workspace (`types`, `ui`); espacos reservados.
- `infra/`: Docker Compose com PostgreSQL/pgvector, Qdrant e Valkey.
- `specs/`: specs SDD no padrao GitHub Spec Kit (pastas `NNN-<slug>`); legado congelado em `specs/_legacy/`.
- `.specify/`: constituicao, templates e scripts do Spec Kit.
- `.agents/skills/`: procedimentos versionados para agentes e humanos trabalharem por bounded context.
- `.claude/skills/speckit-*`: fases do fluxo SDD (specify/plan/tasks/implement) para Claude Code.
- `.local/`: dados locais de desenvolvimento, ignorados pelo Git.

## Estado atual

O bootstrap implementa M0 e avancou em M1/M4/M5/M7: streaming SSE, titulo obrigatorio antes da primeira mensagem, Postgres como storage principal no modo container, fallback JSON para desenvolvimento leve, Qdrant/Valkey, biblioteca de arquivos com upload/download/CRUD/paginacao, indexacao em background, parsing de PDF/Markdown/TXT/CSV/DOCX/HTML e OCR opcional de imagens, bases de conhecimento curadas, projetos/pastas, agentes com politicas de ferramentas, Cost Governor, auditoria, configuracao cifrada de API keys, importacao de historico do ChatGPT, anexos no chat, geracao de imagem via OpenAI Images API, atalho de Deep Research via OpenAI Responses API, resumo oficial de raciocinio como modo opt-in e modo multiagente por contexto de apoio. O modulo de modelagem 3D via MCP local tambem esta funcional: Blender executa ferramentas allowlistadas quando `TRUTHS_FORGE_BLENDER_EXECUTABLE` aponta para o executavel local, Fusion 360 conversa com um add-in desktop via loopback quando instalado, e ambos caem para mock/auditoria quando o adapter real nao esta conectado. As integracoes reais com OpenAI, Anthropic e Google ficam atras do `LLMProvider`; sem chaves/model IDs configurados, o backend usa o provider dev para manter o fluxo local funcionando quando permitido.

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

Se a porta `8080` ja estiver ocupada, ajuste `PGADMIN_PORT` em `infra/.env` para uma porta livre, por exemplo `PGADMIN_PORT=18080`, e rode `dev.ps1` novamente.

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

## SDD e colaboração multiagente

O repositório usa Spec-Driven Development no padrão **GitHub Spec Kit**. Os invariantes ficam em `.specify/memory/constitution.md`, os templates em `.specify/templates/` e as fases como skills em `.claude/skills/speckit-*` (specify → plan → tasks → implement).

- `.specify/memory/constitution.md` reúne os princípios não-negociáveis (P1–P9).
- `AGENTS.md` é o contrato comum para Codex, Claude Code, Devin e humanos.
- `CLAUDE.md` apenas adapta o Claude Code para carregar o contrato comum.
- `specs/000-repo-foundation/` descreve o baseline atual do produto em `spec.md`, `plan.md`, `tasks.md` e `handoff.md`.
- Specs de domínio vivem em `specs/NNN-<slug>/` (catálogo em `specs/README.md`); specs absorvidas ficam congeladas em `specs/_legacy/`.
- `.agents/skills/` guarda procedimentos por bounded context, sem scripts executáveis por padrão.
- `docs/delivery-checklist.md` define o checklist obrigatório que deve acompanhar entregas relevantes.

Mudanças relevantes devem nascer de uma spec existente ou criar `specs/<slug-da-feature>/` quando o escopo exceder ajuste pontual. Quando comportamento, contrato ou fluxo mudar, atualize `docs/` e `specs/` juntos.
