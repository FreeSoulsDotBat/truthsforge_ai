# Tech debt

Itens conhecidos de dívida técnica que ficaram **fora do escopo** de uma entrega,
com contexto suficiente para retomar. Atualize/remova conforme forem resolvidos.

## Origem: revisão de bugs/flags do PR #46 (2026-06)

A revisão multi-agente do PR #46 levantou 80 achados (0 críticos, 4 HIGH, 19 médios,
57 low). A grande maioria foi corrigida no próprio PR. Os itens abaixo são os
**resíduos** — correções parciais (o fix mínimo entrou; a parte estrutural ficou para
depois) e uma decisão de produto adiada.

### Correções parciais (parte estrutural pendente)

| Achado | Arquivo | O que entrou no PR | O que falta (dívida) |
| --- | --- | --- | --- |
| `llm-5` | `backend/app/llm_gateway/providers.py` | Teto do loop de polling do `deep_research` virou env `TRUTHS_FORGE_DEEP_RESEARCH_MAX_POLLS` (default 360). | Quebrar o loop em **desconexão do cliente** (exige plumbing do `Request` na rota) e reavaliar o default de ~30 min. |
| `mdl-adapters-008` | `backend/app/modeling/stdio_client.py` | Lado **cliente** ressincroniza o framing stdio (pula linhas não-JSON-RPC / id divergente). | Endurecer o lado **servidor** (`mcp_servers/_server_base.py`): redirecionar `sys.stdout` não-protocolar para stderr, garantindo pureza do stdout. Adicionar timeout geral de resposta no `call()`. |
| `mdl-exec-7` | `backend/app/modeling/agent_loop.py` | Guarda contra event-loop ativo em `run_plan_with_optional_loop` (RuntimeError claro em vez de erro silencioso). | Fix canônico em `planner.build_corrector`/`correct_step`: detectar loop ativo e despachar para worker thread (em vez de só falhar cedo). |
| `api-rest-001` | `backend/app/api/routes/projects.py` | `except` do cascade ampliado: falha de uma sessão é logada, não derruba a pasta inteira (500). | Hoist dos scans `O(N²→N)` (`other_sessions_file_ids`/`platform_files`/`documents`) para fora do loop — exige mudar a assinatura de `delete_chat_session_with_files` em `chat/session_cleanup.py`. |
| `api-rest-003` | `backend/app/api/routes/audit.py`, `imports.py` | `limit/offset` (max 200) aplicados na rota (`/audit/events`, `/imports/chatgpt/jobs`). | Empurrar o `LIMIT` para a query do store (`postgres_store`/`dev_store`) — hoje ainda materializa a tabela inteira antes de fatiar. |
| `workers-gov-6` | `backend/app/chat/session_cleanup.py` | Scan `O(sessões×msgs)` só roda quando a sessão referencia arquivos. | Índice `file_id → session_ids` no store para eliminar o full scan a cada deleção. |
| `fe-chat-2` | `apps/web/src/features/chat/components/ImagePreview.tsx` | Refcount de scroll-lock entre instâncias de `ImagePreview`. | Hook compartilhado `useBodyScrollLock` para coordenar o scroll-lock **entre overlays distintos** (ImagePreview + ChatTitleRequiredDialog + futuros). |

### Decisão de produto adiada

- **`api-rest-005` (auth nos endpoints de segredo/tool-exec):** decidido **manter sem auth**
  (design local-first) e **documentar o pressuposto loopback-only** (feito em `settings.py`
  e `tools.py`). **Dívida:** se/quando o backend for exposto além do loopback
  (`public_base_url` não-loopback, acesso mobile via Tailscale/WireGuard anunciado no
  `ServerStatus`), adicionar um **gate** (token local/Origin) nas rotas de gravação de
  API key e em `POST /tools/execute` **antes** da exposição.
