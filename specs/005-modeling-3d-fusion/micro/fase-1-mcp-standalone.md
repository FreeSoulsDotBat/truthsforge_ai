# Micro-plano — Fase 1: Servidor MCP standalone (ADR-017)

**Fase**: 1 | **Spec**: [`../spec.md`](../spec.md) (RF-020, RF-021, RNF-001) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> **Depende de**: Fase 0 (gate do dono) — em especial do inventário de tools (T0.6) e do ADR-017 aprovado. Itens marcados _(saída da Fase 0)_ se concretizam com a auditoria.

## Objetivo

Tirar as operações 3D de dentro do backend e colocá-las atrás de um **servidor MCP standalone aderente ao protocolo**, com transport **HTTP/SSE + autenticação**, **local-first**. O backend do produto passa a ser **um cliente** entre outros possíveis (ex.: Claude com conector personalizado). O executor real continua sendo o `FusionDesktopAdapter` (Autodesk Fusion MCP Server via HTTP / add-in loopback / mock).

## Estado atual (ponto de partida)

- `backend/app/modeling/mcp_servers/` — subconjunto JSON-RPC 2.0 sobre **stdio** (`protocol.py`, `_server_base.py`, `fusion_server.py`, `blender_server.py`). O próprio `protocol.py` antecipa troca por SDK MCP oficial.
- `mcp_client.py` + `stdio_client.py` — caminho de cliente interno (stdio).
- `fusion_adapter.py` (`FusionDesktopAdapter`, `FUSION_TOOLS`) — executor; já fala HTTP com o Fusion MCP Server da Autodesk ou com o add-in.
- `tool_registry.py` — allowlist de fonte única.

## Decisões-chave (a fixar no ADR-017)

1. **Protocolo**: adotar SDK MCP oficial (Python) para conformidade (`initialize`/capabilities, `tools/list`, `tools/call`) **ou** estender o subconjunto atual. _Recomendação a validar:_ adotar o SDK oficial — o `protocol.py` já prevê isso e reduz dívida de paridade.
2. **Transport**: HTTP/SSE (ou streamable HTTP do MCP) além do stdio (stdio mantido para dev/test).
3. **Auth**: token/credencial local; **loopback por padrão**, acesso remoto só via VPN/pareamento (Tailscale/WireGuard). Sem exposição pública ingênua (P1/RNF-001).
4. **Fronteira de tools**: derivar de `tool_registry.py` (fonte única) o conjunto exposto — **somente as tools confiadas na auditoria** _(saída da Fase 0)_.
5. **Cliente backend**: substituir o caminho interno (`mcp_client`/`stdio_client`) por cliente MCP apontando ao servidor standalone, com fallback in-process para teste/mock.
6. **Blender**: servidor Blender permanece **compilando e testado**, sem features novas (congelado). Exposição foca Fusion.

## Tarefas atômicas

- **T1.1** — Implementar/Integrar o servidor MCP standalone (handshake + `tools/list` + `tools/call`), expondo as tools confiadas a partir de `tool_registry.py`. _(saída da Fase 0: lista de tools)_
- **T1.2** — Adicionar transport HTTP/SSE + camada de autenticação (token), com bind local-first por padrão.
- **T1.3** — Refatorar o backend para consumir o servidor como **cliente MCP** (substituindo o caminho stdio interno), preservando o fallback mock/in-process para CI.
- **T1.4** — Manter `FusionDesktopAdapter` como executor por trás do servidor (HTTP Autodesk / add-in / mock), sem regressão dos modos mock/ausente/real/erro (RF-002).
- **T1.5** — Garantir `blender_server` compilando + testes (congelado).
- **T1.6** — Testes: contrato do servidor (handshake/list/call), auth (aceita/rejeita), e paridade de envelope (`ok`, `error_code`, `transport`) com o comportamento atual. Atualizar/relocar `test_mcp_stdio.py`, `test_fusion_bridge.py`.
- **T1.7** — Docs: atualizar `docs/3d-mcp-modeling.md` (nova arquitetura cliente/servidor) e registrar ADR-017 como aceito.

## Contratos / invariantes

- Envelope de resposta de tool preserva os campos atuais (`ok`, `mcp_server`, `transport`, `tool_name`, `software`, `error_code`, `retryable`, `message`, `input`).
- Allowlist continua de **fonte única** (`tool_registry.py`); o servidor não expõe nada fora dela (P8/RF-022).
- Sem script livre/shell exposto pelo servidor (RF-023).

## Validação

- Backend: `ruff format --check`, `ruff check`, `pytest` (contrato do servidor + auth + cliente).
- Docs: `pnpm --filter @truths-forge/docs build` se `docs/` mudar.
- Cross-links válidos.
- **Gate do dono (Fusion real)**: (1) conectar um cliente externo (ex.: Claude via conector) ao servidor autenticado, listar e invocar ao menos uma tool; (2) smoke das tools confiadas no Fusion real, capturando trace_id.

## Riscos

- **Auth/exposição mal feita** → vazamento. Mitigação: loopback default + token + sem rota pública; revisão de segurança antes do gate.
- **Quebra de paridade de envelope** ao trocar protocolo → regressão silenciosa no consumo. Mitigação: testes de contrato comparando com o formato atual.
- **SDK oficial vs subconjunto** pode trazer dependência nova → decidir no ADR-017 com P2 em mente (sem troca de stack; adição de lib é aceitável e formalizada).

## Definição de pronto (Fase 1)

- [ ] Servidor MCP standalone aderente ao protocolo, com HTTP/SSE + auth, local-first.
- [ ] Backend consome como cliente; mock/in-process preservado para CI.
- [ ] Allowlist de fonte única; envelope sem regressão.
- [ ] Testes verdes; `docs/3d-mcp-modeling.md` + ADR-017 atualizados.
- [ ] Gate do dono: cliente externo conecta + smoke no Fusion real.
