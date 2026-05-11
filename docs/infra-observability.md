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

Use `localhost:8080` para abrir a UI. Em algumas instalacoes Windows, `127.0.0.1:8080` pode estar ocupado por servicos locais do PostgreSQL/EnterpriseDB.

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
- `chat_sessions`
- `chat_messages`
- `documents`
- `audit_events`
- `cost_policy`

Os dados ficam em payloads `JSONB` para acelerar o MVP sem travar a modelagem final.

## Redis/Valkey com Redis Commander

Abra `http://127.0.0.1:8081`. Ele ja vem apontando para `valkey:6379`.

Hoje o Redis/Valkey esta preparado para cache/fila, mas ainda nao ha fila de producao intensa. Quando workers de OCR, indexacao e jobs longos entrarem, listas, streams ou chaves de status aparecerao ali.

## Qdrant

Abra `http://127.0.0.1:6333/dashboard`.

Colecoes esperadas no estagio atual:

- `truths_forge_documents`: chunks de documentos indexados pelo RAG inicial.

O dashboard permite ver colecoes, pontos, payloads e buscas exploratorias.

## OpenAI

O backend le `OPENAI_API_KEY` de `backend/.env` dentro do container. Nao coloque chaves reais nos arquivos `.env.example`.

O modelo padrao foi configurado no registry local como:

- `id`: `openai/default-chat`
- `provider_model_id`: `gpt-5-mini`
- custo input: `0.25` USD por 1M tokens
- custo output: `2.00` USD por 1M tokens

Esses valores alimentam o Cost Governor local. O billing real continua sendo o da OpenAI.

Como o credito inicial informado foi de US$20, a politica local foi ajustada para `R$100` usando a conversao simples atual do MVP: `1 USD = 5 BRL`.
