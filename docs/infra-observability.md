# Observabilidade da infra local

Este ambiente sobe GUIs basicas para inspecionar os dados do MVP sem sair do Docker Compose.

## URLs

- App web: `http://127.0.0.1:5173`
- Backend: `http://127.0.0.1:8000`
- OpenAPI: `http://127.0.0.1:8000/docs`
- Documentacao Docusaurus: `http://127.0.0.1:3000`
- Postgres UI/pgAdmin: `http://localhost:8080`
- Redis/Valkey UI: `http://127.0.0.1:8081`
- Qdrant dashboard: `http://127.0.0.1:6333/dashboard`

## Postgres com pgAdmin

pgAdmin substitui o Adminer porque oferece uma experiencia mais proxima de MySQL Workbench: navegador de servidores, schemas, tabelas, editor SQL, visualizacao de dados e propriedades do banco.

Use estes dados para entrar no pgAdmin:

- Email: valor de `PGADMIN_DEFAULT_EMAIL` em `infra/.env`
- Senha: valor de `PGADMIN_DEFAULT_PASSWORD` em `infra/.env`

O email default usa dominio `.dev` porque o pgAdmin rejeita dominios locais especiais como `.local` na conta inicial.

Use `localhost:8080` para abrir a UI. Em algumas instalacoes Windows, `127.0.0.1:8080` pode estar ocupado por servicos locais do PostgreSQL/EnterpriseDB. Se isso acontecer, ajuste `PGADMIN_PORT` em `infra/.env` para uma porta livre, por exemplo `PGADMIN_PORT=18080`, e rode `dev.ps1` novamente.

Se o login disser usuario ou senha invalidos depois de mudar `infra/.env`, rode `.\scripts\reset-pgadmin.ps1`. O pgAdmin guarda usuarios em um volume Docker persistente e nao reaplica automaticamente `PGADMIN_DEFAULT_EMAIL`/`PGADMIN_DEFAULT_PASSWORD` quando o volume ja existe.

O mesmo script tambem registra automaticamente o servidor `Truth's Forge Postgres` no painel esquerdo. Ele usa um arquivo `pgpass` dentro do volume do pgAdmin para permitir a conexao com o Postgres local sem reimplementar uma senha na UI do app.

Se precisar registrar manualmente, use estes campos:

- Nome: `Truth's Forge Postgres`
- Host: `postgres`
- Porta: `5432`
- Maintenance database: valor de `POSTGRES_DB` em `infra/.env`
- Usuario: valor de `POSTGRES_USER` em `infra/.env`
- Senha: valor de `POSTGRES_PASSWORD` em `infra/.env`

No pgAdmin, navegue em `Servers > Truth's Forge Postgres > Databases > <database> > Schemas > public > Tables` para ver tabelas e dados.

As tabelas principais hoje sao:

- `model_configs`
- `agents`
- `prompts`
- `projects`
- `project_folders`
- `chat_sessions`
- `chat_messages`
- `documents`
- `platform_files`
- `knowledge_categories`
- `knowledge_bases`
- `knowledge_base_documents`
- `audit_events`
- `cost_policy`
- `import_jobs`
- `modeling_sessions`
- `modeling_plans`
- `modeling_snapshots`
- `modeling_tool_calls`
- `modeling_printability_reports`
- `modeling_model_versions`
- `modeling_trace_events` (criada sob demanda pela `PostgresStore`, não via migração)

Os dados ficam em payloads `JSONB` para acelerar o MVP sem travar a modelagem final.

## Redis/Valkey com Redis Commander

Abra `http://127.0.0.1:8081`. Ele ja vem apontando para `valkey:6379`.

Por padrao (`TRUTHS_FORGE_QUEUE_BACKEND=memory`) as filas de importacao do ChatGPT e indexacao de arquivos rodam em memoria no processo FastAPI. Defina `TRUTHS_FORGE_QUEUE_BACKEND=redis` (ou `valkey`) para usar o servidor em `redis_url` (`job_queue.RedisJobQueue`, sorted set + dedup set, compartilhavel entre replicas) — ai as listas/chaves de status aparecem aqui.

## Qdrant

Abra `http://127.0.0.1:6333/dashboard`.

Colecoes esperadas no estagio atual:

- `truths_forge_documents`: chunks de documentos indexados pelo RAG inicial.

O dashboard permite ver colecoes, pontos, payloads e buscas exploratorias.

## OpenAI

O backend le `OPENAI_API_KEY` de `backend/.env` dentro do container. Nao coloque chaves reais nos arquivos `.env.example`.

O modelo padrao foi configurado no registry local como:

- `id`: `openai/default-chat`
- `provider_model_id`: pode ser editado no Model Registry; no dev store atual o default inicial e `gpt-4o`
- custo input/output: **nao sao semeados** pelo dev store (ficam `None`); defina-os no Model Registry (o Cost Governor exige preco antes de usar o modelo)

Esses valores alimentam o Cost Governor local. O billing real continua sendo o da OpenAI.

A politica local de orcamento usa `monthly_budget_brl`, com default **R$200** (`TRUTHS_FORGE_MONTHLY_BUDGET_BRL`); a conversao simples do MVP e `1 USD = 5 BRL`.
