# API Inicial

## Saude e status

- `GET /health`
- `GET /api/server/status`

## Chat

- `GET /api/chat/sessions`
- `POST /api/chat/sessions`
- `GET /api/chat/sessions/{session_id}`
- `DELETE /api/chat/sessions/{session_id}`
- `POST /api/chat/sessions/{session_id}/move`
- `PUT /api/chat/sessions/{session_id}/context`
- `POST /api/chat/sessions/{session_id}/attachments/analyze`
- `POST /api/chat/stream`

`/api/chat/sessions/{session_id}/attachments/analyze` dispara a análise profunda
de um anexo num chat 3D (vision para imagens, Blender headless para arquivos 3D).

`/api/chat/stream` retorna SSE. Eventos centrais:

- `meta`: ids da sessao e mensagem.
- `token`: fragmento de texto.
- `done`: conclusao do stream.

Conforme o modo da execução também ocorrem `runtime_status`, `error`,
`reasoning_summary` e, em chats 3D, `modeling_plan` (plano/edição, com `trace_id`)
e `session_title`.

O backend valida o projeto ativo antes de criar ou atualizar a sessão: se o
agente principal, o agente solicitado ou agentes de apoio não tiverem acesso ao
`project_id`, a chamada retorna `403`. O contexto RAG da execução usa o projeto
ativo validado e as bases habilitadas para aquele projeto/agente.

Chamadas de chat, custos, uso de documentos em contexto e decisões de agentes
devem permanecer auditáveis conforme `specs/060-cost-audit-governance/`.

## Configuracao

- `GET /api/models`
- `POST /api/models`
- `GET /api/models/providers/{provider}`
- `GET /api/cost/policy`
- `POST /api/cost/policy`
- `GET /api/cost/usage`
- `GET /api/settings/providers`
- `PUT /api/settings/providers/{provider}/api-key`
- `DELETE /api/settings/providers/{provider}/api-key`

## Dominios

- `GET /api/agents`
- `POST /api/agents`
- `PUT /api/agents/{agent_id}`
- `GET /api/prompts`
- `POST /api/prompts`
- `GET /api/projects`
- `POST /api/projects`
- `PUT /api/projects/{project_id}`
- `GET /api/projects/folders`
- `POST /api/projects/folders`
- `PUT /api/projects/folders/{folder_id}`
- `DELETE /api/projects/folders/{folder_id}`
- `GET /api/documents`
- `GET /api/documents/page`
- `POST /api/documents/batch`
- `GET /api/documents/categories`
- `POST /api/documents/categories`
- `PUT /api/documents/categories/{category_id}`
- `POST /api/documents`
- `POST /api/documents/text`
- `POST /api/documents/from-file`
- `POST /api/documents/search`
- `GET /api/knowledge-bases`
- `POST /api/knowledge-bases`
- `PUT /api/knowledge-bases/{knowledge_base_id}`
- `DELETE /api/knowledge-bases/{knowledge_base_id}`
- `GET /api/knowledge-bases/documents`
- `GET /api/knowledge-bases/{knowledge_base_id}/documents`
- `POST /api/knowledge-bases/{knowledge_base_id}/documents`
- `PUT /api/knowledge-bases/documents/{item_id}`
- `DELETE /api/knowledge-bases/{knowledge_base_id}/documents/{document_id}`
- `GET /api/files`
- `GET /api/files/page`
- `GET /api/files/indexing/status`
- `POST /api/files/upload`
- `GET /api/files/{file_id}/content`
- `PUT /api/files/{file_id}`
- `DELETE /api/files/{file_id}`
- `POST /api/imports/chatgpt`
- `POST /api/imports/chatgpt/from-file/{file_id}`
- `GET /api/imports/chatgpt/jobs`
- `GET /api/imports/chatgpt/jobs/{job_id}`
- `GET /api/audit/events`
- `GET /api/tools`
- `GET /api/tools/{tool_id}/permission`
- `POST /api/tools/execute`

`/api/documents/text` salva texto/Markdown em `.local/files`, faz chunking e indexa no Qdrant. `/api/documents/from-file` cria/atualiza documento a partir de um `PlatformFile` e enfileira indexacao. `/api/documents/search` combina busca vetorial no Qdrant com filtros por base/projeto/pasta/categoria/tags/tipo e fallback por metadados quando necessario.

## Modelagem 3D

- `GET /api/3d/capabilities`
- `GET /api/3d/sessions`
- `POST /api/3d/sessions/start`
- `GET /api/3d/plans`
- `GET /api/3d/plans/{plan_id}`
- `POST /api/3d/plans/{plan_id}/approve`
- `PATCH /api/3d/plans/{plan_id}` — edita o plano antes da aprovação
- `POST /api/3d/plans/{plan_id}/execute`
- `POST /api/3d/plans/{plan_id}/rollback` — desfaz a última edição (timeline)
- `GET /api/3d/plans/{plan_id}/diagnostics` — bundle plano + tool calls + trace
- `GET /api/3d/snapshots`
- `POST /api/3d/snapshots`
- `GET /api/3d/snapshots/{snapshot_id}`
- `POST /api/3d/snapshots/{snapshot_id}/restore`
- `GET /api/3d/tool-calls`
- `POST /api/3d/validate/printability`
- `GET /api/3d/printability-reports`
- `GET /api/3d/model-versions`
- `GET /api/3d/plans/{plan_id}/trace`
- `GET /api/3d/traces/{trace_id}`
- `POST /api/3d/traces/events`

> Removidos no v4 (ADR-013, Onda 2.11): `POST /api/3d/plans` (todo plano nasce no
> chat) e `POST /api/3d/steps/{step_id}/approve` (a aprovação é global no plano).

O modulo 3D usa MCP local com fallback mock. O Blender executa ferramentas allowlistadas em background quando `TRUTHS_FORGE_BLENDER_EXECUTABLE` aponta para o executavel. O Fusion 360 usa primeiro o Fusion MCP Server local do aplicativo em `TRUTHS_FORGE_FUSION_MCP_URL` (`http://127.0.0.1:27182/mcp` por padrao) e cai para o bridge desktop legado por discovery file/socket loopback quando necessario. Mesmo no MCP oficial, o backend so envia scripts determinísticos para tools `fusion.*` allowlistadas; sem adapter conectado, as chamadas retornam envelopes auditaveis de mock/erro seguro.

## OpenAPI

O schema fica em `/openapi.json`. O script `backend/scripts/export_openapi.py` exporta o JSON para o frontend quando o ambiente Python estiver instalado.
