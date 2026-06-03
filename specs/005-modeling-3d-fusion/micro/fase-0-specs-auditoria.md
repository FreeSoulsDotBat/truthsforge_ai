# Micro-plano — Fase 0: Specs + Auditoria

**Fase**: 0 | **Spec**: [`../spec.md`](../spec.md) | **Macro**: [`../plan.md`](../plan.md) | **Índice**: [`../tasks.md`](../tasks.md)

> Fase **sem código de produto novo**. Entrega: a tríade reescrita (já feita), o inventário de auditoria do v3 e os rascunhos de ADR. Encerra no **gate do dono**.

## Objetivo

Estabelecer a base do v4: specs reescritas no modelo macro/micro (só-3D) e um **veredito honesto** sobre o que existe no código v3 — o que dá para confiar e o que precisa reescrever — para que as fases seguintes evoluam sobre terreno conhecido, não sobre suposição.

## Entregáveis

1. `spec.md`, `plan.md`, `tasks.md` reescritos. _(feito neste passo)_
2. `micro/fase-0-specs-auditoria.md` — este arquivo. _(feito)_
3. **Inventário de auditoria** do `backend/app/modeling/` (novo: `micro/fase-0-auditoria.md`) com veredito por peça.
4. **Status real-Fusion das tools** do adapter (seção no inventário).
5. **Rascunho ADR-017** (servidor MCP standalone, local-first + auth) em `docs/decisions.md`.
6. **Rascunho ADR-018** (reabrir assemblies / cobertura "todo o Design") em `docs/decisions.md`.

## Tarefas atômicas

### Auditoria de código (veredito confiar / reescrever)

- **T0.5** — Para cada módulo de `backend/app/modeling/`, registrar: responsabilidade, cobertura de teste atual, dependências, e veredito (`confiar` / `reescrever` / `evoluir`) com 1 linha de justificativa:
  - `tool_registry.py` (allowlist de fonte única — base de tudo)
  - `planner.py` + `planner_service.py` (geração de plano)
  - `policy.py` (risco/aprovação)
  - `executor.py` (execução de passos — vira base do loop)
  - `chat_orchestrator.py` + `chat_state.py` (state machine do chat 3D)
  - `discovery.py` (descoberta/clarificação)
  - `fusion_adapter.py` + `fusion_mcp_scripts.py` (~50 tools)
  - `mcp_servers/` (`fusion_server.py`, `blender_server.py`, `_server_base.py`, `protocol.py`) + `mcp_client.py` + `stdio_client.py` (base do servidor standalone)
  - `attachment_analyzer.py` (vision + análise headless)
  - `observability.py` (base da observabilidade forte)
  - `snapshot_service.py` (snapshots/rollback)
  - `artifacts.py` + `printability.py` (export + printability)
  - `service.py` (facade)
- **T0.6** — Mapear as ~50 tools do adapter Fusion marcando: `validada-no-fusion-real` / `nunca-rodada` / `version-sensitive` (cruzar com `adapter-gaps-roadmap.md` G5 e `handoff.md`). Identificar as candidatas de smoke da Fase 1.
- **T0.6b** — **Absorver o fidelity-roadmap**: auditar `agent_loop.py`, `tool_schemas.py` e `planner.build_correction_context` (hoje não-commitados no worktree `master`), confirmar testes, e planejar a **integração na branch v4** (convergência de branches — ver `plan.md` › Pendências). Marcar `fidelity-roadmap.md` como insumo absorvido pelo v4.

### Decisões formais (ADRs)

- **T0.7** — Rascunhar **ADR-017**: servidor MCP standalone — protocolo, transport (HTTP/SSE), autenticação, exposição local-first (loopback/VPN/pareamento), backend como cliente. Referenciar P1/P2.
- **T0.8** — Rascunhar **ADR-018**: reabrir a decisão "single-body" (`g4-assemblies-decision.md`) para a cobertura-alvo "todo o Design"; consequências no data model do plano, selectors/refs, UI do card, printability/export por componente. Referenciar P8; marcar `g4-assemblies-decision.md` como superado por este ADR.
- **T0.9** — Rascunhar **ADR-019**: fronteira de segurança do script Python backend-owned enviado via `featureType:"script"` (`fusion_adapter.py`) — por que respeita RF-023, limites e auditoria (DT-009).

### Reconciliação documental e ambiente

- **T0.10** — Catalogar as inconsistências de doc v2/v3→v4 achadas na varredura (ex.: `safe_auto` e gate "sempre PARA" em `docs/3d-mcp-modeling.md`; endpoints removidos em `docs/api.md`; 27182/stdio como legado; caminho pessoal vazado em `docs/local-dev.md:5`; ADR-012/013 a superar) → backlog para a Fase final.
- **T0.11** — **Pós-merge `homolog-new-ui`→`master`**: ler a nova UI e registrar o alinhamento necessário em `apps/web/src/features/modeling-3d/` (RNF-009). _(Bloqueado até o merge.)_

### Fechamento

- **T0.9** — **Gate Fase 0**: apresentar inventário + ADRs ao dono. Só após o aval, escrever o `micro/fase-1-*.md` e iniciar a Fase 1.

## Validação desta fase

- Cross-links: todos os caminhos citados em `spec.md`/`plan.md`/`tasks.md`/este micro existem.
- Docs: se `docs/decisions.md` mudar, `pnpm --filter @truths-forge/docs build` (quando aplicável).
- **Sem gates de código** (não há código de produto novo nesta fase).
- **Gate do dono**: aprovação do inventário de auditoria e dos rascunhos ADR-017/018.

## Riscos

- Auditoria pode revelar que mais peças precisam reescrita do que o esperado → ajusta o esforço das fases seguintes; é justamente o objetivo desta fase descobrir isso cedo.
- ADR-018 pode mudar bastante o data model → por isso a Fase 8 (assemblies) é a última das ondas de cobertura, depois do núcleo estável.

## Definição de pronto (Fase 0)

- [x] Inventário de auditoria escrito com veredito por peça.
- [x] Status real-Fusion das tools mapeado.
- [x] ADR-017, ADR-018 e ADR-019 rascunhados.
- [x] Inconsistências de doc catalogadas para a Fase final.
- [x] Dono aprovou (gate) → libera Fase 1 (2026-05-24).
