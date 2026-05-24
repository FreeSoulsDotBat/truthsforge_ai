# Micro-plano — Fase 1: Servidor MCP standalone (ADR-017)

**Fase**: 1 | **Spec**: [`../spec.md`](../spec.md) (RF-020, RF-021, RNF-001) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md) | **Auditoria**: [`fase-0-auditoria.md`](./fase-0-auditoria.md)

> **Depende de**: Fase 0 (gate do dono ✅) — inventário de tools (§4) e ADR-017 aprovado.

## Objetivo

Tirar as operações 3D de dentro do backend e colocá-las atrás de um **servidor MCP standalone aderente ao protocolo**, com transport **HTTP streamable/SSE + autenticação por token**, **local-first**. O backend do produto passa a ser **um cliente** entre outros possíveis (ex.: Claude com conector). O executor real continua sendo o `FusionDesktopAdapter` (Autodesk Fusion MCP Server via HTTP / add-in loopback / mock).

## Decisões fechadas com o dono (2026-05-24)

1. **Protocolo**: **SDK MCP oficial** (`mcp` ≥ 1.27, PyPI). Conformidade real (`initialize`/capabilities, `tools/list`, `tools/call`), melhor para clientes externos. Formaliza a dep no ADR-017 (P2 ok).
2. **Implantação**: **processo standalone** — app ASGI próprio (`app.modeling.mcp_standalone`), bind **loopback** por padrão, entrypoint `python -m app.modeling.mcp_standalone`. Rodável in-process nos testes.
3. **Auth**: **token local estático** (Bearer), gerado e guardado em `modeling_dir/mcp_server_token`; loopback default; remoto só via VPN/pareamento. Sem exposição pública ingênua (P1/RNF-001).
4. **Escopo**: **T1.1–T1.7 completo** num PR, validado contra **mock/in-process**. Smoke no Fusion real = gate do dono (fora do container).

## Arquitetura-alvo

```
cliente externo (Claude) ─┐
backend (LocalMCPClient,  ├─► [Servidor MCP standalone]  ──► FusionDesktopAdapter ──► Fusion (HTTP 27182 / add-in / mock)
   modo "mcp_http")       ┘   HTTP streamable + auth Bearer        (executor real, inalterado)
```

- **Allowlist de fonte única**: o servidor expõe `tool_registry.FUSION_TOOLS` (já exclui `run_script`). Nada fora da allowlist (P8/RF-022/RF-023).
- **Envelope preservado**: o handler `tools/call` devolve o envelope atual (`ok`, `mcp_server`, `transport`, `tool_name`, `software`, `error_code`, `retryable`, `message`, `input`, …) como **`structuredContent`** do MCP; o cliente backend o lê de volta sem regressão.
- **Schemas de tool**: Fase 1 usa `inputSchema` permissivo (`{"type":"object"}`). Schemas ricos por tool entram com o asset `tool_schemas.py` (fidelity) na Fase 2/4.

## Estrutura de arquivos (nova)

```
backend/app/modeling/mcp_standalone/
├── __init__.py        # exports
├── auth.py            # load_or_create_token / verify_token (state_dir)
├── tools.py           # build_fusion_tools() -> list[mcp.types.Tool] (do tool_registry)
├── server.py          # build_server(): Server low-level + list_tools/call_tool -> adapter
├── app.py             # create_app(token): Starlette + StreamableHTTPSessionManager + auth ASGI
├── client.py          # StandaloneMCPClient: wrapper sync do cliente MCP oficial (executor)
└── __main__.py        # entrypoint uvicorn (bind loopback)
```

Tocados: `backend/app/core/config.py` (settings), `backend/app/modeling/mcp_client.py` (modo `mcp_http`), `backend/pyproject.toml` (dep `mcp`), `docs/3d-mcp-modeling.md`, `docs/decisions.md` (ADR-017 → Aceito).

## Tarefas atômicas

- **T1.1** — `server.py`: `Server` low-level expondo `FUSION_TOOLS` (handshake + `tools/list` + `tools/call`), delegando ao `FusionDesktopAdapter` (reusa o padrão de `_build_step` do `fusion_server.py`).
- **T1.2** — `app.py` + `auth.py` + `__main__.py`: transport HTTP streamable (`StreamableHTTPSessionManager`) + middleware ASGI de auth Bearer (não-buffering, preserva SSE), bind loopback; token no `state_dir`.
- **T1.3** — `client.py` + `mcp_client.py`: modo de transporte **`mcp_http`** no `LocalMCPClient` consumindo o servidor; preserva `in_process` (mock/CI) e `stdio`.
- **T1.4** — `FusionDesktopAdapter` segue como executor (HTTP Autodesk / add-in / mock), sem regressão dos modos (RF-002).
- **T1.5** — `blender_server`/`stdio` seguem compilando + testados (congelados); `mcp_http` roteia só `fusion.*`, demais caem em `in_process`.
- **T1.6** — Testes: contrato do servidor (initialize/list/call) end-to-end via cliente MCP oficial sobre loopback real; auth (aceita/rejeita); paridade de envelope. (`test_mcp_standalone.py`.)
- **T1.7** — Docs: `docs/3d-mcp-modeling.md` (arquitetura cliente/servidor) + ADR-017 → **Aceito**.

## Contratos / invariantes

- Envelope de resposta preserva os campos atuais; cliente reconstrói o dict do `structuredContent`.
- Allowlist de fonte única (`tool_registry.py`); servidor não expõe nada fora dela.
- Sem script livre/shell exposto (RF-023); `run_script` continua fora.
- Auth obrigatória em toda conexão; loopback default (P1/RNF-001). Fecha o gap de auth do caminho 27182 **no nível do servidor exposto** (o hop interno adapter→27182 é endereçado junto ao ADR-019/Fase 2).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest` (contrato + auth + cliente) no venv `backend/.venv`.
- Docs: `pnpm --filter @truths-forge/docs build` se `docs/` mudar.
- Cross-links válidos.
- **Gate do dono (Fusion real)**: (1) cliente externo (ex.: Claude) conecta ao servidor autenticado, lista e invoca ≥1 tool; (2) smoke das tools confiadas (`open_design→create_sketch→add_rectangle→extrude_profile→validate_printability→export_stl`) no Fusion real, capturando trace_id.

## Riscos

- **Auth/exposição mal feita** → vazamento. Mitigação: loopback default + token + sem rota pública; middleware ASGI testado (aceita/rejeita).
- **Quebra de paridade de envelope** ao trocar protocolo → regressão silenciosa. Mitigação: testes comparando o envelope reconstruído com o formato atual.
- **API do SDK version-sensitive** → fixar `mcp` em faixa compatível; teste end-to-end pega quebra de contrato.
- **Hop extra** (backend→servidor→adapter→Fusion) adiciona latência. Aceitável; é o preço do desacoplamento (ADR-017).

## Definição de pronto (Fase 1)

- [x] Servidor MCP standalone aderente ao protocolo (SDK oficial), HTTP streamable + auth, local-first. (`app/modeling/mcp_standalone/`)
- [x] Backend consome via modo `mcp_http`; `in_process`/`stdio` preservados para CI. (`mcp_client.py`)
- [x] Allowlist de fonte única; envelope sem regressão. (`run_script` nunca exposto; testes de paridade)
- [x] Testes verdes (`test_mcp_standalone.py`; 257 testes de modelagem passam); `docs/3d-mcp-modeling.md` + ADR-017 (Aceito) atualizados.
- [ ] **Gate do dono**: cliente externo conecta + smoke no Fusion real.
