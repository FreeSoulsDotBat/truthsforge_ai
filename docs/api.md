# API Inicial

## Saude e status

- `GET /health`
- `GET /api/server/status`

## Chat

- `GET /api/chat/sessions`
- `POST /api/chat/sessions`
- `POST /api/chat/stream`

`/api/chat/stream` retorna SSE com eventos:

- `meta`: ids da sessao e mensagem.
- `token`: fragmento de texto.
- `done`: conclusao do stream.

## Configuracao

- `GET /api/models`
- `POST /api/models`
- `GET /api/cost/policy`
- `POST /api/cost/policy`
- `GET /api/cost/usage`
- `GET /api/settings/providers`
- `PUT /api/settings/providers/{provider}/api-key`
- `DELETE /api/settings/providers/{provider}/api-key`

## Dominios

- `GET /api/agents`
- `POST /api/agents`
- `GET /api/prompts`
- `POST /api/prompts`
- `GET /api/documents`
- `POST /api/documents`
- `POST /api/documents/text`
- `POST /api/documents/search`
- `GET /api/audit/events`

`/api/documents/text` salva texto/Markdown em `.local/files`, faz chunking e indexa no Qdrant. `/api/documents/search` consulta o indice vetorial inicial.

## Modelagem 3D

- `GET /api/3d/capabilities`
- `GET /api/3d/sessions`
- `POST /api/3d/sessions/start`
- `GET /api/3d/plans`
- `POST /api/3d/plans`
- `POST /api/3d/plans/{plan_id}/approve`
- `POST /api/3d/plans/{plan_id}/execute`
- `POST /api/3d/steps/{step_id}/approve`
- `GET /api/3d/snapshots`
- `POST /api/3d/snapshots`

O MVP do modulo 3D usa MCP local em modo mock: gera plano estruturado para Blender/Fusion, exige aprovacao humana para mutacoes e registra a chamada que sera enviada ao adapter real quando o add-on/add-in local existir.

## OpenAPI

O schema fica em `/openapi.json`. O script `backend/scripts/export_openapi.py` exporta o JSON para o frontend quando o ambiente Python estiver instalado.
